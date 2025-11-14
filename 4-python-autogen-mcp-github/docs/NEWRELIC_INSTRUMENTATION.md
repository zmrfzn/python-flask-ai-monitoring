# New Relic Instrumentation Enhancements

## Overview

This document describes the comprehensive New Relic instrumentation improvements made to the FastMCP tools server to provide detailed monitoring, error tracking, and performance insights.

## Custom Attributes Added

### Calculator Tool

**Namespace:** `calculator.*`

- `calculator.operand_a` - First operand value
- `calculator.operand_b` - Second operand value
- `calculator.operation` - Operation type (add, subtract, multiply, divide)
- `calculator.result` - Computed result (numeric operations only)
- `calculator.success` - Boolean indicating success/failure
- `calculator.error_type` - Error classification when applicable

**Transaction Name:** `Calculator`

### Weather Tool

**Namespace:** `weather.*`

- `weather.city` - City name requested
- `weather.condition` - Weather description (e.g., "foggy", "clear sky")
- `weather.temperature_celsius` - Current temperature
- `weather.feels_like_celsius` - Apparent temperature
- `weather.humidity_percent` - Humidity percentage
- `weather.cache_hit` - Boolean indicating cache hit/miss
- `weather.data_source` - Data source ("cache" or "api")
- `weather.success` - Boolean indicating success/failure
- `weather.error_type` - Error classification when applicable
- `weather.api.rate_limit` - API rate limit (from X-RateLimit-Limit header)
- `weather.api.rate_limit_remaining` - Remaining API calls (from X-RateLimit-Remaining header)
- `weather.api.rate_limit_reset` - Reset timestamp (from X-RateLimit-Reset header)

**Transaction Name:** `GetWeather`

### File Read Tool

**Namespace:** `file.*`

- `file.name` - Requested filename
- `file.path` - Relative path within data directory
- `file.size_bytes` - File size in bytes
- `file.success` - Boolean indicating success/failure
- `file.error_type` - Error classification (access_denied, file_not_found, io_error)

**Transaction Name:** `ReadFile`

### Cache Statistics Tool

**Namespace:** `cache_*`

- `cache_hits` - Total cache hits
- `cache_misses` - Total cache misses
- `cache_size` - Current cache size
- `cache_hit_rate_percent` - Hit rate percentage

**Transaction Name:** `GetCacheStats`

### Feedback Endpoint

**Namespace:** `feedback.*`

- `feedback.trace_id` - New Relic trace ID for correlation with chat responses
- `feedback.rating` - User rating (1 for thumbs up, -1 for thumbs down)
- `feedback.message` - Optional user comment about the response
- `feedback.metadata` - Additional context (JSON object, optional)

**Transaction Name:** `Agent/Feedback`

**Endpoint:** `/feedback` (POST)

**Purpose:** Captures user feedback on LLM responses and correlates them with New Relic traces using `record_llm_feedback_event()`. This enables analysis of which responses users found helpful or unhelpful, correlated with model performance metrics.

**Usage Example:**
```python
# Feedback captured from /chat endpoint response
trace_id = newrelic.agent.current_trace_id()

# User provides feedback via /feedback endpoint
newrelic.agent.record_llm_feedback_event(
    trace_id=trace_id,
    rating=1,  # 1 for thumbs up, -1 for thumbs down
    category="informative",
    message="Very helpful response",
    metadata={"model": "gpt-4o-mini", "response_time": 2751}
)
```

## Custom Metrics

### Weather Metrics

- `Custom/Weather/CacheHit` - Increment counter for cache hits
- `Custom/Weather/CacheMiss` - Increment counter for cache misses
- `Custom/Weather/ResponseTime` - Response time in milliseconds
- `Custom/Weather/Temperature` - Temperature value (for trending)
- `Custom/Weather/Humidity` - Humidity percentage (for trending)
- `Custom/Weather/API/RateLimitRemaining` - Remaining API calls (for quota monitoring)

### Cache Metrics

- `Custom/Cache/Hits` - Cumulative hit count
- `Custom/Cache/Misses` - Cumulative miss count
- `Custom/Cache/HitRate` - Current hit rate percentage
- `Custom/Cache/Size` - Current cache size
- `Custom/Cache/EntryAge` - Age of cached entry in seconds
- `Custom/Cache/Expired` - Increment counter for expired entries
- `Custom/Cache/Writes` - Increment counter for cache writes

### File Metrics

- `Custom/File/Size` - File size in bytes
- `Custom/File/ReadTime` - File read time in milliseconds

## Error Recording

All tools now properly record errors using `newrelic.agent.notice_error()`:

### Calculator Errors
- Division by zero
- Invalid operations
- Unexpected exceptions

### Weather Errors
- Missing API key configuration
- API request failures (network, timeout, HTTP errors)
- Data parsing errors (malformed responses)

### File Read Errors
- Access denied (path outside data directory)
- File not found
- I/O errors (permissions, disk issues)

Each error is tagged with:
- `success: False` attribute
- `error_type` attribute describing the error category
- Full exception context captured by `notice_error()`

## Transaction Naming

All tool invocations set clear transaction names:

- **Calculator:** `Calculator`
- **Weather:** `GetWeather`
- **File Read:** `ReadFile`
- **Cache Stats:** `GetCacheStats`
- **SSE Endpoint:** `MCP/ToolsServer/SSE` (via monkey-patch)

This replaces the verbose default names like:
`WebTransaction/Function/mcp.server.fastmcp.server:FastMCP.sse_app.<locals>.sse_endpoint`

## API Rate Limit Tracking

The weather tool now tracks OpenWeather API rate limits:

- Captures headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`
- Records as custom attributes for alerting thresholds
- Creates custom metric for trending rate limit consumption
- Enables proactive monitoring before hitting quotas

## Cache Performance Monitoring

The weather cache includes comprehensive instrumentation:

- Hit/miss tracking with custom metrics
- Hit rate percentage calculation
- Cache size monitoring
- Entry age tracking (for TTL validation)
- Expired entry counting

## Testing

A comprehensive test suite is available at `examples/test_instrumentation.py`:

```bash
uv run python examples/test_instrumentation.py
```

This tests:
- Calculator operations with various inputs
- Weather API calls with cache behavior (miss → hit → hit)
- File read operations (success and error cases)
- Error handling scenarios

## New Relic Dashboard Queries

### Cache Performance
```sql
SELECT 
  average(newrelic.timeslice.value) 
FROM Metric 
WHERE metricTimesliceName = 'Custom/Cache/HitRate' 
TIMESERIES
```

### Weather Response Time by Data Source
```sql
SELECT 
  average(newrelic.timeslice.value) 
FROM Metric 
WHERE metricTimesliceName = 'Custom/Weather/ResponseTime' 
FACET weather.data_source 
TIMESERIES
```

### API Rate Limit Monitoring
```sql
SELECT 
  latest(weather.api.rate_limit_remaining) 
FROM Transaction 
WHERE name = 'GetWeather' 
TIMESERIES
```

### Error Rate by Tool
```sql
SELECT 
  count(*) 
FROM TransactionError 
FACET transactionName 
TIMESERIES
```

### File Operations
```sql
SELECT 
  average(file.size_bytes), 
  count(*) 
FROM Transaction 
WHERE name = 'ReadFile' 
FACET file.success 
TIMESERIES
```

## Benefits

1. **Detailed Observability**: Every parameter and result is tracked
2. **Error Context**: Errors include classification and full stack traces
3. **Cache Insights**: Understand cache effectiveness and optimize TTL
4. **API Quota Management**: Proactive monitoring of rate limits
5. **Performance Tracking**: Custom metrics for trending and alerting
6. **Transaction Clarity**: Clear, meaningful transaction names

## Implementation Details

All instrumentation is implemented using the New Relic Python agent API:

- `newrelic.agent.set_transaction_name()` - Set clear transaction names
- `newrelic.agent.add_custom_attribute()` - Add contextual attributes
- `newrelic.agent.record_custom_metric()` - Record custom metrics
- `newrelic.agent.notice_error()` - Capture exceptions with context
- `@newrelic.agent.function_trace()` - Trace cache methods

The agent is initialized at module import time (before framework initialization) to ensure proper instrumentation of all code paths.
