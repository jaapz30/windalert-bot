from bs4 import BeautifulSoup

def haal_windgegevens_op():
    # Eerst KNMI proberen
    url = "https://api.dataplatform.knmi.nl/open-data/v1/datasets/actuele10mindataKNMIstations/versions/2/files"
    headers = {
        "Authorization": "APIKey 4ee734442fcf56855889e78e58e5d874"
    }

    try:
        response = requests.get(url, headers=headers)
        files = response.json().get("files", [])
        if not files:
            raise ValueError("Geen KNMI-bestanden gevonden.")

        latest_file = files[0]["filename"]
        file_url = f"{url}/{latest_file}/url"
        download_response = requests.get(file_url, headers=headers)
        download_link = download_response.json()["temporaryDownloadUrl"]
        bestand = requests.get(download_link).text

        for regel in bestand.splitlines():
            if regel.startswith("275"):
                velden = regel.split(",")

                snelheid_ms = float(velden[9]) / 10
                windstoot_ms = float(velden[10]) / 10
                richting_graden = int(velden[11])
                temperatuur = float(velden[6]) / 10

                snelheid_knopen = round(snelheid_ms * 1.94384)
                windstoot_knopen = round(windstoot_ms * 1.94384)
                richting = graden_naar_windrichting(richting_graden)

                print(f"✅ Data via KNMI: {snelheid_knopen} knopen, gusts {windstoot_knopen}, {richting}, {temperatuur}°C")
                return snelheid_knopen, windstoot_knopen, richting, round(temperatuur)

        raise ValueError("Station 275 niet gevonden in KNMI-bestand.")

    except Exception as e:
        print(f"⚠️ KNMI mislukt: {e}")
        print("➡️ Probeer fallback via Windfinder...")

    # Fallback via Windfinder
    try:
        url = "https://www.windfinder.com/weatherforecast/schokkerhaven"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.content, "html.parser")

        # Vind actuele windwaarde
        wind_el = soup.find("div", class_="actual__wind")
        snelheid_kt = int(wind_el.find("span", class_="speed").text.strip().replace("kt", "").strip())

        # Vind actuele windstoten
        gust_el = wind_el.find("span", class_="gusts")
        gust_txt = gust_el.text.strip().replace("Gusts", "").replace("kt", "").strip()
        windstoot_kt = int(gust_txt) if gust_txt else snelheid_kt

        # Vind temperatuur
        temp_el = soup.find("span", class_="actual__temperature")
        temperatuur = int(temp_el.text.strip().replace("°C", "").strip())

        # Richting (bijv. NW)
        richting_txt = wind_el.find("span", class_="dir").text.strip()
        richting = richting_txt if richting_txt else "Onbekend"

        print(f"✅ Data via Windfinder: {snelheid_kt} knopen, gusts {windstoot_kt}, {richting}, {temperatuur}°C")
        return snelheid_kt, windstoot_kt, richting, temperatuur

    except Exception as e:
        print(f"❌ Windfinder fallback faalde ook: {e}")
        return 0, 0, "Onbekend", 0
