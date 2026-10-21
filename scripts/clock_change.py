#!/usr/bin/env python3
"""
Χειρισμός των ημερών ΑΛΛΑΓΗΣ ΩΡΑΣ (23 ή 25 ώρες) για τα αρχεία του ΑΔΜΗΕ — καθαρές συναρτήσεις, χωρίς δίκτυο.

ΔΕΝ χρησιμοποιείται ακόμη από το update_hydro.py (απόφαση D90): δοκιμάζεται πρώτα σε πραγματικά αρχεία (shadow run) και
εγκαθίσταται μετά τις 26/10/2026. Τεκμηρίωση της δομής των αρχείων: docs/DOMAIN_NOTES.md §9.

ΠΑΡΑΤΗΡΗΣΗ (πραγματικά αρχεία 2024–2026): τα αρχεία SCADA και ISP είναι γραμμένα ΧΡΟΝΟΛΟΓΙΚΑ, όχι ανά ώρα ρολογιού:
  * ημέρα 23 ωρών: 23 πραγματικές ώρες στις πρώτες στήλες, η τελευταία στήλη ώρας είναι κενή (~0)·
  * ημέρα 25 ωρών: το SCADA έχει μόνο 24 στήλες ωρών και η 25η ώρα υπάρχει ΜΟΝΟ στη στήλη ΣΥΝΟΛΟΥ ημέρας (σύνολο − άθροισμα των 24)·
    το ISP έχει 100 τεταρτόωρα·
  * μετά τις στήλες των ωρών (SCADA) / των διαστημάτων (ISP) ακολουθεί στήλη ΣΥΝΟΛΟΥ, που ΠΟΤΕ δεν είναι ώρα.
Η ώρα ρολογιού 03:00–04:00 δεν υπάρχει στις ημέρες 23 ωρών και υπάρχει δύο φορές στις ημέρες 25 ωρών.
"""
from datetime import date, datetime, time as dtime, timedelta
from zoneinfo import ZoneInfo

import numpy as np

ATHENS = ZoneInfo("Europe/Athens")
UTC = ZoneInfo("UTC")


def hours_in_day(d):
    """23, 24 ή 25 — πόσες ώρες έχει η ημέρα d στη ζώνη Europe/Athens."""
    a = datetime.combine(d, dtime(0, 0), tzinfo=ATHENS).astimezone(UTC)
    b = datetime.combine(d + timedelta(days=1), dtime(0, 0), tzinfo=ATHENS).astimezone(UTC)
    return int(round((b - a).total_seconds() / 3600))


def _num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if f != f else f


def scada_chrono(hourly, total, d):
    """Οι ΠΡΑΓΜΑΤΙΚΕΣ ώρες της ημέρας με χρονολογική σειρά, από τις 24 στήλες ώρας και τη στήλη ΣΥΝΟΛΟΥ.
    23 ώρες: οι πρώτες 23 στήλες· 24 ώρες: όλες· 25 ώρες: οι 24 στήλες + η 25η ώρα = ΣΥΝΟΛΟ − άθροισμα των 24."""
    n = hours_in_day(d)
    h = [_num(x) for x in list(hourly)[:24]] + [None] * max(0, 24 - len(list(hourly)))
    if n == 23:
        return h[:23]
    if n == 24:
        return h
    t = _num(total)
    if t is None or any(x is None for x in h):
        return h + [None]
    extra = t - sum(h)
    return h + [extra if extra > -0.5 else None]          # αρνητικό υπόλοιπο = το σύνολο δεν ταιριάζει: δεν επινοούμε τιμή


def isp_chrono(values, d, per_hour=4):
    """Ωριαίος μέσος όρος (MW) των διαστημάτων ISP της ημέρας αγοράς d, χρονολογικά. Διαβάζει ΑΚΡΙΒΩΣ τα διαστήματα της ημέρας
    (92, 96 ή 100 τεταρτόωρα) και ΠΟΤΕ τη στήλη ΣΥΝΟΛΟΥ που ακολουθεί."""
    n = hours_in_day(d)
    q = n * per_hour
    arr = np.full(q, np.nan)
    vals = [_num(x) for x in list(values)[:q]]
    for i, v in enumerate(vals):
        if v is not None:
            arr[i] = v
    out = []
    for h in range(n):
        g = arr[h * per_hour:(h + 1) * per_hour]
        out.append(None if np.all(np.isnan(g)) else float(np.nanmean(g)))
    return out


def local_from_market(cur, prev, d):
    """Ώρες Ελλάδας της d από ώρες αγοράς (CET), χρονολογικά: η 1η ώρα είναι η ΤΕΛΕΥΤΑΙΑ ΠΡΑΓΜΑΤΙΚΗ ώρα της προηγούμενης ημέρας αγοράς
    (όχι ο δείκτης 23 — στην ημέρα 23 ωρών εκεί βρίσκεται η στήλη συνόλου), και οι υπόλοιπες n−1 είναι οι πρώτες n−1 της d."""
    n = hours_in_day(d)
    first = prev[-1] if prev else None
    return [first] + list(cur[:n - 1])


def chrono_to_clock(chrono, d):
    """Χρονολογική σειρά (23/24/25 τιμές) -> 24 ώρες ρολογιού H01..H24 + η ΕΝΕΡΓΕΙΑ που δεν χωράει στις 24 γραμμές.
      * 24 ώρες: ταυτότητα.
      * 23 ώρες: η ώρα 03:00–04:00 δεν υπάρχει (H04 = None)· οι επόμενες ώρες μετακινούνται μία θέση.
      * 25 ώρες: η ώρα 03:00–04:00 υπάρχει δύο φορές -> H04 = μέσος όρος των δύο· οι επόμενες μετακινούνται μία θέση πίσω.
    Επιστρέφει (rows[24], extra): extra = άθροισμα(χρονολογικής) − άθροισμα(rows), ώστε ημερήσια ενέργεια = Σ rows + extra."""
    n = hours_in_day(d)
    c = list(chrono)
    if len(c) < n:
        c += [None] * (n - len(c))
    c = c[:n]
    if n == 24:
        return c, 0.0
    if n == 23:
        rows = c[:3] + [None] + c[3:23]
        return rows, 0.0
    a, b = c[3], c[4]
    vs = [x for x in (a, b) if x is not None]
    mid = (sum(vs) / len(vs)) if vs else None
    rows = c[:3] + [mid] + c[5:25]
    extra = sum(x for x in c if x is not None) - sum(x for x in rows if x is not None)
    return rows, extra


def scada_clock(hourly, total, d):
    return chrono_to_clock(scada_chrono(hourly, total, d), d)


def isp_clock(cur_values, prev_values, d, prev_d=None, per_hour=4):
    """ISP -> 24 ώρες ρολογιού της d. prev_values: οι τιμές της γραμμής του ISP της ΠΡΟΗΓΟΥΜΕΝΗΣ ημέρας (ή None)."""
    cur = isp_chrono(cur_values, d, per_hour)
    prev = isp_chrono(prev_values, prev_d or (d - timedelta(days=1)), per_hour) if prev_values is not None else None
    return chrono_to_clock(local_from_market(cur, prev, d), d)
