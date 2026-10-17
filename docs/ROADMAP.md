# Roadmap

Order reflects risk: first what does **not** touch the daily pipeline, then what waits until after the daylight-saving change of 25 Oct 2026.

## Done (up to 2026-10-16)
Pipeline v3 (per-day files, one clock, per-unit small hydro, per-plant ISP pumping, `--only`, `--diagnose`) · Jan–Oct backfill (reservoir, SCADA, ISP, RESMV; MCP from June) ·
weekly ENTSO-E series · calibrated stored-energy model with out-of-sample check · physical estimate · pumping tab · water balance for Acheloos and Aliakmon ·
visible-hydro summary · tests and documentation in the repository.

## Next — no pipeline risk
1. ~~**Look and feel aligned with the other dashboards**~~ — **done** (dark slate, violet accent, English by default, breadcrumb to the hub, Last/Next Update, loading overlay, footer with disclaimer, chart tooltips; see D23–D28). The shared shell for *all* dashboards, and a possible Chart.js migration, are a separate thread.
2. ~~**Pumped-storage (PSH) view**~~ — **done**, as a section of the Pumping tab (recycled share, volume closure, monthly bars and tables for Sfikia and Thesavros; D43–D46). Next: the unit-availability indicator (item 3).
3. **Unit availability indicator** ("Ilarionas: no generation for N days") so an outage explains itself.
4. **Data-quality notes from a file** (machine-readable version of KNOWN_ISSUES) shown in the banner of the affected days.
5. **Capacity check:** derive the capacities implied by ADMIE's own totals and explain the −0.98 pp gap (Ilarionas 412 hm³ is unverified).

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
Per-dam stored energy (not identifiable) · price/capture-price tab (decided against) · seasonal comparison with previous years (ENTSO-E already offers it) · conclusions about Aoos without more data · any claim about Amfilochia's water availability.

## Working agreements for future threads
* Discuss design first, then write code (the owner's preference for anything that changes the look or the pipeline).
* Deliver **complete files with their repository paths**; the owner uploads through the GitHub web interface. Deleting a file is a manual step — list it explicitly.
* Verify on a staged copy of the repository: `python tests/run_all.py` and `node tests/dashboard/run.js`.
* Recompute every number you quote from the data; label estimates as estimates; keep personal information out of this public repository.
* Chat is in Greek, repository documentation in English.
* **Private correspondence** with any third party is never quoted or referred to in this repository (page, data, documents, comments) without that person's explicit permission. Citing a public document is fine.
* **Naming rule:** wherever Professor Stefanakos is mentioned (page, data files, documents, code comments) he is named *Professor Stefanakos* in English and *ο κ. καθηγητής Στεφανάκος* in Greek. Do not state his affiliation unless it has been verified.
