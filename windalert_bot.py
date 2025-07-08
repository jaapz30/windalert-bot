import requests
import json
import os
from datetime import datetime

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
WEERLIVE_API_KEY = os.getenv("WEERLIVE_API_KEY")

DREMPELS = [5, 10, 15, 20, 25, 30, 35]

STATUS_FILE = "status.json"

def graden_naar_windrichting(graden):
    richtingen = ['Noord', 'NNO', 'NO', 'ONO', 'Oost', 'OZO', 'ZO', 'ZZO',
                  'Zuid', 'ZZW', 'ZW', 'WZW', 'West', 'WNW', 'NW', 'NNW']
    index = int((graden + 11.25) / 22.5) % 16
    return richtingen[index]

def haal_knmi_data():
    url = "https://api.dataplatform.knmi.nl/open-data/v1/datasets/actuele10mindata-knmi-stations/versions/2/files"
    headers = {"Authorization": f"Bearer {os.getenv('KNMI_API_KEY')}"}
    params = {"station": "273"}  # Marknesse
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        bestand_url = response.json()["_embedded"]["files"][-1]["url"]
        bestand = requests.get(bestand_url)
        bestand.raise_for_status()
        regels = bestand.text.splitlines()
        laatste = regels[-1].split(",")
        return float(laatste[10]), float(laatste[11]), int(laatste[12])  # wind, stoot, richting
    except:
        return None

def haal_weerlive_data():
    url = f"https://weerlive.nl/api/json-data-10min.php?key={WEERLIVE_API_KEY}&locatie=Marknesse"
    try:
        data = requests.get(url).json()
        wind = float(data["liveweer"][0]["windms"]) * 1.94384
        stoot = float(data["liveweer"][0]["windkmh"]) * 0.539957
        richting = data["liveweer"][0]["windr"]
        return wind, stoot, richting
    except:
        return None

def laad_status():
    if os.path.exists(STATUS_FILE):
        with open(STATUS_FILE) as f:
            return json.load(f)
    return {str(d): False for d in DREMPELS}

def sla_status_op(status):
    with open(STATUS_FILE, "w") as f:
        json.dump(status, f)

def verzend_telegram(wind, stoot, richting):
    tekst = f"""💨 *WINDALARM*
Snelheid: {round(wind)} knopen
Windstoten: {round(stoot)} knopen
Richting: {richting}
🌐 [SWA windapp](https://jaapz30.github.io/SWA-weatherapp/)"""
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": tekst,
        "parse_mode": "Markdown"
    }
    requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", data=payload)

def main():
    status = laad_status()

    data = haal_knmi_data()
    if data:
        wind, stoot, richting_graden = data
        richting = graden_naar_windrichting(richting_graden)
    else:
        data = haal_weerlive_data()
        if data:
            wind, stoot, richting = data
        else:
            print("Geen gegevens beschikbaar via KNMI of Weerlive")
            return

    for drempel in DREMPELS:
        if wind >= drempel and not status[str(drempel)]:
            verzend_telegram(wind, stoot, richting)
            status[str(drempel)] = True

    status["datum"] = datetime.now().strftime("%Y-%m-%d")
    sla_status_op(status)

if __name__ == "__main__":
    main()
