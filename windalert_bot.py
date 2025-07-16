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
        wind = round(float(live["winds"]) * 1.94384)
        gust_raw = live.get("windstoten")
        gust = round(float(gust_raw) * 1.94384) if gust_raw else None
        richting = live["windr"]
        return wind, gust, richting
    except Exception as e:
        print("❌ Fout bij ophalen winddata:", e)
        return None, None, None

# 📩 Telegrambericht sturen
def stuur_telegram(wind, gust, richting):
    bericht = f"💨 *WINDALARM*\nSnelheid: {wind} knopen"
    if gust:
        bericht += f"\nStoten: {gust} knopen"
    bericht += f"\nRichting: {richting}°"
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
    wind, gust, richting = get_winddata()
    if wind is None:
        print("❌ Geen data beschikbaar.")
        return

    uur = datetime.datetime.now().hour
    if 7 <= uur <= 22:
        stuur_telegram(wind, gust, richting)
    else:
        print("⏰ Buiten actieve uren. Geen melding verzonden.")

if __name__ == "__main__":
    main()
