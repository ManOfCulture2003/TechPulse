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
from .storage import HistoryStore
from .windows_events import read_failed_logins

BASE = Path(__file__).resolve().parent
DEFAULT_DB = Path(os.environ.get("TECHPULSE_DB", str(BASE.parent / "data" / "techpulse.sqlite3")))
LOG = logging.getLogger("techpulse")


def create_app(db_path: Path | None = None, collect: bool = True, interval: int = 15) -> FastAPI:
    store = HistoryStore(db_path or DEFAULT_DB)
    monitor = Monitor()

    async def collect_loop():
        await asyncio.to_thread(monitor.prime)
        await asyncio.sleep(.5)
        count = 0
        while True:
            try:
                sample = await asyncio.to_thread(monitor.sample)
                await asyncio.to_thread(store.add, sample)
                count += 1
                if count % 240 == 0:
                    await asyncio.to_thread(store.prune)
            except asyncio.CancelledError:
                raise
            except Exception:
                LOG.exception("Sample failed; trying again on next interval")
            await asyncio.sleep(interval)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        task = asyncio.create_task(collect_loop()) if collect else None
        yield
        if task:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    app = FastAPI(title="TechPulse", version="0.1.0", lifespan=lifespan, docs_url="/api/docs", redoc_url=None)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1"])
    app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")

    @app.get("/", include_in_schema=False)
    def home():
        return FileResponse(BASE / "static" / "index.html")

    @app.get("/api/health")
    def health():
        return {"status": "ok", "version": "0.1.0", "local_only": True}

    @app.get("/api/overview")
    def overview():
        latest = store.latest()
        if latest:
            latest["os_name"] = f"{platform.system()} {platform.release()}"
        return {"sample": latest, "alerts": compute_alerts(latest) if latest else [], "interval_seconds": interval}

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
