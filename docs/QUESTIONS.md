# Questions the project should answer

The data we collect and the models we build exist to answer questions, not only to show values. This page lists the questions, what each one needs, and where it stands. It is the guide for the phase after the dashboard itself (D61–D62).

## The questions
| # | Question | What it needs | Status |
|---|---|---|---|
| 1 | How much stored energy do we have **compared with a normal year for this week**? | a multi-year weekly series (ENTSO-E 16.1.D, 2015–2025) → weekly percentiles | **needs the baseline** (manual backfill workflow, D61) |
| 2 | How many **days** can the stock sustain hydro output, at different rates? | stock (ENTSO-E / model), generation rates (SCADA) | data exist; panel not built |
| 3 | What is the **inflow now**, and is it **unusual** for the season? Has the regime changed (dry → wet)? | apparent inflow (water balance) + the baseline | inflow exists; "unusual" needs the baseline |
| 4 | Is the stock **rising or falling**, how fast, and when would it reach a given level at the current trend? | stock and inflow series | data exist; panel not built |
| 5 | How much of the hydro generation rests on **recycled (pumped) water**, and how does that change between dry and wet periods? | PSH section (2026 only) | exists for 2026 |
| 6 | Which river or reservoir **limits flexibility** (fewest days of cover) or **risks spilling**? | fill, inflow, generation per river | partly exists |
| 7 | How much of the generation was **forced by the need to release water** (must-run) and how much was demand-driven? | fill near 100 %, spills, apparent inflow, generation; February 2026 is the test case | **new**; links with the curtailment research thread |
| 8 | What share of **total supply and of the peak hours** does hydro cover? | system-wide generation or load (ADMIE / ENTSO-E) | **data missing** |
| 9 | How **reliable** are all of the above? | out-of-sample comparison with ENTSO-E | exists (W41: −0.02 %) |

## "Days of cover": a range with named scenarios, never a single number
Snapshot of 16 Oct 2026: stock **1,561 GWh** (ENTSO-E, week 41); generation of the 15 large units (SCADA).

| Rate | GWh a day | Days |
|---|---|---|
| Current (last 30 days) | 10.8 | **145** |
| 2026 average | 17.9 | **87** |
| A peak day (90th percentile) | 31.6 | **49** |
| The largest day of 2026 (February) | 48.4 | **32** |

Rules:
* the days are **"with no inflow at all"**, an upper bound and not a forecast;
* they describe the **electric value** of the water, not water security (irrigation, supply, ecological flow compete for it);
* **February 2026 is a real regime, not an outlier**: after several years without comparable rain the dams were opened and water ran almost continuously because the reservoirs could not hold it [owner]. It may recur. The scenario is therefore kept and named; it is also the test case for question 7 (part of that output was probably forced, which is an inference to test);
* the **inflow scenario** (zero / recent / typical) will be added once the baseline exists, so that the days can grow or shrink with what is arriving.

## The inflow "nose": it already works
The apparent inflow (storage change plus water turbined) reacts before the fill percentage does. Example, October 2026: from the 10th the inflow rose from 1–3 to 5–12 hm³ a day (7.6 against 2.6 hm³ a day over the previous month) while ADMIE's total fill rate **kept falling every day** (42.3 % → 40.9 %), because generation still exceeded inflow. What is missing is the **context**: is that unusual for October? (needs the baseline).
Limits: the apparent inflow is a lower bound of the natural inflow (irrigation, evaporation and spills are not measured) and cannot tell rain from snowmelt or from releases upstream.

## Data still to add, in order
1. **Multi-year ENTSO-E weekly stock** (2015–2025): manual workflow *Backfill ENTSO-E history*, file `data/entsoe_history.json`. First run it in diagnostic mode for one early year.
2. **System-wide generation or load** (ADMIE / ENTSO-E) for question 8.
3. Later, and only after 26 Oct: rainfall (and its forecast) for the catchments — a larger step.

## What we will not claim
A forecast of reservoir levels, a measured round-trip efficiency, or "water security". A single number of days. Anything about a unit's fault: the page says "zero generation", not why.
