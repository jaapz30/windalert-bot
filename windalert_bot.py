import requests
import json
import datetime
import os
from bs4 import BeautifulSoup

# Secrets van GitHub Actions
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Winddrempels in knopen
DREMPELS = [5, 10, 15, 20, 25, 30, 35, 40]
STATUS_FILE = "status.json"
WIND_URL = "https://windverwachting.nl/actuele-wind.php?plaatsnaam=Marknesse"

def haal_windgegevens_op():
    try:
        response = requests.get(WIND_URL, timeout=10)
        response.raise_for_status()
    except Exception as e:
        print(f"Fout bij ophalen winddata: {e}")
        return None

    soup = BeautifulSoup(response.text, 'html.parser')

    try:
        waarden = soup.find_all('div', class_='actual__value')
        richting_div = soup.find('div', class_='actual__windarrowtext')

        wind = float(waarden[0].text.strip())
        windstoten = float(waarden[1].text.strip())
        temperatuur = float(waarden[2].text.strip())
        richting = richting_div.text.strip()
        return wind, windstoten, temperatuur, richting
    except Exception as e:
        print(f"Fout bij parseren winddata: {e}")
        return None

def laad_status():
    if not os.path.exists(STATUS_FILE):
        return {f"melding_{d}": False for d in DREMPELS}
    with open(STATUS_FILE, 'r') as f:
        return json.load(f)

def sla_status_op(status):
    with open(STATUS_FILE, 'w') as f:
        json.dump(status, f)

def reset_status_als_middernacht(status):
    nu = datetime.datetime.now()
    if nu.hour == 0 and nu.minute < 10:
        print("🌙 Middernachtdetectie: status.json wordt gereset")
        return {f"melding_{d}": False for d in_
