# Agentic AI Tier

Planned autonomous-assistance layer for root-cause analysis, operator copilots, and LLM-backed reasoning workflows.

## Tier Purpose

This tier is designed for AI agents that augment operations teams and automate investigative workflows on top of NeuroSlice telemetry and events.

Target capabilities:

- Copilot assistance for NOC/engineering users.
- Automated incident triage and probable root-cause hypotheses.
- Context-aware recommendations grounded in telemetry + AIOps outputs.
- Optional on-prem/self-hosted LLM serving for privacy and latency control.

## Current Status

This tier is scaffold-only at the moment.

Directories present:

- `copilot-agent/`
- `rca-agent/`
- `vllm-serving/`

No runnable code or API contracts are implemented yet.

## Suggested Responsibilities by Folder

- `copilot-agent/`
- Conversational assistant for queries like KPI trend explanations, fault summaries, and suggested operator actions.

- `rca-agent/`
- Root-cause workflow engine that correlates anomalies across RAN/Edge/Core and proposes ranked hypotheses.

- `vllm-serving/`
- Model-serving runtime for local LLM inference endpoints used by agents.

## Suggested Integration Points

Potential data inputs:

- Canonical telemetry (`stream:norm.telemetry`)
- AIOps event streams (`events.anomaly`, `events.sla`, `events.slice.classification`)
- Fault state (`faults:active`) and scenario metadata
- Dashboard/API queries for user-facing workflows

Potential outputs:

- Agent recommendations stream for UI consumption
- RCA reports attached to incident identifiers
- Playbook suggestions forwarded to `control-tier`

## Suggested MVP Roadmap

1. Define a common event/context schema for agent prompts.
2. Implement a minimal `rca-agent` that summarizes current anomalies with evidence references.
3. Add a `copilot-agent` endpoint integrated with dashboard authentication.
4. Add `vllm-serving` deployment profile and model/version management policy.

## Folder Map

```text
agentic-ai-tier/
├── copilot-agent/
├── rca-agent/
└── vllm-serving/
```
