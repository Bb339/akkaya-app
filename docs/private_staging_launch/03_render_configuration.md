# Render configuration prepared

The root `render.yaml` passed the current official Render JSON Schema with zero validation errors.

- Runtime: Python 3.11.11
- Build: `pip install -r requirements.txt`
- Start: `gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --timeout 360 --graceful-timeout 30 --keep-alive 5`
- Instances: 1
- Health path: `/healthz`
- Auto deploy: `autoDeployTrigger: 'off'`
- Disk mount: `/var/data/crop-kds`
- Project store: `/var/data/crop-kds/projects`
- Deployment mode: `staging`
- Basic Auth username/password: Render secret inputs (`sync: false`); values are intentionally absent from Git and evidence.

Status: configuration prepared; Render service not created because this session has no authenticated Render account access.

