import requests
import json
from datetime import datetime

# === Instellingen ===
LAT = 52.645
LON = 5.385
THRESHOLDS = [15, 20, 25, 30, 35]

# === Functie om windrichting in graden om te zetten naar windstreek ===
def graden_naar_richting(graden):
    richtingen = ['N', 'NO', 'O', 'ZO', 'Z', 'ZW', 'W', 'NW']
    index = round(graden / 45) % 8
    return richtingen[index]

# === Laad status.json ===
try:
    with open("status.json", "r") as f:
        status = json.load(f)
except FileNotFoundError:
    status = {f"melding_{t}": False for t in THRESHOLDS}

# === Haal actuele windgegevens op ===
url = f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}&current=wind_speed_10m,wind_direction_10m&timezone=auto"
response = requests.get(url)
data = response.json()

windspeed = data["current"]["wind_speed_10m"]
windrichting = data["current"]["wind_direction_10m"]
windrichting_tekst = graden_naar_richting(windrichting)

# === Telegram secrets ===
import os
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# === Bericht sturen ===
def verzend_telegrambericht(knopen, richting):
    bericht = (
        "💨 *WINDALARM*\n"
        f"Snelheid: {knopen:.1f} knopen\n"
        f"Richting: {richting}\n"
        "[🌐 SWA windapp](https://jaapz30.github.io/SWA-weatherapp/)"
    )
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": bericht,
            "parse_mode": "Markdown"
        }
    )

# === Check en stuur melding als nodig ===
for drempel in THRESHOLDS:
    key = f"melding_{drempel}"
    if windspeed >= drempel and not status.get(key, False):
        verzend_telegrambericht(windspeed, windrichting_tekst)
        status[key] = True

# === Status opslaan ===
with open("status.json", "w") as f:
    json.dump(status, f)
