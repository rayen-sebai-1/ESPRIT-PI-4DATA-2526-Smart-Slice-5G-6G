"""Deterministic remediation recommendation rules."""
from __future__ import annotations

from typing import Any

from .schemas import ActionStatus, ActionType, PolicyDecision, RiskLevel


class PolicyEngine:
    def decide(self, alert: dict[str, Any]) -> PolicyDecision:
        alert_type = str(alert.get("alert_type") or "").upper()
        severity = str(alert.get("severity") or "").upper()

        if alert_type == "CONGESTION" and severity in {"HIGH", "CRITICAL"}:
            return PolicyDecision(
                action_type=ActionType.RECOMMEND_PCF_QOS_UPDATE,
                risk_level=RiskLevel.MEDIUM,
                requires_approval=True,
                status=ActionStatus.PENDING_APPROVAL,
                reason=f"{severity} congestion requires operator-approved QoS policy review.",
                policy_id="POLICY-CONGESTION-HIGH",
            )

        if alert_type == "SLA_RISK" and severity == "CRITICAL":
            return PolicyDecision(
                action_type=ActionType.RECOMMEND_REROUTE_SLICE,
                risk_level=RiskLevel.HIGH,
                requires_approval=True,
                status=ActionStatus.PENDING_APPROVAL,
                reason="Critical SLA risk requires operator-approved slice reroute recommendation.",
                policy_id="POLICY-SLA-CRITICAL",
            )

        if alert_type == "SLA_RISK" and severity == "HIGH":
            return PolicyDecision(
                action_type=ActionType.INVESTIGATE_CONTEXT,
                risk_level=RiskLevel.MEDIUM,
                requires_approval=True,
                status=ActionStatus.PENDING_APPROVAL,
                reason="High SLA risk requires contextual investigation before remediation.",
                policy_id="POLICY-SLA-HIGH",
            )

        if alert_type == "SLICE_MISMATCH":
            return PolicyDecision(
                action_type=ActionType.RECOMMEND_INSPECT_SLICE_POLICY,
                risk_level=RiskLevel.LOW,
                requires_approval=True,
                status=ActionStatus.PENDING_APPROVAL,
                reason="Slice classification mismatch requires operator inspection of slice policy.",
                policy_id="POLICY-SLICE-MISMATCH",
            )

        if alert_type == "FAULT_EVENT":
            return PolicyDecision(
                action_type=ActionType.INVESTIGATE_CONTEXT,
                risk_level=RiskLevel.LOW,
                requires_approval=True,
                status=ActionStatus.PENDING_APPROVAL,
                reason="Fault event requires operator investigation before any remediation.",
                policy_id="POLICY-FAULT-EVENT",
            )

        return PolicyDecision(
            action_type=ActionType.NO_ACTION,
            risk_level=RiskLevel.LOW,
            requires_approval=False,
            status=ActionStatus.EXECUTED_SIMULATED,
            reason=f"No deterministic policy matched alert_type={alert_type or 'UNKNOWN'} severity={severity or 'UNKNOWN'}.",
            policy_id="POLICY-NO-MATCH",
        )
