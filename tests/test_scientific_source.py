"""Frozen V1 definitions complement the behavioral thesis regression tests."""
import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((ROOT / "tests/fixtures/thesis_source_manifest.json").read_text(encoding="utf-8"))


def test_phase2_changes_only_reviewed_delivery_functions():
    source = (ROOT / "app.py").read_text(encoding="utf-8-sig")
    tree = ast.parse(source)
    guard = json.loads((ROOT / 'tests/fixtures/scientific_fix_phase2/source_guard.json').read_text())
    allowed = set(guard['allowed_changed_functions'])
    actual = {n.name: hashlib.sha256(ast.dump(n, include_attributes=False).encode()).hexdigest()
              for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
    assert {name:actual[name] for name in allowed} == guard['current_function_ast_sha256']

    phase1 = json.loads((ROOT / 'tests/fixtures/scientific_fix_phase1/source_boundary.json').read_text())
    assert source.count(phase1['after']) == 1
    perennial = ast.parse(phase1['after']).body[0]
    assert actual['_compute_perennial_locks'] == hashlib.sha256(
        ast.dump(perennial, include_attributes=False).encode()).hexdigest()

    normalized = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == '_canonical_monthly_table_values':
            continue
        if isinstance(node, ast.FunctionDef) and node.name in allowed:
            node.body = [ast.Pass()]
        normalized.append(node)
    tree.body = normalized
    assert hashlib.sha256(ast.dump(tree, include_attributes=False).encode()).hexdigest() == guard['phase1_normalized_module_ast_sha256']

    # Relocated default input literals are frozen too; restoring the old AST
    # alone does not detect an edit to the adapter's data file.
    changes = json.loads((ROOT / 'tests/fixtures/data_boundary_changes.json').read_text(encoding='utf8'))
    original = next(before for before, after in changes if before.startswith('default_crop_params ='))
    values = ast.parse(original).body[0].value
    expected = {key.args[0].value: ast.literal_eval(value) for key, value in zip(values.keys, values.values)}
    parameters = json.loads((ROOT / 'kds/adapters/reference_parameters.json').read_text(encoding='utf8'))
    assert parameters['fallback_crop_parameters'] == expected


def test_legacy_frontend_sources_unchanged():
    for name, expected in MANIFEST["legacy_assets"].items():
        content = (ROOT / name).read_text(encoding="utf-8-sig").replace("\r\n", "\n")
        assert hashlib.sha256(content.encode()).hexdigest() == expected


def test_ga_aco_abc_and_fitness_definitions_match_phase1():
    tree = ast.parse((ROOT / 'app.py').read_text(encoding='utf-8-sig'))
    actual = {n.name: hashlib.sha256(ast.dump(n,include_attributes=False).encode()).hexdigest()
              for n in tree.body if isinstance(n,ast.FunctionDef)}
    for name in ('ga_optimize','aco_optimize','abc_optimize',
                 'ga_optimize_two_season','aco_optimize_two_season','abc_optimize_two_season',
                 '_score_solution','_score_solution_two_season',
                 '_matrix_ga_optimize','_matrix_aco_optimize','_matrix_abc_optimize'):
        assert actual[name] == MANIFEST['definitions'][name]
