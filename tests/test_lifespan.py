"""Collector shutdown must finish even when the application lifespan fails."""
import asyncio
from contextlib import suppress
from unittest.mock import patch

import pytest

from app.main import create_app


@pytest.mark.parametrize("fails", [False, True])
def test_lifespan_always_cancels_collector(tmp_path, fails):
    async def exercise():
        app = create_app(tmp_path / "lifecycle.sqlite", collect=True)
        tasks = []
        create_task = asyncio.create_task

        def track(coroutine):
            task = create_task(coroutine)
            tasks.append(task)
            return task

        with patch("app.main.asyncio.create_task", side_effect=track), patch("app.main.Monitor.prime"):
            try:
                with pytest.raises(RuntimeError, match="lifespan failure") if fails else suppress():
                    async with app.router.lifespan_context(app):
                        # Start the real collector task before requesting shutdown.
                        await asyncio.sleep(0)
                        if fails:
                            raise RuntimeError("lifespan failure")
                assert tasks[0].cancelled()
                assert app.state.collector_status.snapshot()["state"] == "stopped"
            finally:
                # Keep a failing regression from leaving background work behind.
                for task in tasks:
                    task.cancel()
                    with suppress(asyncio.CancelledError):
                        await task

    asyncio.run(exercise())
