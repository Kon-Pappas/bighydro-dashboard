# Roadmap

Order reflects risk: first what does **not** touch the daily pipeline, then what waits until after the daylight-saving change of 25 Oct 2026.

## Done (up to 2026-10-16)
Pipeline v3 (per-day files, one clock, per-unit small hydro, per-plant ISP pumping, `--only`, `--diagnose`) · Jan–Oct backfill (reservoir, SCADA, ISP, RESMV; MCP from June) ·
weekly ENTSO-E series · calibrated stored-energy model with out-of-sample check · physical estimate · pumping tab · water balance for Acheloos and Aliakmon ·
visible-hydro summary · tests and documentation in the repository.

## Next — no pipeline risk
1. ~~**Look and feel aligned with the other dashboards**~~ — **done** (dark slate, violet accent, English by default, breadcrumb to the hub, Last/Next Update, loading overlay, footer with disclaimer, chart tooltips; see D23–D28). The shared shell for *all* dashboards, and a possible Chart.js migration, are a separate thread.
2. ~~**Pumped-storage (PSH) view**~~ — **done**, as a section of the Pumping tab (recycled share, volume closure, monthly bars and tables for Sfikia and Thesavros; D43–D46). Next: the unit-availability indicator (item 3).
3. ~~**Unit availability indicator**~~ — **done** (Rivers tab, *Unit availability*; D52–D57). Next: the capacity check (item 5), then the daylight-saving work after 26 Oct.
4. **Data-quality notes from a file** (machine-readable version of KNOWN_ISSUES) shown in the banner of the affected days.
5. ~~**Capacity check**~~ — **done as an analysis** (K09, D58): ADMIE's total implies Ilarionas ≈ 305 hm³ (RMSE 0.79 → 0.15 pp). Recorded as a hypothesis; the switch is decided at the **December recalibration**.

## Next phase — what the data can tell us (see `QUESTIONS.md`)
9. ~~**Multi-year baseline**~~ — **done**: history fetched (432 weeks, 2017–2025), `climatology.json` and the panel *Stored energy compared with previous years* (D61–D66). The same for **inflow** (batch35, D100, METHODS §10) and for **hydro generation** (batch36, D103, METHODS §11) is done.
10. ~~**Days-of-cover panel**~~ — **done** (scenarios, usual-stock column, trend line; D67–D71). ~~Next: an **inflow scenario** (zero / recent / typical)~~ — **done** (batch36, D102, METHODS §11: a table and a week-by-week projection).
11. ~~**Inflow regime indicator**~~ (dry / transitional / wet) — **done** (batch35, D100, METHODS §10; rank rule, baseline 2018–2025, gaps up to 3 days). *Still open:* the date a chosen level would be reached at the current trend (question 4). The "rising or falling" line already exists in *Days of cover*.
12. **Forced vs demand-driven hydro generation** (question 7), with February 2026 as the test case; this is the bridge to the curtailment research thread.

13. **ADMIE history** — **the diagnose found it: daily files 2016–2026 exist for both categories** (DOMAIN_NOTES §8). The formats diagnose showed that the old files were **relabelled, not incomplete** (DOMAIN_NOTES §8), and `scripts/backfill_admie_history.py` + the manual workflow *Backfill ADMIE history* now write `data/history/admie_YEAR.json` (D78–D81). **Status (20 Oct 2026): ten years loaded (2016–2025), repaired and validated against ENTSO-E** (RMS 22 GWh, D86; DOMAIN_NOTES §8). The repair of 20 Oct (2018 with refresh, then 2016–2025 without) removed every `NaN`, applied the zero rules and rebuilt the 2018 conflicts. **The repair is complete** (checked on 8 Nov 2026: no day has a total without a reservoir value). **Next after the repair:** the climatology of **apparent inflow** is built (batch35); still open: the climatology of fill and generation, and the pumping trend (2025: 836 GWh) for the curtailment thread. (Earlier note: **second version** (manual read-only workflow, D75–D76). The first run returned "0 files" for every year, even 2026, because a whole-year request returns an empty list on `getOperationMarketFile`; the diagnose now measures what the API accepts before scanning: run it, send the log, and then decide whether and how to back-fill reservoir fill and SCADA generation for past years (an inflow baseline, question 3). A backfill must go to a **separate** file, not to `data/days/`.

## Until the clock change — done
The clock change of 25 Oct 2026 and the fix of K04, K05 and K26 are complete and **verified on the re-run data** (DOMAIN_NOTES §9; D90–D97). Still to watch: **28 Mar 2027** (the first 23-hour day in the 28-column SCADA layout) and **31 Oct 2027**.

## After 26 Oct 2026
6. ~~**Daylight-saving handling** (ISP, SCADA, RESMV, MCP)~~ — **done** (batch31, D96–D97; 30 Mar and 25–26 Oct re-run and verified). *Optional:* an **automatic clock-alignment flag** per day (the SCADA–ISP ramp lag, D95), stored in `Meta`.
7. ~~**Water balance for the remaining rivers**~~ — **done** (Nestos, Arachthos, Plastiras, Ladonas and an all-rivers overview; see D36–D39). Next in line: the pumped-storage view (item 2), which reuses the same pump estimates.
8. ~~**Less clutter**~~ — derived files are written only when their content changes (batch34, D98); `data/monthly/*.json` is **kept** on purpose; the Actions versions that warned about Node 20 are replaced (batch37, D104).
9. ~~Optional backfills~~ — **done on 8 Nov 2026**: MCP for January–May (149 days) is in and **all 312 days of 2026 have MCP**; the RESMV of 1–2 Feb is still incomplete at ADMIE (K03).

## Alignment with the hub playbook (« Τυφλοσούρτης »)
The other hub dashboards are aligned; this is the last one (decided 9 Nov 2026, discussed first, one phase at a time: analysis → the owner's decisions → code, with a **browser check** at 360 and 320 px, Greek and English, before every zip). Declared exceptions: own SVG charts and the page-side computation of *Days of cover* (D107).

| # | Phase | What | Status |
|---|---|---|---|
| 1 | Basics | cron-job.org only, no `schedule:`; actions v5 / v6; `meta.json` from the Python; `no-cache`; the H / C lists; first browser check | **done** (batch37, D104–D107) |
| 2 | Data colours | no data colour equal to the accent, to yellow / red or to the « complete » green; the new scenario lines included (sample palette first) | next |
| 3 | Mobile (H06, H02) | secondary box, tabs 3 + 2 at 48 px, the ↑ button, 12 px gaps, short header labels; before / after measures at 360 and 320 px | |
| 4 | Labels and tables (C02, K30) | no all-caps captions; tables that do not fit become cards, no sideways scroll, « – » instead of 0 | |
| 5 | Loading and Methodology | the remaining overlay details, the Methodology window (Short / Detailed switch, section of the tab, title) | |
| 6 | Data size | `scripts/data_size.py` (raw, gzip, growth, days to the 250 KB limit); on 9 Nov 2026 the first visit loads about 174 KB gzip of data, growing about 130 KB a year, so **the limit is reached around mid-2027** (linear estimate) and files per month become due | |
| 7 | Charts | a decision on Chart.js after the basics (D107) | later |

## Later
* Recalibrate the energy factors on the rule in METHODS §2.1 (and in December).
* Marker for the start of the Amfilochia pumped storage in the Kastraki tab, once a date is known.
* CSV export of tables; shareable links (date, tab, river).
* Move the charts to the library chosen for all dashboards, if the shared-shell thread decides so.

## Research question (separate thread)
**River-fed versus closed-loop pumped storage and renewable curtailment.** Does the seasonality of curtailment caused by oversupply (low demand, high RES) coincide with periods in which river-fed pumped storage (Sfikia, Thesavros) is constrained — upper reservoir high, natural inflow high — in contrast to a free (closed-loop) pumped-storage plant?
The question is about curtailment seasonality versus the room river-fed plants have to pump, **not** about whether the future Amfilochia plant will have enough water (that project has been studied far more thoroughly).
Data needed: a curtailment/surplus series (the owner's BESS dashboard already tracks avoided curtailment), `pump_daily.json` (per plant), upper-reservoir fill (Sfikia 16 hm³, Thesavros 570 hm³), `water_balance.json` for natural inflow, and the recycled-share estimate from METHODS §5.

## Deliberately out of scope
Future projects such as the Sfikia–Bravas expansion (years away, and it would enlarge the Sfikia reservoir) · Per-dam stored energy (not identifiable) · price/capture-price tab (decided against) · seasonal comparison with previous years (ENTSO-E already offers it) · conclusions about Aoos without more data · any claim about Amfilochia's water availability.

## Working agreements for future threads
* Discuss design first, then write code (the owner's preference for anything that changes the look or the pipeline).
* Deliver **complete files with their repository paths**; the owner uploads through the GitHub web interface. Deleting a file is a manual step — list it explicitly.
* Verify on a staged copy of the repository: `python tests/run_all.py` and `node tests/dashboard/run.js`.
* Recompute every number you quote from the data; label estimates as estimates; keep personal information out of this public repository.
* Chat is in Greek, repository documentation in English.
* **Sources:** follow `docs/SOURCES.md` — cite only documents we have opened; web or AI summaries with generic attributions are leads, not sources.
* **Private correspondence** with any third party is never quoted or referred to in this repository (page, data, documents, comments) without that person's explicit permission. Citing a public document is fine.
* **Naming rule:** wherever Professor Stefanakos is mentioned (page, data files, documents, code comments) he is named *Professor Stefanakos* in English and *ο κ. καθηγητής Στεφανάκος* in Greek. Do not state his affiliation unless it has been verified.
