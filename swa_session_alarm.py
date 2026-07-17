#!/usr/bin/env python3
"""SWA V603.2 single-active-spot Telegram background alarm.

GitHub Actions polls Telegram commands and checks exactly one active SWA spot.
No Cloudflare KV/D1/R2 bindings are required. State is stored in a small JSON
file committed by the workflow.
"""

from __future__ import annotations

import html
import json
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

ALARM_ENDPOINT_BASE = (
    "https://lively-brook-24bf.jaapzuijderduijn.workers.dev/"
    "api/session-alarm?key=swa-v6032-8c4e1f7a2d9b"
)
APP_URL = "https://lively-brook-24bf.jaapzuijderduijn.workers.dev/"
STATUS_FILE = Path("swa_session_alarm_status.json")
MAX_DATA_AGE_MINUTES = 30
HTTP_TIMEOUT_SECONDS = 50

SPOTS: dict[str, dict[str, str]] = {
    "makkum": {"name": "Makkum", "water": "IJsselmeer"},
    "stavoren": {"name": "Stavoren", "water": "IJsselmeer"},
    "schokkerhaven": {"name": "Schokkerhaven", "water": "Ketelmeer"},
    "urk": {"name": "Urk", "water": "IJsselmeer"},
    "veluwemeer": {"name": "Veluwemeer", "water": "Veluwemeer"},
    "brouwersdam": {"name": "Brouwersdam", "water": "kust"},
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


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def default_status() -> dict[str, Any]:
    return {
        "version": 2,
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
        status["version"] = 2
        return status
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Waarschuwing: statusbestand ongeldig; begin veilig gestopt: {exc}")
        return status


def save_status(status: dict[str, Any]) -> None:
    status["version"] = 2
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
) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            request_headers = {
                "User-Agent": "SWA-Telegram-Single-Spot/603.2",
                "Accept": "application/json",
                "Cache-Control": "no-cache",
            }
            if headers:
                request_headers.update(headers)
            req = urllib.request.Request(url, data=data, headers=request_headers)
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_SECONDS) as response:
                payload = response.read().decode("utf-8")
            result = json.loads(payload)
            if not isinstance(result, dict):
                raise ValueError("response is not a JSON object")
            return result
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
    if not result.get("ok"):
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


def apply_command(
    text: str,
    status: dict[str, Any],
    *,
    send_reply: bool = True,
) -> dict[str, bool]:
    command, arg = split_command(text)
    result = {"changed": False, "test_requested": False}
    reply: str | None = None

    if command in {"/start"}:
        if arg.lower().startswith("spot_"):
            command, arg = "/spot", arg[5:]
        else:
            reply = help_message()
    if command in {"/status"}:
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
        status["telegram_update_offset"] = max(
            int(status.get("telegram_update_offset") or 0), update_id + 1
        )
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


def fetch_alarm_payload(spot_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    url = ALARM_ENDPOINT_BASE + "&spot=" + urllib.parse.quote(spot_id)
    data = request_json(url)
    if not data.get("ok"):
        raise RuntimeError(f"SWA endpoint meldt fout: {data.get('error') or data}")
    generated = parse_iso(data.get("generatedAt"))
    if generated is None:
        raise RuntimeError("SWA endpoint heeft geen geldige generatedAt")
    age_minutes = (datetime.now(timezone.utc) - generated).total_seconds() / 60
    if age_minutes < -5 or age_minutes > MAX_DATA_AGE_MINUTES:
        raise RuntimeError(f"SWA endpointdata is niet vers genoeg: {age_minutes:.1f} minuten")
    spots = data.get("spots")
    if not isinstance(spots, list) or len(spots) != 1 or not isinstance(spots[0], dict):
        raise RuntimeError("SWA endpoint moet exact één spot teruggeven")
    spot = spots[0]
    if str(spot.get("id") or "").lower() != spot_id:
        raise RuntimeError("SWA endpoint gaf een andere spot terug")
    return data, spot


def fmt_number(value: Any, decimals: int = 0) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "?"
    return f"{number:.{decimals}f}"


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


def main() -> int:
    status = load_status()
    test_requested = process_telegram_updates(status)

    manual_command = os.environ.get("MANUAL_COMMAND", "").strip()
    if manual_command:
        outcome = apply_command(manual_command, status, send_reply=True)
        test_requested = test_requested or outcome["test_requested"]

    active_spot = status.get("active_spot")
    if test_requested:
        if active_spot not in SPOTS:
            send_telegram("❌ Test niet uitgevoerd: kies eerst een spot met <code>/spot makkum</code>.")
        else:
            data, spot = fetch_alarm_payload(str(active_spot))
            send_telegram(build_alarm_message(spot, data.get("generatedAt"), test=True))

    if not status.get("enabled") or active_spot not in SPOTS:
        save_status(status)
        print("Geen actieve spot: achtergrondalarm staat uit.")
        return 0

    data, spot = fetch_alarm_payload(str(active_spot))
    if not spot.get("trigger"):
        save_status(status)
        print(f"Geen alarm voor actieve spot {active_spot}.")
        return 0

    alert_id = str(spot.get("alertId") or "")
    if not alert_id:
        raise RuntimeError("Alarmrecord mist alertId")
    spot_status = status.setdefault("spots", {}).setdefault(str(active_spot), {})
    if spot_status.get("last_alert_id") == alert_id:
        save_status(status)
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
