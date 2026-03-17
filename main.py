import time

from fastapi import FastAPI, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from scanner import get_all_projects_status, get_recent_deploy_logs, _cache

app = FastAPI(title="CTSStatus")


@app.get("/api/projects")
async def list_projects(refresh: bool = Query(False)):
    projects = await get_all_projects_status(force=refresh)
    return {
        "projects": projects,
        "cached_at": _cache["timestamp"],
        "count": len(projects),
    }


@app.get("/api/logs")
async def recent_logs(lines: int = Query(100, ge=1, le=500)):
    return {"logs": get_recent_deploy_logs(lines)}


app.mount("/", StaticFiles(directory="static", html=True), name="static")
