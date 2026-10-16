# Data dictionary

Units: MW per hour = MWh in that hour · volumes in hm³ (million m³) · energy factors in MWh per hm³ · prices in €/MWh.
All hourly data are on Greek local time (see ARCHITECTURE.md). JSON is UTF-8.

## data/days/YYYY-MM-DD.json  (written by update_hydro.py)
| Key | Meaning |
|---|---|
| `Date` | day (local) |
| `Reservoir` | fill level % (ADMIE) at 00:00 for 14 reservoirs: `KREMASTA KASTRAKI STRATOS ILARIONAS POLYFYTO SFIKIA ASOMATA THESAVROS PLATANOVRYSI P_AOOU POYRNARI1 POYRNARI2 PLASTIRAS LADONAS` |
| `ReservoirTotalRate` | official ADMIE total fill %, volume-weighted |
| `ReservoirTotal` | simple mean of the 14 levels (kept for legacy comparisons) |
| `Meta.Status` | `reservoir, scada, isp, resmv, mcp` ∈ `ok / partial / missing` |
| `Meta.Updated`, `Meta.Schema` | time of last content change (Athens), schema version (3) |
| `Hourly` | 24 rows, see below. Absent for days with no hourly source |

**Hourly row** (`Hour` = `H01…H24`)
| Field | Source | Notes |
|---|---|---|
| `SCADA_<unit>` | SCADA | actual MW, units `Kremasta Kastraki Stratos1 Ilarionas Polyfyto Sfikia Asomata Thesavros Platanovrysi PAoou Pournari1 Pournari2 Agras Edessaios Ladonas Plastiras` |
| `SCADA_Stratos2, _Makrochori, _Louros, _Gkiona` | SCADA | four PPC small hydro plants in the same block; `SCADA_OtherHydro` = their sum |
| `SCADA_TotalHydro` | SCADA | hydro block total = 16 units + the four above (exact) |
| `SCADA_ResSmallHydro` | SCADA | rows ending in `(ΜΥΗΣ)` in the renewables block (currently `ΑΥΛΑΚΙ (ΜΥΗΣ)`); **not** part of TotalHydro |
| `SCADA_Pump` | SCADA | total pumping (positive). No per-plant split exists in SCADA or ENTSO-E |
| `ISP_<unit>` | ISP | scheduled MW for the same 16 units (no Stratos II, Makrochori, Louros, Gkiona) |
| `ISP_Pump`, `ISP_PumpSfikia`, `ISP_PumpThesavros` | ISP | pumping schedule (positive); Thesavros = sum of its three units |
| `SCADA_SmallHydro` | RESMV | MV-connected small hydro ("ΜΥΗΣ ΕΝΕΡΓΕΙΑ KWh" ÷ 1000). Uncertified measurement |
| `MCP_GR` | ENTSO-E | day-ahead price, €/MWh |

## Derived files (rebuilt by update_hydro.py each run)
| File | Content |
|---|---|
| `data/index.json` | `Days[]` newest first: `{Date, Status{…}, Updated}`; `Count, First, Last, Clock` |
| `data/reservoir_history.json` | ascending list of `{Date, ReservoirTotalRate, ReservoirTotal, Reservoir{…}}` |
| `data/pump_daily.json` | per day: `ScadaMWh, IspMWh, IspSfikiaMWh, IspThesavrosMWh, EstSfikiaMWh, EstThesavrosMWh, ByHourlyShareMWh, ByDayShareMWh, UnallocatedMWh, UnscheduledMWh, NotRealizedMWh` (see METHODS §3) |
| `data/monthly/YYYY-MM.json` | daily/monthly MWh aggregates. **Not used by the page** (candidate for removal) |

## Other data files
| File | Written by | Content |
|---|---|---|
| `data/reservoirs.json` | by hand | cascade order per river, pump direction, capacity (hm³) per reservoir, unit names, non-reservoir plants |
| `data/plant_heads.json` | by hand | gross head (m), efficiency range, net head for four plants; source and caveats |
| `data/entsoe_reservoir.json` | fetch_entsoe_reservoir.py | `Weeks[]`: `{Start, End (UTC), StartLocal, IsoWeek, MWh}` — Monday 00:00 Greek time to Monday 00:00 |
| `data/energy_factors.json` | calibrate_energy.py (manual) | `Factors{dam: EnergyMWhPerHm3, P5, P95, Identifiable}`, `Fit`, `Weeks` used, `Latest` (total and per-river energy with a Min/Max over model variants) |
| `data/water_balance.json` | build_water_balance.py | per river: `Groups`, `KNet`, `KGross`, and `Daily[]`: `dV, E, Qn, Inn, Rivern, Qg, Ing, Riverg, V` (per group, hm³/day; `n` = net-head factors, `g` = gross-head) |

## Status of a day (how to read it)
`RSIRM` in our shorthand = reservoir, SCADA, ISP, RESMV, MCP all ok. Days before June have no MCP (price) by choice; the page lists absent sources in a banner.
