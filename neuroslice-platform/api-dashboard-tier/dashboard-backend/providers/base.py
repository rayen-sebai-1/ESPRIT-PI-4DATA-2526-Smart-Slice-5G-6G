from __future__ import annotations

from abc import ABC, abstractmethod

from schemas import (
    ModelInfo,
    NationalDashboardResponse,
    PredictionResponse,
    RegionDashboardResponse,
    RunBatchRequest,
    SessionListResponse,
    SessionSummary,
)


class DashboardDataProvider(ABC):
    name = "base"

    @abstractmethod
    def get_national_dashboard(self) -> NationalDashboardResponse:
        raise NotImplementedError

    @abstractmethod
    def get_region_dashboard(self, region_id: int) -> RegionDashboardResponse | None:
        raise NotImplementedError

    @abstractmethod
    def list_sessions(
        self,
        *,
        region: str | None,
        risk: str | None,
        slice_type: str | None,
        page: int,
        page_size: int,
    ) -> SessionListResponse:
        raise NotImplementedError

    @abstractmethod
    def get_session(self, session_id: int) -> SessionSummary | None:
        raise NotImplementedError

    @abstractmethod
    def list_predictions(
        self,
        *,
        region: str | None,
        risk: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[PredictionResponse], object]:
        raise NotImplementedError

    @abstractmethod
    def get_prediction(self, session_id: int) -> PredictionResponse | None:
        raise NotImplementedError

    @abstractmethod
    def run_prediction(self, session_id: int) -> PredictionResponse | None:
        raise NotImplementedError

    @abstractmethod
    def run_batch(self, payload: RunBatchRequest) -> list[PredictionResponse]:
        raise NotImplementedError

    @abstractmethod
    def list_models(self) -> list[ModelInfo]:
        raise NotImplementedError
