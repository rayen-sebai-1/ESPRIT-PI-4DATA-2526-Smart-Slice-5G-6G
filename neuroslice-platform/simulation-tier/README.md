# Simulation Tier

The simulation tier generates the synthetic multi-domain 5G/6G network telemetry used by the rest of the NeuroSlice platform and exposes the fault-engine used for scenario control.

## Implemented Components

This tier currently contains:

- `simulator-core/`
- `simulator-edge/`
- `simulator-ran/`
- `fault-engine/`
- `scenarios/`

## Runtime Role

### `simulator-core`

Async SimPy worker for the Core domain.

- no public HTTP API
- emits VES-style telemetry to `adapter-ves`
- simulates:
  - `amf-01`
  - `smf-01`
  - `core-upf-01`
- consumes Redis fault state from `faults:active`
- reads cross-domain signal `ran:congestion_score`

### `simulator-edge`

Async SimPy worker for the Edge domain.

- no public HTTP API
- emits NETCONF-like telemetry to `adapter-netconf`
- simulates:
  - `edge-upf-01`
  - `mec-app-01`
  - `edge-comp-01`
- consumes Redis fault state from `faults:active`
- reads cross-domain congestion from `ran:congestion_score`
- publishes helper state such as `edge:saturation` and `edge:misrouting_ratio`

### `simulator-ran`

Async SimPy worker for the RAN domain.

- no public HTTP API
- emits VES-style telemetry to `adapter-ves`
- simulates:
  - 2 gNBs
  - 2 cells per gNB
  - 3 slices per cell (`eMBB`, `URLLC`, `mMTC`)
- total slice instances: 12
- publishes cross-domain load signals such as `ran:congestion_score` and `core:active_ues`

### `fault-engine`

FastAPI service used to inject faults and run scenarios.

- default Compose port: `7004`
- routes:
  - `GET /health`
  - `GET /faults/active`
  - `GET /scenarios`
  - `POST /scenarios/start`
  - `POST /scenarios/stop`
  - `POST /faults/inject`
- stores active faults in Redis hash `faults:active`
- publishes lifecycle events to Redis stream `stream:fault.events`

## Current Scenario Files

The committed scenarios in `scenarios/` are:

- `normal_day`
- `peak_hour`
- `urllc_misrouting`
- `edge_degradation`
- `cascading_incident`

Brief summary:

- `normal_day`: baseline traffic with no injected faults
- `peak_hour`: elevated traffic and RAN congestion
- `urllc_misrouting`: URLLC traffic forced through the wrong UPF path
- `edge_degradation`: edge compute and MEC overload
- `cascading_incident`: multi-domain chained incident across RAN, edge, and core

## Cross-Domain Coordination

The simulators coordinate through Redis in addition to the adapter flow.

Important keys and streams include:

- `faults:active`
- `stream:fault.events`
- `ran:congestion_score`
- `core:active_ues`
- `edge:saturation`
- `edge:misrouting_ratio`

## Telemetry Flow

```text
simulator-core -> adapter-ves
simulator-ran  -> adapter-ves
simulator-edge -> adapter-netconf

fault-engine -> faults:active + stream:fault.events
simulators   -> poll faults:active
```

## Simulation Characteristics

The tier uses causal, stateful models instead of independent random KPIs.

Examples from the current implementation:

- Core:
  - AMF active UEs drive registration queue, signaling load, CPU, and failure rate
  - SMF session load drives setup queue, latency, and success rate
  - Core UPF throughput, queue depth, latency, and packet loss are influenced by sessions, RAN congestion, and misrouting
- Edge:
  - compute saturation influences MEC app behavior
  - edge UPF latency and packet loss respond to overload and misrouting
- RAN:
  - cell and slice behavior changes with daily traffic shape, congestion, and misrouting flags

## Key Environment Variables

Simulation services rely on shared config from `ingestion-tier/shared/config.py`, including:

- `REDIS_HOST`
- `REDIS_PORT`
- `SERVICE_NAME`
- `SITE_ID`
- `TICK_INTERVAL_SEC`
- `SIM_SPEED`
- `VES_ADAPTER_URL`
- `NETCONF_ADAPTER_URL`
- `FAULT_ENGINE_URL`
- `SCENARIOS_DIR`

## Running The Tier

Use the main platform Compose file:

```bash
cd neuroslice-platform/infrastructure
docker compose up --build fault-engine simulator-core simulator-edge simulator-ran
```

Typical dependencies:

- `redis`
- `adapter-ves`
- `adapter-netconf`

## Notes

- Only `fault-engine` exposes an HTTP API directly.
- The simulator services are background workers and are not published on host ports.
- The scenario JSON files are mounted into relevant services at `/scenarios`.

## Folder Map

```text
simulation-tier/
|-- README.md
|-- fault-engine/
|-- scenarios/
|-- simulator-core/
|-- simulator-edge/
`-- simulator-ran/
```
