"""Service LLM : expose /complete (REST), agnostique du provider."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .router import make_adapter

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
log = logging.getLogger("llm")

SYSTEM_PROMPT = (Path(__file__).parent / "prompts" / "system.md").read_text(encoding="utf-8")


class CompleteRequest(BaseModel):
    messages: list[dict]
    tools: list[dict] | None = None
    provider: str | None = None
    max_tokens: int = 1024
    temperature: float = 0.6


class CompleteResponse(BaseModel):
    text: str
    tool_calls: list[dict] = []
    stop_reason: str = "stop"


app = FastAPI(title="Jarvis LLM router", version="0.1.0")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "llm"}


@app.post("/complete", response_model=CompleteResponse)
async def complete(req: CompleteRequest) -> CompleteResponse:
    try:
        adapter = make_adapter(req.provider)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"adapter init: {e}")
    out = await adapter.complete(
        SYSTEM_PROMPT, req.messages, req.tools, req.max_tokens, req.temperature
    )
    return CompleteResponse(**out)
