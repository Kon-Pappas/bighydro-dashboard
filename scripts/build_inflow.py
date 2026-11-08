#!/usr/bin/env python3
"""
Εισροή ανά ποταμό έναντι «κανονικού» και δείκτης καθεστώτος (ξηρό / μεταβατικό / υγρό)  ->  data/inflow_climatology.json

Εβδομαδιαία (Δευτέρα–Κυριακή) φαινόμενη εισροή ποταμού, με τον ίδιο ορισμό του ισοζυγίου νερού (build_water_balance.py):
    εισροή_εβδομάδας = V(επόμενη Δευτέρα) − V(Δευτέρα) + Σ_{7 ημέρες} Q ,   Q = E_σταθμού_εξόδου / k_καθαρής_πτώσης
V = Σ φράγματα (στάθμη% × χωρητικότητα), στάθμες ΑΔΜΗΕ στις 00:00. Χρειάζονται λοιπόν μόνο οι στάθμες των δύο Δευτερών και η παραγωγή των 7 ημερών:
ένα κενό που πέφτει ΜΕΣΑ στην εβδομάδα δεν κοστίζει τίποτα.

Κενά (D100): έως 3 ημέρες συμπληρώνονται· η στάθμη με παρεμβολή της ΕΙΣΡΟΗΣ (σταθερή εισροή μέσα στο κενό, με την ΓΝΩΣΤΗ παραγωγή να κινεί τη στάθμη —
V(i) = V(p) + (i−p)·Ī − ΣQ), η παραγωγή με γραμμική παρεμβολή. Οι εβδομάδες που στηρίζονται σε παρεμβολή σημαίνονται (Interp). Μεγαλύτερα κενά: η εβδομάδα
μένει κενή. (Σε πείραμα με πλήρη δεδομένα η παρεμβολή εισροής έχει 30–60 % μικρότερο λάθος από την απλή γραμμική παρεμβολή όγκου.)

Βάση (D100): ISO εβδομάδα × έτη 2018–2025 (όπως ο πίνακας αποθέματος)· αποθηκεύεται και η εναλλακτική 2016–2025.
Καθεστώς: η εισροή των τελευταίων 4 εβδομάδων σε σύγκριση με τις ίδιες 4 εβδομάδες των ετών βάσης (≥ 6 έτη). Θέση 1 = υψηλότερη.
    υγρό = ανάμεσα στις 2 υψηλότερες θέσεις, ξηρό = ανάμεσα στις 2 χαμηλότερες, αλλιώς μεταβατικό (με 8 έτη κάθε θέση ≈ 11 ποσοστιαίες μονάδες, γι' αυτό
    κατάταξη και όχι P25/P75, που θα έπεφταν σε ισοπαλίες).
Ευαισθησία: ο Αλιάκμονας υπολογίζεται και με Ιλαρίωνα 305 hm³ (η σημερινή τιμή 412 είναι υποψήφια για αλλαγή τον Δεκέμβριο, K09).

Είσοδοι: data/history/admie_*.json, data/days/*.json, data/reservoirs.json, data/plant_heads.json   Έξοδος: data/inflow_climatology.json
"""
import glob
import json
import os
import sys
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import clock_change as CC                          # ενέργεια ημέρας που αντέχει ημέρες 23/25 ωρών
import jsonio                                      # εγγραφή μόνο όταν αλλάζει το περιεχόμενο (K16)
import build_water_balance as W                    # ίδιες ομάδες φραγμάτων και συντελεστές k με το ισοζύγιο νερού

DATA = "data"
OUT = os.path.join(DATA, "inflow_climatology.json")
ATHENS = ZoneInfo("Europe/Athens")

MAXGAP = 3                       # μέγιστο κενό (ημέρες) που συμπληρώνεται
BASE = (2018, 2025)              # προεπιλεγμένη βάση
EXT = (2016, 2025)               # εναλλακτική βάση
MIN_N_BAND = 4                   # ελάχιστα έτη για να δοθεί ζώνη ανά εβδομάδα
MIN_N_REGIME = 6                 # ελάχιστα έτη βάσης για να δοθεί καθεστώς
REGIME_WEEKS = 4                 # εβδομάδες του καθεστώτος
EXTREME = 2                      # πόσες θέσεις από κάθε άκρο είναι «ξηρό» / «υγρό»
STALE_DAYS = 10                  # το καθεστώς δεν δίνεται αν η τελευταία πλήρης εβδομάδα απέχει περισσότερο από τόσες ημέρες από τα τελευταία δεδομένα
ILARIONAS_ALT = 305.0            # ευαισθησία (K09)
LOW_CONFIDENCE = {
    "arachthos": {"El": "Ο σταθμός εξόδου (Πουρνάρι ΙΙ) έχει εκτιμώμενη πτώση ~12 m (συντελεστής ~25 MWh/hm³): κάθε σφάλμα παραγωγής πολλαπλασιάζεται και η φαινόμενη εισροή μπορεί να βγει αρνητική.",
                  "En": "The exit plant (Pournari II) has an estimated head of ~12 m (factor ~25 MWh/hm³): any generation error is multiplied and the apparent inflow can come out negative."},
}


def log(m=""):
    print(m, flush=True)


# ---------------------------------------------------------------- είσοδοι
def load_series(data_dir, dams, units, caps):
    """-> (fill {dam: {date: %}}, gen {unit: {date: MWh}}, last_date). Ιστορικό 2016-2025 και αρχεία ημέρας· None = λείπει."""
    fill = {k: {} for k in dams}
    gen = {u: {} for u in units}
    last = None
    for f in sorted(glob.glob(os.path.join(data_dir, "history", "admie_*.json"))):
        try:
            with open(f, encoding="utf-8") as fh:
                h = json.load(fh)
            ds = [date.fromisoformat(x) for x in h["Dates"]]
        except (OSError, ValueError, KeyError) as e:
            log(f"   ! {os.path.basename(f)} δεν διαβάζεται ({type(e).__name__}) - παραλείπεται")
            continue
        for k in dams:
            for d, v in zip(ds, (h.get("Fill") or {}).get(k) or []):
                fill[k][d] = v
        for u in units:
            for d, v in zip(ds, (h.get("Gen") or {}).get(u) or []):
                gen[u][d] = v
        last = max(last, ds[-1]) if last and ds else (ds[-1] if ds else last)
    for f in sorted(glob.glob(os.path.join(data_dir, "days", "*.json"))):
        try:
            with open(f, encoding="utf-8") as fh:
                r = json.load(fh)
            d = date.fromisoformat(r["Date"])
        except (OSError, ValueError, KeyError) as e:
            log(f"   ! {os.path.basename(f)} δεν διαβάζεται ({type(e).__name__}) - παραλείπεται")
            continue
        res = r.get("Reservoir") or {}
        for k in dams:
            if res.get(k) is not None:
                fill[k][d] = float(res[k])
        if (r.get("Meta") or {}).get("Status", {}).get("scada") == "ok" and r.get("Hourly"):
            for u in units:
                e = CC.energy(r, "SCADA_" + u)
                if e is not None:
                    gen[u][d] = e
        if res or r.get("Hourly"):
            last = max(last, d) if last else d
    for k in dams:                                         # 0,00% σε μεγάλο φράγμα = άκυρη μέτρηση (όπως στο ισοζύγιο νερού)
        if caps[k] >= W.LARGE_DAM_HM3:
            fill[k] = {d: (None if v == 0.0 else v) for d, v in fill[k].items()}
    return fill, gen, last


# ---------------------------------------------------------------- κενά
def interp_linear(s, maxgap):
    """Γραμμική παρεμβολή σε κενά ≤ maxgap ανάμεσα σε δύο γνωστές τιμές. -> (σειρά, σημαίες «παρεμβλήθηκε»)"""
    s = list(s)
    flag = [False] * len(s)
    i, n = 0, len(s)
    while i < n:
        if s[i] is None:
            j = i
            while j < n and s[j] is None:
                j += 1
            if i > 0 and j < n and (j - i) <= maxgap and s[i - 1] is not None:
                a, b = s[i - 1], s[j]
                for q in range(i, j):
                    s[q] = a + (b - a) * (q - (i - 1)) / (j - (i - 1))
                    flag[q] = True
            i = j
        else:
            i += 1
    return s, flag


def reconstruct_volume(V, Q, maxgap):
    """Συμπληρώνει κενά ≤ maxgap του όγκου με ΣΤΑΘΕΡΗ ΕΙΣΡΟΗ μέσα στο κενό και τη γνωστή παραγωγή Q:
    V(i) = V(p) + (i−p)·Ī − Σ_{q=p}^{i−1} Q(q),  Ī = (V(n) − V(p) + Σ_{q=p}^{n−1} Q(q)) / (n − p)   (p, n = οι γνωστές ημέρες γύρω από το κενό).
    Απαιτεί γνωστή παραγωγή σε όλες τις ημέρες p … n−1. -> (όγκοι, σημαίες)"""
    V = list(V)
    flag = [False] * len(V)
    i, n = 0, len(V)
    while i < n:
        if V[i] is None:
            j = i
            while j < n and V[j] is None:
                j += 1
            p, q_ = i - 1, j
            if p >= 0 and q_ < n and (j - i) <= maxgap and V[p] is not None and all(Q[x] is not None for x in range(p, q_)):
                ibar = (V[q_] - V[p] + sum(Q[x] for x in range(p, q_))) / (q_ - p)
                acc = 0.0
                for x in range(i, j):
                    acc += Q[x - 1]
                    V[x] = V[p] + (x - p) * ibar - acc
                    flag[x] = True
            i = j
        else:
            i += 1
    return V, flag


# ---------------------------------------------------------------- εβδομαδιαία εισροή
def river_setup(river, meta, heads, ratio, caps_override=None):
    rid = river["Id"]
    groups = W.GROUPS[rid]
    dams = [k for g, _a, _b in groups for k in g]
    caps = {k: float(meta["Reservoirs"][k]["CapacityHm3"]) for k in dams}
    if caps_override:
        caps.update({k: v for k, v in caps_override.items() if k in caps})
    outs = [g[-1] for g, _a, _b in groups]
    unit = W.TURBINE_UNIT.get(outs[-1], meta["Reservoirs"][outs[-1]]["Units"][0])
    net, _gross, _est, _ratio = W.k_values(heads, outs, ratio)
    return {"id": rid, "dams": dams, "caps": caps, "unit": unit, "k": net[outs[-1]]}


def weekly_inflow(S, fill, gen, first, last, maxgap=MAXGAP):
    """{Δευτέρα: (hm³, παρεμβλήθηκε)} για κάθε εβδομάδα με επαρκή δεδομένα."""
    days = [first + timedelta(days=i) for i in range((last - first).days + 1)]
    V = []
    for d in days:
        vs = [fill[k].get(d) for k in S["dams"]]
        V.append(None if any(v is None for v in vs) else sum(v / 100.0 * S["caps"][k] for v, k in zip(vs, S["dams"])))
    Q = [None if gen[S["unit"]].get(d) is None else gen[S["unit"]][d] / S["k"] for d in days]
    Qf, qflag = interp_linear(Q, maxgap)
    Vf, vflag = reconstruct_volume(V, Qf, maxgap)
    out = {}
    m = first + timedelta(days=(7 - first.weekday()) % 7)           # πρώτη Δευτέρα
    while m + timedelta(days=7) <= last:
        i = (m - first).days
        j = i + 7
        if Vf[i] is not None and Vf[j] is not None and all(x is not None for x in Qf[i:j]):
            out[m] = (Vf[j] - Vf[i] + sum(Qf[i:j]), vflag[i] or vflag[j] or any(qflag[i:j]))
        m += timedelta(days=7)
    return out


# ---------------------------------------------------------------- στατιστικά
def pct(v, p):
    v = sorted(v)
    i = (len(v) - 1) * p
    lo = int(i)
    hi = min(lo + 1, len(v) - 1)
    return v[lo] + (v[hi] - v[lo]) * (i - lo)


def band_table(weekly, y0, y1, cur_year, slim=False):
    """Λίστα ανά ISO εβδομάδα {Wk, N, Min, P25, Median, P75, Max, MinYear, MaxYear} από τα έτη y0..y1 (ISO έτος της Δευτέρας).
    slim=True (εναλλακτική βάση): μόνο {Wk, N, P25, Median, P75} για να μένει μικρό το αρχείο."""
    by = {}
    for m, (v, _f) in weekly.items():
        iy, wk, _ = m.isocalendar()
        if y0 <= iy <= y1 and iy != cur_year:
            by.setdefault(wk, []).append((v, iy))
    out = {}
    for wk, vs in by.items():
        if len(vs) < MIN_N_BAND:
            continue
        v = [x for x, _y in vs]
        lo, hi = min(vs), max(vs)
        out[wk] = {"Wk": wk, "N": len(v), "P25": round(pct(v, .25), 2), "Median": round(pct(v, .5), 2), "P75": round(pct(v, .75), 2)}
        if not slim:
            out[wk].update({"Min": round(lo[0], 2), "Max": round(hi[0], 2), "MinYear": lo[1], "MaxYear": hi[1]})
    return [out[k] for k in sorted(out)]


def rank_among(base_vals, cur):
    """-> (θέση από την κορυφή: 1 = υψηλότερη, θέση από τον πάτο: 1 = χαμηλότερη, από πόσα)"""
    top = 1 + sum(1 for x in base_vals if x > cur)
    bottom = 1 + sum(1 for x in base_vals if x < cur)
    return top, bottom, len(base_vals) + 1


def classify(base_vals, cur):
    if len(base_vals) < MIN_N_REGIME:
        return None
    top, bottom, of = rank_among(base_vals, cur)
    if top <= EXTREME:
        return "wet", top, of
    if bottom <= EXTREME:
        return "dry", top, of
    return "transitional", top, of


def four_week_sum(weekly, monday):
    """Άθροισμα των REGIME_WEEKS εβδομάδων που τελειώνουν στη Δευτέρα monday· (None, False) αν λείπει κάποια."""
    tot, interp = 0.0, False
    for k in range(REGIME_WEEKS):
        w = weekly.get(monday - timedelta(days=7 * k))
        if w is None:
            return None, False
        tot += w[0]
        interp = interp or w[1]
    return tot, interp


def regime(weekly, last_date, y0, y1, cur_year):
    """Καθεστώς από την τελευταία πλήρη εβδομάδα. -> dict ή None (και ο λόγος)."""
    cands = [m for m in weekly if m.isocalendar()[0] == cur_year or m + timedelta(days=7) > last_date - timedelta(days=21)]
    if not cands:
        return None, "no_current"
    latest = max(cands)
    if (last_date - (latest + timedelta(days=7))).days > STALE_DAYS:
        return None, "stale"
    cur, interp = four_week_sum(weekly, latest)
    if cur is None:
        return None, "gap"
    iy, wk, _ = latest.isocalendar()
    base = []
    for y in range(y0, y1 + 1):
        try:
            mon = date.fromisocalendar(y, wk, 1)
        except ValueError:
            continue                                                  # π.χ. εβδομάδα 53 σε έτος που δεν την έχει
        s, _i = four_week_sum(weekly, mon)
        if s is not None:
            base.append(s)
    c = classify(base, cur)
    if c is None:
        return None, "few_years"
    name, top, of = c
    return {"Weeks": [(latest - timedelta(days=7 * k)).isoformat() for k in range(REGIME_WEEKS - 1, -1, -1)], "LastWeek": latest.isoformat(), "Wk": wk,
            "Mm3": round(cur, 2), "Median": round(pct(base, .5), 2), "P25": round(pct(base, .25), 2), "P75": round(pct(base, .75), 2),
            "N": len(base), "Rank": top, "Of": of, "Regime": name, "Interp": bool(interp)}, None


# ---------------------------------------------------------------- ποταμός
def build_river(river, meta, heads, ratio, fill, gen, first, last, cur_year):
    S = river_setup(river, meta, heads, ratio)
    weekly = weekly_inflow(S, fill, gen, first, last)
    bands = band_table(weekly, BASE[0], BASE[1], cur_year)
    ext = band_table(weekly, EXT[0], EXT[1], cur_year, slim=True)
    bw = {b["Wk"]: b for b in bands}
    base_by_wk = {}
    for m, (v, _f) in weekly.items():
        iy, wk, _ = m.isocalendar()
        if BASE[0] <= iy <= BASE[1]:
            base_by_wk.setdefault(wk, []).append(v)
    cur_rows = []
    for m in sorted(weekly):
        iy, wk, _ = m.isocalendar()
        if iy != cur_year:
            continue
        v, fl = weekly[m]
        row = {"Start": m.isoformat(), "Wk": wk, "Mm3": round(v, 2), "Interp": bool(fl)}
        if wk in bw:
            top, _bt, of = rank_among(base_by_wk[wk], v)
            row.update({"Rank": top, "Of": of, "DeltaMedian": round(v - bw[wk]["Median"], 2)})
        cur_rows.append(row)
    reg, why = regime(weekly, last, BASE[0], BASE[1], cur_year)
    reg_ext, _w = regime(weekly, last, EXT[0], EXT[1], cur_year)
    if reg is not None and reg_ext is not None:
        reg["Extended"] = {"Rank": reg_ext["Rank"], "Of": reg_ext["Of"], "Regime": reg_ext["Regime"], "N": reg_ext["N"]}
    sens = None
    if river["Id"] == "aliakmonas" and "ILARIONAS" in S["dams"]:
        S2 = river_setup(river, meta, heads, ratio, {"ILARIONAS": ILARIONAS_ALT})
        w2 = weekly_inflow(S2, fill, gen, first, last)
        r2, _w2 = regime(w2, last, BASE[0], BASE[1], cur_year)
        sens = {"IlarionasHm3": ILARIONAS_ALT, "Used": S["caps"]["ILARIONAS"]}
        if r2 is not None:
            sens.update({"Mm3": r2["Mm3"], "Rank": r2["Rank"], "Of": r2["Of"], "Regime": r2["Regime"]})
    base_weeks = [m for m in weekly if BASE[0] <= m.isocalendar()[0] <= BASE[1]]
    n_expected = sum(date(y, 12, 28).isocalendar()[1] for y in range(BASE[0], BASE[1] + 1))     # εβδομάδες ISO των ετών βάσης (το 2020 έχει 53)
    return {"Name": river["Name"], "ExitUnit": S["unit"], "KNet": round(S["k"], 1), "Dams": S["dams"],
            "LowConfidence": LOW_CONFIDENCE.get(river["Id"]),
            "Weeks": bands, "Extended": ext, "Current": cur_rows,
            "Regime": reg, "RegimeUnavailable": why if reg is None else None, "Sensitivity": sens,
            "Quality": {"BaselineWeeksWithValue": len(base_weeks), "BaselineWeeksInterpolated": sum(1 for m in base_weeks if weekly[m][1]),
                        "BaselineWeeksPossible": n_expected, "CurrentWeeksWithValue": len(cur_rows),
                        "CurrentWeeksInterpolated": sum(1 for r in cur_rows if r["Interp"])}}


def main():
    for f in ("reservoirs.json", "plant_heads.json"):
        if not os.path.exists(os.path.join(DATA, f)):
            log(f"Λείπει το data/{f}")
            return 1
    with open(os.path.join(DATA, "reservoirs.json"), encoding="utf-8") as f:
        meta = json.load(f)
    with open(os.path.join(DATA, "plant_heads.json"), encoding="utf-8") as f:
        hd = json.load(f)
    heads, ratio = hd["Plants"], hd.get("GrossToNetRatio")
    rivers = [r for r in meta["Rivers"] if r["Id"] in W.GROUPS]
    dams, units, caps = [], [], {}
    for r in rivers:
        S = river_setup(r, meta, heads, ratio)
        dams += [k for k in S["dams"] if k not in dams]
        units.append(S["unit"])
        caps.update(S["caps"])
    fill, gen, last = load_series(DATA, dams, sorted(set(units)), caps)
    if last is None:
        log("Δεν βρέθηκαν δεδομένα")
        return 1
    firsts = [d for k in dams for d in fill[k]]
    first = min(firsts) if firsts else None
    if first is None:
        log("Δεν βρέθηκαν στάθμες")
        return 1
    cur_year = (last - timedelta(days=7)).isocalendar()[0]
    res = {}
    for r in rivers:
        res[r["Id"]] = build_river(r, meta, heads, ratio, fill, gen, first, last, cur_year)
        n = res[r["Id"]]
        rg = n["Regime"]
        log(f"{r['Id']}: {n['Quality']['BaselineWeeksWithValue']}/{n['Quality']['BaselineWeeksPossible']} εβδομάδες βάσης "
            f"({n['Quality']['BaselineWeeksInterpolated']} με παρεμβολή) | "
            + (f"καθεστώς {rg['Regime']} (θέση {rg['Rank']}/{rg['Of']}, {rg['Mm3']} hm³ έναντι διαμέσου {rg['Median']})" if rg else f"χωρίς καθεστώς ({n['RegimeUnavailable']})"))
    if not res:
        log("Κανένας ποταμός")
        return 1
    doc = {"Schema": 1, "Generated": datetime.now(ATHENS).strftime("%Y-%m-%dT%H:%M:%S%z"), "CurrentYear": cur_year, "LastDate": last.isoformat(),
           "Baseline": {"Years": list(BASE), "Extended": list(EXT), "Default": "2018–2025 (όπως ο πίνακας αποθέματος)"},
           "Rule": {"Weeks": REGIME_WEEKS, "Extreme": EXTREME, "MinYears": MIN_N_REGIME, "MaxGapDays": MAXGAP},
           "Method": "εβδομαδιαία εισροή = V(επόμενη Δευτέρα) − V(Δευτέρα) + ΣQ· κενά ≤ 3 ημερών με παρεμβολή εισροής (στάθμη) και γραμμική (παραγωγή)· καθαρή πτώση",
           "Note": "Φαινόμενη εισροή: φυσικές εισροές μείον όσα δεν μετράμε (αρδεύσεις, εξάτμιση, υπερχειλίσεις, οικολογική παροχή). Η θέση 1 είναι η υψηλότερη.",
           "Rivers": res}
    os.makedirs(DATA, exist_ok=True)
    jsonio.write_json_if_changed(OUT, doc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
