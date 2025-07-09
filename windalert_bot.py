import requests
import json
import os
from datetime import datetime

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

DREMPELS = [5, 10, 15, 20, 25, 30, 35]

def graden_naar_windrichting(graden):
    richtingen = ['Noord', 'NNO', 'NO', 'ONO', 'Oost', 'OZO', 'ZO', 'ZZO',
                  'Zuid', 'ZZW', 'ZW', 'WZW', 'West', 'WNW', 'NW', 'NNW']
    index = int((graden + 11.25) / 22.5) % 16
    return richtingen[index]

def haal_wind_knmi():
    try:
        response = requests.get("https://windverwachting.nl/actuele-wind.php?plaatsnaam=Marknesse", headers={"User-Agent": "Mozilla/5.0"})
        html = response.text
        wind = float(html.split('Gemeten wind')[1].split('knopen')[0].split('>')[-1].strip())
        richting = html.split('actual__windarrowtext">')[1].split('</div>')[0].strip()
        return wind, richting
    except Exception as e:
        print("Fout bij ophalen KNMI:", e)
        return None, None

def haal_windstoot_fallback():
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

    wind, richting = haal_wind_knmi()
    windstoot = haal_windstoot_fallback()
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