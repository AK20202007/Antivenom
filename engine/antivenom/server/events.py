"""Local event server.

FastAPI + WebSocket, bound to localhost. Local on purpose: the dashboard must
keep animating when the venue WiFi does not, and a cloud round-trip on the
demo-critical path is a dependency we do not need.

Endpoints:

* ``GET  /health``        — liveness, plus the current feature flags
* ``GET  /api/run``       — the persisted run, for replay with no engine
* ``GET  /api/history``   — everything published on the bus this process
* ``WS   /ws``            — live event stream, replayed from the top on connect

A client that connects mid-run is sent the history first, so refreshing the
browser thirty seconds before a demo does not cost you the cascade.
"""

from __future__ import annotations

import asyncio
import contextlib
from pathlib import Path
from typing import Any

from fastapi.staticfiles import StaticFiles

from ..config import DATA_DIR, features, settings
from ..demo import DEMO_RUN_PATH
from ..events import BUS, EVENT_ADAPTER, load_run

__all__ = ["create_app", "serve"]


def create_app(run_path: Path | None = None) -> FastAPI:
    app = FastAPI(
        title="Antivenom event channel",
        version="0.1.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )

    audio_dir = DATA_DIR / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/audio", StaticFiles(directory=audio_dir), name="audio")

    # The dashboard dev server runs on a different port; in production the
    # static build is served from Pages and talks to this over localhost.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:4173",
            "https://antivenom.pages.dev",
        ],
        allow_credentials=False,
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health() -> dict[str, Any]:
        f = features()
        return {
            "ok": True,
            "flags": {"mongo": f.mongo, "vlm": f.vlm, "voice": f.voice},
            "demo_floor": f.demo_floor,
            "events_buffered": len(BUS.history),
        }

    @app.get("/api/run")
    async def get_run() -> JSONResponse:
        """The persisted run. This is the offline replay source and, if
        everything dies, the honest fallback — which is only honest if it is
        announced as a prior run."""
        path = run_path or DEMO_RUN_PATH
        if not path.exists():
            return JSONResponse(
                {"error": "no run recorded", "hint": "run: antivenom demo --write"},
                status_code=404,
            )
        events, meta = load_run(path)
        return JSONResponse(
            {
                "meta": meta,
                "events": [EVENT_ADAPTER.dump_python(e, mode="json") for e in events],
            }
        )

    @app.get("/api/history")
    async def history() -> dict[str, Any]:
        return {"events": [EVENT_ADAPTER.dump_python(e, mode="json") for e in BUS.history]}

    @app.websocket("/ws")
    async def ws(socket: WebSocket) -> None:
        await socket.accept()
        try:
            for event in BUS.history:
                await socket.send_text(EVENT_ADAPTER.dump_json(event).decode())
            async for event in BUS.subscribe():
                await socket.send_text(EVENT_ADAPTER.dump_json(event).decode())
        except (WebSocketDisconnect, asyncio.CancelledError):
            pass
        except RuntimeError:  # pragma: no cover - socket closed under us
            pass
        finally:
            with contextlib.suppress(RuntimeError):
                await socket.close()

    return app


def serve(run_path: Path | None = None) -> None:
    import uvicorn

    cfg = settings()
    uvicorn.run(create_app(run_path), host=cfg.host, port=cfg.port, log_level="warning")
