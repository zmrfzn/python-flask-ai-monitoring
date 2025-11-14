"""MCP tool handler implementations."""

import json
import logging
import os
import sys
import time
import uuid
from pathlib import Path

import newrelic.agent
import requests
from mcp.server.fastmcp import Context

# Import from parent package
sys.path.insert(0, str(Path(__file__).parent.parent))
from cache import WeatherCache


logger = logging.getLogger("tools.handlers")


def safe_add_custom_attribute(key: str, value) -> None:
    """
    Safely add a custom attribute to the current New Relic transaction.

    If no transaction is active, logs a debug message and skips the attribute.
    This prevents errors when tools are called outside of a web transaction context.

    Note: This function will try to find and activate the current transaction
    by accessing it from the ASGI context. If the transaction is not found,
    it will skip adding the attribute.

    Args:
        key: Attribute key
        value: Attribute value
    """
    try:
        # Try to add the attribute - New Relic will handle context lookup
        newrelic.agent.add_custom_attribute(key, value)
    except (RuntimeError, AttributeError, TypeError) as e:
        # If this fails, it likely means no transaction is active
        logger.debug("[safe_add_custom_attribute] Failed to add attribute %s: %s", key, e)


def register_tools(mcp, weather_cache: WeatherCache):
    """
    Register all MCP tools with the FastMCP server.

    Args:
        mcp: FastMCP server instance
        weather_cache: Shared WeatherCache instance
    """

    @mcp.tool("calculator")
    @newrelic.agent.background_task(name="calculator", group="MCP-Tools")
    def calculator(a: int, b: int, operation: str, ctx: Context) -> str:
        """Perform basic arithmetic operations.

        Args:
            a: First number
            b: Second number
            operation: Operation to perform (add, subtract, multiply, divide)

        Returns:
            Result of the operation as a string
        """
                    
        # Note: Transaction name and input arguments are set by middleware
        # Only add custom attributes for results and status here
        request_id = ctx.request_id
        t0 = time.time()
        logger.debug(
            "[calculator] start",
            extra={"request_id": request_id, "a": a, "b": b, "operation": operation},
        )

        try:
            operations = {
                "add": a + b,
                "subtract": a - b,
                "multiply": a * b,
                "divide": a / b if b != 0 else "Error: Division by zero",
            }
            result = operations.get(operation.lower(), "Error: Invalid operation")

            # Add result as custom attribute
            if isinstance(result, (int, float)):
                safe_add_custom_attribute("calculator.result", result)
                safe_add_custom_attribute("calculator.success", True)
            else:
                # Error case
                safe_add_custom_attribute("calculator.success", False)
                safe_add_custom_attribute(
                    "calculator.error_type", "invalid_operation_or_division_by_zero"
                )

            elapsed_ms = int((time.time() - t0) * 1000)
            logger.info(
                "[calculator] complete",
                extra={
                    "request_id": request_id,
                    "a": a,
                    "b": b,
                    "operation": operation,
                    "result": result,
                    "elapsed_ms": elapsed_ms,
                },
            )
            return str(result)
        except (ZeroDivisionError, KeyError, ValueError, TypeError) as e:
            # Record error in New Relic
            newrelic.agent.notice_error()
            safe_add_custom_attribute("calculator.success", False)
            logger.error(
                "[calculator] unexpected_error",
                extra={"request_id": request_id, "error": str(e)},
            )
            return f"Error: {str(e)}"

    @mcp.tool("get_weather")
    @newrelic.agent.background_task(name="get_weather", group="MCP-Tools")
    def get_weather(city: str, ctx: Context) -> str:
        """Get current weather information for a city.

        Args:
            city: Name of the city (e.g., 'London', 'New York')
            ctx: MCP context for request correlation and logging

        Returns:
            Weather information as a string
        """
        # Note: Transaction name and input arguments (city) are set by middleware
        # Only add custom attributes for results, cache status, and internal metrics here

        # Use context request_id for correlation across logs and traces
        request_id = ctx.request_id

        t0 = time.time()
        logger.debug(
            "[get_weather] start",
            extra={"request_id": request_id, "city": city, "client_id": ctx.client_id},
        )

        cached_result = weather_cache.get(city)
        if cached_result is not None:
            elapsed_ms = int((time.time() - t0) * 1000)

            # Record custom metrics for cache hit
            newrelic.agent.record_custom_metric("Custom/Weather/CacheHit", 1)
            newrelic.agent.record_custom_metric(
                "Custom/Weather/ResponseTime", elapsed_ms
            )

            # Add custom attributes
            safe_add_custom_attribute("weather.cache_hit", True)
            safe_add_custom_attribute("weather.data_source", "cache")

            logger.info(
                "[get_weather] cache_hit",
                extra={
                    "request_id": request_id,
                    "client_id": ctx.client_id,
                    "city": city,
                    "elapsed_ms": elapsed_ms,
                    "cache_stats": weather_cache.get_stats(),
                },
            )
            return cached_result

        logger.info(
            "[get_weather] cache_miss",
            extra={
                "request_id": request_id,
                "client_id": ctx.client_id,
                "city": city,
                "cache_stats": weather_cache.get_stats(),
            },
        )

        # Record custom metric for cache miss
        newrelic.agent.record_custom_metric("Custom/Weather/CacheMiss", 1)

        # Cache miss - fetch from API
        safe_add_custom_attribute("weather.cache_hit", False)
        safe_add_custom_attribute("weather.data_source", "api")

        api_key = os.getenv("OPENWEATHER_API_KEY")
        if not api_key:
            logger.error(
                "[get_weather] missing API key",
                extra={"request_id": request_id, "client_id": ctx.client_id},
            )
            safe_add_custom_attribute("weather.success", False)
            safe_add_custom_attribute("weather.error_type", "missing_api_key")
            newrelic.agent.notice_error()
            raise ValueError(
                "Weather service not configured. OPENWEATHER_API_KEY environment "
                "variable is required."
            )
        try:
            base_weather_url = "http://api.openweathermap.org/data/2.5/weather"
            url = f"{base_weather_url}?q={city}&appid={api_key}&units=metric"
            response = requests.get(url, timeout=5)
            response.raise_for_status()

            # Track API rate limits from response headers
            if "X-RateLimit-Limit" in response.headers:
                safe_add_custom_attribute(
                    "weather.api.rate_limit", int(response.headers["X-RateLimit-Limit"])
                )
            if "X-RateLimit-Remaining" in response.headers:
                remaining = int(response.headers["X-RateLimit-Remaining"])
                safe_add_custom_attribute("weather.api.rate_limit_remaining", remaining)
                newrelic.agent.record_custom_metric(
                    "Custom/Weather/API/RateLimitRemaining", remaining
                )
            if "X-RateLimit-Reset" in response.headers:
                safe_add_custom_attribute(
                    "weather.api.rate_limit_reset",
                    int(response.headers["X-RateLimit-Reset"]),
                )

            data = response.json()
            weather = data["weather"][0]["description"]
            temp = data["main"]["temp"]
            feels_like = data["main"]["feels_like"]
            humidity = data["main"]["humidity"]

            # Add detailed custom attributes for weather data
            safe_add_custom_attribute("weather.condition", weather)
            safe_add_custom_attribute("weather.temperature_celsius", temp)
            safe_add_custom_attribute("weather.feels_like_celsius", feels_like)
            safe_add_custom_attribute("weather.humidity_percent", humidity)
            safe_add_custom_attribute("weather.success", True)

            # Record custom metrics
            newrelic.agent.record_custom_metric("Custom/Weather/Temperature", temp)
            newrelic.agent.record_custom_metric("Custom/Weather/Humidity", humidity)

            result = (
                f"Weather in {city}: {weather}, Temperature: {temp}°C "
                f"(feels like {feels_like}°C), Humidity: {humidity}%"
            )

            # Store in cache
            weather_cache.set(city, result)

            elapsed_ms = int((time.time() - t0) * 1000)
            newrelic.agent.record_custom_metric(
                "Custom/Weather/ResponseTime", elapsed_ms
            )

            logger.info(
                "[get_weather] complete",
                extra={
                    "request_id": request_id,
                    "client_id": ctx.client_id,
                    "city": city,
                    "weather": weather,
                    "temp": temp,
                    "elapsed_ms": elapsed_ms,
                    "cache_stats": weather_cache.get_stats(),
                },
            )
            return result
        except requests.exceptions.RequestException as e:
            # Record error in New Relic
            newrelic.agent.notice_error()
            safe_add_custom_attribute("weather.success", False)
            safe_add_custom_attribute("weather.error_type", "api_request_error")

            logger.error(
                "[get_weather] request_error",
                extra={
                    "request_id": request_id,
                    "client_id": ctx.client_id,
                    "city": city,
                    "error": str(e),
                },
            )
            return (
                f"Error fetching weather data for {city}. Please check the city name."
            )
        except KeyError as e:
            # Record error in New Relic
            newrelic.agent.notice_error()
            safe_add_custom_attribute("weather.success", False)
            safe_add_custom_attribute("weather.error_type", "data_parse_error")

            logger.error(
                "[get_weather] parse_error",
                extra={
                    "request_id": request_id,
                    "client_id": ctx.client_id,
                    "city": city,
                    "error": str(e),
                },
            )
            return f"Error parsing weather data for {city}."

    @mcp.tool("read_file")
    @newrelic.agent.background_task(name="read_file", group="MCP-Tools")
    def read_file(filename: str) -> str:
        """Read contents of a file from the data directory.

        Args:
            filename: Name of the file to read (must be in the 'data' directory)

        Returns:
            Contents of the file as a string
        """
        # Note: Transaction name and input arguments (filename) are set by middleware
        # Only add custom attributes for results, file metadata, and status here

        request_id = str(uuid.uuid4())
        t0 = time.time()
        logger.debug(
            "[read_file] start", extra={"request_id": request_id, "file_name": filename}
        )
        data_dir = Path(__file__).parent.parent.parent / "data"
        logger.info(
            "[read_file] data_dir",
            extra={"request_id": request_id, "data_dir": str(data_dir)},
        )
        file_path = data_dir / filename
        try:
            file_path = file_path.resolve()
            if not str(file_path).startswith(str(data_dir.resolve())):
                logger.warning(
                    "[read_file] path_outside_data_dir",
                    extra={"request_id": request_id, "file_name": filename},
                )
                safe_add_custom_attribute("file.success", False)
                safe_add_custom_attribute("file.error_type", "access_denied")
                newrelic.agent.notice_error()
                return "Error: Access denied. File must be in the data directory."
            if not file_path.exists():
                logger.info(
                    "[read_file] not_found",
                    extra={"request_id": request_id, "file_name": filename},
                )
                safe_add_custom_attribute("file.success", False)
                safe_add_custom_attribute("file.error_type", "file_not_found")
                newrelic.agent.notice_error()
                return f"Error: File '{filename}' not found in data directory."

            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            file_size = len(content)
            elapsed_ms = int((time.time() - t0) * 1000)

            # Add detailed custom attributes
            safe_add_custom_attribute("file.size_bytes", file_size)
            safe_add_custom_attribute("file.success", True)
            safe_add_custom_attribute("file.path", str(file_path.relative_to(data_dir)))

            # Record custom metrics
            newrelic.agent.record_custom_metric("Custom/File/Size", file_size)
            newrelic.agent.record_custom_metric("Custom/File/ReadTime", elapsed_ms)

            logger.info(
                "[read_file] complete",
                extra={
                    "request_id": request_id,
                    "file_name": filename,
                    "size": file_size,
                    "elapsed_ms": elapsed_ms,
                },
            )
            return content
        except (IOError, OSError, PermissionError) as e:
            # Record error in New Relic
            newrelic.agent.notice_error()
            safe_add_custom_attribute("file.success", False)
            safe_add_custom_attribute("file.error_type", "io_error")

            logger.error(
                "[read_file] error",
                extra={
                    "request_id": request_id,
                    "file_name": filename,
                    "error": str(e),
                },
            )
            return f"Error reading file '{filename}': {str(e)}"

    @mcp.tool("get_cache_stats")
    @newrelic.agent.background_task(name="get_cache_stats", group="MCP-Tools")
    def get_cache_stats() -> str:
        """Get weather cache statistics including hits, misses, and hit rate.

        Returns:
            JSON string containing cache statistics
        """
        # Note: Transaction name is set by middleware as MCP/Tools/Call/get_cache_stats
        request_id = str(uuid.uuid4())
        t0 = time.time()
        logger.debug("[get_cache_stats] start", extra={"request_id": request_id})

        stats = weather_cache.get_stats()

        # Add custom New Relic attributes
        for key, value in stats.items():
            safe_add_custom_attribute(f"cache_{key}", value)

        elapsed_ms = int((time.time() - t0) * 1000)
        logger.info(
            "[get_cache_stats] complete",
            extra={
                "request_id": request_id,
                "stats": stats,
                "elapsed_ms": elapsed_ms,
            },
        )

        return json.dumps(stats, indent=2)
