#!/usr/bin/env python3
"""
Παραγωγή και ισοδύναμη εισροή έναντι «κανονικού»  ->  data/energy_climatology.json

Τρία πράγματα, όλα με την ίδια βάση ISO εβδομάδα × έτη 2018–2025 (όπως ο πίνακας αποθέματος και η εισροή, D100/D102):
 1. Εβδομαδιαία ΠΑΡΑΓΩΓΗ (GWh, Δευτέρα–Κυριακή) των μονάδων του αποθέματος (14 ταμιευτήρες ΧΩΡΙΣ Πηγές Αώου, όπως το «Ημέρες κάλυψης») και ανά ποταμό
    (όλες οι μονάδες της σειράς του ποταμού, συμπεριλαμβανομένων των Πηγών Αώου στον Άραχθο), και παραγωγή ΕΤΟΥΣ-ΜΕΧΡΙ-ΣΗΜΕΡΑ. ΑΚΑΘΑΡΙΣΤΗ: η άντληση δεν αφαιρείται
    (τα αντλητικά Σφηκιά–Ασώματα και Θησαυρός–Πλατανόβρυση ανακυκλώνουν νερό).
 2. Παραγωγή των τελευταίων 4 πλήρων εβδομάδων ανά ποταμό έναντι των ίδιων 4 εβδομάδων των ετών βάσης (θέση 1 = υψηλότερη).
 3. ΙΣΟΔΥΝΑΜΗ ΕΙΣΡΟΗ (GWh/ημέρα) = παραγωγή + μεταβολή αποθέματος − ενέργεια που επιστρέφει η άντληση. Μετριέται ΑΠΕΥΘΕΙΑΣ σε ενέργεια (όχι hm³ × συντελεστές ανά
    ποταμό, των οποίων η αξιοπιστία είναι «fair/poor»): απόθεμα = Σ συντελεστής ταμιευτήρα × όγκος (energy_factors.json), όπως στη σελίδα. Είναι ΚΑΤΩ ΟΡΙΟ (οι μη
    μετρημένες απολήψεις, π.χ. άρδευση, είναι μέσα). Επιστροφή άντλησης: 2026 εκτίμηση ανά σταθμό × συντελεστής κύκλου (pump_daily/psh_daily), αλλιώς 70 % της άντλησης
    SCADA· πριν το 2026 ΥΠΟΘΕΣΗ 70 % της άντλησης SCADA (δεν υπάρχει εκτίμηση ανά σταθμό).
Κενά: έως 3 ημέρες συμπληρώνονται και η εβδομάδα σημαίνεται (Interp)· το απόθεμα με σταθερή ΕΙΣΡΟΗ στο κενό (όπως η εισροή ποταμών), η παραγωγή γραμμικά.
Είσοδοι: data/history/admie_*.json, data/days/*.json, data/reservoirs.json, data/energy_factors.json, data/pump_daily.json, data/psh_daily.json   Έξοδος: data/energy_climatology.json
"""
import glob
import json
import os
import sys
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import clock_change as CC
import jsonio
import build_inflow as I                           # κοινός κώδικας κενών, ζωνών και κατάταξης (δοκιμασμένος στο test_inflow)

DATA = "data"
OUT = os.path.join(DATA, "energy_climatology.json")
ATHENS = ZoneInfo("Europe/Athens")
PUMP_BACK_FALLBACK = 0.70                          # επιστροφή άντλησης όταν δεν υπάρχει εκτίμηση ανά σταθμό (όπως η σελίδα)
MIN_N_YTD = 6                                      # ελάχιστα έτη βάσης για κατάταξη έτους-μέχρι-σήμερα


def log(m=""):
    print(m, flush=True)


def sload(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


# ---------------------------------------------------------------- είσοδοι
def load_daily(data_dir, dams, units, all_units):
    """-> (fill {dam: {date: %}}, gen {unit: {date: MWh}}, pump_scada {date: MWh}, last_date)"""
    fill = {k: {} for k in dams}
    gen = {u: {} for u in all_units}
    pump = {}
    last = None
    for f in sorted(glob.glob(os.path.join(data_dir, "history", "admie_*.json"))):
        h = sload(f)
        try:
            ds = [date.fromisoformat(x) for x in h["Dates"]]
        except (TypeError, KeyError, ValueError):
            log(f"   ! {os.path.basename(f)} δεν διαβάζεται - παραλείπεται")
            continue
        for k in dams:
            for d, v in zip(ds, (h.get("Fill") or {}).get(k) or []):
                fill[k][d] = v
        for u in all_units:
            for d, v in zip(ds, (h.get("Gen") or {}).get(u) or []):
                gen[u][d] = v
        for d, v in zip(ds, h.get("Pump") or []):
            pump[d] = v
        if ds:
            last = max(last, ds[-1]) if last else ds[-1]
    for f in sorted(glob.glob(os.path.join(data_dir, "days", "*.json"))):
        r = sload(f)
        try:
            d = date.fromisoformat(r["Date"])
        except (TypeError, KeyError, ValueError):
            log(f"   ! {os.path.basename(f)} δεν διαβάζεται - παραλείπεται")
            continue
        res = r.get("Reservoir") or {}
        for k in dams:
            if res.get(k) is not None:
                fill[k][d] = float(res[k])
        if (r.get("Meta") or {}).get("Status", {}).get("scada") == "ok" and r.get("Hourly"):
            for u in all_units:
                e = CC.energy(r, "SCADA_" + u)
                if e is not None:
                    gen[u][d] = e
            p = CC.energy(r, "SCADA_Pump")
            if p is not None:
                pump[d] = p
        if res or r.get("Hourly"):
            last = max(last, d) if last else d
    return fill, gen, pump, last


def pump_back_series(data_dir, pump_scada, first, last):
    """{ημέρα: GWh που επιστρέφει η άντληση στο απόθεμα} — 2026+: εκτίμηση ανά σταθμό × συντελεστής κύκλου, αλλιώς 70 % της SCADA· πριν: 70 % της SCADA."""
    out = {}
    est = {}
    pd_ = sload(os.path.join(data_dir, "pump_daily.json")) or []
    psh = (sload(os.path.join(data_dir, "psh_daily.json")) or {}).get("Plants") or {}
    cs = (psh.get("SFIKIA") or {}).get("CycleFactor")
    ct = (psh.get("THESAVROS") or {}).get("CycleFactor")
    for x in pd_ if isinstance(pd_, list) else []:
        try:
            d = date.fromisoformat(x["Date"])
        except (KeyError, ValueError, TypeError):
            continue
        if x.get("EstSfikiaMWh") is not None and x.get("EstThesavrosMWh") is not None and cs and ct:
            est[d] = (x["EstSfikiaMWh"] * cs + x["EstThesavrosMWh"] * ct) / 1000.0
        elif x.get("ScadaMWh") is not None:
            est[d] = PUMP_BACK_FALLBACK * x["ScadaMWh"] / 1000.0
    d = first
    while d <= last:
        if d in est:
            out[d] = est[d]
        elif pump_scada.get(d) is not None:
            out[d] = PUMP_BACK_FALLBACK * pump_scada[d] / 1000.0
        d += timedelta(days=1)
    return out


# ---------------------------------------------------------------- εβδομαδιαία αθροίσματα
def daily_sum(gen, units, first, last):
    """{ημέρα: GWh} με άθροισμα μονάδων· None αν λείπει οποιαδήποτε μονάδα εκείνη την ημέρα."""
    out = {}
    d = first
    while d <= last:
        vs = [gen[u].get(d) for u in units]
        out[d] = None if (not units or any(v is None for v in vs)) else sum(vs) / 1000.0
        d += timedelta(days=1)
    return out


def weekly_sum(daily, first, last, maxgap=I.MAXGAP):
    """{Δευτέρα: (GWh, παρεμβλήθηκε)} — εβδομάδα με και τις 7 ημέρες (κενά ≤ maxgap με γραμμική παρεμβολή)."""
    days = [first + timedelta(days=i) for i in range((last - first).days + 1)]
    s, flag = I.interp_linear([daily.get(d) for d in days], maxgap)
    out = {}
    m = first + timedelta(days=(7 - first.weekday()) % 7)
    while m + timedelta(days=6) <= last:
        i = (m - first).days
        w = s[i:i + 7]
        if all(x is not None for x in w):
            out[m] = (sum(w), any(flag[i:i + 7]))
        m += timedelta(days=7)
    return out


def year_to_date(daily, first, last, years, cur_year):
    """Παραγωγή 1 Ιαν … (μήνας/ημέρα της τελευταίας ημέρας) ανά έτος· οι ημέρες που λείπουν συμπληρώνονται με τον μέσο όρο των παρουσών και μετριούνται."""
    res = {}
    for y in years:
        try:
            end = date(y, last.month, last.day)
        except ValueError:
            end = date(y, last.month, last.day - 1)
        start = date(y, 1, 1)
        if start < first:
            continue
        ds = [start + timedelta(days=i) for i in range((end - start).days + 1)]
        s, _fl = I.interp_linear([daily.get(d) for d in ds], I.MAXGAP)
        pres = [v for v in s if v is not None]
        if not pres or len(pres) < 0.9 * len(ds):
            continue
        miss = len(ds) - len(pres)
        res[y] = {"GWh": round(sum(pres) + miss * (sum(pres) / len(pres)), 2), "MissingDays": miss}       # 2 δεκαδικά: το ποσοστό διαφοράς υπολογίζεται από μη στρογγυλοποιημένα ποσά
    return res


# ---------------------------------------------------------------- ποσά ανά ποταμό και σύνολο
def gen_block(weekly, last, cur_year, with_last4=False):
    """Ζώνες, τρέχουσες εβδομάδες και (προαιρετικά) 4 εβδομάδες για ένα σύνολο μονάδων."""
    bands = I.band_table(weekly, I.BASE[0], I.BASE[1], cur_year)
    bw = {b["Wk"]: b for b in bands}
    byw = {}
    for m, (v, _f) in weekly.items():
        iy, wk, _ = m.isocalendar()
        if I.BASE[0] <= iy <= I.BASE[1]:
            byw.setdefault(wk, []).append(v)
    cur = []
    for m in sorted(weekly):
        iy, wk, _ = m.isocalendar()
        if iy != cur_year:
            continue
        v, fl = weekly[m]
        row = {"Start": m.isoformat(), "Wk": wk, "GWh": round(v, 2), "Interp": bool(fl)}
        if wk in bw:
            top, _b, of = I.rank_among(byw[wk], v)
            row.update({"Rank": top, "Of": of, "DeltaMedian": round(v - bw[wk]["Median"], 2)})
        cur.append(row)
    out = {"Weeks": bands, "Current": cur}
    if with_last4:
        out["Last4"] = last4(weekly, last, cur_year)
    return out


def last4(weekly, last, cur_year):
    cands = [m for m in weekly if m.isocalendar()[0] == cur_year]
    if not cands:
        return None
    latest = max(cands)
    if (last - (latest + timedelta(days=7))).days > I.STALE_DAYS:
        return None
    cur, interp = I.four_week_sum(weekly, latest)
    if cur is None:
        return None
    wk = latest.isocalendar()[1]
    base = []
    for y in range(I.BASE[0], I.BASE[1] + 1):
        try:
            mon = date.fromisocalendar(y, wk, 1)
        except ValueError:
            continue
        s, _i = I.four_week_sum(weekly, mon)
        if s is not None:
            base.append(s)
    if len(base) < I.MIN_N_REGIME:
        return None
    top, _b, of = I.rank_among(base, cur)
    return {"Weeks": [(latest - timedelta(days=7 * k)).isoformat() for k in range(I.REGIME_WEEKS - 1, -1, -1)], "LastWeek": latest.isoformat(), "Wk": wk,
            "GWh": round(cur, 2), "Median": round(I.pct(base, .5), 2), "P25": round(I.pct(base, .25), 2), "P75": round(I.pct(base, .75), 2),
            "N": len(base), "Rank": top, "Of": of, "Interp": bool(interp)}


def equivalent_inflow(fill, gen_total_daily, pump_back, factors, caps, dams, first, last, cur_year):
    """Εβδομαδιαία ισοδύναμη εισροή (GWh/ημέρα) = [ΔΑπόθεμα + Σ(παραγωγή − επιστροφή άντλησης)] / 7, με τον κώδικα κενών της εισροής ποταμών."""
    stock, d = {}, first
    while d <= last:
        v, ok = 0.0, True
        for k in dams:
            x = fill[k].get(d)
            if x is None or (caps[k] >= 100 and x == 0.0):
                ok = False
                break
            v += factors[k] * x / 100.0 * caps[k]
        if ok:
            stock[d] = v / 1000.0
        d += timedelta(days=1)
    net = {}
    for d, g in gen_total_daily.items():
        pb = pump_back.get(d)
        if g is not None and pb is not None:
            net[d] = g - pb
    S = {"dams": ["STOCK"], "caps": {"STOCK": 100.0}, "unit": "NET", "k": 1.0}      # «στάθμη%» = GWh, k = 1: ίδια μηχανή με την εισροή ποταμών
    weekly = I.weekly_inflow(S, {"STOCK": stock}, {"NET": net}, first, last)
    wk_day = {m: (v / 7.0, f) for m, (v, f) in weekly.items()}
    return wk_day, stock


def main():
    meta = sload(os.path.join(DATA, "reservoirs.json"))
    ef = sload(os.path.join(DATA, "energy_factors.json"))
    if not meta or not ef:
        log("Λείπει το data/reservoirs.json ή το data/energy_factors.json")
        return 1
    factors = {k: float(v["EnergyMWhPerHm3"]) for k, v in (ef.get("Factors") or {}).items()}
    caps = {k: float(v["CapacityHm3"]) for k, v in meta["Reservoirs"].items()}
    dams = [k for k in meta["Reservoirs"] if k != "P_AOOU" and k in factors]
    stock_units = [u for k in dams for u in meta["Reservoirs"][k]["Units"]]
    rivers = {r["Id"]: r for r in meta["Rivers"] if r.get("Order")}
    river_units = {rid: [u for k in r["Order"] if k in meta["Reservoirs"] for u in meta["Reservoirs"][k]["Units"]] for rid, r in rivers.items()}
    all_units = sorted(set(stock_units) | {u for l in river_units.values() for u in l})
    fill, gen, pump_scada, last = load_daily(DATA, dams, stock_units, all_units)
    firsts = [d for k in dams for d in fill[k]] + [d for u in all_units for d in gen[u]]
    if last is None or not firsts:
        log("Δεν βρέθηκαν δεδομένα")
        return 1
    first = min(firsts)
    cur_year = (last - timedelta(days=7)).isocalendar()[0]
    total_daily = daily_sum(gen, stock_units, first, last)
    total_w = weekly_sum(total_daily, first, last)
    total = gen_block(total_w, last, cur_year)
    ytd = year_to_date(total_daily, first, last, range(I.EXT[0], cur_year + 1), cur_year)
    ytd_doc = None
    if cur_year in ytd:
        base = [ytd[y]["GWh"] for y in range(I.BASE[0], I.BASE[1] + 1) if y in ytd]
        c = ytd[cur_year]["GWh"]
        if len(base) >= MIN_N_YTD:
            top, _b, of = I.rank_among(base, c)
            med = I.pct(base, .5)
            ytd_doc = {"Through": last.isoformat()[5:], "Years": {str(y): v for y, v in sorted(ytd.items())}, "CurrentGWh": c, "N": len(base), "Rank": top, "Of": of,
                       "Median": round(med, 1), "P25": round(I.pct(base, .25), 1), "P75": round(I.pct(base, .75), 1), "DeltaMedian": round(c - med, 1),
                       "DeltaMedianPct": round((c / med - 1) * 100, 1) if med else None}
    total["YearToDate"] = ytd_doc
    res_rivers = {}
    for rid, units in river_units.items():
        dly = daily_sum(gen, units, first, last)
        res_rivers[rid] = dict(gen_block(weekly_sum(dly, first, last), last, cur_year, with_last4=True), Units=units, Name=rivers[rid].get("Name"))
    pb = pump_back_series(DATA, pump_scada, first, last)
    eq_w, _st = equivalent_inflow(fill, total_daily, pb, factors, caps, dams, first, last, cur_year)
    eq_bands = I.band_table(eq_w, I.BASE[0], I.BASE[1], cur_year, slim=True)
    gen_med = {b["Wk"]: b["Median"] for b in I.band_table({m: (v / 7.0, f) for m, (v, f) in total_w.items()}, I.BASE[0], I.BASE[1], cur_year, slim=True)}
    for b in eq_bands:
        b["GenMedian"] = gen_med.get(b["Wk"])
    eq_cur = []
    for m in sorted(eq_w):
        iy, wk, _ = m.isocalendar()
        if iy != cur_year:
            continue
        row = {"Start": m.isoformat(), "Wk": wk, "GWhPerDay": round(eq_w[m][0], 2), "Interp": bool(eq_w[m][1])}
        if m in total_w:
            row["GenGWhPerDay"] = round(total_w[m][0] / 7.0, 2)
        eq_cur.append(row)
    log(f"παραγωγή: {len(total['Weeks'])} εβδομάδες ζώνης, {len(total['Current'])} τρέχουσες" + (f" | έτος-μέχρι-σήμερα {ytd_doc['CurrentGWh']:.0f} GWh (θέση {ytd_doc['Rank']}/{ytd_doc['Of']})" if ytd_doc else ""))
    for rid, r in res_rivers.items():
        l4 = r["Last4"]
        log(f"  {rid}: " + (f"4 εβδομάδες {l4['GWh']} GWh έναντι διαμέσου {l4['Median']} (θέση {l4['Rank']}/{l4['Of']})" if l4 else "χωρίς 4 εβδομάδες"))
    log(f"ισοδύναμη εισροή: {len(eq_bands)} εβδομάδες ζώνης, {len(eq_cur)} τρέχουσες" + (f" | τελευταία {eq_cur[-1]['GWhPerDay']} GWh/ημέρα" if eq_cur else ""))
    doc = {"Schema": 1, "Generated": datetime.now(ATHENS).strftime("%Y-%m-%dT%H:%M:%S%z"), "CurrentYear": cur_year, "LastDate": last.isoformat(),
           "Baseline": {"Years": list(I.BASE), "Extended": list(I.EXT)}, "Rule": {"MaxGapDays": I.MAXGAP, "Weeks": I.REGIME_WEEKS, "MinYears": I.MIN_N_REGIME},
           "Units": {"Stock": stock_units, "Note": "Παραγωγή ΑΚΑΘΑΡΙΣΤΗ (η άντληση δεν αφαιρείται). Σύνολο = μονάδες των 14 ταμιευτήρων χωρίς Πηγές Αώου· ανά ποταμό = όλες οι μονάδες της σειράς του."},
           "Generation": {"Total": total, "Rivers": res_rivers},
           "EquivalentInflow": {"Weeks": eq_bands, "Current": eq_cur,
                                "Note": "GWh/ημέρα = παραγωγή + μεταβολή αποθέματος − επιστροφή άντλησης. Κάτω όριο της φυσικής εισροής (οι μη μετρημένες απολήψεις είναι μέσα). Πριν το 2026 η επιστροφή άντλησης είναι υπόθεση 70 % της άντλησης SCADA."}}
    os.makedirs(DATA, exist_ok=True)
    jsonio.write_json_if_changed(OUT, doc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
