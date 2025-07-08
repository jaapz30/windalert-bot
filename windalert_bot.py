import requests
import json
import os
from datetime import datetime
from bs4 import BeautifulSoup

# Instellingen
DREMPELS = [5, 10, 15, 20, 25, 30, 35]  # Pas aan naar wens
STATUS_FILE = "status.json"
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Windrichting omzetten van graden naar woorden
def graden_naar_windrichting(graden):
    richtingen = ['Noord', 'NNO', 'NO', 'ONO', 'Oost', 'OZO', 'ZO', 'ZZO',
                  'Zuid', 'ZZW', 'ZW', 'WZW', 'West', 'WNW', 'NW', 'NNW']
    index = int((graden + 11.25) / 22.5) % 16
    return richtingen[index]

# Standaard windalertbericht
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

# Melding als er geen data beschikbaar is
def verzend_telegram_foutmelding():
    bericht = (
        "⚠️ *SWA WINDALERT*\n"
        "Er is geen actuele winddata beschikbaar van KNMI of Windfinder.\n"
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

# Data ophalen: eerst KNMI, anders Windfinder
def haal_windgegevens_op():
    # 🔹 KNMI proberen
    try:
        url = "https://api.dataplatform.knmi.nl/open-data/v1/datasets/actuele10mindataKNMIstations/versions/2/files"
        headers = { "Authorization": "APIKey 4ee734442fcf56855889e78e58e5d874" }
        response = requests.get(url, headers=headers)
        files = response.json().get("files", [])
        if not files:
            raise Exception("Geen KNMI-bestanden")

        latest_file = files[0]["filename"]
        file_url = f"{url}/{latest_file}/url"
        download_url = requests.get(file_url, headers=headers).json()["temporaryDownloadUrl"]
        bestand = requests.get(download_url).text

        for regel in bestand.splitlines():
            if regel.startswith("275"):
                velden = regel.split(",")
                snelheid_ms = float(velden[9]) / 10
                windstoot_ms = float(velden[10]) / 10
                richting_graden = int(velden[11])
                temperatuur = float(velden[6]) / 10
                snelheid = round(snelheid_ms * 1.94384)
                windstoot = round(windstoot_ms * 1.94384)
                richting = graden_naar_windrichting(richting_graden)
                return snelheid, windstoot, richting, round(temperatuur)
        raise Exception("Geen data voor station 275")
    except Exception:
        pass

    # 🔸 Windfinder fallback
    try:
        url = "https://www.windfinder.com/weatherforecast/schokkerhaven"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.content, "html.parser")

        wind_el = soup.select_one("div.actual__wind")
        snelheid = int(wind_el.select_one("span.speed").text.strip().replace("kt", "").strip())
        gust_el = wind_el.select_one("span.gusts")
        gust_txt = gust_el.text.strip().replace("Gusts", "").replace("kt", "").strip()
        windstoot = int(gust_txt) if gust_txt else snelheid
        temperatuur = int(soup.select_one("span.actual__temperature").text.strip().replace("°C", "").strip())
        richting = wind_el.select_one("span.dir").text.strip()

        return snelheid, windstoot, richting, temperatuur
    except Exception:
        return None  # Als beide bronnen falen

# Status laden
def laad_status():
    if not os.path.exists(STATUS_FILE):
        return {f"melding_{d}": False for d in DREMPELS}
    with open(STATUS_FILE, "r") as f:
        return json.load(f)

# Status opslaan
def sla_status_op(status):
    with open(STATUS_FILE, "w") as f:
        json.dump(status, f)

# Status resetten
def reset_status():
    status = {f"melding_{d}": False for d in DREMPELS}
    sla_status_op(status)

# Hoofdfunctie
def hoofd():
    nu = datetime.now()
    if nu.hour == 0 and nu.minute < 15:
        reset_status()
        return

    data = haal_windgegevens_op()
    if not data:
        verzend_telegram_foutmelding()
        return

    snelheid, windstoten, richting, temperatuur = data
    status = laad_status()

    for drempel in DREMPELS:
        sleutel = f"melding_{drempel}"
        if snelheid >= drempel and not status.get(sleutel, False):
            verzend_telegrambericht(snelheid, windstoten, richting, temperatuur)
            status[sleutel] = True
            break

    sla_status_op(status)

# Startscript
if __name__ == "__main__":
    hoofd()
