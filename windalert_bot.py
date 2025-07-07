import requests
import json
import datetime
import os

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def graden_naar_windrichting(graden):
    richtingen = ['Noord', 'NNO', 'NO', 'ONO', 'Oost', 'OZO', 'ZO', 'ZZO',
                  'Zuid', 'ZZW', 'ZW', 'WZW', 'West', 'WNW', 'NW', 'NNW']
    index = int((graden + 11.25) / 22.5) % 16
    return richtingen[index]

def verzend_telegrambericht(snelheid, richting):
    bericht = f"💨 *WINDALARM*\nSnelheid: {snelheid} knopen\nRichting: {richting}\n🌐 [SWA windapp](https://jaapz30.github.io/SWA-weatherapp/)"
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        data={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": bericht,
            "parse_mode": "Markdown"
        }
    )

def main():
    response = requests.get("https://api.open-meteo.com/v1/forecast?latitude=52.6&longitude=5.6&current=wind_speed_10m,wind_direction_10m&wind_speed_unit=kn")
    data = response.json()
    wind_kts = round(data["current"]["wind_speed_10m"])
    richting = graden_naar_windrichting(data["current"]["wind_direction_10m"])

    with open("status.json", "r") as f:
        status = json.load(f)

    vandaag = datetime.datetime.now().strftime("%Y-%m-%d")
    if status["datum"] != vandaag:
        status = {
            "datum": vandaag,
            "5": False, "10": False, "15": False, "20": False,
            "25": False, "30": False, "35": False, "40": False
        }

    voor_waarden = [15, 20, 25, 30, 35]
    for waarde in voor_waarden:
        if wind_kts >= waarde and not status[str(waarde)]:
            verzend_telegrambericht(wind_kts, richting)
            status[str(waarde)] = True

    with open("status.json", "w") as f:
        json.dump(status, f, indent=2)

main()
