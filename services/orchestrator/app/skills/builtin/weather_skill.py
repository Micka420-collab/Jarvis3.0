"""Skill 'weather' : météo via Open-Meteo (gratuit, sans clé API)."""

from __future__ import annotations

import logging

import httpx

from .. import Skill

log = logging.getLogger("skills.weather")

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


async def _geocode(city: str) -> tuple[float, float, str] | None:
    async with httpx.AsyncClient(timeout=5.0) as client:
        r = await client.get(GEOCODE_URL, params={"name": city, "count": 1, "language": "fr"})
        r.raise_for_status()
        data = r.json()
    if not data.get("results"):
        return None
    res = data["results"][0]
    return res["latitude"], res["longitude"], res.get("name", city)


async def _now(args: dict, ctx: dict) -> dict:
    city = args.get("city") or "Paris"
    geo = await _geocode(city)
    if geo is None:
        return {"error": f"ville '{city}' inconnue"}
    lat, lon, label = geo
    async with httpx.AsyncClient(timeout=5.0) as client:
        r = await client.get(
            FORECAST_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,wind_speed_10m,relative_humidity_2m,weather_code",
                "daily": "temperature_2m_max,temperature_2m_min,weather_code,precipitation_sum",
                "forecast_days": 1,
                "timezone": "auto",
            },
        )
        r.raise_for_status()
        data = r.json()
    cur = data.get("current", {})
    daily = data.get("daily", {})
    return {
        "city": label,
        "now": {
            "temp_c": cur.get("temperature_2m"),
            "humidity": cur.get("relative_humidity_2m"),
            "wind_kmh": cur.get("wind_speed_10m"),
            "weather_code": cur.get("weather_code"),
        },
        "today": {
            "tmax": (daily.get("temperature_2m_max") or [None])[0],
            "tmin": (daily.get("temperature_2m_min") or [None])[0],
            "rain_mm": (daily.get("precipitation_sum") or [None])[0],
            "weather_code": (daily.get("weather_code") or [None])[0],
        },
    }


def register(s: Skill) -> None:
    s.name = "weather"
    s.description = "Météo actuelle et prévisions du jour"
    s.tool(
        name="weather_now",
        description="Renvoie la météo actuelle et le résumé du jour pour une ville.",
        input_schema={
            "type": "object",
            "properties": {"city": {"type": "string"}},
        },
        handler=_now,
    )
