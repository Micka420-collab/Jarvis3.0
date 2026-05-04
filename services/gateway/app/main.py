"""Jarvis 3.0 — gateway FastAPI.

Point d'entrée HTTPS unique pour le frontend et les clients externes.
- API REST sous /api
- WebSockets sous /ws
- Reverse proxy interne via Traefik
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import close_pool, get_pool
from .routes import admin, auth as auth_routes, chat, explain, health, iot, push, security
from .ws import avatar as avatar_ws, voice as voice_ws

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
log = logging.getLogger("gateway")


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("démarrage du gateway, domaine=%s", settings.jarvis_domain)
    try:
        await get_pool()
    except Exception as e:
        log.warning("Postgres indisponible au boot (%s) — réessai à la 1ère requête", e)
    yield
    await close_pool()


app = FastAPI(title="Jarvis 3.0 Gateway", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[f"https://{settings.jarvis_domain}", "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

# --- REST ---
app.include_router(health.router, prefix="/api")
app.include_router(auth_routes.router, prefix="/api/auth", tags=["auth"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(iot.router, prefix="/api/iot", tags=["iot"])
app.include_router(security.router, prefix="/api/security", tags=["security"])
app.include_router(push.router, prefix="/api/push", tags=["push"])
app.include_router(explain.router, prefix="/api/explain", tags=["explain"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])

# --- WebSockets ---
app.include_router(voice_ws.router, prefix="/ws")
app.include_router(avatar_ws.router, prefix="/ws")


@app.get("/")
async def root() -> dict:
    return {"name": "Jarvis 3.0", "version": "0.1.0", "docs": "/docs"}
