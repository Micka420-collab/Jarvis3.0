"""Skill 'time' : heure courante, date, fuseau."""

from __future__ import annotations

import datetime as dt
import zoneinfo

from .. import Skill


async def _now(args: dict, ctx: dict) -> dict:
    tz_name = args.get("timezone") or "Europe/Paris"
    try:
        tz = zoneinfo.ZoneInfo(tz_name)
    except Exception:
        tz = zoneinfo.ZoneInfo("Europe/Paris")
    now = dt.datetime.now(tz)
    return {
        "iso": now.isoformat(),
        "weekday": now.strftime("%A"),
        "human_fr": now.strftime("%H:%M, %A %d %B %Y"),
        "tz": str(tz),
    }


def register(s: Skill) -> None:
    s.name = "time"
    s.description = "Heure et date courantes"
    s.tool(
        name="time_now",
        description="Renvoie l'heure et la date courantes dans un fuseau donné.",
        input_schema={
            "type": "object",
            "properties": {
                "timezone": {"type": "string", "description": "ex: Europe/Paris"}
            },
        },
        handler=_now,
    )
