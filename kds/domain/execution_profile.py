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


def effective_execution_profile(project_or_document) -> ExecutionProfile:
    """Return the project-owned execution profile used by every presentation surface."""
    document = project_or_document if isinstance(project_or_document, dict) else {}
    project = document.get("project", document)
    metadata = document.get("metadata", {})
    reference = (
        metadata.get("reference_demo") is True
        or str(metadata.get("classification") or "").strip().upper() == ExecutionProfile.REFERENCE_DEMO.value
        or str(project.get("data_source_notes") or "").strip().casefold() == "reference_demo"
        or metadata.get("source_version") == "v1.0.0-thesis-final"
    )
    return ExecutionProfile.REFERENCE_DEMO if reference else ExecutionProfile.VERIFIED_INSTITUTIONAL


def authority_label(profile: ExecutionProfile, *, synthetic: bool) -> str:
    if profile is ExecutionProfile.REFERENCE_DEMO:
        return "REFERENCE MODEL / DEMO DATA"
    return "SYNTHETIC / NOT_OFFICIAL" if synthetic else "VERIFIED INSTITUTIONAL INPUTS"


def result_classification(profile: ExecutionProfile, *, synthetic: bool) -> str:
    if profile is ExecutionProfile.REFERENCE_DEMO:
        return "REFERENCE_MODEL_OUTPUT"
    return "SYNTHETIC_TEST_OUTPUT" if synthetic else "VERIFIED_INSTITUTIONAL_MODEL_OUTPUT"
