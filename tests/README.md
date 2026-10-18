# Tests

Two suites, both run in CI (`.github/workflows/tests.yml`) when code or tests change. They never run on the daily data commits, and a failing test never blocks the daily update.

## Pipeline (Python) — `python tests/run_all.py`
Needs `pandas numpy requests openpyxl xlrd` (see `requirements.txt`). Exit code is non-zero if any check fails. Fixtures are built in memory (synthetic ADMIE workbooks and ENTSO-E XML); no network, no repository data are read.
| File | Covers |
|---|---|
| `test_v3.py` | main pipeline: parsing, clock shift, merging rules, reconciliation, status flags, derived files. **Also provides the fixtures** the next three files reuse |
| `test_only.py` | `--only` / `ONLY` source selection, date env variables |
| `test_perunit.py` | per-unit small hydro, per-plant ISP pumping, `(ΜΥΗΣ)` rows in the renewables block |
| `test_pump.py` | SCADA/ISP pump split logic and `pump_daily.json` |
| `test_admie_formats.py` | formats diagnose with simulated old-format files: missing and unmatched reservoir labels (a renamed Stratos), SCADA unit matching and differently named total rows, duplicate files with their record fields, a non-Excel file, network down, read-only |
| `test_admie_diag.py` | ADMIE history diagnose with a simulated API: the probe of addresses and window sizes (including the real case where the default address answers long windows with an empty list), scans with 366-day, 31-day and single-day windows, samples parsed with the pipeline's own parsers (complete and incomplete files), read-only, never raises |
| `test_clim.py` | climatology builder: baseline selection (partial years excluded, current year not in its own baseline), percentiles, ranks, week 53, missing weeks, overlap, failures never write |
| `test_units.py` | unit-availability builder: daily sums, which days count, null vs zero, metadata, robustness |
| `test_psh.py` | pumped-storage builder: Q, P, lower- and upper-plant water (Ql, Qu), factors, which days are used, ISP pumping carried along, robustness |
| `test_wb.py` | water balance builder for all six rivers: formulas, grouping, pump independence (Sfikia/Asomata, Thesavros/Platanovrysi, Pournari I/II), Ilarionas outage, 0.00 % readings, fallbacks |
| `test_entsoe.py` | ENTSO-E weekly parser: DST-safe week boundaries, compressed curves, merge/revision, failure modes; history mode (one request per year, separate file, skipped years, nothing written on failure) |

## Page (JavaScript, jsdom) — `node tests/dashboard/run.js`
First `npm install --prefix tests/dashboard`. The test loads the real `index.html` and the real JSON files in `data/` into jsdom and checks that tabs, cards, charts, tables, both languages and the numbers shown agree with the data files; it also covers the shell (breadcrumb, Last/Next Update, language defaults, the GR | EN switch and the shared `kp_lang` key, badge and banner, footer), the loading overlay **with its real pauses** (steps appear in order, "ready" only after the last one), the modals (fixed header/footer structure, ✕, Close, Escape, backdrop), the clickable-card cues, the date navigation inside the river modal (select, previous/next, arrow keys, limits) the pumped-storage section (cards, rolling chart, stacked bars and tables recomputed from `psh_daily.json`, graceful absence) the unit-availability section (flags, zero-day counts, last normal day, chart, selector, modal warnings, graceful absence), the comparison with previous years (percentiles and ranks recomputed from the raw ENTSO-E files), days of cover (rates, days, usual stock, trend and inflow equivalent recomputed for two dates), the Ilarionas + Polyfyto sum line, the confirmed Nestos pump direction, and the tooltips on every chart. It therefore depends on the repository data: the "today" cases (a day with reservoir levels but no SCADA, and a day with only ISP) are built as **synthetic days** appended after the last real one, so the result does not depend on the time of day; the other assertions are written to be **dynamic** (recomputed from the files) rather than fixed numbers, so they keep passing as new days arrive. Keep it that way when adding checks.

## Not covered
Real browser rendering (charts are checked as SVG markup, not pixels), live ADMIE/ENTSO-E responses (only synthetic samples), `calibrate_energy.py` (run manually and reviewed by eye).

## Adding a test
Pipeline: add a function to the closest file and use `check(name, condition, extra)`; keep the final `sys.exit`. Page: add a `ck(name, condition, extra)` line to `tests/dashboard/run.js`.
