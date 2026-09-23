"""Explicit execution modes and institutional result labels."""
from enum import Enum


class ExecutionProfile(str, Enum):
    REFERENCE_DEMO = "REFERENCE_DEMO"
    VERIFIED_INSTITUTIONAL = "VERIFIED_INSTITUTIONAL"


def execution_profile(value) -> ExecutionProfile:
    try:
        return ExecutionProfile(str(value or "").strip().upper())
    except ValueError as exc:
        raise ValueError("execution_profile must be REFERENCE_DEMO or VERIFIED_INSTITUTIONAL.") from exc


def authority_label(profile: ExecutionProfile, *, synthetic: bool) -> str:
    if profile is ExecutionProfile.REFERENCE_DEMO:
        return "REFERENCE MODEL / DEMO DATA"
    return "SYNTHETIC / NOT_OFFICIAL" if synthetic else "VERIFIED INSTITUTIONAL INPUTS"


def result_classification(profile: ExecutionProfile, *, synthetic: bool) -> str:
    if profile is ExecutionProfile.REFERENCE_DEMO:
        return "REFERENCE_MODEL_OUTPUT"
    return "SYNTHETIC_TEST_OUTPUT" if synthetic else "VERIFIED_INSTITUTIONAL_MODEL_OUTPUT"
