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
9. ~~**Multi-year baseline**~~ — **done**: history fetched (432 weeks, 2017–2025), `climatology.json` and the panel *Stored energy compared with previous years* (D61–D66). Next: the same for **inflow** (needs ADMIE's per-reservoir history) and for **hydro generation**.
10. ~~**Days-of-cover panel**~~ — **done** (scenarios, usual-stock column, trend line; D67–D71). Next: an **inflow scenario** (zero / recent / typical) once an inflow baseline exists.
11. **Inflow regime indicator** (dry / transition / wet) from the apparent inflow, and the date a chosen level would be reached at the current trend (questions 3 and 4). The "rising or falling" line already exists in *Days of cover*.
12. **Forced vs demand-driven hydro generation** (question 7), with February 2026 as the test case; this is the bridge to the curtailment research thread.

13. **ADMIE history** — **the diagnose found it: daily files 2016–2026 exist for both categories** (DOMAIN_NOTES §8). The formats diagnose showed that the old files were **relabelled, not incomplete** (DOMAIN_NOTES §8), and `scripts/backfill_admie_history.py` + the manual workflow *Backfill ADMIE history* now write `data/history/admie_YEAR.json` (D78–D81). **Status (20 Oct 2026): ten years loaded (2016–2025), repaired and validated against ENTSO-E** (RMS 22 GWh, D86; DOMAIN_NOTES §8). The repair of 20 Oct (2018 with refresh, then 2016–2025 without) removed every `NaN`, applied the zero rules and rebuilt the 2018 conflicts. **One small step remains:** run *Backfill ADMIE history* once more for `2016`–`2025` **without** refresh with the script of batch19, which drops the stale totals of the five days that have no reservoir value (D87); it takes a few minutes and downloads almost nothing. Hourly pumping profiles are **not** stored (owner's decision, D88; QUESTIONS 10). **Next after the repair:** the climatology of fill, generation and apparent inflow built from these files (question 3), and the pumping trend (2025: 836 GWh) for the curtailment thread. (Earlier note: **second version** (manual read-only workflow, D75–D76). The first run returned "0 files" for every year, even 2026, because a whole-year request returns an empty list on `getOperationMarketFile`; the diagnose now measures what the API accepts before scanning: run it, send the log, and then decide whether and how to back-fill reservoir fill and SCADA generation for past years (an inflow baseline, question 3). A backfill must go to a **separate** file, not to `data/days/`.

## Until the clock change (Sunday 25 Oct 2026: at 04:00 the clocks go back to 03:00, a 25-hour day)
1. **Tue 20 Oct:** upload the latest batch (it replaces the previous one) and run *Backfill ADMIE history* once more for 2016–2025 **without** refresh (D87).
2. **Wed 21 – Fri 23 Oct (prepare, do not deploy):** a read-only diagnose of the **real clock-change files of past years** — 26 Oct 2025 (25 hours) and 29 Mar 2026 (23 hours): how ADMIE lays out the extra or missing hour in the SCADA file (hourly columns) and in the ISP file (quarter-hours). Then write and test the fix for K05 and K04 on those real files. The fix is **not** deployed before the day.
3. **Fri 23 Oct (evening):** health check — the test workflow and the daily job green, nothing queued.
4. **Sat 24 – Mon 26 Oct:** no uploads, no manual workflows. The pipeline runs unchanged, so that 25 Oct is a clean observation of what it does on a 25-hour day. *Expected, to be confirmed:* the SCADA parser takes the first 24 of the hourly columns (`SCADA_H0:SCADA_H1`) and the ISP parser the first 96 quarter-hours (`ISP_Q0:ISP_Q1`), so the day is slightly wrong, not a failure.
5. **From Mon 26 Oct:** compare the 25 Oct record with the past-year files, run the diagnose on the real file, then deploy the tested fix (next section).

## After 26 Oct 2026
6. **Daylight-saving handling** (ISP, SCADA, RESMV, MCP) and an **automatic clock-alignment flag** (SCADA–ISP correlation per day, stored in `Meta`); repair 30 March and 25–26 October by re-running those days.
7. ~~**Water balance for the remaining rivers**~~ — **done** (Nestos, Arachthos, Plastiras, Ladonas and an all-rivers overview; see D36–D39). Next in line: the pumped-storage view (item 2), which reuses the same pump estimates.
8. **Less clutter:** stop writing `data/monthly/*.json`; write derived files only when their content changes; update the Actions versions that warn about Node 20.
9. Optional backfills: MCP for January–May; retry RESMV for 1–2 Feb if ADMIE republishes.

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
