import requests
import json
import datetime
import os
from bs4 import BeautifulSoup

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

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
        return {f"melding_{d}": False for d in DREMPELS}
    return status

def verzend_telegrambericht(wind, richting):
    bericht = (
        f"💨 *WINDALARM*\n"
        f"Snelheid: {wind} knopen\n"
        f"Richting: {richting}\n"
        f"🌐 [SWA windapp](https://jaapz30.github.io/SWA-weatherapp/)"
    )
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': bericht,
        'parse_mode': 'Markdown'
    }
    requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", data=payload)

def main():
    gegevens = haal_windgegevens_op()
    if gegevens is None:
        return

    wind, windstoten, temperatuur, richting = gegevens
    richting = richting.replace(' - ', '-')

    status = laad_status()
    status = reset_status_als_middernacht(status)

    for drempel in sorted(DREMPELS, reverse=True):
        key = f"melding_{drempel}"
        if wind >= drempel and not status.get(key, False):
            verzend_telegrambericht(wind, richting)
            status[key] = True
            break

    sla_status_op(status)

if __name__ == "__main__":
    main()
