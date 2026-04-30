# 04 Data Flow

## End-to-end pipeline
```text
simulator-core + simulator-ran -> adapter-ves -> stream:raw.ves
simulator-edge                 -> adapter-netconf -> stream:raw.netconf

stream:raw.ves + stream:raw.netconf
  -> normalizer
  -> stream:norm.telemetry
  -> Redis entity:{entity_id}
  -> Kafka telemetry-norm

stream:norm.telemetry
  -> congestion-detector  -> events.anomaly
  -> sla-assurance        -> events.sla
  -> slice-classifier     -> events.slice.classification
  -> online-evaluator (joins with prediction streams and pseudo-ground-truth)

events.anomaly + events.sla + events.slice.classification
  -> alert-management -> stream:control.alerts
  -> policy-control   -> stream:control.actions
  -> policy-control simulated actuator -> stream:control.actuations + control:sim:* keys

events.anomaly + events.sla + events.slice.classification + stream:norm.telemetry
  -> online-evaluator -> events.evaluation + aiops:evaluation:{model_name}

Redis streams + hashes -> api-bff-service -> dashboard-backend -> React
```

## Redis streams (core)
| Stream | Producer | Consumer |
|---|---|---|
| `stream:raw.ves` | `adapter-ves` | `normalizer` |
| `stream:raw.netconf` | `adapter-netconf` | `normalizer` |
| `stream:norm.telemetry` | `normalizer` | AIOps workers (+ optional aiops drift) |
| `events.anomaly` | `congestion-detector` | `alert-management`, `mlops-drift-monitor` |
| `events.sla` | `sla-assurance` | `alert-management` |
| `events.slice.classification` | `slice-classifier` | `alert-management` |
| `stream:control.alerts` | `alert-management` | `policy-control` |
| `stream:control.actions` | `policy-control` | dashboard/control readers |
| `stream:control.actuations` | `policy-control` | dashboard/control readers + simulator context |
| `events.drift` | drift monitors | dashboard/BFF readers |
| `events.evaluation` | `online-evaluator` | BFF/dashboard readers |

## Kafka topics in Scenario B
| Topic | Producer |
|---|---|
| `telemetry-norm` | `normalizer` |
| `events.anomaly` | `congestion-detector` |
| `events.sla` | `sla-assurance` |
| `events.slice.classification` | `slice-classifier` |
| `drift.alert` | `aiops-drift-monitor` |

## InfluxDB usage
- `telemetry-exporter` consumes `telemetry-norm` and writes telemetry/fault measurements.
- AIOps workers can mirror inference outputs to InfluxDB (`aiops_*` measurements).
- Dashboard and observability tooling reference InfluxDB for time-series views.
