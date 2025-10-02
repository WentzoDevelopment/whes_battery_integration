# WHES Battery (EMS + Ammeter) – Home Assistant integratie


Leest elke 60s de **WHES OpenAPI** (EU datacenter by default) en maakt sensoren aan voor EMS en Ammeter.

## Sensoren



## Installatie (HACS)
1. HACS → Integrations → 3‑puntjes → **Custom repositories** → voeg jouw repo‑URL toe, Category: Integration.
2. Installeer **WHES Battery (EMS + Ammeter)**.
3. Home Assistant herstarten.
4. Instellingen → Apparaten & Diensten → **Integratie toevoegen** → WHES Battery.
5. Vul **API Key**, **API Secret**, **Project ID**, **Device ID**, **Ammeter ID** in. Optioneel: **Base URL**.


## Opmerking over waarden
- EMS sensoren publiceren de laatst beschikbare sample in het 60s‑window.
- Ammeter vermogens worden **genormaliseerd** (teken omgedraaid) zodat import/afname positief wordt.
- Polling interval staat op 60s; wil je iets anders, pas `DEFAULT_UPDATE_SECONDS` aan in `const.py`.