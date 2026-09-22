"""Generate the read-only V2 scientific pre-pilot freeze evidence package."""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import platform
import subprocess
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "docs" / "prepilot_freeze"
SCIENTIFIC_FREEZE_COMMIT = "bb0c6ff516a7d995c2894ee66285ebf124ac9340"
PARENT_TAG = "v2-crop-identity-phenology-contract-complete"
PROTECTED_PATHS = (
    "app.py", "kds/science", "kds/application/optimization.py", "data",
    "index.html", "script.js", "style.css",
)
LINEAGE = (
    ("V1 thesis reference", "v1.0.0-thesis-final", "a49daac1ae6d15d83428565c388bfafb4b6da08a"),
    ("Main generalized V2 baseline", "", "3d12895a80bc6c964b72e81d65577dd502a5402c"),
    ("Scientific Fix Phase 1", "v2-scientific-fix-phase1-complete", "8c77cd063ee592680e02bf01d6f83b17aaf030c2"),
    ("Scientific Fix Phase 2", "v2-scientific-fix-phase2-complete", "b2ec7157493943966bee825c14fbc03110e7a204"),
    ("Water authority audit", "v2-scientific-water-audit-complete", "3b0847370e8abbb7316d40aa1741d5242d736125"),
    ("Water data contract", "v2-water-data-contract-complete", "5018bde15d659e415a106b7b1bae949dc011ccbc"),
    ("Economics provenance audit", "v2-scientific-economics-audit-complete", "2ff32b3b81cb635e1393de5b45f01c11ad2ca195"),
    ("Economics data contract", "v2-economics-data-contract-complete", "62a88bda787f1b3ce7c7a3b01c3d7c8022474096"),
    ("Turp dominance audit", "v2-scientific-turp-dominance-audit-complete", "444092c7bcd721870f3e02157a9398ec0af925e0"),
    ("Crop catalog audit", "v2-scientific-crop-catalog-audit-complete", "38f8c89d4ab14de6868dcd84f017e6e5378353aa"),
    ("Crop identity and phenology contract", PARENT_TAG, SCIENTIFIC_FREEZE_COMMIT),
)


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, text=True, capture_output=True,
    ).stdout.strip()


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in fields} for row in rows)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _tree_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    for file in sorted(item for item in path.rglob("*") if item.is_file() and "__pycache__" not in item.parts):
        digest.update(file.relative_to(path).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(bytes.fromhex(_sha256(file)))
    return digest.hexdigest()


def _imports():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    import app
    from kds.adapters.akkaya_demo import build_demo
    from kds.application.readiness import readiness
    return app, build_demo, readiness


def _lineage_rows() -> list[dict[str, Any]]:
    rows = []
    for milestone, tag, expected in LINEAGE:
        actual = _git("rev-list", "-n", "1", tag) if tag else _git("rev-parse", expected)
        if actual != expected:
            raise RuntimeError(f"Unexpected lineage target for {tag or milestone}: {actual}")
        rows.append({
            "milestone": milestone,
            "tag_or_reference": tag or "commit-only generalized baseline",
            "commit": actual,
            "git_object_type": _git("cat-file", "-t", tag) if tag else "commit",
            "accepted_fix": {
                "Scientific Fix Phase 1": "Observed current_crop authority for perennial locks.",
                "Scientific Fix Phase 2": "Canonical monthly delivery contract and YYYY-MM to calendar-month correction.",
                "Water authority audit": "Water authority, perennial-demand floor and real-world claim boundary.",
                "Water data contract": "Authority, versioning, preview and official-data import boundary.",
                "Economics provenance audit": "Profit lineage, proxy interpretation and Turp economics.",
                "Economics data contract": "Verified dependency graph, scope and authority safety, and versioning.",
                "Turp dominance audit": "Low-water, TL/m3 and runtime-expansion root-cause diagnosis.",
                "Crop catalog audit": "58/69 crop-catalog reconciliation without invented data.",
                "Crop identity and phenology contract": "Reviewed identity resolution, agricultural season semantics and fail-closed readiness.",
            }.get(milestone, "Reference baseline."),
        })
    tagged = [row for row in rows if row["git_object_type"] == "tag"]
    for earlier, later in zip(tagged, tagged[1:]):
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", earlier["commit"], later["commit"]],
            cwd=ROOT, check=True, capture_output=True,
        )
    return rows


def _reference_state() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    app, build_demo, readiness = _imports()
    document = build_demo(app.DATA_DIR)
    report = readiness(document)
    units = document["analysis_units"]
    water = _json(ROOT / "docs/audits/water_supply_phase3/annual_water_reconciliation.json")
    perennial = _json(ROOT / "docs/audits/water_supply_phase3/protected_perennial_demand_summary.json")
    turp = _json(ROOT / "docs/audits/economics_phase4/turp_economic_summary.json")
    phase6 = _json(ROOT / "docs/audits/crop_catalog_phase6/root_cause_breakdown.json")
    catalog = _csv(ROOT / "data/urun_parametreleri_demo.csv")
    turp_catalog = next(row for row in catalog if row["urun_adi"] == "TURP (KIRMIZI)")
    cost_counts = Counter(
        row["reconciliation_status"]
        for row in _csv(ROOT / "docs/audits/economics_phase4/cost_breakdown_reconciliation.csv")
    )
    params = report["crop_parameter_readiness"]
    phenology = report["phenology_readiness"]
    reference = {
        "planning_year": 2024,
        "analysis_units": len(units),
        "area_da": float(sum(Decimal(str(row["area_da"])) for row in units)),
        "current_pattern_calculated_gross_irrigation_demand_m3": float(document["water_budget"]["amount"]),
        "current_calculated_profit_tl": float(sum(Decimal(row["metadata"]["current_profit_tl"]) for row in units)),
        "candidate_rows": int(document["metadata"]["references"]["raw_candidate_rows"]),
        "raw_quota_flagged_rows": int(document["metadata"]["references"]["raw_water_quota_flagged_rows"]),
        "project_crop_catalog": len(document["crops"]),
        "protected_perennial_units": perennial["protected_units"],
        "protected_perennial_area_da": perennial["protected_area_da"],
        "semantics": {
            "current_pattern_calculated_gross_irrigation_demand_m3": "Calculated current-pattern gross irrigation demand; not official allocation, measured use or available reservoir supply.",
            "current_calculated_profit_tl": "Catalog-derived current-pattern baseline; not independent farm accounting.",
            "candidate_rows": "Raw candidate-matrix rows; not recommendations.",
        },
        "water_boundary": {
            "reservoir_irrigation_baseline_annual_sum_m3": water["reservoir_irrigation_baseline_annual_sum_m3"],
            "engine_annual_scenario_budget_m3": water["engine_annual_budget_m3"],
            "delivery_authority": water["delivery_authority"],
            "environmental_flow_ratio": water["environmental_flow_ratio"],
            "environmental_flow_authority": water["environmental_flow_authority"],
            "protected_perennial_current_model_floor_m3": perennial["protected_perennial_model_floor_m3"],
            "interpretation": "STRUCTURAL INFEASIBILITY UNDER CURRENT MODEL INPUTS",
            "not_a_claim": "REAL-WORLD INFEASIBILITY",
        },
        "economics_boundary": {
            "current_profit_interpretation": "catalog-derived baseline",
            "independent_farm_accounting": False,
            "turp_profit_tl_da": float(turp_catalog["net_kar_tl_da"]),
            "turp_yield_kg_da": float(turp_catalog["beklenen_verim_kg_da"]),
            "turp_sale_price_tl_kg": float(turp_catalog["fiyat_tl_kg"]),
            "turp_gross_revenue_tl_da": float(turp_catalog["brut_hasilat_tl_da"]),
            "turp_catalog_cost_tl_da": float(turp_catalog["maliyet_tl_da"]),
            "turp_water_m3_da": turp["water_per_da"],
            "cost_reconciliation": {
                "match": cost_counts["MATCH"],
                "mismatch": cost_counts["MISMATCH"],
                "missing_cost_rule": cost_counts["MISSING_COST_RULE"],
            },
            "dut_gap": "Yield/gross revenue and itemized cost evidence remain incomplete.",
            "verified_real_farm_economics_integrated": False,
        },
        "crop_parameter_boundary": {
            "runtime_catalog": phase6["production_canonical"]["catalog"],
            "parameter_catalog": phase6["production_canonical"]["parameters"],
            "canonical_intersection": phase6["production_canonical"]["intersection"],
            "symmetric_difference": phase6["production_canonical"]["symmetric_difference_identities"],
            "legacy_direct_parameter_lookup": phase6["runtime_direct_coverage"]["kc_and_stage_fraction_hits"],
            "reviewed_parameter_aliases": params["reviewed_alias_count"],
            "ambiguous_parameter_identities": params["ambiguous_count"],
            "missing_parameter_identities": params["missing_count"],
            "legacy_fallback_inventory": params["legacy_fallback_count"],
            "verified_parameter_ready": params["verified_parameter_count"],
            "verified_phenology": phenology["verified_complete_count"],
            "phenology_population": phenology["runtime_crop_count"],
        },
        "turp_boundary": {
            "raw_coverage_units": turp["candidate_unit_count"],
            "raw_coverage_area_da": turp["candidate_area_coverage_da"],
            "s1_runtime_availability_units": 127,
            "s1_runtime_availability_area_da": 95433.0,
            "water_rank_comparable_annual_crops": "1/37",
            "tl_per_m3": turp["tl_per_m3"],
            "tl_per_m3_rank": "3/37",
            "primary_drivers": ["low water", "high TL/m3", "runtime candidate expansion"],
            "market_capacity_constraint": "ABSENT",
            "forbidden_claims": [
                "Turp should be planted on 95433 da.",
                "42.4% is the full 179-unit basin recommendation.",
            ],
            "fixture_scope_note": "The frozen 42.4% value belongs to a small regression fixture.",
        },
    }
    pilot = {
        "demo_status": report["pilot_readiness"]["demo_status"],
        "pilot_status": report["pilot_readiness"]["status"],
        "engine_connected": report["pilot_readiness"]["engine_connected"],
        "runtime_crop_count": params["runtime_crop_count"],
        "verified_parameter_ready": params["verified_parameter_count"],
        "verified_phenology_count": phenology["verified_complete_count"],
        "phenology_population": phenology["runtime_crop_count"],
        "ambiguous_parameter_identities": params["ambiguous_count"],
        "missing_parameter_identities": params["missing_count"],
        "blocking_reasons": [
            "verified parameter ready = 0",
            "verified phenology = 0/58",
            "three ambiguous crop-parameter identities",
            "one missing crop parameter identity",
            "official annual/monthly water supply is missing",
            "verified economic inputs are incomplete",
            "verified replacement datasets are disconnected from the scientific engine",
        ],
        "classification": "Scientific readiness boundary, not a software failure.",
    }
    return reference, pilot, report


def _authority_rows() -> list[dict[str, Any]]:
    common = {"planning_year": "2024", "verified": "NO"}
    return [
        {**common, "concept": "current water demand", "source": "Akkaya project adapter / current pattern", "unit": "m3", "authority_provenance": "CALCULATED_REFERENCE", "engine_role": "current-pattern reference", "limitation": "Not allocation, measured use or available supply."},
        {**common, "concept": "reservoir baseline", "source": "data/enhanced_dataset/csv/akkaya_reservoir_monthly_backend.csv", "unit": "m3/year", "authority_provenance": "UNKNOWN upstream authority", "engine_role": "annual baseline before environmental-flow deduction", "limitation": "Official allocation is absent."},
        {**common, "concept": "annual scenario budget", "source": "reservoir baseline × (1-assumed environmental flow)", "unit": "m3/year", "authority_provenance": "DERIVED from UNKNOWN + ASSUMED", "engine_role": "scenario constraint", "limitation": "Not an official operating allocation."},
        {**common, "concept": "monthly delivery", "source": "data/enhanced_dataset/csv/delivery_capacity_monthly_assumed.csv", "unit": "m3/month", "authority_provenance": "DERIVED_PROXY", "engine_role": "monthly delivery ceiling", "limitation": "Measured delivery and channel capacity are absent."},
        {**common, "concept": "environmental flow ratio", "source": "water audit / decision policy", "unit": "ratio", "authority_provenance": "ASSUMED", "engine_role": "annual budget deduction", "limitation": "No official release rule integrated."},
        {**common, "concept": "crop water requirement", "source": "data/urun_parametreleri_demo.csv and candidate matrix", "unit": "m3/da", "authority_provenance": "Excel-derived / proxy", "engine_role": "candidate water coefficient", "limitation": "Crop-specific verified irrigation requirements are incomplete."},
        {**common, "concept": "Kc and stage", "source": "data/enhanced_dataset/csv/crop_params_assumed.csv", "unit": "Kc; fraction", "authority_provenance": "ASSUMED with legacy fallback", "engine_role": "legacy calibrated path", "limitation": "45 direct identities; 13 fallback; verified ready 0."},
        {**common, "concept": "phenology", "source": "no frozen Akkaya planting/harvest source", "unit": "date/window", "authority_provenance": "MISSING", "engine_role": "not connected", "limitation": "Verified coverage 0/58; no dates invented."},
        {**common, "concept": "yield", "source": "data/urun_parametreleri_demo.csv", "unit": "kg/da", "authority_provenance": "catalog-derived proxy", "engine_role": "economics/reference output", "limitation": "Local dated yield evidence incomplete; DUT gap."},
        {**common, "concept": "sale price", "source": "data/urun_parametreleri_demo.csv", "unit": "TL/kg", "authority_provenance": "catalog proxy", "engine_role": "gross-revenue source", "limitation": "Not a dated verified market series."},
        {**common, "concept": "cost", "source": "data/cost_breakdown_rules_2024.csv", "unit": "TL/da", "authority_provenance": "PROXY allocation rules", "engine_role": "audit/reconciliation", "limitation": "7 match, 50 mismatch, 1 DUT missing rule."},
        {**common, "concept": "net profit", "source": "catalog and seasonal tables", "unit": "TL/da", "authority_provenance": "catalog-derived baseline", "engine_role": "optimization value", "limitation": "Not independent farm accounting."},
        {**common, "concept": "candidate eligibility", "source": "data/excel_derived/combined_parcel_candidate_matrix_2024.csv", "unit": "row/flag", "authority_provenance": "Excel-derived", "engine_role": "candidate universe and quota compatibility", "limitation": "Runtime expansion broadens annual-crop availability; market caps absent."},
        {**common, "concept": "perennial lock", "source": "observed current_crop plus accepted Phase 1 rule", "unit": "unit/da", "authority_provenance": "observed project state for model locking", "engine_role": "hard protection of current perennial pattern", "verified": "YES FOR FROZEN MODEL STATE", "limitation": "Not an external agronomic recommendation."},
    ]


def _official_gap_rows() -> list[dict[str, str]]:
    gaps = [
        ("official annual allocation", "WATER", "PILOT BLOCKER", "authorized annual volume and validity period"),
        ("official monthly allocation", "WATER", "PILOT BLOCKER", "authorized calendar-month volumes"),
        ("measured/operational delivery", "WATER", "PILOT BLOCKER", "dated delivered-flow observations"),
        ("channel capacity", "WATER", "MAJOR", "measured or officially documented capacity by period"),
        ("conveyance efficiency", "WATER", "MAJOR", "system-specific measured efficiency"),
        ("crop-specific irrigation requirement", "PARAMETER", "PILOT BLOCKER", "local verified m3/da or ET-based requirement"),
        ("crop-specific Kc/stage", "PARAMETER", "PILOT BLOCKER", "verified evidence for unresolved/fallback crops"),
        ("planting/harvest phenology", "PHENOLOGY", "PILOT BLOCKER", "local dates or climatological windows for 58 crops"),
        ("local dated yield", "ECONOMICS", "MAJOR", "crop/year/scope-specific observed yield"),
        ("local dated prices", "ECONOMICS", "MAJOR", "crop/year/scope-specific farm-gate prices"),
        ("itemized production cost", "ECONOMICS", "MAJOR", "auditable cost components including DUT"),
        ("support payments", "ECONOMICS", "MAJOR", "dated crop-specific support records or explicit zero"),
        ("market capacity", "MARKET", "MAJOR", "demand, sales, processing, storage and crop-area ceilings"),
        ("farmer preference/behavior", "BEHAVIOR", "MAJOR", "survey or revealed-preference evidence"),
        ("rotation history", "AGRONOMY", "MAJOR", "field-level prior crop sequence where required"),
    ]
    return [
        {"gap": gap, "domain": domain, "priority": priority, "required_evidence": evidence, "current_state": "NOT INTEGRATED"}
        for gap, domain, priority, evidence in gaps
    ]


def _reviewer_rows() -> list[dict[str, str]]:
    return [
        {"reviewer_issue": "Irrigation Science: single-year analysis", "previous_weakness": "One reference planning year limited temporal claims.", "current_v2_improvement": "Planning-year contracts, provenance and reproducible baseline are explicit.", "fully_resolved": "NO", "partially_resolved": "YES", "not_resolved": "NO", "evidence": "reproducibility_manifest.json; scientific lineage", "publication_action": "Run a separate multi-year/uncertainty experiment before temporal resilience claims."},
        {"reviewer_issue": "Irrigation Science: field validation", "previous_weakness": "Recommendations lacked field or operational validation.", "current_v2_improvement": "Claim boundaries now distinguish calculated references from observations.", "fully_resolved": "NO", "partially_resolved": "NO", "not_resolved": "YES", "evidence": "claim_boundary.md; official_data_gaps.csv", "publication_action": "State absence of field validation and require future measured comparison."},
        {"reviewer_issue": "Irrigation Science: limited generalizability", "previous_weakness": "Architecture appeared tied to Akkaya data.", "current_v2_improvement": "A 24-unit independent synthetic project runs S1/S2 and GA/ACO/ABC without Akkaya files.", "fully_resolved": "NO", "partially_resolved": "YES", "not_resolved": "NO", "evidence": "docs/generalization_acceptance.md; tests/test_general_project.py", "publication_action": "Claim software/architectural generalization only, not external agronomic validity."},
        {"reviewer_issue": "Irrigation Science: farmer behavior/economic uncertainty", "previous_weakness": "Farmer response and uncertain economics were not represented.", "current_v2_improvement": "Economic provenance and proxy boundaries are explicit.", "fully_resolved": "NO", "partially_resolved": "YES", "not_resolved": "NO", "evidence": "economics audit; publication_limitation_matrix.csv", "publication_action": "Run price/yield sensitivity and collect farmer evidence before behavioral claims."},
        {"reviewer_issue": "CEA: technological novelty concern", "previous_weakness": "Novelty and reproducible architecture were insufficiently separated from application results.", "current_v2_improvement": "Project-agnostic contracts, deterministic audits, lineage and source guards are documented.", "fully_resolved": "NO", "partially_resolved": "YES", "not_resolved": "NO", "evidence": "scientific_lineage.csv; reproducibility_manifest.json; generalization acceptance", "publication_action": "Frame novelty around auditable architecture and evidence boundaries; avoid claiming a new optimizer."},
        {"reviewer_issue": "IJER: editorial rejection without detailed technical comments", "previous_weakness": "No detailed technical reason was supplied.", "current_v2_improvement": "No causal correction can be attributed to an unspecified editorial decision.", "fully_resolved": "NO", "partially_resolved": "NO", "not_resolved": "YES", "evidence": "No detailed reviewer evidence available.", "publication_action": "Report only the absence of detailed comments; do not invent a rejection rationale."},
    ]


def _limitation_rows() -> list[dict[str, str]]:
    rows = [
        ("single-year analysis", "2024 reference baseline only", "Planning-year semantics and reproducibility", "Temporal stability", "V2 reports a reproducible 2024 reference scenario.", "V2 proves multi-year resilience.", "Multi-year scenario study"),
        ("field validation", "No measured intervention outcome", "Reference/measurement claims separated", "Observed outcome validation", "Results are model outputs under frozen inputs.", "Recommendations are field validated.", "Measured field or operational comparison"),
        ("generalizability", "One real reference project", "Independent 24-unit synthetic architecture test", "External agronomic validity", "The software pipeline is project-agnostic in synthetic acceptance tests.", "Agronomic validity generalizes across regions.", "Independent regional dataset validation"),
        ("economic uncertainty", "Proxy/catalog economics", "Authority and dependency contracts", "Sensitivity and verified farm accounts", "Economic outputs use catalog-derived baseline values.", "Profit outcomes are observed farm income.", "Price/yield/cost uncertainty experiment and farm records"),
        ("farmer behavior", "Not modeled", "Explicit gap inventory", "Adoption and preference response", "Farmer behavior is outside the current model.", "Farmers will adopt the recommended pattern.", "Survey or revealed-preference study"),
        ("market constraints", "Demand/capacity ceilings absent", "Turp root-cause diagnosis", "Feasible sales and production limits", "Market-capacity constraints are absent from the active path.", "The proposed crop mix is market feasible.", "Demand, sales, storage and processing evidence"),
        ("proxy data", "Several water/economic inputs are proxy or assumed", "Provenance and engine-role matrix", "Official/observed replacement", "Each proxy is identified with its engine role and limit.", "All inputs are official or measured.", "Authority-reviewed replacement datasets"),
        ("phenology", "Verified Akkaya coverage 0/58", "Cross-year and mode-safe import contract", "Actual local crop dates", "V2 supports explicit phenology contracts but has no verified Akkaya dates.", "The model uses verified local phenology.", "Local sourced planting/harvest records"),
        ("external validity", "No multi-region real-data validation", "Transparent frozen baseline and synthetic generalization", "Cross-region outcome validation", "Findings apply to the frozen Akkaya model context.", "Results are externally valid for other basins.", "Pre-registered multi-region validation"),
    ]
    fields = ["limitation", "current_status", "what_v2_solved", "what_remains_unresolved", "safe_manuscript_wording", "unsafe_manuscript_wording", "future_validation_requirement"]
    return [dict(zip(fields, row)) for row in rows]


def _evidence_rows() -> list[dict[str, str]]:
    commit = SCIENTIFIC_FREEZE_COMMIT
    rows = [
        ("Scientific lineage table", "docs/prepilot_freeze/scientific_lineage.csv", "Git tag/object resolution", "commit", "accepted V1/V2 lineage", "YES", "YES"),
        ("Akkaya reference-value table", "docs/prepilot_freeze/reference_values.json", "read-only adapter plus frozen audits", "da; m3; TL; count", "179-unit Akkaya reference", "YES", "YES WITH CLAIM BOUNDARY"),
        ("Water reconciliation table", "docs/audits/water_supply_phase3/annual_water_reconciliation.json", "Phase 3 deterministic audit", "m3/year", "2024 model inputs", "YES", "YES WITH AUTHORITY LABELS"),
        ("Protected perennial floor", "docs/audits/water_supply_phase3/protected_perennial_demand_summary.json", "Phase 3 model-floor calculation", "m3; da; units", "52 protected units", "YES", "YES AS MODEL FLOOR"),
        ("Economics reconciliation", "docs/audits/economics_phase4/cost_breakdown_reconciliation.csv", "Phase 4 deterministic audit", "TL/da", "58-crop catalog", "YES", "YES AS PROXY AUDIT"),
        ("Crop-catalog reconciliation", "docs/audits/crop_catalog_phase6/root_cause_breakdown.json", "Phase 6 identity audit", "crop identities", "58 runtime / 69 parameter", "YES", "YES"),
        ("Phenology contract cases", "docs/audits/crop_identity_phenology_phase7_fix1/season_year_cases.json", "Phase 7 corrective generator", "date/window semantics", "synthetic contract cases", "YES", "YES AS CONTRACT EVIDENCE"),
        ("Turp root-cause tables", "docs/audits/turp_dominance/root_cause_attribution.csv", "Phase 5 read-only audit", "rank; units; da; TL/m3", "Akkaya model and frozen fixtures", "YES", "YES WITH FIXTURE SCOPE"),
        ("Generalization acceptance", "docs/generalization_acceptance.md", "public-import 24-unit synthetic tests", "units; candidates", "synthetic project", "YES", "YES AS SOFTWARE EVIDENCE"),
        ("Seeded algorithm fixtures", "tests/fixtures/scientific_baseline", "GA/ACO/ABC seeded parity", "model outputs", "full Akkaya fixtures at seeds 123/456/789", "YES", "YES AS REPRODUCIBILITY EVIDENCE"),
        ("Pilot readiness snapshot", "docs/prepilot_freeze/pilot_readiness_snapshot.json", "read-only readiness evaluation", "counts/status", "Akkaya 2024", "YES", "YES"),
        ("Publication limitation matrix", "docs/prepilot_freeze/publication_limitation_matrix.csv", "claim-boundary synthesis", "n/a", "manuscript scope", "YES", "YES"),
    ]
    fields = ["table_figure_candidate", "source_file", "generation_method", "unit", "scenario_population", "frozen", "publication_safe"]
    return [{**dict(zip(fields, row)), "source_commit": commit} for row in rows]


def _dataset_hashes() -> dict[str, str]:
    paths = (
        "data/excel_derived/combined_parcel_candidate_matrix_2024.csv",
        "data/urun_parametreleri_demo.csv",
        "data/enhanced_dataset/csv/akkaya_reservoir_monthly_backend.csv",
        "data/enhanced_dataset/csv/delivery_capacity_monthly_assumed.csv",
        "data/enhanced_dataset/csv/crop_params_assumed.csv",
        "data/cost_breakdown_rules_2024.csv",
        "tests/fixtures/scientific_baseline/baseline_metadata.json",
    )
    return {path: _sha256(ROOT / path) for path in paths}


def _source_guard() -> dict[str, Any]:
    changed = _git("diff", "--name-only", SCIENTIFIC_FREEZE_COMMIT, "--", *PROTECTED_PATHS).splitlines()
    objects = {}
    for path in PROTECTED_PATHS:
        base = _git("rev-parse", f"{SCIENTIFIC_FREEZE_COMMIT}:{path}")
        current = _git("rev-parse", f"HEAD:{path}")
        objects[path] = {"freeze_object": base, "current_head_object": current, "identical": base == current}
    return {
        "comparison_base": SCIENTIFIC_FREEZE_COMMIT,
        "protected_paths": list(PROTECTED_PATHS),
        "changed_protected_paths": changed,
        "git_objects": objects,
        "candidate_matrix_sha256": _sha256(ROOT / "data/excel_derived/combined_parcel_candidate_matrix_2024.csv"),
        "protected_worktree_sha256": {
            path: _tree_sha256(ROOT / path) if (ROOT / path).is_dir() else _sha256(ROOT / path)
            for path in PROTECTED_PATHS
        },
        "optimizer_changed": False,
        "candidate_matrix_changed": False,
        "scientific_behavior_changed": False,
    }


def generate(output: Path = OUTPUT, test_report: dict[str, Any] | None = None) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    lineage = _lineage_rows()
    reference, pilot, _ = _reference_state()
    guard = _source_guard()
    authority = _authority_rows()
    gaps = _official_gap_rows()
    reviewers = _reviewer_rows()
    limitations = _limitation_rows()
    evidence = _evidence_rows()

    _write_csv(output / "scientific_lineage.csv", lineage, ["milestone", "tag_or_reference", "commit", "git_object_type", "accepted_fix"])
    _write_json(output / "reference_values.json", reference)
    _write_csv(output / "data_authority_matrix.csv", authority, ["concept", "source", "planning_year", "unit", "authority_provenance", "engine_role", "verified", "limitation"])
    _write_json(output / "pilot_readiness_snapshot.json", pilot)
    _write_csv(output / "official_data_gaps.csv", gaps, ["gap", "domain", "priority", "required_evidence", "current_state"])
    _write_csv(output / "reviewer_response_matrix.csv", reviewers, ["reviewer_issue", "previous_weakness", "current_v2_improvement", "fully_resolved", "partially_resolved", "not_resolved", "evidence", "publication_action"])
    _write_csv(output / "publication_limitation_matrix.csv", limitations, ["limitation", "current_status", "what_v2_solved", "what_remains_unresolved", "safe_manuscript_wording", "unsafe_manuscript_wording", "future_validation_requirement"])
    _write_csv(output / "publication_evidence_inventory.csv", evidence, ["table_figure_candidate", "source_file", "source_commit", "generation_method", "unit", "scenario_population", "frozen", "publication_safe"])
    _write_json(output / "source_guard.json", guard)

    dependencies = {
        name: importlib.metadata.version(name)
        for name in ("Flask", "pandas", "openpyxl", "numpy", "python-dateutil", "pytest")
    }
    manifest = {
        "manifest_schema": "v2-scientific-prepilot-freeze-v1",
        "scientific_freeze_commit": SCIENTIFIC_FREEZE_COMMIT,
        "scientific_freeze_commit_semantics": "Immutable accepted scientific source/data commit; evidence-only commits follow it.",
        "parent_tag": PARENT_TAG,
        "parent_tag_target": _git("rev-list", "-n", "1", PARENT_TAG),
        "proposed_completion_tag": "v2-scientific-prepilot-freeze",
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "critical_dependencies": dependencies,
        "random_seed_policy": {
            "reference_fixtures": [123, 456, 789],
            "generalization_fixture": 2468,
            "policy": "Explicit seeded engine runs; no HTTP repeat or algorithm seed offsets.",
        },
        "project_reference_values": reference,
        "scientific_tag_lineage": lineage,
        "dataset_sha256": _dataset_hashes(),
        "protected_code_git_objects": guard["git_objects"],
        "known_test_exclusions": [{
            "test": "tests/test_decision_pipeline.py::test_s2_high_budget_can_return_feasible_two_crop_plan",
            "classification": "INHERITED BASELINE FAILURE / SEPARATE BACKLOG",
            "expected": "ok / feasible two-crop plan",
            "actual": "no_feasible_two_crop_plan",
            "publication_use": "EXCLUDED",
        }],
        "default_deselection": "Tier 2/full-project cases; Tier 3 multi-seed profile is manual/nightly.",
        "current_readiness": pilot,
        "engine_connection_states": {
            "water_replacement_datasets": False,
            "economics_replacement_datasets": False,
            "crop_water_parameter_datasets": False,
            "phenology_datasets": False,
            "execution_path": "frozen legacy/calibrated path",
        },
        "generalization_evidence": {
            "classification": "SOFTWARE / ARCHITECTURAL GENERALIZATION",
            "synthetic_analysis_units": 24,
            "synthetic_candidate_rows": 192,
            "scenarios": ["S1", "S2"],
            "algorithms": ["GA", "ACO", "ABC"],
            "project_isolation": True,
            "seeded_reproducibility": True,
            "akkaya_source_access": False,
            "external_agronomic_field_validation": False,
        },
        "algorithm_reproducibility": {
            "full_akkaya": "Frozen seeded fixtures cover S1/S2 × GA/ACO/ABC; default tests use seed 123 and extended fixtures contain 123/456/789.",
            "synthetic_project": "24-unit public-import fixture repeats S1/S2 × GA/ACO/ABC with seed 2468.",
            "small_regression_fixture": "Phase 5 seed diagnostics are fixture-scoped; the 42.4% Turp share is not a basin result.",
        },
        "robustness_experiments_run": False,
    }
    _write_json(output / "reproducibility_manifest.json", manifest)
    _write_json(output / "test_report.json", test_report or {"status": "PENDING_FINAL_VALIDATION"})

    claim_boundary = """# Scientific pre-pilot claim boundary

## Safe now

- The V2 software architecture accepts an independent 24-unit synthetic project without Akkaya source files.
- Data provenance, versioning, replacement preview, authority controls and fail-closed readiness are explicit and reproducible.
- The frozen Akkaya values describe a 2024 model reference state under the recorded inputs.
- The Turp audit diagnoses low water, high TL/m³ and runtime candidate expansion as model-space drivers.

## Safe only after the robustness experiment

- Resilience to price, yield and water-budget perturbations.
- Crop-pattern stability and algorithm agreement under uncertainty.
- Water-profit-concentration responses across a predeclared experimental grid.

## Not yet supported

- Field-validated recommendations, official water-allocation feasibility, farmer adoption or market feasibility.
- Multi-region agronomic validity, multi-year resilience or verified local phenology/economic completeness.

`100700080.81 m³` is calculated current-pattern gross irrigation demand. It is not official allocation, measured use or available reservoir supply. The current water result is structural infeasibility under current model inputs, not real-world infeasibility. Current profit is a catalog-derived baseline, not independent farm accounting. Runtime availability of Turp on 95,433 da is not a recommendation. The 42.4% Turp value is confined to a small regression fixture.
"""
    (output / "claim_boundary.md").write_text(claim_boundary, encoding="utf-8")

    backlog = """# Known pre-pilot backlog

## Inherited baseline failure

`tests/test_decision_pipeline.py::test_s2_high_budget_can_return_feasible_two_crop_plan` expects an `ok`, feasible two-crop plan but the frozen baseline returns `no_feasible_two_crop_plan`. It remains a separate backlog and must not be used as publication evidence.

## Phase 5 reporting terminology

Rotation exposure counts are 7 same-family and 81 field units; actual applied Turp-option penalties are 6 and 32. The root-cause conclusion is unchanged. Terminology should distinguish exposure from applied-option counts.

## Scientific and operational gaps

Official supply, measured delivery, verified crop parameters, local phenology, verified farm economics, market capacity, farmer behavior and required rotation history remain open. Replacement datasets remain disconnected from the engine. Tier 3 full-project multi-seed execution was not run for this freeze.
"""
    (output / "known_backlog.md").write_text(backlog, encoding="utf-8")

    report = f"""# V2 Scientific Pre-Pilot Freeze

## Frozen scientific reference

The immutable scientific source/data baseline is `{SCIENTIFIC_FREEZE_COMMIT}`, accepted by annotated tag `{PARENT_TAG}`. This package adds reproducibility and publication-boundary evidence only. It does not change the optimizer, scientific engine, candidate matrix, crop values, water values, economics values or phenology values.

## Accepted lineage and fixes

The Git lineage in `scientific_lineage.csv` resolves every accepted tag to a full commit and verifies ancestry. It records perennial-lock authority, the calendar-month correction, water/economics authority contracts, Turp diagnosis, 58/69 catalog reconciliation, and Phase 7 agricultural season semantics with fail-closed readiness.

## Reference and readiness

The frozen Akkaya state contains {reference['analysis_units']} analysis units, {reference['area_da']:.0f} da, {reference['candidate_rows']} candidate rows and {reference['project_crop_catalog']} crops. Current calculated demand is {reference['current_pattern_calculated_gross_irrigation_demand_m3']:.2f} m³ and current calculated profit is {reference['current_calculated_profit_tl']:.3f} TL. Status remains `DEMO_READY` and `PILOT_DATA_NOT_READY`.

## Reproducibility scope

GA, ACO and ABC have seeded frozen artifacts. The 24-unit synthetic project demonstrates software and architectural generalization for S1/S2 without Akkaya sources. Neither result establishes external agronomic field validation. No robustness or sensitivity experiment was run in this milestone.

## Publication use

Use `claim_boundary.md`, the reviewer and limitation matrices, and `publication_evidence_inventory.csv` when designing the next experiment or manuscript. Proxy, assumed and missing inputs must retain their authority labels.
"""
    (output / "scientific_prepilot_freeze.md").write_text(report, encoding="utf-8")

    expected = {
        "analysis_units": 179, "area_da": 134919.0, "candidate_rows": 6859,
        "raw_quota_flagged_rows": 3673, "project_crop_catalog": 58,
        "protected_perennial_units": 52, "protected_perennial_area_da": 39486.0,
    }
    for key, value in expected.items():
        if reference[key] != value:
            raise RuntimeError(f"Unexpected frozen reference {key}: {reference[key]!r}")
    if abs(reference["current_pattern_calculated_gross_irrigation_demand_m3"] - 100700080.81) > 1e-6:
        raise RuntimeError("Unexpected current-pattern demand")
    if abs(reference["current_calculated_profit_tl"] - 1041499119.212) > 1e-6:
        raise RuntimeError("Unexpected current calculated profit")
    if pilot["demo_status"] != "DEMO_READY" or pilot["pilot_status"] != "PILOT_DATA_NOT_READY":
        raise RuntimeError("Unexpected readiness state")
    if guard["changed_protected_paths"] or not all(row["identical"] for row in guard["git_objects"].values()):
        raise RuntimeError("Protected source changed after scientific freeze commit")
    return {
        "scientific_freeze_commit": SCIENTIFIC_FREEZE_COMMIT,
        "lineage_entries": len(lineage),
        "authority_rows": len(authority),
        "official_gaps": len(gaps),
        "protected_changes": guard["changed_protected_paths"],
        "output_files": len(list(output.iterdir())),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--test-report", type=Path)
    args = parser.parse_args()
    report = _json(args.test_report) if args.test_report else None
    print(json.dumps(generate(args.output, report), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
