import requests
import json
import datetime
import os

# CONFIG
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
STATUS_FILE = "status.json"
DREMPELS = [5, 10, 15, 20, 25, 30, 35]

# Brouwersdam: 51.75, 3.87
LAT = 51.75
LON = 3.87
TIMEZONE = "Europe/Amsterdam"

# Windrichting helper
def graden_naar_richting(graden):
    richtingen = ['N', 'NO', 'O', 'ZO', 'Z', 'ZW', 'W', 'NW']
    index = round(graden / 45) % 8
    return richtingen[index]

# Wind ophalen van Open-Meteo
def get_actuele_wind():
    try:
        url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={LAT}&longitude={LON}"
            f"&current_weather=true"
            f"&hourly=wind_gusts_10m"
            f"&wind_speed_unit=kn"
            f"&forecast_hours=3"
            f"&timezone={TIMEZONE}"
        )
        response = requests.get(url)
        data = response.json()

        wind_knopen = round(data["current_weather"]["windspeed"])
        windrichting = graden_naar_richting(float(data["current_weather"]["winddirection"]))
        windstoten = round(data["hourly"]["wind_gusts_10m"][0])
        return wind_knopen, windstoten, windrichting
    except Exception as e:
        print("❌ Fout bij ophalen data:", e)
        return None, None, None

# Telegrambericht sturen
def stuur_telegram(wind, windstoot, richting):
    bericht = (
        f"💨 *WINDALARM*\n"
        f"Snelheid: {wind} knopen\n"
        f"Stoten: {windstoot} knopen\n"
        f"Richting: {richting}\n"
        f"🌐 [SWA windapp](https://jaapz30.github.io/SWA-weatherapp/)"
    )
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": bericht,
        "parse_mode": "Markdown"
    }
    response = requests.post(url, data=payload)
    print("📨 Telegram verzonden:", response.text)

# status.json inlezen
def load_status():
    if not os.path.exists(STATUS_FILE):
        return {str(d): False for d in DREMPELS} | {"datum": str(datetime.date.today())}
    with open(STATUS_FILE, "r") as f:
        return json.load(f)

# status.json opslaan
def save_status(status):
    with open(STATUS_FILE, "w") as f:
        json.dump(status, f, indent=2)

# Reset bij nieuwe dag
def reset_status(status):
    vandaag = str(datetime.date.today())
    if status.get("datum") != vandaag:
        print("🕛 Reset status.json voor nieuwe dag")
        return {str(d): False for d in DREMPELS} | {"datum": vandaag}
    return status

# Hoofdscript
def main():
    print("🚀 Script gestart")
    wind, windstoot, richting = get_actuele_wind()
    if wind is None:
        print("❌ Geen volledige data beschikbaar.")
        return

    status = load_status()
    status = reset_status(status)

    for drempel in DREMPELS:
        if wind >= drempel and not status.get(str(drempel), False):
            print(f"✅ Drempel {drempel} overschreden")
            stuur_telegram(wind, windstoot, richting)
            status[str(drempel)] = True

    save_status(status)

if __name__ == "__main__":
    main()
