#!/usr/bin/env python3
"""
Διαγνωστικό ΜΟΝΟ ΑΝΑΓΝΩΣΗΣ για το RESMV τις ημέρες αλλαγής ώρας (K26). Δεν γράφει τίποτα.

Γνωστό (4/11/2026): το αρχείο της 25/10/2026 ΥΠΑΡΧΕΙ στον ΑΔΜΗΕ (https://www.admie.gr/sites/default/files/attached-files/type-file/2026/10/20261026_RESMV_01.xls,
ΗΜΕΡΑ = 20261025, 24 γραμμές ΩΡΑ 1–24 με την ώρα 4 = ΑΘΡΟΙΣΜΑ των δύο ωρών 03:00–04:00), αλλά η λίστα του API δεν το επιστρέφει.
Για κάθε ημερομηνία το script δείχνει:
  1. τη λίστα του API όπως τη βλέπει το pipeline (getOperationMarketFile, μία ημέρα)·
  2. τη λίστα του API με εύρος μίας ημέρας και με ΕΥΡΥ εύρος (D−3 … D+3) — με ΟΛΑ τα πεδία κάθε εγγραφής και ΑΝ περιέχει το αναμενόμενο όνομα·
  3. άμεση λήψη με βάση το όνομα (ημερομηνία δημοσίευσης D+1, φάκελοι έτους/μήνα δημοσίευσης και δύο μήνες μετά, .xls και .xlsx)·
  4. για ΚΑΘΕ αρχείο που βρέθηκε: ποιες ΗΜΕΡΑ περιέχει (και πόσες γραμμές η καθεμία), ποιες ΩΡΑ έχει η ημέρα, ποια γραμμή μοιάζει με ΑΘΡΟΙΣΜΑ δύο ωρών, και την ενέργεια ΜΥΗΣ.
Κωδικός εξόδου πάντα 0, εκτός από μη έγκυρη ημερομηνία.
Χρήση:  python scripts/diagnose_admie_resmv.py [ΗΜΕΡΟΜΗΝΙΑ ...]
"""
import io
import os
import sys
import time
import warnings
from datetime import date, timedelta

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import clock_change as C                # noqa: E402
import diagnose_admie_history as H      # noqa: E402
import update_hydro as U                # noqa: E402

URL_RANGE = H.ENDPOINTS[1][1]
EXTS = ("xls", "xlsx")
DEFAULT_DATES = ["2024-03-31", "2024-10-27", "2025-03-30", "2025-10-26", "2026-03-29", "2026-10-25"]


def log(m=""):
    print(m, flush=True)


def expected_name(d):
    """Το αρχείο της ημέρας D λέγεται με την ημερομηνία δημοσίευσης D+1."""
    return f"{(d + timedelta(days=1)):%Y%m%d}_RESMV_01"


def fmt_entry(e):
    return (f"{os.path.basename(str(e.get('file_path')))} [{e.get('file_fromdate')}→{e.get('file_todate')}, δημοσιεύθηκε {str(e.get('file_published'))[:16]}]"
            f"  διαδρομή: {e.get('file_path')}")


def candidate_urls(d, extra_months=2):
    pub = d + timedelta(days=1)
    out = []
    for k in range(extra_months + 1):
        idx = pub.year * 12 + (pub.month - 1) + k
        y, m = idx // 12, idx % 12 + 1
        for ext in EXTS:
            out.append(f"{U.BASE_URL}/sites/default/files/attached-files/type-file/{y}/{m:02d}/{expected_name(d)}.{ext}")
    return out


def looks_like_excel(b):
    return bool(b) and len(b) > 1000 and (b[:4] == bytes([0xD0, 0xCF, 0x11, 0xE0]) or b[:2] == b"PK")


def try_direct(d):
    results = []
    for url in candidate_urls(d):
        r = U.http_get(url, what="ADMIE RESMV άμεση λήψη", tries=1)
        code = None if r is None else r.status_code
        if code == 200 and looks_like_excel(r.content):
            results.append((url, 200))
            return url, r.content, results
        results.append((url, "200 (ΔΕΝ είναι Excel: πιθανή σελίδα σφάλματος)" if code == 200 else code))
    return None, None, results


def download_entry(e):
    r = U.http_get(U.urljoin(U.BASE_URL + "/", e["file_path"]), what="ADMIE RESMV αρχείο")
    return r.content if r is not None and r.status_code == 200 and looks_like_excel(r.content) else None


def analyse(content, d, exp, label):
    try:
        df = pd.read_excel(io.BytesIO(content))
    except Exception as e:                                          # noqa: BLE001
        log(f"      [{label}] δεν διαβάζεται ({type(e).__name__}: {e})")
        return
    hcol = [c for c in df.columns if "ΗΜΕΡΑ" == U.norm(c)]
    wcol = [c for c in df.columns if "ΩΡΑ" == U.norm(c)]
    mcol = [c for c in df.columns if "ΜΥΗΣ ΕΝΕΡΓΕΙΑ" in U.norm(c)]
    if not (hcol and wcol and mcol):
        log(f"      [{label}] άγνωστη δομή: στήλες {list(df.columns)[:10]}")
        return
    hours = pd.to_numeric(df[wcol[0]], errors="coerce")
    rows = df[hours.notna()].copy()
    rows["_h"] = pd.to_numeric(rows[wcol[0]], errors="coerce").astype(int)
    rows["_d"] = rows[hcol[0]].astype(str).str.replace(r"\.0$", "", regex=True)
    counts = rows["_d"].value_counts().sort_index()
    log(f"      [{label}] ΗΜΕΡΑ στο αρχείο: " + ", ".join(f"{k}: {v} γραμμές" for k, v in counts.items()))
    sel = rows[rows["_d"] == d.strftime("%Y%m%d")]
    if sel.empty:
        log(f"      [{label}] ΚΑΜΙΑ γραμμή για {d} (η ημέρα που ψάχνουμε δεν υπάρχει στο αρχείο)")
        return
    h = [int(x) for x in sel["_h"]]
    absent = sorted(set(range(1, 25)) - set(h))
    log(f"      [{label}] γραμμές της {d}: {len(sel)} (η ημέρα έχει {exp} ώρες) | ΩΡΑ: {h[0]}…{h[-1]}" + (f" | ΛΕΙΠΟΥΝ οι ΩΡΑ {absent}" if absent else "") + (" | ΕΠΑΝΑΛΑΜΒΑΝΟΝΤΑΙ ΩΡΑ" if len(set(h)) != len(h) else ""))
    v = pd.to_numeric(sel[mcol[0]], errors="coerce").to_numpy(dtype=float)
    flagged = []
    for i in range(len(v)):
        nb = [v[j] for j in (i - 1, i + 1) if 0 <= j < len(v) and v[j] == v[j]]
        if nb and v[i] == v[i] and np.median(nb) > 0 and v[i] / np.median(nb) > 1.7:
            flagged.append((h[i], v[i] / np.median(nb)))
    log(f"      [{label}] γραμμές που μοιάζουν με ΑΘΡΟΙΣΜΑ δύο ωρών (πάνω από 1,7× των γειτονικών): " + (", ".join(f"ΩΡΑ {a} (×{b:.2f})" for a, b in flagged) if flagged else "καμία"))
    log(f"      [{label}] ΜΥΗΣ: άθροισμα {np.nansum(v) / 1000:.1f} MWh | τιμές ανά γραμμή (kWh): {' '.join('·' if x != x else f'{x:.0f}' for x in v)}")


def process(d):
    exp = C.hours_in_day(d)
    name = expected_name(d)
    log(f"\n  --- {d} ({d.strftime('%a')}): {exp} ώρες {'← ΑΛΛΑΓΗ ΩΡΑΣ' if exp != 24 else '(κανονική)'} | αναμενόμενο όνομα αρχείου: {name}.xls[x] ---")
    single, why1 = H.list_files(U.API_FILES, U.CAT_RESMV, d, d)
    log("      1) API όπως το χρησιμοποιεί το pipeline (getOperationMarketFile, μία ημέρα): " + (f"δεν ήρθε ({why1})" if single is None else f"{len(single)} εγγραφές"))
    for e in single or []:
        log("         · " + fmt_entry(e))
    narrow, why2 = H.list_files(URL_RANGE, U.CAT_RESMV, d, d)
    log("      2) API με εύρος μίας ημέρας (getOperationMarketFilewRange): " + (f"δεν ήρθε ({why2})" if narrow is None else f"{len(narrow)} εγγραφές"))
    for e in narrow or []:
        log("         · " + fmt_entry(e))
    wide, why3 = H.list_files(URL_RANGE, U.CAT_RESMV, d - timedelta(days=3), d + timedelta(days=3))
    in_wide = [e for e in (wide or []) if os.path.basename(str(e.get("file_path"))).startswith(name)]
    log(f"      3) API με ΕΥΡΥ εύρος ({d - timedelta(days=3)} … {d + timedelta(days=3)}): " + (f"δεν ήρθε ({why3})" if wide is None else f"{len(wide)} εγγραφές") + f" | περιέχει το αναμενόμενο όνομα: {'ΝΑΙ' if in_wide else 'ΟΧΙ'}")
    for e in wide or []:
        log("         · " + fmt_entry(e) + ("   <-- ΑΝΑΜΕΝΟΜΕΝΟ" if e in in_wide else ""))
    sources = []
    for label, ents in (("API μίας ημέρας", single), ("API εύρους", narrow), ("API ευρέως εύρους", in_wide)):
        if ents:
            c = download_entry(ents[0])
            log(f"      λήψη από {label}: " + ("ΕΠΙΤΥΧΗΣ" if c else "ΑΠΕΤΥΧΕ"))
            if c:
                sources.append((label, c))
                break
    url, content, tried = try_direct(d)
    log("      4) ΆΜΕΣΗ λήψη με βάση το όνομα: " + ("ΒΡΕΘΗΚΕ στη διεύθυνση " + url if url else "ΔΕΝ βρέθηκε σε καμία από τις δοκιμασμένες διευθύνσεις"))
    log("         δοκιμές: " + " | ".join(f"{u.split('type-file/')[1]} → {c}" for u, c in tried))
    if content:
        sources.append(("άμεση λήψη", content))
    if not sources:
        log("      ΣΥΜΠΕΡΑΣΜΑ: το αρχείο ΔΕΝ βρέθηκε με κανέναν τρόπο")
        return
    for label, c in sources:
        analyse(c, d, exp, label)
    how = [lab for lab, _ in sources]
    log(f"      ΣΥΜΠΕΡΑΣΜΑ: το αρχείο βρέθηκε μέσω: {', '.join(how)}; το pipeline (1) " + ("το βρίσκει" if single else "ΔΕΝ το βρίσκει"))


def main():
    warnings.simplefilter("ignore")
    args = [a for a in sys.argv[1:] if not a.startswith("--")] or DEFAULT_DATES
    try:
        dates = [date.fromisoformat(a) for a in args]
    except ValueError:
        log("Χρήση: python scripts/diagnose_admie_resmv.py [ΗΜΕΡΟΜΗΝΙΑ ...]")
        return 1
    log("=== RESMV τις ημέρες αλλαγής ώρας (μόνο ανάγνωση· δεν γράφεται τίποτα) ===")
    for d in dates:
        try:
            process(d)
        except Exception as e:                                      # noqa: BLE001
            log(f"      ΣΦΑΛΜΑ στην ημέρα {d}: {type(e).__name__}: {e} — συνεχίζω με την επόμενη")
        time.sleep(0.4)
    log("\n=== ΤΕΛΟΣ ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
