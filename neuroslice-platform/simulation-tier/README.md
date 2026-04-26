# Simulation Tier

The simulation tier generates synthetic multi-domain 5G/6G telemetry and provides the fault engine used for scenarios and manual fault injection.

## Components

- `simulator-core/`: Core-domain worker for AMF, SMF, and Core UPF entities
- `simulator-edge/`: Edge-domain worker for Edge UPF, MEC app, and compute node entities
- `simulator-ran/`: RAN-domain worker for gNB, cell, and slice telemetry
- `fault-engine/`: FastAPI control plane for scenarios and injected faults
- `scenarios/`: committed scenario JSON files mounted into containers at `/scenarios`

## Runtime Behavior

### `simulator-core`

- emits VES-like telemetry to `adapter-ves`
- models `amf-01`, `smf-01`, and `core-upf-01`
- consumes `faults:active`
- reacts to cross-domain state such as `ran:congestion_score`

### `simulator-edge`

- emits NETCONF-like telemetry to `adapter-netconf`
- models `edge-upf-01`, `mec-app-01`, and `edge-comp-01`
- publishes helper state such as `edge:saturation` and `edge:misrouting_ratio`

### `simulator-ran`

- emits VES-like telemetry to `adapter-ves`
- models two gNBs, four cells, and slice instances across `eMBB`, `URLLC`, and `mMTC`
- publishes `ran:congestion_score` and `core:active_ues`

### `fault-engine`

- default host port: `7004`
- routes:
  - `GET /health`
  - `GET /faults/active`
  - `GET /scenarios`
  - `POST /scenarios/start`
  - `POST /scenarios/stop`
  - `POST /faults/inject`
- stores active faults in Redis hash `faults:active`
- publishes lifecycle updates to `stream:fault.events`

## Built-In Scenarios

- `normal_day`: baseline traffic
- `peak_hour`: elevated traffic plus RAN congestion
- `urllc_misrouting`: URLLC path and QoS mismatch
- `edge_degradation`: edge overload and latency amplification
- `cascading_incident`: chained RAN, edge, and core incidents

## Shared State

Important Redis keys and streams:

- `faults:active`
- `stream:fault.events`
- `ran:congestion_score`
- `core:active_ues`
- `edge:saturation`
- `edge:misrouting_ratio`

Telemetry path:

```text
simulator-core -> adapter-ves
simulator-ran  -> adapter-ves
simulator-edge -> adapter-netconf
```

## Key Configuration

The simulators and fault engine rely on shared config from `ingestion-tier/shared/config.py`:

- `REDIS_HOST`
- `REDIS_PORT`
- `SERVICE_NAME`
- `SITE_ID`
- `TICK_INTERVAL_SEC`
- `SIM_SPEED`
- `VES_ADAPTER_URL`
- `NETCONF_ADAPTER_URL`
- `SCENARIOS_DIR`

## Run Only This Tier

```bash
cd neuroslice-platform/infrastructure
docker compose up --build redis adapter-ves adapter-netconf fault-engine simulator-core simulator-edge simulator-ran
```

## Current Limits

- Only `fault-engine` exposes a public HTTP API.
- Simulator services are background workers and do not publish host ports.
- Fault effects are implemented for the currently modeled KPIs only.
