"""The three violation categories the system records."""
from __future__ import annotations

from typing import Optional

HELMET = "NO-Hardhat"  # same string the model uses for its "NO-Hardhat" class
VEST = "NO-Safety Vest"  # same string the model uses for its "NO-Safety Vest" class
COMBINED = "COMBINED"  # helmet AND vest missing: one incident, not two

ALL_TYPES = (HELMET, VEST, COMBINED)

LABELS = {
    HELMET: "Missing helmet",
    VEST: "Missing safety vest",
    COMBINED: "Missing helmet + vest",
}


def classify(has_hardhat: bool, has_vest: bool) -> Optional[str]:
    """Return the violation type for a worker's PPE status, or None if compliant."""
    if not has_hardhat and not has_vest:
        return COMBINED
    if not has_hardhat:
        return HELMET
    if not has_vest:
        return VEST
    return None


def missing_items(violation_type: str) -> list[str]:
    if violation_type == COMBINED:
        return ["Hardhat", "Safety Vest"]
    if violation_type == HELMET:
        return ["Hardhat"]
    if violation_type == VEST:
        return ["Safety Vest"]
    return []
