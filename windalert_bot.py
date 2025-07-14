import requests
import json
import datetime
import os

# CONFIGURATIE
WEERLIVE_API_KEY = os.environ.get("WEERLIVE_API_KEY")  # Zet dit als secret
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

DREMPELS = [2, 5, 10, 15, 20, 25, 30, 35]
STATUS_FILE = "status.json"

# Hulpfunctie: graden naar windrichting
def graden_naar_richting(graden):
    richtingen = ['N', 'NO', 'O', 'ZO', 'Z', 'ZW', 'W', 'NW']
    index = round(graden / 45) % 8
    return richtingen[index]

# Live wind ophalen van WeerLive en Open-Meteo
def get_actuele_wind():
    try:
        wl_url = f"https://weerlive.nl/api/weerlive_api_v2.php?key={WEERLIVE_API_KEY}&locatie=Marknesse"
        om_url = "https://api.open-meteo.com/v1/forecast?latitude=52.613&longitude=5.747&current_weather=true&hourly=wind_gusts_10m&wind_speed_unit=kn&forecast_hours=1&timezone=Europe/Amsterdam"

        wl_data = requests.get(wl_url).json()
        om_data = requests.get(om_url).json()

        live = wl_data["liveweer"][0]
        wind = round(float(live["windknp"]))
        gust = round(float(live.get("windknpmax") or om_data["hourly"]["wind_gusts_10m"][0]))
        richting = graden_naar_richting(om_data["current_weather"]["winddirection"])

        print(f"🌬️ Huidige wind: {wind} kn, gust: {gust} kn, richting: {richting}")
        return wind, gust, richting
    except Exception as e:
        print("❌ Fout bij ophalen data:", e)
        return None, None, None

# Bericht sturen via Telegram
def stuur_telegram(wind, gust, richting):
    bericht = (
        f"💨 *WINDALARM*\n"
        f"Snelheid: {wind} knopen\n"
        f"Windstoot: {gust} knopen\n"
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
    print("📤 Telegram verzonden:", response.text)

# Laad of initialiseer status.json
def load_status():
    if not os.path.exists(STATUS_FILE):
        print("📄 status.json nog niet aanwezig, maken...")
        return {str(d): False for d in DREMPELS} | {"datum": str(datetime.date.today())}
    with open(STATUS_FILE, "r") as f:
        return json.load(f)

# Sla status.json op
def save_status(status):
    with open(STATUS_FILE, "w") as f:
        json.dump(status, f, indent=2)
        print("💾 status.json opgeslagen")

# Reset bij nieuwe dag
def reset_status(status):
    vandaag = str(datetime.date.today())
    if status.get("datum") != vandaag:
        print("🔁 Nieuwe dag - status reset")
        return {str(d): False for d in DREMPELS} | {"datum": vandaag}
    return status

# Hoofdscript
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
            print(f"✅ Drempel {drempel} overschreden")

