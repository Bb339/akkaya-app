# Private staging configuration

`render.yaml` pins Python 3.11.11, installs `requirements.txt`, attaches one persistent disk, and runs:

`gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --timeout 360 --graceful-timeout 30 --keep-alive 5`

The service has one instance, one Gunicorn worker, automatic deployment disabled, and `/healthz` as its health check. The 360-second worker timeout is above the application's 300-second scientific execution timeout.

Required staging variables are `KDS_DEPLOYMENT_MODE=staging`, `KDS_PROJECT_STORE=/var/data/crop-kds/projects`, `KDS_BASIC_AUTH_USERNAME`, and `KDS_BASIC_AUTH_PASSWORD`. Credential values are secret environment settings and are absent from the repository.

`py app.py` selects the explicit local-development profile and uses Flask's local debug server. That command is not a staging entrypoint.

## Resource contract

One Gunicorn worker may spawn one scientific child for a synchronous analysis. Capacity planning must therefore cover the resident WSGI process plus a spawned Python process importing the scientific stack. Requests are serialized by the single worker during a long analysis. The hosting edge must permit a request longer than 300 seconds; the manifest can govern Gunicorn but cannot guarantee an external proxy timeout.

`MULTI-INSTANCE / HORIZONTAL SCALE = NOT SUPPORTED`

