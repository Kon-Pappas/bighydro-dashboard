# Architecture

## Data flow
```
ADMIE (getOperationMarketFile)           ENTSO-E Transparency
  ReservoirFillingRate  (levels)           A44 day-ahead price, zone 10YGR-HTSO-----Y   (MCP)
  SystemRealizationSCADA (actual MW)       16.1.D weekly stored energy (A72/A16)
  ISP2ISPResults        (schedule)                       │
  RESMV                 (MV small hydro)                  │
        │                                                  │
        ▼                                                  ▼
 scripts/update_hydro.py  ───────────────►  data/days/YYYY-MM-DD.json   (one file per day)
        │  rebuild_derived()                        │
        ▼                                           ▼
 data/index.json, reservoir_history.json,   scripts/fetch_entsoe_reservoir.py → data/entsoe_reservoir.json
 pump_daily.json, monthly/*.json            scripts/build_water_balance.py   → data/water_balance.json
                                            scripts/calibrate_energy.py (manual) → data/energy_factors.json
        └──────────────────────────────────────────┬──────────────────────────────┘
                                                   ▼
                                  index.html (static page, fetch() of the JSON files)
```

## Workflow (`.github/workflows/fetch_data.yml`)
Steps run in this order, in one job (`concurrency: bighydro-fetch`, runs never overlap):
1. `update_hydro.py` — main fetch. **A failure here stops the job.**
2. `fetch_entsoe_reservoir.py` — weekly ENTSO-E series (`continue-on-error`).
3. `build_water_balance.py` — water balance (`continue-on-error`).
4. Commit and push `data/` if anything changed (`git pull --rebase` first).

Inputs: `start_date`, `end_date`, `only`, `diagnose`. Secret: `ENTSOE_TOKEN`. Python 3.12; the job installs `pandas numpy requests openpyxl xlrd`.
`calibrate_energy.py` needs `scipy` and is **not** part of the daily job.

## Pipeline rules (update_hydro.py)
* **One file per day.** `data/days/YYYY-MM-DD.json` holds the 00:00 reservoir readings, 24 hourly rows and a `Meta` block with a status per source.
* **Lookback.** With no dates given, a run processes today−3 … today. A file published late is picked up by a later run.
* **`null` ≠ `0`.** A missing value is `null`. A new `null` never overwrites an existing value; a new non-null value always does, so a wrong day is fixed by re-running it.
* **Status per source:** `ok` (all 24 hours), `partial`, `missing`. Missing sources are listed in the page banner.
* **Corrupt day file** → the run stops and leaves it untouched.
* **`--only`** (or env `ONLY`) restricts which sources are fetched; everything else in the file is preserved.
* **`--diagnose`** prints the structure of the ADMIE/ENTSO-E files, unit matching, reconciliation and the full list of row labels; it writes nothing.
* **Reconciliation.** `TotalHydro − (16 units + Stratos II + Makrochori + Louros + Gkiona)` must be ≈ 0 (tolerance 3 MW); in 2026 it is exactly 0.000 MW.
* **Derived files** are rebuilt from all day files at the end of every run: `index.json`, `reservoir_history.json`, `pump_daily.json`, `monthly/*.json`.

## Clock conventions (important)
All hourly series are stored on **Greek local time** (Europe/Athens): `H01` = 00:00–01:00 local.

| Source | Published on | Handling |
|---|---|---|
| SCADA, RESMV | Greek local time | stored as is |
| ISP (96 quarter-hours) | market time (CET/CEST) | averaged per hour and shifted **+1 h**; `H01` therefore needs the **previous day's** ISP file (its last market hour) |
| MCP (ENTSO-E, PT15M, curve type A03 = compressed) | market time | requested with an Athens midnight-to-midnight window, quarter-hours averaged per hour, forward-filled where compressed |
| Reservoir levels | a reading at 00:00 of day D | `ΔV` for day D = reading(D+1) − reading(D) |

Verified over 288 days: the median SCADA–ISP correlation at lag 0 is 0.984. Daylight-saving days are the weak point: see `KNOWN_ISSUES.md` (29–30/3 and 25/10).

## Publication times (Athens, observed Sunday 11/10/2026)
ISP2 for day D ≈ 00:25 on D · Reservoir Filling Rate for D ≈ 08:35 on D · SCADA ("Unit Production and System Facts") for D ≈ 06:05 on D+1 · RESMV for D ≈ 10:05 on D+1.
The 10:15 run has only ~10 minutes of margin for RESMV, hence the recommended 13:30 safety run.

## The page (index.html)
One self-contained file: CSS variables, vanilla JS, hand-written SVG charts, no external libraries. It `fetch()`es the JSON files with relative paths,
so it must be served over http(s) (GitHub Pages), not opened as a local file.
* **Look:** dark slate base shared with the other dashboards; the accent colour is the single variable `--acc` (violet); chart colours are `--c1` (sky), `--c2` (amber), `--c3` (emerald).
* **Shell:** breadcrumb to the hub, title, *Last Update* (newest `Updated` of the latest days in `index.json`), *Next Update* (from the `RUN_TIMES` constant), a *Complete/Partial Data* badge and banner for the selected day (reservoir, SCADA, ISP, RESMV only), footer with sources and disclaimer.
* **Loading overlay:** `boot()` reads the eight JSON files (progress bar 1), then `load(date, hook)` renders the five tabs one at a time and the hook fills one overlay row per tab; deliberate pauses (`STEP`, `MIN_READ`, `READY_MS`) keep each step visible (about 3.5 s in total) and are zero when `window.__BH_FAST` is set (tests).
* **Modals:** one component (`modalHtml`) builds a fixed header (title, boxed ✕), a scrolling body and a fixed footer (boxed Close); `openModal`/`closeModal` also lock the page scroll, and Escape or a click on the backdrop closes them. The river modal also carries the date navigation (select, previous/next, arrow keys): `gotoDay` reloads the page data and re-renders the open modal in place.
* **Language:** English by default; a two-option switch **GR | EN** with the active option highlighted; the choice is stored in `localStorage` under the shared key `kp_lang` (the legacy key `bh_lang` is still read).
* **Days:** `dayList()` returns only the days in `index.json` that have reservoir levels (all calculations rest on them); the date selectors, the river-modal navigation and the default day use it, and `load()` falls back to the latest available day (with a notice) when asked for another one.
* **Tooltips:** every chart registers its scales and series; a delegated pointer handler finds the nearest point and shows a tooltip plus a crosshair (works with touch; `touch-action: pan-y` keeps vertical scrolling).
Energy for any day is computed **in the browser** from `energy_factors.json` and `reservoir_history.json`, so new days appear without re-running the calibration.
For testing, the page exposes `window.__bh` (state and helpers).
