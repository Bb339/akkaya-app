"""Light, read-only acceptance tests for the Phase 3 water audit."""
import ast
import hashlib
import importlib.util
import json
import math
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/scientific_audit/water_supply_phase3.py"


def load_module():
    spec = importlib.util.spec_from_file_location("water_supply_phase3", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def generated(tmp_path):
    module = load_module()
    protected = [ROOT / "app.py", ROOT / "data/parsel_su_kar_ozet.csv",
                 ROOT / "data/enhanced_dataset/csv/akkaya_reservoir_monthly_backend.csv",
                 ROOT / "data/enhanced_dataset/csv/delivery_capacity_monthly_assumed.csv"]
    before = {p: digest(p) for p in protected}
    result = module.build(tmp_path)
    assert {p: digest(p) for p in protected} == before
    return result


def test_water_reconciliation_and_authority_are_deterministic(tmp_path):
    result = generated(tmp_path)
    annual = result["annual"]
    assert annual["current_pattern_calculated_gross_demand_m3"] == 100700080.81
    assert math.isclose(annual["reservoir_irrigation_baseline_annual_sum_m3"], 11557762.84, abs_tol=1e-6)
    assert math.isclose(annual["engine_annual_budget_m3"], 10401986.556, abs_tol=1e-6)
    assert annual["reservoir_baseline_authority"] == "UNKNOWN"
    assert math.isclose(annual["upstream_2024_withdrawal_named_field_m3"], 11557762.839961313, abs_tol=1e-9)
    assert annual["upstream_annual_match_absolute_difference_m3"] < 0.001
    assert annual["delivery_authority"] == "DERIVED_PROXY"


def test_protected_set_floor_and_aggregation(tmp_path):
    result = generated(tmp_path)
    floor = result["floor"]
    assert floor["protected_units"] == 52
    assert floor["protected_area_da"] == 39486.0
    assert math.isclose(floor["protected_perennial_current_reference_demand_m3"], 31264646.99, abs_tol=1e-6)
    assert math.isclose(floor["protected_perennial_model_floor_m3"], 22510545.8328, abs_tol=1e-6)
    assert math.isclose(sum(r["model_water_floor_m3"] for r in result["protected_rows"]),
                        floor["protected_perennial_model_floor_m3"], abs_tol=1e-6)
    assert floor["survival_water_claim_allowed"] is False


def test_monthly_and_annual_lower_bound_contract(tmp_path):
    result = generated(tmp_path)
    annual, bounds = result["annual"], result["bounds"]
    assert len(result["monthly"]) == 12
    assert math.isclose(sum(r["raw_delivery_capacity_m3"] for r in result["monthly"]),
                        annual["raw_monthly_delivery_sum_m3"], abs_tol=1e-6)
    assert all(r["protected_perennial_demand_m3"] == "" for r in result["monthly"])
    assert bounds["annual_necessary_condition_met"] is False
    assert bounds["monthly_necessary_condition_evaluated"] is False
    assert bounds["classification"] == "STRUCTURAL INFEASIBILITY UNDER CURRENT MODEL INPUTS"
    assert bounds["real_world_infeasibility_claim"] is False


def test_forbidden_supply_classifications_never_appear(tmp_path):
    result = generated(tmp_path)
    by_name = {r["variable"]: r for r in result["authority"]}
    assert by_name["current_pattern_calculated_gross_demand"]["authority_class"] == "CALCULATED_REFERENCE"
    assert by_name["current_pattern_calculated_gross_demand"]["real_world_claim_allowed"] == "demand estimate only"
    assert by_name["raw_delivery_capacity"]["authority_class"] == "DERIVED_PROXY"
    assert by_name["reservoir_irrigation_baseline"]["authority_class"] == "UNKNOWN"
    assert all(r["authority_class"] != "MEASURED" for r in result["authority"])
    guard = json.loads((tmp_path / "source_and_mutation_guard.json").read_text(encoding="utf-8"))
    assert guard["optimizer_executed"] is False and guard["project_store_accessed"] is False


def test_audit_has_only_standard_library_imports_and_no_store_access():
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    imports = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imports.update(
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    )
    assert imports <= {"__future__", "csv", "hashlib", "json", "math", "re", "unicodedata", "pathlib"}
    assert all(
        not (isinstance(node, ast.Name) and node.id == "ProjectStore")
        for node in ast.walk(tree)
    )


def test_generator_outputs_are_byte_deterministic(tmp_path):
    module = load_module()
    first, second = tmp_path / "first", tmp_path / "second"
    module.build(first)
    module.build(second)
    first_hashes = {p.name: digest(p) for p in first.iterdir()}
    second_hashes = {p.name: digest(p) for p in second.iterdir()}
    assert first_hashes == second_hashes


def test_phase3_diff_is_confined_to_audit_docs_tool_and_test():
    completed = subprocess.run(
        ["git", "diff", "--name-only", "v2-scientific-fix-phase2-complete..v2-scientific-water-audit-complete"],
        cwd=ROOT, check=True, text=True, capture_output=True,
    )
    changed = {line for line in completed.stdout.splitlines() if line}
    allowed = (
        "docs/audits/water_supply_phase3/",
        "tools/scientific_audit/water_supply_phase3.py",
        "tests/test_water_supply_phase3.py",
    )
    assert changed
    assert all(path.startswith(allowed[0]) or path in allowed[1:] for path in changed)
