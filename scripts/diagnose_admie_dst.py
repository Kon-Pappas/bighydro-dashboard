#!/usr/bin/env python3
"""
Διαγνωστικό ΜΟΝΟ ΑΝΑΓΝΩΣΗΣ (3ο): πώς είναι τα πραγματικά αρχεία του ΑΔΜΗΕ τις ημέρες ΑΛΛΑΓΗΣ ΩΡΑΣ (23 ή 25 ώρες),
ώστε να διορθωθούν δοκιμασμένα τα K05/K04 ΠΡΙΝ και ΜΕΤΑ την αλλαγή ώρας της 25/10/2026.
Δεν γράφει ΤΙΠΟΤΑ. Χρησιμοποιεί τη διεύθυνση getOperationMarketFilewRange και τους parsers του pipeline.

Για κάθε ημερομηνία (προεπιλογή: οι αλλαγές ώρας 2024, 2025, 2026 και μία κανονική ημέρα δίπλα σε κάθε μία ως μάρτυρας) τυπώνει:
  * πόσες ώρες ΕΧΕΙ η ημέρα (23/24/25, από τη ζώνη Europe/Athens)·
  * SCADA: πλάτος φύλλου, πόσες αριθμητικές στήλες ωρών έχει η γραμμή TOTAL HYDRO (ή ΣΥΝΟΛΟ ΥΔΡΟΗΛΕΚΤΡΙΚΩΝ) και τις τιμές της ώρα-ώρα,
    και πόση ενέργεια θα έβγαζε το pipeline σήμερα (πρώτες 24 στήλες) έναντι όλων των στηλών (άρα πόσο λάθος θα έβγαινε)·
  * ISP: το ίδιο για τα τεταρτόωρα (πρώτα 96 έναντι όλων) στη γραμμή του Κρεμαστών.
Κωδικός εξόδου πάντα 0, εκτός από μη έγκυρη ημερομηνία.
Χρήση:  python scripts/diagnose_admie_dst.py [ΗΜΕΡΟΜΗΝΙΑ ...]
"""
import os
import sys
import time
from datetime import date, datetime, time as dtime, timedelta
from zoneinfo import ZoneInfo

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import diagnose_admie_history as H      # noqa: E402
import update_hydro as U                # noqa: E402

URL = H.ENDPOINTS[1][1]
ATHENS = ZoneInfo("Europe/Athens")
DEFAULT_DATES = ["2024-03-30", "2024-03-31", "2024-10-26", "2024-10-27", "2025-03-29", "2025-03-30", "2025-10-25", "2025-10-26",
                 "2026-03-28", "2026-03-29", "2026-10-24"]


def log(m=""):
    print(m, flush=True)


def hours_in_day(d):
    a = datetime.combine(d, dtime(0, 0), tzinfo=ATHENS).astimezone(ZoneInfo("UTC"))
    b = datetime.combine(d + timedelta(days=1), dtime(0, 0), tzinfo=ATHENS).astimezone(ZoneInfo("UTC"))
    return int(round((b - a).total_seconds() / 3600))


def fmt(arr, n=40):
    s = " ".join("·" if v != v else f"{v:.0f}" for v in arr[:n])
    return s + (" …" if len(arr) > n else "")


def numeric_row(df, idx, c0):
    import pandas as pd
    arr = pd.to_numeric(pd.Series(df.iloc[idx, c0:]), errors="coerce").to_numpy(dtype=float)
    return arr


def show_scada(d, exp):
    content = H.pick_and_download(URL, U.CAT_SCADA, d)
    if content is None:
        log("      SCADA: δεν κατέβηκε αρχείο")
        return
    try:
        df, sheet = U.read_sheet(content, "System_Production")
    except Exception as e:                                      # noqa: BLE001
        log(f"      SCADA: δεν διαβάζεται ({type(e).__name__})")
        return
    labels = [U.norm(x) for x in df[U.SCADA_LABEL_COL]] if df.shape[1] > U.SCADA_LABEL_COL else []
    idx = next((labels.index(U.norm(n)) for n in ("TOTAL HYDRO", "ΣΥΝΟΛΟ ΥΔΡΟΗΛΕΚΤΡΙΚΩΝ") if U.norm(n) in labels), None)
    log(f"      SCADA: φύλλο {df.shape[0]}×{df.shape[1]} (το pipeline διαβάζει τις στήλες {U.SCADA_H0}–{U.SCADA_H1 - 1})")
    if idx is None:
        log("      SCADA: δεν βρέθηκε γραμμή συνόλου υδροηλεκτρικών")
        return
    arr = numeric_row(df, idx, U.SCADA_H0)
    ok = int(np.sum(~np.isnan(arr)))
    first24 = arr[:U.SCADA_H1 - U.SCADA_H0]
    e_all, e_24 = float(np.nansum(arr)), float(np.nansum(first24))
    log(f"      SCADA TOTAL HYDRO (MW ανά στήλη ωρών): {fmt(arr, 28)}")
    log(f"      → αριθμητικές στήλες ωρών: {ok} | η ημέρα έχει {exp} ώρες | ενέργεια όλων των στηλών {e_all:.0f} MWh, των πρώτων 24 (pipeline) {e_24:.0f} MWh"
        + (f" → το pipeline χάνει {e_all - e_24:.0f} MWh ({(e_all - e_24) / e_all * 100:.1f}%)" if e_all and abs(e_all - e_24) > 0.5 else " → ίδια"))


def show_isp(d, exp):
    content = H.pick_and_download(URL, U.CAT_ISP, d)
    if content is None:
        log("      ISP: δεν κατέβηκε αρχείο")
        return
    try:
        df, _ = U.read_sheet(content, None)
    except Exception as e:                                      # noqa: BLE001
        log(f"      ISP: δεν διαβάζεται ({type(e).__name__})")
        return
    labels = [U.norm(x) for x in df[U.ISP_LABEL_COL]] if df.shape[1] > U.ISP_LABEL_COL else []
    row = None
    for key, _s, names in U.HYDRO_UNITS:
        if key == "Kremasta":
            i, _how = U.find_row(labels, names)
            row = i
    log(f"      ISP: φύλλο {df.shape[0]}×{df.shape[1]} (το pipeline διαβάζει τις στήλες {U.ISP_Q0}–{U.ISP_Q1 - 1})")
    if row is None:
        log("      ISP: δεν βρέθηκε η γραμμή των Κρεμαστών")
        return
    arr = numeric_row(df, row, U.ISP_Q0)
    ok = int(np.sum(~np.isnan(arr)))
    first = arr[:U.ISP_Q1 - U.ISP_Q0]
    e_all, e_96 = float(np.nansum(arr)) / 4, float(np.nansum(first)) / 4
    log(f"      ISP Κρεμαστά: τεταρτόωρα με τιμή: {ok} (η ημέρα έχει {exp * 4}) | ενέργεια όλων {e_all:.0f} MWh, των πρώτων 96 (pipeline) {e_96:.0f} MWh"
        + (f" → χάνονται {e_all - e_96:.0f} MWh" if abs(e_all - e_96) > 0.5 else " → ίδια"))
    log(f"      τεταρτόωρα γύρω από τις 02:00–05:00 (στήλες 9–20): {fmt(arr[8:20], 12)}")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")] or DEFAULT_DATES
    try:
        dates = [date.fromisoformat(a) for a in args]
    except ValueError:
        log("Χρήση: python scripts/diagnose_admie_dst.py [ΗΜΕΡΟΜΗΝΙΑ ...]")
        return 1
    log("=== ADMIE: ημέρες αλλαγής ώρας (μόνο ανάγνωση· δεν γράφεται τίποτα) ===")
    for d in dates:
        exp = hours_in_day(d)
        log(f"\n  --- {d} ({d.strftime('%a')}): {exp} ώρες {'← ΑΛΛΑΓΗ ΩΡΑΣ' if exp != 24 else '(κανονική)'} ---")
        show_scada(d, exp)
        time.sleep(0.4)
        show_isp(d, exp)
        time.sleep(0.4)
    log("\n=== ΤΕΛΟΣ ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
