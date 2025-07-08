import requests
import json
import os
from datetime import datetime

# Drempelwaardes in knopen
DREMPELS = [5, 10, 15, 20, 25, 30, 35]

# Telegram instellingen (uit GitHub Secrets)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Bestandspad voor status
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
