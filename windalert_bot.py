import requests
import os
import json
from datetime import datetime

# 🧪 Ingevulde secrets uit GitHub
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
KNMI_API_KEY = os.getenv("KNMI_API_KEY")

# 📌 Station Marknesse: ID = 273
STATION_ID = 273
DREMPELS = [5, 10, 15, 20, 25, 30, 35]

# 📁 Statusbestand laden
STATUS_FILE = "status.json"
if os.path.exists(STATUS_FILE):
    with open(STATUS_FILE, "r") as f:
        status = json.load(f)
else:
    status = {f"melding_{d}": False for d in DREMPELS}

# 🧭 Windrichting omzetten
def graden_naar_richting(graden):
    richtingen = ['Noord', 'NNO', 'NO', 'ONO', 'Oost', 'OZO', 'ZO', 'ZZO',
                  'Zuid', 'ZZW', 'ZW', 'WZW', 'West', 'WNW', 'NW', 'NNW']
    index = int((graden + 11.25) / 22.5) % 16
    return richtingen[index]

# 🛰️ KNMI actuele data ophalen
def haal_knmi_data():
    headers = {
        "Authorization": KNMI_API_KEY,
        "Accept": "application/json"
    }
    url = "https://api.dataplatform.knmi.nl/open-data/v1/datasets/actuele10mindata-knmi-stations/versions/2/files"
    response = requests.get(url, headers=headers)
    bestanden = response.json()["files"]

    # Laatste bestand ophalen
    laatste_bestand = sorted(bestanden, key=lambda x: x['filename'], reverse=True)[0]['filename']
    data_url = f"https://api.dataplatform.knmi.nl/open-data/v1/datasets/actuele10mindata-knmi-stations/versions/2/files/{laatste_bestand}/url"
    url_response = requests.get(data_url, headers=headers).json()
    download_url = url_response['temporaryDownloadUrl']

    # CSV inladen
    csv_data = requests.get(download_url).text
    for regel in csv_data.splitlines():
        if regel.startswith(str(STATION_ID)):
            kolommen = regel.split(',')
            windsnelheid = round(float(kolommen[6]) * 1.94384)  # m/s naar knopen
            windstoten = round(float(kolommen[7]) * 1.94384)
            windrichting = graden_naar_richting(float(kolommen[5]))
            return windsnelheid, windstoten, windrichting
    return None, None, None

# 🚨 Telegrammelding
def stuur_melding(knopen, stoten, richting):
    tekst = f"💨 *WINDALARM*\nSnelheid: {knopen} knopen\nWindstoten: {stoten} knopen\nRichting: {richting}\n🌐 [SWA windapp](https://jaapz30.github.io/SWA-weatherapp/)"
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": tekst,
        "parse_mode": "Markdown"
    }
    requests.post(url, json=payload)

# ✅ Hoofdscript
windsnelheid, windstoten, richting = haal_knmi_data()

if windsnelheid:
    for drempel in DREMPELS:
        key = f"melding_{drempel}"
        if windsnelheid >= drempel and not status.get(key, False):
            stuur_melding(windsnelheid, windstoten, richting)
            status[key] = True

# 💾 Status opslaan
with open(STATUS_FILE, "w") as f:
    json.dump(status, f)
