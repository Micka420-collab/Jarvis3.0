"""Service IoT : routeur unifié MQTT / HA / série."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

import yaml
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from .ha_bridge import HABridge
from .mqtt_bridge import MQTTBridge
from .serial_bridge import SerialBridge

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
log = logging.getLogger("iot")

DEVICES_FILE = Path(__file__).parent / "devices.yaml"


def load_devices() -> dict[str, dict]:
    raw = yaml.safe_load(DEVICES_FILE.read_text(encoding="utf-8"))
    return {d["id"]: d for d in raw.get("devices", [])}


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.devices = load_devices()
    app.state.mqtt = MQTTBridge()
    app.state.ha = HABridge()
    app.state.serial = SerialBridge()
    try:
        await app.state.serial.open()
    except Exception as e:
        log.warning("serial init KO (%s) — bridge désactivé", e)
    log.info("iot service ready, %d devices", len(app.state.devices))
    yield


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
        return {"status": "sent", "transport": "mqtt"}

    if transport == "homeassistant":
        domain = cfg["entity_id"].split(".")[0]
        service = {"on": "turn_on", "off": "turn_off"}.get(req.action, req.action)
        await app.state.ha.call_service(domain, service, cfg["entity_id"], req.params)
        return {"status": "sent", "transport": "homeassistant"}

    if transport == "serial":
        await app.state.serial.send(
            cfg["port"], {"id": cfg["protocol_id"], "action": req.action, **req.params}
        )
        return {"status": "sent", "transport": "serial"}

    raise HTTPException(status_code=500, detail=f"transport inconnu: {transport}")


@app.get("/state")
async def state(device_id: str = Query(...)) -> dict:
    dev = app.state.devices.get(device_id)
    if dev is None:
        raise HTTPException(status_code=404, detail="device inconnu")
    if dev["transport"] == "homeassistant":
        return await app.state.ha.get_state(dev["config"]["entity_id"])
    return {"state": "unknown", "note": "implémentation à compléter pour ce transport"}
