# Tools Server Custom Middleware

This document describes the custom ASGI middleware implementation for the FastMCP tools server.

## Overview

The tools server now uses custom ASGI middleware to enhance observability of MCP tool invocations and SSE communication. This provides:

- **MCP-Specific Transaction Naming**: Transaction names that reflect MCP protocol operations
- **Tool Invocation Tracking**: Monitoring of which tools are being called
- **SSE Endpoint Monitoring**: Detailed tracking of SSE connections and messages
- **Request/Response Timing**: Automatic timing for all MCP operations

## Middleware Components

### 1. ToolsRequestMiddleware

**Purpose**: Primary middleware for MCP request tracking and New Relic transaction naming

**Features**:
- Sets descriptive transaction names for MCP endpoints
- Captures HTTP method, path, status code, and duration
- Logs request/response lifecycle
- Adds service identification attributes

**Transaction Names**:
```python
/sse            → WebTransaction/MCP/Tools/SSE
/mcp/tools/list → WebTransaction/MCP/Tools/ListTools
/mcp/tools/call → WebTransaction/MCP/Tools/CallTool
/health         → WebTransaction/MCP/Tools/Health
/*              → WebTransaction/MCP/Tools/{path}
```

**Custom Attributes Added**:
- `http.method` - HTTP method (GET, POST, etc.)
- `http.path` - Request path
- `http.status_code` - Response status code
- `http.duration_ms` - Request processing time
- `service.name` - Always set to "tools-server"

### 2. ToolInvocationMiddleware

**Purpose**: Track MCP tool invocations and extract correlation IDs

**Features**:
- Identifies tool invocation requests
- Extracts correlation headers (`X-Request-ID`, `X-Trace-ID`)
- Adds MCP-specific metadata to transactions
- Enables distributed tracing from agent → tools

**Custom Attributes Added**:
- `mcp.endpoint_type` - Set to "tool_invocation" for tool calls
- `correlation.request_id` - Request ID from agent server
- `correlation.trace_id` - Distributed trace ID

## Integration with FastMCP

### Middleware Application

The middleware is applied by monkey-patching FastMCP's `sse_app` method:

```python
if nr_enabled == "1":
    from middleware import ToolsRequestMiddleware, ToolInvocationMiddleware
    
    original_sse_app = mcp.sse_app
    
    def patched_sse_app(*args, **kwargs):
        """Wrapper for sse_app that injects custom middleware stack."""
        app = original_sse_app(*args, **kwargs)
        
        # Apply middleware in reverse order (last added runs first)
        # 1. ToolInvocationMiddleware (innermost)
        app = ToolInvocationMiddleware(app)
        
        # 2. ToolsRequestMiddleware (outermost)
        app = ToolsRequestMiddleware(app)
        
        return app
    
    mcp.sse_app = patched_sse_app
```

### Execution Flow

1. **ToolsRequestMiddleware** (outermost)
   - Sets New Relic transaction name
   - Starts request timing
   - Logs request received

2. **ToolInvocationMiddleware** (inner)
   - Identifies tool invocations
   - Extracts correlation IDs
   - Adds MCP-specific attributes

3. **FastMCP/Starlette** (innermost)
   - Processes MCP protocol
   - Invokes tools (calculator, weather, file_reader, etc.)
   - Returns response

4. **Response through middleware**
   - ToolInvocationMiddleware: passes through
   - ToolsRequestMiddleware: logs completion, adds timing

## MCP Protocol Tracking

### SSE Connection Tracking

The middleware tracks SSE connections used for MCP communication:

```
[middleware] Request completed: GET /sse -> 200 (35ms)
```

This shows:
- SSE connection established successfully (200 status)
- Connection took 35ms to establish
- Transaction named `MCP/Tools/SSE` in New Relic

### Tool Discovery Tracking

When agents query available tools:

```
[middleware] Request completed: POST /messages/ -> 202 (0ms)
Processing request of type ListToolsRequest
```

This tracks:
- Agent requesting tool list
- MCP protocol message exchange
- Fast response time (cached tools)

### Tool Invocation Tracking

When a tool is called (e.g., calculator):

```
[tool_invocation] MCP tool call detected on path: /sse
[tool_invocation] Correlation ID: req-abc-123
[calculator] start - a=123, b=456, operation=multiply
[calculator] complete - result=56088, elapsed_ms=1
```

This provides end-to-end visibility of tool execution.

## Benefits for MCP Monitoring

### 1. Clear Transaction Separation

In New Relic, you can now filter by:
- **SSE connections**: `WHERE transaction = 'MCP/Tools/SSE'`
- **Tool listings**: `WHERE transaction = 'MCP/Tools/ListTools'`
- **Tool calls**: `WHERE transaction = 'MCP/Tools/CallTool'`

### 2. Distributed Tracing

Correlation IDs link requests across services:

```
Client Request (req-123)
  → Agent /chat (req-123)
    → Tools /sse (req-123)
      → calculator tool
```

### 3. Performance Analysis

Track MCP operation performance:

```sql
-- Average SSE connection time
SELECT average(http.duration_ms) 
FROM Transaction 
WHERE transaction = 'MCP/Tools/SSE' 
SINCE 1 hour ago

-- Tool invocation distribution
SELECT count(*) 
FROM Transaction 
WHERE mcp.endpoint_type = 'tool_invocation' 
FACET http.path 
SINCE 1 hour ago
```

### 4. Service Health Monitoring

Monitor tools server health:

```sql
-- Error rate by endpoint
SELECT percentage(count(*), WHERE http.status_code >= 400) 
FROM Transaction 
WHERE service.name = 'tools-server' 
FACET transaction 
SINCE 1 hour ago

-- Slow MCP operations
SELECT http.path, http.duration_ms 
FROM Transaction 
WHERE service.name = 'tools-server' 
AND http.duration_ms > 100 
SINCE 1 hour ago
```

## Comparison: Agent vs Tools Middleware

| Aspect | Agent Server | Tools Server |
|--------|-------------|--------------|
| Framework | Pure FastAPI | FastMCP + Starlette |
| Primary Protocol | HTTP REST | MCP over SSE |
| Transaction Focus | Chat operations | Tool invocations |
| Middleware Type | FastAPI middleware | ASGI middleware wrapper |
| Integration | `app.add_middleware()` | Monkey-patch `mcp.sse_app` |

## Log Examples

### Startup

```
[startup] tools server starting
[newrelic] Custom middleware stack applied (ToolsRequestMiddleware, ToolInvocationMiddleware)
[startup] Starting SSE server on port 8090
```

### Normal Operation

```
[middleware] Request completed: GET /sse -> 200 (35ms)
[middleware] Request completed: POST /messages/ -> 202 (0ms)
[tool_invocation] MCP tool call detected on path: /sse
[calculator] complete - result=56088, elapsed_ms=1
[middleware] Request completed: GET /sse -> 200 (8ms)
```

### With Correlation IDs

```
[tool_invocation] Correlation ID: req-agent-456
[weather] checking_cache - request_id=req-agent-456
[weather] cache_hit - request_id=req-agent-456, elapsed_ms=2
[middleware] Request completed: GET /sse -> 200 (5ms)
```

## Performance Considerations

### Minimal Overhead

- **ToolsRequestMiddleware**: ~1-2ms per request
- **ToolInvocationMiddleware**: ~0.5ms per request
- **Total**: < 3ms per MCP operation

### High-Frequency Operations

The tools server handles many SSE messages:
- Tool discovery: 4 requests per agent initialization
- Tool calls: 2+ requests per invocation (request + response)
- Keep-alive: Periodic SSE messages

The middleware is optimized for high-frequency operations with minimal logging overhead.

## Troubleshooting

### Middleware Not Applied

**Issue**: No middleware logs appearing

**Solutions**:
1. Check `NEW_RELIC_ENABLED=1` in `tools/.env`
2. Verify import: `from middleware import ToolsRequestMiddleware`
3. Check monkey-patch executed before `mcp.run()`

### Transaction Names Wrong

**Issue**: Still seeing generic transaction names

**Solutions**:
1. Ensure middleware wrapper applied to correct app
2. Check `mcp.sse_app` is patched before `mcp.run()`
3. Verify path matching in `ToolsRequestMiddleware`

### Missing Correlation IDs

**Issue**: `correlation.request_id` not appearing

**Solutions**:
1. Check agent server sends `X-Request-ID` header
2. Verify `ToolInvocationMiddleware` extracts headers correctly
3. Test with curl: `curl -H "X-Request-ID: test-123" http://localhost:8090/sse`

## Future Enhancements

### Tool-Specific Metrics

Track performance by tool type:

```python
# In ToolInvocationMiddleware
async def __call__(self, scope, receive, send):
    # Extract tool name from request body
    tool_name = extract_tool_name(scope)
    if tool_name:
        newrelic.agent.add_custom_attribute("mcp.tool_name", tool_name)
```

### Request Body Logging

Log tool arguments (for debugging):

```python
# Add to ToolInvocationMiddleware
if "tools/call" in path:
    body = await extract_body(receive)
    args = body.get("arguments", {})
    newrelic.agent.add_custom_attribute("mcp.tool_args", json.dumps(args))
```

### Rate Limiting

Add rate limiting per tool:

```python
class ToolRateLimitMiddleware:
    def __init__(self, app, max_calls_per_minute=100):
        self.app = app
        self.rate_limiter = RateLimiter(max_calls_per_minute)
    
    async def __call__(self, scope, receive, send):
        if not self.rate_limiter.allow_request():
            # Return 429 Too Many Requests
            await send_error(send, 429, "Rate limit exceeded")
            return
        
        await self.app(scope, receive, send)
```

## Summary

The tools server middleware provides:

✅ **MCP-Specific Monitoring** - Transaction names reflect MCP operations  
✅ **Tool Invocation Tracking** - Visibility into which tools are used  
✅ **Distributed Tracing** - Correlation IDs link agent → tools requests  
✅ **Performance Metrics** - Timing for SSE connections and tool calls  
✅ **Minimal Overhead** - < 3ms per operation  
✅ **FastMCP Compatible** - Works seamlessly with FastMCP framework  

Combined with the agent server middleware, you now have complete observability across your entire MCP-based AI agent system!
