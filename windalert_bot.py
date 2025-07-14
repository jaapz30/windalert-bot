import requests
import json
import datetime
import os
import gzip
import io

# CONFIGURATIE
KNMI_API_KEY = os.environ.get("KNMI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

STATION = "273"  # Marknesse
DREMPELS = [2, 5, 10, 15, 20, 25, 30, 35]  # Winddrempels in knopen
STATUS_FILE = "status.json"

def graden_naar_richting(graden):
    richtingen = ['N', 'NO', 'O', 'ZO', 'Z', 'ZW', 'W', 'NW']
    index = round(graden / 45) % 8
    return richtingen[index]

def get_actuele_wind_knmi():
    try:
        base_url = "https://api.dataplatform.knmi.nl/open-data/v1/datasets/actuele10mindata-knmi/versions/2.0/files"
        headers = {"Authorization": f"Bearer {KNMI_API_KEY}"}

        today = datetime.datetime.utcnow().strftime("%Y%m%d")
        response = requests.get(f"{base_url}?date={today}", headers=headers)
        files = response.json()["files"]

        laatste_bestand = sorted([f["filename"] for f in files if f["filename"].endswith(".csv")])[-1]

        file_url = f"{base_url}/{laatste_bestand}/url"
        file_response = requests.get(file_url, headers=headers)
        download_url = file_response.json()["temporaryDownloadUrl"]

        bestand = requests.get(download_url)
        content = gzip.decompress(io.BytesIO(bestand.content).read()).decode("utf-8")

        for regel in content.splitlines():
            if regel.startswith(STATION):
                kolommen = regel.split(",")
                windsnelheid_ms = float(kolommen[6])  # FXX in m/s
                windrichting_gr = float(kolommen[5])  # DD in graden

                wind_knopen = round(windsnelheid_ms * 1.94384, 1)
                windrichting = graden_naar_richting(windrichting_gr)
                print(f"🌬️ Wind: {wind_knopen} knopen | Richting: {windrichting}")
                return wind_knopen, windrichting
    except Exception as e:
        print("❌ Fout bij ophalen KNMI data:", e)
        return None, None

def stuur_telegram(wind, richting):
    bericht = f"💨 *WINDALARM*\nSnelheid: {wind} knopen\nRichting: {richting}\n🌐 [SWA windapp](https://jaapz30.github.io/SWA-weatherapp/)"
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": bericht,
        "parse_mode": "Markdown"
    }
    response = requests.post(url, data=payload)
    print("📤 Telegram verzonden:", response.text)

def load_status():
    if not os.path.exists(STATUS_FILE):
