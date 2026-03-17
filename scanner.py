import asyncio
import os
import subprocess
import time

import docker as docker_sdk
import httpx
import yaml

PROJECTS_DIR = os.getenv("PROJECTS_DIR", "/opt/ctsdeploy/projects")
DOMAIN = os.getenv("DOMAIN", "benkruseski.com")
LOG_FILE = os.getenv("LOG_FILE", "/var/log/ctsdeploy/deploy.log")

_cache: dict = {"data": None, "timestamp": 0.0}
CACHE_TTL = 30  # seconds


def scan_projects() -> list[dict]:
    """Scan PROJECTS_DIR for CTSDeploy projects by reading their deploy.yaml files."""
    projects = []
    if not os.path.isdir(PROJECTS_DIR):
        return projects

    for repo_name in sorted(os.listdir(PROJECTS_DIR)):
        repo_path = os.path.join(PROJECTS_DIR, repo_name)
        if not os.path.isdir(repo_path):
            continue

        deploy_yaml_path = os.path.join(repo_path, "deploy.yaml")
        if not os.path.isfile(deploy_yaml_path):
            continue

        try:
            with open(deploy_yaml_path) as f:
                config = yaml.safe_load(f)
        except Exception:
            continue

        project_name = config.get("project_name")
        port = config.get("port")
        branch = config.get("branch", "main")

        if not project_name or not port:
            continue

        projects.append({
            "repo_name": repo_name,
            "project_name": project_name,
            "port": port,
            "branch": branch,
            "url": f"https://{project_name}.{DOMAIN}",
            "repo_path": repo_path,
        })

    return projects


async def check_http_status(url: str) -> tuple[str, int | None]:
    """Return (status_label, http_code) for a URL."""
    try:
        async with httpx.AsyncClient(timeout=5, follow_redirects=True) as client:
            resp = await client.get(url)
            code = resp.status_code
            if code < 400:
                return "up", code
            elif code < 500:
                return "degraded", code
            else:
                return "error", code
    except httpx.TimeoutException:
        return "timeout", None
    except Exception:
        return "down", None


def get_docker_containers(repo_path: str) -> list[dict]:
    """Get Docker container statuses for a project using compose project labels."""
    try:
        client = docker_sdk.from_env()
        compose_project = os.path.basename(repo_path).lower()
        containers = client.containers.list(
            all=True,
            filters={"label": f"com.docker.compose.project={compose_project}"},
        )
        return [
            {
                "name": c.name,
                "status": c.status,
                "image": c.image.tags[0] if c.image.tags else c.image.short_id,
            }
            for c in containers
        ]
    except Exception:
        return []


def get_last_commit(repo_path: str) -> dict | None:
    """Return last git commit info for a repo."""
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%H|%s|%aI"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().split("|", 2)
            if len(parts) == 3:
                return {
                    "hash": parts[0][:8],
                    "message": parts[1],
                    "timestamp": parts[2],
                }
    except Exception:
        pass
    return None


async def get_project_status(project: dict) -> dict:
    """Fetch full status for a single project."""
    http_status, http_code = await check_http_status(project["url"])
    containers = get_docker_containers(project["repo_path"])
    last_commit = get_last_commit(project["repo_path"])

    if http_status == "up":
        overall = "up"
    elif http_status == "degraded":
        overall = "degraded"
    elif http_status in ("down", "timeout", "error"):
        overall = "down"
    else:
        overall = "unknown"

    return {
        "repo_name": project["repo_name"],
        "project_name": project["project_name"],
        "port": project["port"],
        "branch": project["branch"],
        "url": project["url"],
        "status": overall,
        "http_status": http_status,
        "http_code": http_code,
        "containers": containers,
        "last_commit": last_commit,
    }


async def get_all_projects_status(force: bool = False) -> list[dict]:
    """Return status for all detected projects, with a 30-second cache."""
    now = time.time()
    if not force and _cache["data"] is not None and (now - _cache["timestamp"]) < CACHE_TTL:
        return _cache["data"]

    projects = scan_projects()
    results = await asyncio.gather(*[get_project_status(p) for p in projects])
    _cache["data"] = list(results)
    _cache["timestamp"] = now
    return _cache["data"]


def get_recent_deploy_logs(lines: int = 100) -> list[str]:
    """Read the most recent lines from the CTSDeploy log file."""
    if not os.path.isfile(LOG_FILE):
        return []
    try:
        with open(LOG_FILE) as f:
            all_lines = f.readlines()
        return [line.rstrip() for line in all_lines[-lines:]]
    except Exception:
        return []
