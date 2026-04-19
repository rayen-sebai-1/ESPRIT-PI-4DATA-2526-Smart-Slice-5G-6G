# neuroslice-sim

**A production-style 5G AIOps / NWDAF-like telemetry simulator**

> Stateful, discrete-event, multi-domain network telemetry simulator with realistic correlated KPIs, fault injection, slice misrouting, Redis Streams, and Grafana dashboards.

---

## Quick Start

```bash
# From repo root
cd services/simulator
cp .env.example .env           # optional — defaults are fine
docker compose up --build
```

Wait ~30 seconds for all services to become healthy, then:

| Service | URL |
|---|---|
| **API** | http://localhost:8000 |
| **Swagger UI** | http://localhost:8000/docs |
| **Grafana** | http://localhost:3000 (admin / neuroslice) |
| **Prometheus** | http://localhost:9090 |
| **Redis** | localhost:6379 |

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                        neuroslice-sim stack                          │
│                                                                      │
│  simulator-ran ──▶ adapter-ves  ──┐                                  │
│  simulator-core ─▶ adapter-ves  ──┤                                  │
│  simulator-edge ─▶ adapter-netconf┤                                  │
│                                   ▼                                  │
│                              normalizer                              │
│                                   │                                  │
│                  ┌────────────────┴──────────────────┐              │
│                  ▼                                    ▼              │
│         stream:norm.telemetry              entity:{id} (hashes)     │
│                  │                                    │              │
│           api-service (SSE,                    api-service           │
│           exports, queries)               telemetry-exporter         │
│                                                  │                  │
│                                             Prometheus               │
│                                                  │                  │
│                                              Grafana                 │
│                                                                      │
│  fault-engine ──▶ faults:active (hash) ◀─ simulators poll           │
└──────────────────────────────────────────────────────────────────────┘
```

### Domains simulated

| Domain | Entities |
|---|---|
| **Core** | AMF-01, SMF-01, Core-UPF-01 |
| **Edge** | Edge-UPF-01, MEC-App-01, Edge-Comp-01 |
| **RAN** | gNB-01, gNB-02 × 2 cells each × 3 slices (eMBB / URLLC / mMTC) |

---

## KPI Model

KPIs are **not** random values. They are computed from latent state variables:

```
active_ues → signaling_load → cpu_util, registration_error_rate
active_ues → active_sessions → pdu_queue → pdu_latency
active_sessions → dl_throughput → queue_depth → forwarding_latency → packet_loss
rb_utilization → latency (exponential above 70%) → packet_loss (above 85%)
ran_congestion → propagates to edge and core via Redis
```

Each entity has a **causal update chain** per tick. Faults inject into latent variables, not directly into KPIs.

---

## Fault Injection

### Via API

```bash
# Inject a manual fault
curl -X POST http://localhost:8000/api/v1/faults/inject \
  -H "Content-Type: application/json" \
  -d '{
    "fault_type": "ran_congestion",
    "affected_entities": ["gnb-01", "gnb-02"],
    "severity": 3,
    "duration_sec": 120,
    "kpi_impacts": {"congestion": 0.7}
  }'
```

### Via Scenarios

```bash
# Start URLLC misrouting scenario
curl -X POST http://localhost:8000/api/v1/scenarios/start \
  -H "Content-Type: application/json" \
  -d '{"scenario_id": "urllc_misrouting"}'

# Stop current scenario
curl -X POST http://localhost:8000/api/v1/scenarios/stop
```

### Available scenarios

| Scenario ID | Description |
|---|---|
| `normal_day` | Baseline with sinusoidal daily pattern |
| `peak_hour` | 1.8× traffic, RAN congestion |
| `urllc_misrouting` | URLLC sent to wrong UPF, SLA breached |
| `edge_degradation` | Edge compute overload, MEC app response spikes |
| `cascading_incident` | All domains affected simultaneously |

---

## Sample API Calls

```bash
# Health check
curl http://localhost:8000/health

# Latest KPIs — all entities
curl http://localhost:8000/api/v1/kpis/latest

# Filter by domain
curl "http://localhost:8000/api/v1/kpis/latest?domain=ran"

# Filter by slice
curl "http://localhost:8000/api/v1/kpis/latest?sliceId=slice-urllc-01-01"

# Recent 15-minute telemetry window
curl "http://localhost:8000/api/v1/kpis/recent?minutes=15"

# Specific entity
curl http://localhost:8000/api/v1/kpis/entity/amf-01

# Active faults
curl http://localhost:8000/api/v1/faults/active

# SSE stream (live events)
curl -N http://localhost:8000/api/v1/stream/kpis

# ML export: SLA feature view
curl http://localhost:8000/api/v1/export/sla | python -m json.tool

# ML export: Slice classifier features
curl http://localhost:8000/api/v1/export/slice-classifier

# ML export: LSTM congestion sequences
curl http://localhost:8000/api/v1/export/congestion-sequences
```

---

## Redis Streams

| Stream | Producer | Consumer | Purpose |
|---|---|---|---|
| `stream:raw.ves` | adapter-ves | normalizer | Raw VES events |
| `stream:raw.netconf` | adapter-netconf | normalizer | Flat NETCONF records |
| `stream:norm.telemetry` | normalizer | api-service, exporter | Canonical events |
| `stream:fault.events` | fault-engine | (audit log) | Fault lifecycle events |

Entity latest state is stored in Redis hashes: `entity:{entity_id}` — used by the API for sub-ms reads.

---

## Slice Misrouting

When `urllc_misrouting` scenario is active:

- URLLC slice `actualUpf` → `core-upf-01` (instead of `edge-upf-01`)  
- `qosProfileActual` → `embb` (wrong class)  
- Latency +15ms → breaches 5ms SLA  
- Core UPF DL throughput rises unexpectedly  
- Edge UPF `localBreakoutRatio` drops  
- `misroutingScore` > 0 appears in canonical events and Grafana  

Observable in dashboards AND in `/api/v1/kpis/latest?domain=ran` (routing fields).

---

## Extending the Simulator

### Add a new entity

1. Create `entities/new_entity.py` in the relevant simulator service
2. Add `@dataclass` with latent state + `update()` + `kpis()`
3. Instantiate in `engine.py` and include in the tick chain
4. Map entity type in `shared/models.py` `EntityType` enum

### Add a new KPI

1. Return it from the entity's `kpis()` dict
2. It will flow automatically through VES → normalizer → Redis → Prometheus → Grafana

### Add a new fault type

1. Add value to `shared/models.py` `FaultType` enum
2. Create a JSON scenario in `scenarios/`
3. Handle the fault impacts in the relevant simulator engine's `_load_fault_state()`

### Add a new scenario

Simply create a JSON file in `scenarios/` following the existing pattern.

---

## Folder Structure

```
services/simulator/
├── docker-compose.yml
├── .env.example
├── README.md
├── shared/            ← Pydantic models, Redis helpers, config
├── simulator-core/    ← AMF, SMF, central UPF
├── simulator-edge/    ← Edge UPF, MEC app, compute node
├── simulator-ran/     ← gNBs, cells, slices (eMBB/URLLC/mMTC)
├── fault-engine/      ← Scenario runner + fault injector API
├── adapter-ves/       ← HTTP VES event receiver
├── adapter-netconf/   ← NETCONF polling adapter
├── normalizer/        ← Canonical schema mapper
├── api-service/       ← FastAPI public API + ML exports
├── telemetry-exporter/← Prometheus metrics exporter
├── scenarios/         ← JSON scenario definitions
└── observability/
    ├── grafana/        ← Provisioning + dashboard JSON
    └── prometheus/     ← Scrape config
```
