# Agentic AI Tier

The agentic AI tier provides LLM-driven operator assistance and manual RCA workflows on top of NeuroSlice telemetry and runtime AIOps context.

## Current Status

This tier is implemented and integrated in Compose, but should be treated as **Beta/Internal**.

Implemented service directories:

- `copilot-agent/`
- `root-cause/`

Integrated Compose services:

- `copilot-agent` (default host port `7006`)
- `root-cause` (default host port `7005`)

## Implemented Services

### copilot-agent

Purpose:

- conversational NOC copilot with streaming token output

API:

- `GET /health`
- `POST /copilot/query` (SSE stream)
- `POST /copilot/query/text` (single text response)

Runtime dependencies:

- Ollama (`OLLAMA_BASE_URL`, `COPILOT_OLLAMA_MODEL`, `COPILOT_OLLAMA_TIMEOUT_SECONDS`)
- InfluxDB (`INFLUXDB_URL`, `INFLUXDB_TOKEN`, `INFLUXDB_ORG`, `INFLUXDB_BUCKET`) for summarized telemetry/fault evidence
- Redis (`REDIS_URL`, `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB`) for conversation/session memory and live entity/AIOps state

### root-cause

Purpose:

- manual slice-level RCA scan endpoint for operator workflows

API:

- `GET /health`
- `POST /internal/rca/manual-scan`

Runtime dependencies:

- Ollama (`OLLAMA_BASE_URL`, `RCA_OLLAMA_MODEL`, `RCA_AGENT_MAX_RETRIES`)
- InfluxDB (`INFLUXDB_URL`, `INFLUXDB_TOKEN`, `INFLUXDB_ORG`, `INFLUXDB_BUCKET`)
- Redis (`REDIS_URL`, `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB`)

## Real Telemetry and Compact LLM Context

Both agents now query the live NeuroSlice data plane instead of mocked tool responses:

- InfluxDB `telemetry` and `faults` measurements in org `neuroslice`, bucket `telemetry`
- Redis `faults:active`, `entity:{entity_id}`, `aiops:*:{entity_id}`, `stream:norm.telemetry`, AIOps event streams, and scalar cross-domain keys

Raw telemetry is never passed directly to the LLM. The shared tool layer aggregates records in Python first, grouping by `slice_id`, `domain`, `entity_id`, `entity_type`, `slice_type`, and field. Returned evidence includes compact stats such as `count`, `min`, `max`, `mean`, `last`, `p95`, `trend`, `slope_simple`, `breach_count`, and first/last breach timestamps.

The default analysis window is 30 minutes: `{"start":"-30m","stop":"now()"}`. This keeps qwen2.5:3b-instruct on a local 32k context focused on top breached KPIs, anomalous entities, active faults, Redis entity state, and AIOps outputs rather than thousands of raw field values.

## Runtime Inputs and Contract

The agents are designed to work with:

- canonical telemetry model aligned with the `telemetry` and `faults` measurements
- Redis state context for slice/entity diagnostics
- runtime AIOps outcomes (for cross-checking RCA narratives)

Current code-level tool interfaces follow this contract using Influx/Redis-oriented query arguments such as:

- `slice_id`
- `domain`
- `entity_type`
- `slice_type`
- `time_range`

Tool calls tolerate missing optional filters and return structured error/no-data payloads if Redis or InfluxDB is unavailable.

## Architecture Flow

```text
Operator or internal API caller
	-> copilot-agent (SSE/text) or root-cause (manual scan)
	-> LangChain agent/service layer
	-> Tool layer (InfluxDB and Redis context contract)
	-> Ollama model inference
	-> Streamed or JSON response
```

## Known Limits

- Services are exposed directly by Compose ports and are not routed through dashboard gateway/auth flows in this tier.
- LLM quality depends on the local Ollama model's tool-calling behavior. The RCA service keeps a deterministic fallback for malformed JSON responses.

## Rebuild and Smoke Test

```powershell
cd neuroslice-platform/infrastructure
docker compose up --build root-cause copilot-agent
```

Health checks:

```powershell
curl.exe http://localhost:7005/health
curl.exe http://localhost:7006/health
```

Manual RCA scan:

```powershell
curl.exe -X POST http://localhost:7005/internal/rca/manual-scan `
  -H "Content-Type: application/json" `
  -d "{\"slice_id\":\"slice-001\",\"domain\":\"ran\",\"time_range\":{\"start\":\"-30m\",\"stop\":\"now()\"}}"
```

Copilot text query:

```powershell
curl.exe -X POST http://localhost:7006/copilot/query/text `
  -H "Content-Type: application/json" `
  -d "{\"session_id\":\"smoke-session\",\"query\":\"Check slice-001 over the last 30 minutes. Summarize top breached KPIs, active faults, and recommended actions.\"}"
```

Local unit smoke checks:

```powershell
cd ../agentic-ai-tier
.\root-cause\.venv\Scripts\python.exe -m unittest discover -s tests
```
