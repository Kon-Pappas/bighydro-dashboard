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
| `test_wb.py` | water balance builder: formulas, grouping, pump independence, Ilarionas outage, 0.00 % readings, fallbacks |
| `test_entsoe.py` | ENTSO-E weekly parser: DST-safe week boundaries, compressed curves, merge/revision, failure modes |

## Page (JavaScript, jsdom) — `node tests/dashboard/run.js`
First `npm install --prefix tests/dashboard`. The test loads the real `index.html` and the real JSON files in `data/` into jsdom and checks that tabs, cards, charts, tables, both languages and the numbers shown agree with the data files; it also covers the shell (breadcrumb, Last/Next Update, language defaults, the GR | EN switch and the shared `kp_lang` key, badge and banner, footer), the loading overlay **with its real pauses** (steps appear in order, "ready" only after the last one), the modals (fixed header/footer structure, ✕, Close, Escape, backdrop), the clickable-card cues, the date navigation inside the river modal (select, previous/next, arrow keys, limits) and the tooltips on every chart. It therefore depends on the repository data: the "today" cases (a day with reservoir levels but no SCADA, and a day with only ISP) are built as **synthetic days** appended after the last real one, so the result does not depend on the time of day; the other assertions are written to be **dynamic** (recomputed from the files) rather than fixed numbers, so they keep passing as new days arrive. Keep it that way when adding checks.

## Not covered
Real browser rendering (charts are checked as SVG markup, not pixels), live ADMIE/ENTSO-E responses (only synthetic samples), `calibrate_energy.py` (run manually and reviewed by eye).

## Adding a test
Pipeline: add a function to the closest file and use `check(name, condition, extra)`; keep the final `sys.exit`. Page: add a `ck(name, condition, extra)` line to `tests/dashboard/run.js`.
