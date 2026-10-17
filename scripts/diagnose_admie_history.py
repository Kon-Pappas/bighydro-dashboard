#!/usr/bin/env python3
"""
Διαγνωστικό ΜΟΝΟ ΑΝΑΓΝΩΣΗΣ: υπάρχει ιστορικό του ΑΔΜΗΕ για τους ταμιευτήρες και την παραγωγή SCADA σε προηγούμενα έτη;

Δεν γράφει ΤΙΠΟΤΑ στο repo. Χρησιμοποιεί τον ίδιο κώδικα επικοινωνίας και ανάλυσης με το pipeline (update_hydro.py).

ΠΡΩΤΑ μετράει τι δέχεται το API (δεν το υποθέτει): για κάθε κατηγορία και για δύο διευθύνσεις
(getOperationMarketFile και getOperationMarketFilewRange) ζητά παράθυρα 1, 7, 31, 93, 366 ημερών που τελειώνουν σε μια πρόσφατη
ημερομηνία όπου ξέρουμε ότι υπάρχουν αρχεία, και τυπώνει πόσες ημέρες καλύφθηκαν. Έτσι φαίνεται ποια διεύθυνση και ποιο μέγεθος
παραθύρου δουλεύουν (ένα αίτημα για ολόκληρο έτος είχε επιστρέψει ΚΕΝΗ λίστα ακόμη και για το 2026, άρα δεν αρκεί).
ΜΕΤΑ σαρώνει κάθε έτος με το μεγαλύτερο παράθυρο που δούλεψε· αν δεν δουλεύει κανένα πάνω από 1 ημέρα, δειγματίζει την 15η κάθε μήνα.
Τέλος διαβάζει ένα δείγμα (15 Ιουλίου) με τους parsers του pipeline.

Κωδικός εξόδου πάντα 0 (το αποτέλεσμα είναι στο log), εκτός από λάθος ορίσματα.
Χρήση:  python scripts/diagnose_admie_history.py [ΠΡΩΤΟ_ΕΤΟΣ] [ΤΕΛΕΥΤΑΙΟ_ΕΤΟΣ]     (προεπιλογή 2016 2026)
"""
import io
import os
import sys
import time
from collections import Counter
from datetime import date, timedelta
from urllib.parse import urljoin

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import update_hydro as U           # noqa: E402

CATEGORIES = [("ReservoirFillingRate", U.CAT_RESERVOIR), ("SystemRealizationSCADA", U.CAT_SCADA)]
ENDPOINTS = [("getOperationMarketFile", U.API_FILES), ("getOperationMarketFilewRange", U.BASE_URL + "/getOperationMarketFilewRange")]
WINDOWS = [1, 7, 31, 93, 366]
GOOD = 0.8                       # ένα παράθυρο «δουλεύει» αν καλύπτει ≥ 80% των ημερών του (οι σειρές είναι ημερήσιες)


def log(m=""):
    print(m, flush=True)


def list_files(url, category, d0, d1):
    """-> (λίστα εγγραφών | None, αιτία αποτυχίας | None). Μια ΚΕΝΗ λίστα είναι έγκυρη απάντηση."""
    r = U.http_get(url, params={"dateStart": d0.isoformat(), "dateEnd": d1.isoformat(), "FileCategory": category},
                   what=f"ADMIE {category} λίστα {d0}..{d1}")
    if r is None:
        return None, "δεν απάντησε"
    if r.status_code != 200:
        return None, f"HTTP {r.status_code}"
    try:
        data = r.json()
    except ValueError:
        return None, "μη έγκυρη JSON"
    if not isinstance(data, list):
        return None, "μη αναμενόμενη δομή"
    return [x for x in data if isinstance(x, dict) and x.get("file_path")], None


def days_covered(files, d0, d1):
    cov = set()
    for x in files:
        f, t = U.parse_admie_date(x.get("file_fromdate")), U.parse_admie_date(x.get("file_todate"))
        if f and t and t >= f:
            for k in range(min((t - f).days + 1, 400)):
                dd = f + timedelta(days=k)
                if d0 <= dd <= d1:
                    cov.add(dd)
    return cov


def probe_windows(category, end):
    """Μετρά τι δέχεται το API. -> (γραμμές, καλύτερο (όνομα, url, παράθυρο) | None)"""
    rows, best = [], None
    for name, url in ENDPOINTS:
        for w in WINDOWS:
            d0 = end - timedelta(days=w - 1)
            t0 = time.time()
            files, why = list_files(url, category, d0, end)
            dt = time.time() - t0
            time.sleep(0.4)
            if files is None:
                rows.append((name, w, None, None, why, dt))
                continue
            cov = len(days_covered(files, d0, end))
            rows.append((name, w, len(files), cov, None, dt))
            if cov >= GOOD * w and (best is None or w > best[2]):
                best = (name, url, w)
    return rows, best


def summarize(files, d0, d1):
    seen, dur, firsts, lasts, ext = set(), Counter(), [], [], Counter()
    uniq = []
    for x in files:
        if x["file_path"] in seen:
            continue
        seen.add(x["file_path"])
        uniq.append(x)
        f, t = U.parse_admie_date(x.get("file_fromdate")), U.parse_admie_date(x.get("file_todate"))
        ext[os.path.splitext(str(x["file_path"]))[1].lower() or "?"] += 1
        if f and t and t >= f:
            dur[(t - f).days + 1] += 1
            firsts.append(f)
            lasts.append(t)
    cov = days_covered(uniq, d0, d1)
    return {"n": len(seen), "first": min(firsts) if firsts else None, "last": max(lasts) if lasts else None,
            "dur": dict(dur.most_common(3)), "cov": len(cov), "span": (d1 - d0).days + 1, "ext": dict(ext)}


def scan_year(url, category, year, today, w):
    d0, d1 = date(year, 1, 1), min(date(year, 12, 31), today)
    files, fails, a = [], 0, d0
    while a <= d1:
        b = min(a + timedelta(days=w - 1), d1)
        part, _ = list_files(url, category, a, b)
        if part is None:
            fails += 1
        else:
            files += part
        a = b + timedelta(days=1)
        time.sleep(0.3)
    r = summarize(files, d0, d1)
    r["fails"] = fails
    return r


def sample_year(url, category, year, today):
    """Δειγματοληψία: η 15η κάθε μήνα (όταν κανένα παράθυρο > 1 ημέρας δεν δουλεύει)."""
    found, probed, files = 0, 0, []
    for m in range(1, 13):
        d = date(year, m, 15)
        if d > today:
            break
        part, _ = list_files(url, category, d, d)
        probed += 1
        time.sleep(0.3)
        if part:
            found += 1
            files += part
    r = summarize(files, date(year, 1, 1), min(date(year, 12, 31), today))
    r.update({"probed": probed, "found": found})
    return r


def pick_and_download(url, category, d):
    files, _ = list_files(url, category, d, d)
    if not files:
        return None
    exact, ranged, unknown = [], [], []
    for x in files:
        f, t = U.parse_admie_date(x.get("file_fromdate")), U.parse_admie_date(x.get("file_todate"))
        if f == d and t == d:
            exact.append(x)
        elif f and t and f <= d <= t:
            ranged.append(x)
        elif f is None or t is None:
            unknown.append(x)
    pick = (exact or ranged or unknown or [None])[0]
    if pick is None:
        return None
    r = U.http_get(urljoin(U.BASE_URL + "/", pick["file_path"]), what=f"ADMIE {category} αρχείο")
    return r.content if r is not None and r.status_code == 200 and r.content else None


def raw_head(content, rows=10):
    try:
        import pandas as pd
        xls = pd.ExcelFile(io.BytesIO(content))
        df = xls.parse(xls.sheet_names[0], header=None)
        log(f"      φύλλα: {xls.sheet_names[:6]} | πρώτο φύλλο {df.shape[0]}×{df.shape[1]}")
        for i in range(min(rows, len(df))):
            log("      " + " | ".join(str(c)[:18] for c in list(df.iloc[i])[:8]))
    except Exception as e:                           # noqa: BLE001
        log(f"      δεν διαβάζεται ως Excel ({type(e).__name__})")


def sample_reservoir(url, d):
    content = pick_and_download(url, U.CAT_RESERVOIR, d)
    if content is None:
        log(f"      δείγμα {d}: δεν κατέβηκε αρχείο")
        return None
    try:
        res = U.parse_reservoir(content)
    except Exception as e:                           # noqa: BLE001
        log(f"      δείγμα {d}: ο parser απέτυχε ({type(e).__name__})")
        raw_head(content)
        return False
    if not res:
        log(f"      δείγμα {d}: ο parser δεν βρήκε ταμιευτήρες")
        raw_head(content)
        return False
    reservoirs, official = res
    ok = len(reservoirs) == len(U.RESERVOIRS) and official is not None
    log(f"      δείγμα {d}: {len(reservoirs)}/{len(U.RESERVOIRS)} ταμιευτήρες, επίσημο σύνολο {official}%"
        f" | Κρεμαστά {reservoirs.get('KREMASTA')}% · Πολύφυτο {reservoirs.get('POLYFYTO')}% · Ιλαρίων {reservoirs.get('ILARIONAS')}%"
        + ("" if ok else "  <-- ΕΛΛΙΠΕΣ"))
    return ok


def sample_scada(url, d):
    content = pick_and_download(url, U.CAT_SCADA, d)
    if content is None:
        log(f"      δείγμα {d}: δεν κατέβηκε αρχείο")
        return None
    try:
        out, pump, extra = U.parse_scada(content)
    except Exception as e:                           # noqa: BLE001
        log(f"      δείγμα {d}: ο parser απέτυχε ({type(e).__name__})")
        raw_head(content)
        return False
    found = [k for k, v in out.items() if v is not None]
    tot = extra.get("TotalHydro")
    gwh = None if not tot else sum(v for v in tot if v is not None) / 1000
    ok = len(found) >= 12 and tot is not None
    log(f"      δείγμα {d}: {len(found)}/{len(out)} μονάδες, TOTAL HYDRO {'—' if gwh is None else f'{gwh:.1f} GWh'}, "
        f"άντληση {'ναι' if pump else 'όχι'}" + ("" if ok else "  <-- ΕΛΛΙΠΕΣ"))
    return ok


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    try:
        y0 = int(args[0]) if args else 2016
        y1 = int(args[1]) if len(args) > 1 else 2026
    except ValueError:
        log("Χρήση: python scripts/diagnose_admie_history.py [ΠΡΩΤΟ_ΕΤΟΣ] [ΤΕΛΕΥΤΑΙΟ_ΕΤΟΣ]")
        return 1
    if not (2000 <= y0 <= y1 <= 2100):
        log(f"Μη έγκυρα έτη: {y0}–{y1}")
        return 1
    today = date.today()
    ref = today - timedelta(days=3)               # πρόσφατη ημερομηνία όπου το pipeline ξέρει ότι υπάρχουν αρχεία
    log("=== ADMIE: διαθεσιμότητα ιστορικού (μόνο ανάγνωση· δεν γράφεται τίποτα) ===")
    summary, modes = {}, {}
    for label, cat in CATEGORIES:
        log(f"\n--- {label} ---")
        log(f"1) Τι δέχεται το API; (παράθυρα που τελειώνουν στις {ref}, γνωστή ημερομηνία με αρχεία)")
        log("   διεύθυνση | παράθυρο ημερών | εγγραφές | ημέρες που καλύφθηκαν | χρόνος")
        rows, best = probe_windows(cat, ref)
        for name, w, n, cov, why, dt in rows:
            log(f"   {name} | {w:>3} | " + (f"{n:>3} | {cov:>3} / {w}" if n is not None else f"— ({why})") + f" | {dt:.1f}s")
        if best is None:
            log("   => ΚΑΝΕΝΑ παράθυρο δεν δουλεύει: δειγματοληψία (15η κάθε μήνα, ένα αίτημα την ημέρα)")
            url, w = U.API_FILES, 1
        else:
            url, w = best[1], best[2]
            log(f"   => χρήση: {best[0]} με παράθυρα {w} ημερών")
        modes[label] = (url, w, best is not None and w > 1)
        log(f"2) Έτη (μέθοδος: {'σάρωση με παράθυρα ' + str(w) + ' ημερών' if w > 1 else 'δειγματοληψία 15ης'})")
        log("έτος | αρχεία | πρώτη → τελευταία ημερομηνία | διάρκεια αρχείου (ημέρες: πλήθος) | κάλυψη ημερών | τύπος")
        for y in range(y0, y1 + 1):
            if date(y, 1, 1) > today:
                break
            r = scan_year(url, cat, y, today, w) if w > 1 else sample_year(url, cat, y, today)
            if r["n"] == 0:
                log(f"{y} | 0      | —" + (f" (δείγμα: 0/{r['probed']} μήνες)" if w <= 1 else "") + (f" [{r['fails']} αιτήματα απέτυχαν]" if r.get("fails") else ""))
                summary[(label, y)] = 0.0
                continue
            cov = (r["found"] / r["probed"]) if w <= 1 else r["cov"] / r["span"]
            extra = f"δείγμα {r['found']}/{r['probed']} μηνών" if w <= 1 else f"{r['cov']}/{r['span']} ({cov:.0%})"
            log(f"{y} | {r['n']:<6} | {r['first']} → {r['last']} | {r['dur']} | {extra} | {r['ext']}" + (f" [{r['fails']} αιτήματα απέτυχαν]" if r.get("fails") else ""))
            summary[(label, y)] = cov
        log("δείγματα (15 Ιουλίου κάθε έτους με αρχεία):")
        for y in range(y0, y1 + 1):
            if date(y, 7, 15) > today or not summary.get((label, y)):
                continue
            time.sleep(0.4)
            (sample_reservoir if cat == U.CAT_RESERVOIR else sample_scada)(url, date(y, 7, 15))
    log("\n=== ΣΥΜΠΕΡΑΣΜΑ ===")
    for label, _ in CATEGORIES:
        u, w, _x = modes[label]
        good = [y for (l, y), c in sorted(summary.items()) if l == label and c is not None and c >= 0.9]
        some = [y for (l, y), c in sorted(summary.items()) if l == label and c is not None and 0 < c < 0.9]
        log(f"{label}: διεύθυνση που δούλεψε: {[n for n, uu in ENDPOINTS if uu == u][0]}, παράθυρο {w} ημερών | "
            f"έτη με κάλυψη ≥ 90%: {good or 'κανένα'}" + (f" | μερική κάλυψη: {some}" if some else ""))
    both = sorted(set(y for (l, y), c in summary.items() if l == CATEGORIES[0][0] and c is not None and c >= 0.9) &
                  set(y for (l, y), c in summary.items() if l == CATEGORIES[1][0] and c is not None and c >= 0.9))
    log("Έτη όπου υπάρχουν ΚΑΙ τα δύο (ό,τι χρειάζεται για ιστορική εισροή ανά ταμιευτήρα): " + (", ".join(map(str, both)) if both else "κανένα"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
