"""FastAPI server for the local-only TechPulse dashboard."""
from __future__ import annotations
import asyncio
import logging
import os
import platform
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .monitor import Monitor, compute_alerts, top_processes
from .health_state import evaluate_sample_state
from .collector_state import CollectorStatus
from .storage import HistoryStore
from .windows_events import read_failed_logins

BASE = Path(__file__).resolve().parent
DEFAULT_DB = Path(os.environ.get("TECHPULSE_DB", str(BASE.parent / "data" / "techpulse.sqlite3")))
LOG = logging.getLogger("techpulse")


def create_app(db_path: Path | None = None, collect: bool = True, interval: int = 15) -> FastAPI:
    store = HistoryStore(db_path or DEFAULT_DB)
    monitor = Monitor()
    collector_status = CollectorStatus(enabled=collect)

    async def collect_loop():
        count = 0
        primed = False
        try:
            while True:
                try:
                    if not primed:
                        await asyncio.to_thread(monitor.prime)
                        primed = True
                        await asyncio.sleep(.5)
                    sample = await asyncio.to_thread(monitor.sample)
                    await asyncio.to_thread(store.add, sample)
                    collector_status.succeeded()
                    count += 1
                    if count % 240 == 0:
                        await asyncio.to_thread(store.prune)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    collector_status.failed()
                    primed = False
                    LOG.exception("Sample failed; trying again on next interval")
                await asyncio.sleep(interval)
        finally:
            collector_status.stopped()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        task = asyncio.create_task(collect_loop()) if collect else None
        yield
        if task:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    app = FastAPI(title="TechPulse", version="0.1.0", lifespan=lifespan, docs_url="/api/docs", redoc_url=None)
    app.state.collector_status = collector_status
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1"])
    app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")

    @app.get("/", include_in_schema=False)
    def home():
        return FileResponse(BASE / "static" / "index.html")

    @app.get("/api/health")
    def health():
        # "ok" means the HTTP server responds; inspect collector.state for sampling health.
        return {"status": "ok", "version": "0.1.0", "local_only": True,
                "collector": collector_status.snapshot()}

    @app.get("/api/overview")
    def overview():
        latest = store.latest()
        freshness = evaluate_sample_state(latest, interval_seconds=interval)
        collector = collector_status.snapshot()
        if latest:
            latest["os_name"] = f"{platform.system()} {platform.release()}"
        # A recent SQLite row is not proof this process is still sampling.
        live = freshness["state"] == "fresh" and collector["state"] == "running"
        alerts = compute_alerts(latest) if live else []
        return {"sample": latest, "alerts": alerts, "interval_seconds": interval,
                "collection": freshness, "collector": collector}

    @app.get("/api/history")
    def history(minutes: int = Query(default=120, ge=10, le=10080)):
        return {"points": store.recent(minutes=minutes), "window_minutes": minutes}

    @app.get("/api/processes")
    def processes():
        return {"processes": top_processes()}

    @app.get("/api/security")
    def security():
        return read_failed_logins()

    @app.get("/api/export.csv")
    def export_csv():
        return PlainTextResponse(store.csv_export(), media_type="text/csv",
                                 headers={"Content-Disposition": 'attachment; filename="techpulse-history.csv"'})
    return app


app = create_app()
