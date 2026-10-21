#!/usr/bin/env python3
"""
Shadow run ΜΟΝΟ ΑΝΑΓΝΩΣΗΣ: εφαρμόζει τον ΝΕΟ χειρισμό αλλαγής ώρας (scripts/clock_change.py) στα ΠΡΑΓΜΑΤΙΚΑ αρχεία του ΑΔΜΗΕ και τυπώνει
ΠΑΛΙΟ (όπως τα διαβάζει σήμερα το pipeline) και ΝΕΟ δίπλα-δίπλα. Δεν γράφει τίποτα· το update_hydro.py δεν αλλάζει (D90).

Για κάθε ημερομηνία:
  * SCADA (άθροισμα των 16 μονάδων και TOTAL HYDRO): οι 24 γραμμές ωρών παλιά/νέα και ο έλεγχος ενέργειας: Σ νέων γραμμών + ενέργεια εκτός γραμμών = στήλη ΣΥΝΟΛΟΥ του αρχείου·
  * ISP (άθροισμα των 16 μονάδων): H01–H03 και H22–H24 παλιά/νέα, και έλεγχος ότι καμία ώρα δεν είναι «απίθανη» (πάνω από 3 φορές το μέγιστο των υπόλοιπων ωρών)·
  * συσχέτιση SCADA–ISP (μετά τη στοίχιση του pipeline) παλιά και νέα.
Κωδικός εξόδου πάντα 0, εκτός από μη έγκυρη ημερομηνία.
Χρήση:  python scripts/diagnose_admie_dst_fix.py [ΗΜΕΡΟΜΗΝΙΑ ...]
"""
import os
import sys
import time
import warnings
from datetime import date, timedelta

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import clock_change as C                # noqa: E402
import diagnose_admie_history as H      # noqa: E402
import update_hydro as U                # noqa: E402

URL = H.ENDPOINTS[1][1]
DEFAULT_DATES = ["2025-03-30", "2025-03-31", "2025-10-26", "2025-10-27", "2026-03-29", "2026-03-30", "2025-10-25", "2026-03-28"]


def log(m=""):
    print(m, flush=True)


def fmt(rows, idx=None):
    vals = rows if idx is None else [rows[i] for i in idx]
    return " ".join("·" if v is None or v != v else f"{v:.0f}" for v in vals)


def num_tail(df, idx, c0):
    import pandas as pd
    return pd.to_numeric(pd.Series(df.iloc[idx, c0:]), errors="coerce").to_numpy(dtype=float)


def scada_rows(content):
    """-> {κλειδί: (hourly24, total)} για TOTAL HYDRO και τις 16 μονάδες, όπως είναι στο αρχείο."""
    df, _ = U.read_sheet(content, "System_Production")
    labels = [U.norm(x) for x in df[U.SCADA_LABEL_COL]]
    out = {}
    for key, names in [("TOTAL", ("TOTAL HYDRO", "ΣΥΝΟΛΟ ΥΔΡΟΗΛΕΚΤΡΙΚΩΝ"))] + [(k, n) for k, n, _i in U.HYDRO_UNITS]:
        idx, _how = U.find_row(labels, list(names), exclude=("PUMP", "ΑΝΤΛ"))
        if idx is None:
            continue
        h = [None if x != x else float(x) for x in U.to_numeric_array(df.iloc[idx, U.SCADA_H0:U.SCADA_H1], U.SCADA_H1 - U.SCADA_H0)]
        t = num_tail(df, idx, U.SCADA_H1)
        out[key] = (h, float(t[0]) if len(t) and t[0] == t[0] else None)
    return out


def isp_rows(content):
    """-> {κλειδί μονάδας: τιμές της γραμμής από τη στήλη ISP_Q0 και μετά (διαστήματα + στήλη συνόλου)}"""
    df, _ = U.read_sheet(content, None)
    labels = [U.norm(x) for x in df[U.ISP_LABEL_COL]]
    out = {}
    for key, _s, names in U.HYDRO_UNITS:
        idx, _how = U.find_row(labels, list(names), exclude=("PUMP",))
        if idx is not None:
            out[key] = num_tail(df, idx, U.ISP_Q0)
    return out


def sum_rows(rows_list):
    arr = np.array([[np.nan if x is None else x for x in r] for r in rows_list], float)
    s = np.nansum(arr, axis=0)
    s[np.all(np.isnan(arr), axis=0)] = np.nan
    return [None if x != x else float(x) for x in s]


def corr(a, b):
    p = [(x, y) for x, y in zip(a, b) if x is not None and y is not None and x == x and y == y]
    if len(p) < 6:
        return float("nan")
    x, y = np.array([q[0] for q in p]), np.array([q[1] for q in p])
    return float(np.corrcoef(x, y)[0, 1]) if np.std(x) > 0 and np.std(y) > 0 else float("nan")


def implausible(rows):
    vals = [v for v in rows if v is not None]
    if len(vals) < 6:
        return []
    out = []
    for i, v in enumerate(rows):
        others = [x for j, x in enumerate(rows) if j != i and x is not None]
        if v is not None and others and v > 3 * max(others) and v > 50:
            out.append(i + 1)
    return out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")] or DEFAULT_DATES
    try:
        dates = [date.fromisoformat(a) for a in args]
    except ValueError:
        log("Χρήση: python scripts/diagnose_admie_dst_fix.py [ΗΜΕΡΟΜΗΝΙΑ ...]")
        return 1
    log("=== Shadow run: παλιός έναντι νέου χειρισμού αλλαγής ώρας, σε ΠΡΑΓΜΑΤΙΚΑ αρχεία (μόνο ανάγνωση· δεν γράφεται τίποτα) ===")
    for d in dates:
        n = C.hours_in_day(d)
        log(f"\n  --- {d} ({d.strftime('%a')}): {n} ώρες {'← ΑΛΛΑΓΗ ΩΡΑΣ' if n != 24 else '(κανονική)'} ---")
        sc_c = H.pick_and_download(URL, U.CAT_SCADA, d)
        time.sleep(0.4)
        old_sc_sum = new_sc_sum = None
        if sc_c is None:
            log("      SCADA: δεν κατέβηκε αρχείο")
        else:
            try:
                rows = scada_rows(sc_c)
                tot_h, tot_total = rows["TOTAL"]
                new_rows, extra = C.scada_clock(tot_h, tot_total, d)
                e_new = sum(x for x in new_rows if x is not None) + extra
                dropped = abs(tot_h[23]) if n == 23 and tot_h[23] is not None else 0.0     # η τελευταία στήλη μιας 23ωρης ημέρας ΔΕΝ είναι ώρα, αλλά μετράει στο σύνολο του αρχείου
                ok = tot_total is not None and abs(e_new - tot_total) <= 1.0 + dropped
                log(f"      SCADA TOTAL HYDRO  παλιά (24 στήλες ως H01–H24): {fmt(tot_h)}")
                log(f"      SCADA TOTAL HYDRO  νέα   (ώρες ρολογιού):         {fmt(new_rows)}   | ενέργεια εκτός γραμμών: {extra:.0f} MWh")
                note = (f" (η τελευταία στήλη, που δεν είναι ώρα, έχει {dropped:.0f} MW και μετράει στο σύνολο του αρχείου)" if n == 23 and dropped else "")
                circ = " — ΚΥΚΛΙΚΟΣ έλεγχος: η 25η ώρα προκύπτει από το σύνολο" if n == 25 else ""
                log(f"      ενέργεια ημέρας: αρχείο {tot_total} MWh | παλιά Σ24 {sum(x for x in tot_h if x is not None):.0f} | νέα Σ+εκτός {e_new:.0f} → " + ("ΟΚ (ισούται με το σύνολο του αρχείου)" if ok else "<-- ΔΕΝ ΤΑΙΡΙΑΖΕΙ") + note + circ)
                if n == 25 and new_rows[23] is not None and new_rows[22]:
                    log(f"      ανεξάρτητη ένδειξη για την 25η ώρα: {new_rows[23]:.0f} MW μετά από {new_rows[22]:.0f} MW (×{new_rows[23] / new_rows[22]:.2f}) — αν ήταν η επαναλαμβανόμενη 03:00 θα ήταν νυχτερινή τιμή (λίγα MW)")
                units = [k for k in rows if k != "TOTAL"]
                old_sc_sum = sum_rows([rows[k][0] for k in units])
                new_sc_sum = sum_rows([C.scada_clock(rows[k][0], rows[k][1], d)[0] for k in units])
                tot_units_file = sum(rows[k][1] or 0 for k in units)
                e_units_new = sum(x for x in new_sc_sum if x is not None) + sum(C.scada_clock(rows[k][0], rows[k][1], d)[1] for k in units)
                dropped_u = sum(abs(rows[k][0][23]) for k in units if n == 23 and rows[k][0][23] is not None)
                log(f"      άθροισμα {len(units)} μονάδων: σύνολα αρχείου {tot_units_file:.0f} MWh | νέα Σ+εκτός {e_units_new:.0f} → " + ("ΟΚ" if abs(tot_units_file - e_units_new) <= 1.0 * max(1, len(units)) + dropped_u else "<-- ΔΕΝ ΤΑΙΡΙΑΖΕΙ"))
            except Exception as e:                                  # noqa: BLE001
                log(f"      SCADA: σφάλμα ({type(e).__name__}: {e})")
        if d < date(2025, 10, 1):
            log("      ISP: μορφή 30 λεπτών (πριν την 1/10/2025) — η σύγκριση παραλείπεται (το pipeline δεν βλέπει τέτοια αρχεία)")
            continue
        isp_cur = H.pick_and_download(URL, U.CAT_ISP, d)
        time.sleep(0.4)
        isp_prev = H.pick_and_download(URL, U.CAT_ISP, d - timedelta(days=1))
        time.sleep(0.4)
        if isp_cur is None:
            log("      ISP: δεν κατέβηκε αρχείο")
            continue
        try:
            cur = isp_rows(isp_cur)
            prev = isp_rows(isp_prev) if isp_prev is not None else {}
            keys = list(cur)
            # ΠΑΛΙΟ: όπως το pipeline — 96 στήλες, ωριαίος μέσος, H01 = prev[23]
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", category=RuntimeWarning)
                old_cur = {k: [float(x) if x == x else None for x in np.nanmean(np.array(U.to_numeric_array(cur[k], 96), float).reshape(24, 4), axis=1)] for k in keys}
                old_prev = {k: [float(x) if x == x else None for x in np.nanmean(np.array(U.to_numeric_array(prev[k], 96), float).reshape(24, 4), axis=1)] for k in prev}
            old_rows = sum_rows([[None if x is None else x for x in U.isp_to_local([np.nan if v is None else v for v in old_cur[k]], old_prev.get(k) and [np.nan if v is None else v for v in old_prev[k]])] for k in keys])
            new_rows = sum_rows([C.isp_clock(cur[k], prev.get(k), d)[0] for k in keys])
            log(f"      ISP άθροισμα μονάδων  παλιά H01–H03 | H22–H24: {fmt(old_rows, [0, 1, 2])} | {fmt(old_rows, [21, 22, 23])}")
            log(f"      ISP άθροισμα μονάδων  νέα   H01–H03 | H22–H24: {fmt(new_rows, [0, 1, 2])} | {fmt(new_rows, [21, 22, 23])}")
            bo, bn = implausible(old_rows), implausible(new_rows)
            log("      απίθανες ώρες ISP: παλιά " + (f"H{bo}  <-- ΣΦΑΛΜΑ (K04)" if bo else "καμία") + " | νέα " + (f"H{bn}  <-- ΑΠΙΘΑΝΗ ΤΙΜΗ ΚΑΙ ΣΤΟ ΝΕΟ" if bn else "καμία"))
            if old_sc_sum is not None and new_sc_sum is not None:
                log(f"      συσχέτιση SCADA–ISP (άθροισμα μονάδων, ώρες ρολογιού, χωρίς μετατόπιση): παλιά {corr(old_sc_sum, old_rows):.2f} | νέα {corr(new_sc_sum, new_rows):.2f}")
                if n != 24:
                    ratio = lambda a, b: [round(a[i] / b[i], 2) if a[i] is not None and b[i] else None for i in (20, 21, 22, 23)]
                    log(f"      λόγος SCADA/ISP στις ώρες H21–H24 (σταθερός λόγος = σωστή στοίχιση): νέα {ratio(new_sc_sum, new_rows)} | παλιά {ratio(old_sc_sum, old_rows)}")
        except Exception as e:                                      # noqa: BLE001
            log(f"      ISP: σφάλμα ({type(e).__name__}: {e})")
    log("\n=== ΤΕΛΟΣ ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
