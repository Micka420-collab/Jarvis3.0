"""Service `agents` : délègue des tâches à des agents externes (Hermes, OpenClaw, MCP).

Endpoints :
  GET  /health
  GET  /agents                    → liste des adapters disponibles + dispo binaire
  POST /delegate                  → {agent, goal} → {task_id, status}
  GET  /tasks                     → liste tâches récentes
  GET  /tasks/{id}                → détail tâche
  GET  /tasks/{id}/stream         → SSE live output (utile pour UI)
  POST /tasks/{id}/cancel         → kill subprocess
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from _shared.bus import EventBus  # noqa: E402

from .adapters import build_default_registry  # noqa: E402
from .tasks import TaskRegistry  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
log = logging.getLogger("agents")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.adapters = build_default_registry()
    app.state.tasks = TaskRegistry()
    await app.state.tasks.connect()
    app.state.bus = EventBus()
    await app.state.bus.connect()
    log.info("agents service ready, adapters=%s", list(app.state.adapters.keys()))
    yield
    await app.state.bus.close()


app = FastAPI(title="Jarvis Agents", version="0.1.0", lifespan=lifespan)


class DelegateRequest(BaseModel):
    agent: str
    goal: str
    user_id: str | None = None
    context: dict = {}


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "agents"}


@app.get("/agents")
async def list_agents() -> list[dict]:
    out = []
    for name, ad in app.state.adapters.items():
        info = await ad.info()
        out.append(
            {
                "name": info.name,
                "available": info.available,
                "command": info.command,
                "notes": info.notes,
            }
        )
    return out


@app.post("/delegate")
async def delegate(req: DelegateRequest) -> dict:
    adapter = app.state.adapters.get(req.agent)
    if adapter is None:
        raise HTTPException(status_code=404, detail=f"agent inconnu: {req.agent}")
    info = await adapter.info()
    if not info.available:
        raise HTTPException(
            status_code=503,
            detail=f"agent '{req.agent}' indispo : binaire '{info.command}' introuvable. "
            "Voir docs/agents.md pour l'installation.",
        )
    task = await app.state.tasks.create(
        agent=req.agent, goal=req.goal, user_id=req.user_id
    )
    task.proc_handle = asyncio.create_task(_run_task(task.id, adapter, req.goal, req.context))
    return {"task_id": task.id, "status": task.status}


async def _run_task(task_id: str, adapter, goal: str, context: dict) -> None:
    registry: TaskRegistry = app.state.tasks
    bus: EventBus = app.state.bus
    await registry.update(task_id, status="running")
    await bus.publish_pubsub(
        "ui.agents", {"type": "started", "task_id": task_id, "agent": adapter.name}
    )
    final_chunks: list[str] = []
    exit_code = 0
    try:
        async for chunk in adapter.run(goal, context):
            final_chunks.append(chunk)
            # update DB toutes les ~512 chars de output pour ne pas spammer
            if sum(len(c) for c in final_chunks) % 512 < len(chunk):
                await registry.update(task_id, output_append=chunk)
            await bus.publish_pubsub(
                "ui.agents", {"type": "chunk", "task_id": task_id, "text": chunk}
            )
            if chunk.startswith('{"type": "exit"'):
                try:
                    exit_code = json.loads(chunk).get("code", 0)
                except Exception:
                    pass
    except asyncio.CancelledError:
        await registry.update(task_id, status="cancelled", output_append="\n[cancelled]")
        await bus.publish_pubsub("ui.agents", {"type": "cancelled", "task_id": task_id})
        raise
    except Exception as e:
        log.exception("task %s failed: %s", task_id, e)
        await registry.update(
            task_id, status="failed", output_append=f"\n[error] {e}", exit_code=1
        )
        await bus.publish_pubsub(
            "ui.agents", {"type": "failed", "task_id": task_id, "error": str(e)}
        )
        return

    await registry.update(
        task_id,
        status="completed" if exit_code == 0 else "failed",
        output_append="".join(final_chunks),
        exit_code=exit_code,
    )
    await bus.publish_pubsub(
        "ui.agents",
        {"type": "completed", "task_id": task_id, "exit_code": exit_code},
    )


@app.get("/tasks")
async def list_tasks(limit: int = 50) -> list[dict]:
    return await app.state.tasks.list_recent(limit=limit)


@app.get("/tasks/{task_id}")
async def get_task(task_id: str) -> dict:
    out = await app.state.tasks.get(task_id)
    if out is None:
        raise HTTPException(status_code=404, detail="task inconnue")
    return out


@app.get("/tasks/{task_id}/stream")
async def stream_task(task_id: str) -> StreamingResponse:
    """SSE : suit un stream pub/sub `ui.agents` filtré sur ce task_id."""

    async def gen():
        bus: EventBus = app.state.bus
        async for payload in bus.subscribe_pubsub("ui.agents"):
            if payload.get("task_id") != task_id:
                continue
            yield f"data: {json.dumps(payload)}\n\n"
            if payload.get("type") in {"completed", "failed", "cancelled"}:
                return

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.post("/tasks/{task_id}/cancel")
async def cancel_task(task_id: str) -> dict:
    ok = await app.state.tasks.cancel(task_id)
    if not ok:
        raise HTTPException(status_code=404, detail="task inconnue ou déjà terminée")
    return {"cancelled": True}
