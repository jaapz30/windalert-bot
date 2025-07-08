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
        text = soup.get_text(separator="\n")

        # ✅ Wind en windstoten in knopen
        knopen = re.findall(r"(\d+(?:\.\d+)?)\s*knopen", text)
        if len(knopen) < 2:
            raise ValueError("Niet genoeg knopenwaarden gevonden")
        snelheid = round(float(knopen[0]))
        windstoten = round(float(knopen[1]))

        # ✅ Windrichting uit bekende lijst zoeken
        richtingen_lijst = [
            "Noord", "Noord-Oost", "Oost", "Zuid-Oost", "Zuid", "Zuid-West", "West", "Noord-West"
        ]
        richting = "Onbekend"
        for regel in text.splitlines():
            for r in richtingen_lijst:
                if r.lower() in regel.lower():
                    richting = r
                    break
            if richting != "Onbekend":
                break

        print(f"✅ Gevonden: {snelheid} knopen, {windstoten} knopen, {richting}")
        return snelheid, windstoten, richting

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

def verzend_telegrambericht(snelheid, windstoten, richting):
    bericht = (
        "💨 *SWA WINDALERT*\n"
        f"🌬️ Wind: {snelheid} knopen ({richting})\n"
        f"🌪️ Windstoten: {windstoten} knopen\n"
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
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": bericht,
        "parse_mode": "Markdown"
    }
    requests.post(url, data=payload)

def hoofd():
    nu = datetime.now()

    if nu.hour == 0 and nu.minute < 15:
        reset_status()
        print("✅ Statusbestand automatisch gereset.")
        return

    gegevens = haal_windgegevens_op()
    if not gegevens:
        verzend_geen_data_bericht()
        return

    snelheid, windstoten, richting = gegevens
    status = laad_status()

    for drempel in DREMPELS:
        sleutel = f"melding_{drempel}"
        if snelheid >= drempel and not status.get(sleutel, False):
            verzend_telegrambericht(snelheid, windstoten, richting)
            status[sleutel] = True
            break

    sla_status_op(status)

if __name__ == "__main__":
    hoofd()
