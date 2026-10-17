# Known issues and data caveats

Status: **open** (needs action or a decision), **accepted** (understood, no action planned), **watch** (monitor).

| # | Date(s) | Issue | Impact | Status |
|---|---|---|---|---|
| K01 | 2026-07-19 → 07-25 | ADMIE reports Ilarionas at exactly 0.00 % fill (−63 hm³ for a week) | Interpolated in energy and water-balance calculations; raw files unchanged; banner on those days | accepted |
| K02 | since 2026-06-13 | **Ilarionas unit out of service** (owner); short runs from 1 Oct look like tests | Ilarionas/Polyfyto split of the water balance unreliable; sum and river total fine | watch (until repaired) |
| K03 | 2026-02-01, 02-02, 03-29 | RESMV file incomplete (21/24 h), empty, and 23-hour (DST) | Those days lack MV small hydro; the pipeline correctly writes nothing. A re-run on 1–2 Feb found the same ADMIE files | accepted |
| K04 | 2026-03-30 | **ISP offset by one hour** on the day after the DST start (SCADA–ISP correlation 0.22; the DST day itself, 29/3, is fine) | Hourly ISP fields and the hourly pump split of 30/3 are unreliable; daily sums are fine | open (fix with K05) |
| K05 | 2026-10-25 (25-hour day) | Daylight-saving end is not handled; expect an offset on the 25th or, as in March, on the 26th | Possible wrong hours for that day; recoverable by re-running the day after a fix | open (after 26 Oct) |
| K06 | 2026-10-10 | ENTSO-E has no day-ahead price for delivery day 10 Oct (only the previous day's last hour) | MCP `partial` for 10 and 11 Oct | watch |
| K07 | week of 2026-08-17 (W34) | Missing from the ENTSO-E weekly series | One week fewer in calibration and in the weekly chart | accepted |
| K08 | whole year | Kastraki above 100 %: volume above 100 % uncertain (capacity 53 hm³) | Kastraki ΔV and balance terms have extra uncertainty | accepted |
| K09 | whole year | Official total fill is 0.98 pp above our rebuild; Ilarionas capacity (412 hm³) unverified | Small systematic difference in hm³ | open (capacity check planned) |
| K10 | whole year | Per-plant pumping is an estimate; 9.2 % of actual pumping falls in hours with no schedule | Labelled "estimate" everywhere | accepted |
| K11 | — | Platanovrysi → Thesavros pump direction is an assumption | Pump arrow on the Nestos card | open (owner to confirm) |
| K12 | 2026-01-10, 06-12, 09-22 | Low SCADA–ISP correlation (0.62–0.73) without a clear offset | Probably unusual operation; not investigated | watch |
| K13 | Jan–May | No day-ahead price (MCP) backfilled | Only matters for price analysis | accepted |
| K14 | — | Stratos II excluded from the water-balance volume; the seven other small PPC plants are not visible in SCADA | Small | accepted |
| K15 | — | Heads/efficiencies are unofficial; RESMV is uncertified; "ENTSO-E equivalent" is an estimate | See README "Read this before trusting a number" | accepted |
| K16 | housekeeping | `data/monthly/*.json` is produced but unused by the page; the Node 20 deprecation warning in Actions; derived files get a new timestamp on every run, producing commits with no real change | Clutter only | open (after 26 Oct) |
| K17 | every morning, ≈ 00:25 → ≈ 08:35 | The newest day in `index.json` exists (from the ISP file) but has **no reservoir levels** yet; the page used to crash when it was selected (found by the CI on 2026-10-17) | Fixed in the page: such days are not offered and a request falls back to the latest available day with a notice (D35) | accepted (fixed) |

## How to recognise a clock offset quickly
Compute, per day, the correlation between the summed SCADA and summed ISP of the 16 large units at lags −2 … +2 h. Normal days: ≥ 0.9 at lag 0. A day with a low lag-0 value and a better value at ±1 h is offset (as 30 March).
