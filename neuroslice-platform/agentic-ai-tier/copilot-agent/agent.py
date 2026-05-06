from __future__ import annotations

import logging
import os
from typing import Any, AsyncIterator, Dict, Optional

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_community.chat_message_histories import RedisChatMessageHistory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory

from tools import fetch_influx_kpis, fetch_redis_state

try:
    from langchain_ollama import ChatOllama
except Exception:  # pragma: no cover - dependency fallback
    ChatOllama = None  # type: ignore

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
You are NeuroSlice Copilot Agent, assisting NOC operators with 5G/6G slice telemetry investigations.
You explain clearly, stay concise, and provide actionable operator guidance.

Canonical telemetry contract (must be respected in reasoning and tool usage):
- InfluxDB org: neuroslice
- InfluxDB bucket: telemetry
- Enums:
  domain = core | edge | ran
  entity_type = amf | smf | upf | edge_upf | mec_app | compute_node | gnb | cell
  slice_type = eMBB | URLLC | mMTC
- telemetry measurement:
  tags = domain, entity_id, entity_type, slice_id, slice_type
  fields = kpi_* (e.g. kpi_cpuUtilPct, kpi_packetLossPct, kpi_rbUtilizationPct),
           derived_congestionScore, derived_healthScore
- faults measurement:
  tags = type, fault_id, fault_type
  fields = active_count, severity, active

Behavior policy:
1) Use tools to gather facts before concluding.
2) Correlate KPIs + faults + live state.
3) Highlight uncertainty when evidence is incomplete.
4) Keep final answers operator-friendly and concrete.
5) When calling fetch_redis_state, pass the slice identifier explicitly as `slice_id`.
6) Tool results are compact summaries from real InfluxDB/Redis, not mock data. Use p95, max, last, trend, breach_count, active faults, Redis entity state, and AIOps outputs.
7) Do not dump huge JSON. Summarize the evidence, mention the analysis window, and give concise operational recommendations.
8) If the operator query is under-specified, use the default 30-minute window and ask for missing slice/domain/entity details only when they would change the action.
9) Do not invent unavailable KPI values. Say when InfluxDB or Redis returned no data.
10) If the operator explicitly provided a slice identifier, keep that exact slice identifier in tool calls and in the final response. Never switch to a different slice ID.
"""


class CopilotAgentError(RuntimeError):
    pass


class OllamaConnectionError(CopilotAgentError):
    pass


class OllamaTimeoutError(OllamaConnectionError):
    pass


class CopilotAgentService:
    def __init__(self) -> None:
        self._tools = [fetch_influx_kpis, fetch_redis_state]
        self._model = os.getenv("OLLAMA_MODEL", "qwen2.5:3b-instruct")
        self._base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self._redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self._timeout_seconds = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "60"))
        self._max_iterations = int(os.getenv("COPILOT_AGENT_MAX_ITERATIONS", "8"))
        self._redis_ttl_seconds = int(os.getenv("COPILOT_HISTORY_TTL_SECONDS", "86400"))

        self._executor_with_history: Optional[RunnableWithMessageHistory] = None
        self._initialization_error: Optional[Exception] = None
        self._initialize_agent_executor()

    def _initialize_agent_executor(self) -> None:
        try:
            llm = self._build_chat_ollama_llm()
            # Guard against ChatOllama variants where bind_tools exists but is not implemented.
            llm.bind_tools(self._tools)
            executor = self._build_executor(llm)
            provider = "langchain_ollama.ChatOllama"

            self._executor_with_history = RunnableWithMessageHistory(
                executor,
                self._get_session_history,
                input_messages_key="input",
                history_messages_key="chat_history",
                output_messages_key="output",
            )
            logger.info(
                "Copilot agent initialized with provider=%s model=%s base_url=%s num_ctx=32768",
                provider,
                self._model,
                self._base_url,
            )
        except Exception as exc:
            logger.exception("Failed to initialize Copilot agent: %s", exc)
            self._initialization_error = exc
            self._executor_with_history = None

    def _build_chat_ollama_llm(self) -> Any:
        if ChatOllama is None:
            raise RuntimeError("langchain_ollama is not installed. Install langchain-ollama and rebuild image.")
        try:
            return ChatOllama(
                base_url=self._base_url,
                model=self._model,
                num_ctx=32768,
                temperature=0.0,
                timeout=self._timeout_seconds,
            )
        except TypeError:
            return ChatOllama(
                base_url=self._base_url,
                model=self._model,
                num_ctx=32768,
                temperature=0.0,
            )

    def _build_executor(self, llm: Any) -> AgentExecutor:
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", SYSTEM_PROMPT),
                MessagesPlaceholder("chat_history"),
                ("human", "{input}"),
                MessagesPlaceholder("agent_scratchpad"),
            ]
        )
        agent = create_tool_calling_agent(
            llm=llm,
            tools=self._tools,
            prompt=prompt,
        )
        return AgentExecutor(
            agent=agent,
            tools=self._tools,
            verbose=False,
            max_iterations=self._max_iterations,
            early_stopping_method="force",
            handle_parsing_errors=True,
        )

    def _get_session_history(self, session_id: str) -> RedisChatMessageHistory:
        normalized = session_id.strip()
        if not normalized:
            raise ValueError("session_id cannot be empty")

        try:
            return RedisChatMessageHistory(
                session_id=normalized,
                url=self._redis_url,
                ttl=self._redis_ttl_seconds,
            )
        except TypeError:
            try:
                return RedisChatMessageHistory(
                    session_id=normalized,
                    redis_url=self._redis_url,
                    ttl=self._redis_ttl_seconds,
                )
            except TypeError:
                return RedisChatMessageHistory(
                    session_id=normalized,
                    url=self._redis_url,
                )

    async def stream_query(self, query: str, session_id: str) -> AsyncIterator[str]:
        normalized_query = query.strip()
        normalized_session_id = session_id.strip()
        if not normalized_query:
            raise ValueError("query cannot be empty")
        if not normalized_session_id:
            raise ValueError("session_id cannot be empty")

        if self._initialization_error is not None:
            raise self._map_ollama_error(self._initialization_error, stage="initialization")
        if self._executor_with_history is None:
            raise CopilotAgentError("Copilot agent executor is unavailable.")

        emitted_any_token = False
        final_text_fallback = ""
        config = {"configurable": {"session_id": normalized_session_id}}

        try:
            async for event in self._executor_with_history.astream_events(
                {"input": normalized_query},
                config=config,
                version="v1",
            ):
                event_name = str(event.get("event", ""))
                data = event.get("data", {})

                if event_name in {"on_chat_model_stream", "on_llm_stream"}:
                    token = self._extract_token(data)
                    if token:
                        emitted_any_token = True
                        yield token
                elif event_name == "on_chain_end":
                    final_candidate = self._extract_final_output_text(data)
                    if final_candidate:
                        final_text_fallback = final_candidate

            if not emitted_any_token and final_text_fallback:
                yield final_text_fallback
        except Exception as exc:
            raise self._map_ollama_error(exc, stage="execution") from exc

    @staticmethod
    def _extract_final_output_text(data: Dict[str, Any]) -> str:
        output = data.get("output")
        if isinstance(output, dict):
            candidate = output.get("output")
            if isinstance(candidate, str):
                return candidate
        if isinstance(output, str):
            return output
        return ""

    @staticmethod
    def _extract_token(data: Dict[str, Any]) -> str:
        chunk = data.get("chunk")
        if chunk is None:
            return ""

        if isinstance(chunk, str):
            return chunk

        text_attr = getattr(chunk, "text", None)
        if isinstance(text_attr, str):
            return text_attr

        content = getattr(chunk, "content", None)
        if isinstance(content, str):
            return content

        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    text = item.get("text")
                    if isinstance(text, str):
                        parts.append(text)
            return "".join(parts)

        return ""

    def _map_ollama_error(self, exc: Exception, stage: str) -> CopilotAgentError:
        full_error = self._flatten_exception_messages(exc).lower()

        timeout_markers = (
            "timeout",
            "timed out",
            "readtimeout",
            "connecttimeout",
            "operation timed out",
        )
        connection_markers = (
            "failed to connect",
            "connection refused",
            "max retries exceeded",
            "name or service not known",
            "temporary failure in name resolution",
            "no connection adapters",
            "ollama",
        )

        if any(marker in full_error for marker in timeout_markers):
            return OllamaTimeoutError(
                f"Ollama request timed out during {stage}. "
                f"Verify Ollama at {self._base_url} is reachable and model '{self._model}' is loaded."
            )

        if any(marker in full_error for marker in connection_markers):
            return OllamaConnectionError(
                f"Could not connect to Ollama during {stage}. "
                f"Expected endpoint: {self._base_url} | model: {self._model}."
            )

        return CopilotAgentError(f"Copilot agent failed during {stage}: {self._flatten_exception_messages(exc)}")

    @staticmethod
    def _flatten_exception_messages(exc: Exception) -> str:
        messages = []
        visited = set()
        cursor: Optional[BaseException] = exc
        while cursor is not None and id(cursor) not in visited:
            visited.add(id(cursor))
            text = str(cursor).strip()
            if text:
                messages.append(text)
            cursor = cursor.__cause__ or cursor.__context__
        return " | ".join(messages) if messages else exc.__class__.__name__
