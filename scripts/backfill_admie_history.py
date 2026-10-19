#!/usr/bin/env python3
"""
Ιστορικό ΑΔΜΗΕ (στάθμες ταμιευτήρων + παραγωγή SCADA) -> ΧΩΡΙΣΤΑ αρχεία  data/history/admie_ΕΤΟΣ.json

ΔΕΝ γράφει στο data/days/ και ΔΕΝ αλλάζει το pipeline (update_hydro.py): χρησιμοποιεί τους ΙΔΙΟΥΣ parsers του, αφού πρώτα μετονομάσει
τις ετικέτες των παλιών αρχείων (το διαγνωστικό της 18/10/2026 έδειξε ότι ΜΕΤΟΝΟΜΑΣΤΗΚΑΝ, δεν έλειπαν):
    στάθμες:  STRATOS1 -> STRATOS · POURNARI1 -> POYRNARI1 · POURNARI2 -> POYRNARI2          (ο Ιλαρίων ΔΕΝ υπάρχει στα αρχεία του 2016)
    SCADA:    ΣΥΝΟΛΟ ΥΔΡΟΗΛΕΚΤΡΙΚΩΝ -> TOTAL HYDRO · ΑΝΤΛΗΣΗ -> TOTAL PUMPING                 (πριν το 2020)
Μία αίτηση ανά έτος και κατηγορία (διεύθυνση getOperationMarketFilewRange), μετά λήψη ανά ημέρα.

ΔΙΠΛΑ ΑΡΧΕΙΑ: οι εγγραφές της ίδιας ημέρας ομαδοποιούνται κατά διαδρομή (μία εγγραφή που εμφανίζεται δύο φορές κατεβαίνει ΜΙΑ φορά)·
αν υπάρχουν περισσότερες εκδόσεις (π.χ. _01, _02), κατεβαίνουν ΟΛΕΣ, συγκρίνονται, και επιλέγεται η ΤΕΛΕΥΤΑΙΑ (μεγαλύτερη ημερομηνία
δημοσίευσης, μετά μεγαλύτερος αριθμός _NN)· κάθε διαφορά καταγράφεται στο Quality.Conflicts.

Αποθηκεύεται ΗΜΕΡΗΣΙΑ ενέργεια (MWh = άθροισμα των 24 ωριαίων MW) ανά μονάδα και στάθμη % ανά ταμιευτήρα (όπως δημοσιεύεται, όριο αναφοράς του ΑΔΜΗΕ).
Τιμή null = λείπει (ποτέ μηδέν). Τα αρχεία είναι ανακτήσιμα: μια δεύτερη εκτέλεση δεν ξανακατεβάζει ό,τι υπάρχει (εκτός από --refresh).

Χρήση:  python scripts/backfill_admie_history.py ΠΡΩΤΟ_ΕΤΟΣ [ΤΕΛΕΥΤΑΙΟ_ΕΤΟΣ] [--only=reservoir|scada] [--from=ΗΜΕΡΟΜΗΝΙΑ] [--to=ΗΜΕΡΟΜΗΝΙΑ]
                                                                           [--refresh] [--max-minutes=N]
Κωδικός εξόδου 1 μόνο για λάθος ορίσματα. Μερικό αποτέλεσμα (λήξη χρόνου, αποτυχίες λήψης) είναι κανονικό και αποθηκεύεται.
"""
import io
import json
import os
import re
import sys
import time
from collections import Counter
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import update_hydro as U           # noqa: E402

RANGE_URL = U.BASE_URL + "/getOperationMarketFilewRange"
OUTDIR = os.path.join("data", "history")
ATHENS = ZoneInfo("Europe/Athens")
RES_ALIASES = {"STRATOS1": "STRATOS", "POURNARI1": "POYRNARI1", "POURNARI2": "POYRNARI2"}
SCADA_ALIASES = [("ΣΥΝΟΛΟ ΥΔΡΟΗΛΕΚΤΡΙΚΩΝ", "TOTAL HYDRO"), ("ΑΝΤΛΗΣΗ", "TOTAL PUMPING")]
UNIT_ALL = list(U.UNIT_KEYS) + [k for k, _ in U.OTHER_HYDRO_SCADA]
SLEEP = 0.25


def log(m=""):
    print(m, flush=True)


# ---------- ΛΙΣΤΑ ΚΑΙ ΕΠΙΛΟΓΗ ΕΚΔΟΣΗΣ ----------
def list_year(category, d0, d1):
    r = U.http_get(RANGE_URL, params={"dateStart": d0.isoformat(), "dateEnd": d1.isoformat(), "FileCategory": category},
                   what=f"ADMIE {category} λίστα {d0}..{d1}")
    if r is None or r.status_code != 200:
        return None
    try:
        data = r.json()
    except ValueError:
        return None
    return [x for x in data if isinstance(x, dict) and x.get("file_path")] if isinstance(data, list) else None


def published(e):
    try:
        return datetime.strptime(str(e.get("file_published", "")).strip(), "%d.%m.%Y %H:%M")
    except ValueError:
        return datetime.min


def suffix(path):
    m = re.search(r"_(\d+)\.xlsx?$", str(path))
    return int(m.group(1)) if m else 0


def group_days(entries):
    """-> {ημέρα: [εγγραφές μοναδικές κατά διαδρομή, παλαιότερη -> νεότερη]}· μόνο ημερήσια αρχεία"""
    by, skipped = {}, 0
    for e in entries:
        f, t = U.parse_admie_date(e.get("file_fromdate")), U.parse_admie_date(e.get("file_todate"))
        if not f or f != t:
            skipped += 1
            continue
        cur = by.setdefault(f, {})
        old = cur.get(e["file_path"])
        if old is None or published(e) > published(old):
            cur[e["file_path"]] = e
    return {d: sorted(v.values(), key=lambda e: (published(e), suffix(e["file_path"]))) for d, v in by.items()}, skipped


# ---------- ΜΕΤΟΝΟΜΑΣΙΑ ΕΤΙΚΕΤΩΝ ΚΑΙ ΑΝΑΛΥΣΗ ----------
def _to_xlsx(df, sheet):
    bio = io.BytesIO()
    df.to_excel(bio, sheet_name=str(sheet)[:31], header=False, index=False, engine="openpyxl")
    return bio.getvalue()


def relabel_reservoir(content):
    xls = pd.ExcelFile(io.BytesIO(content))
    name = xls.sheet_names[0]
    df = xls.parse(name, header=None)
    changed = {}
    if df.shape[1] > 1:
        for i in range(len(df)):
            lab = U.norm(df.iat[i, 1])
            if lab in RES_ALIASES:
                df.iat[i, 1] = RES_ALIASES[lab]
                changed[lab] = RES_ALIASES[lab]
    return (_to_xlsx(df, name), changed) if changed else (content, {})


def relabel_scada(content):
    df, sheet = U.read_sheet(content, "System_Production")
    if df.shape[1] <= U.SCADA_LABEL_COL:
        return content, {}
    labels = [U.norm(x) for x in df[U.SCADA_LABEL_COL]]
    changed = {}
    for old, new in SCADA_ALIASES:
        if U.norm(new) in labels:
            continue                                     # νέα μορφή: δεν αγγίζεται
        if U.norm(old) in labels:
            df.iat[labels.index(U.norm(old)), U.SCADA_LABEL_COL] = new
            changed[old] = new
    return (_to_xlsx(df, sheet), changed) if changed else (content, {})


def day_sum(v):
    """Ημερήσια ενέργεια MWh από 24 ωριαία MW· None αν λείπει έστω μία ώρα (δεν συμπληρώνουμε)."""
    if v is None or any(x is None for x in v):
        return None
    return round(float(sum(v)), 1)


def parse_reservoir_day(content):
    c2, ch = relabel_reservoir(content)
    res = U.parse_reservoir(c2)
    if not res:
        return None, ch
    reservoirs, official = res
    return {"fill": {k: reservoirs.get(k) for k in U.RESERVOIRS}, "total": official}, ch


def parse_scada_day(content):
    c2, ch = relabel_scada(content)
    out, pump, extra = U.parse_scada(c2)
    gen = {k: day_sum(v) for k, v in out.items()}
    for k, v in (extra.get("Parts") or {}).items():
        gen[k] = day_sum(v)
    return {"gen": {k: gen.get(k) for k in UNIT_ALL}, "hydro": day_sum(extra.get("TotalHydro")), "pump": day_sum(pump)}, ch


@contextmanager
def collect_logs(counter):
    old = U.log

    def sink(msg=""):
        s = re.sub(r"\d+(?:[.,]\d+)?", "#", str(msg).strip())[:140]
        if s:
            counter[s] += 1
    U.log = sink
    try:
        yield
    finally:
        U.log = old


def download(entry, what):
    r = U.http_get(urljoin(U.BASE_URL + "/", entry["file_path"]), what=what)
    time.sleep(SLEEP)
    return r.content if r is not None and r.status_code == 200 and r.content else None


def diff_summary(a, b, keys):
    out = []
    for k in keys:
        if a.get(k) != b.get(k):
            out.append(f"{k}: {a.get(k)} → {b.get(k)}")
    return out[:6]


def process_day(kind, d, entries, warn, relab):
    """-> (αποτέλεσμα | None, κατάσταση 'ok'|'failed', σύγκρουση | None)"""
    parsed = []
    parse = parse_reservoir_day if kind == "reservoir" else parse_scada_day
    for e in entries:
        content = download(e, f"ADMIE {kind} {d}")
        if content is None:
            continue
        try:
            with collect_logs(warn):
                p, ch = parse(content)
        except Exception as ex:                          # noqa: BLE001
            warn[f"parser απέτυχε: {type(ex).__name__}"] += 1
            continue
        if p is None:
            continue
        for k in ch:
            relab[kind][k] += 1
        parsed.append((e, p))
    if not parsed:
        return None, "failed", None
    chosen_e, chosen = parsed[-1]
    conflict = None
    if len(parsed) > 1:
        flat = (lambda p: {**p["fill"], "TOTAL": p["total"]}) if kind == "reservoir" else (lambda p: {**p["gen"], "HYDRO": p["hydro"], "PUMP": p["pump"]})
        first = flat(parsed[0][1])
        diffs = []
        for e, p in parsed[1:]:
            diffs += diff_summary(first, flat(p), sorted(set(first) | set(flat(p))))
        if diffs:
            conflict = {"date": d.isoformat(), "category": kind, "files": [os.path.basename(e["file_path"]) for e, _ in parsed],
                        "chosen": os.path.basename(chosen_e["file_path"]), "diff": diffs[:6]}
    return chosen, "ok", conflict


# ---------- ΑΡΧΕΙΟ ΕΤΟΥΣ ----------
def dst_days(year):
    out = []
    for m in (3, 10):
        d = date(year, m, 31)
        while d.weekday() != 6:
            d -= timedelta(days=1)
        out.append(d.isoformat())
    return out


def load_year(path):
    if not os.path.exists(path):
        return {}, {"Failed": {}, "Conflicts": [], "Relabelled": {"reservoir": {}, "scada": {}}}
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    recs = {}
    for i, d in enumerate(doc["Dates"]):
        fill = {k: doc["Fill"][k][i] for k in doc["Fill"]}
        gen = {k: doc["Gen"][k][i] for k in doc["Gen"]}
        res = {"fill": fill, "total": doc["FillTotal"][i]} if (doc["FillTotal"][i] is not None or any(v is not None for v in fill.values())) else None
        sc = {"gen": gen, "hydro": doc["TotalHydro"][i], "pump": doc["Pump"][i]} if (doc["TotalHydro"][i] is not None or any(v is not None for v in gen.values())) else None
        recs[d] = {"res": res, "sc": sc}
    q = doc.get("Quality", {})
    return recs, {"Failed": q.get("Failed", {}), "Conflicts": q.get("Conflicts", []), "Relabelled": q.get("Relabelled", {"reservoir": {}, "scada": {}})}


def write_year(year, recs, qual, warn, today):
    dates = sorted(recs)
    col = lambda f: [f(recs[d]) for d in dates]
    fill = {k: col(lambda r, k=k: (r["res"] or {"fill": {}})["fill"].get(k) if r["res"] else None) for k in U.RESERVOIRS}
    gen = {k: col(lambda r, k=k: r["sc"]["gen"].get(k) if r["sc"] else None) for k in UNIT_ALL}
    d0, d1 = date(year, 1, 1), min(date(year, 12, 31), today)
    allday = [(d0 + timedelta(days=i)).isoformat() for i in range((d1 - d0).days + 1)]
    has_res = {d for d in dates if recs[d]["res"]}
    has_sc = {d for d in dates if recs[d]["sc"]}
    first = {k: next((d for d, v in zip(dates, fill[k]) if v is not None), None) for k in U.RESERVOIRS}
    doc = {"Schema": 1, "Year": year, "Generated": datetime.now(ATHENS).strftime("%Y-%m-%dT%H:%M:%S%z"),
           "Source": "ADMIE ReservoirFillingRate + SystemRealizationSCADA (αρχεία ημέρας)",
           "Units": "Fill: % όπως δημοσιεύεται (όριο αναφοράς ΑΔΜΗΕ)· Gen, TotalHydro, Pump: MWh την ημέρα (άθροισμα 24 ωριαίων MW)· null = λείπει",
           "Dates": dates, "FillTotal": col(lambda r: r["res"]["total"] if r["res"] else None), "Fill": fill, "Gen": gen,
           "TotalHydro": col(lambda r: r["sc"]["hydro"] if r["sc"] else None), "Pump": col(lambda r: r["sc"]["pump"] if r["sc"] else None),
           "Quality": {"NoReservoirData": [d for d in allday if d not in has_res], "NoScadaData": [d for d in allday if d not in has_sc],
                       "Failed": qual["Failed"], "Conflicts": qual["Conflicts"], "Relabelled": qual["Relabelled"],
                       "ReservoirFirstDay": first, "DstDays": dst_days(year),
                       "WarningsLastRun": dict(warn.most_common(12)),
                       "Note": "Οι ημέρες αλλαγής ώρας έχουν 23 ή 25 ώρες: το άθροισμα 24 ωριαίων τιμών δεν είναι ακριβές εκείνες τις ημέρες."}}
    os.makedirs(OUTDIR, exist_ok=True)
    path = os.path.join(OUTDIR, f"admie_{year}.json")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)
    return doc


def run_year(year, a, today, deadline):
    path = os.path.join(OUTDIR, f"admie_{year}.json")
    recs, qual = load_year(path)
    qual["Relabelled"] = {"reservoir": Counter(qual["Relabelled"].get("reservoir", {})), "scada": Counter(qual["Relabelled"].get("scada", {}))}
    warn = Counter()
    d0, d1 = date(year, 1, 1), min(date(year, 12, 31), today)
    lo, hi = max(d0, a["from"] or d0), min(d1, a["to"] or d1)
    groups, nonday = {}, 0
    for kind, cat in (("reservoir", U.CAT_RESERVOIR), ("scada", U.CAT_SCADA)):
        if a["only"] and a["only"] != kind:
            continue
        entries = list_year(cat, d0, d1)
        if entries is None:
            log(f"   {year} {kind}: δεν ήρθε λίστα· παραλείπεται")
            continue
        g, sk = group_days(entries)
        groups[kind] = g
        nonday += sk
    days = sorted({d for g in groups.values() for d in g if lo <= d <= hi})
    log(f"{year}: {len(days)} ημέρες προς έλεγχο ({lo} → {hi})" + (f" | μη ημερήσιες εγγραφές που αγνοήθηκαν: {nonday}" if nonday else ""))
    done = fetched = fails = stopped = 0
    for d in days:
        if time.time() > deadline:
            stopped = 1
            log("   ΔΙΑΚΟΠΗ: έληξε ο χρόνος· αποθηκεύεται ό,τι έγινε, η επόμενη εκτέλεση συνεχίζει")
            break
        key = d.isoformat()
        rec = recs.setdefault(key, {"res": None, "sc": None})
        for kind, slot in (("reservoir", "res"), ("scada", "sc")):
            if kind not in groups or d not in groups[kind]:
                continue
            if rec[slot] is not None and not a["refresh"]:
                continue
            got, status, conflict = process_day(kind, d, groups[kind][d], warn, qual["Relabelled"])
            fetched += 1
            if status == "failed":
                fails += 1
                qual["Failed"].setdefault(key, [])
                if kind not in qual["Failed"][key]:
                    qual["Failed"][key].append(kind)
                continue
            rec[slot] = got
            if key in qual["Failed"] and kind in qual["Failed"][key]:
                qual["Failed"][key].remove(kind)
                if not qual["Failed"][key]:
                    del qual["Failed"][key]
            if conflict:
                qual["Conflicts"] = [c for c in qual["Conflicts"] if not (c["date"] == key and c["category"] == kind)] + [conflict]
        done += 1
        if done % 60 == 0:
            write_year(year, {k: v for k, v in recs.items() if v["res"] or v["sc"]}, qual, warn, today)
    recs = {k: v for k, v in recs.items() if v["res"] or v["sc"]}
    qual["Relabelled"] = {k: dict(v) for k, v in qual["Relabelled"].items()}
    if recs:
        doc = write_year(year, recs, qual, warn, today)
        first = {k: v for k, v in doc["Quality"]["ReservoirFirstDay"].items() if v and v > doc["Dates"][0]}   # εμφανίζονται ΜΕΤΑ την πρώτη αποθηκευμένη ημέρα
        log(f"   → data/history/admie_{year}.json: {len(doc['Dates'])} ημέρες | λήψεις {fetched} | αποτυχίες {fails} | συγκρούσεις εκδόσεων {len(doc['Quality']['Conflicts'])}"
            + (f" | ταμιευτήρες που εμφανίζονται ΜΕΤΑ την πρώτη αποθηκευμένη ημέρα ({doc['Dates'][0]}): {first}" if first else "")
            + (f" | μετονομασίες: {doc['Quality']['Relabelled']}" if any(doc['Quality']['Relabelled'].values()) else ""))
        for msg, n in warn.most_common(5):
            log(f"      προειδοποίηση ×{n}: {msg}")
    else:
        log(f"   {year}: τίποτα να αποθηκευτεί")
    return stopped


def parse_args(argv):
    pos = [x for x in argv if not x.startswith("--")]
    opt = {x.split("=", 1)[0]: (x.split("=", 1)[1] if "=" in x else True) for x in argv if x.startswith("--")}
    try:
        y0 = int(pos[0])
        y1 = int(pos[1]) if len(pos) > 1 else y0
        if not (2000 <= y0 <= y1 <= 2100):
            raise ValueError
        only = opt.get("--only")
        if only not in (None, "reservoir", "scada"):
            raise ValueError
        a = {"y0": y0, "y1": y1, "only": only, "refresh": bool(opt.get("--refresh")),
             "from": date.fromisoformat(opt["--from"]) if "--from" in opt else None, "to": date.fromisoformat(opt["--to"]) if "--to" in opt else None,
             "max": float(opt.get("--max-minutes", 330))}
        return a
    except (IndexError, ValueError, TypeError):
        return None


def main():
    a = parse_args(sys.argv[1:])
    if a is None:
        log("Χρήση: python scripts/backfill_admie_history.py ΠΡΩΤΟ_ΕΤΟΣ [ΤΕΛΕΥΤΑΙΟ_ΕΤΟΣ] [--only=reservoir|scada] [--from=ΗΜΕΡΟΜΗΝΙΑ] [--to=ΗΜΕΡΟΜΗΝΙΑ] [--refresh] [--max-minutes=N]")
        return 1
    today = date.today()
    deadline = time.time() + a["max"] * 60
    log(f"=== ADMIE ιστορικό {a['y0']}–{a['y1']} → {OUTDIR}/ (δεν αγγίζει το data/days/) ===")
    for y in range(a["y0"], a["y1"] + 1):
        if date(y, 1, 1) > today:
            break
        if run_year(y, a, today, deadline):
            break
    return 0


if __name__ == "__main__":
    sys.exit(main())
