#!/usr/bin/env python3
"""
Διαγνωστικό ΜΟΝΟ ΑΝΑΓΝΩΣΗΣ: υπάρχει ιστορικό του ΑΔΜΗΕ για τους ταμιευτήρες και την παραγωγή SCADA σε προηγούμενα έτη;

Δεν γράφει ΤΙΠΟΤΑ στο repo. Χρησιμοποιεί τον ίδιο κώδικα επικοινωνίας και ανάλυσης με το pipeline (update_hydro.py).
Για κάθε κατηγορία (ReservoirFillingRate, SystemRealizationSCADA) και κάθε έτος τυπώνει:
  * πόσα αρχεία υπάρχουν, από ποια ημερομηνία ως ποια, ποια διάρκεια έχει το καθένα (1 ημέρα; εβδομάδα; μήνας;),
    και πόσες ημέρες του έτους καλύπτονται·
  * ένα δείγμα (15 Ιουλίου): αν το αρχείο κατεβαίνει και αν ο parser του pipeline το διαβάζει πλήρως
    (14 ταμιευτήρες + επίσημο σύνολο· μονάδες SCADA + TOTAL HYDRO)· αν όχι, τυπώνει τις πρώτες γραμμές του φύλλου.
Κωδικός εξόδου πάντα 0 (το αποτέλεσμα είναι στο log), εκτός από λάθος ορίσματα.

Χρήση:  python scripts/diagnose_admie_history.py [ΠΡΩΤΟ_ΕΤΟΣ] [ΤΕΛΕΥΤΑΙΟ_ΕΤΟΣ]     (προεπιλογή 2016 2026)
"""
import io
import os
import sys
import time
from collections import Counter
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import update_hydro as U           # noqa: E402

CATEGORIES = [("ReservoirFillingRate", U.CAT_RESERVOIR), ("SystemRealizationSCADA", U.CAT_SCADA)]


def log(m=""):
    print(m, flush=True)


def list_files(category, d0, d1):
    """-> (λίστα εγγραφών | None, αιτία αποτυχίας | None)"""
    r = U.http_get(U.API_FILES, params={"dateStart": d0.isoformat(), "dateEnd": d1.isoformat(), "FileCategory": category},
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


def year_listing(category, year, today):
    d0, d1 = date(year, 1, 1), min(date(year, 12, 31), today)
    files, why = list_files(category, d0, d1)
    if files is None:                                   # το API μπορεί να περιορίζει το εύρος: δοκιμάζουμε ανά τρίμηνο
        files, why2 = [], []
        for q in range(4):
            a, b = date(year, 1 + 3 * q, 1), min(date(year + (q == 3), 1 + (3 * q + 3) % 12, 1) - timedelta(days=1), today)
            if a > today:
                break
            part, w = list_files(category, a, b)
            if part is None:
                why2.append(w)
            else:
                files += part
        if why2 and not files:
            return {"n": None, "why": f"{why}; ανά τρίμηνο: {why2[0]}"}
    seen, covered, dur, firsts, lasts, ext = set(), set(), Counter(), [], [], Counter()
    for x in files:
        if x["file_path"] in seen:
            continue
        seen.add(x["file_path"])
        f, t = U.parse_admie_date(x.get("file_fromdate")), U.parse_admie_date(x.get("file_todate"))
        ext[os.path.splitext(str(x["file_path"]))[1].lower() or "?"] += 1
        if f and t and t >= f:
            dur[(t - f).days + 1] += 1
            firsts.append(f)
            lasts.append(t)
            for k in range(min((t - f).days + 1, 400)):
                dd = f + timedelta(days=k)
                if d0 <= dd <= d1:
                    covered.add(dd)
    span = (d1 - d0).days + 1
    return {"n": len(seen), "first": min(firsts) if firsts else None, "last": max(lasts) if lasts else None,
            "dur": dict(dur.most_common(3)), "cov": len(covered), "span": span, "ext": dict(ext)}


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


def sample_reservoir(d):
    content = U.fetch_admie_file(U.CAT_RESERVOIR, d)
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


def sample_scada(d):
    content = U.fetch_admie_file(U.CAT_SCADA, d)
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
    log("=== ADMIE: διαθεσιμότητα ιστορικού (μόνο ανάγνωση· δεν γράφεται τίποτα) ===")
    summary = {}
    for label, cat in CATEGORIES:
        log(f"\n--- {label} ---")
        log("έτος | αρχεία | πρώτη → τελευταία ημερομηνία | διάρκεια αρχείου (ημέρες: πλήθος) | κάλυψη ημερών | τύπος")
        for y in range(y0, y1 + 1):
            if date(y, 1, 1) > today:
                break
            time.sleep(0.4)
            r = year_listing(cat, y, today)
            if r["n"] is None:
                log(f"{y} | — δεν ήρθε λίστα ({r['why']})")
                summary[(label, y)] = None
                continue
            if r["n"] == 0:
                log(f"{y} | 0      | —")
                summary[(label, y)] = 0.0
                continue
            cov = r["cov"] / r["span"]
            log(f"{y} | {r['n']:<6} | {r['first']} → {r['last']} | {r['dur']} | {r['cov']}/{r['span']} ({cov:.0%}) | {r['ext']}")
            summary[(label, y)] = cov
        log("δείγματα (15 Ιουλίου κάθε έτους με αρχεία):")
        for y in range(y0, y1 + 1):
            if date(y, 7, 15) > today or not summary.get((label, y)):
                continue
            time.sleep(0.4)
            (sample_reservoir if cat == U.CAT_RESERVOIR else sample_scada)(date(y, 7, 15))
    log("\n=== ΣΥΜΠΕΡΑΣΜΑ ===")
    for label, _ in CATEGORIES:
        good = [y for (l, y), c in sorted(summary.items()) if l == label and c is not None and c >= 0.9]
        some = [y for (l, y), c in sorted(summary.items()) if l == label and c is not None and 0 < c < 0.9]
        log(f"{label}: έτη με κάλυψη ≥ 90%: {good or 'κανένα'}" + (f" | μερική κάλυψη: {some}" if some else ""))
    both = sorted(set(y for (l, y), c in summary.items() if l == CATEGORIES[0][0] and c is not None and c >= 0.9) &
                  set(y for (l, y), c in summary.items() if l == CATEGORIES[1][0] and c is not None and c >= 0.9))
    log("Έτη όπου υπάρχουν ΚΑΙ τα δύο (ό,τι χρειάζεται για ιστορική εισροή ανά ταμιευτήρα): " + (", ".join(map(str, both)) if both else "κανένα"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
