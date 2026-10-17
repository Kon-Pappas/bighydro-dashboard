#!/usr/bin/env python3
"""
Πολυετής βάση: η αποθηκευμένη ενέργεια ENTSO-E ανά εβδομάδα ISO σε σχέση με προηγούμενα έτη  ->  data/climatology.json

Είσοδοι:  data/entsoe_history.json  (χειροκίνητο workflow «Backfill ENTSO-E history»)  και  data/entsoe_reservoir.json  (ζωντανή σειρά)
Για κάθε εβδομάδα ISO 1–53 υπολογίζεται, από τα ΠΛΗΡΗ προηγούμενα έτη, ελάχιστο, 25ο εκατοστημόριο, διάμεσος, 75ο εκατοστημόριο, μέγιστο
(γραμμική παρεμβολή). Το τρέχον έτος ΔΕΝ μπαίνει στη βάση του. Έτος είναι «πλήρες» αν έχει ≥ 50 εβδομάδες.
Για κάθε εβδομάδα του τρέχοντος έτους: θέση (1 = υψηλότερη) ανάμεσα στα προηγούμενα έτη + το τρέχον, και διαφορά από τον διάμεσο.
Με λίγα έτη (π.χ. 8) δίνουμε ΘΕΣΗ και όχι «εκατοστημόριο».

Η εβδομάδα που λείπει από τη σειρά καταγράφεται (MissingWeeks), δεν συμπληρώνεται.
Έξοδος: data/climatology.json     Κωδικός εξόδου 1 αν δεν υπάρχει αρκετή βάση (τίποτα δεν γράφεται).
"""
import json
import os
import sys
from datetime import date, datetime
from zoneinfo import ZoneInfo

DATA = "data"
HIST = os.path.join(DATA, "entsoe_history.json")
LIVE = os.path.join(DATA, "entsoe_reservoir.json")
OUT = os.path.join(DATA, "climatology.json")
ATHENS = ZoneInfo("Europe/Athens")
MIN_WEEKS = 50      # ένα έτος είναι «πλήρες» με τουλάχιστον τόσες εβδομάδες
MIN_N = 3           # λιγότερα έτη από αυτά: δεν δίνουμε ζώνη (π.χ. εβδομάδα 53)


def log(m=""):
    print(m, flush=True)


def load_weeks(path, required):
    if not os.path.exists(path):
        if required:
            log(f"Λείπει το {path}")
            return None
        return []
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        w = d["Weeks"]
        assert isinstance(w, list)
        return w
    except (OSError, ValueError, KeyError, AssertionError) as e:
        log(f"Το {path} δεν διαβάζεται ({type(e).__name__})")
        return None


def pct(sorted_vals, p):
    """Εκατοστημόριο με γραμμική παρεμβολή (όπως numpy.percentile)."""
    n = len(sorted_vals)
    if n == 1:
        return sorted_vals[0]
    k = (n - 1) * p / 100.0
    lo = int(k)
    hi = min(lo + 1, n - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (k - lo)


def iso(w):
    y, wk = w["IsoWeek"].split("-W")
    return int(y), int(wk)


def main():
    hist = load_weeks(HIST, True)
    live = load_weeks(LIVE, False)
    if hist is None or live is None:
        return 1
    merged = {w["Start"]: w for w in hist}
    for w in live:
        merged[w["Start"]] = w                      # η ζωντανή σειρά υπερισχύει στην επικάλυψη
    weeks = sorted(merged.values(), key=lambda w: w["Start"])
    if not weeks:
        log("Καμία εβδομάδα")
        return 1
    E = {}
    for w in weeks:
        E[iso(w)] = w["MWh"] / 1000.0               # GWh
    cur = max(y for y, _ in E)
    count = {}
    for y, _ in E:
        count[y] = count.get(y, 0) + 1
    base = sorted(y for y, n in count.items() if y < cur and n >= MIN_WEEKS)
    excluded = {str(y): n for y, n in sorted(count.items()) if y < cur and n < MIN_WEEKS}
    if len(base) < MIN_N:
        log(f"Όχι αρκετά πλήρη έτη στη βάση ({len(base)} < {MIN_N}): δεν γράφω τίποτα")
        return 1
    log(f"Βάση: {base[0]}–{base[-1]} ({len(base)} έτη) | τρέχον έτος {cur} | αποκλείστηκαν (μερικά): {excluded or 'κανένα'}")
    out_weeks = []
    for wk in range(1, 54):
        vals = [(E[(y, wk)], y) for y in base if (y, wk) in E]
        if not vals:
            continue
        v = sorted(x[0] for x in vals)
        lo = min(vals)
        hi = max(vals)
        out_weeks.append({"Wk": wk, "N": len(v), "Min": round(v[0], 1), "MinYear": lo[1], "P25": round(pct(v, 25), 1),
                          "Median": round(pct(v, 50), 1), "P75": round(pct(v, 75), 1), "Max": round(v[-1], 1), "MaxYear": hi[1]})
    byw = {x["Wk"]: x for x in out_weeks}
    current, missing = [], []
    wk_cur = sorted(wk for (y, wk) in E if y == cur)
    start_of = {iso(w): w["StartLocal"] for w in weeks}
    for wk in range(wk_cur[0], wk_cur[-1] + 1):
        if (cur, wk) not in E:
            missing.append(f"{cur}-W{wk:02d}")
    for wk in wk_cur:
        b = byw.get(wk)
        row = {"Wk": wk, "StartLocal": start_of[(cur, wk)], "GWh": round(E[(cur, wk)], 1)}
        if b and b["N"] >= MIN_N:
            vals = [E[(y, wk)] for y in base if (y, wk) in E]
            row.update({"Rank": 1 + sum(1 for x in vals if x > E[(cur, wk)]), "Of": len(vals) + 1,
                        "DeltaMedian": round(E[(cur, wk)] - b["Median"], 1),
                        "DeltaMedianPct": round((E[(cur, wk)] - b["Median"]) / b["Median"] * 100, 1)})
        current.append(row)
    peaks = {str(y): round(max(v for (yy, _), v in E.items() if yy == y), 1) for y in base}
    cp = max((v, wk) for (yy, wk), v in E.items() if yy == cur)
    allp = sorted(list(peaks.values()) + [round(cp[0], 1)], reverse=True)
    doc = {"Schema": 1, "Generated": datetime.now(ATHENS).strftime("%Y-%m-%dT%H:%M:%S%z"), "Unit": "GWh",
           "Method": "ανά εβδομάδα ISO, από τα πλήρη προηγούμενα έτη: ελάχιστο, P25, διάμεσος, P75, μέγιστο (γραμμική παρεμβολή)· θέση 1 = υψηλότερη",
           "BaselineYears": base, "ExcludedPartialYears": excluded, "CurrentYear": cur, "Weeks": out_weeks, "Current": current,
           "Peaks": {"Baseline": peaks, "Current": {"GWh": round(cp[0], 1), "Wk": cp[1], "Rank": 1 + allp.index(round(cp[0], 1)), "Of": len(allp)}},
           "MissingWeeks": missing}
    os.makedirs(DATA, exist_ok=True)
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, OUT)
    last = current[-1]
    log(f"Τελευταία εβδομάδα {cur}-W{last['Wk']:02d}: {last['GWh']:,.0f} GWh" + (f" | θέση {last['Rank']}/{last['Of']}, {last['DeltaMedian']:+.0f} GWh από τον διάμεσο" if "Rank" in last else "") + (f" | λείπουν: {missing}" if missing else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
