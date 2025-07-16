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
WEERLIVE_API_KEY = os.environ.get("WEERLIVE_API_KEY")

# 📍 Configuratie
STATION_KNMI = "330"  # Vlissingen
LAT = 51.75
LON = 3.87
KNOT_CONV = 0.539957

# 🌬️ Gemeten wind uit Renesse (WeerLive)
def get_renesse_wind():
    try:
        url = f"https://weerlive.nl/api/json-data-10min.php?key={WEERLIVE_API_KEY}&locatie=Renesse"
        data = requests.get(url).json()
        live = data["liveweer"][0]
        wind_ms = float(live["winds"])
        wind_kn = round(wind_ms * 1.94384)
        richting = int(live["windrgr"])
        return wind_kn, richting
    except Exception as e:
        print("❌ Fout bij WeerLive:", e)
        return None, None

# 🌬️ Windstoten uit KNMI Vlissingen
def get_knmi_gust():
    try:
        headers = {"Authorization": f"Bearer {KNMI_API_KEY}"}
        base_url = "https://api.dataplatform.knmi.nl/open-data/v1/datasets/actuele10mindata-knmi/versions/2/files"
        files = requests.get(base_url, headers=headers).json()["files"]
        latest_file = sorted(files, key=lambda x: x["name"], reverse=True)[0]
        file_url = latest_file["url"]

        response = requests.get(file_url, headers=headers)
        with gzip.GzipFile(fileobj=BytesIO(response.content)) as gz:
            wrapper = TextIOWrapper(gz, encoding="utf-8")
            reader = csv.DictReader(wrapper, delimiter=";")
            for row in reader:
                if row["STN"] == STATION_KNMI:
                    gust_kmh = int(row["FX"])
                    gust_kn = round(gust_kmh * KNOT_CONV)
                    return gust_kn
    except Exception as e:
        print("❌ Fout bij KNMI gust:", e)
        return None

# 🔁 Fallback via Open-Meteo
def get_openmeteo():
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}&current_weather=true&hourly=wind_gusts_10m&wind_speed_unit=kn&forecast_hours=1&timezone=Europe/Amsterdam"
        data = requests.get(url).json()
        wind = round(data["current_weather"]["windspeed"])
        gust = round(data["hourly"]["wind_gusts_10m"][0])
        richting = data["current_weather"]["winddirection"]
        print("⚠️ Open-Meteo fallback gebruikt")
        return wind, gust, richting
    except Exception as e:
        print("❌ Fout bij Open-Meteo:", e)
        return None, None, None

# 📩 Telegrambericht sturen
def stuur_telegram(wind, gust, richting):
    bericht = f"💨 *WINDALARM*\nSnelheid: {wind} knopen\nStoten: {gust} knopen\nRichting: {richting}°"
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": bericht,
        "parse_mode": "Markdown"
    }
    requests.post(url, data=payload)
    print("✅ Bericht verzonden")

# 🧠 Hoofdprogramma
def main():
    uur = datetime.datetime.now().hour
    if uur in [7, 10, 13, 16, 19, 21, 22]:
        wind, richting = get_renesse_wind()
        gust = get_knmi_gust()

        if wind is None or gust is None or richting is None:
            wind, gust, richting = get_openmeteo()

        if wind is not None and gust is not None:
            stuur_telegram(wind, gust, richting)
        else:
            print("❌ Geen winddata beschikbaar.")
    else:
        print("⏰ Buiten actieve tijden.")

if __name__ == "__main__":
    print("🚀 Script gestart")
    main()
