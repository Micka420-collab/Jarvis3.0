"""Registry des tâches déléguées aux agents.

Stocke en Postgres : id, agent, goal, status, created_at, finished_at, output, exit_code.
État : pending → running → completed | failed | cancelled
"""

from __future__ import annotations

import asyncio
import datetime as dt
import logging
import os
import uuid
from dataclasses import dataclass, field
from typing import Literal

import asyncpg

log = logging.getLogger("agents.tasks")

Status = Literal["pending", "running", "completed", "failed", "cancelled"]


@dataclass
class Task:
    id: str
    agent: str
    goal: str
    user_id: str | None = None
    status: Status = "pending"
    output: str = ""
    exit_code: int | None = None
    created_at: dt.datetime = field(default_factory=lambda: dt.datetime.utcnow())
    finished_at: dt.datetime | None = None
    proc_handle: asyncio.Task | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "agent": self.agent,
            "goal": self.goal,
            "user_id": self.user_id,
            "status": self.status,
            "output": self.output,
            "exit_code": self.exit_code,
            "created_at": self.created_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
        }


CREATE_SQL = """
CREATE TABLE IF NOT EXISTS agent_tasks (
    id          UUID PRIMARY KEY,
    agent       TEXT NOT NULL,
    goal        TEXT NOT NULL,
    user_id     UUID REFERENCES users(id) ON DELETE SET NULL,
    status      TEXT NOT NULL DEFAULT 'pending',
    output      TEXT NOT NULL DEFAULT '',
    exit_code   INT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS agent_tasks_status_idx ON agent_tasks(status, created_at DESC);
"""


class TaskRegistry:
    def __init__(self) -> None:
        self.pool: asyncpg.Pool | None = None
        self._live: dict[str, Task] = {}

    async def connect(self) -> None:
        self.pool = await asyncpg.create_pool(
            host=os.getenv("POSTGRES_HOST", "postgres"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            database=os.getenv("POSTGRES_DB", "jarvis"),
            user=os.getenv("POSTGRES_USER", "jarvis"),
            password=os.getenv("POSTGRES_PASSWORD", ""),
            min_size=1,
            max_size=3,
        )
        async with self.pool.acquire() as conn:
            await conn.execute(CREATE_SQL)

    async def create(self, agent: str, goal: str, user_id: str | None = None) -> Task:
        task = Task(id=str(uuid.uuid4()), agent=agent, goal=goal, user_id=user_id)
        self._live[task.id] = task
        async with self.pool.acquire() as conn:  # type: ignore[union-attr]
            await conn.execute(
                "INSERT INTO agent_tasks(id, agent, goal, user_id, status) VALUES($1, $2, $3, $4, $5)",
                task.id,
                task.agent,
                task.goal,
                user_id,
                task.status,
            )
        return task

    async def update(self, task_id: str, *, status: Status | None = None, output_append: str = "", exit_code: int | None = None) -> None:
        task = self._live.get(task_id)
        if task and status:
            task.status = status
        if task and output_append:
            task.output += output_append
        if task and exit_code is not None:
            task.exit_code = exit_code
        if task and status in {"completed", "failed", "cancelled"}:
            task.finished_at = dt.datetime.utcnow()

        # persist
        sets: list[str] = []
        values: list = []
        if status:
            sets.append(f"status = ${len(values) + 1}")
            values.append(status)
        if output_append:
            sets.append(f"output = output || ${len(values) + 1}")
            values.append(output_append)
        if exit_code is not None:
            sets.append(f"exit_code = ${len(values) + 1}")
            values.append(exit_code)
        if status in {"completed", "failed", "cancelled"}:
            sets.append("finished_at = NOW()")
        if not sets:
            return
        values.append(task_id)
        async with self.pool.acquire() as conn:  # type: ignore[union-attr]
            await conn.execute(
                f"UPDATE agent_tasks SET {', '.join(sets)} WHERE id = ${len(values)}",
                *values,
            )

    async def get(self, task_id: str) -> dict | None:
        live = self._live.get(task_id)
        if live:
            return live.to_dict()
        async with self.pool.acquire() as conn:  # type: ignore[union-attr]
            row = await conn.fetchrow("SELECT * FROM agent_tasks WHERE id = $1", task_id)
        if row is None:
            return None
        return {
            "id": str(row["id"]),
            "agent": row["agent"],
            "goal": row["goal"],
            "user_id": str(row["user_id"]) if row["user_id"] else None,
            "status": row["status"],
            "output": row["output"],
            "exit_code": row["exit_code"],
            "created_at": row["created_at"].isoformat(),
            "finished_at": row["finished_at"].isoformat() if row["finished_at"] else None,
        }

    async def list_recent(self, limit: int = 50) -> list[dict]:
        async with self.pool.acquire() as conn:  # type: ignore[union-attr]
            rows = await conn.fetch(
                """
                SELECT id, agent, goal, status, exit_code, created_at, finished_at
                  FROM agent_tasks
              ORDER BY created_at DESC
                 LIMIT $1
                """,
                limit,
            )
        return [
            {
                "id": str(r["id"]),
                "agent": r["agent"],
                "goal": r["goal"],
                "status": r["status"],
                "exit_code": r["exit_code"],
                "created_at": r["created_at"].isoformat(),
                "finished_at": r["finished_at"].isoformat() if r["finished_at"] else None,
            }
            for r in rows
        ]

    async def cancel(self, task_id: str) -> bool:
        task = self._live.get(task_id)
        if task is None or task.proc_handle is None:
            return False
        task.proc_handle.cancel()
        await self.update(task_id, status="cancelled")
        return True
