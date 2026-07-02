# Vedligehold af fysisk funktionsnedsættelse

Vedligeholder forløbsindplacering for borgere med fysisk funktionsnedsættelse i KMD Nexus ved at oprette en vedvarende indsats når en ophørende indsats nærmer sig sin slutdato, og derefter afslutte den tidligere indsats.

## Hvad gør robotten?

1. Henter borgere med ophørende "fysisk funktionsnedsættelse"-indsatser fra Nexus-databasen og tilføjer dem til arbejdskøen med CPR og indsats-ID.
2. For hver borger i køen hentes borgerdata fra KMD Nexus.
3. Undersøger om borgeren allerede har en aktiv "Fysisk funktionsnedsættelse vedvarende"-indsats under forløbet "ÆHF - Forløbsindplacering (Grundforløb)".
4. Hvis ingen vedvarende indsats findes, oprettes en ny "Fysisk funktionsnedsættelse vedvarende"-indsats med dags dato som oprettelses- og faktureringsstartdato.
5. Afslutter den tidligere ophørende indsats ved at sætte fakturerings- og bevillingens slutdato til i går.
6. Fejl ved behandling rapporteres til rapport-id `vedligehold_af_fysisk_funktionsnedsaettelse` og arbejdsemnet markeres som fejlet.

## Forudsætninger

- Python ≥ 3.13
- [`uv`](https://docs.astral.sh/uv/) til pakkehåndtering
- Adgang til **Automation Server** (arbejdskø og credentials)
- Adgang til **KMD Nexus** (produktion og database)
- Adgang til **Odense SQL Server**

## Installation

```sh
uv sync
```

## Konfiguration

Credentials registreres i Automation Server:

- `KMD Nexus - produktion`
- `KMD Nexus - database`
- `Odense SQL Server`

| Miljøvariabel | Beskrivelse |
|---|---|
| `ATS_URL` | URL til Automation Server API (f.eks. `http://localhost/api`) |
| `ATS_TOKEN` | Bearer token til autentificering mod Automation Server |
| `ATS_WORKQUEUE_OVERRIDE` | Overstyr arbejdskø-ID (valgfri) |

## Kørsel

```sh
uv run python main.py --queue   # Fyld arbejdskøen med borgere med ophørende indsatser
uv run python main.py           # Behandl borgere i arbejdskøen
```

## Afhængigheder

| Pakke | Formål |
|---|---|
| `automation-server-client` | Håndtering af arbejdskø, arbejdsemner og credentials via Automation Server |
| `kmd-nexus-client` | API-klient til KMD Nexus for hentning og opdatering af borgere og indsatser |
| `nexus-database-client` | Databaseklient til Nexus for forespørgsler om ophørende indsatser |
| `odk-tools` | Sporing (Tracker) og fejlrapportering (report) |
| `ruff` | Kode-linting |

## GDPR og sikkerhed

Processen behandler CPR-numre på borgere med fysisk funktionsnedsættelse samt deres indsats-ID'er fra KMD Nexus. Oplysningerne anvendes udelukkende til at identificere og opdatere forløbsindplaceringen i Nexus og gemmes ikke lokalt. Fejlrapporter tilgås via Automation Server under rapport-id `vedligehold_af_fysisk_funktionsnedsaettelse`.
