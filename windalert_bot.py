import requests
import json
import os
from datetime import datetime

# Instellingen
DREMPELS = [5, 10, 15, 20, 25, 30, 35]
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
STATUS_FILE = "status.json"

def graden_naar_windrichting(graden):
    richtingen = ['Noord', 'NNO', 'NO', 'ONO', 'Oost', 'OZO', 'ZO', 'ZZO',
                  'Zuid', 'ZZW', 'ZW', 'WZW', 'West', 'WNW', 'NW', 'NNW']
    index = int((graden + 11.25) / 22.5) % 16
    return richtingen[index]

def haal_windgegevens_op():
    url = (
        "https://api.open-meteo.com/v1/forecast?"
        "latitude=52.65&longitude=5.58&current=wind_speed_10m,"
        "wind_gusts_10m,wind_direction_10m,temperature_2m"
        "&timezone=Europe%2FAmsterdam"
    )
    response = requests.get(url)
    data = response.json()
    current = data.get("current", {})

    # Haal data op met fallback naar 0 als het ontbreekt
    snelheid_ms = current.get("wind_speed_10m", 0) or 0
    windstoten_ms = current.get("wind_gusts_10m", 0) or 0
    richting_graden = current.get("wind_direction_10m", 0) or 0
    temperatuur = current.get("temperature_2m", 0) or 0

    snelheid = round(snelheid_ms * 1.94384)
    windstoten = round(windstoten_ms * 1.94384)
    richting = graden_naar_windrichting(richting_graden)

    # Debug output
    print(f"API wind m/s: {snelheid_ms}, windstoten m/s: {windstoten_ms}, richting: {richting_graden}")

    return snelheid, windstoten, richting, round(temperatuur)

def laad_status():
    if not os.path.exists(STATUS_FILE):
        return {f"melding_{d}": False for d in DREMPELS}
    with open(STATUS_FILE, "r") as f:
        return json.load(f)

def sla_status_op(status):
    with open(STATUS_FILE, "w") as f:
        json.dump(status, f)

def reset_status():
    status = {f"melding_{d}": False for d in DREMPELS}
    sla_status_op(status)

def verzend_telegrambericht(snelheid, windstoten, richting, temperatuur):
    bericht = (
        "💨 *SWA WINDALERT*\n"
        f"🌬️ Wind: {snelheid} knopen ({richting})\n"
        f"🌪️ Windstoten: {windstoten} knopen\n"
        f"🌡️ Temperatuur: {temperatuur} °C\n"
        "🌐 [SWA windapp](https://jaapz30.github.io/SWA-weatherapp/)"
    )
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": bericht,
        "parse_mode": "Markdown"
    }
    response = requests.post(url, data=payload)
    print("Telegram respons:", response.status_code, response.text)

def hoofd():
    nu = datetime.now()

    # Nachtelijke reset tussen 00:00 en 00:14
    if nu.hour == 0 and nu.minute < 15:
        reset_status()
        print("Statusbestand automatisch gereset.")
        return

    snelheid, windstoten, richting, temperatuur = haal_windgegevens_op()
    print(f"Actuele wind: {snelheid} knopen, Windstoten: {windstoten}, Richting: {richting}, Temp: {temperatuur}°C")

    status = laad_status()

    for drempel in DREMPELS:
        sleutel = f"melding_{drempel}"
        if snelheid >= drempel and not status.get(sleutel, False):
            verzend_telegrambericht(snelheid, windstoten, richting, temperatuur)
            status[sleutel] = True
            print(f"Melding verzonden voor {drempel} knopen.")
            break

    sla_status_op(status)

if __name__ == "__main__":
    hoofd()
