"""Frozen V1 definitions complement the behavioral thesis regression tests."""
import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((ROOT / "tests/fixtures/thesis_source_manifest.json").read_text(encoding="utf-8"))


def test_all_thesis_function_and_class_definitions_unchanged():
    tree = ast.parse(legacy_source())
    actual = {n.name: hashlib.sha256(ast.dump(n, include_attributes=False).encode()).hexdigest()
              for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
    assert actual == MANIFEST["definitions"]


def test_legacy_frontend_sources_unchanged():
    for name, expected in MANIFEST["legacy_assets"].items():
        content = (ROOT / name).read_text(encoding="utf-8-sig").replace("\r\n", "\n")
        assert hashlib.sha256(content.encode()).hexdigest() == expected


def test_only_project_blueprint_registration_added_to_legacy_module():
    tree = ast.parse(legacy_source())
    def integration(node):
        return (isinstance(node, ast.ImportFrom) and node.module == "kds.api") or (
            isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name) and node.value.func.id == "register_project_api")
    tree.body = [node for node in tree.body if not integration(node)]
    assert hashlib.sha256(ast.dump(tree, include_attributes=False).encode()).hexdigest() == MANIFEST["module_ast"]


def legacy_source():
    source = (ROOT / "app.py").read_text(encoding="utf-8-sig")
    changes = json.loads((ROOT / "tests/fixtures/data_boundary_changes.json").read_text(encoding="utf-8"))
    for before, after in reversed(changes):
        assert after in source
        source = before.join(source.rsplit(after, 1))
    return source
