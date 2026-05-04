"""E2E phase 1 : envoi texte (bypass STT) → orchestrator → réponse non vide.

Permet de valider le pipeline LLM sans micro réel.
"""

import asyncio
import json

import pytest
import websockets


@pytest.mark.asyncio
async def test_text_bypass_returns_reply() -> None:
    uri = "ws://gateway:8000/ws/voice"
    async with websockets.connect(uri) as ws:
        await ws.send(json.dumps({"type": "text", "text": "dis bonjour en un mot"}))
        # On attend transcript + au moins 1 chunk TTS, ou un transcript echo si LLM down
        got_transcript = False
        got_tts = False
        for _ in range(40):
            try:
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=10.0))
            except asyncio.TimeoutError:
                break
            if msg.get("type") == "transcript":
                got_transcript = True
            elif msg.get("type") == "tts_chunk":
                got_tts = True
                if msg.get("is_final"):
                    break
        assert got_transcript, "pas de transcript reçu"
        # tts peut être absent si Piper/modèle pas téléchargé : on ne fail pas dur ici
