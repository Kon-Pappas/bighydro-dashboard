# Decisions log

Format: **what** · *why* · alternatives rejected. Dates are approximate (the project ran from September to October 2026). Newest decisions last.

| # | Decision | Why / what was rejected |
|---|---|---|
| D01 | One JSON file per day plus derived files | Cheap re-runs and small diffs. Rejected: one large `hydro_data.json` (frozen legacy copy was removed). |
| D02 | `null` ≠ `0`; a new `null` never overwrites a value, a new value always does | Safe merging of partially published days; wrong data are repaired by re-running. |
| D03 | Store everything on **Greek local time**; shift ISP and MCP by +1 h | One clock for the page; verified on 288 days (median correlation 0.984). Rejected: keep each source on its native clock. |
| D04 | Lookback of 4 days on every run | Late ADMIE files heal on the next run without manual action. |
| D05 | Volume = fill % × capacity from the Stefanakos PDF; keep ADMIE's official total separately | Official total is volume-weighted and our rebuild is 0.98 pp lower; both are shown. |
| D06 | ENTSO-E weekly value = mean of end-of-day readings (Monday+1 … +7) | Best fit by far; an earlier "end of week" conclusion (from summer data only) was wrong. |
| D07 | Cascade model (sum of downstream plant factors) fitted by NNLS; report energy per **river**, not per dam | Per-dam factors are not identifiable (synthetic test). A single factor was 4.5× worse. |
| D08 | Two energy numbers: "ENTSO-E equivalent" (primary, calibrated) and "physical estimate" (gross head); Aoos shown separately | Owner agreed; they answer different questions and the page says so. |
| D09 | Gross head (not net) in the physical estimate | Data prefer it (κ = 1.005 vs 1.127). |
| D10 | Pigai Aoou is excluded from the ENTSO-E equivalent | Data show 0–200 MWh/hm³, not ≈ 1,795. Rejected: an unofficial document's claim. Revisit when more autumn data or ADMIE methodology is available. |
| D11 | 0.00 % readings on large dams are interpolated in calculations only | Ilarionas read 0.00 % for 19–25 July (63 hm³). Raw files stay untouched; the banner explains. |
| D12 | The water balance is called **apparent inflow** | It includes unmeasured withdrawals and losses; it must not be read as a flow measurement. |
| D13 | Sfikia and Asomata form one group in the balance | The pump cancels algebraically; avoids using the uncertain pump estimate. Proven and tested. |
| D14 | Ilarionas stays a separate group, with a caveat | Owner: the unit is faulty and must not be merged with Polyfyto. The split is unreliable while it does not turbine; the sum and the river total are unaffected. |
| D15 | Pumping per plant = SCADA total split by hourly ISP share (day share as fallback), always labelled *estimate* | SCADA/ENTSO-E have no per-plant pumping. DAM/intraday prices are deliberately **not** mixed in (owner: ISP vs SCADA is enough). |
| D16 | "Visible hydro" = TOTAL HYDRO + RESMV small hydro + Aulaki; RESMV flagged as an uncertified estimate | All small hydro (RESMV + PPC small + Aulaki) are ≈ 12 % of visible generation; RESMV alone reaches 21 % in April. |
| D17 | Kastraki > 100 % is normal and not flagged; a dedicated Kastraki tab tracks it | Owner knowledge; will matter when Amfilochia starts. |
| D18 | No pipeline changes for daylight-saving handling before 26 Oct 2026 | We have one real sample (29–30 March) and the effect is recoverable by re-running the day. |
| D19 | Recalibrate only on evidence (two weeks > 10 GWh out of sample) or in December | Factors moved ≤ 0.3 % when week 41 was added. |
| D20 | The page has no external libraries (SVG charts, vanilla JS) | Fully testable offline. To be revisited together with the shared look of all dashboards (Chart.js tooltips were proposed). |
| D21 | Scope: this repository is handled in its own threads; the other dashboards and the shared shell are separate work | Keeps context clean; everything needed to continue is in `docs/`. |
| D22 | `stored_energy.json` and the unused legacy files were retired | The page computes weekly/daily energy itself; fewer files to keep consistent. |
