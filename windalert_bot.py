import requests
import json
import os
from datetime import datetime

# Instellingen
DREMPELS = [5, 10, 15, 20, 25, 30, 35]
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
STATUS_FILE = "status.json"

def graden_naar_windrichting(graden):
    richtingen = ['Noord', 'NNO', 'NO', 'ONO', 'Oost', 'OZO', 'ZO', 'ZZO',
                  'Zuid', 'ZZW', 'ZW', 'WZW', 'West', 'WNW', 'NW', 'NNW']
    index = int((graden + 11.25) / 22.5) % 16
    return richtingen[index]

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
    response = requests.post(url, data=payload)
    print("Telegram respons:", response.status_code, response.text)

def verzend_foutmelding_telegram(foutmelding):
    bericht = f"⚠️ *KNMI windalarmfout*\n{foutmelding}"
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": bericht,
        "parse_mode": "Markdown"
    }
    requests.post(url, data=payload)

def haal_windgegevens_op():
    url = "https://api.dataplatform.knmi.nl/open-data/v1/datasets/actuele10mindataKNMIstations/versions/2/files"
    headers = {
        "Authorization": "APIKey 4ee734442fcf56855889e78e58e5d874"
    }

    try:
        # Stap 1: nieuwste bestand ophalen
        response = requests.get(url, headers=headers)
        files = response.json().get("files", [])

        if not files:
            fout = "Geen actuele bestanden gevonden bij KNMI."
            print(fout)
            verzend_foutmelding_telegram(fout)
            return 0, 0, "Onbekend", 0

        latest_file = files[0]["filename"]

        # Stap 2: downloadlink ophalen
        file_url = f"{url}/{latest_file}/url"
        download_response = requests.get(file_url, headers=headers)
        download_link = download_response.json()["temporaryDownloadUrl"]

        # Stap 3: data ophalen en verwerken
        bestand = requests.get(download_link).text
        for regel in bestand.splitlines():
            if regel.startswith("275"):  # station Marknesse
                velden = regel.split(",")

                snelheid_ms = float(velden[9]) / 10  # ff
                windstoot_ms = float(velden[10]) / 10  # fx
                richting_graden = int(velden[11])  # dd
                temperatuur = float(velden[6]) / 10  # T

                snelheid_knopen = round(snelheid_ms * 1.94384)
                windstoot_knopen = round(windstoot_ms * 1.94384)
                richting = graden_naar_windrichting(richting_graden)

                print(f"KNMI: {snelheid_knopen} knopen, gusts {windstoot_knopen}, {richting}, {temperatuur}°C")
                return snelheid_knopen, windstoot_knopen, richting, round(temperatuur)

        fout = "Geen dataregel gevonden voor station 275."
        print(fout)
        verzend_foutmelding_telegram(fout)
        return 0, 0, "Onbekend", 0

    except Exception as e:
        fout = f"KNMI API-fout: {e}"
        print(fout)
        verzend_foutmelding_telegram(fout)
        return 0, 0, "Onbekend", 0

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

def hoofd():
    nu = datetime.now()

    if nu.hour == 0 and nu.minute < 15:
        reset_status()
        print("Statusbestand automatisch gereset.")
        return

    snelheid, windstoten, richting, temperatuur = haal_windgegevens_op()
    print(f"DEBUG - Actuele wind: {snelheid} knopen, Gusts: {windstoten}, Richting: {richting}, Temp: {temperatuur}°C")

    status = laad_status()

    for drempel in DREMPELS:
        sleutel = f"melding_{drempel}"
        if snelheid >= drempel and not status.get(sleutel, False):
            verzend_telegrambericht(snelheid, windstoten, richting, temperatuur)
            status[sleutel] = True
            print(f"Melding verzonden voor {drempel} knopen.")
            break

    sla_status_op(status)

if __name__ == "__main__":
    hoofd()
