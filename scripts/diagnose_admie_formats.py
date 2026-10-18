#!/usr/bin/env python3
"""
Διαγνωστικό ΜΟΝΟ ΑΝΑΓΝΩΣΗΣ (2ο): πώς είναι δομημένα τα ΠΑΛΙΑ αρχεία του ΑΔΜΗΕ, ώστε να γραφτούν σωστά οι parsers του ιστορικού.
Δεν γράφει ΤΙΠΟΤΑ. Χρησιμοποιεί τη διεύθυνση που δούλεψε στο 1ο diagnose (getOperationMarketFilewRange) και τους parsers του pipeline.

Τυπώνει, για κάθε ημερομηνία-δείγμα:
  * ΣΤΑΘΜΕΣ: φύλλα, μέγεθος, τις γραμμές με ετικέτα, ποιοι αναμενόμενοι ταμιευτήρες ΛΕΙΠΟΥΝ και ποιες ετικέτες δεν αντιστοιχούν
    σε κανέναν αναμενόμενο (πιθανή μετονομασία: π.χ. ο Στράτος που δεν βρέθηκε στα έτη 2018–2021).
  * SCADA: πώς ταιριάζει κάθε μία από τις 16 μονάδες (ετικέτα, ακριβές/«περιέχει») και η ημερήσια παραγωγή της, και ΟΛΕΣ οι ετικέτες που
    μοιάζουν με σύνολα/άντληση/υδροηλεκτρικά (γιατί λείπουν τα «TOTAL HYDRO»/«TOTAL PUMPING» πριν το 2020).
  * ΔΙΠΛΑ ΑΡΧΕΙΑ: ημέρες με πάνω από ένα αρχείο (2018 στις στάθμες, 2020 στο SCADA), με τα πεδία των εγγραφών, για να οριστεί κανόνας επιλογής.
Κωδικός εξόδου πάντα 0, εκτός από μη έγκυρη ημερομηνία.
Χρήση:  python scripts/diagnose_admie_formats.py [ΗΜΕΡΟΜΗΝΙΑ ...]     (προεπιλογή: 15 Ιουλίου 2016, 2018, 2020, 2022, 2026)
"""
import io
import os
import sys
import time
from collections import defaultdict
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import diagnose_admie_history as H      # noqa: E402
import update_hydro as U                # noqa: E402

URL = H.ENDPOINTS[1][1]                 # getOperationMarketFilewRange: δούλεψε στο 1ο diagnose
DEFAULT_DATES = ["2016-07-15", "2018-07-15", "2020-07-15", "2022-07-15", "2026-07-15"]
KEYWORDS = ("TOTAL", "ΣΥΝΟΛ", "PUMP", "ΑΝΤΛ", "HYDRO", "ΥΔΡΟ", "ΑΝΑΝΕΩΣΙΜ", "RES")
DUP_CHECKS = [("ReservoirFillingRate", U.CAT_RESERVOIR, 2018), ("SystemRealizationSCADA", U.CAT_SCADA, 2020)]


def log(m=""):
    print(m, flush=True)


def cell(v, n=22):
    s = "" if v is None or (isinstance(v, float) and v != v) else str(v)
    return s[:n]


def show_reservoir(d):
    log(f"\n  --- ΣΤΑΘΜΕΣ {d} ---")
    content = H.pick_and_download(URL, U.CAT_RESERVOIR, d)
    if content is None:
        log("      δεν κατέβηκε αρχείο")
        return
    try:
        import pandas as pd
        xls = pd.ExcelFile(io.BytesIO(content))
        df = xls.parse(xls.sheet_names[0], header=None)
    except Exception as e:                                    # noqa: BLE001
        log(f"      δεν διαβάζεται ως Excel ({type(e).__name__})")
        return
    log(f"      φύλλα: {xls.sheet_names[:6]} | πρώτο φύλλο {df.shape[0]}×{df.shape[1]}")
    seen, extra = set(), []
    shown = 0
    for i in range(len(df)):
        row = list(df.iloc[i])
        lab = row[1] if len(row) > 1 else None
        has_text = any(isinstance(x, str) and x.strip() for x in row[:4])
        if has_text and shown < 45:
            log("      " + f"{i:>3}: " + " | ".join(cell(x) for x in row[:5]))
            shown += 1
        if isinstance(lab, str) and lab.strip():
            nm = U.normalize_reservoir_name(lab)
            seen.add(nm)
            if nm not in U.RESERVOIRS:
                extra.append(U.norm(lab))
    missing = [n for n in U.RESERVOIRS if n not in seen]
    log(f"      ΛΕΙΠΟΥΝ από τους αναμενόμενους: {missing or 'κανένας'}")
    log(f"      ετικέτες στη στήλη 2 που ΔΕΝ αντιστοιχούν σε αναμενόμενο ταμιευτήρα: {sorted(set(extra))[:30] or 'καμία'}")


def show_scada(d):
    log(f"\n  --- SCADA {d} ---")
    content = H.pick_and_download(URL, U.CAT_SCADA, d)
    if content is None:
        log("      δεν κατέβηκε αρχείο")
        return
    try:
        df, sheet = U.read_sheet(content, "System_Production")
    except Exception as e:                                    # noqa: BLE001
        log(f"      δεν διαβάζεται ως Excel ({type(e).__name__})")
        return
    labels = [U.norm(x) for x in df[U.SCADA_LABEL_COL]] if df.shape[1] > U.SCADA_LABEL_COL else []
    nonempty = [(i, l) for i, l in enumerate(labels) if l]
    log(f"      φύλλο '{sheet}' {df.shape[0]}×{df.shape[1]} | ετικέτες: {len(nonempty)} | πρώτες: {[l for _, l in nonempty[:5]]} | τελευταίες: {[l for _, l in nonempty[-5:]]}")

    def day_gwh(idx):
        try:
            arr = U.to_numeric_array(df.iloc[idx, U.SCADA_H0:U.SCADA_H1], 24)
            return float(sum(v for v in arr if v == v)) / 1000
        except Exception:                                      # noqa: BLE001
            return None
    parts = []
    for key, names, _isp in U.HYDRO_UNITS:
        idx, how = U.find_row(labels, names, exclude=("PUMP", "ΑΝΤΛ"))
        if idx is None:
            parts.append(f"{key}→ΛΕΙΠΕΙ")
        else:
            g = day_gwh(idx)
            parts.append(f"{key}→'{labels[idx]}'[{how}] {'—' if g is None else f'{g:.2f}'}")
    log("      μονάδες: " + " · ".join(parts))
    kw = [(i, l) for i, l in nonempty if any(k in l for k in KEYWORDS)]
    log("      ετικέτες με λέξεις-κλειδιά (σύνολα / άντληση / υδροηλεκτρικά / ΑΠΕ):")
    for i, l in kw[:40]:
        g = day_gwh(i)
        log(f"        {i:>3}: {l[:60]}  →  {'—' if g is None else f'{g:.2f} GWh'}")


def show_duplicates(label, cat, year):
    log(f"\n  --- ΔΙΠΛΑ ΑΡΧΕΙΑ: {label} {year} ---")
    files, why = H.list_files(URL, cat, date(year, 1, 1), date(year, 12, 31))
    if files is None:
        log(f"      δεν ήρθε λίστα ({why})")
        return
    keys = sorted({k for x in files for k in x})
    log(f"      εγγραφές: {len(files)} | πεδία: {keys}")
    by = defaultdict(list)
    for x in files:
        by[(x.get("file_fromdate"), x.get("file_todate"))].append(x)
    dup = {k: v for k, v in by.items() if len(v) > 1}
    log(f"      ημέρες με πάνω από ένα αρχείο: {len(dup)} (από {len(by)} διαφορετικές ημερομηνίες)")
    for k, v in list(sorted(dup.items()))[:5]:
        log(f"        {k[0]}→{k[1]}: {len(v)} αρχεία")
        for x in v:
            rest = {kk: str(vv)[:30] for kk, vv in x.items() if kk not in ("file_path", "file_fromdate", "file_todate")}
            log(f"           …{str(x['file_path'])[-55:]} {rest}")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")] or DEFAULT_DATES
    try:
        dates = [date.fromisoformat(a) for a in args]
    except ValueError:
        log("Χρήση: python scripts/diagnose_admie_formats.py [ΗΜΕΡΟΜΗΝΙΑ ...]  (π.χ. 2018-07-15)")
        return 1
    log("=== ADMIE: μορφή παλιών αρχείων (μόνο ανάγνωση· δεν γράφεται τίποτα) ===")
    log("\n#### ΣΤΑΘΜΕΣ ΤΑΜΙΕΥΤΗΡΩΝ ####")
    for d in dates:
        show_reservoir(d)
        time.sleep(0.4)
    log("\n#### SCADA ####")
    for d in dates:
        show_scada(d)
        time.sleep(0.4)
    log("\n#### ΔΙΠΛΑ ΑΡΧΕΙΑ ####")
    for label, cat, y in DUP_CHECKS:
        show_duplicates(label, cat, y)
        time.sleep(0.4)
    log("\n=== ΤΕΛΟΣ ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
