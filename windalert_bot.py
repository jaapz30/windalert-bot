import requests
import json
import os
from datetime import datetime

# Drempelwaardes in knopen – pas aan voor test (bijv. [0])
DREMPELS = [5, 10, 15, 20, 25, 30, 35]

# Secrets vanuit GitHub
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Bestand om te onthouden wat al gemeld is
STATUS_FILE = "status.json"

def graden_naar_windrichting(graden):
    richtingen = ['Noord', 'NNO', 'NO', 'ONO', 'Oost', 'OZO', 'ZO', 'ZZO',
                  'Zuid', 'ZZW', 'ZW', 'WZW', 'West', 'WNW', 'NW', 'NNW']
    index = int((graden + 11.25) / 22.5) % 16
    return richtingen[index]

def haal_windgegevens_op():
    url = "https://api.open-meteo.com/v1/forecast?latitude=52.65&longitude=5.58&current=wind_speed_10m,wind_direction_10m&timezone=Europe%2FAmsterdam"
    response = requests.get(url)
    data = response.json()
    snelheid = round(data["current"]["wind_speed_10m"] * 1.94384)  # m/s naar knopen
    richting = graden_naar_windrichting(data["current"]["wind_direction_10m"])
    return snelheid, richting

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

def verzend_telegrambericht(snelheid, richting):
    bericht = (
        f"💨 WINDALARM\n"
        f"Snelheid: {snelheid} knopen\n"
        f"Richting: {richting}\n"
        f"SWA windapp: https://jaapz30.github.io/SWA-weatherapp/"
    )
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": bericht
    }
    response = requests.post(url, data=payload)
    print("Verzendbericht:", response.status_code, response.text)

def hoofd():
    nu = datetime.now()

    # Reset automatisch rond middernacht
    if nu.hour == 0 and nu.minute < 15:
        reset_status()
        print("Statusbestand automatisch gereset.")
        return

    snelheid, richting = haal_windgegevens_op()
    print(f"Actuele wind: {snelheid} knopen, {richting}")

    status = laad_status()

    for drempel in DREMPELS:
        sleutel = f"melding_{drempel}"
        if snelheid >= drempel and not status.get(sleutel, False):
            verzend_telegrambericht(snelheid, richting)
            status[sleutel] = True
            print(f"Melding verzonden voor {drempel} knopen.")
            break  # maar 1 melding per run

    sla_status_op(status)

if __name__ == "__main__":
    hoofd()
