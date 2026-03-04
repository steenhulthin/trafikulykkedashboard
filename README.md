# Trafikulykke-dashboard (Shiny for Python)

Interaktivt dashboard for trafikulykker med fokus på køn, skadegrad, alder og transportmiddel.

## Krav

- Python 3.13 (eller kompatibel 3.x)

valgfrit (scripts og kommandolinjer kan køre på andre måder, men er ikke testet):
- PowerShell (Windows)

## Installation

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Kør dashboard lokalt (udvikling)

```powershell
.\.venv\Scripts\python.exe -m shiny run .\trafikulykker\app.py --reload
```

## Klargør data (valgfrit)

Hvis du vil regenerere den bearbejdede datamodel fra Excel:

```powershell
.\.venv\Scripts\python.exe .\data\prepare_ligehi10.py --structure long --format parquet
```

Output skrives som standard til `data/processed/ligehi10_long.parquet`.

## Eksport til Shinylive

Projektet har en hjælpe-scriptfil:

```powershell
.\shinyliveexport2docs.ps1
```

Den kører:

```powershell
shinylive export .\trafikulykker\ .\docs\
```

Efter eksport ligger den statiske Shinylive-app i `docs/`.

## Kør den eksporterede Shinylive-app lokalt

Brug hjælpe-scriptet:

```powershell
.\shinyliveserve.ps1
```

Det svarer til:

```powershell
python -m http.server --directory docs --bind localhost 8008
```

Åbn derefter `http://localhost:8008` i din browser.

## Licens

Dette projekt er licenseret under **GNU AGPL-3.0-or-later**.  
Se [LICENSE](./LICENSE) og [LICENSES/AGPL-3.0-or-later.txt](./LICENSES/AGPL-3.0-or-later.txt).

