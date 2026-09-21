"""Crop identity, parameter-resolution and phenology contracts.

The contracts are project data-management metadata in Phase 7.  Active datasets
remain disconnected from the legacy scientific engine until a later, separately
validated integration milestone.
"""
from __future__ import annotations

import math
import unicodedata
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Iterable


CROP_PARAMETER_DATA_TYPES = {"crop_water_parameters", "crop_phenology"}


class IdentityRelationType(str, Enum):
    EXACT = "EXACT"
    REVIEWED_ALIAS = "REVIEWED_ALIAS"
    SPELLING_EQUIVALENT = "SPELLING_EQUIVALENT"
    UNICODE_EQUIVALENT = "UNICODE_EQUIVALENT"
    WORD_ORDER_EQUIVALENT = "WORD_ORDER_EQUIVALENT"
    GRANULARITY_PARENT = "GRANULARITY_PARENT"
    UNRESOLVED = "UNRESOLVED"
    UNSAFE_AUTO_MERGE = "UNSAFE_AUTO_MERGE"


class RelationStatus(str, Enum):
    REVIEWED = "REVIEWED"
    UNRESOLVED = "UNRESOLVED"
    AMBIGUOUS = "AMBIGUOUS"


class ResolutionStatus(str, Enum):
    EXACT = "EXACT"
    REVIEWED_ALIAS = "REVIEWED_ALIAS"
    AMBIGUOUS = "AMBIGUOUS"
    MISSING = "MISSING"
    LEGACY_GENERIC_FALLBACK = "LEGACY_GENERIC_FALLBACK"


class ParameterAuthority(str, Enum):
    OFFICIAL = "OFFICIAL"
    LOCAL_INSTITUTIONAL = "LOCAL_INSTITUTIONAL"
    PEER_REVIEWED = "PEER_REVIEWED"
    EXPERT_VALIDATED = "EXPERT_VALIDATED"
    ASSUMED = "ASSUMED"
    UNKNOWN = "UNKNOWN"


AUTHORITY_PRECEDENCE = {
    ParameterAuthority.OFFICIAL: 6,
    ParameterAuthority.LOCAL_INSTITUTIONAL: 5,
    ParameterAuthority.PEER_REVIEWED: 4,
    ParameterAuthority.EXPERT_VALIDATED: 3,
    ParameterAuthority.ASSUMED: 2,
    ParameterAuthority.UNKNOWN: 1,
}
VERIFIED_AUTHORITIES = {
    ParameterAuthority.OFFICIAL,
    ParameterAuthority.LOCAL_INSTITUTIONAL,
    ParameterAuthority.PEER_REVIEWED,
    ParameterAuthority.EXPERT_VALIDATED,
}


@dataclass(frozen=True)
class CropIdentity:
    canonical_crop_id: str
    display_name: str
    normalized_key: str
    crop_form: str | None = None
    annual_perennial: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class IdentityRelation:
    runtime_crop_id: str
    parameter_crop_id: str
    relation_type: IdentityRelationType
    status: RelationStatus
    evidence: str
    source: str
    review_note: str


REVIEWED_IDENTITY_RELATIONS = (
    IdentityRelation("KIMYON", "KI\u0307MYON", IdentityRelationType.UNICODE_EQUIVALENT, RelationStatus.REVIEWED,
                     "U+0130 and i+U+0307 are textual Unicode forms of KİMYON.", "Phase 6 independent validation", "Parameter resolution only; global crop ids are unchanged."),
    IdentityRelation("TRTIKALEDANE", "TRITIKALEDANE", IdentityRelationType.SPELLING_EQUIVALENT, RelationStatus.REVIEWED,
                     "Catalog TRTİKALE and parameter TRİTİKALE identify the same grain form.", "Phase 6 independent validation", "Reviewed spelling relation."),
    IdentityRelation("SALCALIKDOMATES", "DOMATESSALCALIK", IdentityRelationType.WORD_ORDER_EQUIVALENT, RelationStatus.REVIEWED,
                     "Both labels explicitly identify salçalık domates.", "Phase 6 independent validation", "Explicit relation; no token-sort inference."),
    IdentityRelation("SOFRALIKDOMATES", "DOMATESSOFRALIK", IdentityRelationType.WORD_ORDER_EQUIVALENT, RelationStatus.REVIEWED,
                     "Both labels explicitly identify sofralık domates.", "Phase 6 independent validation", "Explicit relation; no token-sort inference."),
    IdentityRelation("SIVRIBIBER", "BIBERSIVRI", IdentityRelationType.WORD_ORDER_EQUIVALENT, RelationStatus.REVIEWED,
                     "Both labels explicitly identify sivri biber.", "Phase 6 independent validation", "Explicit relation; no token-sort inference."),
    IdentityRelation("SALCALIKBIBER", "BIBERSALCALIK", IdentityRelationType.WORD_ORDER_EQUIVALENT, RelationStatus.REVIEWED,
                     "Both labels explicitly identify salçalık biber.", "Phase 6 independent validation", "Explicit relation; no token-sort inference."),
    IdentityRelation("SILAJLIKMISIR", "MISIRSILAJLIK", IdentityRelationType.WORD_ORDER_EQUIVALENT, RelationStatus.REVIEWED,
                     "Both labels explicitly identify silajlık mısır.", "Phase 6 independent validation", "The grain identity remains separate."),
    IdentityRelation("KAYSI", "KAYISI", IdentityRelationType.REVIEWED_ALIAS, RelationStatus.REVIEWED,
                     "Existing production canonical alias maps KAYISI to KAYSI.", "app.py canonical_crop_key + Phase 6 validation", "Parameter resolution only."),
    IdentityRelation("NEKTAR", "NEKTARIN", IdentityRelationType.REVIEWED_ALIAS, RelationStatus.REVIEWED,
                     "Existing production canonical alias maps NEKTARIN to NEKTAR.", "app.py canonical_crop_key + Phase 6 validation", "Parameter resolution only."),
)

AMBIGUOUS_GRANULARITY_RELATIONS = tuple(
    IdentityRelation(runtime, "KABAK", IdentityRelationType.GRANULARITY_PARENT, RelationStatus.AMBIGUOUS,
                     "One generic parameter row cannot prove crop-form equivalence.", "Phase 6 independent validation",
                     "UNSAFE_AUTO_MERGE; crop-specific evidence is required.")
    for runtime in ("KABAKBAL", "KABAKCEREZLIK", "KABAKSAKIZ")
)

LEGACY_DIRECT_FALLBACK_CROPS = (
    "KABAKBAL", "KABAKCEREZLIK", "KABAKSAKIZ", "KAYSI", "KIMYON", "NEKTAR",
    "SALCALIKBIBER", "SALCALIKDOMATES", "SILAJLIKMISIR", "SIVRIBIBER",
    "SOFRALIKDOMATES", "SOGANTAZE", "TRTIKALEDANE",
)

PARAMETER_ONLY_IDENTITIES = (
    "ASPIR", "BAMYA", "BEZELYETAZE", "BURCAKYESILOT", "DIGERALAN", "HIYARTURSULUK",
    "IGDE", "KORUNGAYESILOT", "PATLICAN", "RYEGRASSUTOTU", "SARIMSAKTAZE",
    "YEMBEZELYESI", "YESILMERCIMEK", "ZERDALI",
)

FUTURE_ANALYSIS_RUN_PROVENANCE_FIELDS = (
    "crop_parameter_dataset_id", "crop_parameter_version", "phenology_dataset_id",
    "phenology_version", "identity_resolution_revision",
)
IDENTITY_RESOLUTION_REVISION = "phase7-reviewed-relations-v1"


def textual_equivalence_key(value: Any) -> str:
    """Normalize Unicode encoding only; never reorder tokens or collapse crop forms."""
    text = str(value or "").translate(str.maketrans({"ı": "i", "İ": "I"})).casefold()
    text = "".join(ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch))
    return text


def authority(value: Any) -> ParameterAuthority:
    if isinstance(value, ParameterAuthority):
        return value
    try:
        return ParameterAuthority(str(value or "").strip().upper())
    except ValueError as exc:
        raise ValueError("Unknown crop parameter authority_class.") from exc


def authority_rank(value: Any) -> int:
    return AUTHORITY_PRECEDENCE[authority(value)]


def is_verified_authority(value: Any) -> bool:
    return authority(value) in VERIFIED_AUTHORITIES


def finite_nonnegative(value: Any, name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite nonnegative number.")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a finite nonnegative number.") from exc
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{name} must be a finite nonnegative number.")
    return number


def resolution_for(runtime_crop_id: str, parameter_ids: Iterable[str], *, legacy_direct_match: bool,
                   parameter_authority: str = "ASSUMED", engine_connected: bool = False) -> dict[str, Any]:
    available = set(parameter_ids)
    reviewed = {r.runtime_crop_id: r for r in REVIEWED_IDENTITY_RELATIONS if r.status is RelationStatus.REVIEWED}
    ambiguous = {r.runtime_crop_id: r for r in AMBIGUOUS_GRANULARITY_RELATIONS}
    if runtime_crop_id in available:
        status, resolved, method, evidence = ResolutionStatus.EXACT, runtime_crop_id, "exact_parameter_identity", "Exact parameter identity exists."
    elif runtime_crop_id in reviewed and reviewed[runtime_crop_id].parameter_crop_id in available:
        relation = reviewed[runtime_crop_id]
        status, resolved, method, evidence = ResolutionStatus.REVIEWED_ALIAS, relation.parameter_crop_id, relation.relation_type.value, relation.evidence
    elif runtime_crop_id in ambiguous and ambiguous[runtime_crop_id].parameter_crop_id in available:
        relation = ambiguous[runtime_crop_id]
        status, resolved, method, evidence = ResolutionStatus.AMBIGUOUS, None, "AMBIGUOUS_GRANULARITY", relation.evidence
    else:
        status, resolved, method, evidence = ResolutionStatus.MISSING, None, "MISSING_PARAMETER", "No defensible parameter identity exists."
    identity_verified = status in {ResolutionStatus.EXACT, ResolutionStatus.REVIEWED_ALIAS}
    evidence_verified = bool(identity_verified and is_verified_authority(parameter_authority))
    legacy_fallback = not legacy_direct_match
    return {
        "runtime_crop_id": runtime_crop_id,
        "resolution_status": status.value,
        "resolved_parameter_identity": resolved,
        "resolution_method": method,
        "resolution_evidence": evidence,
        "identity_resolution_reviewed": identity_verified,
        "legacy_generic_fallback": legacy_fallback,
        "legacy_engine_uses_fallback": legacy_fallback,
        "legacy_fallback_status": ResolutionStatus.LEGACY_GENERIC_FALLBACK.value if legacy_fallback else None,
        "parameter_authority": authority(parameter_authority).value,
        "verified_parameter_evidence": evidence_verified,
        "verified_parameter_ready": bool(evidence_verified and not legacy_fallback and engine_connected),
        "engine_connected": bool(engine_connected),
        "identity_resolution_revision": IDENTITY_RESOLUTION_REVISION,
    }


def scope_key(data_type: str, records: list[dict[str, Any]]) -> str:
    years = {record["applicable_year"] for record in records}
    scopes = {record["geographic_scope"] for record in records}
    if len(years) != 1 or len(scopes) != 1:
        raise ValueError("One dataset must use one applicable_year and geographic_scope.")
    return f"{data_type}|{next(iter(years))}|{next(iter(scopes))}"


def active_dataset(document: dict[str, Any], data_type: str, records: list[dict[str, Any]] | None = None) -> dict[str, Any] | None:
    store = document.get("crop_parameter_data", {})
    if records:
        dataset_id = store.get("active", {}).get(scope_key(data_type, records))
    else:
        matching = [value for key, value in store.get("active", {}).items() if key.startswith(data_type + "|")]
        dataset_id = matching[0] if len(matching) == 1 else None
    return store.get("datasets", {}).get(dataset_id) if dataset_id else None


def dataset_authority(records: list[dict[str, Any]]) -> str:
    values = {record["authority_class"] for record in records}
    if len(values) != 1:
        raise ValueError("One imported dataset must have exactly one authority_class.")
    return next(iter(values))


def _record_values(data_type: str, record: dict[str, Any] | None) -> dict[str, Any] | None:
    if record is None:
        return None
    fields = (("kc_ini", "kc_mid", "kc_end", "stage_value_mode", "p_ini", "p_dev", "p_mid", "p_late", "stage_total")
              if data_type == "crop_water_parameters" else
              ("mode", "season", "season_year_semantics", "planting_date", "harvest_date", "planting_window_start",
               "planting_window_end", "harvest_window_start", "harvest_window_end"))
    return {field: record.get(field) for field in fields}


def replacement_preview(document: dict[str, Any], data_type: str, records: list[dict[str, Any]]) -> dict[str, Any]:
    existing = active_dataset(document, data_type, records)
    old_records = {record["runtime_crop_id"]: record for record in existing.get("records", [])} if existing else {}
    new_records = {record["runtime_crop_id"]: record for record in records}
    crops = sorted(old_records.keys() | new_records.keys())
    changes = [{
        "affected_crop": crop,
        "old_resolution": old_records.get(crop, {}).get("resolution_status"),
        "new_resolution": new_records.get(crop, {}).get("resolution_status"),
        "old_authority": old_records.get(crop, {}).get("authority_class"),
        "new_authority": new_records.get(crop, {}).get("authority_class"),
        "old_values": _record_values(data_type, old_records.get(crop)),
        "new_values": _record_values(data_type, new_records.get(crop)),
    } for crop in crops if _record_values(data_type, old_records.get(crop)) != _record_values(data_type, new_records.get(crop))]
    old_authority = existing.get("authority_class") if existing else None
    new_authority = dataset_authority(records)
    return {
        "scope_key": scope_key(data_type, records),
        "existing_dataset_id": existing.get("dataset_id") if existing else None,
        "old_authority": old_authority, "new_authority": new_authority,
        "authority_change": "LOWER" if existing and authority_rank(new_authority) < authority_rank(old_authority) else "HIGHER" if existing and authority_rank(new_authority) > authority_rank(old_authority) else "SAME" if existing else "INITIAL",
        "requires_authority_override": bool(existing and authority_rank(new_authority) < authority_rank(old_authority)),
        "same_authority_conflict": bool(existing and old_authority == new_authority),
        "changes": changes, "change_count": len(changes),
        "affected_crops": crops, "affected_scenarios": ["S1", "S2"],
        "requires_reanalysis": True, "activation_occurs_only_after_confirm": True,
        "engine_connected": False,
    }


def authority_snapshot(document: dict[str, Any]) -> dict[str, Any]:
    store = document.get("crop_parameter_data", {})
    result = {}
    for key, dataset_id in store.get("active", {}).items():
        dataset = store.get("datasets", {}).get(dataset_id, {})
        result[key] = {
            "active_dataset_id": dataset_id, "data_version": dataset.get("version"),
            "authority_class": dataset.get("authority_class"), "confirmed_at": dataset.get("confirmed_at"),
            "requires_reanalysis": dataset.get("requires_reanalysis", True), "engine_connected": False,
        }
    return result
