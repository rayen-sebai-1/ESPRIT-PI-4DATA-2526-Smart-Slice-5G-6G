from __future__ import annotations

from enum import Enum


class UserRole(str, Enum):
    ADMIN = "ADMIN"
    NETWORK_OPERATOR = "NETWORK_OPERATOR"
    NETWORK_MANAGER = "NETWORK_MANAGER"


class RICStatus(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    CRITICAL = "CRITICAL"
    MAINTENANCE = "MAINTENANCE"


class SliceType(str, Enum):
    EMBB = "eMBB"
    URLLC = "URLLC"
    MMTC = "mMTC"
    ERLLC = "ERLLC"
    FEMBB = "feMBB"
    UMMTC = "umMTC"
    MBRLLC = "MBRLLC"
    MURLLC = "mURLLC"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
