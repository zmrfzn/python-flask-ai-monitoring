# Multi-Model Rotation for Performance Comparison

## Overview

The agent server now supports automatic model rotation for performance comparison in New Relic. Each request will use a different model from a configured list, allowing you to compare response times, accuracy, and other metrics across different LLM models.

## Configuration

### Environment Variables

Edit `server/.env` to configure the models:

```bash
# Multiple models for performance comparison (comma-separated)
# Each request will use a different model from this list in rotation
# NOTE: Only use models that support function calling (tools)
# NOTE: Only use models available in GitHub Models API
# Valid models: gpt-4o-mini, gpt-4o
LLM_MODELS=gpt-4o-mini,gpt-4o

# Fallback if LLM_MODELS is not set
LLM_MODEL=gpt-4o-mini
```

### ⚠️ Important: Model Availability & Function Calling Support

**Requirements:**
1. Model must be available in the GitHub Models API
2. Model must support function calling (tool use) for MCP tools to work

**Available & Compatible Models (GitHub Models API):**
- ✅ **gpt-4o-mini** - Fast, cost-effective, supports function calling
- ✅ **gpt-4o** - Latest GPT-4 optimized, supports function calling

**Available but Incompatible Models:**
- ❌ **o1-mini** - Reasoning model, does NOT support function calling
- ❌ **o1-preview** - Reasoning model, does NOT support function calling

**Not Available in GitHub Models API:**
- ❌ gpt-4-turbo (returns "Unknown model" error)
- ❌ gpt-3.5-turbo (not currently available)
- ❌ gpt-4 (original, not currently available)

**Common Errors:**

1. **Function calling not supported:**
   ```
   ValueError: The model does not support function calling.
   ```
   Solution: Remove o1-mini/o1-preview from model list

2. **Unknown model:**
   ```
   openai.BadRequestError: Unknown model: gpt-4-turbo
   ```
   Solution: Only use models available in GitHub Models API (gpt-4o, gpt-4o-mini)

### How It Works

1. **Round-Robin Rotation**: Models are selected in round-robin fashion
   - Request 1: gpt-4o-mini
   - Request 2: gpt-4o
   - Request 3: gpt-4o-mini (cycles back)
   - Request 4: gpt-4o
   - And so on...

2. **New Relic Tracking**: Each request includes:
   - `llm_model` - The specific model used for this request
   - `model_count` - Total number of models in rotation
   - `available_models` - Comma-separated list of all models

3. **Client Display**: The Streamlit client shows:
   - Model name used for each response
   - Response time for each request
   - Statistics in the sidebar

## New Relic Performance Analysis

### Custom Attributes

Each transaction in New Relic includes these custom attributes for filtering and analysis:

- **llm_model**: The specific model used (e.g., "gpt-4o-mini")
- **model_count**: Number of models in rotation
- **duration_ms**: Response time in milliseconds

### NRQL Queries for Analysis

#### Compare Average Response Times by Model

```sql
SELECT average(duration_ms) as 'Avg Response Time (ms)'
FROM Transaction
WHERE appName = 'agent-server'
  AND name = 'Chat'
FACET llm_model
SINCE 1 hour ago
```

#### Model Usage Distribution

```sql
SELECT count(*) as 'Request Count'
FROM Transaction
WHERE appName = 'agent-server'
  AND name = 'Chat'
FACET llm_model
SINCE 1 hour ago
```

#### Performance Percentiles by Model

```sql
SELECT percentile(duration_ms, 50, 95, 99) as 'Response Time'
FROM Transaction
WHERE appName = 'agent-server'
  AND name = 'Chat'
FACET llm_model
SINCE 1 hour ago
```

#### Throughput by Model

```sql
SELECT rate(count(*), 1 minute) as 'Requests per Minute'
FROM Transaction
WHERE appName = 'agent-server'
  AND name = 'Chat'
FACET llm_model
TIMESERIES AUTO
SINCE 1 hour ago
```

#### Error Rate by Model

```sql
SELECT percentage(count(*), WHERE error = true) as 'Error Rate %'
FROM Transaction
WHERE appName = 'agent-server'
  AND name = 'Chat'
FACET llm_model
SINCE 1 hour ago
```

## Testing the Rotation

1. Start all services:
   ```bash
   ./start_all.sh
   ```

2. Open the client at http://localhost:8501

3. Send multiple requests using the example buttons or custom queries

4. Observe:
   - Each response shows the model name below the message
   - Different models are used in rotation
   - Toast notifications show model name and response time

5. Check New Relic:
   - Go to APM → agent-server → Transactions
   - Filter by transaction name "Chat"
   - Use custom attributes to analyze model performance
   - Create dashboards with the NRQL queries above

## Adding/Removing Models

To modify the model list:

1. Edit `server/.env`:
   ```bash
   LLM_MODELS=model1,model2,model3
   ```

2. Restart the agent server:
   ```bash
   pkill -f "uv run python server/agent.py"
   nohup uv run python server/agent.py > logs/agent.log 2>&1 &
   ```

3. Check logs to verify:
   ```bash
   grep "Configured LLM models" logs/agent.log
   ```

## Benefits

1. **Performance Comparison**: Compare response times across different models
2. **Cost Analysis**: Balance performance vs. API costs
3. **Quality Assessment**: Evaluate response quality from different models
4. **Load Distribution**: Distribute requests across multiple models
5. **Real-time Monitoring**: Track model performance in New Relic dashboards

## Logs

Model rotation information appears in logs:

```
[startup] Configured LLM models for rotation - models: gpt-4o-mini,gpt-4o, model_count: 2
[chat] Initializing OpenAIChatCompletionClient with model rotation - model: gpt-4o-mini, available_models: gpt-4o-mini,gpt-4o
```

## Tips

- Start with 2-3 models to keep costs manageable
- Use cheaper models (gpt-4o-mini) more frequently by listing them multiple times
- Monitor error rates - some models may not support all features
- Consider model-specific prompt tuning based on performance data
