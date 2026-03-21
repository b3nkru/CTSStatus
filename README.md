# CTSStatus

Live status dashboard for all projects deployed via [CTSDeploy](https://github.com/benkruseski/CTSDeploy) on `benkruseski.com`.

**Live:** [status.benkruseski.com](https://status.benkruseski.com)

## What it does

- Auto-detects CTSDeploy projects by scanning `/opt/ctsdeploy/projects` for `deploy.yaml` files
- Checks HTTP status of each project's public URL
- Reports Docker container state for each project
- Shows last git commit (hash, message, timestamp) per project
- Streams recent CTSDeploy deploy logs
- 30-second response cache, force-refreshable via `?refresh=true`

## Stack

- **Backend:** FastAPI + Python 3.11
- **Container:** Docker via `docker-compose`
- **Deploy:** CTSDeploy webhook → auto-build on push to `main`
- **Reverse proxy:** nginx (managed by CTSDeploy)

## API

| Endpoint | Description |
|----------|-------------|
| `GET /api/projects` | All project statuses (cached 30s) |
| `GET /api/projects?refresh=true` | Force cache refresh |
| `GET /api/logs?lines=100` | Recent deploy log lines (1–500) |

## Running locally

```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 6767
```

The app expects `/opt/ctsdeploy/projects` to exist and contain CTSDeploy project directories. Override via env vars:

```bash
PROJECTS_DIR=/path/to/projects DOMAIN=yourdomain.com uvicorn main:app --port 6767
```

## Docker

```bash
docker compose up --build
```

Mounts required:
- `/opt/ctsdeploy/projects` — project directories (read-only)
- `/var/run/docker.sock` — Docker socket for container inspection (read-only)
- `/var/log/ctsdeploy` — deploy log directory (read-only)
