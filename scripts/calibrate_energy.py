#!/usr/bin/env python3
"""
Βαθμονόμηση "όγκος νερού -> αποθηκευμένη ενέργεια" πάνω στα εβδομαδιαία του ENTSO-E (16.1.D).

Μοντέλο (καταρράκτης): κάθε hm3 στο φράγμα i αξίζει όσο παράγει καθώς κατεβαίνει τους σταθμούς
κατάντη (και τον δικό του):   e_i = Σ_{j κατάντη του i, συμπεριλαμβανομένου}  k_j      [MWh / hm3]
Αποθηκευμένη ενέργεια = Σ_i e_i · V_i,   V_i = (πλήρωση ADMIE %) × (ωφέλιμη χωρητικότητα PDF).
Οι k_j εκτιμώνται με μη-αρνητικά ελάχιστα τετράγωνα (NNLS) πάνω στις εβδομαδιαίες τιμές του ENTSO-E.

Σύμβαση εβδομάδας (επαληθευμένη στα δεδομένα 2026): η τιμή ENTSO-E μιας εβδομάδας (Δευτέρα 00:00 τοπική)
ισούται με τον ΜΕΣΟ ΟΡΟ των ημερήσιων τιμών ΤΕΛΟΥΣ ημέρας, δηλαδή των αρχείων ADMIE με ημερομηνία
Δευτέρα+1 ... Δευτέρα+7 (η μέτρηση του ADMIE είναι στις 00:00 της ημέρας).

Είσοδοι : data/days/*.json , data/entsoe_reservoir.json , data/reservoirs.json
Έξοδοι  : data/energy_factors.json , data/stored_energy.json

Χρήση:   python scripts/calibrate_energy.py            (απαιτεί numpy, scipy)

Reliability ανά ποταμό: διασπορά ανάμεσα σε 4 εναλλακτικές υποθέσεις (good ≤5%, fair ≤15%, αλλιώς poor).
Σε συνθετικά δεδομένα με γνωστή αλήθεια το σφάλμα ήταν της ίδιας τάξης με τη διασπορά (έως ~11% όταν η διασπορά ήταν ~9%).

ΠΡΟΣΟΧΗ: το σύνολο της ενέργειας προσδιορίζεται καλά. Η κατανομή ανά φράγμα όχι πάντα, επειδή οι ταμιευτήρες
ενός καταρράκτη κινούνται μαζί. Κάθε συντελεστής έχει διάστημα εμπιστοσύνης (bootstrap) και ένδειξη Identifiable.
"""

import glob
import json
import os
import sys
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
from scipy.optimize import nnls

DATA = "data"
LARGE_DAM_HM3 = 100.0        # για φράγματα >= αυτού του όγκου, η τιμή 0,00% θεωρείται άκυρη μέτρηση
TRAIN_SPLIT = date(2026, 6, 1)
N_BOOT = 1000
SEED = 7
MIN_WEEKS = 20
ATHENS = ZoneInfo("Europe/Athens")


def log(m=""):
    print(m, flush=True)


# ---------------------------------------------------------------- είσοδοι
def load_meta():
    with open(os.path.join(DATA, "reservoirs.json"), encoding="utf-8") as f:
        meta = json.load(f)
    keys = [k for r in meta["Rivers"] for k in r["Order"]]
    cap = {k: float(meta["Reservoirs"][k]["CapacityHm3"]) for k in keys}
    return meta, keys, cap


def load_days():
    out = {}
    for f in glob.glob(os.path.join(DATA, "days", "*.json")):
        with open(f, encoding="utf-8") as fh:
            r = json.load(fh)
        if r.get("Reservoir"):
            out[date.fromisoformat(r["Date"])] = r["Reservoir"]
    return out


def load_entsoe():
    with open(os.path.join(DATA, "entsoe_reservoir.json"), encoding="utf-8") as f:
        w = json.load(f)["Weeks"]
    return {date.fromisoformat(x["StartLocal"]): float(x["MWh"]) for x in w}, {date.fromisoformat(x["StartLocal"]): x.get("IsoWeek") for x in w}


def sanitize(days, keys, cap):
    """Μεγάλα φράγματα με πλήρωση ακριβώς 0,00% = άκυρη μέτρηση -> γραμμική παρεμβολή. Επιστρέφει (πίνακας, αναφορά)."""
    dates = sorted(days)
    P = np.array([[days[d][k] for k in keys] for d in dates], float)       # ποσοστά
    notes = []
    t = np.arange(len(dates), dtype=float)
    for j, k in enumerate(keys):
        if cap[k] < LARGE_DAM_HM3:
            continue
        bad = P[:, j] == 0.0
        if bad.any() and (~bad).sum() >= 2:
            P[bad, j] = np.interp(t[bad], t[~bad], P[~bad, j])
            idx = np.where(bad)[0]
            runs, s, p = [], idx[0], idx[0]
            for i in idx[1:]:
                if i != p + 1:
                    runs.append((s, p)); s = i
                p = i
            runs.append((s, p))
            for a, b in runs:
                notes.append({"Dam": k, "From": dates[a].isoformat(), "To": dates[b].isoformat(),
                              "Days": int(b - a + 1), "Action": "0,00% θεωρήθηκε άκυρη τιμή, γραμμική παρεμβολή"})
    return dates, P, notes


# ---------------------------------------------------------------- μοντέλο
def cascade_design(V, keys, meta):
    """Στήλη j = συνολικός όγκος όλων των φραγμάτων ανάντη-ή-ίσα με τον σταθμό j."""
    X = np.zeros((V.shape[0], len(keys)))
    for r in meta["Rivers"]:
        order = r["Order"]
        for pos, kj in enumerate(order):
            X[:, keys.index(kj)] = V[:, [keys.index(k) for k in order[:pos + 1]]].sum(1)
    return X


def e_from_k(p, keys, meta):
    e = np.zeros(len(keys))
    for r in meta["Rivers"]:
        order = r["Order"]
        ks = [p[keys.index(k)] for k in order]
        for pos, k in enumerate(order):
            e[keys.index(k)] = sum(ks[pos:])
    return e


def river_design(V, keys, meta):
    return np.column_stack([V[:, [keys.index(k) for k in r["Order"]]].sum(1) for r in meta["Rivers"]])


def river_energy(e, v, keys, meta):
    """GWh ανά ποταμό για διάνυσμα e (MWh/hm3 ανά φράγμα) και όγκους v (hm3)."""
    return {r["Id"]: float(sum(e[keys.index(k)] * v[keys.index(k)] for k in r["Order"]) / 1000) for r in meta["Rivers"]}


def week_matrix(dates, V, weeks, keys, meta):
    pos = {d: i for i, d in enumerate(dates)}
    mons, rows = [], []
    for m in sorted(weeks):
        need = [m + timedelta(t) for t in range(1, 8)]
        if all(d in pos for d in need):
            mons.append(m)
            rows.append(np.mean([V[pos[d]] for d in need], axis=0))
    return mons, np.array(rows)


def rms(a):
    return float(np.sqrt(np.mean(np.square(a))))


def main():
    for f in ("reservoirs.json", "entsoe_reservoir.json"):
        if not os.path.exists(os.path.join(DATA, f)):
            log(f"Λείπει το data/{f}")
            return 1
    meta, keys, cap = load_meta()
    days = load_days()
    weeks, iso = load_entsoe()
    if not days:
        log("Δεν υπάρχουν ημέρες με δεδομένα ταμιευτήρων")
        return 1
    dates, P, notes = sanitize(days, keys, cap)
    capv = np.array([cap[k] for k in keys])
    V = P / 100.0 * capv                                                    # hm3 ανά ημέρα και φράγμα
    for n in notes:
        log(f"   ! {n['Dam']} {n['From']}→{n['To']} ({n['Days']} ημέρες): {n['Action']}")

    mons, Vw = week_matrix(dates, V, weeks, keys, meta)
    if len(mons) < MIN_WEEKS:
        log(f"Μόνο {len(mons)} εβδομάδες με πλήρη δεδομένα (χρειάζονται ≥{MIN_WEEKS})")
        return 1
    y = np.array([weeks[m] for m in mons])
    X = cascade_design(Vw, keys, meta)
    n = len(y)
    fit = lambda A, b: nnls(A, b)[0]
    p = fit(X, y)
    r_fit = rms(X @ p - y)
    loo = np.array([X[i] @ fit(X[np.arange(n) != i], y[np.arange(n) != i]) - y[i] for i in range(n)])
    tr = np.array([m < TRAIN_SPLIT for m in mons])
    block = None
    if tr.sum() >= 10 and (~tr).sum() >= 5:
        block = rms(X[~tr] @ fit(X[tr], y[tr]) - y[~tr])
    # σύγκριση με απλό συντελεστή
    tot = Vw.sum(1)
    k1 = float(np.linalg.lstsq(tot[:, None], y, rcond=None)[0][0])
    loo1 = rms(np.array([tot[i] * np.linalg.lstsq(np.delete(tot, i)[:, None], np.delete(y, i), rcond=None)[0][0] - y[i] for i in range(n)]))

    rng = np.random.default_rng(SEED)
    e0 = e_from_k(p, keys, meta)
    boot = np.array([e_from_k(fit(X[ix], y[ix]), keys, meta) for ix in (rng.integers(0, n, n) for _ in range(N_BOOT))])
    lo, hi = np.percentile(boot, [5, 95], axis=0)
    ident = []
    for i in range(len(keys)):
        width = (hi[i] - lo[i]) / e0[i] if e0[i] > 0 else float("inf")
        ident.append("ok" if (lo[i] > 0 and width <= 0.6) else ("weak" if e0[i] > 0 else "none"))

    # ΕΥΑΙΣΘΗΣΙΑ ΣΕ ΥΠΟΘΕΣΕΙΣ: το bootstrap υποτιμά την αβεβαιότητα (επαληθεύτηκε σε συνθετικά δεδομένα),
    # γι' αυτό μετράμε και πόσο αλλάζει η ενέργεια ανά ποταμό όταν αλλάζουμε τις υποθέσεις.
    vlast = V[-1]
    alts = {"cascade": river_energy(e0, vlast, keys, meta)}
    Xr = river_design(Vw, keys, meta)
    pr = nnls(Xr, y)[0]
    Vl_r = river_design(vlast[None, :], keys, meta)[0]
    alts["river-level"] = {r["Id"]: float(pr[i] * Vl_r[i] / 1000) for i, r in enumerate(meta["Rivers"])}
    if tr.sum() >= 10:
        alts["cascade-train-only"] = river_energy(e_from_k(fit(X[tr], y[tr]), keys, meta), vlast, keys, meta)
    if "KASTRAKI" in keys:
        Pc = P.copy()
        Pc[:, keys.index("KASTRAKI")] = np.minimum(Pc[:, keys.index("KASTRAKI")], 100.0)
        Vc = Pc / 100.0 * capv
        mons_c, Vwc = week_matrix(dates, Vc, weeks, keys, meta)
        yc = np.array([weeks[m] for m in mons_c])
        alts["cascade-kastraki-capped"] = river_energy(e_from_k(fit(cascade_design(Vwc, keys, meta), yc), keys, meta), Vc[-1], keys, meta)
    by_river_latest = {}
    for r in meta["Rivers"]:
        vals = [a[r["Id"]] for a in alts.values()]
        base = alts["cascade"][r["Id"]]
        spread = (max(vals) - min(vals)) / base if base > 0 else 0.0
        by_river_latest[r["Id"]] = {"GWh": round(base, 1), "Min": round(min(vals), 1), "Max": round(max(vals), 1),
                                    "SpreadPercent": round(spread * 100, 1),
                                    "Reliability": "good" if spread <= 0.05 else ("fair" if spread <= 0.15 else "poor")}
    tot_vals = [sum(a.values()) for a in alts.values()]

    # ενέργεια ανά ημέρα (εφαρμογή στις ημερήσιες μετρήσεις)
    daily = []
    for d, v in zip(dates, V):
        by_river = {}
        for r in meta["Rivers"]:
            idx = [keys.index(k) for k in r["Order"]]
            by_river[r["Id"]] = round(float((e0[idx] * v[idx]).sum() / 1000), 1)
        daily.append({"Date": d.isoformat(), "VolumeHm3": round(float(v.sum()), 1),
                      "TotalGWh": round(float((e0 * v).sum() / 1000), 1), "ByRiverGWh": by_river})
    weekly = [{"IsoWeek": iso.get(m), "StartLocal": m.isoformat(), "EntsoeMWh": round(float(a)),
               "ModelMWh": round(float(b)), "DiffGWh": round(float((b - a) / 1000), 1)}
              for m, a, b in zip(mons, y, X @ p)]

    last = dates[-1]
    vlast = V[-1]
    tot_boot = (boot * vlast).sum(1) / 1000
    now = datetime.now(ATHENS).strftime("%Y-%m-%dT%H:%M:%S%z")
    factors = {}
    for i, k in enumerate(keys):
        factors[k] = {"EnergyMWhPerHm3": round(float(e0[i]), 1), "P5": round(float(lo[i]), 1), "P95": round(float(hi[i]), 1),
                      "Identifiable": ident[i], "CapacityHm3": cap[k]}
    doc = {
        "Schema": 1, "Generated": now,
        "Method": "e_i = άθροισμα συντελεστών k_j των σταθμών κατάντη (συμπεριλαμβανομένου του i). k_j από NNLS στα εβδομαδιαία ENTSO-E.",
        "WeekConvention": "ENTSO-E εβδομάδα = μέσος όρος των αρχείων ADMIE Δευτέρα+1 ... Δευτέρα+7 (τιμές τέλους ημέρας)",
        "Weeks": {"Used": n, "From": mons[0].isoformat(), "To": mons[-1].isoformat()},
        "Fit": {"RmsGWh": round(r_fit / 1000, 2), "LeaveOneOutRmsGWh": round(rms(loo) / 1000, 2),
                "LeaveOneOutPercentOfMean": round(rms(loo) / y.mean() * 100, 2),
                "TrainBeforeTestAfter": {"Split": TRAIN_SPLIT.isoformat(), "RmsGWh": None if block is None else round(block / 1000, 2)},
                "SingleFactor": {"MWhPerHm3": round(k1, 1), "LeaveOneOutRmsGWh": round(loo1 / 1000, 2)}},
        "Factors": factors,
        "Latest": {"Date": last.isoformat(), "VolumeHm3": round(float(vlast.sum()), 1),
                   "TotalGWh": round(float((e0 * vlast).sum() / 1000), 1),
                   "TotalGWhP5": round(float(np.percentile(tot_boot, 5)), 1), "TotalGWhP95": round(float(np.percentile(tot_boot, 95)), 1),
                   "TotalGWhAcrossModels": {"Min": round(min(tot_vals), 1), "Max": round(max(tot_vals), 1), "Models": list(alts)},
                   "ByRiver": by_river_latest},
        "Sanitized": notes,
        "Limitations": [
            "Το συνολικό ενεργειακό απόθεμα προσδιορίζεται καλά. Οι συντελεστές ανά φράγμα όχι πάντα (οι ταμιευτήρες ενός καταρράκτη κινούνται μαζί).",
            "Φράγματα με Identifiable = weak/none έχουν μικρό όγκο ή ασαφή συντελεστή: μην τα διαβάζεις μεμονωμένα.",
            "Τα διαστήματα P5-P95 ανά φράγμα (bootstrap) ΥΠΟΤΙΜΟΥΝ την αβεβαιότητα: σε συνθετικά δεδομένα με γνωστούς συντελεστές, 3 από 5 φράγματα 'ok' είχαν την αληθινή τιμή εκτός διαστήματος (π.χ. Ιλαρίων/Πολύφυτο μπερδεύονται). Χρησιμοποίησε την ενέργεια ανά ποταμό (Latest.ByRiver, με Min/Max μεταξύ υποθέσεων) και όχι ανά φράγμα.",
            "Η εκτίμηση ημερήσιας τιμής εφαρμόζει τους συντελεστές στη μέτρηση 00:00 της ημέρας, ενώ οι συντελεστές βαθμονομήθηκαν σε μέσους όρους εβδομάδας.",
            "Οι συντελεστές βαθμονομήθηκαν με δεδομένα Ιανουαρίου-Σεπτεμβρίου 2026: να επανεκτιμηθούν όταν προστεθούν Οκτώβριος-Δεκέμβριος (νέα πλήρωση, Αμφιλοχία)."]}
    os.makedirs(DATA, exist_ok=True)
    for name, obj, ind in (("energy_factors.json", doc, 1), ("stored_energy.json", {"Schema": 1, "Generated": now, "Daily": daily, "Weekly": weekly}, 1)):
        tmp = os.path.join(DATA, name + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=ind)
            f.write("\n")
        os.replace(tmp, os.path.join(DATA, name))

    log(f"Εβδομάδες: {n} ({mons[0]} → {mons[-1]}) | RMS fit {r_fit/1000:.1f} GWh | LOO {rms(loo)/1000:.1f} GWh ({rms(loo)/y.mean()*100:.2f}%)"
        f" | απλός συντελεστής LOO {loo1/1000:.1f} GWh" + ("" if block is None else f" | train<{TRAIN_SPLIT}→test {block/1000:.1f} GWh"))
    log(f"Τελευταία ημέρα {last}: {doc['Latest']['TotalGWh']:,.0f} GWh (5–95%: {doc['Latest']['TotalGWhP5']:,.0f}–{doc['Latest']['TotalGWhP95']:,.0f})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
