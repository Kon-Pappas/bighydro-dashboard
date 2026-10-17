# Sources

Rule of the project: **a source is cited only if we opened it and can name it** (title, year, link). Summaries from the web or from AI assistants that attribute a figure to a generic institution ("official report of …", "technical archive of …") without a document are **leads, not sources**. A lead may be used only after it is confirmed by something stronger — for example by our own data. Access date for all links: 2026-10-17.

## Tier 1 — official public documents
| Document | What we take from it |
|---|---|
| Ministry of Environment and Energy (YPEKA), flood-hazard maps for the Aliakmon, `floods.ypeka.gr` — e.g. [map 4470](https://floods.ypeka.gr/wp-content/uploads/2024/03/EL09-05-DMAX-100-025-34-4470-02.pdf) and [map 4455](https://floods.ypeka.gr/wp-content/uploads/2024/03/EL09-05-DMAX-050-025-34-4455-02.pdf) | Reservoir levels as marked on the maps (legend: "highest level of the lake-reservoir as marked"): **Sfikia +142.1 m** (and +140.9 m on another map), **Asomata +84.5 m**. Their difference, ≈ 57–58 m, is an indicative gross head of the Sfikia plant |

## Tier 2 — academic and conference papers (reviewed or co-authored by the operator)
| Document | What we take from it |
|---|---|
| P. Dimas, A. Lykou, G.-K. Sakki, A. Efstratiadis, N. Mamasis, E. Zacharopoulou, T. Karantoumanis, I. Mavros, *Αξιολόγηση πολιτικών διαχείρισης συστημάτων υδροηλεκτρικών έργων υπό το πρίσμα του πλημμυρικού κινδύνου των κατάντη περιοχών: Η περίπτωση του Αλιάκμονα*, 4th Conference on Dams and Reservoirs, Athens, 10–11 Sep 2024 (NTUA with PPC hydro-division co-authors). [PDF](https://www.itia.ntua.gr/el/getfile/2477/1/documents/Dimas_2024LargeDams.pdf) | **Cascade order**: Ilarionas, Polyfyto, Sfikia, Asomata, followed by the Ag. Varvara regulating reservoir. Uses of the Ag. Varvara water: supply of Thessaloniki, irrigation (Imathia, Pella, Thessaloniki) and an ecological flow |
| Same group, companion presentation [EYE_Presentation_Dimas.pdf](https://www.itia.ntua.gr/el/getfile/2540/2/documents/EYE_Presentation_Dimas.pdf) | An upper design level of the Sfikia reservoir, marked **ΑΣΥ +146.00 m** (the exact meaning of the abbreviation was not checked; it is a ceiling for the water level, not a typical operating level) |
| *Δελτίο της Ελληνικής Γεωλογικής Εταιρίας*, article on the **Sfikia dam** ([link](https://ejournals.epublishing.ekt.gr/index.php/geosociety/article/download/16632/14814); title, authors and year not captured) | Rock-fill dam, **maximum height of the body 82 m**, crest length 220 m — a *dam height*, not a hydraulic head |
| *Δελτίο της Ελληνικής Γεωλογικής Εταιρίας*, article on the **Thesavros and Platanovrysi reservoirs** ([link](https://ejournals.epublishing.ekt.gr/index.php/geosociety/article/download/17137/15293); title, authors and year not captured) | Thesavros dam founded at +220 m, height **175 m**; **Platanovrysi receives the outflows of the Thesavros plant** (it is the lower reservoir) |
| 2020 presentation by Professor Stefanakos (public PDF) | Useful volumes (slide 17), PPC small-hydro list (slide 15), volumes by river (slide 30). See `DOMAIN_NOTES.md` |
| University of Western Macedonia lecture notes, *Τεχνολογίες Αποθήκευσης Ενέργειας* (Kontis, 28/12/2021), [course page](https://eclass.teiwm.gr/courses/EE193/) | Sfikia 3 × 105 = 315 MW |

## Tier 3 — secondary and press
| Document | What we take from it |
|---|---|
| [Wikipedia, "Thisavros Dam"](https://en.wikipedia.org/wiki/Thisavros_Dam) (cites the Greek Commission on Large Dams) | Dam height **172 m**, crest +390 m, active capacity 565 hm³ (total 705), 3 × 128 MW reversible Francis, 384 MW |
| [Newmoney, "ΔΕΗ: «Μεγαλώνει» το project αντλησιοταμίευσης στον ΥΗΣ Σφηκιάς"](https://www.newmoney.gr/roh/palmos-oikonomias/energeia/dei-megaloni-to-project-antlisiotamiefsis-ston-iis-sfikias-pic/) (date not captured) | The two mainland pumped-storage plants (Sfikia, Thesavros) total 699 MW = 315 + 384. The article also describes a **future** extension (Sfikia–Bravas); it is out of scope here |
| [SKAI, "Δράμα: Ανησυχία από τη μείωση της στάθμης του νερού στο μεγάλο φράγμα του Θησαυρού"](https://www.skai.gr/news/environment/drama-meiosi-tis-stathmis-tou-nerou-sto-megalo-fragma-tou-thisayrou) | Most of the Nestos water behind Thesavros comes from Rila, in Bulgaria |

## Tier 4 — leads only (not citable)
* Web or AI-assistant summaries giving "head" values of 172 m (Thesavros) and 82 m (Sfikia), pumping powers, round-trip efficiencies (Sfikia 70–72 %, Thesavros 74–76 %) and attributing them to a "Directorate", an "association archive" or an "environmental impact study" without a document.
  * The **powers and the pumping limits** in them (315 and 384 MW; 220 and 250 MW for two units) match **our own data** (maximum SCADA 314 and 378 MW; ISP pumping equal to exactly 220 and 250 MW in 99 % of the pumping hours), so those figures are trusted *because of our data*.
  * The **"heads"** are dam heights (82 m = the Sfikia dam body; 172 m = the Thesavros dam) and are **not used**.
  * The **round-trip efficiencies** are plausible but unverified; they are not used as estimates (D47).
* `data/plant_heads.json` (gross head, efficiency, a few net heads) comes from unofficial documents. Its status is tracked below.

## Cross-checks of what we use
| Quantity | Our value | Evidence | Status |
|---|---|---|---|
| Aliakmon cascade order | Ilarionas → Polyfyto → Sfikia → Asomata | Dimas et al. 2024 | confirmed |
| Platanovrysi is the lower reservoir of Thesavros | yes | Geological Society article | confirmed |
| Sfikia gross head | 54 m | marked levels give ≈ 57–58 m; the dam body is 82 m | consistent (82 m is a dam height) |
| Thesavros gross head | 172 m | the Thesavros **dam** is 172 m high (175 m in another source); crest +390 m on a +220 m foundation | **suspect**: it equals the dam height, the true head must be smaller (KNOWN_ISSUES K19) |
| Installed power | 315 / 384 MW | data maxima 314 / 378 MW; Wikipedia; lecture notes | confirmed |
| Thesavros useful capacity | 570 hm³ | Wikipedia: 565 hm³ active | close |
| Ilarionas capacity | 412 hm³ | no public confirmation found | open (ROADMAP item 5) |
