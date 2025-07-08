import requests
import json
import os
from datetime import datetime
from bs4 import BeautifulSoup

DREMPELS = [5, 10, 15, 20, 25, 30, 35]
STATUS_FILE = "status.json"
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def graden_naar_windrichting(graden):
    richtingen = ['Noord', 'NNO', 'NO', 'ONO', 'Oost', 'OZO', 'ZO', 'ZZO',
                  'Zuid', 'ZZW', 'ZW', 'WZW', 'West', 'WNW', 'NW', 'NNW']
    index = int((graden + 11.25) / 22.5) % 16
    return richtingen[index]

def verzend_telegrambericht(snelheid, windstoten, richting, temperatuur):
    bericht = (
        "💨 *SWA WINDALERT*\n"
        f"🌬️ Wind: {snelheid} knopen ({richting})\n"
        f"🌪️ Windstoten: {windstoten} knopen\n"
        f"🌡️ Temperatuur: {temperatuur} °C\n"
        "🌐 [SWA windapp](https://jaapz30.github.io/SWA-weatherapp/)"
    )
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": bericht,
        "parse_mode": "Markdown"
    }
    response = requests.post(url, data=payload)
    print("✅ Telegram melding verzonden:", response.status_code, response.text)

def verzend_telegram_foutmelding():
    bericht = (
        "⚠️ *SWA WINDALERT*\n"
        "Er is geen actuele winddata beschikbaar van KNMI of Windfinder.\n"
        "Controleer handmatig op storing of wijziging.\n"
        "🌐 [SWA windapp](https://jaapz30.github.io/SWA-weatherapp/)"
    )
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": bericht,
        "parse_mode": "Markdown"
    }
    response = requests.post(url, data=payload)
    print("⚠️ Telegram foutmelding verzonden:", response.status_code, response.text)

def haal_windgegevens_op():
    # 1. KNMI proberen
    try:
        print("📡 KNMI ophalen...")
        url = "https://api.dataplatform.knmi.nl/open-data/v1/datasets/actuele10mindataKNMIstations/versions/2/files"
        headers = { "Authorization": "APIKey 4ee734442fcf56855889e78e58e5d874" }
        response = requests.get(url, headers=headers)
        files = response.json().get("files", [])
        if not f
