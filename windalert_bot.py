# windalert_bot.py
import requests
import json
from datetime import datetime
import os

# ===== INSTELLINGEN =====
BOT_TOKEN = "8184152270:AAF3BEkQP6m6nX2Jk4MVzQKuFTOSeSX3Va8"
CHAT_ID = "6644202562"
WIND_THRESHOLD_KNOTS = 5  # Testdrempel, makkelijk aan te passen
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
    if os.path.exists(STATUS_FILE):
        with open(STATUS_FILE, 'r') as f:
            data = json.load(f)
            if data.get("datum") == datetime.now().strftime("%Y-%m-%d"):
                return data
    return {"datum": datetime.now().strftime("%Y-%m-%d"), "gemeld": False}

def save_status(status):
    with open(STATUS_FILE, 'w') as f:
        json.dump(status, f)

# ===== TELEGRAM BERICHT VERZENDEN =====
def stuur_telegram_bericht(knopen, richting):
    bericht = f"\ud83d\udca8 *SWA Windalert*\nActuele wind: *{knopen:.1f}* knopen uit het *{richting}*.\n\ud83c\udf10 [SWA windapp](https://jaapz30.github.io/SWA-weatherapp/)"
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
    if status.get("gemeld"):
        return

    response = requests.get(API_URL)
    if response.status_code != 200:
        return

    data = response.json()
    windspeed_mps = data['current_weather']['windspeed']
    winddirection_deg = data['current_weather']['winddirection']
    knopen = windspeed_mps * 1.94384
    richting = graden_naar_richting(winddirection_deg)

    if knopen >= WIND_THRESHOLD_KNOTS:
        stuur_telegram_bericht(knopen, richting)
        status['gemeld'] = True
        save_status(status)

if __name__ == "__main__":
    main()
