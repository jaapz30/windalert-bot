# windalert_bot.py
import requests
import json
from datetime import datetime
import os

# ===== INSTELLINGEN =====
BOT_TOKEN = "8184152270:AAF3BEkQP6m6nX2Jk4MVzQKuFTOSeSX3Va8"
CHAT_ID = "6644202562"
WIND_THRESHOLDS = [3, 4, 5, 15]  # Voeg hier zoveel drempels toe als je wilt
ONLY_BETWEEN_HOURS = (7, 20)  # Actief tussen 07:00 en 20:00
STATUS_FILE = "status.json"

# ===== WIND API =====
API_URL = "https://api.open-meteo.com/v1/forecast?latitude=52.707&longitude=5.874&current_weather=true"

# ===== WINDRICHTING CONVERSIE =====
def graden_naar_richting(graden):
    richtingen = ['N', 'NO', 'O', 'ZO', 'Z', 'ZW', 'W', 'NW']
    index = round(graden / 45) % 8
    return richtingen[index]

# ===== STATUS LADEN/OPSLAAN =====
def load_status():
    today = datetime.now().strftime("%Y-%m-%d")
    if os.path.exists(STATUS_FILE):
        with open(STATUS_FILE, 'r') as f:
            data = json.load(f)
            if data.get("datum") != today:
                return reset_status(today)
            return data
    return reset_status(today)

def reset_status(today):
    return {"datum": today, **{str(d): False for d in WIND_THRESHOLDS}}

def save_status(status):
    with open(STATUS_FILE, 'w') as f:
        json.dump(status, f)

# ===== TELEGRAM BERICHT VERZENDEN =====
def stuur_telegram_bericht(knopen, richting, temperatuur, windstoten_knopen):
    bericht = (
        "*SWA WINDALERT!*\n\n"
        f"Actuele wind: *{knopen:.1f}* knopen uit het *{richting}*\n\n"
        f"Windstoten: *{windstoten_knopen:.1f}* knopen\n\n"
        f"Temperatuur: *{temperatuur:.1f}°C*\n\n"
        "[🌐 SWA windapp](https://jaapz30.github.io/SWA-weatherapp/)"
    )

    payload = {
        "chat_id": CHAT_ID,
        "text": bericht,
        "parse_mode": "Markdown"
    }

    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data=payload)

# ===== HOOFDPROGRAMMA =====
def main():
    nu = datetime.now()
    uur = nu.hour

    if not (ONLY_BETWEEN_HOURS[0] <= uur <= ONLY_BETWEEN_HOURS[1]):
        return

    status = load_status()

    response = requests.get(API_URL)
    if response.status_code != 200:
        return

    data = response.json()
    weather = data['current_weather']

    windspeed_kmh = weather['windspeed']
    winddirection_deg = weather['winddirection']
    temperature = weather['temperature']
    windgusts_kmh = weather.get('windgusts', windspeed_kmh + 5)  # fallback

    knopen = windspeed_kmh * 0.539957
    windstoten_knopen = windgusts_kmh * 0.539957
    richting = graden_naar_richting(winddirection_deg)

    for drempel in WIND_THRESHOLDS:
        key = str(drempel)
        if knopen >= drempel and not status.get(key, False):
            stuur_telegram_bericht(knopen, richting, temperature, windstoten_knopen)
            status[key] = True

    save_status(status)

if __name__ == "__main__":
    main()
