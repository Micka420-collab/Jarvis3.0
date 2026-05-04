"""Service 'learning' :

1. Observe le bus (`iot.device.commanded`, `iot.device.state`) et persiste les
   actions dans la table `observations`.
2. Périodiquement (cron toutes les heures), lance la détection de patterns :
   actions répétées (≥ N fois sur ≥ X jours différents, à la même heure ±15 min).
3. Quand un pattern stable est détecté ET pas encore en routine, on insère une
   routine `learned=true` désactivée et on émet un IntentResponse proactif :
   « j'ai remarqué que tu allumes la cuisine à 7h chaque matin, tu veux que je
   le fasse automatiquement ? ». L'owner active via tool routines_enable.

4. Worker simulation de présence : si presence_state.simulate_presence est ON,
   rejoue des actions IoT typiques avec randomisation toutes les ~30 minutes
   pendant la nuit (heures où la maison habituellement éclairée).
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import logging
import os
import random
import sys
import uuid
from pathlib import Path

import asyncpg
import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from _shared.bus import EventBus  # noqa: E402
from _shared.events import (  # noqa: E402
    STREAM_INTENT_RESPONSE,
    STREAM_IOT_COMMAND,
    IntentResponse,
    IotDeviceCommand,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
log = logging.getLogger("learning")

PATTERN_MIN_SAMPLES = int(os.getenv("LEARN_PATTERN_MIN_SAMPLES", "5"))
PATTERN_MIN_DAYS = int(os.getenv("LEARN_PATTERN_MIN_DAYS", "3"))
PATTERN_HOUR_TOLERANCE = 0  # heure exacte (le bucket est par heure pleine)
LEARN_INTERVAL_S = int(os.getenv("LEARN_INTERVAL_S", "3600"))
SIMULATION_INTERVAL_S = int(os.getenv("PRESENCE_SIM_INTERVAL_S", "1800"))


async def make_pool() -> asyncpg.Pool:
    return await asyncpg.create_pool(
        host=os.getenv("POSTGRES_HOST", "postgres"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.getenv("POSTGRES_DB", "jarvis"),
        user=os.getenv("POSTGRES_USER", "jarvis"),
        password=os.getenv("POSTGRES_PASSWORD", ""),
        min_size=1,
        max_size=3,
    )


# ---------------------------------------------------------------------------
# 1. Observation des commandes IoT
# ---------------------------------------------------------------------------


async def observe_iot_commands(bus: EventBus, pool: asyncpg.Pool) -> None:
    async for _id, ev in bus.consume(
        STREAM_IOT_COMMAND, "learning-obs", "learning-obs-1", IotDeviceCommand
    ):
        try:
            now = dt.datetime.now()
            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO observations(kind, device_id, action, metadata, weekday, hour)
                    VALUES('iot_command', $1, $2, $3::jsonb, $4, $5)
                    """,
                    ev.device_id,
                    ev.action,
                    json.dumps({"transport": ev.transport, "params": ev.params}),
                    now.weekday(),
                    now.hour,
                )
        except Exception as e:
            log.warning("observe failed: %s", e)


# ---------------------------------------------------------------------------
# 2. Pattern detection
# ---------------------------------------------------------------------------


async def detect_patterns(bus: EventBus, pool: asyncpg.Pool) -> None:
    """Cherche les buckets (device, action, hour) qui ont été observés ≥ N fois
    sur ≥ X jours distincts dans les 30 derniers jours."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT device_id, action, hour,
                   COUNT(*) AS samples,
                   COUNT(DISTINCT date_trunc('day', ts)) AS distinct_days
              FROM observations
             WHERE kind = 'iot_command'
               AND ts > NOW() - INTERVAL '30 days'
             GROUP BY device_id, action, hour
            HAVING COUNT(*) >= $1 AND COUNT(DISTINCT date_trunc('day', ts)) >= $2
            """,
            PATTERN_MIN_SAMPLES,
            PATTERN_MIN_DAYS,
        )
        if not rows:
            return
        for r in rows:
            # vérifie si une routine équivalente existe déjà
            existing = await conn.fetchrow(
                """
                SELECT id FROM routines
                 WHERE trigger->>'kind' = 'time'
                   AND (trigger->'spec'->>'hour')::int = $1
                   AND actions::text LIKE $2
                """,
                r["hour"],
                f'%"{r["device_id"]}"%',
            )
            if existing:
                continue
            confidence = min(1.0, r["samples"] / 10.0)
            name = f"Auto: {r['device_id']} {r['action']} à {r['hour']:02d}h"
            trigger = {"kind": "time", "spec": {"hour": int(r["hour"])}}
            actions = [
                {"tool": "iot_command", "args": {"device_id": r["device_id"], "action": r["action"]}}
            ]
            routine_id = await conn.fetchval(
                """
                INSERT INTO routines(name, trigger, actions, enabled, learned, confidence)
                VALUES($1, $2::jsonb, $3::jsonb, FALSE, TRUE, $4)
                RETURNING id
                """,
                name,
                json.dumps(trigger),
                json.dumps(actions),
                confidence,
            )
            log.info("nouvelle routine apprise: %s id=%s conf=%.2f", name, routine_id, confidence)
            # propose à l'owner via TTS proactif
            await bus.publish(
                STREAM_INTENT_RESPONSE,
                IntentResponse(
                    source="learning",
                    session_id=str(uuid.uuid4()),
                    text=(
                        f"J'ai remarqué que tu déclenches '{r['device_id']}' "
                        f"({r['action']}) vers {int(r['hour']):02d}h, "
                        f"{int(r['samples'])} fois sur {int(r['distinct_days'])} jours. "
                        f"Veux-tu que je le fasse automatiquement ?"
                    ),
                    proactive=True,
                ),
            )


async def learning_loop(bus: EventBus, pool: asyncpg.Pool) -> None:
    while True:
        try:
            await detect_patterns(bus, pool)
        except Exception as e:
            log.exception("detect_patterns failed: %s", e)
        await asyncio.sleep(LEARN_INTERVAL_S)


# ---------------------------------------------------------------------------
# 3. Routines temporelles : déclenche les routines `enabled=true` à l'heure prévue
# ---------------------------------------------------------------------------


async def schedule_loop(pool: asyncpg.Pool) -> None:
    """Toutes les minutes, exécute les routines time-triggered dont l'heure correspond."""
    last_min = -1
    while True:
        now = dt.datetime.now()
        if now.minute != last_min:
            last_min = now.minute
            try:
                async with pool.acquire() as conn:
                    rows = await conn.fetch(
                        """
                        SELECT id, name, actions
                          FROM routines
                         WHERE enabled = TRUE
                           AND trigger->>'kind' = 'time'
                           AND (trigger->'spec'->>'hour')::int = $1
                           AND COALESCE((trigger->'spec'->>'minute')::int, 0) = $2
                        """,
                        now.hour,
                        now.minute,
                    )
                for r in rows:
                    await _run_actions(r["actions"])
                    async with pool.acquire() as conn:
                        await conn.execute(
                            "UPDATE routines SET last_run_at = NOW() WHERE id = $1", r["id"]
                        )
                    log.info("routine '%s' exécutée", r["name"])
            except Exception as e:
                log.warning("schedule loop error: %s", e)
        await asyncio.sleep(15)


async def _run_actions(actions_json) -> None:
    actions = json.loads(actions_json) if isinstance(actions_json, str) else actions_json
    async with httpx.AsyncClient(timeout=5.0) as client:
        for a in actions:
            tool = a.get("tool")
            args = a.get("args") or {}
            if tool == "iot_command":
                try:
                    await client.post("http://iot:8002/command", json=args)
                except Exception as e:
                    log.warning("action iot KO: %s", e)


# ---------------------------------------------------------------------------
# 4. Présence simulée : rejoue actions typiques pendant que owner absent
# ---------------------------------------------------------------------------


async def presence_simulation_loop(pool: asyncpg.Pool) -> None:
    while True:
        try:
            async with pool.acquire() as conn:
                state = await conn.fetchrow(
                    "SELECT away, simulate_presence, away_until FROM presence_state WHERE id = 1"
                )
            if not state or not (state["away"] and state["simulate_presence"]):
                await asyncio.sleep(SIMULATION_INTERVAL_S)
                continue
            if state["away_until"] and dt.datetime.now(dt.timezone.utc) > state["away_until"]:
                async with pool.acquire() as conn:
                    await conn.execute(
                        "UPDATE presence_state SET away = FALSE, simulate_presence = FALSE WHERE id = 1"
                    )
                continue

            # heure typique d'éclairage : 18-23h
            hour = dt.datetime.now().hour
            if not 17 <= hour <= 23:
                await asyncio.sleep(SIMULATION_INTERVAL_S)
                continue

            # Choisit une action typique parmi les observations historiques
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT device_id, action
                      FROM observations
                     WHERE kind = 'iot_command'
                       AND hour BETWEEN 17 AND 23
                  ORDER BY random()
                     LIMIT 1
                    """
                )
            if row is None:
                await asyncio.sleep(SIMULATION_INTERVAL_S)
                continue

            # ajoute une jitter de 0..15 min avant exécution
            await asyncio.sleep(random.randint(0, 15 * 60))
            log.info("présence simulée: %s %s", row["device_id"], row["action"])
            await _run_actions(
                json.dumps([{"tool": "iot_command",
                             "args": {"device_id": row["device_id"], "action": row["action"]}}])
            )
        except Exception as e:
            log.warning("presence sim error: %s", e)
        await asyncio.sleep(SIMULATION_INTERVAL_S)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main() -> None:
    bus = EventBus()
    await bus.connect()
    pool = await make_pool()
    log.info("learning service ready (interval=%ss)", LEARN_INTERVAL_S)
    await asyncio.gather(
        observe_iot_commands(bus, pool),
        learning_loop(bus, pool),
        schedule_loop(pool),
        presence_simulation_loop(pool),
    )


if __name__ == "__main__":
    asyncio.run(main())
