from __future__ import annotations

import logging
from typing import AsyncIterator, Dict

from fastapi import FastAPI, HTTPException, Request
from sse_starlette.sse import EventSourceResponse
import uvicorn

from agent import CopilotAgentError, CopilotAgentService, OllamaConnectionError, OllamaTimeoutError
from models import CopilotQueryRequest, CopilotQueryResponse, SSEErrorPayload

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")

app = FastAPI(
    title="NeuroSlice Copilot Agent",
    version="1.0.0",
    description="Conversational NOC copilot with LangChain tools, Redis memory, and SSE streaming.",
)

agent_service = CopilotAgentService()


def _sse_event(event: str, data: str) -> Dict[str, str]:
    return {"event": event, "data": data}


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok", "service": "copilot-agent"}


@app.post("/copilot/query")
async def copilot_query(payload: CopilotQueryRequest, request: Request) -> EventSourceResponse:
    async def stream() -> AsyncIterator[Dict[str, str]]:
        try:
            async for token in agent_service.stream_query(payload.query, payload.session_id):
                if await request.is_disconnected():
                    logger.info("SSE client disconnected for session_id=%s", payload.session_id)
                    return
                yield _sse_event("token", token)

            if not await request.is_disconnected():
                yield _sse_event("done", "[DONE]")
        except OllamaTimeoutError as exc:
            logger.warning("Ollama timeout for session_id=%s: %s", payload.session_id, exc)
            error = SSEErrorPayload(code="OLLAMA_TIMEOUT", message=str(exc))
            yield _sse_event("error", error.model_dump_json())
        except OllamaConnectionError as exc:
            logger.warning("Ollama connection error for session_id=%s: %s", payload.session_id, exc)
            error = SSEErrorPayload(code="OLLAMA_CONNECTION_ERROR", message=str(exc))
            yield _sse_event("error", error.model_dump_json())
        except CopilotAgentError as exc:
            logger.exception("Copilot agent error for session_id=%s: %s", payload.session_id, exc)
            error = SSEErrorPayload(code="COPILOT_AGENT_ERROR", message=str(exc))
            yield _sse_event("error", error.model_dump_json())
        except Exception as exc:
            logger.exception("Unexpected copilot service error for session_id=%s: %s", payload.session_id, exc)
            error = SSEErrorPayload(
                code="INTERNAL_SERVER_ERROR",
                message="Unexpected copilot service failure.",
                details={"exception": str(exc)},
            )
            yield _sse_event("error", error.model_dump_json())

    return EventSourceResponse(
        stream(),
        media_type="text/event-stream",
        ping=15,
    )


@app.post("/copilot/query/text", response_model=CopilotQueryResponse)
async def copilot_query_text(payload: CopilotQueryRequest) -> CopilotQueryResponse:
    try:
        chunks = []
        async for token in agent_service.stream_query(payload.query, payload.session_id):
            chunks.append(token)
        return CopilotQueryResponse(
            session_id=payload.session_id,
            answer="".join(chunks).strip(),
        )
    except OllamaTimeoutError as exc:
        logger.warning("Ollama timeout for session_id=%s: %s", payload.session_id, exc)
        raise HTTPException(status_code=504, detail={"code": "OLLAMA_TIMEOUT", "message": str(exc)}) from exc
    except OllamaConnectionError as exc:
        logger.warning("Ollama connection error for session_id=%s: %s", payload.session_id, exc)
        raise HTTPException(
            status_code=503,
            detail={"code": "OLLAMA_CONNECTION_ERROR", "message": str(exc)},
        ) from exc
    except CopilotAgentError as exc:
        logger.exception("Copilot agent error for session_id=%s: %s", payload.session_id, exc)
        raise HTTPException(
            status_code=500,
            detail={"code": "COPILOT_AGENT_ERROR", "message": str(exc)},
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected copilot service error for session_id=%s: %s", payload.session_id, exc)
        raise HTTPException(
            status_code=500,
            detail={
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Unexpected copilot service failure.",
                "details": {"exception": str(exc)},
            },
        ) from exc


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=7006, log_level="info")
