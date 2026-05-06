"""Bridge série Arduino — protocole JSON-line.

Le firmware Arduino doit lire/écrire des lignes JSON sur USB :
  → {"id":"garage_door","action":"open"}
  ← {"id":"garage_door","state":"opened","ts":1234567890}
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from collections.abc import Callable, Coroutine

import serial_asyncio

log = logging.getLogger("iot.serial")

OnState = Callable[[str, dict], Coroutine]


class SerialBridge:
    def __init__(self, on_state: OnState | None = None) -> None:
        ports_csv = os.getenv("ARDUINO_SERIAL_PORTS", "/dev/ttyUSB0")
        self.ports = [p.strip() for p in ports_csv.split(",") if p.strip()]
        self.baudrate = int(os.getenv("ARDUINO_BAUDRATE", "115200"))
        self._writers: dict[str, asyncio.StreamWriter] = {}
        self._on_state = on_state

    async def open(self) -> None:
        for port in self.ports:
            try:
                reader, writer = await serial_asyncio.open_serial_connection(
                    url=port, baudrate=self.baudrate
                )
                self._writers[port] = writer
                asyncio.create_task(self._reader_loop(port, reader))
                log.info("serial port ouvert: %s", port)
            except Exception as e:
                log.warning("port %s indispo (%s)", port, e)

    async def _reader_loop(self, port: str, reader: asyncio.StreamReader) -> None:
        try:
            while True:
                line = await reader.readline()
                if not line:
                    await asyncio.sleep(0.1)
                    continue
                try:
                    data = json.loads(line.decode("utf-8", errors="replace"))
                except Exception:
                    log.debug("serial(%s) ligne non-JSON: %r", port, line)
                    continue
                log.info("serial(%s) ← %s", port, data)
                device_id = data.get("id")
                if self._on_state and device_id:
                    await self._on_state(device_id, data)
        except Exception as e:
            log.warning("reader %s arrêté: %s", port, e)

    async def send(self, port: str, payload: dict) -> None:
        writer = self._writers.get(port)
        if writer is None:
            raise RuntimeError(f"port {port} non ouvert")
        line = (json.dumps(payload) + "\n").encode("utf-8")
        writer.write(line)
        await writer.drain()
        log.info("serial(%s) → %s", port, payload)
