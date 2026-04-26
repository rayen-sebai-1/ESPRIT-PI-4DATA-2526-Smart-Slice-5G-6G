# Agentic AI Tier

The agentic AI tier provides operator-assistance services on top of NeuroSlice telemetry, Redis state, InfluxDB metrics, and runtime AIOps outputs.

## Implemented Services

- `root-cause/`: manual root-cause analysis service
- `copilot-agent/`: conversational NOC copilot with streaming responses

Both services are included in the default integrated Compose runtime.

## Root-Cause Agent

Path: `agentic-ai-tier/root-cause/`

Default port:

- `7005`

Routes:

- `GET /health`
- `POST /internal/rca/manual-scan`

The service collects diagnostics from Redis and InfluxDB, then uses LangChain/Ollama to produce root-cause analysis output. It returns structured errors with diagnostics when Ollama or tool execution fails.

Key environment variables:

- `OLLAMA_BASE_URL`, default `http://host.docker.internal:11434`
- `RCA_OLLAMA_MODEL`, default `qwen2.5:3b-instruct`
- `RCA_AGENT_MAX_RETRIES`
- `RCA_ENABLE_HEURISTIC_FALLBACK`
- `INFLUXDB_URL`
- `INFLUXDB_ORG`
- `INFLUXDB_BUCKET`
- `REDIS_HOST`
- `REDIS_PORT`

## Copilot Agent

Path: `agentic-ai-tier/copilot-agent/`

Default port:

- `7006`

Routes:

- `GET /health`
- `POST /copilot/query`: SSE token stream
- `POST /copilot/query/text`: non-streaming text response

The copilot uses LangChain tools and Redis-backed context/memory to answer operator questions. SSE responses emit `token`, `done`, and `error` events.

Key environment variables:

- `OLLAMA_BASE_URL`, default `http://host.docker.internal:11434`
- `OLLAMA_MODEL` or Compose `COPILOT_OLLAMA_MODEL`, default `qwen2.5:3b-instruct`
- `OLLAMA_TIMEOUT_SECONDS`
- `REDIS_URL`

## Runtime Inputs

- canonical telemetry from Redis and InfluxDB
- runtime AIOps streams: `events.anomaly`, `events.sla`, `events.slice.classification`
- latest Redis entity state: `entity:{entity_id}`
- fault and scenario context from `fault-engine`
- dashboard/API workflows through the platform API stack

## Local Checks

```bash
curl http://localhost:7005/health
curl http://localhost:7006/health
```

Example copilot text call:

```bash
curl -X POST http://localhost:7006/copilot/query/text \
  -H "Content-Type: application/json" \
  -d '{"session_id":"local-test","query":"Summarize current AIOps risks."}'
```

## Current Limits

- Both services depend on an accessible Ollama endpoint.
- They are local-development services and do not yet enforce dashboard authentication directly.
- Root-cause scans are manual API calls, not automatically triggered by AIOps events.
