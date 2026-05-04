"""Enrôlement voix-print : enregistre 5 phrases et stocke l'embedding moyen.

Usage :
    docker compose exec voice python /app/scripts/enroll_voiceprint.py \
        --user mickael --owner

Le micro doit être disponible dans le conteneur (volume `/dev/snd`).
Sinon, exécuter le script depuis l'hôte avec un Python local et `sounddevice`.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

import numpy as np

PHRASES = [
    "Jarvis, c'est moi, ton créateur.",
    "Active la sécurité de la maison ce soir à minuit.",
    "Prépare le café pour sept heures du matin.",
    "Quelle est la température dans le salon ?",
    "Lance la routine cinéma dans le salon.",
]


def record(duration_s: float, sample_rate: int = 16_000) -> bytes:
    import sounddevice as sd

    print(f"  [enregistrement {duration_s:.1f}s — parle maintenant]")
    audio = sd.rec(int(duration_s * sample_rate), samplerate=sample_rate, channels=1, dtype="int16")
    sd.wait()
    return audio.tobytes()


async def store_embedding(user: str, is_owner: bool, embedding: np.ndarray) -> None:
    import asyncpg

    pool = await asyncpg.create_pool(
        host=os.getenv("POSTGRES_HOST", "postgres"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.getenv("POSTGRES_DB", "jarvis"),
        user=os.getenv("POSTGRES_USER", "jarvis"),
        password=os.getenv("POSTGRES_PASSWORD", ""),
        min_size=1,
        max_size=1,
    )
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT id FROM users WHERE username = $1", user)
            if row is None:
                row = await conn.fetchrow(
                    "INSERT INTO users(username, is_owner) VALUES($1, $2) RETURNING id",
                    user,
                    is_owner,
                )
            user_id = row["id"]
            vec = "[" + ",".join(f"{x:.8f}" for x in embedding.tolist()) + "]"
            await conn.execute(
                """
                INSERT INTO voiceprints(user_id, embedding, sample_count)
                VALUES($1, $2::vector, $3)
                """,
                user_id,
                vec,
                len(PHRASES),
            )
            print(f"✅ voix-print enregistrée pour {user} (owner={is_owner})")
    finally:
        await pool.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", required=True)
    parser.add_argument("--owner", action="store_true")
    args = parser.parse_args()

    sys.path.insert(0, "/app")
    from app.voiceprint import VoiceprintEngine

    engine = VoiceprintEngine()
    embeddings: list[np.ndarray] = []
    for i, phrase in enumerate(PHRASES, 1):
        print(f"\nPhrase {i}/{len(PHRASES)} :")
        print(f"  → \"{phrase}\"")
        input("  Appuie sur Entrée puis lis la phrase…")
        pcm = record(4.0)
        emb = engine.embed(pcm)
        embeddings.append(emb)

    avg = np.mean(embeddings, axis=0)
    avg = avg / (np.linalg.norm(avg) + 1e-9)
    asyncio.run(store_embedding(args.user, args.owner, avg))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
