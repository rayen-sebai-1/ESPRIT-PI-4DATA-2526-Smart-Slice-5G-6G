# Agentic AI Tier

The agentic AI tier is reserved for future LLM-driven operator assistance, RCA workflows, and autonomous investigation features on top of NeuroSlice telemetry and AIOps outputs.

## Current Status

This tier is a placeholder only in the current repository state.

- No service directories are committed under `agentic-ai-tier/`
- No Docker Compose services are defined for this tier in `infrastructure/docker-compose.yml`
- No APIs, workers, prompts, or model-serving runtimes are implemented here yet

Today, the folder contains only this file.

## Likely Future Responsibilities

Based on the rest of the platform, this tier would naturally sit on top of:

- canonical telemetry from `stream:norm.telemetry`
- AIOps output streams:
  - `events.anomaly`
  - `events.sla`
  - `events.slice.classification`
- latest Redis entity state in `entity:{entityId}`
- fault and scenario context exposed through `fault-engine` and `api-bff-service`
- protected dashboard APIs for user-facing workflows

Possible future capabilities:

- NOC copilot queries over current network state
- evidence-based root-cause summaries for active incidents
- operator recommendations linked to SLA, congestion, and slice-classification events
- on-prem LLM serving for privacy-sensitive deployments

## Documentation Note

Older documentation may refer to subfolders such as `copilot-agent/`, `rca-agent/`, or `vllm-serving/`. Those directories are not present in the current workspace.

## Folder Map

```text
agentic-ai-tier/
`-- README.md
```
