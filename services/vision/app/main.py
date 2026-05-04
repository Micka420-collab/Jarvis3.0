"""Service vision : événements Frigate → reconnaissance faciale → bus."""

from __future__ import annotations

import asyncio
import logging
import sys
import uuid
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from _shared.bus import EventBus  # noqa: E402
from _shared.events import (  # noqa: E402
    STREAM_INTENT_RESPONSE,
    STREAM_VISION_FACE,
    IntentResponse,
    VisionFaceRecognized,
)

from .face_recog import FaceRecognizer  # noqa: E402
from .frigate_consumer import FrigateConsumer  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
log = logging.getLogger("vision")


async def main() -> None:
    bus = EventBus()
    await bus.connect()
    try:
        face = FaceRecognizer()
    except Exception as e:
        log.warning("face recognizer indisponible (%s) — démo désactivée", e)
        face = None

    async def on_frame(camera: str, frame: np.ndarray) -> None:
        if face is None:
            return
        results = face.identify(frame)
        for name, sim, bbox in results:
            ev = VisionFaceRecognized(
                source="vision",
                camera=camera,
                name=name,
                confidence=sim,
                bbox=bbox,
            )
            await bus.publish(STREAM_VISION_FACE, ev)
            await bus.publish_pubsub("ui.vision", ev.model_dump())
            if name:
                # salutation contextuelle
                await bus.publish(
                    STREAM_INTENT_RESPONSE,
                    IntentResponse(
                        source="vision",
                        session_id=str(uuid.uuid4()),
                        text=f"Bonjour {name}.",
                        proactive=True,
                    ),
                )

    consumer = FrigateConsumer(on_frame)
    await consumer.run()


if __name__ == "__main__":
    asyncio.run(main())
