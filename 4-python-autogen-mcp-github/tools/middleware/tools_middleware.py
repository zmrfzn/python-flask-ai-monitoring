"""
Custom middleware for the FastMCP tools server.

This middleware provides logging, monitoring, and request tracking capabilities
for the MCP tools server, integrated with New Relic APM.
"""

import json
import logging
import time
from typing import Optional
import newrelic.agent


class ToolsRequestMiddleware:
    """
    ASGI middleware for tracking tools server requests with New Relic integration.

    This middleware:
    - Sets descriptive New Relic transaction names for MCP endpoints
    - Logs request/response timing
    - Tracks custom attributes for monitoring
    - Provides request correlation via request_id
    """

    def __init__(self, app):
        """
        Initialize the middleware.

        Args:
            app: The ASGI application to wrap
        """
        self.app = app
        self._logger = logging.getLogger("tools.middleware")
        self._logger.info(
            "[ToolsRequestMiddleware] Initialized - will track MCP requests and set transaction names"
        )

    async def __call__(self, scope, receive, send):
        """
        Process incoming requests and set New Relic transaction names.

        Args:
            scope: ASGI scope dictionary
            receive: ASGI receive callable
            send: ASGI send callable
        """
        if scope["type"] != "http":
            # Pass through non-HTTP requests (websockets, lifespan, etc.)
            return await self.app(scope, receive, send)

        # Extract request information
        path = scope.get("path", "")
        method = scope.get("method", "")
        start_time = time.time()

        # For streamable-http, we need to read the body to get the MCP method/tool name
        transaction_name = None
        tool_name = None
        body_cache = []
        first_message = None

        # Try to read first chunk to parse MCP message
        try:
            first_message = await receive()
            if first_message["type"] == "http.request":
                body = first_message.get("body", b"")
                body_cache.append(first_message)

                # Parse MCP JSON-RPC message
                if body and path == "/mcp":
                    try:
                        mcp_message = json.loads(body.decode("utf-8"))
                        mcp_method = mcp_message.get("method", "")
                        self._logger.info(
                            "[middleware] MCP message: %s",
                            mcp_message,
                            extra={"mcp_method": mcp_method},
                        )

                        # Extract transaction name based on MCP method
                        if mcp_method == "tools/list":
                            transaction_name = "MCP/Tools/ListTools"
                        elif mcp_method == "tools/call":
                            # Extract the actual tool name being called
                            params = mcp_message.get("params", {})
                            tool_name = params.get("name", "unknown")
                            transaction_name = f"MCP/Tools/Call/{tool_name}"
                            newrelic.agent.add_custom_attribute(
                                "mcp.tool_name", tool_name
                            )

                            # Extract and log each tool argument as a separate custom attribute
                            arguments = params.get("arguments", {})
                            if arguments and isinstance(arguments, dict):
                                arg_count = 0
                                for arg_name, arg_value in arguments.items():
                                    # Prefix with tool name to avoid conflicts between different tools
                                    attr_key = f"tool.{tool_name}.{arg_name}"
                                    try:
                                        # Convert complex types to strings for New Relic
                                        if isinstance(
                                            arg_value, (str, int, float, bool)
                                        ):
                                            newrelic.agent.add_custom_attribute(
                                                attr_key, arg_value
                                            )
                                        else:
                                            # For complex types (lists, dicts), convert to JSON string
                                            newrelic.agent.add_custom_attribute(
                                                attr_key, json.dumps(arg_value)
                                            )

                                        arg_count += 1
                                        self._logger.debug(
                                            "[middleware] Added tool argument as custom attribute: %s=%s",
                                            attr_key,
                                            arg_value,
                                            extra={
                                                "attribute_key": attr_key,
                                                "attribute_value": arg_value,
                                            },
                                        )
                                    except (TypeError, ValueError, AttributeError) as e:
                                        self._logger.warning(
                                            "[middleware] Failed to add custom attribute for %s: %s",
                                            attr_key,
                                            str(e),
                                            extra={
                                                "attribute_key": attr_key,
                                                "error": str(e),
                                            },
                                        )

                                # Log summary at INFO level
                                if arg_count > 0:
                                    self._logger.info(
                                        "[middleware] Added %d tool arguments as custom attributes for %s",
                                        arg_count,
                                        tool_name,
                                        extra={
                                            "tool_name": tool_name,
                                            "argument_count": arg_count,
                                            "arguments": list(arguments.keys()),
                                        },
                                    )
                        elif mcp_method == "initialize":
                            transaction_name = "MCP/Tools/Initialize"
                        elif mcp_method == "ping":
                            transaction_name = "MCP/Tools/Ping"
                        else:
                            transaction_name = (
                                f"MCP/Tools/{mcp_method.replace('/', '_')}"
                            )

                        newrelic.agent.add_custom_attribute("mcp.method", mcp_method)
                    except (json.JSONDecodeError, UnicodeDecodeError, KeyError) as e:
                        # If we can't parse, fall back to generic name
                        self._logger.debug(
                            "[middleware] Failed to parse MCP message: %s",
                            str(e),
                            extra={"error": str(e)},
                        )
        except (RuntimeError, ValueError, OSError):
            # If reading fails, just continue with generic name
            pass

        # Reconstruct receive to replay cached body
        body_index = [0]

        async def receive_wrapper():
            """Return cached message or continue receiving."""
            if body_index[0] < len(body_cache):
                msg = body_cache[body_index[0]]
                body_index[0] += 1
                return msg
            return await receive()

        # Set transaction name
        if not transaction_name:
            if path == "/health" or path == "/":
                transaction_name = "MCP/Tools/Health"
            else:
                # Generic transaction name for unknown paths
                clean_path = path.replace("/", "_").strip("_") or "root"
                transaction_name = f"MCP/Tools/{clean_path}"

        newrelic.agent.set_transaction_name(
            transaction_name, group="WebTransaction", priority=9
        )


        # Add custom attributes for filtering/grouping
        newrelic.agent.add_custom_attribute("http.method", method)
        newrelic.agent.add_custom_attribute("http.path", path)
        newrelic.agent.add_custom_attribute("service.name", "tools-server")

        if tool_name:
            self._logger.info(
                "[middleware] Request received: %s %s (tool: %s)",
                method,
                path,
                tool_name,
                extra={"method": method, "path": path, "tool_name": tool_name},
            )
        else:
            self._logger.info(
                "[middleware] Request received: %s %s",
                method,
                path,
                extra={"method": method, "path": path},
            )

        # Custom send wrapper to capture response status
        response_status: Optional[int] = None

        async def send_wrapper(message):
            nonlocal response_status
            if message["type"] == "http.response.start":
                response_status = message.get("status")
                if response_status:
                    newrelic.agent.add_custom_attribute(
                        "http.status_code", response_status
                    )
            await send(message)

        # Process the request with cached body
        try:
            await self.app(scope, receive_wrapper, send_wrapper)
        finally:
            # Log completion with timing
            duration_ms = int((time.time() - start_time) * 1000)
            newrelic.agent.add_custom_attribute("http.duration_ms", duration_ms)

            self._logger.info(
                "[middleware] Request completed: %s %s -> %s (%dms)",
                method,
                path,
                response_status or "unknown",
                duration_ms,
                extra={
                    "method": method,
                    "path": path,
                    "status_code": response_status,
                    "duration_ms": duration_ms,
                },
            )


class ToolInvocationMiddleware:
    """
    ASGI middleware to track MCP tool invocations.

    This middleware extracts tool names from MCP requests and adds them
    as custom attributes for better observability in New Relic.
    """

    def __init__(self, app):
        """
        Initialize the middleware.

        Args:
            app: The ASGI application to wrap
        """
        self.app = app
        self._logger = logging.getLogger("tools.middleware.invocation")
        self._logger.info(
            "[ToolInvocationMiddleware] Initialized - will extract tool names and correlation IDs"
        )

    async def __call__(self, scope, receive, send):
        """
        Extract tool invocation details from requests.

        Args:
            scope: ASGI scope dictionary
            receive: ASGI receive callable
            send: ASGI send callable
        """
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        path = scope.get("path", "")

        # Track tool invocations specifically
        if "tools/call" in path or path == "/sse":
            newrelic.agent.add_custom_attribute("mcp.endpoint_type", "tool_invocation")
            self._logger.debug(
                "[tool_invocation] MCP tool call detected on path: %s",
                path,
                extra={"path": path},
            )

        # Extract correlation headers
        headers = dict(scope.get("headers", []))
        request_id = headers.get(b"x-request-id")

        if request_id:
            request_id_str = request_id.decode("utf-8")
            newrelic.agent.add_custom_attribute(
                "correlation.request_id", request_id_str
            )
            self._logger.debug(
                "[tool_invocation] Correlation ID: %s",
                request_id_str,
                extra={"request_id": request_id_str},
            )

        await self.app(scope, receive, send)
