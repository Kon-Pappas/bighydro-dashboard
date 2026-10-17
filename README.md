# BigHydro — Greek hydro, pumped storage and reservoir analytics

**Live:** https://kon-pappas.github.io/bighydro-dashboard/  ·  **Hub:** https://kon-pappas.github.io/

Daily-updated analytics for the Greek hydro system, built from public ADMIE/IPTO and ENTSO-E data:
reservoir levels, hydro generation by river and cascade, pumped-storage (pumping) behaviour, a stored-energy
estimate that reproduces the ENTSO-E weekly figure, and a water balance per river.

*Ελληνικά, σύντομα:* καθημερινή ανάλυση του ελληνικού υδροηλεκτρικού συστήματος από δημόσια δεδομένα ΑΔΜΗΕ και ENTSO-E:
στάθμες ταμιευτήρων, παραγωγή ανά ποταμό και καταρράκτη, άντληση (ISP έναντι SCADA), ισοδύναμο αποθηκευμένης ενέργειας
βαθμονομημένο στο εβδομαδιαίο ENTSO-E, και ισοζύγιο νερού. Όλη η τεκμηρίωση είναι στον φάκελο `docs/`.

## What the page shows
| Tab | Content |
|---|---|
| Rivers | Summary cards (visible hydro, pumping, fill level, stored energy), one card per river, cascade view per river (dam order, fill, generation, pump arrows, hourly profile), and **unit availability** (units with zero generation on at least half of the last 90 days, with a daily-generation chart) |
| Stored energy | "ENTSO-E equivalent" (calibrated) and "physical estimate" (gross head), weekly comparison with ENTSO-E, per-river table; **comparison with previous years** (2018–2025 ranges per ISO week) and **days of cover** (named rate scenarios, never one number) |
| Pumping | SCADA vs ISP pumping, per-plant estimate (Sfikia, Thesavros), monthly table; and a **pumped-storage section**: how much of the water each plant turbines had been pumped up first (recycled share, volume closure) |
| Water balance | Apparent inflow (storage change + turbined water) for all six rivers, with an "All rivers" overview: stacked monthly bars, total line and table |
| Kastraki | Level history and daily storage change of the Kastraki lake |

## How it works (one paragraph)
`scripts/update_hydro.py` fetches ADMIE files (reservoir filling rate, SCADA, ISP, RESMV) and ENTSO-E day-ahead prices, normalises every
hourly series to **Greek local time**, and writes one JSON file per day in `data/days/`. Three small scripts then derive weekly ENTSO-E
reservoir energy (`fetch_entsoe_reservoir.py`), the water balance (`build_water_balance.py`), the pumped-storage data (`build_psh.py`), the unit availability (`build_unit_status.py`), the comparison with previous years (`build_climatology.py`) and, manually, the stored-energy factors
(`calibrate_energy.py`). The page is a single `index.html` with no dependencies that reads those JSON files.
Details: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Repository map
```
index.html                     the whole page (HTML + CSS + JS, no external libraries)
scripts/update_hydro.py        daily pipeline (ADMIE + ENTSO-E prices)  → data/days, index, history, pump_daily
scripts/fetch_entsoe_reservoir.py   weekly ENTSO-E 16.1.D stored energy  → data/entsoe_reservoir.json
scripts/build_water_balance.py      apparent inflow per river            → data/water_balance.json
scripts/build_psh.py                recycled vs river water (Sfikia, Thesavros) → data/psh_daily.json
scripts/build_unit_status.py        daily generation per unit            → data/unit_daily.json
scripts/build_climatology.py        stock vs previous years (ENTSO-E)    → data/climatology.json
scripts/diagnose_admie_history.py   read-only check of ADMIE's historical files (manual workflow)
scripts/calibrate_energy.py         MANUAL: stored-energy factors        → data/energy_factors.json  (needs scipy)
data/days/YYYY-MM-DD.json      one file per day (hourly rows + reservoir levels + status)
data/*.json                    derived and static files (see docs/DATA_DICTIONARY.md)
docs/                          architecture, data dictionary, methods, decisions, known issues, roadmap
tests/                         Python pipeline tests + jsdom page tests (run in CI)
.github/workflows/             fetch_data.yml (daily update), tests.yml (tests on code changes)
```

## Daily schedule
The update is triggered by an external scheduler (cron-job.org) calling the `Daily BigHydro Fetcher` workflow at
**07:15, 09:15 and 10:15 Athens time** (a 13:30 safety run is recommended). The times follow ADMIE's publication times
(observed 11/10/2026): ISP for day D ≈ 00:25 on D · reservoir levels for D ≈ 08:35 on D · SCADA for D ≈ 06:05 on D+1 · RESMV for D ≈ 10:05 on D+1.
Each run re-reads the last 4 days, so a late file is picked up by the next run. GitHub's own `schedule` trigger (04:17 UTC) exists in the
workflow but has not been observed to fire.

## Manual runs and backfills
Actions → *Daily BigHydro Fetcher* → *Run workflow*. Inputs: `start_date`, `end_date` (empty = last 4 days), `only` (comma list of
`reservoir, scada, isp, resmv, mcp`; empty = all) and `diagnose` (prints file structure and all labels, writes nothing).
Keep a run to roughly **120 requests or fewer**: about 4 per day for `scada,isp`, 2 per day for a single ADMIE source, 1 per day for `mcp`.
A re-run overwrites old values with new non-null values; a missing value never erases an existing one.

## Tests
`python tests/run_all.py` (pipeline, 207 checks) and `node tests/dashboard/run.js` after `npm install --prefix tests/dashboard`
(page, ~245 checks, uses the real data in `data/`). Both run automatically on pushes that touch code. See [tests/README.md](tests/README.md).
A failing test never blocks the daily data update.

## Read this before trusting a number
* **RESMV** (medium-voltage small hydro) is published by ADMIE as *uncertified* measurements.
* **"ENTSO-E equivalent" energy** is a calibrated estimate (total error ≈ 0.17 %, per river ±10–20 %); it is not an official figure.
* **Heads and efficiencies** (`data/plant_heads.json`) come from unofficial documents and are approximate.
* **Water balance** shows *apparent* inflow: natural inflow minus whatever is not measured (irrigation, evaporation, spills).
* Several days have known data gaps or clock offsets: [docs/KNOWN_ISSUES.md](docs/KNOWN_ISSUES.md).

## Documentation index
[ARCHITECTURE](docs/ARCHITECTURE.md) · [DATA_DICTIONARY](docs/DATA_DICTIONARY.md) · [METHODS](docs/METHODS.md) ·
[DOMAIN_NOTES](docs/DOMAIN_NOTES.md) · [SOURCES](docs/SOURCES.md) · [QUESTIONS](docs/QUESTIONS.md) · [DECISIONS](docs/DECISIONS.md) · [KNOWN_ISSUES](docs/KNOWN_ISSUES.md) · [ROADMAP](docs/ROADMAP.md)

*Independent analysis, not affiliated with ADMIE/IPTO, PPC or ENTSO-E. No investment or operational advice.*
