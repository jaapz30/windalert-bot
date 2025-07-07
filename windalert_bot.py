# windalert_bot.py

import requests
import json
from datetime import datetime
import os

# ===== INSTELLINGEN =====
BOT_TOKEN = "8184152270:AAF3BEkQP6m6n2KJ4Mv7cQKuFTOSsEX3Va8"
CHAT_ID = "6644202562"

API_URL = "https://api.open-meteo.com/v1/forecast?latitude=52.7078&longitude=5.874&current_weather=true"

def graden_naar_richting(graden):
    richtingen = ['N', 'NO', 'O', 'ZO', 'Z', 'ZW', 'W', 'NW']
    index = round(graden / 45) % 8
    return richtingen[index]

def stuur_telegram_bericht(knopen, richting, temperatuur, windstoten_knopen):
    bericht = (
        "💨 *WINDALERT!*\n"
        f"Actuele wind: *{knopen:.1f}* knopen uit het *{richting}*\n\n"
        f"💥 Windstoten: *{windstoten_knopen:.1f}* knopen\n"
        f"🌡️ Temperatuur: *{temperatuur:.1f}°C*\n\n"
        "[🌐 SWA windapp](https://jaapz30.github.io/SWA-weatherapp/)"
    )
    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={
            "chat_id": CHAT_ID,
            "text": bericht,
            "parse_mode": "Markdown"
        }
    )

def main():
    response = requests.get(API_URL)
    if response.status_code != 200:
        print("Fout bij ophalen weerdata")
        return

    data = response.json()
    weer = data["current_weather"]

    wind_kmh = weer["windspeed"]
    wind_knopen = wind_kmh * 0.539957
    richting = graden_naar_richting(weer["winddirection"])
    temperatuur = weer["temperature"]
    windstoten_knopen = weer.get("windgusts", 0) * 0.539957 if "windgusts" in weer else 0

    # Testmelding sturen
    stuur_telegram_bericht(wind_knopen, richting, temperatuur, windstoten_knopen)
    print("Testmelding verzonden!")

# ===== UITVOERING STARTEN =====
if __name__ == "__main__":
    main()
