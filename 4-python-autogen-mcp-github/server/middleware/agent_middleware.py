"""
Custom middleware for the FastAPI agent server.

This middleware provides logging, monitoring, and request tracking capabilities
for the agent server, integrated with New Relic APM.
"""

import logging
import time
from typing import Optional
import newrelic.agent


class AgentRequestMiddleware:
    """
    ASGI middleware for tracking agent server requests with New Relic integration.

    This middleware:
    - Sets descriptive New Relic transaction names
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
        self._logger = logging.getLogger("server.middleware")

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

        # Set New Relic transaction name based on endpoint
        if path == "/chat":
            newrelic.agent.set_transaction_name("Agent/Chat", group="WebTransaction")
        elif path == "/health":
            newrelic.agent.set_transaction_name("Agent/Health", group="WebTransaction")
        elif path.startswith("/docs") or path.startswith("/openapi"):
            newrelic.agent.set_transaction_name("Agent/Docs", group="WebTransaction")
        else:
            # Generic transaction name for unknown paths
            clean_path = path.replace("/", "_").strip("_") or "root"
            newrelic.agent.set_transaction_name(
                f"Agent/{clean_path}", group="WebTransaction"
            )

        # Add custom attributes for filtering/grouping
        newrelic.agent.add_custom_attribute("http.method", method)
        newrelic.agent.add_custom_attribute("http.path", path)

        self._logger.debug(
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

        # Process the request
        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            # Log completion with timing
            duration_ms = int((time.time() - start_time) * 1000)
            self._logger.info(
                "[middleware] Request completed: %s %s -> %s (%sms)",
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


class CorrelationIdMiddleware:
    """
    ASGI middleware to extract and track correlation IDs.

    Note: For the agent server, request_id is generated internally in the /chat
    endpoint and added as a custom attribute there. This middleware is kept for
    future use if external correlation IDs need to be tracked (e.g., from a
    load balancer or API gateway).

    For now, it only extracts headers if they exist but doesn't require them.
    """

    def __init__(self, app):
        """
        Initialize the middleware.

        Args:
            app: The ASGI application to wrap
        """
        self.app = app
        self._logger = logging.getLogger("server.middleware.correlation")

    async def __call__(self, scope, receive, send):
        """
        Extract correlation IDs from headers if present.

        Args:
            scope: ASGI scope dictionary
            receive: ASGI receive callable
            send: ASGI send callable
        """
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        # Extract request ID from headers if present (optional)
        headers = dict(scope.get("headers", []))
        request_id = headers.get(b"x-request-id")

        if request_id:
            request_id_str = request_id.decode("utf-8")
            newrelic.agent.add_custom_attribute(
                "correlation.external_request_id", request_id_str
            )
            self._logger.debug(
                "[correlation] External Request ID from header: %s",
                request_id_str,
                extra={"external_request_id": request_id_str},
            )

        # Check for other correlation headers (optional)
        trace_id = headers.get(b"x-trace-id")
        if trace_id:
            trace_id_str = trace_id.decode("utf-8")
            newrelic.agent.add_custom_attribute("correlation.trace_id", trace_id_str)
            self._logger.debug(
                "[correlation] Trace ID from header: %s",
                trace_id_str,
                extra={"trace_id": trace_id_str},
            )

        await self.app(scope, receive, send)
