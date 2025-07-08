import requests
import json
import os
from datetime import datetime

# Ingevoerde drempels in knopen
DREMPELS = [5, 10, 15, 20, 25, 30, 35]

# Windrichting omzetten naar woorden
def graden_naar_richting(graden):
    richtingen = ['Noord', 'NO', 'Oost', 'ZO', 'Zuid', 'ZW', 'West', 'NW']
    index = int((graden + 22.5) % 360 / 45)
    return richtingen[index]

# Data ophalen van Open-Meteo
def haal_wind_data_op():
    url = "https://api.open-meteo.com/v1/forecast?latitude=52.65&longitude=5.38&current=wind_speed_10m,wind_direction_10m"
    response = requests.get(url)
    data = response.json()
    snelheid = round(data['current']['wind_speed_10m'] * 1.94384)  # m/s → knopen
    richting = graden_naar_richting(data['current']['wind_direction_10m'])
    return snelheid, richting

# Status.json laden
def laad_status():
    try:
        with open("status.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {f"melding_{d}": False for d in DREMPELS}

# Status.json opslaan
def sla_status_op(status):
    with open("status.json", "w") as f:
        json.dump(status, f)

# Telegrambericht versturen
def verzend_telegrambericht(wind_kts, richting):
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    tekst = (
        "🌬️ *WINDALERT*\n"
        f"Snelheid: *{wind_kts} knopen*\n"
        f"Richting: *{richting}*\n\n"
        "🌐 [SWA windapp](https://jaapz30.github.io/SWA-weatherapp/)"
    )

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": tekst,
        "parse_mode": "Markdown"
    }

    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Fout bij verzenden van Telegrambericht: {e}")

# Hoofdfunctie
def main():
    wind_kts, richting = haal_wind_data_op()
    status = laad_status()

    for drempel in DREMPELS:
        sleutel = f"melding_{drempel}"
        if wind_kts >= drempel and not status[sleutel]:
            verzend_telegrambericht(wind_kts, richting)
            status[sleutel] = True
        elif wind_kts < drempel:
            status[sleutel] = False

    sla_status_op(status)

if __name__ == "__main__":
    main()
