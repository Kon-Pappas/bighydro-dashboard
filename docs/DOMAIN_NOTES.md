# Domain notes — what we know, and how well we know it

Every statement is tagged with its source: **[owner]** provided by the repository owner (domain knowledge, treated as correct unless data contradict it),
**[doc]** from unofficial documents/AI-generated summaries (approximate, unverified), **[data]** derived from the data here (empirical, may change),
**[assumption]** a working assumption that needs confirmation.

## 1. Cascades and plants
River cascades, upstream → downstream (`data/reservoirs.json`):
| River | Order | Pump | Notes |
|---|---|---|---|
| Acheloos | Kremasta → Kastraki → Stratos (I + II) | — | [owner] order, and "Stratos 1+2" counts as one dam |
| Aliakmon | Ilarionas → Polyfyto → Sfikia → Asomata | Asomata → Sfikia (upward) | [owner] order and pump direction (confirmed) |
| Nestos | Thesavros → Platanovrysi | Platanovrysi → Thesavros | Platanovrysi is the lower reservoir of the Thesavros plant [public article, SOURCES.md]; the Nestos inflow comes from Bulgaria [owner; press]; pump direction **[assumption]**, supported by the volume-closure test (METHODS §4), not yet confirmed by the owner |
| Arachthos | Pigai Aoou (Aoos) → Pournari I → Pournari II | — | [owner] the Aoos water is diverted to the Arachthos basin and used again at Pournari |
| Plastiras (Tavropos), Ladonas | one dam each | — | |
Agras and Edessaios have no reservoir in the ADMIE reservoir file (run-of-river).

## 2. Plant lists in the ADMIE files
* **Large hydro (16 units, SCADA + ISP):** Kremasta, Kastraki, Stratos I, Ilarionas, Polyfyto, Sfikia, Asomata, Thesavros, Platanovrysi, Pigai Aoou, Pournari I, Pournari II, Agras, Edessaios, Ladonas, Plastiras. Hydro block of the SCADA sheet = 20 unit rows + `TOTAL HYDRO`.
* **Small PPC plants in the same SCADA block (not in ISP):** Stratos II, Makrochori, Louros, Gkiona.
* **Small hydro in the renewables block (`ΑΝΑΝΕΩΣΙΜΑ`, 163 rows):** exactly one row ending in `(ΜΥΗΣ)` — `ΑΥΛΑΚΙ (ΜΥΗΣ)` [data], ≈ 20 MW run-of-river, 43 GWh in Jan–Oct. The block's other rows are PV (66, all zero at night), CG (4), BM (1) and 91 unlabelled rows assumed to be wind [owner/data: only one looks solar, `ΜΑΚΡΥΧΩΡΙ_2`].
* **MV small hydro:** only an aggregate, in the RESMV file column `ΜΥΗΣ ΕΝΕΡΓΕΙΑ KWh` (the file states ≈ 270 MW installed on 4 Oct) [data]. Uncertified.
* **Not visible anywhere in SCADA** [data]: the other seven PPC small plants named in Professor Stefanakos's PDF (Glafkos, Vermio, Agia and Almyros in Crete, Ag. Ioannis Serron, Ag. Varvara, Smokovo). Unknown whether RESMV includes them.

## 3. Plants that matter for interpretation
* **Ilarionas is out of service** [owner] (a fault being repaired). [data] no generation from 2026-06-13; short runs on 1, 2, 6, 9, 13 and 15 October look like tests.
* **Kastraki above 100 %** is a common occurrence [owner]. It is not an anomaly.
* **Amfilochia pumped storage** (planned start ≈ end-2026) will use the Kastraki lake as its lower reservoir [owner]. The owner's estimate is that first filling of its upper reservoirs needs about 9 % of the lake (≈ 4.8 hm³); the recent >100 % levels may be chance or preparation [owner]. [data] single-day swings ≥ 4.8 hm³ are rare (7 of 279 days up to 16 Oct); the strongest 11-day rise of 2026 was +24.6 hm³ (22 Sep → 3 Oct).
* **The Inachos river flows into Kastraki** [owner] — a source of natural inflow not passing through Kremasta.
* **Sfikia and Thesavros** are the two pumped-storage plants whose pumping appears in SCADA (total only) and ISP (per plant).

## 4. ENTSO-E
* The owner believed an ENTSO-E "week" is a weekly average [owner]. [data] confirmed with a precise form: the mean of the daily end-of-day readings, Monday+1 … Monday+7 (see METHODS §2.1). An earlier conclusion in the project history ("end of week") was wrong and was corrected.
* The weekly series lags about one week. Week 34 (17 Aug) is missing from the ENTSO-E series.
* An unofficial document claimed ADMIE values the Aoos water at ≈ 1,795 MWh/hm³ using an internal table. The claim could not be verified and the data do not support it (METHODS §2.1).

## 5. Heads and efficiencies (`data/plant_heads.json`) [doc]
Two PDF/AI-generated tables supplied by the owner give gross head, efficiency range and, for four plants, net head: Kremasta 160 m (net 140–150), Kastraki 95 (80–85), Polyfyto 112 (95–102), Thesavros 172 (150–160), Sfikia 54, Asomata 50, Ilarionas 118, Stratos I 38, Stratos II 6, Platanovrysi 85, Pigai Aoou 670, Pournari I 72, Pournari II 12, Plastiras 577, Ladonas 225.
Five of them were checked against the ENTSO-E data and agree within ≈ 5 % (Kremasta, Kastraki, Polyfyto, Thesavros, Plastiras); the rest are small or not testable. Net heads for plants without a published net head are taken as gross/1.125 (the average ratio of the four that have both).

Source cross-checks of the Sfikia and Thesavros heads are in `SOURCES.md`: the Sfikia value is consistent with the public reservoir levels; the Thesavros gross head (172 m) equals the dam height and is suspect (KNOWN_ISSUES K19).

## 6. Reference documents
The 2020 presentation by Professor Stefanakos: slide 15 (PPC small hydro list), **slide 17 (useful volumes, source of `CapacityHm3`)**, slide 30 (volumes by river; e.g. Acheloos 2,869 hm³, Aliakmon 1,458, Nestos 582, Arachthos 307, Plastiras 300, Aoos 145, Ladon 46.2). An earlier version of the page quoted an irrigation figure for the Acheloos reservoirs and attributed it to this slide; it could not be verified, so it was **removed** (D42). It may be restored only after it has been checked against the PDF.

## 7. Glossary
**ISP** integrated scheduling process (schedule) · **SCADA** actual measured output · **RESMV** RES injections at medium voltage · **MCP** market clearing price (day-ahead) ·
**PSH** pumped-storage hydro · **apparent inflow** natural inflow minus unmeasured losses/withdrawals · **river-fed (mixed) PSH** upper reservoir receives natural inflow, **closed-loop PSH** does not · **hm³** million cubic metres · **κ** common scale factor used to compare heads.
