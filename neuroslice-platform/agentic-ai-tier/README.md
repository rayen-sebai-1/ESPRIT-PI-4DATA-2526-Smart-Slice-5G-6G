# Agentic AI Tier

The agentic AI tier is reserved for future LLM-driven operator assistance, RCA workflows, and autonomous investigation features on top of NeuroSlice telemetry and runtime AIOps outputs.

## Current Status

This tier is still a placeholder in the current repository state.

- no service directories are committed under `agentic-ai-tier/`
- no Compose services are defined for it in `infrastructure/docker-compose.yml`
- no prompts, model-serving runtimes, tools, or APIs are implemented here yet

Today, this folder contains only this README.

## Likely Future Inputs

- canonical telemetry from `stream:norm.telemetry`
- runtime AIOps streams `events.anomaly`, `events.sla`, and `events.slice.classification`
- latest Redis entity state in `entity:{entity_id}`
- fault and scenario context from `fault-engine` and `api-bff-service`
- protected dashboard workflows from `api-dashboard-tier`
