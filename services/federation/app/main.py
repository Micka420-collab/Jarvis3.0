"""Service `federation` : sync entre instances Jarvis (résidence principale ↔
secondaire, voire mobile).

Fonctionnalités cibles (v0.1) :
- Heartbeat : chaque instance publie son état toutes les 30 s
- Catalog sync : devices, routines, users (préfixés par `instance_id`)
- Memory share : facts global vs local (Qdrant collection partagée)
- Forwarding : si un device n'est pas trouvé localement, on demande aux peers

Sécurité :
- Auth mTLS + token JWT signé par la clé maître de l'utilisateur
- Whitelist d'instances dans config/peers.yaml
- Pas de propagation de secrets (clés API LLM restent locales)

Pour l'instant : skeleton FastAPI + bus pub/sub `federation.*` + heartbeat.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from _shared.bus import EventBus  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
log = logging.getLogger("federation")

INSTANCE_ID = os.getenv("FEDERATION_INSTANCE_ID", str(uuid.uuid4())[:8])
INSTANCE_LABEL = os.getenv("FEDERATION_LABEL", "primary")
PEERS = [p.strip() for p in os.getenv("FEDERATION_PEERS", "").split(",") if p.strip()]
HEARTBEAT_INTERVAL = int(os.getenv("FEDERATION_HEARTBEAT_S", "30"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.bus = EventBus()
    await app.state.bus.connect()
    app.state.peers_state: dict[str, dict] = {}
    app.state.bg_task = asyncio.create_task(_heartbeat_loop(app))
    log.info("federation ready (instance=%s, peers=%s)", INSTANCE_ID, PEERS)
    yield
    app.state.bg_task.cancel()
    await app.state.bus.close()


app = FastAPI(title="Jarvis Federation", version="0.1.0", lifespan=lifespan)


async def _heartbeat_loop(app: FastAPI) -> None:
    while True:
        try:
            payload = {
                "instance_id": INSTANCE_ID,
                "label": INSTANCE_LABEL,
                "ts": time.time(),
                "kind": "heartbeat",
            }
            await app.state.bus.publish_pubsub("federation", payload)
            for peer in PEERS:
                try:
                    async with httpx.AsyncClient(timeout=3.0) as c:
                        await c.post(f"{peer}/api/federation/heartbeat", json=payload)
                except Exception as e:
                    log.debug("peer %s unreachable: %s", peer, e)
        except Exception as e:
            log.exception("heartbeat loop crashed: %s", e)
        await asyncio.sleep(HEARTBEAT_INTERVAL)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "federation", "instance_id": INSTANCE_ID}


@app.get("/peers")
async def peers() -> dict:
    return {"configured": PEERS, "live": list(app.state.peers_state.keys())}


@app.post("/heartbeat")
async def heartbeat(payload: dict) -> dict:
    """Endpoint reçu par les peers. Stocke leur état pour la /peers query."""
    iid = payload.get("instance_id")
    if iid:
        app.state.peers_state[iid] = {**payload, "received_at": time.time()}
    return {"ack": True}
