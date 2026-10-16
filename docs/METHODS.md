# Methods

Numbers marked *(snapshot)* were measured on 2026-10-15/16 and will drift as data accumulate; the method is what matters.

## 1. Reservoir volumes
`V = fill% × useful capacity`. Capacities (hm³, `data/reservoirs.json`) come from the PPC/Stefanakos 2020 presentation (slide 17); they sum to 5,707 hm³ for the 14 ADMIE reservoirs.
* ADMIE's official total is volume-weighted. Our rebuild with these capacities is on average **0.98 percentage points lower** (std 0.15; range −1.38 … −0.75) — one capacity is probably different. A first hypothesis (Ilarionas ≈ 300 instead of 412 hm³) is **unverified**; ENTSO-E data cannot decide it.
* **Kastraki above 100 %** is normal (109 of 280 days up to 2026-10-07 *(snapshot)*, peaking at 128.8 % on 3 Oct). The volume above 100 % is uncertain (53 hm³ × fill).
* Readings of exactly **0.00 %** on a large dam (≥ 100 hm³) are treated as invalid and linearly interpolated *in the calculations* (not in the data files). Small regulating ponds (Stratos, Sfikia, Asomata, Pournari II) swing tens of percent per day and are left alone.

## 2. Stored energy
### 2.1 "ENTSO-E equivalent" (calibrated)
A cascade model: each hm³ in dam *i* is worth what it generates while descending every plant downstream (itself included):
`e_i = Σ_{j downstream of i, including i} k_j` (MWh/hm³); `E = Σ e_i · V_i`. The `k_j ≥ 0` are fitted (non-negative least squares) to ENTSO-E 16.1.D weekly values.
* **Week convention (found empirically):** an ENTSO-E week (Monday 00:00 local → Monday) equals the **mean of the daily end-of-day readings**, i.e. the ADMIE files dated Monday+1 … Monday+7. This beats start-of-week, end-of-week and mean-of-start-of-day readings.
* **Fit (snapshot):** 38 weeks (2026-01-05 → 2026-09-28). Leave-one-out error **4.3 GWh = 0.17 %**; a single constant factor gives 19.5 GWh. Trained on January–May only, it predicts June–September within 10.2 GWh.
* **Out-of-sample test (week 41, 5–11 Oct, never used in fitting):** model 1,561,053 MWh vs ENTSO-E 1,561,350 MWh = **−0.3 GWh (−0.02 %)**; the week-on-week change was −48.8 vs −49.4 GWh.
* **Stability (2026-10-16):** refitting with week 41 added moved no factor by more than 0.3 % and the total energy by 0.01 %.
* **Resolution limit.** Reservoirs of one cascade move together, so **per-dam factors are not identifiable**. In a synthetic test with known factors the total was recovered to 0.04 %, but 3 of 5 dams flagged "ok" had the true value outside their bootstrap interval. The page therefore reports energy **per river** (±10–20 %), never per dam. The bootstrap intervals understate the uncertainty; the spread between model variants (`Latest.ByRiver`) is the better guide.
* **Pigai Aoou (Aoos).** Its physical value would be ≈ 1,850 MWh/hm³ (≈ 186 GWh, 10 % of the total) but it is **not visible** in the ENTSO-E series: a free fit gives 0–200 MWh/hm³, and forcing the value claimed by an unofficial document (1,795) raises the error from 3.0 to 9.7 GWh. Whether ADMIE values it differently is unknown. The Aoos reservoir is shown separately and never added to the ENTSO-E equivalent.
* **Recalibration rule:** only if the out-of-sample error exceeds ≈ 10 GWh for two consecutive weeks, or in December after the autumn refill. Run `python scripts/calibrate_energy.py` (needs scipy) on a copy of the repo, review `Fit`, then commit `data/energy_factors.json`.

### 2.2 "Physical estimate"
`k_j = 2.725 × H_gross × η_mid` (MWh/hm³; 2.725 = ρ·g·10⁶ m³ / 3.6·10⁹). Gross head (not net) is used because the data agree with it: fitting a common scale κ on top of the four plants with published heads gives κ = 1.005 with gross heads but 1.127 with net heads. The physical total excluding Aoos was 1,592 GWh vs 1,577 GWh equivalent on 2026-10-07 (+1 %). Plastiras agrees within ≈ 5 %. Heads are unofficial and approximate (see DOMAIN_NOTES.md). Stratos counts Stratos I only (Stratos II works on ecological flow).

## 3. Pumping per plant (estimate)
SCADA reports only total pumping; ISP has the schedule per plant. Each hour the SCADA total is split with the **ISP share of that hour**; hours with no schedule take the **share of the day**; days with no schedule at all stay unallocated.
Jun–Oct *(snapshot)*: 90.8 % of the energy split by hourly share, 8.8 % by day share, 0.4 % unallocated. 9.2 % of actual pumping happened in hours with no scheduled pumping; 7.0 % of the scheduled pumping did not happen. Jan–Oct SCADA 375.9 GWh vs ISP 374.7 GWh, but month by month the ratio ranges from 0.46 (March: 42 % of the schedule not delivered) to 1.19 (August).

## 4. Water balance ("apparent inflow")
Dams are grouped. For group *g* and day *d* (reservoir readings at 00:00):
* `dV_g = Σ_dams [V(d+1) − V(d)]`
* `Q_g = E_g / k_g` — water leaving the group through its exit plant (hm³), from SCADA energy `E_g` and plant factor `k_g`
* head group: `inflow = dV + Q`; others: `inflow = dV + Q_g − Q_(g−1)`; river: `Σ dV + Q_last`

"Apparent" = natural inflow **minus** what is not measured (irrigation, evaporation, spills, ecological release). Two factor sets are computed: net head (`n`) and gross head (`g`); their difference is the uncertainty indicator.
* **Sfikia + Asomata are one group.** The Asomata → Sfikia pump moves water *inside* the system, so the pumped volume and Sfikia's own turbined volume cancel algebraically; the result does not depend on the uncertain pump estimate (verified algebraically and by a test).
* **Ilarionas is separate** because it is a real, distinct dam, **but it has been out of service** (no generation since 2026-06-13, short test runs from 2026-10-01). While it does not turbine, the water passing it is unmeasured and appears at Polyfyto, so the Ilarionas/Polyfyto *split* is unreliable; their sum and the river total are not affected.
* **Stratos II** (≈ 6 m head) is excluded from the volume.

**Results *(snapshot, Jan 1 – Oct 15)*, net head / gross head:**
* **Acheloos** 3,224 / 2,842 hm³ apparent inflow, 71 % in Jan–Feb. Kastraki turbines **≥ 14 % more water than Kremasta** even under the most favourable heads in the source documents, so there is real extra inflow into Kastraki (the Inachos river and the local basin; it may also include non-turbine releases from Kremasta). Kremasta is slightly negative in Aug–Oct and Stratos is negative in Jun–Sep: withdrawals and losses exceed natural inflow.
* **Aliakmon** 1,514 / 1,305 hm³. The lower basin (Sfikia + Asomata) is **negative all year (−835 hm³)**: Asomata turbines only 69 % of what Polyfyto turbines. The size depends on the Asomata head, which is an *estimate* (net ≈ 44 m): −836 hm³ with 44 m, −1,044 with 50 m, and zero at ≈ 31 m.
* 1–2 July: a one-day ±5.6/−2.9 hm³ wobble in the Polyfyto reading cancels itself; read the 7-day average.

## 5. Exploratory (not in the page): how much of Sfikia's water is recycled?
With pumping ≈ 55 m / η 0.87 (k ≈ 172 MWh/hm³) and Sfikia/Polyfyto net heads: Sfikia turbined 3,742 hm³ in Jan–Oct, of which ≈ **1,351 hm³ (36 %) was pumped water**; the rest is river flow from Polyfyto. The monthly share ranges from 9 % (February, flood) to 64 % (September), and the volumes close within 8 % on average: (Polyfyto turbined + pumped) / Sfikia turbined = 1.08 (1.00–1.18). ±10 % on the pump factor moves 36 % to 33–40 %. So Sfikia behaves as a river-fed (mixed) pumped-storage plant that is close to closed-loop in dry months. This is the seed of the planned PSH view (ROADMAP.md).

## 6. Data-quality checks
* **Clock alignment:** correlation SCADA vs ISP hourly at lag 0, per day: median 0.984 over 288 days. Outliers: 2026-03-30 (0.217, best shift −1 h), 2026-09-22 (0.62), 2026-01-10 (0.66), 2026-06-12 (0.73). Only 30/3 shows a clear offset signature.
* **Reconciliation:** TotalHydro equals the sum of its 20 units exactly.
* **RESMV** is uncertified; three days are incomplete (KNOWN_ISSUES.md).
