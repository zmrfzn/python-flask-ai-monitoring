"""
Example: Using MCP Context Parameter for Enhanced Tool Functionality

The Context parameter provides access to:
- Request metadata
- Server configuration
- Client information
- Shared state across tool calls
- Progress reporting for long-running operations
"""

import logging
from mcp.server.fastmcp import Context, FastMCP

mcp = FastMCP("Enhanced Tools")
logger = logging.getLogger("enhanced_tools")


# Example 1: Using Context for Request Tracking
@mcp.tool("calculator_with_context")
def calculator_with_context(a: int, b: int, operation: str, ctx: Context) -> str:
    """
    Calculator that uses context for enhanced logging and tracking.
    
    Benefits:
    - Access request metadata
    - Track client information
    - Share state between tool calls in the same session
    """
    # Access request ID from context (if available)
    # Note: Actual Context API may vary - check MCP documentation
    
    logger.info(
        "[calculator] Request received",
        extra={
            "operation": operation,
            "a": a,
            "b": b,
            # Context might provide: client_id, session_id, etc.
        }
    )
    
    operations = {
        "add": a + b,
        "subtract": a - b,
        "multiply": a * b,
        "divide": a / b if b != 0 else "Error: Division by zero",
    }
    
    result = operations.get(operation.lower(), "Error: Invalid operation")
    
    # Could store result in context for subsequent tool calls
    # ctx.set_metadata("last_calculation", result)
    
    return str(result)


# Example 2: Using Context for Progress Reporting
@mcp.tool("batch_calculator")
def batch_calculator(numbers: list[int], operation: str, ctx: Context) -> str:
    """
    Perform batch calculations with progress reporting.
    
    Benefits:
    - Report progress for long-running operations
    - Allow cancellation via context
    - Provide intermediate results
    """
    results = []
    total = len(numbers)
    
    for i, num in enumerate(numbers):
        # Check if client requested cancellation
        # if ctx.is_cancelled():
        #     return f"Operation cancelled after {i} calculations"
        
        # Report progress (if context supports it)
        # ctx.report_progress(current=i+1, total=total)
        
        if operation == "square":
            results.append(num ** 2)
        elif operation == "double":
            results.append(num * 2)
    
    return f"Processed {total} numbers: {results}"


# Example 3: Using Context for Client-Specific Behavior
@mcp.tool("weather_with_preferences")
def weather_with_preferences(city: str, ctx: Context) -> str:
    """
    Get weather with client-specific preferences.
    
    Benefits:
    - Access user preferences (temperature units, language)
    - Customize output based on client
    - Store user-specific state
    """
    # Get user preferences from context
    # units = ctx.get_preference("temperature_units", default="celsius")
    # language = ctx.get_preference("language", default="en")
    
    units = "celsius"  # Default without context
    
    # Fetch weather data (simplified)
    temp = 22  # Example temperature
    
    if units == "fahrenheit":
        temp = (temp * 9/5) + 32
        unit_symbol = "°F"
    else:
        unit_symbol = "°C"
    
    return f"Weather in {city}: {temp}{unit_symbol}"


# Example 4: Using Context for Rate Limiting
@mcp.tool("api_call_with_limits")
def api_call_with_limits(endpoint: str, ctx: Context) -> str:
    """
    Make API calls with client-specific rate limiting.
    
    Benefits:
    - Track request counts per client
    - Enforce rate limits
    - Provide quota information
    """
    # Get client identifier from context
    # client_id = ctx.client_id
    # request_count = ctx.get_state(f"requests_{client_id}", default=0)
    
    # Check rate limit
    # MAX_REQUESTS = 100
    # if request_count >= MAX_REQUESTS:
    #     return f"Rate limit exceeded. {request_count}/{MAX_REQUESTS} requests used."
    
    # Increment counter
    # ctx.set_state(f"requests_{client_id}", request_count + 1)
    
    # Make actual API call
    result = f"Called {endpoint} successfully"
    
    # Return with quota info
    # return f"{result}. Requests: {request_count + 1}/{MAX_REQUESTS}"
    return result


# Example 5: Using Context for Caching
@mcp.tool("expensive_calculation")
def expensive_calculation(input_data: str, ctx: Context) -> str:
    """
    Perform expensive calculation with context-based caching.
    
    Benefits:
    - Cache results within a session
    - Avoid redundant computations
    - Share data between tool calls
    """
    # Check cache in context
    # cache_key = f"calc_{hash(input_data)}"
    # cached_result = ctx.get_cache(cache_key)
    # if cached_result:
    #     logger.info("Returning cached result")
    #     return cached_result
    
    # Perform expensive calculation
    import time
    time.sleep(0.1)  # Simulate expensive operation
    result = f"Processed: {input_data.upper()}"
    
    # Store in cache
    # ctx.set_cache(cache_key, result, ttl=300)  # Cache for 5 minutes
    
    return result


# Example 6: Using Context for Multi-Step Operations
@mcp.tool("start_workflow")
def start_workflow(workflow_name: str, ctx: Context) -> str:
    """Start a multi-step workflow and store state."""
    workflow_id = f"workflow_{workflow_name}_{id(ctx)}"
    
    # Store workflow state in context for subsequent steps
    # ctx.set_state(workflow_id, {
    #     "name": workflow_name,
    #     "step": 1,
    #     "status": "started",
    #     "data": {}
    # })
    
    return f"Workflow {workflow_name} started. ID: {workflow_id}"


@mcp.tool("continue_workflow")
def continue_workflow(workflow_id: str, step_data: dict, ctx: Context) -> str:
    """Continue a workflow using stored state."""
    # Retrieve workflow state from context
    # workflow_state = ctx.get_state(workflow_id)
    # if not workflow_state:
    #     return f"Workflow {workflow_id} not found"
    
    # Update state
    # workflow_state["step"] += 1
    # workflow_state["data"].update(step_data)
    # ctx.set_state(workflow_id, workflow_state)
    
    return f"Workflow {workflow_id} continued"


# Benefits Summary:
"""
Using Context Parameter Enables:

1. REQUEST TRACKING
   - Access unique request IDs
   - Correlate logs across tool calls
   - Track request lifecycle

2. CLIENT AWARENESS
   - Identify calling client
   - Customize behavior per client
   - Store client-specific preferences

3. STATE MANAGEMENT
   - Share data between tool calls
   - Implement multi-step workflows
   - Cache expensive computations

4. PROGRESS REPORTING
   - Report progress for long operations
   - Allow client-side cancellation
   - Provide intermediate results

5. RATE LIMITING & QUOTAS
   - Track usage per client
   - Enforce limits
   - Provide quota information

6. SESSION MANAGEMENT
   - Maintain state within a session
   - Clean up resources
   - Implement conversation memory

7. SECURITY & AUTHORIZATION
   - Access client credentials
   - Enforce permissions
   - Audit actions

8. METRICS & OBSERVABILITY
   - Track tool usage patterns
   - Measure performance per client
   - Identify bottlenecks

IMPORTANT: The actual Context API depends on the MCP version and implementation.
Check the MCP documentation for available methods and properties.
"""
