import requests
import json
import datetime
import os

# CONFIGURATIE
WEERLIVE_API_KEY = os.environ.get("WEERLIVE_API_KEY")  # Zorg dat deze als secret staat
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# Drempelwaarden (in knopen)
DREMPELS = [5, 10, 15, 20, 25, 30, 35]

# Bestanden
STATUS_FILE = "status.json"

# Hulp: graden naar windrichting
def graden_naar_richting(graden):
    richtingen = ['N', 'NO', 'O', 'ZO', 'Z', 'ZW', 'W', 'NW']
    index = round(graden / 45) % 8
    return richtingen[index]

# Wind ophalen van WeerLive API
def get_actuele_wind():
    try:
        url = f"https://weerlive.nl/api/json-data-10min.php?key={WEERLIVE_API_KEY}&locatie=Marknesse"
        response = requests.get(url)
        data = response.json()

        live = data["liveweer"][0]
        wind_knopen = round(float(live["winds"]) * 0.54, 1)
        windstoten_knopen = round(float(live["windstoten"]) * 0.54, 1)
        windrichting = graden_naar_richting(float(live["windr"]))
        return wind_knopen, windstoten_knopen, windrichting
    except Exception as e:
        print("Fout bij ophalen Weerlive:", e)
        return None, None, None

# Telegrambericht sturen
def stuur_telegram(wind, richting):
    bericht = f"💨 *WINDALARM*\nSnelheid: {wind} knopen\nRichting: {richting}\n🌐 [SWA windapp](https://jaapz30.github.io/SWA-weatherapp/)"
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": bericht,
        "parse_mode": "Markdown"
    }
    response = requests.post(url, data=payload)
    print("Telegram verzonden:", response.text)

# Laden van status.json
def load_status():
    if not os.path.exists(STATUS_FILE):
        return {str(d): False for d in DREMPELS} | {"datum": str(datetime.date.today())}
    with open(STATUS_FILE, "r") as f:
        return json.load(f)

# Opslaan van status.json
def save_status(status):
    with open(STATUS_FILE, "w") as f:
        json.dump(status, f, indent=2)

# Reset status als datum is veranderd
def reset_status(status):
    vandaag = str(datetime.date.today())
    if status.get("datum") != vandaag:
        print("Reset status.json voor nieuwe dag")
        return {str(d): False for d in DREMPELS} | {"datum": vandaag}
    return status

# Hoofdprogramma
def main():
    wind, windstoot, richting = get_actuele_wind()
    if wind is None:
        print("❌ Geen volledige data beschikbaar.")
        return

    status = load_status()
    status = reset_status(status)

    for drempel in DREMPELS:
        if wind >= drempel and not status.get(str(drempel), False):
            print(f"✅ Drempel {drempel} overschreden ({wind} knopen). Melding sturen.")
            stuur_telegram(wind, richting)
            status[str(drempel)] = True

    save_status(status)

if __name__ == "__main__":
    main()
