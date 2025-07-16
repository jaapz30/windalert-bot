import requests
import os
import datetime

# 🔐 API-sleutels via GitHub Secrets
WEERLIVE_API_KEY = os.environ.get("WEERLIVE_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# 📍 Locatie
LOCATIE = "Renesse"

# 🌬️ Winddata ophalen van WeerLive
def get_winddata():
    try:
        url = f"https://weerlive.nl/api/json-data-10min.php?key={WEERLIVE_API_KEY}&locatie={LOCATIE}"
        response = requests.get(url)
        data = response.json()

        live = data["liveweer"][0]
        wind = round(float(live["windknp"]))
        gust = round(float(live.get("windknpmax") or 0))
        richting = live["windr"]
        tijd = live["time"]
        return wind, gust, richting, tijd
    except Exception as e:
        print("❌ Fout bij ophalen winddata:", e)
        return None, None, None, None

# 📩 Telegrambericht sturen
def stuur_telegram(wind, gust, richting, tijd):
    bericht = (
        f"💨 *WINDUPDATE*\n"
        f"Tijdstip: {tijd}\n"
        f"Snelheid: {wind} knopen\n"
        f"Stoten: {gust} knopen\n"
        f"Richting: {richting}°\n"
        f"🌐 [SWA windapp](https://jaapz30.github.io/SWA-weatherapp/)"
    )
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": bericht,
        "parse_mode": "Markdown"
    }
    requests.post(url, data=payload)
    print("✅ Telegrambericht verzonden")

# 🧠 Hoofdscript
def main():
    wind, gust, richting, tijd = get_winddata()
    if wind is None:
        print("❌ Geen data beschikbaar.")
        return

    # Controleer of huidige tijd binnen 07:00–22:00 valt
    uur = datetime.datetime.now().hour
    if 7 <= uur <= 22:
        stuur_telegram(wind, gust, richting, tijd)
    else:
        print("⏰ Buiten actieve uren (07:00–22:00). Geen melding verzonden.")

if __name__ == "__main__":
    main()
