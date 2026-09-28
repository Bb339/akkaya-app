"""Private-staging authentication, readiness, and one-time restart recovery."""
from __future__ import annotations

import hmac
import os
import tempfile
import threading
from pathlib import Path

from flask import Flask, jsonify, request

from kds.config import project_store_path


LOCAL_MODE = "local-development"
STAGING_MODE = "staging"
PROTECTED_PREFIXES = ("/projects", "/api/v2/")


def deployment_mode() -> str:
    return os.environ.get("KDS_DEPLOYMENT_MODE", "").strip().lower()


def store_readiness() -> dict:
    configured = bool(os.environ.get("KDS_PROJECT_STORE", "").strip())
    path = project_store_path()
    exists = path.is_dir()
    writable = False
    error_code = None
    if deployment_mode() == STAGING_MODE and not configured:
        error_code = "KDS_PROJECT_STORE_REQUIRED"
    else:
        try:
            path.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=path, prefix=".readiness-", delete=True):
                pass
            exists = True
            writable = True
        except OSError:
            error_code = "PROJECT_STORE_NOT_WRITABLE"
    return {
        "configured": configured,
        "exists": exists,
        "writable": writable,
        "ready": configured and exists and writable if deployment_mode() == STAGING_MODE else exists and writable,
        "error_code": error_code,
    }


def _credentials_ready() -> bool:
    return bool(os.environ.get("KDS_BASIC_AUTH_USERNAME") and os.environ.get("KDS_BASIC_AUTH_PASSWORD"))


def _authorized() -> bool:
    auth = request.authorization
    if not auth:
        return False
    username = os.environ.get("KDS_BASIC_AUTH_USERNAME", "")
    password = os.environ.get("KDS_BASIC_AUTH_PASSWORD", "")
    return hmac.compare_digest(auth.username or "", username) and hmac.compare_digest(auth.password or "", password)


def register_operational_controls(app: Flask) -> None:
    app.extensions["kds_startup_diagnostics"] = {
        "effective_project_store": str(project_store_path()),
        "deployment_mode": deployment_mode() or "unconfigured",
    }
    app.logger.info(
        "KDS operational profile: mode=%s project_store=%s",
        app.extensions["kds_startup_diagnostics"]["deployment_mode"],
        app.extensions["kds_startup_diagnostics"]["effective_project_store"],
    )
    startup_lock = threading.Lock()
    startup_complete = False

    @app.get("/healthz")
    def healthz():
        store = store_readiness()
        mode = deployment_mode()
        configuration_ready = mode == LOCAL_MODE or (mode == STAGING_MODE and _credentials_ready())
        ready = store["ready"] and configuration_ready
        return jsonify(
            alive=True,
            ready=ready,
            deployment_mode=mode or "unconfigured",
            project_store=store,
            execution_profiles=["REFERENCE_DEMO", "VERIFIED_INSTITUTIONAL"],
            authentication={"required": mode != LOCAL_MODE, "configured": _credentials_ready()},
        ), 200 if ready else 503

    @app.before_request
    def private_staging_boundary():
        nonlocal startup_complete
        protected = request.path == "/projects" or request.path.startswith(PROTECTED_PREFIXES)
        if not protected:
            return None
        mode = deployment_mode()
        if mode != LOCAL_MODE:
            if mode != STAGING_MODE or not _credentials_ready() or not store_readiness()["ready"]:
                return jsonify(error="PRIVATE_STAGING_NOT_READY", ready=False), 503
            if not _authorized():
                response = jsonify(error="AUTHENTICATION_REQUIRED")
                response.status_code = 401
                response.headers["WWW-Authenticate"] = 'Basic realm="Crop KDS private staging"'
                return response
        if not startup_complete:
            with startup_lock:
                if not startup_complete:
                    repository = app.extensions.get("kds_project_repository")
                    recover = getattr(repository, "recover_interrupted_runs", None)
                    if recover:
                        recover()
                    startup_complete = True
        return None
