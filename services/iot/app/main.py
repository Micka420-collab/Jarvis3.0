"""Service IoT : routeur unifié MQTT / HA / série.

- Charge `devices.yaml` au démarrage
- Expose `/command` (REST) pour les commandes
- Découvre les entités HA via `/discover/ha` (sync vers la table `devices`)
- Publie les states reçus (MQTT/série) sur le bus Redis (`iot.device.state`)
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import asyncpg
import yaml
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

# permet d'importer services/_shared/*
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from _shared.bus import EventBus  # noqa: E402
from _shared.events import (  # noqa: E402
    STREAM_IOT_COMMAND,
    STREAM_IOT_STATE,
    IotDeviceCommand,
    IotDeviceState,
)

from .ha_bridge import HABridge  # noqa: E402
from .mqtt_bridge import MQTTBridge  # noqa: E402
from .serial_bridge import SerialBridge  # noqa: E402
from .zigbee_bridge import Z2MBridge  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
log = logging.getLogger("iot")

DEVICES_FILE = Path(__file__).parent / "devices.yaml"


def load_devices() -> dict[str, dict]:
    raw = yaml.safe_load(DEVICES_FILE.read_text(encoding="utf-8"))
    return {d["id"]: d for d in raw.get("devices", [])}


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.devices = load_devices()
    app.state.bus = EventBus()
    await app.state.bus.connect()

    async def emit_state(device_id: str, payload: dict, transport: str) -> None:
        # filtrer les valeurs non-scalaires pour l'event Pydantic
        clean = {
            k: v for k, v in payload.items() if isinstance(v, (str, int, float, bool))
        }
        ev = IotDeviceState(
            source="iot", device_id=device_id, state=clean, transport=transport
        )
        await app.state.bus.publish(STREAM_IOT_STATE, ev)
        await app.state.bus.publish_pubsub("ui.iot", ev.model_dump())

    async def on_mqtt_state(device_id: str, payload: dict) -> None:
        await emit_state(device_id, payload, "mqtt")

    async def on_serial_state(device_id: str, payload: dict) -> None:
        await emit_state(device_id, payload, "serial")

    app.state.mqtt = MQTTBridge()
    app.state.ha = HABridge()
    app.state.serial = SerialBridge(on_state=on_serial_state)
    app.state.zigbee = Z2MBridge()
    try:
        await app.state.serial.open()
    except Exception as e:
        log.warning("serial init KO (%s) — bridge désactivé", e)

    async def on_zigbee_state(device_id: str, payload: dict) -> None:
        await emit_state(device_id, payload, "mqtt")  # transport "zigbee2mqtt" mappé sur mqtt event

    async def _zigbee_subscriber():
        try:
            await app.state.zigbee.subscribe_states(on_zigbee_state)
        except Exception as e:
            log.warning("Z2M subscribe loop arrêtée: %s", e)

    app.state.zigbee_task = asyncio.create_task(_zigbee_subscriber())

    # MQTT subscribe pour tous les devices avec state_topic
    mqtt_topics: list[tuple[str, str]] = []
    for d in app.state.devices.values():
        if d["transport"] == "mqtt":
            t = d["config"].get("state_topic")
            if t:
                mqtt_topics.append((d["id"], t))
    if mqtt_topics:
        async def _mqtt_subscriber():
            try:
                await app.state.mqtt.subscribe_states(mqtt_topics, on_mqtt_state)
            except Exception as e:
                log.warning("MQTT subscribe loop arrêtée: %s", e)

        app.state.mqtt_task = asyncio.create_task(_mqtt_subscriber())

    log.info("iot service ready, %d devices", len(app.state.devices))
    yield
    if hasattr(app.state, "mqtt_task"):
        app.state.mqtt_task.cancel()
    await app.state.bus.close()


app = FastAPI(title="Jarvis IoT", version="0.1.0", lifespan=lifespan)


class CommandRequest(BaseModel):
    device_id: str
    action: str
    params: dict = {}


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "iot"}


@app.get("/devices")
async def devices() -> list[dict]:
    return list(app.state.devices.values())


@app.post("/command")
async def command(req: CommandRequest) -> dict:
    dev = app.state.devices.get(req.device_id)
    if dev is None:
        raise HTTPException(status_code=404, detail="device inconnu")
    transport = dev["transport"]
    cfg = dev["config"]

    if transport == "mqtt":
        topic = cfg["cmd_topic"]
        await app.state.mqtt.publish(topic, {"action": req.action, **req.params})
        result = {"status": "sent", "transport": "mqtt"}

    elif transport == "homeassistant":
        domain = cfg["entity_id"].split(".")[0]
        service = {"on": "turn_on", "off": "turn_off"}.get(req.action, req.action)
        await app.state.ha.call_service(domain, service, cfg["entity_id"], req.params)
        result = {"status": "sent", "transport": "homeassistant"}

    elif transport == "serial":
        await app.state.serial.send(
            cfg["port"], {"id": cfg["protocol_id"], "action": req.action, **req.params}
        )
        result = {"status": "sent", "transport": "serial"}

    elif transport == "zigbee2mqtt":
        await app.state.zigbee.command(cfg["friendly_name"], req.action, req.params)
        result = {"status": "sent", "transport": "zigbee2mqtt"}

    else:
        raise HTTPException(status_code=500, detail=f"transport inconnu: {transport}")

    # publier la commande sur le bus pour audit
    await app.state.bus.publish(
        STREAM_IOT_COMMAND,
        IotDeviceCommand(
            source="iot",
            device_id=req.device_id,
            action=req.action,
            params={
                k: v for k, v in req.params.items()
                if isinstance(v, (str, int, float, bool))
            },
            transport=transport,
        ),
    )
    return result


@app.get("/state")
async def state(device_id: str = Query(...)) -> dict:
    dev = app.state.devices.get(device_id)
    if dev is None:
        raise HTTPException(status_code=404, detail="device inconnu")
    if dev["transport"] == "homeassistant":
        return await app.state.ha.get_state(dev["config"]["entity_id"])
    return {"state": "unknown", "note": "implémentation à compléter pour ce transport"}


@app.post("/discover/zigbee")
async def discover_zigbee() -> dict:
    """Récupère la liste Z2M et upsert dans la table devices."""
    entities = await app.state.zigbee.list_devices()
    pool = await asyncpg.create_pool(
        host=os.getenv("POSTGRES_HOST", "postgres"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.getenv("POSTGRES_DB", "jarvis"),
        user=os.getenv("POSTGRES_USER", "jarvis"),
        password=os.getenv("POSTGRES_PASSWORD", ""),
        min_size=1,
        max_size=2,
    )
    inserted = 0
    try:
        async with pool.acquire() as conn:
            for e in entities:
                await conn.execute(
                    """
                    INSERT INTO devices(id, name, transport, config, requires_admin)
                    VALUES($1, $2, $3, $4::jsonb, $5)
                    ON CONFLICT (id) DO UPDATE
                       SET name = EXCLUDED.name,
                           config = EXCLUDED.config,
                           requires_admin = EXCLUDED.requires_admin
                    """,
                    e["id"],
                    e["name"],
                    e["transport"],
                    __import__("json").dumps(e["config"]),
                    e["requires_admin"],
                )
                inserted += 1
    finally:
        await pool.close()
    return {"discovered": inserted}


@app.post("/discover/ha")
async def discover_ha() -> dict:
    """Récupère toutes les entités HA et met à jour la table `devices` Postgres."""
    entities = await app.state.ha.list_entities()
    pool = await asyncpg.create_pool(
        host=os.getenv("POSTGRES_HOST", "postgres"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.getenv("POSTGRES_DB", "jarvis"),
        user=os.getenv("POSTGRES_USER", "jarvis"),
        password=os.getenv("POSTGRES_PASSWORD", ""),
        min_size=1,
        max_size=2,
    )
    inserted = 0
    try:
        async with pool.acquire() as conn:
            for e in entities:
                await conn.execute(
                    """
                    INSERT INTO devices(id, name, transport, config, requires_admin)
                    VALUES($1, $2, $3, $4::jsonb, $5)
                    ON CONFLICT (id) DO UPDATE
                       SET name = EXCLUDED.name,
                           config = EXCLUDED.config,
                           requires_admin = EXCLUDED.requires_admin
                    """,
                    e["id"],
                    e["name"],
                    e["transport"],
                    __import__("json").dumps(e["config"]),
                    e["requires_admin"],
                )
                inserted += 1
    finally:
        await pool.close()
    return {"discovered": inserted}
