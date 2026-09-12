from pathlib import Path
import pytest
from kds.application.project_service import ProjectService
from kds.data.project_store import FileProjectStore
from kds.data.repositories import ConflictError


def values(project_id="example"):
    return dict(id=project_id, name="Example", planning_year=2024,
                annual_water_budget=1000, water_budget_unit="m3")


def test_create_persist_and_duplicate(tmp_path):
    service = ProjectService(FileProjectStore(tmp_path))
    assert service.create(values())["id"] == "example"
    assert ProjectService(FileProjectStore(tmp_path)).get("example")["project"]["name"] == "Example"
    assert len(service.list()) == 1
    with pytest.raises(ConflictError):
        service.create(values())


@pytest.mark.parametrize("project_id", ["../escape", "a/b", "a\\b", "CON", "con", ".", "", "C:bad"])
def test_invalid_id(tmp_path, project_id):
    with pytest.raises(ValueError):
        ProjectService(FileProjectStore(tmp_path)).create(values(project_id))
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("field,value", [("annual_water_budget", -1), ("annual_water_budget", float("nan")),
                                       ("name", " "), ("planning_year", 2024.5), ("water_budget_unit", "")])
def test_invalid_project(tmp_path, field, value):
    payload = values()
    payload[field] = value
    with pytest.raises(ValueError):
        ProjectService(FileProjectStore(tmp_path)).create(payload)


def test_isolation_and_atomic_failure(tmp_path, monkeypatch):
    store = FileProjectStore(tmp_path)
    service = ProjectService(store)
    service.create(values("one"))
    service.create(values("two"))
    before = store.get("one")
    def fail_replace(*args):
        raise OSError("simulated disk failure")
    monkeypatch.setattr("kds.data.project_store.os.replace", fail_replace)
    with pytest.raises(OSError):
        store.update("one", lambda doc: doc["metadata"].update(note="lost"))
    assert store.get("one") == before
    assert store.get("two")["metadata"] == {}
    assert not list(Path(tmp_path).rglob(".write-*"))
