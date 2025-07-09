import requests
import json
import os
from datetime import datetime

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
WEERLIVE_API_KEY = os.getenv("WEERLIVE_API_KEY")

DREMPELS = [5, 10, 15, 20, 25, 30, 35]

def haal_weerlive_data():
    try:
        url = f"https://weerlive.nl/api/json-data-10min.php?key={WEERLIVE_API_KEY}&locatie=Marknesse"
        data = requests.get(url).json()
        live = data["liveweer"][0]
        wind_m_s = float(live["winds"])  # winds = wind in m/s
        wind_knopen = round(wind_m_s * 1.94384, 1)  # m/s naar knopen
        richting = live["windr"]  # windrichting als tekst, bv. 'ZW'
        return wind_knopen, richting
    except Exception as e:
        print("Fout bij ophalen Weerlive:", e)
        return None, None

def haal_windstoot_openmeteo():
    try:
        url = "https://api.open-meteo.com/v1/dwd-icon?latitude=52.7&longitude=5.9&current=wind_gusts_10m&windspeed_unit=kn"
        data = requests.get(url).json()
        return round(data["current"]["wind_gusts_10m"], 1)
    except Exception as e:
        print("Fout bij ophalen windstoot:", e)
        return None

def verzend_telegrambericht(knopen, richting, windstoot):
    bericht = f"""💨 *WINDALARM*
Snelheid: {knopen} knopen
Richting: {richting}
🌪️ Windstoten: {windstoot} knopen
🌐 [SWA windapp](https://jaapz30.github.io/SWA-weatherapp/)"""
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": bericht,
            "parse_mode": "Markdown"
        }
    )

def main():
    today = datetime.now().strftime("%Y-%m-%d")
    with open("status.json", "r") as f:
        status = json.load(f)

    if status.get("datum") != today:
        status = {"datum": today}
        for d in DREMPELS:
            status[str(d)] = False

    wind, richting = haal_weerlive_data()
    windstoot = haal_windstoot_openmeteo()
    if not wind or not richting or not windstoot:
        print("Geen volledige data beschikbaar.")
        return

    for drempel in DREMPELS:
        if wind >= drempel and not status[str(drempel)]:
            verzend_telegrambericht(wind, richting, windstoot)
            status[str(drempel)] = True

    with open("status.json", "w") as f:
        json.dump(status, f, indent=2)

if __name__ == "__main__":
    main()
