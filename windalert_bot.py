import requests
import json
import os
from bs4 import BeautifulSoup
from datetime import datetime

# Instellingen
DREMPELS = [5, 10, 15, 20, 25, 30, 35]
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
STATUS_FILE = "status.json"

def haal_windgegevens_op():
    url = "https://windverwachting.nl/actuele-wind.php?plaatsnaam=Marknesse"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.content, "html.parser")
        table = soup.find("table", class_="winddata")
        rows = table.find_all("tr")

        data = {}
        for row in rows:
            cols = row.find_all("td")
            if len(cols) == 2:
                key = cols[0].get_text(strip=True).lower()
                val = cols[1].get_text(strip=True)
                data[key] = val

        # ✅ Gebruik juiste benamingen van de site
        snelheid = int(data.get("wind", "0").replace("knopen", "").strip())
        windstoten = int(data.get("windstoten", str(snelheid)).replace("knopen", "").strip())
        richting = data.get("windrichting", "Onbekend")
        temperatuur = int(data.get("temperatuur", "0").replace("°c", "").strip())

        print(f"✅ Windverwachting.nl: {snelheid} knopen, gusts {windstoten}, {richting}, {temperatuur}°C")
        return snelheid, windstoten, richting, temperatuur

    except Exception as e:
        print(f"❌ Kan geen actuele winddata ophalen: {e}")
        return None  # Fallback

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
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": bericht,
        "parse_mode": "Markdown"
    }
    requests.post(url, data=payload)

def hoofd():
    nu = datetime.now()

    # ✅ Nachtelijke reset tussen 00:00 en 00:14
    if nu.hour == 0 and nu.minute < 15:
        reset_status()
        print("✅ Statusbestand automatisch gereset.")
        return

    gegevens = haal_windgegevens_op()
    if not gegevens:
        verzend_geen_data_bericht()
        return

    snelheid, windstoten, richting, temperatuur = gegevens
    status = laad_status()

    for drempel in DREMPELS:
        sleutel = f"melding_{drempel}"
        if snelheid >= drempel and not status.get(sleutel, False):
            verzend_telegrambericht(snelheid, windstoten, richting, temperatuur)
            status[sleutel] = True
            break

    sla_status_op(status)

if __name__ == "__main__":
    hoofd()
