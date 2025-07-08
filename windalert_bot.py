import requests
import json
import os
import re
from bs4 import BeautifulSoup
from datetime import datetime

# Instellingen
DREMPELS = [5, 10, 15, 20, 25, 30, 35]
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
STATUS_FILE = "status.json"

def haal_windgegevens_op():
    url = "https://windverwachting.nl/actuele-wind.php?plaatsnaam=Marknesse"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/114.0.0.0 Safari/537.36"
        )
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")
        text = soup.get_text()

        # Zoek alle knopen-waarden
        knopen = re.findall(r"(\d+(?:\.\d+)?)\s*knopen", text)
        richting = re.search(r"(Noord|Zuid|Oost|West|Noord-West|Zuid-Oost|Zuid-West|Noord-Oost)", text)
        temp_match = re.search(r"Temperatuur.*?(-?\d+)\s*°C", text)

        if len(knopen) < 2:
            raise ValueError("Niet genoeg knopenwaarden gevonden")

        snelheid = round(float(knopen[0]))
        windstoten = round(float(knopen[1]))
        richting = richting.group(0) if richting else "Onbekend"
        temperatuur = int(temp_match.group(1)) if temp_match else 0

        print(f"✅ Gevonden: {snelheid} knopen, {windstoten} knopen, {richting}, {temperatuur}°C")
        return snelheid, windstoten, richting, temperatuur

    except Exception as e:
        print(f"❌ Data ophalen mislukt: {e}")
        return None

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
    requests.post(url, data=payload)

def verzend_geen_data_bericht():
    bericht = (
        "⚠️ *SWA WINDALERT*\n"
        "Er is op dit moment geen actuele winddata beschikbaar van Windverwachting.nl.\n"
        "Controleer handmatig op storing of wijziging.\n"
        "🌐 [SWA windapp](https://jaapz30.github.io/SWA-weatherapp/)"
    )
    url = f"https://api.telegram.org/bot{TEL
