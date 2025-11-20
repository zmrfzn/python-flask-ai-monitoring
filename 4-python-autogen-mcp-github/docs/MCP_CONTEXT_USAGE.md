# Using MCP Context Parameter - Practical Guide

## Overview

The MCP `Context` parameter provides tools with access to request-level information, enabling advanced features like request tracking, state management, and client-specific behavior.

## When to Use Context

### ✅ Good Use Cases:
1. **Request correlation** - Track requests across distributed systems
2. **Progress reporting** - Report progress for long-running operations
3. **Session state** - Share data between multiple tool calls
4. **Client preferences** - Customize behavior per client
5. **Rate limiting** - Enforce per-client quotas
6. **Caching** - Store expensive computation results
7. **Audit logging** - Track who did what and when

### ❌ When NOT to Use Context:
1. Simple, stateless operations (like our basic calculator)
2. When you don't need request-level information
3. When tools are completely independent

## Practical Implementation Example

Here's how you could enhance the weather tool with Context:

```python
from mcp.server.fastmcp import Context, FastMCP

@mcp.tool("get_weather_enhanced")
def get_weather_enhanced(city: str, ctx: Context) -> str:
    """
    Get weather with enhanced context-aware features.
    
    Context enables:
    - Request tracking for debugging
    - User preference for temperature units
    - Caching to reduce API calls
    - Rate limiting per client
    """
    request_id = str(uuid.uuid4())
    
    # 1. Request Tracking
    logger.info(
        "Weather request started",
        extra={
            "request_id": request_id,
            "city": city,
            # Context could provide: session_id, client_id, etc.
        }
    )
    
    # 2. Check Cache (if context supports it)
    cache_key = f"weather_{city}"
    # cached = ctx.get_cache(cache_key)
    # if cached:
    #     logger.info("Returning cached weather data")
    #     return cached
    
    # 3. Get User Preferences (if context provides them)
    # units = ctx.get_preference("temperature_units", default="celsius")
    
    # 4. Rate Limiting
    # client_id = ctx.client_id
    # if not check_rate_limit(client_id):
    #     return "Rate limit exceeded. Please try again later."
    
    # 5. Make API call (actual implementation)
    weather_data = fetch_weather_from_api(city)
    
    # 6. Cache result
    # ctx.set_cache(cache_key, weather_data, ttl=300)
    
    return weather_data
```

## Context API Methods (Typical)

**Note:** Actual API depends on MCP version. Check documentation.

```python
# State Management
ctx.set_state(key, value)           # Store state
ctx.get_state(key, default=None)    # Retrieve state
ctx.delete_state(key)                # Remove state

# Caching
ctx.set_cache(key, value, ttl=None) # Cache with optional TTL
ctx.get_cache(key)                   # Retrieve cached value
ctx.clear_cache()                    # Clear all cache

# Client Information
ctx.client_id                        # Unique client identifier
ctx.session_id                       # Current session ID
ctx.request_id                       # Unique request ID

# Progress Reporting
ctx.report_progress(current, total)  # Report progress
ctx.is_cancelled()                   # Check if cancelled

# Metadata
ctx.set_metadata(key, value)         # Store metadata
ctx.get_metadata(key, default=None)  # Retrieve metadata
```

## Real-World Enhancement Ideas

### 1. **Conversation Memory**
```python
@mcp.tool("remember_fact")
def remember_fact(fact: str, ctx: Context) -> str:
    """Store a fact for later retrieval."""
    facts = ctx.get_state("facts", default=[])
    facts.append(fact)
    ctx.set_state("facts", facts)
    return f"Remembered: {fact}"

@mcp.tool("recall_facts")
def recall_facts(ctx: Context) -> str:
    """Recall all stored facts."""
    facts = ctx.get_state("facts", default=[])
    if not facts:
        return "No facts remembered yet."
    return "Remembered facts:\n" + "\n".join(f"- {f}" for f in facts)
```

### 2. **Multi-Step File Processing**
```python
@mcp.tool("start_file_analysis")
def start_file_analysis(filename: str, ctx: Context) -> str:
    """Start analyzing a file and store intermediate results."""
    content = read_file(filename)
    
    # Store for next step
    ctx.set_state("analysis_file", filename)
    ctx.set_state("analysis_content", content)
    ctx.set_state("analysis_line_count", len(content.split('\n')))
    
    return f"Started analysis of {filename}"

@mcp.tool("continue_analysis")
def continue_analysis(ctx: Context) -> str:
    """Continue analysis using stored state."""
    filename = ctx.get_state("analysis_file")
    if not filename:
        return "No analysis in progress"
    
    line_count = ctx.get_state("analysis_line_count")
    return f"File {filename} has {line_count} lines"
```

### 3. **Rate-Limited API Access**
```python
@mcp.tool("premium_search")
def premium_search(query: str, ctx: Context) -> str:
    """Search with rate limiting."""
    client_id = ctx.client_id
    requests_key = f"requests_{client_id}"
    
    count = ctx.get_state(requests_key, default=0)
    if count >= 10:  # 10 requests per session
        return f"Rate limit reached ({count}/10). Please start a new session."
    
    # Perform search
    results = perform_search(query)
    
    # Update counter
    ctx.set_state(requests_key, count + 1)
    
    return f"{results}\n\nRequests used: {count + 1}/10"
```

## Why We Removed It from Our Tools

For the current implementation:
1. **Simplicity** - Basic calculator, weather, and file reader don't need state
2. **Stateless** - Each tool call is independent
3. **No caching needed** - Operations are fast enough
4. **No rate limiting** - Internal use only

## When to Add It Back

Consider adding Context when you need:
- **Session memory** - Remember previous calculations or queries
- **Progress tracking** - For batch operations on multiple files
- **User preferences** - Temperature units, output format, etc.
- **Rate limiting** - If exposed to external clients
- **Audit trail** - Track who used which tools and when
- **Multi-step workflows** - Tools that work together across multiple calls

## Implementation Checklist

If you decide to add Context:

1. ✅ Import Context from MCP
2. ✅ Add `ctx: Context` parameter to tool functions
3. ✅ Document what context is used for in docstring
4. ✅ Use consistent naming convention (always `ctx`)
5. ✅ Check MCP documentation for available methods
6. ✅ Handle missing/None context gracefully
7. ✅ Test with and without context
8. ✅ Consider cleanup on session end

## Further Reading

- MCP Server Documentation: https://github.com/modelcontextprotocol/servers
- FastMCP Context API: Check package documentation
- Example implementations in MCP examples repository
