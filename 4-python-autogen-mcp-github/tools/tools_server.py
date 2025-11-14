"""
MCP (Model Context Protocol) tools server providing AI agent utilities.

This module implements an MCP server using FastMCP that exposes tools for:
- Calculator operations (add, subtract, multiply, divide)
- Weather information retrieval via OpenWeather API
- File reading from a sandboxed data directory

The server runs with streamable-http transport and integrates with
New Relic for application monitoring.
"""

import logging
import os
import sys
import time
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables FIRST before any other imports
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

# Initialize New Relic BEFORE importing any frameworks
import newrelic.agent

nr_enabled = os.getenv("NEW_RELIC_ENABLED", "0")
if nr_enabled == "1":
    # Initialize with environment variables (no ini file needed)
    newrelic.agent.initialize()
    newrelic.agent.register_application(timeout=10)

# Configure JSON logging BEFORE importing FastMCP
# This must be done after New Relic initialization to allow instrumentation,
# but before FastMCP import because FastMCP adds its own handler on instantiation
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

# Now import frameworks (after logging configuration)
from mcp.server.fastmcp import FastMCP

# Import the custom SSE server creator
sys.path.append(str(Path(__file__).parent))

# Import cache and tool handlers
from cache import WeatherCache
from handlers import register_tools

mcp = FastMCP(log_level="WARNING", name="Tools service")

logger = logging.getLogger("tools")
# Ensure tools logger respects LOG_LEVEL (defaults to INFO, can be set to DEBUG via env var)
logger.setLevel(os.getenv("LOG_LEVEL", "INFO"))
logger.debug("Tools MCP server initializing")


# Initialize weather cache with configurable TTL
WEATHER_CACHE_TTL_MINUTES = int(os.getenv("WEATHER_CACHE_TTL_MINUTES", "10"))
weather_cache = WeatherCache(ttl_minutes=WEATHER_CACHE_TTL_MINUTES)

# Register all MCP tools
register_tools(mcp, weather_cache)


def main():
    """Run the FastMCP server."""

    # Get port from environment variable, default to 8090
    port = int(os.getenv("TOOLS_SERVER_PORT", "8090"))

    logger.info(
        "[startup] tools server starting",
        extra={"port": port, "weather_cache_ttl_minutes": WEATHER_CACHE_TTL_MINUTES},
    )

    # Configure server settings BEFORE patching
    mcp.settings.port = port
    mcp.settings.host = "0.0.0.0"

    # Apply custom middleware for New Relic tracking and monitoring
    if nr_enabled == "1":
        from middleware import ToolsRequestMiddleware, ToolInvocationMiddleware

        # Patch the streamable_http_app method before calling run
        original_http_app = mcp.streamable_http_app

        def patched_http_app(*args, **kwargs):
            """Wrapper for streamable_http_app that injects custom middleware stack."""
            app = original_http_app(*args, **kwargs)

            # Apply ASGI middleware in reverse order (last added runs first)
            # 1. ToolInvocationMiddleware (innermost) - extracts tool details
            app = ToolInvocationMiddleware(app)

            # 2. Wrap with New Relic's ASGI wrapper - provides automatic instrumentation
            app = newrelic.agent.ASGIApplicationWrapper(app)

            # 3. ToolsRequestMiddleware (outermost) - transaction naming runs LAST to override
            #    any default naming from ASGIApplicationWrapper
            app = ToolsRequestMiddleware(app)

            return app

        mcp.streamable_http_app = patched_http_app  # type: ignore
        logger.info(
            "[newrelic] ASGI middleware stack: ToolsRequestMiddleware -> ASGIApplicationWrapper -> ToolInvocationMiddleware"
        )

    logger.info("[startup] Starting Streamable HTTP server on port %s", port)

    # FastMCP supports multiple transports: "sse", "streamable-http", "stdio"
    # Using Streamable HTTP as it's the most reliable for HTTP-based communication
    t0 = time.time()
    mcp.run(transport="streamable-http")

    # This log will only appear when server shuts down
    logger.info(
        "[shutdown] tools server stopped",
        extra={"elapsed_ms": int((time.time() - t0) * 1000)},
    )


if __name__ == "__main__":
    # Configure specific loggers (they will use the root logger's JSON handler)

    # Reduce verbosity of httpx logs (only show warnings and errors)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    # Configure uvicorn loggers to use JSON format
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)

    # Only show warnings for uvicorn access logs (reduce noise)
    uvicorn_access_logger = logging.getLogger("uvicorn.access")
    uvicorn_access_logger.setLevel(logging.WARNING)

    # Configure MCP framework loggers
    logging.getLogger("mcp").setLevel(logging.INFO)
    logging.getLogger("mcp.server").setLevel(logging.INFO)

    # Configure middleware logger
    logging.getLogger("tools.middleware").setLevel(logging.INFO)

    main()
