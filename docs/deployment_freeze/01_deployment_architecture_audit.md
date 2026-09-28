# Local / staging deployment architecture audit

## Audited baseline

- Accepted local annotated tag: `v2-unified-decision-screen-smart-import-complete`
- Tag target and worktree HEAD: `6a76edce875451507b865e608e23c2384ff60d67`
- Audit branch: `v2-local-staging-deployment-freeze`
- Audit mode: source/configuration inspection only; the server, browser, optimizer, GA and demo package were not run.

## Flask entry point and existing commands

- WSGI object: `app:app`. `app.py` creates `app = Flask(__name__, static_folder=None)` and registers the V2 project API during module import.
- Repository-documented local command: `py app.py`.
- That command executes Flask's development server with `debug=True`, `host="127.0.0.1"`, `port=5000`, and `use_reloader=False`. It is local-only and is not a staging command.
- The project-science documentation also gives a local alternative: `py -B -m flask --app app run --host 127.0.0.1 --port 5052 --no-reload`.
- Repository-defined staging command: **ABSENT**. There is no `render.yaml`, `render.yml`, `Procfile`, Dockerfile, compose file or other deployment manifest.
- `gunicorn` is listed in `requirements.txt`, so `app:app` is a compatible WSGI target on a POSIX host, but the repository does not define worker count, bind address, port interpolation or timeout. A command such as `gunicorn app:app` would inherit Gunicorn's default timeout and is not safe for the current synchronous analysis endpoint.

## Python and dependency requirements

`requirements.txt` declares:

- `flask>=2.2`
- `pandas>=2.0`
- `openpyxl>=3.1`
- `numpy>=1.24`
- `python-dateutil>=2.8`
- `pytest>=8.0`
- `gunicorn`

There is no Python runtime pin, lock file or hashes. Runtime syntax uses Python 3.10 union types, so Python **3.10 or newer** is required. The accepted local validation environment used Python 3.11, but the repository does not encode that choice for staging. `pytest` is included in the runtime requirements even though it is test-only.

## Multiprocessing and subprocess contract

- Every scientific analysis uses `multiprocessing.get_context('spawn')` and a fresh daemon child process.
- The scientific execution limit is 300 seconds. The parent waits on a pipe, then joins for 2 seconds and terminates a still-running child with a further 5-second join.
- Reference-data snapshot preparation also uses a spawned child process with a 120-second limit.
- A deployment must allow Python child-process creation, IPC pipes and enough memory for the parent worker plus imported NumPy/Pandas/application state in each child.
- Multiple WSGI workers may each spawn analysis children concurrently. No queue or global concurrency limit is configured.
- Analysis requests are synchronous HTTP requests. Gunicorn's default 30-second worker timeout is shorter than the application's 300-second analysis limit. The hosting/proxy timeout must also be checked. Until an explicit command and compatible timeout policy exist, staging analyses can be killed before the application timeout is reached.
- Run provenance calls `git rev-parse HEAD` through `subprocess.run`. If Git exists but repository metadata is absent, the recorded engine commit becomes `null`. If the Git executable itself is absent, `FileNotFoundError` is not caught. The staging image therefore has an undeclared Git/runtime-metadata dependency.

## Render / staging inventory and risks

- Render configuration: **ABSENT**.
- Build command: **NOT DEFINED**.
- Start command: **NOT DEFINED**.
- Python version: **NOT PINNED**.
- Persistent disk: **NOT CONFIGURED**.
- Database/object store: **NOT CONFIGURED**.
- Health check: **NOT CONFIGURED**.
- Worker count and analysis concurrency: **NOT CONFIGURED**.
- WSGI/edge timeout policy: **NOT CONFIGURED**.
- The README states that authentication has not been added and the API is local-development scope. Exposing the current project/import/analysis API on a public staging URL would expose unauthenticated state-changing endpoints.

## Local Windows-path dependency

- Local instructions use the Windows `py` launcher and the default store uses `%LOCALAPPDATA%` when available.
- Runtime source/data discovery uses paths relative to `app.py`; no hard-coded `C:\Users\...` or OneDrive path was found in runtime code.
- The store falls back portably to `XDG_DATA_HOME` or `~/.local/share` outside Windows.
- File locking has explicit Windows (`msvcrt`) and POSIX (`fcntl`) implementations.
- Gunicorn is a POSIX staging server and is not the Windows local launch path.

## Deployment blockers

1. **STAGING ENTRYPOINT CONFIGURATION BLOCKER:** no repository-defined Render/staging build or start configuration exists.
2. **REQUEST TIMEOUT BLOCKER:** the synchronous analysis may run for 300 seconds while an unconfigured Gunicorn launch defaults to a substantially shorter worker timeout.
3. **PUBLIC ACCESS BLOCKER:** state-changing project, upload and analysis APIs have no authentication; public staging must be access-restricted or gain an authentication boundary.
4. **PROCESS/PROVENANCE RISK:** spawned analysis workers require child-process support and sufficient memory; Git executable/metadata availability is not declared even though run provenance invokes Git.

No staging deployment should start until these blockers have explicit, reviewed resolutions.
