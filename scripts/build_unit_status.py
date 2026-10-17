#!/usr/bin/env python3
"""
Διαθεσιμότητα μονάδων: ημερήσια παραγωγή κάθε υδροηλεκτρικής μονάδας  ->  data/unit_daily.json

Για κάθε μονάδα του SCADA (16 μεγάλες + μικρές της ΔΕΗ στο ίδιο μπλοκ) αποθηκεύεται η ημερήσια ενέργεια (MWh) για κάθε ημέρα με
πλήρες SCADA. Οι στατιστικοί δείκτες (ημέρες μηδενικής παραγωγής, τελευταία κανονική ημέρα κ.λπ.) υπολογίζονται στη σελίδα ως προς την
ΕΠΙΛΕΓΜΕΝΗ ημερομηνία, γι' αυτό εδώ μένουν μόνο τα ακατέργαστα ημερήσια σύνολα.

Μονάδες: από το data/reservoirs.json (μονάδες των φραγμάτων, Άγρας/Εδεσσαίος χωρίς ταμιευτήρα, και οι μικρές της ΔΕΗ).
Μια τιμή null σημαίνει ότι η μονάδα λείπει εκείνη την ημέρα από το αρχείο (δεν μετράει ως μηδέν).

Είσοδοι: data/days/*.json, data/reservoirs.json     Έξοδος: data/unit_daily.json
"""
import glob
import json
import os
import sys
from datetime import date, datetime
from zoneinfo import ZoneInfo

DATA = "data"
OUT = os.path.join(DATA, "unit_daily.json")
ATHENS = ZoneInfo("Europe/Athens")


def log(m=""):
    print(m, flush=True)


def units_from_meta(meta):
    """{unit: {"Dam": dam key or None, "Name": greek name or None}} με σταθερή σειρά (φράγματα, χωρίς ταμιευτήρα, μικρές ΔΕΗ)."""
    units = {}
    for dam, info in meta["Reservoirs"].items():
        for u in info["Units"]:
            units[u] = {"Dam": dam, "Name": None}
    for x in meta.get("WithoutReservoir", []):
        for u in x["Units"]:
            units[u] = {"Dam": None, "Name": x.get("Name")}
    for u in meta.get("OtherHydro", []):
        units[u] = {"Dam": None, "Name": None}
    return units


def main():
    if not os.path.exists(os.path.join(DATA, "reservoirs.json")):
        log("Λείπει το data/reservoirs.json")
        return 1
    with open(os.path.join(DATA, "reservoirs.json"), encoding="utf-8") as f:
        units = units_from_meta(json.load(f))
    dates, series = [], {u: [] for u in units}
    skipped = 0
    for f in sorted(glob.glob(os.path.join(DATA, "days", "*.json"))):
        try:
            with open(f, encoding="utf-8") as fh:
                rec = json.load(fh)
            d = rec["Date"]
            date.fromisoformat(d)
        except (OSError, ValueError, KeyError) as e:
            log(f"   ! {os.path.basename(f)} δεν διαβάζεται ({type(e).__name__}) - παραλείπεται")
            skipped += 1
            continue
        H = rec.get("Hourly") or []
        if not H or (rec.get("Meta") or {}).get("Status", {}).get("scada") != "ok":
            continue
        dates.append(d)
        for u in units:
            vals = [h.get("SCADA_" + u) for h in H]
            series[u].append(None if any(v is None for v in vals) or not any("SCADA_" + u in h for h in H) else round(sum(vals), 1))
    if not dates:
        log("Δεν βρέθηκαν ημέρες με πλήρες SCADA")
        return 1
    log(f"{len(dates)} ημέρες ({dates[0]} → {dates[-1]}), {len(units)} μονάδες" + (f", παραλείφθηκαν {skipped} αρχεία" if skipped else ""))
    doc = {"Schema": 1, "Generated": datetime.now(ATHENS).strftime("%Y-%m-%dT%H:%M:%S%z"),
           "Method": "ημερήσια ενέργεια (MWh) ανά μονάδα SCADA, για ημέρες με πλήρες SCADA· null = η μονάδα λείπει εκείνη την ημέρα",
           "Dates": dates, "Units": {u: {"Dam": units[u]["Dam"], "Name": units[u]["Name"], "Mwh": series[u]} for u in units}}
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
