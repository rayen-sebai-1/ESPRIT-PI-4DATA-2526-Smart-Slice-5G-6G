# 01 Setup

## Prerequisites
| Requirement | Recommended |
|---|---|
| OS | Linux, WSL2, or macOS with Docker Desktop |
| Docker | Docker Engine + Compose v2 |
| CPU/RAM | 4+ vCPU, 12+ GB RAM (more if `mlops` profile enabled) |
| Disk | 15+ GB free (images, volumes, artifacts) |
| Network ports | Must be free (see section below) |

## Repository entry points
- Platform root: `neuroslice-platform/`
- Compose runtime: `neuroslice-platform/infrastructure/`
- Main Compose file: `neuroslice-platform/infrastructure/docker-compose.yml`

## Key exposed ports (from Compose)
| Service | URL/Port |
|---|---|
| API BFF | `http://localhost:8000` |
| Kong gateway | `http://localhost:8008` |
| React dashboard | `http://localhost:5173` |
| VES adapter | `http://localhost:7001` |
| NETCONF adapter | `http://localhost:7002` |
| Fault engine | `http://localhost:7004` |
| Alert management | `http://localhost:7010` |
| Policy control | `http://localhost:7011` |
| AIOps drift monitor (`drift` profile) | `http://localhost:7012` |
| Grafana | `http://localhost:3000` |
| Prometheus | `http://localhost:9090` |
| InfluxDB | `http://localhost:8086` |
| PostgreSQL (platform) | `localhost:5432` |
| Redis | `localhost:6379` |
| Kafka host listener | `localhost:29092` |

## Optional `mlops` profile ports
| Service | URL/Port |
|---|---|
| MLflow | `http://localhost:5000` |
| MinIO API | `http://localhost:9000` |
| MinIO console | `http://localhost:9001` |
| MLOps API | `http://localhost:8010` |
| Elasticsearch | `http://localhost:9200` |
| Kibana | `http://localhost:5601` |
| MLOps PostgreSQL | `localhost:5433` |

## Environment variables
Primary values are defined through Compose defaults and optional `.env` files under `neuroslice-platform/infrastructure/`.

Important examples:
- `DASHBOARD_DATA_PROVIDER` (default `bff`)
- `MODEL_NAME` per AIOps worker (`congestion_5g`, `sla_5g`, `slice_type_5g`)
- `MLOPS_RUNNER_URL`, `MLOPS_RUNNER_TOKEN`
- `MLOPS_PIPELINE_ENABLED`
- Drift-related variables (`DRIFT_WINDOW_SIZE`, `DRIFT_P_VALUE_THRESHOLD`, `DRIFT_ANOMALY_THRESHOLD`, etc.)

## Warnings (local/dev credentials)
This stack includes development defaults and must be treated as non-production by default.

- Default admin user is seeded locally (`admin@neuroslice.tn` / `change-me-now`)
- Development secrets exist in Compose/env defaults
- MLflow/MinIO/Kibana are host-exposed in `mlops` profile

Use strong secrets and restricted network exposure outside local demos.
