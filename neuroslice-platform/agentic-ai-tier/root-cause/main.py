from __future__ import annotations

import json
import logging
from typing import Any, Dict

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
import uvicorn

from agent import RCAAgentError, RCAAgentService
from models import ManualScanRequest, ManualScanResponse, RCAErrorResponse
from tools import fetch_influx_kpis_raw, fetch_redis_state_raw

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")

app = FastAPI(
    title="NeuroSlice Root Cause Agent",
    version="1.0.0",
    description="Manual RCA scanning service powered by LangChain + Ollama",
)

agent_service = RCAAgentService()


def _serialize_time_range(time_range: Dict[str, str]) -> str:
    return json.dumps(time_range, separators=(",", ":"), ensure_ascii=True)


def _collect_raw_diagnostics(slice_id: str, time_range: Dict[str, str]) -> Dict[str, Any]:
    serialized_range = _serialize_time_range(time_range)
    diagnostics: Dict[str, Any] = {"slice_id": slice_id, "time_range": time_range}

    try:
        diagnostics["influx"] = fetch_influx_kpis_raw(slice_id=slice_id, time_range=serialized_range)
    except Exception as exc:
        logger.exception("Failed to fetch Influx diagnostics: %s", exc)
        diagnostics["influx_error"] = str(exc)

    try:
        diagnostics["redis"] = fetch_redis_state_raw(slice_id=slice_id)
    except Exception as exc:
        logger.exception("Failed to fetch Redis diagnostics: %s", exc)
        diagnostics["redis_error"] = str(exc)

    return diagnostics


@app.exception_handler(RCAAgentError)
async def handle_rca_agent_error(_: Request, exc: RCAAgentError) -> JSONResponse:
    diagnostics = dict(exc.diagnostics or {})
    if exc.raw_output:
        diagnostics["raw_agent_output"] = exc.raw_output

    payload = RCAErrorResponse(
        error="SERVICE_UNAVAILABLE",
        message=exc.message,
        diagnostics=diagnostics or None,
    )
    return JSONResponse(status_code=503, content=payload.model_dump(exclude_none=True))


@app.exception_handler(Exception)
async def handle_unexpected_error(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled RCA service error: %s", exc)
    payload = RCAErrorResponse(
        error="INTERNAL_SERVER_ERROR",
        message="Unexpected RCA service failure.",
    )
    return JSONResponse(status_code=500, content=payload.model_dump(exclude_none=True))


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok", "service": "root-cause-agent"}


@app.post(
    "/internal/rca/manual-scan",
    response_model=ManualScanResponse,
    responses={
        503: {"model": RCAErrorResponse, "description": "Ollama/agent failure with diagnostics"},
        500: {"model": RCAErrorResponse, "description": "Unexpected RCA service failure"},
    },
)
def manual_scan(request: ManualScanRequest) -> ManualScanResponse:
    diagnostics = _collect_raw_diagnostics(
        slice_id=request.slice_id,
        time_range=request.time_range.model_dump(),
    )

    try:
        return agent_service.analyze_manual_scan(
            slice_id=request.slice_id,
            domain=request.domain.value if request.domain else None,
            time_range=request.time_range.model_dump(),
        )
    except RCAAgentError as exc:
        merged_diagnostics = dict(diagnostics)
        merged_diagnostics.update(exc.diagnostics or {})
        raise RCAAgentError(
            message=exc.message,
            diagnostics=merged_diagnostics,
            raw_output=exc.raw_output,
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unexpected error while processing manual RCA scan: %s", exc)
        raise HTTPException(status_code=500, detail="Unexpected RCA service failure.") from exc


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=7005, log_level="info")
