#!/usr/bin/env python3
"""
Διαγνωστικό ΜΟΝΟ ΑΝΑΓΝΩΣΗΣ (3ο): πώς είναι τα πραγματικά αρχεία του ΑΔΜΗΕ τις ημέρες ΑΛΛΑΓΗΣ ΩΡΑΣ (23 ή 25 ώρες),
ώστε να διορθωθούν δοκιμασμένα τα K05/K04 ΠΡΙΝ και ΜΕΤΑ την αλλαγή ώρας της 25/10/2026.
Δεν γράφει ΤΙΠΟΤΑ. Χρησιμοποιεί τη διεύθυνση getOperationMarketFilewRange και τους parsers του pipeline.

Για κάθε ημερομηνία (προεπιλογή: οι αλλαγές ώρας 2024, 2025, 2026 και μία κανονική ημέρα δίπλα σε κάθε μία ως μάρτυρας) τυπώνει:
  * πόσες ώρες ΕΧΕΙ η ημέρα (23/24/25, από τη ζώνη Europe/Athens)·
  * SCADA: τις 24 στήλες ωρών του TOTAL HYDRO, τη στήλη ΣΥΝΟΛΟΥ ΗΜΕΡΑΣ που ακολουθεί, και αν το σύνολο υπερβαίνει το άθροισμα των 24 ωρών
    (= ενέργεια που δεν φαίνεται στις στήλες), την κεφαλίδα του φύλλου, και τη στήλη του ελάχιστου/μέγιστου του ΣΥΝΟΛΙΚΟΥ ΦΟΡΤΙΟΥ
    (μετατόπιση κατά μία στήλη σε σχέση με τις κανονικές ημέρες = οι ώρες μετά τις 03:00 δεν αντιστοιχούν στο ρολόι)·
  * ISP: πόσα διαστήματα έχει η γραμμή των Κρεμαστών (τεταρτόωρα ή ημίωρα), αν η τελευταία στήλη είναι ΣΥΝΟΛΟ και με ποια σχέση,
    και τι διαβάζει το pipeline (πρώτες 96 στήλες): πόσα διαστήματα χάνει και αν διαβάζει τη στήλη συνόλου ως διάστημα (K04).
  ΠΡΟΣΟΧΗ: η 1η εκδοχή μετρούσε τη στήλη συνόλου ως ώρα και έβγαζε «50% απώλεια» ακόμη και σε κανονικές ημέρες· διορθώθηκε στη 2η.
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
DEFAULT_DATES = ["2024-03-30", "2024-03-31", "2024-04-01", "2024-10-26", "2024-10-27", "2024-10-28",
                 "2025-03-29", "2025-03-30", "2025-03-31", "2025-10-25", "2025-10-26", "2025-10-27",
                 "2026-03-28", "2026-03-29", "2026-03-30", "2026-10-24"]          # μάρτυρας πριν, η αλλαγή, και η ΗΜΕΡΑ ΜΕΤΑ (το K04 αφορά την 30/3/2026)


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


def row_by_label(df, labels, names):
    for n in names:
        if U.norm(n) in labels:
            return labels.index(U.norm(n))
    return None


def show_scada(d, exp):
    content = H.pick_and_download(URL, U.CAT_SCADA, d)
    if content is None:
        log("      SCADA: δεν κατέβηκε αρχείο")
        return None
    try:
        df, sheet = U.read_sheet(content, "System_Production")
    except Exception as e:                                      # noqa: BLE001
        log(f"      SCADA: δεν διαβάζεται ({type(e).__name__})")
        return None
    labels = [U.norm(x) for x in df[U.SCADA_LABEL_COL]] if df.shape[1] > U.SCADA_LABEL_COL else []
    nh = U.SCADA_H1 - U.SCADA_H0
    log(f"      SCADA: φύλλο {df.shape[0]}×{df.shape[1]}· ώρες στις στήλες {U.SCADA_H0}–{U.SCADA_H1 - 1} ({nh} στήλες)· η στήλη {U.SCADA_H1} (αν υπάρχει) θεωρείται ΣΥΝΟΛΟ ΗΜΕΡΑΣ")
    for r in range(min(4, len(df))):
        cells = [str(df.iat[r, c])[:7] for c in range(min(df.shape[1], U.SCADA_H1 + 1)) if str(df.iat[r, c]) not in ("nan", "None")]
        if len(cells) >= 3:
            log(f"      κεφαλίδα γραμμή {r}: " + " | ".join(cells[:30]))
    idx = row_by_label(df, labels, ("TOTAL HYDRO", "ΣΥΝΟΛΟ ΥΔΡΟΗΛΕΚΤΡΙΚΩΝ"))
    if idx is None:
        log("      SCADA: δεν βρέθηκε γραμμή συνόλου υδροηλεκτρικών")
    else:
        hourly = U.to_numeric_array(df.iloc[idx, U.SCADA_H0:U.SCADA_H1], nh)
        tcol = numeric_row(df, idx, U.SCADA_H1)
        total = float(tcol[0]) if len(tcol) and tcol[0] == tcol[0] else None
        s24 = float(np.nansum(hourly))
        log(f"      TOTAL HYDRO, 24 ώρες (MW): {fmt(hourly, 24)}")
        if total is None:
            rel = "δεν υπάρχει στήλη συνόλου"
        elif abs(total - s24) <= 0.5:
            rel = "το ΣΥΝΟΛΟ ημέρας = άθροισμα των 24 στηλών"
        else:
            rel = f"το ΣΥΝΟΛΟ ({total:.0f} MWh) ΥΠΕΡΒΑΙΝΕΙ το άθροισμα των 24 στηλών ({s24:.0f}) κατά {total - s24:.0f} MWh ({(total - s24) / total * 100:.1f}% της ημέρας): ενέργεια που ΔΕΝ φαίνεται στις 24 στήλες"
        last = float(hourly[-1]) if nh and hourly[-1] == hourly[-1] else float("nan")
        note = f" | η τελευταία στήλη ώρας = {last:.0f} MW (ανάμεσα σε μέγιστο {np.nanmax(hourly):.0f})" if exp != 24 else ""
        log(f"      → η ημέρα έχει {exp} ώρες | {rel}{note}")
    li = row_by_label(df, labels, ("ΣΥΝΟΛΙΚΟ ΦΟΡΤΙΟ",))
    if li is not None:
        load = U.to_numeric_array(df.iloc[li, U.SCADA_H0:U.SCADA_H1], nh)
        night = int(np.nanargmin(load[:9])) if np.any(~np.isnan(load[:9])) else None
        peak = 14 + int(np.nanargmax(load[14:])) if np.any(~np.isnan(load[14:])) else None
        log(f"      ΣΥΝΟΛΙΚΟ ΦΟΡΤΙΟ (MW): {fmt(load, 24)}")
        log(f"      → ελάχιστο φορτίου νύχτας στη στήλη {night}, απογευματινό μέγιστο στη στήλη {peak} (0 = πρώτη στήλη). Συγκρίνετε με τις κανονικές ημέρες: μετατόπιση κατά 1 σημαίνει ότι οι ώρες μετά τις 03:00 δεν αντιστοιχούν στο ρολόι")
    return content


def show_isp(d, exp):
    content = H.pick_and_download(URL, U.CAT_ISP, d)
    if content is None:
        log("      ISP: δεν κατέβηκε αρχείο")
        return None, None
    try:
        df, _ = U.read_sheet(content, None)
    except Exception as e:                                      # noqa: BLE001
        log(f"      ISP: δεν διαβάζεται ({type(e).__name__})")
        return None, None
    labels = [U.norm(x) for x in df[U.ISP_LABEL_COL]] if df.shape[1] > U.ISP_LABEL_COL else []
    row = None
    for key, _s, names in U.HYDRO_UNITS:
        if key == "Kremasta":
            row, _how = U.find_row(labels, names)
    log(f"      ISP: φύλλο {df.shape[0]}×{df.shape[1]} (το pipeline διαβάζει τις στήλες {U.ISP_Q0}–{U.ISP_Q1 - 1})")
    if row is None:
        log("      ISP: δεν βρέθηκε η γραμμή των Κρεμαστών")
        return None, None
    arr = numeric_row(df, row, U.ISP_Q0)
    pos = np.where(~np.isnan(arr))[0]
    ok = len(pos)
    if ok == 0:
        log("      ISP Κρεμαστά: καμία αριθμητική τιμή")
        return None, None
    last = float(arr[pos[-1]])
    body = arr[pos[:-1]]
    sm = float(np.nansum(body))
    rel = None
    for name, val in (("άθροισμα MW", sm), ("άθροισμα MW ÷ 4", sm / 4), ("άθροισμα MW ÷ 2", sm / 2)):
        if sm and abs(last - val) <= 0.01 * abs(val) + 0.5:
            rel = name
    has_total = rel is not None
    n_int = ok - 1 if has_total else ok
    kind = "τεταρτόωρα" if n_int in (92, 96, 100) else ("ημίωρα (μορφή 30 λεπτών, πριν την 1/10/2025)" if n_int in (46, 48, 50) else "άγνωστο")
    in_range = has_total and (ok + U.ISP_Q0 - 1) < U.ISP_Q1                 # η στήλη συνόλου μέσα στο εύρος που διαβάζει το pipeline
    log(f"      ISP Κρεμαστά: {n_int} διαστήματα ({kind}) | η ημέρα έχει {exp * 4} τεταρτόωρα ή {exp * 2} ημίωρα | τελευταία στήλη: "
        + (f"ΣΥΝΟΛΟ ({rel})" if has_total else "δεν αναγνωρίζεται ως σύνολο"))
    if n_int in (92, 96, 100):
        lost = max(0, n_int - (U.ISP_Q1 - U.ISP_Q0))
        log(f"      → το pipeline (στήλες {U.ISP_Q0}–{U.ISP_Q1 - 1}): διαβάζει {min(n_int, U.ISP_Q1 - U.ISP_Q0)} διαστήματα"
            + (f", χάνει τα τελευταία {lost}" if lost else "")
            + (" και διαβάζει τη ΣΤΗΛΗ ΣΥΝΟΛΟΥ ως διάστημα (K04)" if in_range else ""))
    log(f"      διαστήματα γύρω από τις 02:00–05:00 (στήλες 9–20): {fmt(arr[8:20], 12)}")
    return content, n_int


def hourly_sum(units):
    arrs = [np.array([np.nan if v is None else v for v in lst], float) for lst in units.values() if lst]
    return np.nansum(np.vstack(arrs), axis=0) if arrs else None


def lag_report(sc_content, isp_content):
    """Συσχέτιση ωριαίας παραγωγής (άθροισμα όλων των υδροηλεκτρικών μονάδων) SCADA έναντι ISP, ΟΠΩΣ τα διαβάζει το pipeline, για μετατοπίσεις -2..+2 ωρών."""
    old = U.log
    U.log = lambda *a, **k: None
    try:
        sc, _p, _x = U.parse_scada(sc_content)
        isp, _p2, _x2 = U.parse_isp(isp_content)
    except Exception as e:                                      # noqa: BLE001
        U.log = old
        log(f"      συσχέτιση SCADA–ISP: δεν υπολογίστηκε ({type(e).__name__})")
        return
    U.log = old
    S, I = hourly_sum(sc), hourly_sum(isp)
    if S is None or I is None:
        log("      συσχέτιση SCADA–ISP: λείπουν μονάδες")
        return
    res = {}
    for lag in range(-2, 3):
        a, b = (S[lag:], I[:24 - lag]) if lag >= 0 else (S[:24 + lag], I[-lag:])
        res[lag] = float(np.corrcoef(a, b)[0, 1]) if np.std(a) > 0 and np.std(b) > 0 else float("nan")
    best = max((l for l in res if res[l] == res[l]), key=lambda l: res[l], default=None)
    if best is None:
        log("      συσχέτιση SCADA–ISP: σταθερές τιμές, δεν υπολογίζεται")
        return
    # Το ISP δημοσιεύεται σε ώρα αγοράς (CET) και το pipeline το μετατοπίζει +1 ώρα (CLOCK_NOTE): ΑΝΑΜΕΝΕΤΑΙ καλύτερη μετατόπιση +1.
    log(f"      συσχέτιση SCADA–ISP όπως τα διαβάζει το pipeline (πριν τη μετατόπιση +1 ώρα CET→Ελλάδα): χωρίς μετατόπιση {res[0]:.2f}· καλύτερη {res[best]:.2f} όταν το ISP μετατοπίζεται κατά {best:+d} ώρες"
        + ("  (αναμενόμενο: +1)" if best == 1 else "  <-- ΑΝΩΜΑΛΙΑ: αναμενόταν +1"))
    ks = [k for k, v in isp.items() if v]
    last = [float(isp[k][23]) for k in ks if isp[k][23] is not None]
    rest = [float(x) for k in ks for x in isp[k][:23] if x is not None]
    if last and rest:
        L, M = float(np.nansum(last)), float(np.max([float(np.nansum([isp[k][h] or 0 for k in ks])) for h in range(23)]))
        log(f"      ώρα 24 του ISP (άθροισμα όλων των μονάδων) όπως τη διαβάζει το pipeline: {L:.0f} MW, ενώ το μέγιστο των ωρών 1–23 είναι {M:.0f} MW"
            + ("  <-- ΑΠΙΘΑΝΗ ΤΙΜΗ: η στήλη συνόλου διαβάστηκε ως διάστημα και θα περάσει στην H01 της επόμενης ημέρας (K04)" if L > 3 * M and L > 50 else ""))


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
        sc = show_scada(d, exp)
        time.sleep(0.4)
        isp, n_int = show_isp(d, exp)
        time.sleep(0.4)
        if sc is not None and isp is not None and n_int in (92, 96, 100):
            lag_report(sc, isp)
    log("\n=== ΤΕΛΟΣ ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
