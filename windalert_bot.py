import requests
import json
import os
from datetime import datetime
from bs4 import BeautifulSoup

DREMPELS = [0]  # TESTMELDING: overschrijdt altijd drempel
STATUS_FILE = "status.json"
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def graden_naar_windrichting(graden):
    richtingen = ['Noord', 'NNO', 'NO', 'ONO', 'Oost', 'OZO', 'ZO', 'ZZO',
                  'Zuid', 'ZZW', 'ZW', 'WZW', 'West', 'WNW', 'NW', 'NNW']
    index = int((graden + 11.25) / 22.5) % 16
    return richtingen[index]

def verzend_telegrambericht(snelheid, windstoten, richting, temperatuur, bron):
    bericht = (
        "💨 *SWA WINDALERT*\n"
        f"📡 Bron: {bron}\n"
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

def haal_windgegevens_op():
    # 🔹 PROBEER KNMI
    try:
        print("📡 KNMI ophalen...")
        url = "https://api.dataplatform.knmi.nl/open-data/v1/datasets/actuele10mindataKNMIstations/versions/2/files"
        headers = { "Authorization": "APIKey 4ee734442fcf56855889e78e58e5d874" }
        response = requests.get(url, headers=headers)
        files = response.json().get("files", [])
        if not files:
            raise ValueError("Geen bestanden bij KNMI.")

        latest_file = files[0]["filename"]
        file_url = f"{url}/{latest_file}/url"
        download_response = requests.get(file_url, headers=headers)
        download_link = download_response.json()["temporaryDownloadUrl"]
        bestand = requests.get(download_link).text

        for regel in bestand.splitlines():
            if regel.startswith("275"):
                velden = regel.split(",")
                snelheid_ms = float(velden[9]) / 10
                windstoot_ms = float(velden[10]) / 10
                richting_graden = int(velden[11])
                temperatuur = float(velden[6]) / 10

                return (
                    round(snelheid_ms * 1.94384),
                    round(windstoot_ms * 1.94384),
                    graden_naar_windrichting(richting_graden),
                    round(temperatuur),
                    "KNMI"
                )
        raise ValueError("Geen data voor station 275.")

    except Exception as e:
        print(f"⚠️ KNMI mislukt: {e}")

    # 🔸 FALLBACK: WINDFINDER
    try:
        print("🌐 Probeer fallback via Windfinder...")
        url = "https://www.windfinder.com/weatherforecast/schokkerhaven"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.content, "html.parser")

        wind_el = soup.find("div", class_="actual__wind")
        snelheid = int(wind_el.find("span", class_="speed").text.strip().replace("kt", "").strip())

        gust_txt = wind_el.find("span", class_="gusts").text.strip().replace("Gusts", "").replace("kt", "").strip()
        windstoot = int(gust_txt) if gust_txt else snelheid

        temp_el = soup.find("span", class_="actual__temperature")
        temperatuur = int(temp_el.text.strip().replace("°C", "").strip())

        richting = wind_el.find("span", class_="dir").text.strip() or "Onbekend"

        return snelheid, windstoot, richting, temperatuur, "Windfinder"

    except Exception as e:
        print(f"❌ Windfinder fallback faalde ook: {e}")
        return 0, 0, "Onbekend", 0, "GEEN DATA"

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
        print("🌙 Statusbestand gereset.")
        return

    snelheid, windstoten, richting, temperatuur, bron = haal_windgegevens_op()
    print(f"✅ Data: {snelheid} knopen, Gusts {windstoten}, {richting}, {temperatuur}°C via {bron}")

    status = laad_status()

    for drempel in DREMPELS:
        sleutel = f"melding_{drempel}"
        if snelheid >= drempel and not status.get(sleutel, False):
            verzend_telegrambericht(snelheid, windstoten, richting, temperatuur, bron)
            status[sleutel] = True
            print(f"📤 Melding verzonden voor {drempel} knopen.")
            break

    sla_status_op(status)

if __name__ == "__main__":
    hoofd()
