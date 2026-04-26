from __future__ import annotations

import ast
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Sequence

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from pydantic import ValidationError

from models import ManualScanResponse
from tools import fetch_influx_kpis, fetch_redis_state

CHAT_OLLAMA_PROVIDER = "unavailable"

try:
    from langchain_ollama import ChatOllama  # type: ignore
    CHAT_OLLAMA_PROVIDER = "langchain_ollama"
except Exception:  # pragma: no cover - defensive import fallback
    try:
        from langchain_community.chat_models import ChatOllama
        CHAT_OLLAMA_PROVIDER = "langchain_community"
    except Exception:  # pragma: no cover - defensive import fallback
        ChatOllama = None  # type: ignore

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
You are NeuroSlice-RCA, an autonomous 5G/6G telecom root cause analysis specialist.
Your responsibility is to diagnose slice degradation using telemetry and live state context.

You MUST reason with this canonical schema vocabulary:
- InfluxDB org: neuroslice
- InfluxDB bucket: telemetry
- Measurement telemetry:
  - Tags: domain, entity_id, entity_type, slice_id, slice_type
  - Fields include kpi_* (e.g., kpi_cpuUtilPct, kpi_packetLossPct, kpi_forwardingLatencyMs, kpi_rbUtilizationPct),
    derived_congestionScore, derived_healthScore, derived_misroutingScore, severity
- Measurement faults:
  - Tags: type (aggregate|fault), fault_id, fault_type, scenario_id, affected_entities
  - Fields: active_count, severity, active
- AIOps measurements:
  - aiops_congestion, aiops_slice_classification, aiops_sla with tags service, entity_id, entity_type, site_id, slice_id

Entity vocabulary:
- domain: core | edge | ran
- entity_type: amf | smf | upf | edge_upf | mec_app | compute_node | gnb | cell
- slice_type: eMBB | URLLC | mMTC
- fault_type: ran_congestion | edge_overload | amf_degradation | upf_overload | packet_loss_spike |
              latency_spike | telemetry_drop | malformed_telemetry | slice_misrouting

Critical interpretation rules:
1) Slice events are often emitted with entity_type=cell, but the RCA key is slice_id. Prioritize slice_id correlation.
2) If derived_congestionScore is high and faults include ran_congestion, verify kpi_rbUtilizationPct elevation.
3) If packet_loss_spike appears, validate with kpi_packetLossPct trend and latency escalation.
4) If derived_misroutingScore is high, investigate slice_misrouting and inconsistent slice_type signals.
5) Use faults.active and active_count to separate currently active causes from stale events.
6) Prefer explanations that connect at least one fault signal with KPI evidence and affected entities.
7) Tool output is already aggregated for a local 32k-context qwen2.5 model. Use aggregated evidence, not raw telemetry.
8) Prefer deterministic summary fields: p95, max, last, trend, breach_count, active faults, Redis entity state, and AIOps outputs.
9) Do not invent unavailable KPI values. If InfluxDB or Redis returns no data, state uncertainty clearly.

Tooling policy (mandatory):
- You MUST call fetch_influx_kpis and fetch_redis_state before giving any final answer.
- Call each required tool exactly once unless the call fails.
- After both tools succeed, immediately return the final JSON and stop.
- Do not produce final output if one required tool call is missing.
- If a tool fails, attempt diagnosis with available data and clearly state uncertainty in summary/rootCause.

Output policy (strict):
- Return exactly one JSON object.
- No markdown, no code fences, no extra prose.
- JSON keys must be exactly:
  summary (string),
  rootCause (string),
  affectedEntities (array of strings),
  evidenceKpis (object),
  recommendedAction (array of strings)
"""


class RCAAgentError(RuntimeError):
    def __init__(
        self,
        message: str,
        diagnostics: Optional[Dict[str, Any]] = None,
        raw_output: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.diagnostics = diagnostics or {}
        self.raw_output = raw_output


class RCAAgentService:
    def __init__(self) -> None:
        self._required_tools = {"fetch_influx_kpis", "fetch_redis_state"}
        self._tools = [fetch_influx_kpis, fetch_redis_state]
        self._max_retries = max(1, int(os.getenv("RCA_AGENT_MAX_RETRIES", "3")))
        self._enable_heuristic_fallback = os.getenv("RCA_ENABLE_HEURISTIC_FALLBACK", "true").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        self._initialization_error: Optional[Exception] = None
        self._executor: Optional[AgentExecutor] = None
        self._initialize_agent_executor()

    def _initialize_agent_executor(self) -> None:
        model_name = os.getenv("RCA_OLLAMA_MODEL", "qwen2.5:3b-instruct")
        ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

        try:
            if ChatOllama is None:
                raise ImportError(
                    "ChatOllama is unavailable. Install langchain-ollama for tool-calling compatibility."
                )
            llm = ChatOllama(
                base_url=ollama_base_url,
                model=model_name,
                num_ctx=32768,
                temperature=0.0,
            )
            # Guard against ChatOllama variants where bind_tools exists but is not implemented.
            try:
                llm.bind_tools(self._tools)
            except NotImplementedError as bind_exc:
                raise RuntimeError(
                    f"Loaded ChatOllama provider '{CHAT_OLLAMA_PROVIDER}' does not implement bind_tools. "
                    "Use langchain_ollama.ChatOllama (install langchain-ollama and rebuild the root-cause image)."
                ) from bind_exc

            prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", SYSTEM_PROMPT),
                    ("human", "{input}"),
                    MessagesPlaceholder("agent_scratchpad"),
                ]
            )
            agent = create_tool_calling_agent(
                llm=llm,
                tools=self._tools,
                prompt=prompt,
            )
            self._executor = AgentExecutor(
                agent=agent,
                tools=self._tools,
                verbose=False,
                max_iterations=6,
                # "force" is the most compatible option across LangChain 0.2.x variants.
                early_stopping_method="force",
                handle_parsing_errors=True,
                return_intermediate_steps=True,
            )
            logger.info(
                "RCA agent initialized with provider=%s, model=%s, base_url=%s, num_ctx=32768",
                CHAT_OLLAMA_PROVIDER,
                model_name,
                ollama_base_url,
            )
        except Exception as exc:
            logger.exception("Failed to initialize RCA agent executor: %s", exc)
            self._initialization_error = exc
            self._executor = None

    def analyze_manual_scan(
        self,
        slice_id: str,
        domain: Optional[str],
        time_range: Dict[str, str],
    ) -> ManualScanResponse:
        if self._initialization_error is not None:
            raise RCAAgentError(
                "RCA agent initialization failed. Verify LangChain tool-calling compatibility and Ollama availability.",
                raw_output=str(self._initialization_error),
            ) from self._initialization_error

        if self._executor is None:
            raise RCAAgentError("RCA agent executor is not initialized.")

        attempt_feedback = ""
        last_output: Optional[str] = None
        last_error: Optional[Exception] = None

        for attempt in range(1, self._max_retries + 1):
            input_prompt = self._build_request_prompt(
                slice_id=slice_id,
                domain=domain,
                time_range=time_range,
                feedback=attempt_feedback,
            )
            try:
                result = self._executor.invoke({"input": input_prompt})
                intermediate_steps = result.get("intermediate_steps", [])
                used_tools = self._extract_used_tools(intermediate_steps)

                if not self._required_tools.issubset(set(used_tools)):
                    missing = sorted(self._required_tools.difference(set(used_tools)))
                    raise ValueError(f"Agent response rejected because required tool calls are missing: {missing}")

                raw_output = str(result.get("output", "")).strip()
                if not raw_output:
                    raise ValueError("Agent produced an empty output payload")
                last_output = raw_output

                try:
                    parsed = self._extract_json_object(raw_output)
                    response = ManualScanResponse.model_validate(parsed)
                    return response
                except (ValueError, json.JSONDecodeError, ValidationError) as parse_exc:
                    if self._enable_heuristic_fallback:
                        fallback_response = self._build_heuristic_response(
                            slice_id=slice_id,
                            domain=domain,
                            time_range=time_range,
                            intermediate_steps=intermediate_steps,
                        )
                        if fallback_response is not None:
                            logger.warning(
                                "RCA response used heuristic fallback after parse failure: %s",
                                parse_exc,
                            )
                            return fallback_response
                    raise parse_exc
            except (ValueError, json.JSONDecodeError, ValidationError) as exc:
                last_error = exc
                attempt_feedback = (
                    "Previous attempt failed validation. Re-run both required tools and return only one strict JSON object "
                    f"that matches the required schema. Validation error: {exc}"
                )
                logger.warning("RCA output validation failed on attempt %d/%d: %s", attempt, self._max_retries, exc)
            except Exception as exc:
                last_error = exc
                attempt_feedback = (
                    "Previous attempt failed execution. Re-run both required tools before finalizing the RCA JSON output. "
                    f"Execution error: {exc}"
                )
                logger.warning("RCA execution failed on attempt %d/%d: %s", attempt, self._max_retries, exc)

        message = "RCA agent failed to produce a valid JSON response after controlled retries."
        if last_error is not None:
            message = f"{message} Last error: {last_error}"
        raise RCAAgentError(message=message, raw_output=last_output)

    @staticmethod
    def _build_request_prompt(
        slice_id: str,
        domain: Optional[str],
        time_range: Dict[str, str],
        feedback: str,
    ) -> str:
        domain_value = domain or "not_provided"
        time_range_str = json.dumps(time_range, separators=(",", ":"), ensure_ascii=True)
        guidance = (
            "Manual scan request context:\n"
            f"- slice_id: {slice_id}\n"
            f"- domain: {domain_value}\n"
            f"- time_range: {time_range_str}\n\n"
            "Required process:\n"
            "1. Call fetch_influx_kpis(slice_id, time_range) exactly with this slice_id and time_range string.\n"
            "2. Call fetch_redis_state(slice_id).\n"
            "3. Call each tool once unless it errors.\n"
            "4. Correlate KPI trends, fault_type signals, and slice-level state.\n"
            "5. Return strict JSON only with keys: summary, rootCause, affectedEntities, evidenceKpis, recommendedAction.\n"
        )
        if feedback:
            guidance = f"{guidance}\nRetry correction:\n{feedback}\n"
        return guidance

    @staticmethod
    def _extract_used_tools(intermediate_steps: Sequence[Any]) -> List[str]:
        used: List[str] = []
        for step in intermediate_steps:
            tool_name: Optional[str] = None
            if isinstance(step, tuple) and step:
                tool_name = getattr(step[0], "tool", None)
            elif hasattr(step, "tool"):
                tool_name = getattr(step, "tool")
            elif isinstance(step, dict):
                raw_name = step.get("tool")
                if isinstance(raw_name, str):
                    tool_name = raw_name

            if tool_name:
                used.append(tool_name)
        return used

    @staticmethod
    def _extract_json_object(raw_output: str) -> Dict[str, Any]:
        cleaned = raw_output.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, count=1, flags=re.IGNORECASE)
            cleaned = re.sub(r"\s*```$", "", cleaned, count=1)

        try:
            parsed = json.loads(cleaned)
            if not isinstance(parsed, dict):
                raise ValueError("Agent output must be a JSON object")
            return parsed
        except json.JSONDecodeError:
            candidate = RCAAgentService._extract_first_braced_block(cleaned)
            parsed = json.loads(candidate)
            if not isinstance(parsed, dict):
                raise ValueError("Agent output must be a JSON object")
            return parsed

    @staticmethod
    def _extract_first_braced_block(text: str) -> str:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise json.JSONDecodeError("No JSON object found in model output", text, 0)
        return match.group(0)

    @staticmethod
    def _coerce_to_dict(value: Any) -> Optional[Dict[str, Any]]:
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return None
            try:
                decoded = json.loads(stripped)
                if isinstance(decoded, dict):
                    return decoded
            except json.JSONDecodeError:
                pass
            try:
                decoded = ast.literal_eval(stripped)
                if isinstance(decoded, dict):
                    return decoded
            except Exception:
                return None
        return None

    def _extract_tool_payloads(self, intermediate_steps: Sequence[Any]) -> Dict[str, Dict[str, Any]]:
        payloads: Dict[str, Dict[str, Any]] = {}
        for step in intermediate_steps:
            tool_name: Optional[str] = None
            observation: Any = None
            if isinstance(step, tuple) and len(step) >= 2:
                tool_name = getattr(step[0], "tool", None)
                observation = step[1]
            elif isinstance(step, dict):
                raw_name = step.get("tool")
                if isinstance(raw_name, str):
                    tool_name = raw_name
                    observation = step.get("observation")

            if not tool_name:
                continue
            payload = self._coerce_to_dict(observation)
            if payload is not None:
                payloads[tool_name] = payload
        return payloads

    def _build_heuristic_response(
        self,
        slice_id: str,
        domain: Optional[str],
        time_range: Dict[str, str],
        intermediate_steps: Sequence[Any],
    ) -> Optional[ManualScanResponse]:
        payloads = self._extract_tool_payloads(intermediate_steps)
        influx = payloads.get("fetch_influx_kpis")
        redis_state = payloads.get("fetch_redis_state")
        if influx is None or redis_state is None:
            return None

        telemetry = influx.get("telemetry", {}) if isinstance(influx, dict) else {}
        faults = influx.get("faults", {}) if isinstance(influx, dict) else {}
        telemetry_groups = telemetry.get("groups", []) if isinstance(telemetry, dict) else []
        if not isinstance(telemetry_groups, list):
            telemetry_groups = []

        def _field_max(field: str) -> Optional[float]:
            values = []
            for group in telemetry_groups:
                if isinstance(group, dict) and group.get("field") == field:
                    try:
                        values.append(float(group.get("max") or 0))
                    except (TypeError, ValueError):
                        continue
            return max(values) if values else None

        def _field_min(field: str) -> Optional[float]:
            values = []
            for group in telemetry_groups:
                if isinstance(group, dict) and group.get("field") == field:
                    try:
                        values.append(float(group.get("min") or 0))
                    except (TypeError, ValueError):
                        continue
            return min(values) if values else None

        def _round_optional(value: Optional[float], digits: int) -> Optional[float]:
            return round(float(value), digits) if value is not None else None

        def _field_trends(field: str) -> List[str]:
            trends = []
            for group in telemetry_groups:
                if isinstance(group, dict) and group.get("field") == field and group.get("trend"):
                    trends.append(str(group.get("trend")))
            return sorted(set(trends))

        peak_congestion = _field_max("derived_congestionScore")
        peak_rb = _field_max("kpi_rbUtilizationPct")
        peak_packet_loss = _field_max("kpi_packetLossPct")
        peak_latency = _field_max("kpi_forwardingLatencyMs")
        min_health = _field_min("derived_healthScore")

        active_faults: List[Dict[str, Any]] = []
        if isinstance(faults, dict):
            for key in ("active_faults", "redis_active_faults"):
                value = faults.get(key, [])
                if isinstance(value, list):
                    active_faults.extend([item for item in value if isinstance(item, dict)])
        if isinstance(redis_state, dict):
            value = redis_state.get("active_faults", [])
            if isinstance(value, list):
                active_faults.extend([item for item in value if isinstance(item, dict)])

        active_fault_types = sorted(
            {
                str(fault.get("fault_type")).strip()
                for fault in active_faults
                if str(fault.get("fault_type") or "").strip()
            }
        )

        affected_entities: List[str] = []
        for fault in active_faults:
            raw_affected = fault.get("affected_entities", [])
            if isinstance(raw_affected, list):
                affected_entities.extend([str(entity) for entity in raw_affected if str(entity).strip()])
        if isinstance(redis_state, dict):
            entities = redis_state.get("entities", {})
            if isinstance(entities, dict):
                affected_entities.extend([str(entity_id) for entity_id in entities.keys() if str(entity_id).strip()])
        telemetry_summary = telemetry.get("summary", {}) if isinstance(telemetry, dict) else {}
        top_entities = telemetry_summary.get("top_anomalous_entities", []) if isinstance(telemetry_summary, dict) else []
        if isinstance(top_entities, list):
            for entity in top_entities:
                if isinstance(entity, dict) and entity.get("entity_id"):
                    affected_entities.append(str(entity["entity_id"]))
        affected_entities = sorted(set(affected_entities))

        if "ran_congestion" in active_fault_types and (peak_congestion or 0) >= 0.8 and (peak_rb or 0) >= 90:
            root_cause = (
                "Likely RAN congestion on cell/gnb resources impacting the slice, supported by active ran_congestion "
                "faults with high radio block utilization and elevated congestion score."
            )
            summary = (
                f"Slice {slice_id} is degraded due to congestion-driven radio pressure; packet loss and latency trends "
                "indicate service quality erosion in the selected window."
            )
            recommended_action = [
                "Apply RAN load balancing and admission control tuning on the affected gNB/cell.",
                "Temporarily prioritize URLLC scheduling weights for the impacted slice.",
                "Re-route edge traffic bursts to alternate cell sectors where capacity is available.",
            ]
        elif "packet_loss_spike" in active_fault_types and (peak_packet_loss or 0) >= 3:
            root_cause = (
                "Primary issue appears to be packet loss escalation, likely linked to transient forwarding congestion "
                "across slice path entities."
            )
            summary = (
                f"Slice {slice_id} shows packet-loss-driven degradation with correlated latency increase and low health score."
            )
            recommended_action = [
                "Inspect UPF and edge transport queues for buffer pressure and drops.",
                "Enable short-term traffic shaping for bursty flows on this slice.",
                "Validate QoS profile consistency between RAN and edge forwarding policies.",
            ]
        elif telemetry.get("status") == "no_data" or influx.get("status") == "error" or redis_state.get("status") == "error":
            root_cause = (
                "RCA confidence is limited because one or more telemetry sources returned no data or an error. "
                "No unavailable KPI values were inferred."
            )
            summary = f"Slice {slice_id} could not be diagnosed confidently from the available summarized evidence."
            recommended_action = [
                "Verify InfluxDB and Redis connectivity for the agent containers.",
                "Confirm normalized telemetry is flowing on stream:norm.telemetry and into the telemetry bucket.",
                "Repeat the scan after the default 30-minute window contains fresh samples.",
            ]
        else:
            root_cause = (
                "Slice degradation is likely multifactorial with active faults and KPI stress signals present, "
                "but no single fault pattern is dominant."
            )
            summary = f"Slice {slice_id} is degraded with active faults and reduced health indicators."
            recommended_action = [
                "Correlate per-entity CPU, queue, and latency counters to isolate the tightest bottleneck.",
                "Audit recent policy/config changes affecting slice routing and scheduling.",
                "Increase telemetry sampling temporarily to improve RCA confidence.",
            ]

        evidence_kpis: Dict[str, Any] = {
            "requestedDomain": domain or "not_provided",
            "timeRange": time_range,
            "telemetryStatus": telemetry.get("status"),
            "influxStatus": influx.get("status"),
            "redisStatus": redis_state.get("status"),
            "activeFaultTypes": sorted(set(active_fault_types)),
            "peakDerivedCongestionScore": _round_optional(peak_congestion, 4),
            "peakRbUtilizationPct": _round_optional(peak_rb, 2),
            "peakPacketLossPct": _round_optional(peak_packet_loss, 2),
            "peakForwardingLatencyMs": _round_optional(peak_latency, 2),
            "minDerivedHealthScore": _round_optional(min_health, 4),
            "packetLossTrends": _field_trends("kpi_packetLossPct"),
            "latencyTrends": _field_trends("kpi_forwardingLatencyMs"),
            "topAnomalousEntities": top_entities[:5] if isinstance(top_entities, list) else [],
            "topBreachedKpis": telemetry_summary.get("top_breached_kpis", [])[:5]
            if isinstance(telemetry_summary, dict)
            else [],
        }

        return ManualScanResponse(
            summary=summary,
            rootCause=root_cause,
            affectedEntities=affected_entities,
            evidenceKpis=evidence_kpis,
            recommendedAction=recommended_action,
        )
