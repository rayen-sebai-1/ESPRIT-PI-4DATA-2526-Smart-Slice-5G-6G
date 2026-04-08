from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "NeuroSlice Tunisia"
    service_name: str = "neuroslice-service"
    environment: str = "development"
    database_url: str = "postgresql+psycopg://neuroslice:neuroslice123@postgres:5432/neuroslice_tunisia"
    secret_key: str = "change-this-in-production"
    access_token_expire_minutes: int = 180
    prediction_provider: str = "hybrid"
    sla_model_path: str = "data/models/sla/model_b_sla_5g_boosting.pkl"
    sla_scaler_path: str = "data/models/sla/scaler_sla_5g.pkl"
    sla_metadata_path: str = "data/models/sla/metadata_model_b.json"
    sla_dataset_path: str = "data/raw/train_dataset.csv"
    congestion_model_path: str = "data/models/congestion/model_congestion_timeseries_boosting.pkl"
    congestion_metadata_path: str = "data/models/congestion/metadata_congestion_timeseries.json"
    congestion_dataset_path: str = "data/raw/network_slicing_dataset_enriched_timeseries.csv"
    anomaly_model_path: str = "data/models/anomaly/model_anomaly_misrouting_isolation_forest.pkl"
    anomaly_metadata_path: str = "data/models/anomaly/metadata_anomaly_misrouting.json"
    anomaly_dataset_path: str = "data/raw/network_slicing_dataset_v3.csv"
    slice_model_path: str = "data/models/slice/model_slice_lightgbm.json"
    slice_metadata_path: str = "data/models/slice/metadata_slice_lightgbm.json"
    slice_dataset_path: str = "data/raw/train_dataset.csv"
    reference_manifest_path: str = "data/reference_assets_manifest.json"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
