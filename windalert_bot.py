import requests
import os
import datetime
import gzip
import csv
from io import BytesIO, TextIOWrapper

# 🔐 Secrets
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
KNMI_API_KEY = os.environ.get("KNMI_API_KEY")

# 📍 Station Vlissingen (330)
STATION = "330"

def get_latest_knmi_file_url():
    headers = {"Authorization": f"Bearer {KNMI_API_KEY}"}
    base_url = "https://api.dataplatform.knmi.nl/open-data/v1/datasets/actuele10mindata-knmi/versions/2/files"
    response = requests.get(base_url, headers=headers)
    files = response.json()["files"]
    latest_file = sorted(files, key=lambda x: x["name"], reverse=True)[0]
    return latest_file["url"]

def get_wind_data():
    try:
        file_url = get_latest_knmi_file_url()
        headers = {"Authorization": f"Bearer {KNMI_API_KEY}"}
        response = requests.get(file_url, headers=headers)

        with gzip.GzipFile(fileobj=BytesIO(response.content)) as gz:
            wrapper = TextIOWrapper(gz, encoding="utf-8")
            reader = csv.DictReader(wrapper, delimiter=";")
            for row in reader:
                if row["STN"] == STATION:
                    # Windstoot = FX (km/h), Wind = FXX (km/h), Richting = DDVEC
                    gust = int(row["FX"])
                    wind = int(row["FXX"])
                    direction = row["DDVEC"]
                    return wind, gust, direction
    except Exception as e:
        print("❌ Fout bij ophalen KNMI data:", e)
        return None, None, None

def stuur_telegram(wind, gust, richting):
    bericht = f"💨 *WINDALARM*\nSnelheid: {wind} km/u\nStoten: {gust} km/u\nRichting: {richting}°"
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": bericht,
        "parse_mode": "Markdown"
    }
    requests.post(url, data=payload)
    print("✅ Bericht verzonden")

def main():
    uur = datetime.datetime.now().hour
    if 7 <= uur <= 22 and uur % 3 == 1:  # Alleen bij 7:00, 10:00, 13:00, 16:00, 19:00, 22:00
        wind, gust, richting = get_wind_data()
        if wind is not None:
            stuur_telegram(wind, gust, richting)
        else:
            print("❌ Geen data beschikbaar.")
    else:
        print("⏰ Buiten actieve tijden.")

if __name__ == "__main__":
    main()
