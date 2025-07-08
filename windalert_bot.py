def haal_windgegevens_op():
    url = "https://api.dataplatform.knmi.nl/open-data/v1/datasets/actuele10mindataKNMIstations/versions/2/files"

    headers = {
        "Authorization": "APIKey 4ee734442fcf56855889e78e58e5d874"
    }

    # Stap 1: haal de nieuwste bestandsnaam op
    response = requests.get(url, headers=headers)
    files = response.json().get("files", [])
    latest_file = files[0]["filename"]

    # Stap 2: download het bestand
    file_url = f"{url}/{latest_file}/url"
    download_response = requests.get(file_url, headers=headers)
    download_link = download_response.json()["temporaryDownloadUrl"]

    bestand = requests.get(download_link).text

    # Stap 3: zoek data van station 275 (Marknesse)
    for regel in bestand.splitlines():
        if regel.startswith("275"):
            velden = regel.split(",")

            try:
                # Indexen kunnen wijzigen, dus we gebruiken kolomnamen als referentie:
                # Volgens documentatie (versie 2): 
                # veld[9] = ff (windsnelheid), veld[10] = fx (windstoot), veld[11] = dd (richting), veld[6] = T (temp)
                snelheid_ms = float(velden[9]) / 10  # ff = m/s * 10
                windstoot_ms = float(velden[10]) / 10
                richting_graden = int(velden[11])
                temperatuur = float(velden[6]) / 10  # °C * 10

                snelheid_knopen = round(snelheid_ms * 1.94384)
                windstoot_knopen = round(windstoot_ms * 1.94384)
                richting = graden_naar_windrichting(richting_graden)

                print(f"KNMI: {snelheid_knopen} knopen, gusts {windstoot_knopen}, {richting}, {temperatuur}°C")
                return snelheid_knopen, windstoot_knopen, richting, round(temperatuur)

            except Exception as e:
                print("Fout bij uitlezen regel:", e)

    # Fallback bij geen resultaat
    return 0, 0, "Onbekend", 0
