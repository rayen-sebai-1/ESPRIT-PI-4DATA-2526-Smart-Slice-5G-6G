from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from random import Random
from pathlib import Path
import sys
import csv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import delete, select

from packages.neuroslice_common.config import get_settings
from packages.neuroslice_common.db import SessionLocal
from packages.neuroslice_common.enums import RICStatus, SliceType, UserRole
from packages.neuroslice_common.models import DashboardSnapshot, NetworkSession, Prediction, Region, User
from packages.neuroslice_common.prediction_common import normalize_slice_class
from packages.neuroslice_common.prediction_provider import get_prediction_provider
from packages.neuroslice_common.security import hash_password


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


@dataclass(frozen=True, slots=True)
class RegionSeedProfile:
    code: str
    name: str
    description: str
    ric_status: RICStatus
    network_load: float
    gnodeb_count: int
    session_count: int
    latency_base: float
    packet_loss_base: float
    throughput_base: float
    slice_pool: tuple[SliceType, ...]


REGION_PROFILES = (
    RegionSeedProfile(
        code="GT",
        name="Grand Tunis",
        description="Région capitale très dense, forte charge eMBB et trafic critique entreprise.",
        ric_status=RICStatus.DEGRADED,
        network_load=88.0,
        gnodeb_count=96,
        session_count=24,
        latency_base=28.0,
        packet_loss_base=1.35,
        throughput_base=620.0,
        slice_pool=(SliceType.EMBB, SliceType.FEMBB, SliceType.URLLC, SliceType.MURLLC, SliceType.MBRLLC),
    ),
    RegionSeedProfile(
        code="CB",
        name="Cap Bon",
        description="Zone littorale mixte tourisme-industrie avec charge variable.",
        ric_status=RICStatus.HEALTHY,
        network_load=73.0,
        gnodeb_count=52,
        session_count=14,
        latency_base=22.0,
        packet_loss_base=0.95,
        throughput_base=420.0,
        slice_pool=(SliceType.EMBB, SliceType.URLLC, SliceType.MMTC, SliceType.FEMBB),
    ),
    RegionSeedProfile(
        code="SH",
        name="Sahel",
        description="Couloir urbain intermédiaire avec forte activité résidentielle et tourisme.",
        ric_status=RICStatus.DEGRADED,
        network_load=68.0,
        gnodeb_count=71,
        session_count=16,
        latency_base=19.0,
        packet_loss_base=0.82,
        throughput_base=390.0,
        slice_pool=(SliceType.EMBB, SliceType.FEMBB, SliceType.URLLC, SliceType.MMTC),
    ),
    RegionSeedProfile(
        code="SF",
        name="Sfax",
        description="Hub industriel et logistique à trafic soutenu.",
        ric_status=RICStatus.DEGRADED,
        network_load=70.0,
        gnodeb_count=66,
        session_count=18,
        latency_base=21.0,
        packet_loss_base=0.88,
        throughput_base=430.0,
        slice_pool=(SliceType.EMBB, SliceType.MBRLLC, SliceType.URLLC, SliceType.MMTC),
    ),
    RegionSeedProfile(
        code="NO",
        name="Nord Ouest",
        description="Région étendue à densité modérée avec couverture plus hétérogène.",
        ric_status=RICStatus.HEALTHY,
        network_load=49.0,
        gnodeb_count=31,
        session_count=10,
        latency_base=25.0,
        packet_loss_base=0.72,
        throughput_base=210.0,
        slice_pool=(SliceType.MMTC, SliceType.UMMTC, SliceType.EMBB),
    ),
    RegionSeedProfile(
        code="CO",
        name="Centre Ouest",
        description="Région intérieure avec montée progressive de trafic IoT et transport.",
        ric_status=RICStatus.HEALTHY,
        network_load=54.0,
        gnodeb_count=38,
        session_count=12,
        latency_base=24.0,
        packet_loss_base=0.79,
        throughput_base=240.0,
        slice_pool=(SliceType.MMTC, SliceType.UMMTC, SliceType.EMBB, SliceType.MURLLC),
    ),
    RegionSeedProfile(
        code="SE",
        name="Sud Est",
        description="Zone portuaire et énergétique avec trafic critique ponctuel.",
        ric_status=RICStatus.HEALTHY,
        network_load=46.0,
        gnodeb_count=29,
        session_count=10,
        latency_base=23.0,
        packet_loss_base=0.66,
        throughput_base=220.0,
        slice_pool=(SliceType.MMTC, SliceType.URLLC, SliceType.MBRLLC, SliceType.EMBB),
    ),
    RegionSeedProfile(
        code="SO",
        name="Sud Ouest",
        description="Région la moins chargée du MVP, principalement monitoring standard et IoT.",
        ric_status=RICStatus.HEALTHY,
        network_load=33.0,
        gnodeb_count=22,
        session_count=8,
        latency_base=18.0,
        packet_loss_base=0.45,
        throughput_base=160.0,
        slice_pool=(SliceType.UMMTC, SliceType.MMTC, SliceType.EMBB),
    ),
)

DEMO_USERS = (
    ("Administrateur NeuroSlice", "admin@neuroslice.tn", "admin123", UserRole.ADMIN),
    ("Opérateur Réseau", "operator@neuroslice.tn", "operator123", UserRole.NETWORK_OPERATOR),
    ("Manager Réseau", "manager@neuroslice.tn", "manager123", UserRole.NETWORK_MANAGER),
)

ANOMALY_TEMPLATE_ALIASES = {
    SliceType.EMBB: "feMBB",
    SliceType.URLLC: "mURLLC",
    SliceType.MMTC: "umMTC",
}

TRAIN_DATASET_SLICE_TARGETS = {
    "1": "eMBB",
    "2": "mMTC",
    "3": "URLLC",
}


def upsert_users(db) -> None:
    for full_name, email, password, role in DEMO_USERS:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(
                full_name=full_name,
                email=email,
                password_hash=hash_password(password),
                role=role,
                is_active=True,
            )
            db.add(user)
        else:
            user.full_name = full_name
            user.password_hash = hash_password(password)
            user.role = role
            user.is_active = True


def upsert_regions(db) -> dict[str, Region]:
    regions_by_code: dict[str, Region] = {}
    for profile in REGION_PROFILES:
        region = db.scalar(select(Region).where(Region.code == profile.code))
        if region is None:
            region = Region(
                code=profile.code,
                name=profile.name,
                description=profile.description,
                ric_status=profile.ric_status,
                network_load=profile.network_load,
                gnodeb_count=profile.gnodeb_count,
            )
            db.add(region)
            db.flush()
        else:
            region.name = profile.name
            region.description = profile.description
            region.ric_status = profile.ric_status
            region.network_load = profile.network_load
            region.gnodeb_count = profile.gnodeb_count
        regions_by_code[profile.code] = region
    return regions_by_code


def reset_runtime_data(db) -> None:
    db.execute(delete(Prediction))
    db.execute(delete(NetworkSession))
    db.execute(delete(DashboardSnapshot))
    db.flush()


def parse_numeric(raw_value: str) -> float:
    return float(str(raw_value).replace(",", "."))


@lru_cache
def load_anomaly_templates() -> dict[str, list[dict[str, object]]]:
    dataset_path = ROOT / "data" / "raw" / "network_slicing_dataset_v3.csv"
    templates_by_slice: dict[str, list[dict[str, object]]] = {}
    if not dataset_path.exists():
        return templates_by_slice

    with dataset_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=";")
        for row in reader:
            slice_key = str(row["Slice Type"])
            templates_by_slice.setdefault(slice_key, []).append(
                {
                    "use_case_type": str(row["Use Case Type"]),
                    "required_mobility": str(row["Required Mobility"]).strip().lower() == "yes",
                    "required_connectivity": str(row["Required Connectivity"]).strip().lower() == "yes",
                    "slice_handover": str(row["Slice Handover"]).strip().lower() == "yes",
                    "packet_loss_budget": parse_numeric(row["Packet Loss Budget"]),
                    "latency_budget_ns": int(parse_numeric(row["Latency Budget (ns)"])),
                    "jitter_budget_ns": int(parse_numeric(row["Jitter Budget (ns)"])),
                    "data_rate_budget_gbps": parse_numeric(row["Data Rate Budget (Gbps)"]),
                    "slice_available_transfer_rate_gbps": parse_numeric(row["Slice Available Transfer Rate (Gbps)"]),
                    "slice_latency_ns": int(parse_numeric(row["Slice Latency (ns)"])),
                    "slice_packet_loss": parse_numeric(row["Slice Packet Loss"]),
                    "slice_jitter_ns": int(parse_numeric(row["Slice Jitter (ns)"])),
                }
            )

    return templates_by_slice


@lru_cache
def load_slice_feature_templates() -> dict[str, list[dict[str, int]]]:
    dataset_path = ROOT / "data" / "raw" / "train_dataset.csv"
    templates_by_slice: dict[str, list[dict[str, int]]] = {}
    if not dataset_path.exists():
        return templates_by_slice

    with dataset_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            canonical_slice = TRAIN_DATASET_SLICE_TARGETS.get(str(row["slice Type"]).strip())
            if not canonical_slice:
                continue

            templates_by_slice.setdefault(canonical_slice, []).append(
                {
                    "lte_5g_category": int(float(row["LTE/5g Category"])),
                    "smartphone": int(float(row["Smartphone"])),
                    "gbr": int(float(row["GBR"])),
                }
            )

    return templates_by_slice


def build_session_metrics(rng: Random, profile: RegionSeedProfile, slice_type: SliceType) -> tuple[float, float, float]:
    canonical_slice = normalize_slice_class(slice_type)

    latency_center = profile.latency_base
    packet_loss_center = profile.packet_loss_base
    throughput_center = profile.throughput_base

    if canonical_slice == "eMBB":
        latency_center *= 1.05
        packet_loss_center *= 0.95
        throughput_center *= 1.18
    elif canonical_slice == "mMTC":
        latency_center *= 1.35
        packet_loss_center *= 1.18
        throughput_center *= 0.72
    elif canonical_slice == "URLLC":
        latency_center *= 0.42
        packet_loss_center *= 0.28
        throughput_center *= 0.88

    latency = clamp(rng.gauss(latency_center, 5.0), 4.0, 120.0)
    packet_loss = clamp(rng.gauss(packet_loss_center, 0.30), 0.005, 3.5)
    throughput = clamp(rng.gauss(throughput_center, 80.0), 30.0, 920.0)
    return round(latency, 2), round(packet_loss, 3), round(throughput, 2)


def build_slice_runtime_context(rng: Random, slice_type: SliceType) -> tuple[int, int, int]:
    canonical_slice = normalize_slice_class(slice_type)
    templates_by_slice = load_slice_feature_templates()
    templates = templates_by_slice.get(canonical_slice, [])

    if templates:
        template = rng.choice(templates)
        return (
            int(template["lte_5g_category"]),
            int(template["smartphone"]),
            int(template["gbr"]),
        )

    if canonical_slice == "eMBB":
        return rng.randint(10, 20), 1, int(rng.random() < 0.55)
    if canonical_slice == "mMTC":
        return rng.randint(4, 14), 0, int(rng.random() < 0.70)
    return rng.randint(14, 20), 0, int(rng.random() < 0.15)


def build_congestion_metrics(
    rng: Random,
    profile: RegionSeedProfile,
    slice_type: SliceType,
    latency_ms: float,
    packet_loss: float,
    throughput_mbps: float,
) -> tuple[float, float, float, int, int]:
    base_load = profile.network_load
    slice_bias = {
        SliceType.ERLLC: 8.0,
        SliceType.URLLC: 6.0,
        SliceType.MURLLC: 5.0,
        SliceType.MBRLLC: 4.0,
        SliceType.FEMBB: 7.5,
        SliceType.EMBB: 5.5,
        SliceType.MMTC: 2.0,
        SliceType.UMMTC: 1.0,
    }.get(slice_type, 3.0)

    cpu_util_pct = clamp(base_load + slice_bias + rng.gauss(0.0, 6.0), 30.0, 99.9)
    mem_util_pct = clamp((base_load * 0.72) + (slice_bias * 0.45) + rng.gauss(0.0, 4.0), 28.0, 82.7)
    bw_util_pct = clamp((base_load * 0.88) + (slice_bias * 0.60) + rng.gauss(0.0, 6.0), 22.7, 99.9)

    user_density = max(profile.gnodeb_count, 1) / 22.0
    active_users = int(clamp((base_load * 2.6) + (user_density * 18.0) + rng.gauss(0.0, 22.0), 30.0, 458.0))

    queue_pressure = (
        (cpu_util_pct / 18.0)
        + (bw_util_pct / 22.0)
        + (latency_ms / 30.0)
        + (packet_loss / 1.5)
        - (throughput_mbps / 260.0)
        + rng.gauss(0.0, 1.5)
    )
    queue_len = int(clamp(round(queue_pressure), 0.0, 26.0))

    return round(cpu_util_pct, 2), round(mem_util_pct, 2), round(bw_util_pct, 2), active_users, queue_len


def build_service_flags(rng: Random, profile: RegionSeedProfile, slice_type: SliceType) -> tuple[int, int, int]:
    iot_probability = 0.10
    public_safety_probability = 0.08
    smart_city_probability = 0.12

    if slice_type in (SliceType.MMTC, SliceType.UMMTC):
        iot_probability = 0.78
        smart_city_probability = 0.22
    elif slice_type in (SliceType.URLLC, SliceType.ERLLC, SliceType.MURLLC):
        public_safety_probability = 0.45
        smart_city_probability = 0.18
    elif slice_type in (SliceType.EMBB, SliceType.FEMBB):
        smart_city_probability = 0.38
    elif slice_type is SliceType.MBRLLC:
        public_safety_probability = 0.22
        smart_city_probability = 0.30

    if profile.code in {"GT", "CB", "SH"}:
        smart_city_probability += 0.10
    if profile.code in {"GT", "SF", "SE"}:
        public_safety_probability += 0.08
    if profile.code in {"NO", "CO", "SO"}:
        iot_probability += 0.08

    iot_devices = int(rng.random() < clamp(iot_probability, 0.0, 1.0))
    public_safety = int(rng.random() < clamp(public_safety_probability, 0.0, 1.0))
    smart_city_home = int(rng.random() < clamp(smart_city_probability, 0.0, 1.0))

    if not any((iot_devices, public_safety, smart_city_home)):
        if slice_type in (SliceType.MMTC, SliceType.UMMTC):
            iot_devices = 1
        elif slice_type in (SliceType.URLLC, SliceType.ERLLC, SliceType.MURLLC):
            public_safety = 1
        else:
            smart_city_home = 1

    return iot_devices, public_safety, smart_city_home


def build_anomaly_context(
    rng: Random,
    profile: RegionSeedProfile,
    slice_type: SliceType,
    packet_loss: float,
) -> dict[str, object]:
    templates_by_slice = load_anomaly_templates()
    template_key = ANOMALY_TEMPLATE_ALIASES.get(slice_type, slice_type.value)
    templates = templates_by_slice.get(template_key) or next(iter(templates_by_slice.values()), [])

    if not templates:
        return {
            "use_case_type": "Smart City",
            "required_mobility": False,
            "required_connectivity": True,
            "slice_handover": False,
            "packet_loss_budget": 0.000005,
            "latency_budget_ns": 1_000_000,
            "jitter_budget_ns": 1_000_000,
            "data_rate_budget_gbps": 5.0,
            "slice_available_transfer_rate_gbps": 100.0,
            "slice_latency_ns": 1_200_000,
            "slice_packet_loss": 0.0002,
            "slice_jitter_ns": 1_100_000,
        }

    template = dict(rng.choice(templates))
    pressure = clamp((profile.network_load / 100.0) + (packet_loss / 4.0), 0.25, 1.35)

    template["slice_available_transfer_rate_gbps"] = round(
        clamp(
            float(template["slice_available_transfer_rate_gbps"]) * (1.08 - pressure * 0.14 + rng.uniform(-0.06, 0.06)),
            1.0,
            10_000.0,
        ),
        3,
    )
    template["slice_latency_ns"] = int(
        clamp(
            int(template["slice_latency_ns"]) * (0.88 + pressure * 0.28 + rng.uniform(-0.08, 0.12)),
            1.0,
            4_000_000.0,
        )
    )
    template["slice_packet_loss"] = round(
        clamp(
            float(template["slice_packet_loss"]) * (0.90 + pressure * 0.22 + rng.uniform(-0.05, 0.08)),
            0.0,
            0.001,
        ),
        6,
    )
    template["slice_jitter_ns"] = int(
        clamp(
            int(template["slice_jitter_ns"]) * (0.90 + pressure * 0.26 + rng.uniform(-0.08, 0.12)),
            1.0,
            4_000_000.0,
        )
    )
    return template


def seed_sessions_and_predictions(db, regions_by_code: dict[str, Region]) -> int:
    now = datetime.now(timezone.utc)
    rng = Random(20260407)
    provider = get_prediction_provider(get_settings())
    inserted_sessions = 0

    for profile in REGION_PROFILES:
        region = regions_by_code[profile.code]
        for index in range(1, profile.session_count + 1):
            slice_type = rng.choice(profile.slice_pool)
            latency_ms, packet_loss, throughput_mbps = build_session_metrics(rng, profile, slice_type)
            cpu_util_pct, mem_util_pct, bw_util_pct, active_users, queue_len = build_congestion_metrics(
                rng,
                profile,
                slice_type,
                latency_ms,
                packet_loss,
                throughput_mbps,
            )
            iot_devices, public_safety, smart_city_home = build_service_flags(rng, profile, slice_type)
            lte_5g_category, smartphone, gbr = build_slice_runtime_context(rng, slice_type)
            anomaly_context = build_anomaly_context(rng, profile, slice_type, packet_loss)
            session_obj = NetworkSession(
                session_code=f"NS-{profile.code}-{index:04d}",
                region_id=region.id,
                slice_type=slice_type,
                use_case_type=anomaly_context["use_case_type"],
                required_mobility=anomaly_context["required_mobility"],
                required_connectivity=anomaly_context["required_connectivity"],
                slice_handover=anomaly_context["slice_handover"],
                lte_5g_category=lte_5g_category,
                smartphone=smartphone,
                gbr=gbr,
                latency_ms=latency_ms,
                packet_loss=packet_loss,
                throughput_mbps=throughput_mbps,
                iot_devices=iot_devices,
                public_safety=public_safety,
                smart_city_home=smart_city_home,
                cpu_util_pct=cpu_util_pct,
                mem_util_pct=mem_util_pct,
                bw_util_pct=bw_util_pct,
                active_users=active_users,
                queue_len=queue_len,
                packet_loss_budget=anomaly_context["packet_loss_budget"],
                latency_budget_ns=anomaly_context["latency_budget_ns"],
                jitter_budget_ns=anomaly_context["jitter_budget_ns"],
                data_rate_budget_gbps=anomaly_context["data_rate_budget_gbps"],
                slice_available_transfer_rate_gbps=anomaly_context["slice_available_transfer_rate_gbps"],
                slice_latency_ns=anomaly_context["slice_latency_ns"],
                slice_packet_loss=anomaly_context["slice_packet_loss"],
                slice_jitter_ns=anomaly_context["slice_jitter_ns"],
                timestamp=now - timedelta(minutes=rng.randint(5, 900)),
            )
            db.add(session_obj)
            db.flush()

            result = provider.predict(session_obj, region)
            db.add(
                Prediction(
                    session_id=session_obj.id,
                    sla_score=result.sla_score,
                    congestion_score=result.congestion_score,
                    anomaly_score=result.anomaly_score,
                    risk_level=result.risk_level,
                    predicted_slice_type=result.predicted_slice_type,
                    slice_confidence=result.slice_confidence,
                    recommended_action=result.recommended_action,
                    model_source=result.model_source,
                    predicted_at=now - timedelta(minutes=rng.randint(0, 90)),
                )
            )
            inserted_sessions += 1

    return inserted_sessions


def seed_snapshots(db) -> int:
    rng = Random(20260408)
    now = datetime.now(timezone.utc).replace(hour=8, minute=0, second=0, microsecond=0)
    inserted_snapshots = 0

    for day_offset in range(6, -1, -1):
        generated_at = now - timedelta(days=day_offset)
        national_weight = 0
        national_sla = 0.0
        national_latency = 0.0
        national_congestion = 0.0
        national_alerts = 0
        national_anomalies = 0
        national_sessions = 0

        for profile in REGION_PROFILES:
            session_count = max(1, profile.session_count + rng.randint(-2, 2))
            load = clamp(profile.network_load + rng.uniform(-6.0, 6.0), 18.0, 98.0)
            sla_percent = clamp(99.0 - (load * 0.23) - rng.uniform(0.5, 4.5), 70.0, 99.2)
            avg_latency = clamp(profile.latency_base + rng.uniform(-3.0, 5.5) + load * 0.05, 5.0, 95.0)
            congestion_rate = clamp(load * 0.86 + rng.uniform(-4.0, 5.0), 10.0, 97.0)
            active_alerts = max(0, int(round(congestion_rate / 17.0 + rng.uniform(-1.0, 1.0))))
            anomalies_count = max(0, int(round(active_alerts * 0.65 + rng.uniform(0.0, 1.5))))

            region = db.scalar(select(Region).where(Region.code == profile.code))
            db.add(
                DashboardSnapshot(
                    region_id=region.id if region else None,
                    sla_percent=round(sla_percent, 2),
                    avg_latency_ms=round(avg_latency, 2),
                    congestion_rate=round(congestion_rate, 2),
                    active_alerts_count=active_alerts,
                    anomalies_count=anomalies_count,
                    total_sessions=session_count,
                    generated_at=generated_at,
                )
            )
            inserted_snapshots += 1

            national_weight += session_count
            national_sla += sla_percent * session_count
            national_latency += avg_latency * session_count
            national_congestion += congestion_rate * session_count
            national_alerts += active_alerts
            national_anomalies += anomalies_count
            national_sessions += session_count

        db.add(
            DashboardSnapshot(
                region_id=None,
                sla_percent=round(national_sla / national_weight, 2),
                avg_latency_ms=round(national_latency / national_weight, 2),
                congestion_rate=round(national_congestion / national_weight, 2),
                active_alerts_count=national_alerts,
                anomalies_count=national_anomalies,
                total_sessions=national_sessions,
                generated_at=generated_at,
            )
        )
        inserted_snapshots += 1

    return inserted_snapshots


def main() -> None:
    db = SessionLocal()
    try:
        upsert_users(db)
        regions_by_code = upsert_regions(db)
        reset_runtime_data(db)
        sessions_count = seed_sessions_and_predictions(db, regions_by_code)
        snapshots_count = seed_snapshots(db)
        db.commit()
        print(
            f"[seed] OK: {len(DEMO_USERS)} users, {len(regions_by_code)} regions, "
            f"{sessions_count} sessions, {sessions_count} predictions, {snapshots_count} snapshots."
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
