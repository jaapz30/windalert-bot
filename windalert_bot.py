import requests
import json
import os
from datetime import datetime

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
    current = data["current"]
    snelheid = round(current["wind_speed_10m"] * 1.94384)        # m/s → knopen
    windstoten = round(current["wind_gusts_10m"] * 1.94384)      # m/s → knopen
    richting = graden_naar_windrichting(current["wind_direction_10m"])
    temperatuur = round(current["temperature_2m"])
    return snelheid, windstoten, richting, temperatuur

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
    print("Verzendbericht:", response.status_code, response.text)

def hoofd():
    nu = datetime.now()
    if nu.hour == 0 and nu.minute < 15:
        reset_status()
        print("Statusbestand automatisch gereset.")
        return

    snelheid, windstoten, richting, temperatuur = haal_windgegevens_op()
    print(f"Wind: {snelheid} knopen, Windstoten: {windstoten}, Richting: {richting}, Temp: {temperatuur}°C")

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
