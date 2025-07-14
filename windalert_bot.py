import requests
import json
import datetime
import os

# 📌 CONFIG
WEERLIVE_API_KEY = os.environ.get("WEERLIVE_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

LAT = 52.613
LON = 5.747
TZ = "Europe/Amsterdam"
LOCATIE = "Lelystad"

DREMPELS = [2, 5, 10, 15, 20, 25, 30, 35]
STATUS_FILE = "status.json"

# 🧭 Graden naar windrichting
def graden_naar_richting(graden):
    richtingen = ['N', 'NO', 'O', 'ZO', 'Z', 'ZW', 'W', 'NW']
    index = round(graden / 45) % 8
    return richtingen[index]

# 🌬️ Winddata ophalen
def get_actuele_wind():
    try:
        # URLs
        wl_url = f"https://weerlive.nl/api/weerlive_api_v2.php?key={WEERLIVE_API_KEY}&locatie={LOCATIE}"
        om_url = (
            f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}"
            f"&current_weather=true&hourly=wind_gusts_10m&wind_speed_unit=kn&forecast_hours=1&timezone={TZ}"
        )

        wl_data = requests.get(wl_url).json()
        om_data = requests.get(om_url).json()

        # WeerLive: wind & gust
        live = wl_data["liveweer"][0]
        wind = round(float(live.get("windknp", 0)))
        gust = round(float(live.get("windknpmax", 0)))

        # Open-Meteo: windrichting
        richting_graden = om_data["current_weather"]["winddirection"]
        richting = graden_naar_richting(richting_graden)

        # Fallbacks
        if gust == 0:
            gust = round(om_data["hourly"]["wind_gusts_10m"][0])
        if wind == 0:
            wind = round(om_data["current_weather"]["windspeed"])

        print(f"🌬️ Wind: {wind} knopen | Gust: {gust} | Richting: {richting}")
        return wind, gust, richting

    except Exception as e:
        print("❌ Fout bij ophalen data:", e)
        return None, None, None

# 📩 Telegrambericht sturen
def stuur_telegram(wind, richting):
    bericht = f"💨 *WINDALARM*\nSnelheid: {wind} knopen\nRichting: {richting}\n🌐 [SWA windapp](https://jaapz30.github.io/SWA-weatherapp/)"
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": bericht,
        "parse_mode": "Markdown"
    }
    response = requests.post(url, data=payload)
    print("📤 Telegram verzonden:", response.text)

# 📁 Statusbestand inladen
def load_status():
    if not os.path.exists(STATUS_FILE):
        return {str(d): False for d in DREMPELS} | {"datum": str(datetime.date.today())}
    with open(STATUS_FILE, "r") as f:
        return json.load(f)

# 💾 Statusbestand opslaan
def save_status(status):
    with open(STATUS_FILE, "w") as f:
        json.dump(status, f, indent=2)

# 🔄 Status resetten als dag veranderd is
def reset_status(status):
    vandaag = str(datetime.date.today())
    if status.get("datum") != vandaag:
        print("🔄 Nieuwe dag: reset status.json")
        return {str(d): False for d in DREMPELS} | {"datum": vandaag}
    return status

# 🚀 Hoofdprogramma
def main():
    print("🚀 Script gestart")
    wind, gust, richting = get_actuele_wind()
    if wind is None:
        print("❌ Geen volledige data beschikbaar.")
        return

    status = load_status()
    status = reset_status(status)

    for drempel in DREMPELS:
        if wind >= drempel and not status.get(str(drempel), False):
            print(f"✅ Drempel {drempel} knopen overschreden ({wind}). Bericht sturen.")
            stuur_telegram(wind, richting)
            status[str(drempel)] = True

    save_status(status)

if __name__ == "__main__":
    main()
