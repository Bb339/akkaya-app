from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import Mock

import pytest
import yaml
from flask import Flask

from kds.api import register_project_api
from kds.application import optimization
from kds.data.project_store import FileProjectStore
from kds.operations import register_operational_controls, store_readiness


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "render.yaml"


def project_payload(project_id="persisted-project"):
    return {
        "id": project_id,
        "name": "Synthetic persistence fixture",
        "planning_year": 2025,
        "annual_water_budget": 100.0,
        "water_budget_unit": "m3",
        "data_source_notes": "synthetic fixture",
    }


def operational_app(store: Path) -> Flask:
    application = Flask("deployment-hardening-test")
    application.config["TESTING"] = True
    register_project_api(application, FileProjectStore(store))
    register_operational_controls(application)
    return application


def auth(username="demo", password="secret"):
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def test_deployment_manifest_parses_and_pins_single_worker_timeout_and_disk():
    manifest = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    service = manifest["services"][0]
    command = service["startCommand"]
    assert service["runtime"] == "python" and service["numInstances"] == 1
    assert "$PORT" in command and "--workers 1" in command and "--timeout 360" in command
    assert service["healthCheckPath"] == "/healthz"
    assert service["disk"]["mountPath"] == "/var/data/crop-kds"
    assert (ROOT / ".python-version").read_text().strip().startswith("3.11")


def test_project_store_override_and_writable_readiness(monkeypatch, tmp_path):
    target = tmp_path / "persistent" / "projects"
    monkeypatch.setenv("KDS_DEPLOYMENT_MODE", "staging")
    monkeypatch.setenv("KDS_PROJECT_STORE", str(target))
    assert store_readiness() == {
        "configured": True, "exists": True, "writable": True, "ready": True, "error_code": None,
    }


def test_missing_or_unwritable_staging_store_fails_closed(monkeypatch, tmp_path):
    monkeypatch.setenv("KDS_DEPLOYMENT_MODE", "staging")
    monkeypatch.delenv("KDS_PROJECT_STORE", raising=False)
    assert store_readiness()["error_code"] == "KDS_PROJECT_STORE_REQUIRED"
    monkeypatch.setenv("KDS_PROJECT_STORE", str(tmp_path / "store"))
    monkeypatch.setattr("kds.operations.tempfile.NamedTemporaryFile", Mock(side_effect=OSError("denied")))
    assert store_readiness()["error_code"] == "PROJECT_STORE_NOT_WRITABLE"


def test_restart_recovery_preserves_completed_and_terminalizes_running(tmp_path):
    store = FileProjectStore(tmp_path)
    document = {"project": {"id": "p1", "name": "P1"}, "runs": {
        "done": {"id": "done", "status": "completed", "started_at": "a", "completed_at": "b", "result": {"score": 1}},
        "active": {"id": "active", "status": "running", "started_at": "c", "completed_at": None, "result": None},
        "failed": {"id": "failed", "status": "failed", "started_at": "d", "completed_at": "e", "error": "x"},
    }}
    store.create(document)
    assert store.recover_interrupted_runs() == [{"project_id": "p1", "run_id": "active"}]
    after = store.get("p1")["runs"]
    assert after["done"] == document["runs"]["done"] and after["failed"] == document["runs"]["failed"]
    assert after["active"]["status"] == "interrupted"
    assert after["active"]["started_at"] == "c" and after["active"]["completed_at"] is None
    assert after["active"]["interruption"]["code"] == "PROCESS_RESTART_INTERRUPTED"
    assert after["active"]["result"] is None
    assert store.recover_interrupted_runs() == []


@pytest.mark.parametrize("outcome, expected", [
    (Mock(returncode=0, stdout="abc123\n"), "abc123"),
    (FileNotFoundError("git"), None),
    (Mock(returncode=128, stdout=""), None),
])
def test_git_provenance_fallback(monkeypatch, outcome, expected):
    if isinstance(outcome, BaseException):
        monkeypatch.setattr(optimization.subprocess, "run", Mock(side_effect=outcome))
    else:
        monkeypatch.setattr(optimization.subprocess, "run", Mock(return_value=outcome))
    assert optimization.engine_commit() == expected


def test_staging_authentication_health_and_no_secret_exposure(monkeypatch, tmp_path):
    monkeypatch.setenv("KDS_DEPLOYMENT_MODE", "staging")
    monkeypatch.setenv("KDS_PROJECT_STORE", str(tmp_path))
    monkeypatch.setenv("KDS_BASIC_AUTH_USERNAME", "demo")
    monkeypatch.setenv("KDS_BASIC_AUTH_PASSWORD", "secret")
    application = operational_app(tmp_path)
    client = application.test_client()
    assert client.get("/projects").status_code == 401
    assert client.get("/api/v2/projects").status_code == 401
    assert client.get("/projects", headers=auth(password="wrong")).status_code == 401
    assert client.get("/projects", headers=auth()).status_code == 200
    health = client.get("/healthz")
    body = health.get_data(as_text=True)
    assert health.status_code == 200 and health.json["ready"] is True
    assert "secret" not in body and str(tmp_path) not in body
    assert application.extensions["kds_startup_diagnostics"]["effective_project_store"] == str(tmp_path.resolve())


def test_staging_missing_credentials_fails_closed(monkeypatch, tmp_path):
    monkeypatch.setenv("KDS_DEPLOYMENT_MODE", "staging")
    monkeypatch.setenv("KDS_PROJECT_STORE", str(tmp_path))
    monkeypatch.delenv("KDS_BASIC_AUTH_USERNAME", raising=False)
    monkeypatch.delenv("KDS_BASIC_AUTH_PASSWORD", raising=False)
    client = operational_app(tmp_path).test_client()
    assert client.get("/projects").status_code == 503
    assert client.get("/healthz").status_code == 503


def test_explicit_local_development_disables_authentication(monkeypatch, tmp_path):
    monkeypatch.setenv("KDS_DEPLOYMENT_MODE", "local-development")
    monkeypatch.setenv("KDS_PROJECT_STORE", str(tmp_path))
    monkeypatch.delenv("KDS_BASIC_AUTH_USERNAME", raising=False)
    monkeypatch.delenv("KDS_BASIC_AUTH_PASSWORD", raising=False)
    client = operational_app(tmp_path).test_client()
    assert client.get("/projects").status_code == 200


def test_actual_two_process_restart_persistence(monkeypatch, tmp_path):
    store = tmp_path / "process-store"
    environment = os.environ.copy()
    environment.update(KDS_DEPLOYMENT_MODE="local-development", KDS_PROJECT_STORE=str(store), PYTHONPATH=str(ROOT))
    create = """
import app
client=app.app.test_client()
payload={payload!r}
response=client.post('/api/v2/projects',json=payload)
assert response.status_code==201,response.get_data(as_text=True)
repo=app.app.extensions['kds_project_repository']
def add(d):
 d['imports']['fixture']={{'filename':'synthetic.csv','file_hash':'sha256-fixture','rows':[{{'value':1}}],'history':[{{'status':'applied'}}]}}
 d['runs']['completed-fixture']={{'id':'completed-fixture','status':'completed','started_at':'a','completed_at':'b','result':{{'score':1}}}}
 d['runs']['running-fixture']={{'id':'running-fixture','status':'running','started_at':'c','completed_at':None,'result':None}}
repo.update(payload['id'],add)
""".format(payload=project_payload())
    first = subprocess.run([sys.executable, "-c", create], cwd=ROOT, env=environment, text=True, capture_output=True)
    assert first.returncode == 0, first.stderr
    verify = """
import json,app
client=app.app.test_client()
assert client.get('/projects').status_code==200
d=app.app.extensions['kds_project_repository'].get('persisted-project')
print(json.dumps({'project':d['project']['id'],'import_hash':d['imports']['fixture']['file_hash'],'completed':d['runs']['completed-fixture'],'interrupted':d['runs']['running-fixture']}))
"""
    second = subprocess.run([sys.executable, "-c", verify], cwd=ROOT, env=environment, text=True, capture_output=True)
    assert second.returncode == 0, second.stderr
    evidence = json.loads(second.stdout.strip().splitlines()[-1])
    assert evidence["project"] == "persisted-project" and evidence["import_hash"] == "sha256-fixture"
    assert evidence["completed"]["status"] == "completed" and evidence["completed"]["result"] == {"score": 1}
    assert evidence["interrupted"]["status"] == "interrupted"
    assert evidence["interrupted"]["interruption"]["code"] == "PROCESS_RESTART_INTERRUPTED"
