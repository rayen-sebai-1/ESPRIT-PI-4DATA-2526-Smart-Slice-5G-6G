# Agentic AI Tier

The agentic AI tier is reserved for future operator-assistance and investigation services on top of NeuroSlice telemetry and runtime AIOps outputs.

## Current Status

This tier is still placeholder-only in the current repository state.

- no service directories are committed under `agentic-ai-tier/`
- no active Compose services are defined for it in `infrastructure/docker-compose.yml`
- no prompts, tool integrations, model-serving runtimes, or APIs are implemented here yet

There are commented Compose stubs and matching `.env.example` variables for two future services:

- `root-cause`
- `copilot-agent`

Those stubs are not enabled and there is no service code behind them in this workspace.

## Likely Future Inputs

- canonical telemetry from `stream:norm.telemetry`
- runtime AIOps streams `events.anomaly`, `events.sla`, and `events.slice.classification`
- latest Redis entity state in `entity:{entity_id}`
- fault and scenario context from `fault-engine` and `api-bff-service`
- protected dashboard workflows from `api-dashboard-tier`
