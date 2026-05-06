"""Skill 'briefing' : résumé matinal météo + agenda + état maison + alertes.

Tool LLM `briefing_today` : rassemble en parallèle les sources et renvoie un dict
synthétique. Le LLM le résume en 3-4 phrases et le service voice le lit.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta

import httpx

from .. import Skill

log = logging.getLogger("skills.briefing")


async def _fetch_weather(city: str) -> dict:
    from .weather_skill import _now as weather_now

    try:
        return await weather_now({"city": city}, {})
    except Exception as e:
        return {"error": str(e)}


async def _fetch_calendar() -> list[dict]:
    """CalDAV : liste les événements des 24 prochaines heures.

    Configure via :
        CALDAV_URL=https://nuage.example.com/dav.php/calendars/me/perso/
        CALDAV_USER=...
        CALDAV_PASS=...
    """
    url = os.getenv("CALDAV_URL")
    if not url:
        return []
    try:
        from caldav import DAVClient  # type: ignore

        client = DAVClient(
            url=url, username=os.getenv("CALDAV_USER"), password=os.getenv("CALDAV_PASS")
        )
        principal = client.principal()
        events: list[dict] = []
        start = datetime.utcnow()
        end = start + timedelta(hours=24)
        for cal in principal.calendars():
            for ev in cal.search(start=start, end=end, event=True, expand=True):
                vobj = ev.icalendar_component
                summary = str(vobj.get("summary", ""))
                dtstart = vobj.get("dtstart")
                events.append(
                    {
                        "summary": summary,
                        "start": dtstart.dt.isoformat() if dtstart else None,
                    }
                )
        events.sort(key=lambda e: e.get("start") or "")
        return events[:10]
    except Exception as e:
        log.warning("CalDAV indisponible: %s", e)
        return []


async def _fetch_security_status() -> dict:
    try:
        async with httpx.AsyncClient(timeout=3.0) as c:
            r = await c.get("http://security:8003/status")
            return r.json()
    except Exception:
        return {"connected": False}


async def _fetch_iot_summary() -> dict:
    try:
        async with httpx.AsyncClient(timeout=3.0) as c:
            r = await c.get("http://iot:8002/devices")
            devs = r.json()
        return {
            "total": len(devs),
            "by_transport": {
                t: sum(1 for d in devs if d.get("transport") == t)
                for t in {"mqtt", "homeassistant", "serial", "zigbee2mqtt"}
            },
        }
    except Exception:
        return {"total": 0}


async def _briefing(args: dict, ctx: dict) -> dict:
    city = args.get("city") or os.getenv("BRIEFING_CITY", "Paris")
    weather, agenda, sec, iot = await asyncio.gather(
        _fetch_weather(city),
        _fetch_calendar(),
        _fetch_security_status(),
        _fetch_iot_summary(),
    )
    return {
        "weather": weather,
        "agenda": agenda,
        "security": {
            "connected": sec.get("connected"),
            "last_alert": sec.get("last_alert"),
        },
        "iot": iot,
    }


def register(s: Skill) -> None:
    s.name = "briefing"
    s.description = "Briefing matinal : météo, agenda, sécurité, état maison"
    s.tool(
        name="briefing_today",
        description="Récupère un résumé agrégé de la journée à venir (météo, agenda, alertes, état maison).",
        input_schema={
            "type": "object",
            "properties": {"city": {"type": "string"}},
        },
        handler=_briefing,
    )
