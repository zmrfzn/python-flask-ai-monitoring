"""
FastAPI chat server with AI agent capabilities using AutoGen and MCP tools.

This module provides a chat API server that integrates with:
- AutoGen for AI agent orchestration
- MCP (Model Context Protocol) for tool integration
- OpenAI for language model capabilities
- New Relic for application monitoring

The server exposes endpoints for health checks and chat interactions.
"""

import asyncio
import logging
import os
import ssl
import time
import uuid
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables FIRST before any other imports
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

# Initialize New Relic BEFORE importing any frameworks (only if enabled)
import newrelic.agent

nr_enabled = os.getenv("NEW_RELIC_ENABLED", "0")
if nr_enabled == "1":
    newrelic.agent.initialize()
    newrelic.agent.register_application(timeout=10)
else:
    sys.stderr.write(f"[NR-INIT] New Relic disabled (NEW_RELIC_ENABLED={nr_enabled})\n")
    sys.stderr.flush()

from contextlib import asynccontextmanager
from dataclasses import dataclass

from typing import Any, Dict, Optional, Sequence
import click
import httpx
import uvicorn
from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_ext.tools.mcp import (
    StreamableHttpMcpToolAdapter,
    StreamableHttpServerParams,
)
from fastapi import FastAPI
from pydantic import BaseModel

from util.llm_utils import get_llm_models, get_next_llm_model

# Note: Logging configuration is done in __main__ after New Relic initialization
# to ensure New Relic can properly instrument the logging framework

# Create logger (will use handlers configured in __main__)
logger = logging.getLogger("server")

# Global cache for tool adapters (initialized once on startup)
_tool_adapters_cache: Dict[str, Any] = {}
_tool_adapters_initialized: bool = False


def get_tool_hostname() -> str:
    """
    Return the tool hostname from environment variables.

    Returns:
        str: The hostname for the MCP tool service, defaults to 'localhost'.
    """
    return os.getenv("TOOL_HOSTNAME", "localhost")


def get_tool_port() -> int:
    """
    Get the tool port from environment variables.

    Returns:
        int: The port number for the MCP tool service, defaults to 8090.
    """
    return int(os.getenv("TOOL_PORT", "8090"))


def get_tool_url() -> str:
    """
    Construct the full URL for the MCP tool service.

    Returns:
        str: The complete HTTP endpoint URL for the MCP tool service.
    """
    return f"http://{get_tool_hostname()}:{get_tool_port()}/mcp"


def get_openai_base_url() -> str:
    """
    Get the OpenAI API base URL from environment variables.

    Returns:
        str: The base URL for OpenAI API calls, or empty string for default.
    """
    return os.getenv("OPENAI_BASE_URL", "")


@dataclass
class ChatData(BaseModel):
    """
    Data model for chat requests.

    Attributes:
        message: The user's chat message to be processed by the AI agent.
    """

    message: str


@click.command()
@click.option("--port", default=8080, help="Port to listen on for SSE")
def main(port: int):
    """
    Start the FastAPI chat server with AI agent capabilities.

    Args:
        port: The port number to run the server on (default: 8080).
    """
    logger.debug("Starting main() entrypoint", extra={"port": port})

    async def initialize_tool_adapters():
        """
        Initialize and cache the MCP tool adapters once on startup.

        This function is called during application startup to create the tool
        adapters once and reuse them across all chat requests, avoiding the
        overhead of repeated SSE connections and tool discovery.
        """
        global _tool_adapters_initialized  # pylint: disable=global-statement

        if _tool_adapters_initialized:
            logger.info("[initialize_tool_adapters] Already initialized, skipping")
            return

        logger.info("[initialize_tool_adapters] Starting tool adapter initialization")
        start_ts = time.time()

        # Create server params for the remote MCP service
        server_params = StreamableHttpServerParams(
            url=get_tool_url(),
            headers={"Content-Type": "application/json"},
            timeout=5,  # Connection timeout in seconds
        )

        # Retry logic with exponential backoff for connecting to tools server
        max_retries = 5
        retry_delay = 1  # Start with 1 second delay

        for attempt in range(max_retries):
            try:
                logger.info(
                    "[initialize_tool_adapters] Connecting to MCP tools",
                    extra={
                        "tool_url": get_tool_url(),
                        "attempt": attempt + 1,
                        "max_retries": max_retries,
                    },
                )

                # Create tool adapters once and cache them
                _tool_adapters_cache["calculator"] = (
                    await StreamableHttpMcpToolAdapter.from_server_params(
                        server_params, "calculator"
                    )
                )
                _tool_adapters_cache["get_weather"] = (
                    await StreamableHttpMcpToolAdapter.from_server_params(
                        server_params, "get_weather"
                    )
                )
                _tool_adapters_cache["read_file"] = (
                    await StreamableHttpMcpToolAdapter.from_server_params(
                        server_params, "read_file"
                    )
                )
                _tool_adapters_cache["get_cache_stats"] = (
                    await StreamableHttpMcpToolAdapter.from_server_params(
                        server_params, "get_cache_stats"
                    )
                )

                _tool_adapters_initialized = True
                elapsed = time.time() - start_ts

                logger.info(
                    "[initialize_tool_adapters] Tools cached successfully",
                    extra={
                        "tools": list(_tool_adapters_cache.keys()),
                        "elapsed_ms": int(elapsed * 1000),
                        "attempts": attempt + 1,
                    },
                )
                break  # Success, exit retry loop

            except (ConnectionError, TimeoutError, ValueError, Exception) as e:
                # Catch all exceptions including httpx.ConnectError, ExceptionGroup, etc.
                logger.error(
                    "Failed to initialize tool adapter (attempt %s/%s): %s",
                    attempt + 1,
                    max_retries,
                    str(e)[:200],  # Truncate long error messages
                )
                if attempt < max_retries - 1:
                    logger.warning(
                        "[initialize_tool_adapters] Connection failed, retrying",
                        extra={
                            "tool_url": get_tool_url(),
                            "attempt": attempt + 1,
                            "max_retries": max_retries,
                            "retry_delay": retry_delay,
                            "error": str(e),
                        },
                    )
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    logger.error(
                        "[initialize_tool_adapters] Failed to connect after all retries",
                        extra={
                            "tool_url": get_tool_url(),
                            "max_retries": max_retries,
                            "error": str(e),
                        },
                    )
                    raise  # Re-raise the exception after all retries exhausted

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """
        Lifespan context manager for FastAPI application startup and shutdown.

        This replaces the deprecated @app.on_event("startup") pattern.
        """
        # Log configured models for performance comparison
        available_models = get_llm_models()
        logger.info(
            "[startup] Configured LLM models for rotation",
            extra={
                "models": ",".join(available_models),
                "model_count": len(available_models),
            },
        )

        logger.info("[startup] Initializing tool adapters")
        app.state.start_time = time.time()

        await initialize_tool_adapters()
        logger.info("[startup] Application ready")
        yield
        # Shutdown logic can be added here if needed

    app = FastAPI(title="Chat API", lifespan=lifespan)

    # Add custom middleware for New Relic transaction naming and request tracking
    if nr_enabled == "1":
        from middleware import AgentRequestMiddleware, CorrelationIdMiddleware

        # Add correlation ID middleware first (innermost)
        app.add_middleware(CorrelationIdMiddleware)

        # Add request tracking middleware (outermost)
        app.add_middleware(AgentRequestMiddleware)

        logger.info("[startup] Custom middleware registered for New Relic tracking")

    async def create_agent(request_id: str, model_name: str) -> AssistantAgent:
        """
        Create an AI assistant agent with cached MCP tool adapters.

        Args:
            request_id: Unique identifier for tracking this request.
            model_name: The LLM model to use for this agent.

        Returns:
            AssistantAgent: Configured agent with calculator, weather, and file reading tools.
        """
        start_ts = time.time()
        logger.debug("[create_agent] Begin", extra={"request_id": request_id})

        # Reuse cached tool adapters
        tools: Sequence = [
            _tool_adapters_cache["calculator"],
            _tool_adapters_cache["read_file"],
            _tool_adapters_cache["get_weather"],
            _tool_adapters_cache["get_cache_stats"],
        ]

        logger.debug(
            "[create_agent] Using cached tools",
            extra={
                "request_id": request_id,
                "tools": ["calculator", "get_weather", "read_file"],
            },
        )

        # Create model client with provided model name for performance comparison
        base_url = get_openai_base_url()
        client_kwargs: Dict[str, Any] = {"model": model_name}
        if base_url:
            client_kwargs["base_url"] = base_url

        # Handle SSL verification for corporate proxies
        verify_ssl = os.getenv("HTTPX_VERIFY", "true").lower() != "false"
        if not verify_ssl:
            # Create a custom SSL context that doesn't verify certificates
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            http_client = httpx.AsyncClient(verify=False)
            client_kwargs["http_client"] = http_client
            logger.warning("SSL verification disabled - only use this in development!")

        # Log available models and current selection for New Relic tracking
        available_models = get_llm_models()
        logger.info(
            "Initializing OpenAIChatCompletionClient with model rotation",
            extra={
                "request_id": request_id,
                "model": model_name,
                "available_models": ",".join(available_models),
                "model_count": len(available_models),
                "base_url": base_url or "default",
            },
        )

        # Add New Relic custom attributes for model tracking
        newrelic.agent.add_custom_attribute("llm_model", model_name)
        newrelic.agent.add_custom_attribute("model_count", len(available_models))

        model_client = OpenAIChatCompletionClient(**client_kwargs)

        # Create a single agent with access to all tools
        agent = AssistantAgent(
            name="assistant",
            model_client=model_client,
            tools=tools,  # type: ignore
            reflect_on_tool_use=True,
            system_message=(
                "You are a helpful AI assistant with access to the following tools:\n"
                "1. calculator - Perform arithmetic operations (add, subtract, multiply, divide)\n"
                "2. get_weather - Get current weather information for any city\n"
                "3. read_file - Read contents of files from the data directory\n\n"
                "4. get_cache_stats - Get statistics about the weather cache\n"
                "Analyze the user's request and use the appropriate tool(s) to help them. "
                "You can use multiple tools if needed to complete the task."
            ),
        )
        elapsed = time.time() - start_ts
        logger.debug(
            "[create_agent] Complete",
            extra={"request_id": request_id, "elapsed_ms": int(elapsed * 1000)},
        )
        return agent

    @app.get("/health")
    async def health_check():
        """Health check endpoint to verify the server is running."""
        # Set New Relic transaction name
        newrelic.agent.set_transaction_name("HealthCheck")
        return {"status": "healthy"}

    @app.post("/chat")
    async def chat(request: ChatData):
        """
        Handle chat requests by processing user messages through the AI agent.

        Args:
            request: ChatData containing the user's message.

        Returns:
            dict: Response containing request_id, message, response text, and duration.
        """
        # Set New Relic transaction name
        newrelic.agent.set_transaction_name("Chat")

        request_id = str(uuid.uuid4())
        # Get New Relic trace_id for feedback correlation
        trace_id = newrelic.agent.current_trace_id()
        
        # Optional: Add custom attributes for filtering/grouping in New Relic
        newrelic.agent.add_custom_attribute("request_id", request_id)
        newrelic.agent.add_custom_attribute("message_length", len(request.message))

        t0 = time.time()
        # Get model for this request before creating agent (for later use in response)
        model_name = get_next_llm_model()

        # Avoid using reserved LogRecord attribute names (e.g. 'message') in 'extra'
        logger.info(
            "[chat] Received request",
            extra={"request_id": request_id, "user_message": request.message},
        )
        agent = await create_agent(request_id, model_name)

        # Run the agent with the user's message
        logger.info(
            "[chat] Starting agent.run",
            extra={"request_id": request_id, "request_message": request.message},
        )
        result = await agent.run(task=request.message)
        logger.info(
            "[chat] agent.run completed",
            extra={"request_id": request_id, "result": result},
        )
        # Log only lightweight metadata about the TaskResult to prevent large payloads
        logger.info(
            "chat result from agent run",
            extra={
                "request_id": request_id,
                "result_type": result.__class__.__name__,
                "message_count": len(getattr(result, "messages", []) or []),
            },
        )

        # Extract the response
        response_text = ""
        if hasattr(result, "messages") and result.messages:
            last_message = result.messages[-1]
            content = getattr(last_message, "content", None)

            if content is not None:
                if isinstance(content, str):
                    response_text = content
                elif isinstance(content, list):
                    # Handle content blocks
                    text_parts = []
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            text_parts.append(block.get("text", ""))
                        elif isinstance(block, str):
                            text_parts.append(block)
                    response_text = "".join(text_parts) if text_parts else str(content)
                else:
                    response_text = str(content)

        duration_ms = int((time.time() - t0) * 1000)

        logger.info(
            "[chat] Completed",
            extra={
                "request_id": request_id,
                "user_message": request.message,
                "response": response_text,
                "duration_ms": duration_ms,
                "model": model_name,
                "trace_id": trace_id,
            },
        )
        return {
            "request_id": request_id,
            "message": request.message,
            "response": response_text,
            "duration_ms": duration_ms,
            "model": model_name,
            "trace_id": trace_id,
        }

    @dataclass
    class FeedbackData(BaseModel):
        """
        Data model for feedback requests.

        Attributes:
            trace_id: The New Relic trace_id from the chat response.
            rating: The user's rating (1 for thumbs up, 0 for thumbs down).
            message: Optional message associated with the feedback.
            metadata: Optional additional metadata (e.g., category, model).
        """

        trace_id: str
        rating: int
        message: str = ""
        metadata: Optional[dict] = None

    @app.post("/feedback")
    async def feedback(request: FeedbackData):
        """
        Handle feedback requests by recording LLM feedback events in New Relic.

        Args:
            request: FeedbackData containing trace_id, rating, and optional message/metadata.

        Returns:
            dict: Response confirming feedback was recorded.
        """
        # Set New Relic transaction name
        newrelic.agent.set_transaction_name("Feedback")

        # Add custom attributes for tracking
        newrelic.agent.add_custom_attribute("feedback_trace_id", request.trace_id)
        newrelic.agent.add_custom_attribute("feedback_rating", request.rating)

        logger.info(
            "[feedback] Received feedback",
            extra={
                "trace_id": request.trace_id,
                "rating": request.rating,
                "feedback_message": request.message,
                "metadata": request.metadata,
            },
        )

        # Record LLM feedback event in New Relic
        try:
            newrelic.agent.record_llm_feedback_event(
                trace_id=request.trace_id,
                rating=request.rating,
                message=request.message,
                metadata=request.metadata or {},
            )
            logger.info(
                "[feedback] Recorded feedback event",
                extra={
                    "trace_id": request.trace_id,
                    "rating": request.rating,
                },
            )
            return {
                "status": "success",
                "trace_id": request.trace_id,
                "rating": request.rating,
            }
        except Exception as e:
            logger.error(
                "[feedback] Failed to record feedback",
                extra={
                    "trace_id": request.trace_id,
                    "rating": request.rating,
                    "error": str(e),
                },
            )
            return {
                "status": "error",
                "trace_id": request.trace_id,
                "error": str(e),
            }

    # Configure uvicorn to use our JSON formatter (by disabling its log_config)
    # The uvicorn loggers will inherit the root logger's JSON handler
    uvicorn.run(
        app,
        port=port,
        log_config=None,  # Use the logging configuration we already set up
    )


if __name__ == "__main__":
    # Configure logging AFTER New Relic initialization (done at module import time)
    import json

    class JSONFormatter(logging.Formatter):
        """Custom formatter that outputs logs as JSON with all extra fields."""

        def format(self, record):
            log_data = {
                "timestamp": self.formatTime(record, "%Y-%m-%d %H:%M:%S"),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
            }

            # Add all extra fields (anything not in standard LogRecord attributes)
            standard_attrs = {
                "name",
                "msg",
                "args",
                "created",
                "filename",
                "funcName",
                "levelname",
                "levelno",
                "lineno",
                "module",
                "msecs",
                "message",
                "pathname",
                "process",
                "processName",
                "relativeCreated",
                "thread",
                "threadName",
                "exc_info",
                "exc_text",
                "stack_info",
                "taskName",
                "getMessage",  # Exclude method
            }

            extra_fields = {}
            for k, v in record.__dict__.items():
                if k not in standard_attrs and not k.startswith("_"):
                    # Convert non-serializable objects to strings
                    try:
                        json.dumps({k: v})  # Test if serializable
                        extra_fields[k] = v
                    except (TypeError, ValueError):
                        extra_fields[k] = str(v)

            if extra_fields:
                log_data.update(extra_fields)

            # Add exception info if present
            if record.exc_info:
                log_data["exception"] = self.formatException(record.exc_info)

            return json.dumps(log_data)

    # Configure with JSON formatter as the default handler for all logging
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())

    # Get the root logger and configure it with our JSON handler
    root_logger = logging.getLogger()
    root_logger.setLevel(os.getenv("LOG_LEVEL", "INFO"))

    # Remove any existing handlers to avoid duplicates
    root_logger.handlers.clear()

    # Add our JSON formatter handler
    root_logger.addHandler(handler)

    # Configure specific loggers
    # Reduce verbosity of httpx logs (only show warnings and errors)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    # Configure uvicorn loggers to use JSON format too
    uvicorn_logger = logging.getLogger("uvicorn")
    uvicorn_logger.setLevel(logging.INFO)

    uvicorn_error_logger = logging.getLogger("uvicorn.error")
    uvicorn_error_logger.setLevel(logging.INFO)

    # Only show warnings for uvicorn access logs (reduce noise)
    uvicorn_access_logger = logging.getLogger("uvicorn.access")
    uvicorn_access_logger.setLevel(logging.WARNING)

    # Configure autogen loggers to use JSON format
    logging.getLogger("autogen").setLevel(logging.INFO)
    logging.getLogger("autogen_agentchat").setLevel(logging.INFO)
    logging.getLogger("autogen_ext").setLevel(logging.INFO)
    uvicorn_error_logger = logging.getLogger("uvicorn.error")
    uvicorn_error_logger.handlers.clear()
    uvicorn_error_logger.propagate = False

    main()  # type: ignore[call-arg]
