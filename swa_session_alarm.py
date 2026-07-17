#!/usr/bin/env python3
"""SWA V603.2c single-active-spot Telegram background alarm.

The alarm is fully standalone in GitHub Actions. It does not depend on a
Cloudflare /api route, KV, D1, R2, or an open PWA. State is stored in a small
JSON file committed by the workflow.
"""

from __future__ import annotations

import html
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

APP_URL = "https://lively-brook-24bf.jaapzuijderduijn.workers.dev/"
STATUS_FILE = Path("swa_session_alarm_status.json")
HTTP_TIMEOUT_SECONDS = 45
AMSTERDAM = ZoneInfo("Europe/Amsterdam")

SPOTS: dict[str, dict[str, Any]] = {
    "makkum": {"name": "Makkum", "water": "IJsselmeer", "lat": 53.0530, "lon": 5.3756},
    "stavoren": {"name": "Stavoren", "water": "IJsselmeer", "lat": 52.8860, "lon": 5.3630},
    "schokkerhaven": {"name": "Schokkerhaven", "water": "Ketelmeer", "lat": 52.6380, "lon": 5.7560},
    "urk": {"name": "Urk", "water": "IJsselmeer", "lat": 52.6620, "lon": 5.6040},
    "veluwemeer": {"name": "Veluwemeer", "water": "Veluwemeer", "lat": 52.3970, "lon": 5.6350},
    "brouwersdam": {"name": "Brouwersdam", "water": "kust", "lat": 51.7480, "lon": 3.8850},
}
SPOT_ALIASES = {
    "makkum": "makkum",
    "stavoren": "stavoren",
    "schokkerhaven": "schokkerhaven",
    "schokker": "schokkerhaven",
    "schokkerheaven": "schokkerhaven",
    "urk": "urk",
    "veluwemeer": "veluwemeer",
    "veluwe": "veluwemeer",
    "brouwersdam": "brouwersdam",
    "brouwers": "brouwersdam",
    "bdam": "brouwersdam",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def default_status() -> dict[str, Any]:
    return {
        "version": 3,
        "enabled": False,
        "active_spot": None,
        "telegram_update_offset": 0,
        "spots": {},
    }


def load_status() -> dict[str, Any]:
    status = default_status()
    if not STATUS_FILE.exists():
        return status
    try:
        loaded = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise ValueError("status is not an object")
        status.update(loaded)
        if not isinstance(status.get("spots"), dict):
            status["spots"] = {}
        if status.get("active_spot") not in SPOTS:
            status["active_spot"] = None
            status["enabled"] = False
        status["telegram_update_offset"] = int(status.get("telegram_update_offset") or 0)
        status["version"] = 3
        return status
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Waarschuwing: statusbestand ongeldig; begin veilig gestopt: {exc}")
        return status


def save_status(status: dict[str, Any]) -> None:
    status["version"] = 3
    status["updated_at"] = utc_now_iso()
    tmp = STATUS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(status, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(STATUS_FILE)


def request_json(
    url: str,
    *,
    data: bytes | None = None,
    headers: dict[str, str] | None = None,
    attempts: int = 3,
) -> Any:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            request_headers = {
                "User-Agent": "SWA-Telegram-Single-Spot/603.2c",
                "Accept": "application/json",
                "Cache-Control": "no-cache",
            }
            if headers:
                request_headers.update(headers)
            req = urllib.request.Request(url, data=data, headers=request_headers)
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_SECONDS) as response:
                payload = response.read().decode("utf-8")
            return json.loads(payload)
        except (
            urllib.error.URLError,
            urllib.error.HTTPError,
            TimeoutError,
            ValueError,
            json.JSONDecodeError,
        ) as exc:
            last_error = exc
            if attempt < attempts:
                time.sleep(2 ** (attempt - 1))
    raise RuntimeError(f"HTTP-aanvraag mislukt: {last_error}")


def telegram_credentials() -> tuple[str, str]:
    token = os.environ.get("TELEGRAM_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        raise RuntimeError("GitHub secrets TELEGRAM_TOKEN en TELEGRAM_CHAT_ID ontbreken")
    return token, chat_id


def telegram_api(method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    token, _ = telegram_credentials()
    endpoint = f"https://api.telegram.org/bot{token}/{method}"
    encoded = urllib.parse.urlencode(params or {}).encode("utf-8")
    result = request_json(
        endpoint,
        data=encoded,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    if not isinstance(result, dict) or not result.get("ok"):
        raise RuntimeError(f"Telegram {method} wees aanvraag af: {result}")
    return result


def send_telegram(message: str) -> None:
    _, chat_id = telegram_credentials()
    telegram_api(
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": "true",
        },
    )


def get_updates(offset: int) -> list[dict[str, Any]]:
    result = telegram_api(
        "getUpdates",
        {
            "offset": str(max(0, offset)),
            "limit": "100",
            "timeout": "0",
            "allowed_updates": json.dumps(["message"]),
        },
    ).get("result")
    return [item for item in (result or []) if isinstance(item, dict)]


def normalize_spot(value: str) -> str | None:
    key = re.sub(r"[^a-z0-9]", "", value.strip().lower())
    return SPOT_ALIASES.get(key)


def split_command(text: str) -> tuple[str, str]:
    cleaned = text.strip()
    if not cleaned.startswith("/"):
        return "", ""
    first, _, rest = cleaned.partition(" ")
    command = first.split("@", 1)[0].lower()
    return command, rest.strip()


def spot_title(spot_id: str | None) -> str:
    if not spot_id or spot_id not in SPOTS:
        return "geen"
    spot = SPOTS[spot_id]
    return f"{spot['name']} · {spot['water']}"


def status_message(status: dict[str, Any]) -> str:
    active = status.get("active_spot")
    if not status.get("enabled") or active not in SPOTS:
        return (
            "⏸ <b>SWA sessiealarm staat uit</b>\n\n"
            "Kies één spot met bijvoorbeeld <code>/spot makkum</code>."
        )
    return (
        "✅ <b>SWA volgt precies één spot</b>\n\n"
        f"Actief: <b>{html.escape(spot_title(str(active)))}</b>\n"
        "Controle: ongeveer iedere 10 minuten\n"
        "De PWA mag gesloten zijn."
    )


def help_message() -> str:
    return (
        "🏄 <b>SWA Telegramcommando’s</b>\n\n"
        "<code>/spot makkum</code>\n"
        "<code>/spot stavoren</code>\n"
        "<code>/spot schokkerhaven</code>\n"
        "<code>/spot urk</code>\n"
        "<code>/spot veluwemeer</code>\n"
        "<code>/spot brouwersdam</code>\n\n"
        "<code>/spot</code> — toon actieve spot\n"
        "<code>/test</code> — testmelding actieve spot\n"
        "<code>/stop</code> — stop alle sessiealarmen\n"
        "<code>/help</code> — toon deze uitleg"
    )


def apply_command(text: str, status: dict[str, Any], *, send_reply: bool = True) -> dict[str, bool]:
    command, arg = split_command(text)
    result = {"changed": False, "test_requested": False}
    reply: str | None = None

    if command == "/start":
        if arg.lower().startswith("spot_"):
            command, arg = "/spot", arg[5:]
        else:
            reply = help_message()
    if command == "/status":
        command = "/spot"

    if command == "/spot":
        if not arg:
            reply = status_message(status)
        else:
            spot_id = normalize_spot(arg)
            if not spot_id:
                reply = "❌ Onbekende spot.\n\n" + help_message()
            else:
                status["active_spot"] = spot_id
                status["enabled"] = True
                result["changed"] = True
                reply = (
                    "✅ <b>SWA volgt nu alleen "
                    + html.escape(spot_title(spot_id))
                    + "</b>\n\nAndere spots geven geen Telegram-sessiealarm."
                )
    elif command == "/stop":
        status["enabled"] = False
        result["changed"] = True
        reply = "⏸ <b>SWA sessiealarm gestopt</b>\n\nEr wordt nu geen enkele spot gevolgd."
    elif command == "/test":
        if status.get("active_spot") not in SPOTS:
            reply = "❌ Kies eerst een spot, bijvoorbeeld <code>/spot makkum</code>."
        else:
            result["test_requested"] = True
            reply = "🧪 Test voor <b>" + html.escape(spot_title(str(status["active_spot"]))) + "</b> wordt uitgevoerd."
    elif command == "/help":
        reply = help_message()
    elif command and reply is None:
        reply = "❓ Onbekend commando.\n\n" + help_message()

    if send_reply and reply:
        send_telegram(reply)
    return result


def process_telegram_updates(status: dict[str, Any]) -> bool:
    _, allowed_chat_id = telegram_credentials()
    offset = int(status.get("telegram_update_offset") or 0)
    updates = get_updates(offset)
    test_requested = False
    for update in updates:
        update_id = int(update.get("update_id") or 0)
        status["telegram_update_offset"] = max(int(status.get("telegram_update_offset") or 0), update_id + 1)
        message = update.get("message") or {}
        chat = message.get("chat") or {}
        if str(chat.get("id")) != allowed_chat_id:
            continue
        text = message.get("text")
        if not isinstance(text, str) or not text.strip().startswith("/"):
            continue
        outcome = apply_command(text, status, send_reply=True)
        test_requested = test_requested or outcome["test_requested"]
    return test_requested


def as_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def parse_utc_time(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z") or re.search(r"[+-]\d\d:?\d\d$", text):
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)
    return datetime.fromisoformat(text).replace(tzinfo=timezone.utc)


def nearest_time_index(times: list[str], now: datetime | None = None) -> int:
    target = now or datetime.now(timezone.utc)
    best_index = 0
    best_seconds = float("inf")
    for index, value in enumerate(times):
        try:
            seconds = abs((parse_utc_time(str(value)) - target).total_seconds())
        except (ValueError, TypeError):
            continue
        if seconds < best_seconds:
            best_seconds = seconds
            best_index = index
    return best_index


def compass(degrees: float | None) -> str | None:
    if degrees is None:
        return None
    labels = ["N", "NNO", "NO", "ONO", "O", "OZO", "ZO", "ZZO", "Z", "ZZW", "ZW", "WZW", "W", "WNW", "NW", "NNW"]
    return labels[round((degrees % 360) / 22.5) % 16]


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return 2 * radius * math.asin(min(1.0, math.sqrt(a)))


def bearing_degrees(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlon = math.radians(lon2 - lon1)
    y = math.sin(dlon) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dlon)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def direction_difference(a: float, b: float) -> float:
    diff = abs((a % 360) - (b % 360))
    return 360 - diff if diff > 180 else diff


def fetch_pressure_series(lat: float, lon: float) -> tuple[list[str], list[float | None]]:
    params = urllib.parse.urlencode(
        {
            "latitude": lat,
            "longitude": lon,
            "hourly": "surface_pressure",
            "past_days": 1,
            "forecast_days": 1,
            "timezone": "UTC",
            "models": "best_match",
        }
    )
    data = request_json("https://api.open-meteo.com/v1/forecast?" + params)
    hourly = data.get("hourly") if isinstance(data, dict) else None
    if not isinstance(hourly, dict):
        raise RuntimeError("Open-Meteo luchtdrukpayload ontbreekt")
    times = hourly.get("time") or []
    values = [as_float(v) for v in (hourly.get("surface_pressure") or [])]
    if not times or not values:
        raise RuntimeError("Open-Meteo luchtdrukwaarden ontbreken")
    return [str(t) for t in times], values


def gradient_signal() -> dict[str, Any]:
    west_times, west_pressure = fetch_pressure_series(51.44, 3.60)
    east_times, east_pressure = fetch_pressure_series(53.20, 7.15)
    index_west = nearest_time_index(west_times)
    index_east = nearest_time_index(east_times)
    ago_west = max(0, index_west - 3)
    ago_east = max(0, index_east - 3)
    now_west = west_pressure[index_west]
    now_east = east_pressure[index_east]
    old_west = west_pressure[ago_west]
    old_east = east_pressure[ago_east]
    if now_west is None or now_east is None:
        raise RuntimeError("Luchtdrukgradiënt heeft geen actuele waarden")
    current = now_west - now_east
    magnitude = abs(current)
    trend: int | None = None
    change_3h: float | None = None
    if old_west is not None and old_east is not None:
        old_magnitude = abs(old_west - old_east)
        change_3h = magnitude - old_magnitude
        trend = 1 if change_3h > 0.4 else (-1 if change_3h < -0.4 else 0)
    return {
        "ok": True,
        "magnitude": round(magnitude, 1),
        "trend": trend,
        "change3h": round(change_3h, 1) if change_3h is not None else None,
        "good": magnitude >= 4.0 or trend == 1,
        "source": "Open-Meteo luchtdruk",
    }


def buienradar_stations() -> list[dict[str, Any]]:
    data = request_json("https://data.buienradar.nl/2.0/feed/json")
    stations = (((data or {}).get("actual") or {}).get("stationmeasurements") or []) if isinstance(data, dict) else []
    valid: list[dict[str, Any]] = []
    for station in stations:
        if not isinstance(station, dict):
            continue
        lat = as_float(station.get("lat") or station.get("latitude"))
        lon = as_float(station.get("lon") or station.get("longitude"))
        wind_ms = as_float(station.get("windspeed"))
        if lat is None or lon is None or wind_ms is None:
            continue
        if abs(lat) < 0.0001 and abs(lon) < 0.0001:
            continue
        valid.append(station)
    if not valid:
        raise RuntimeError("Buienradar heeft geen geldige stations")
    return valid


def find_upwind_station(stations: list[dict[str, Any]], spot: dict[str, Any], wind_direction: float | None) -> dict[str, Any] | None:
    if wind_direction is None:
        return None
    best: dict[str, Any] | None = None
    for station in stations:
        lat = as_float(station.get("lat") or station.get("latitude"))
        lon = as_float(station.get("lon") or station.get("longitude"))
        wind_ms = as_float(station.get("windspeed"))
        if lat is None or lon is None or wind_ms is None:
            continue
        distance = haversine_km(float(spot["lat"]), float(spot["lon"]), lat, lon)
        if distance < 15 or distance > 130:
            continue
        diff = direction_difference(bearing_degrees(float(spot["lat"]), float(spot["lon"]), lat, lon), wind_direction)
        if diff > 45:
            continue
        score = diff + distance * 0.25
        if best is None or score < float(best["score"]):
            gust_ms = as_float(station.get("windgusts"))
            best = {
                "station": str(station.get("stationname") or station.get("regio") or "Meetstation").replace("Meetstation ", ""),
                "distanceKm": round(distance),
                "windKt": round(wind_ms * 1.94384),
                "gustKt": round(gust_ms * 1.94384) if gust_ms is not None else None,
                "score": round(score, 1),
                "source": "Buienradar meetstation",
            }
    return best


def spot_forecast(spot: dict[str, Any]) -> dict[str, Any]:
    params = urllib.parse.urlencode(
        {
            "latitude": spot["lat"],
            "longitude": spot["lon"],
            "hourly": "wind_speed_10m,wind_gusts_10m,wind_direction_10m",
            "wind_speed_unit": "kn",
            "timezone": "UTC",
            "past_hours": 1,
            "forecast_days": 2,
            "models": "best_match",
        }
    )
    data = request_json("https://api.open-meteo.com/v1/forecast?" + params)
    hourly = data.get("hourly") if isinstance(data, dict) else None
    if not isinstance(hourly, dict):
        raise RuntimeError("Open-Meteo windverwachting ontbreekt")
    times = [str(t) for t in (hourly.get("time") or [])]
    speeds = hourly.get("wind_speed_10m") or []
    gusts = hourly.get("wind_gusts_10m") or []
    directions = hourly.get("wind_direction_10m") or []
    if not times or not speeds:
        raise RuntimeError("Open-Meteo windwaarden ontbreken")
    start = nearest_time_index(times)
    peak: dict[str, Any] | None = None
    for index in range(start, min(start + 12, len(times))):
        wind = as_float(speeds[index] if index < len(speeds) else None)
        if wind is None:
            continue
        if peak is None or wind > float(peak["windKt"]):
            moment = parse_utc_time(times[index])
            local = moment.astimezone(AMSTERDAM)
            direction = as_float(directions[index] if index < len(directions) else None)
            gust = as_float(gusts[index] if index < len(gusts) else None)
            peak = {
                "windKt": round(wind, 1),
                "gustKt": round(gust, 1) if gust is not None else None,
                "dirDeg": direction % 360 if direction is not None else None,
                "direction": compass(direction),
                "timeUtc": moment.isoformat().replace("+00:00", "Z"),
                "localDate": local.strftime("%Y-%m-%d"),
                "localTime": local.strftime("%H:%M"),
            }
    current_direction = as_float(directions[start] if start < len(directions) else None)
    return {
        "currentDirectionDeg": current_direction % 360 if current_direction is not None else None,
        "currentDirection": compass(current_direction),
        "peak": peak,
        "source": "Open-Meteo best_match",
    }


def spot_ensemble(spot: dict[str, Any]) -> dict[str, Any]:
    params = urllib.parse.urlencode(
        {
            "latitude": spot["lat"],
            "longitude": spot["lon"],
            "hourly": "wind_speed_10m",
            "wind_speed_unit": "kn",
            "timezone": "UTC",
            "forecast_days": 1,
            "models": "ecmwf_ifs025",
        }
    )
    data = request_json("https://ensemble-api.open-meteo.com/v1/ensemble?" + params)
    hourly = data.get("hourly") if isinstance(data, dict) else None
    if not isinstance(hourly, dict):
        raise RuntimeError("ECMWF-ensemble ontbreekt")
    times = [str(t) for t in (hourly.get("time") or [])]
    keys = [key for key in hourly if key.startswith("wind_speed_10m_member")]
    if not times or not keys:
        raise RuntimeError("ECMWF-ensembleleden ontbreken")
    start = nearest_time_index(times)
    best_pct = -1
    best_time: datetime | None = None
    for index in range(start, min(start + 12, len(times))):
        values = [as_float((hourly.get(key) or [])[index] if index < len(hourly.get(key) or []) else None) for key in keys]
        valid = [value for value in values if value is not None]
        if not valid:
            continue
        percentage = round(100 * sum(1 for value in valid if value >= 15.0) / len(valid))
        if percentage > best_pct:
            best_pct = percentage
            best_time = parse_utc_time(times[index])
    if best_pct < 0:
        raise RuntimeError("ECMWF-ensemble heeft geen geldige waarden")
    local = best_time.astimezone(AMSTERDAM) if best_time else datetime.now(AMSTERDAM)
    return {
        "probabilityPct": best_pct,
        "timeUtc": best_time.isoformat().replace("+00:00", "Z") if best_time else None,
        "localDate": local.strftime("%Y-%m-%d"),
        "localTime": local.strftime("%H:%M"),
        "memberCount": len(keys),
        "thresholdKt": 15,
        "source": "ECMWF ensemble",
    }


def evaluate_spot(spot_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    spot_config = SPOTS[spot_id]
    errors: list[str] = []
    gradient: dict[str, Any] | None = None
    forecast: dict[str, Any] | None = None
    ensemble: dict[str, Any] | None = None
    stations: list[dict[str, Any]] = []

    try:
        gradient = gradient_signal()
    except Exception as exc:  # source failures may never break status persistence
        errors.append(f"gradient: {exc}")
    try:
        forecast = spot_forecast(spot_config)
    except Exception as exc:
        errors.append(f"forecast: {exc}")
    try:
        ensemble = spot_ensemble(spot_config)
    except Exception as exc:
        errors.append(f"ensemble: {exc}")
    try:
        stations = buienradar_stations()
    except Exception as exc:
        errors.append(f"stations: {exc}")

    upwind = find_upwind_station(stations, spot_config, (forecast or {}).get("currentDirectionDeg")) if forecast else None
    upwind_good = bool(upwind and float(upwind.get("windKt") or 0) >= 15)
    ensemble_good = bool(ensemble and float(ensemble.get("probabilityPct") or 0) >= 60)
    gradient_good = bool(gradient and gradient.get("good"))
    trigger = gradient_good and (upwind_good or ensemble_good)

    now_local = datetime.now(AMSTERDAM)
    event_date = (
        (ensemble or {}).get("localDate")
        or (((forecast or {}).get("peak") or {}).get("localDate"))
        or now_local.strftime("%Y-%m-%d")
    )
    reasons: list[str] = []
    if gradient_good:
        reasons.append("drukgradiënt neemt toe" if gradient and gradient.get("trend") == 1 else "sterke drukgradiënt")
    if upwind_good and upwind:
        reasons.append(f"bovenwinds {upwind['windKt']} kt")
    if ensemble_good and ensemble:
        reasons.append(f"{ensemble['probabilityPct']}% ensemblekans")

    result = {
        "id": spot_id,
        "name": spot_config["name"],
        "water": spot_config["water"],
        "lat": spot_config["lat"],
        "lon": spot_config["lon"],
        "trigger": trigger,
        "level": "strong" if upwind_good and ensemble_good else ("watch" if trigger else "none"),
        "alertId": f"swa-session-{spot_id}-{event_date}",
        "eventDate": event_date,
        "reason": " · ".join(reasons) if reasons else "signalen onvoldoende",
        "gradient": gradient,
        "upwind": upwind,
        "ensemble": ensemble,
        "forecast": forecast,
        "errors": errors or None,
    }
    payload = {
        "ok": True,
        "version": "v603.2c-standalone",
        "generatedAt": utc_now_iso(),
        "timezone": "Europe/Amsterdam",
        "rule": {"gradient": "neemt toe of >=4 hPa", "upwindKt": 15, "ensemblePct": 60, "windowHours": 12},
        "spots": [result],
    }
    return payload, result


def fmt_number(value: Any, decimals: int = 0) -> str:
    number = as_float(value)
    return "?" if number is None else f"{number:.{decimals}f}"


def spot_lines(spot: dict[str, Any]) -> list[str]:
    name = html.escape(str(spot.get("name") or spot.get("id") or "Onbekende spot"))
    water = html.escape(str(spot.get("water") or ""))
    reason = html.escape(str(spot.get("reason") or "signalen vallen samen"))
    lines = [f"<b>{name}{' · ' + water if water else ''}</b>", reason]

    gradient = spot.get("gradient") or {}
    if gradient:
        trend = gradient.get("trend")
        trend_text = "neemt toe" if trend == 1 else ("neemt af" if trend == -1 else "stabiel")
        lines.append(f"Drukgradiënt: {fmt_number(gradient.get('magnitude'), 1)} hPa · {trend_text}")

    upwind = spot.get("upwind") or {}
    if upwind:
        gust = upwind.get("gustKt")
        gust_text = f" · vlagen {fmt_number(gust)} kt" if gust is not None else ""
        lines.append(
            f"Bovenwinds: {fmt_number(upwind.get('windKt'))} kt{gust_text} · "
            f"{html.escape(str(upwind.get('station') or 'meetstation'))} "
            f"({fmt_number(upwind.get('distanceKm'))} km)"
        )

    ensemble = spot.get("ensemble") or {}
    if ensemble:
        lines.append(
            f"Ensemble: {fmt_number(ensemble.get('probabilityPct'))}% kans op ≥15 kt"
            f" rond {html.escape(str(ensemble.get('localTime') or '?'))}"
        )

    peak = (spot.get("forecast") or {}).get("peak") or {}
    if peak:
        direction = html.escape(str(peak.get("direction") or ""))
        lines.append(
            f"Modelpiek komende 12 uur: {fmt_number(peak.get('windKt'), 1)} kt"
            f"{' ' + direction if direction else ''} rond "
            f"{html.escape(str(peak.get('localTime') or '?'))}"
        )
    return lines


def build_alarm_message(spot: dict[str, Any], generated_at: str | None, *, test: bool) -> str:
    title = "🧪 <b>SWA TELEGRAM-TEST</b>" if test else "🏄 <b>SWA SESSIEALARM</b>"
    intro = "De achtergrondcontrole werkt voor de actieve spot." if test else "De vooruitblikkende signalen vallen samen:"
    blocks = [title, intro, "\n".join(spot_lines(spot))]
    blocks.append(f"Controle: {html.escape(generated_at or utc_now_iso())}")
    blocks.append(f'<a href="{html.escape(APP_URL, quote=True)}">Open SWA Surfweer</a>')
    return "\n\n".join(blocks)


def simple_test_message(active_spot: str) -> str:
    return (
        "🧪 <b>SWA TELEGRAM-TEST</b>\n\n"
        f"De achtergrondcontrole en Telegram werken voor <b>{html.escape(spot_title(active_spot))}</b>.\n"
        "De PWA mag gesloten zijn.\n\n"
        f'<a href="{html.escape(APP_URL, quote=True)}">Open SWA Surfweer</a>'
    )


def main() -> int:
    status = load_status()
    test_requested = False

    try:
        test_requested = process_telegram_updates(status)
    except Exception as exc:
        print(f"Waarschuwing: Telegramcommando's ophalen mislukt: {exc}")

    manual_command = os.environ.get("MANUAL_COMMAND", "").strip()
    if manual_command:
        outcome = apply_command(manual_command, status, send_reply=True)
        test_requested = test_requested or outcome["test_requested"]

    # Persist the selected spot before any weather source is contacted.
    save_status(status)

    active_spot = status.get("active_spot")
    if test_requested:
        if active_spot not in SPOTS:
            send_telegram("❌ Test niet uitgevoerd: kies eerst een spot met <code>/spot makkum</code>.")
        else:
            send_telegram(simple_test_message(str(active_spot)))

    if not status.get("enabled") or active_spot not in SPOTS:
        print("Geen actieve spot: achtergrondalarm staat uit.")
        return 0

    try:
        data, spot = evaluate_spot(str(active_spot))
    except Exception as exc:
        # A temporary weather-source issue should never undo the selected spot
        # or make the workflow red. The next scheduled run retries automatically.
        print(f"Waarschuwing: weercontrole tijdelijk mislukt: {exc}")
        return 0

    if not spot.get("trigger"):
        print(f"Geen alarm voor actieve spot {active_spot}.")
        return 0

    alert_id = str(spot.get("alertId") or "")
    if not alert_id:
        print("Waarschuwing: alarmrecord mist alertId; geen melding verzonden.")
        return 0

    spot_status = status.setdefault("spots", {}).setdefault(str(active_spot), {})
    if spot_status.get("last_alert_id") == alert_id:
        print(f"Geen duplicaat voor {active_spot}: {alert_id}")
        return 0

    send_telegram(build_alarm_message(spot, data.get("generatedAt"), test=False))
    spot_status.update(
        {
            "last_alert_id": alert_id,
            "event_date": spot.get("eventDate"),
            "level": spot.get("level"),
            "reason": spot.get("reason"),
            "sent_at": utc_now_iso(),
        }
    )
    save_status(status)
    print(f"Nieuw Telegram-sessiealarm verzonden voor uitsluitend {active_spot}.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FOUT: {exc}", file=sys.stderr)
        raise SystemExit(1)
