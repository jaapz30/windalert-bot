import requests
import datetime
import os

API_KEY = os.getenv("KNMI_API_KEY")
STATION_CODE = "273"  # Marknesse

def haal_knmi_data_op():
    vandaag = datetime.datetime.utcnow().strftime("%Y%m%d")
    bestandsnaam = f"K10{vandaag}.csv"

    print(f"➡️ Bestandsnaam: {bestandsnaam}")

    url = f"https://api.dataplatform.knmi.nl/open-data/v1/datasets/actuele10mindataKNMI/versions/2.0/files/{bestandsnaam}/url"
    headers = {"Authorization": f"Bearer {API_KEY}"}

    print(f"📡 Ophalen downloadlink...")
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"❌ Fout bij ophalen link: {response.status_code} - {response.text}")
        return

    download_url = response.json().get("temporaryDownloadUrl")
    print("✅ Downloadlink verkregen!")

    # CSV-bestand ophalen
    print("📥 Ophalen CSV-bestand...")
    csv_response = requests.get(download_url)
    if csv_response.status_code != 200:
        print(f"❌ Fout bij downloaden CSV: {csv_response.status_code}")
        return

    regels = csv_response.text.splitlines()
    for regel in reversed(regels):  # van nieuwste naar oudste
        delen = regel.split(",")
        if delen[0] == STATION_CODE:
            try:
                tijd = delen[1]
                richting = int(delen[3])
                snelheid = int(delen[4]) / 10  # m/s
                snelheid_knopen = round(snelheid * 1.94384, 1)
                print("✅ Laatste meting:")
                print(f"⏰ Tijd (UTC): {tijd}")
                print(f"🌬️ Snelheid: {snelheid_knopen} knopen")
                print(f"🧭 Richting: {richting} graden")
                return
            except:
                continue

    print("⚠️ Geen gegevens gevonden voor station 273")

if __name__ == "__main__":
    haal_knmi_data_op()
