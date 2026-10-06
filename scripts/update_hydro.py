#!/usr/bin/env python3
"""
BigHydro pipeline v3
====================

Πηγές -> πεδία:
  * Reservoir (ADMIE ReservoirFillingRate)  -> Reservoir, ReservoirTotal, ReservoirTotalRate
  * SCADA     (ADMIE SystemRealizationSCADA) -> Hourly SCADA_*  (+ SCADA_OtherHydro, SCADA_TotalHydro)
  * ISP       (ADMIE ISP2ISPResults)         -> Hourly ISP_*
  * RESMV     (ADMIE RESMV)                  -> Hourly SCADA_SmallHydro
  * MCP       (ENTSO-E day-ahead, GR)        -> Hourly MCP_GR

ΡΟΛΟΙ (επαληθευμένο με δεδομένα 15/9-6/10/2026):
  * SCADA, RESMV: ώρα Ελλάδας.   * ISP, ΤΙΜΕΣ: ώρα αγοράς (CET) = ώρα Ελλάδας - 1.
  Το pipeline αποθηκεύει ΟΛΑ σε ώρα Ελλάδας (H01 = 00:00-01:00 τοπική).
  Το ISP μετατοπίζεται +1 ώρα (H01 = τελευταία ώρα αγοράς της προηγούμενης ημέρας),
  γι' αυτό κατεβαίνει και το αρχείο ISP της D-1.  Το MCP ζητείται απευθείας με παράθυρο ώρας Ελλάδας.

ΑΠΟΘΗΚΕΥΣΗ:
  data/days/YYYY-MM-DD.json      μία εγγραφή ανά ημέρα (raw ωριαία)
  data/index.json                διαθέσιμες ημέρες + κατάσταση πηγών
  data/reservoir_history.json    ιστορικό ταμιευτήρων (αύξουσα σειρά)
  data/monthly/YYYY-MM.json      ημερήσια/μηνιαία αθροίσματα (MWh) για reports

Χρήση:
  python scripts/update_hydro.py                        # τελευταίες 4 ημέρες (σήμερα-3 .. σήμερα)
  python scripts/update_hydro.py 2026-09-16             # μία ημέρα
  python scripts/update_hydro.py 2026-09-16 2026-09-30  # backfill (προτείνεται ανά 15 ημέρες)
  python scripts/update_hydro.py --diagnose 2026-10-04  # δεν γράφει τίποτα, δείχνει τη δομή των αρχείων

Env (GitHub Actions): START_DATE, END_DATE, ENTSOE_TOKEN

Κανόνες:
  * null  = δεν υπάρχει τιμή (δεν βρέθηκε αρχείο / μονάδα / ώρα).   0 = πραγματικό μηδέν.
  * Ένα source που αποτυγχάνει ΔΕΝ σβήνει όσα υπήρχαν ήδη (merge, όχι overwrite).
  * Αν ένα υπάρχον αρχείο ημέρας δεν διαβάζεται, το script σταματά (δεν το αντικαθιστά).
  * Ημέρες αλλαγής ώρας (23/25 ώρες): κρατούνται οι πρώτες 24 ώρες (γνωστός περιορισμός).
"""

import io
import json
import os
import re
import sys
import time
import unicodedata
import warnings
import xml.etree.ElementTree as ET
from datetime import date, datetime, time as dtime, timedelta, timezone
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests

warnings.filterwarnings("ignore", message="Workbook contains no default style")

# ============================================================
# CONFIG
# ============================================================

BASE_URL = "https://www.admie.gr"
API_FILES = BASE_URL + "/getOperationMarketFile"
DATA_DIR = "data"
DAYS_DIR = os.path.join(DATA_DIR, "days")
MONTHLY_DIR = os.path.join(DATA_DIR, "monthly")
INDEX_FILE = os.path.join(DATA_DIR, "index.json")
RES_HISTORY_FILE = os.path.join(DATA_DIR, "reservoir_history.json")
SCHEMA_VERSION = 3
RECON_TOL = 3.0          # MW: ανοχή TOTAL HYDRO έναντι αθροίσματος μονάδων (το SCADA δημοσιεύει ακέραια MW)
CLOCK_NOTE = ("Hourly rows use Greek local time (Europe/Athens): H01 = 00:00-01:00 local. "
              "SCADA and RESMV are published on this clock. ISP and MCP are published on market (CET) time "
              "and are shifted +1 h by the pipeline.")
TIMEOUT = 60
LOOKBACK_DAYS = 4                      # default run: σήμερα-3 .. σήμερα
ATHENS = ZoneInfo("Europe/Athens")
BRUSSELS = ZoneInfo("Europe/Brussels")   # η ημέρα αγοράς (SDAC) ορίζεται σε CET/CEST

ENTSOE_TOKEN = os.environ.get("ENTSOE_TOKEN")
ENTSOE_URL = "https://web-api.tp.entsoe.eu/api"
ENTSOE_GR = "10YGR-HTSO-----Y"

CAT_SCADA = "SystemRealizationSCADA"
CAT_ISP = "ISP2ISPResults"
CAT_RESMV = "RESMV"
CAT_RESERVOIR = "ReservoirFillingRate"

# Θέσεις στηλών στα Excel (όπως στο παλιό script c0d3233)
SCADA_LABEL_COL, SCADA_H0, SCADA_H1 = 1, 2, 26      # 24 ωριαίες τιμές
ISP_LABEL_COL, ISP_Q0, ISP_Q1 = 0, 1, 97            # 96 τεταρτάωρα

# (json_key, SCADA ετικέτες (ελληνικά), ISP ετικέτες)
HYDRO_UNITS = [
    ("Kremasta",     ["ΚΡΕΜΑΣΤΑ"],                                  ["KREMASTA"]),
    ("Kastraki",     ["ΚΑΣΤΡΑΚΙ"],                                  ["KASTRAKI"]),
    ("Stratos1",     ["ΣΤΡΑΤΟΣ 1", "ΣΤΡΑΤΟΣ1", "ΣΤΡΑΤΟΣ"],         ["STRATOS1"]),
    ("Ilarionas",    ["ΙΛΑΡΙΩΝ", "ΙΛΑΡΙΩΝΑΣ"],                      ["ILARIONAS"]),
    ("Polyfyto",     ["ΠΟΛΥΦΥΤΟ"],                                  ["POLYFYTO"]),
    ("Sfikia",       ["ΣΦΗΚΙΑ"],                                    ["SFIKIA"]),
    ("Asomata",      ["ΑΣΩΜΑΤΑ"],                                   ["ASOMATA"]),
    ("Thesavros",    ["ΘΗΣΑΥΡΟΣ"],                                  ["THESAVROS1", "THESAVROS2", "THESAVROS3"]),
    ("Platanovrysi", ["ΠΛΑΤΑΝΟΒΡΥΣΗ"],                              ["PLATANOVRYSI"]),
    ("PAoou",        ["ΑΩΟΣ", "ΠΗΓΕΣ ΑΩΟΥ"],                        ["P_AOOU"]),
    ("Pournari1",    ["ΠΟΥΡΝΑΡΙ", "ΠΟΥΡΝΑΡΙ 1", "ΠΟΥΡΝΑΡΙ Ι"],      ["POURNARI1"]),
    ("Pournari2",    ["ΠΟΥΡΝΑΡΙ 2", "ΠΟΥΡΝΑΡΙ ΙΙ", "ΠΟΥΡΝΑΡΙ2"],    ["POURNARI2"]),
    ("Agras",        ["ΑΓΡΑΣ"],                                     ["AGRAS"]),
    ("Edessaios",    ["ΕΔΕΣΣΑΙΟΣ", "ΕΔΕΣΣΑΙΟΥ", "ΕΔΕΣΑΙΟΣ"],        ["EDESSAIOS"]),
    ("Ladonas",      ["ΛΑΔΩΝΑΣ"],                                   ["LADONAS"]),
    ("Plastiras",    ["ΠΛΑΣΤΗΡΑΣ"],                                 ["PLASTIRAS"]),
]
UNIT_KEYS = [u[0] for u in HYDRO_UNITS]

# Μικρά υδροηλεκτρικά που υπάρχουν στο SCADA (και στο TOTAL HYDRO) αλλά ΟΧΙ στο ISP.
# Αποθηκεύονται αθροιστικά ως SCADA_OtherHydro.
OTHER_HYDRO_SCADA = [
    ("Stratos2",   ["ΣΤΡΑΤΟΣ 2"]),
    ("Makrochori", ["ΜΑΚΡΟΧΩΡΙ"]),
    ("Louros",     ["ΛΟΥΡΟΣ"]),
    ("Gkiona",     ["ΓΚΙΩΝΑ"]),
]

ISP_PUMP_UNITS = ["SFIKIA_PUMP", "THESAVROS1_PUMP", "THESAVROS2_PUMP", "THESAVROS3_PUMP"]

# Ονόματα ταμιευτήρων όπως τα δημοσιεύει το ADMIE (η ορθογραφία POYRNARI είναι δική τους)
RESERVOIRS = [
    "ASOMATA", "ILARIONAS", "KASTRAKI", "KREMASTA", "LADONAS", "PLASTIRAS",
    "PLATANOVRYSI", "POLYFYTO", "POYRNARI1", "POYRNARI2", "P_AOOU", "SFIKIA",
    "STRATOS", "THESAVROS",
]

session = requests.Session()
session.headers.update({
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36"),
    "Accept": "*/*",
    "Referer": BASE_URL + "/",
})


def log(msg=""):
    print(msg, flush=True)


# ============================================================
# HELPERS
# ============================================================

def norm(v):
    """Κεφαλαία, χωρίς τόνους, μονά κενά. None/NaN -> ''."""
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return ""
    s = unicodedata.normalize("NFD", str(v))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s.upper()).strip()


def http_get(url, params=None, tries=3, what="", use_session=True):
    for attempt in range(1, tries + 1):
        try:
            getter = session.get if use_session else requests.get
            r = getter(url, params=params, timeout=TIMEOUT, allow_redirects=True)
            if r.status_code >= 500 and attempt < tries:
                log(f"   ! {what}: HTTP {r.status_code}, προσπάθεια {attempt}/{tries}")
                time.sleep(2 * attempt)
                continue
            return r
        except requests.RequestException as e:
            # ΜΗΝ τυπώνεις το exception: μπορεί να περιέχει URL με token.
            log(f"   ! {what}: {type(e).__name__}, προσπάθεια {attempt}/{tries}")
            time.sleep(2 * attempt)
    return None


def find_row(labels, aliases, exclude=(), contains=True):
    """Επιστρέφει (index, 'exact'|'contains') ή (None, None).
    Πρώτα ακριβές ταίριασμα, μετά 'περιέχει' με προτίμηση στη συντομότερη ετικέτα
    (ώστε το 'ΠΟΥΡΝΑΡΙ' να μην πιάσει το 'ΠΟΥΡΝΑΡΙ 2')."""
    al = [norm(a) for a in aliases]
    for a in al:
        for i, lab in enumerate(labels):
            if lab == a:
                return i, "exact"
    if contains:
        ex = [norm(x) for x in exclude]
        cands = [(len(lab), i) for i, lab in enumerate(labels)
                 if lab and any(a in lab for a in al) and not any(x in lab for x in ex)]
        if cands:
            return min(cands)[1], "contains"
    return None, None


def to_numeric_array(sl, size):
    arr = pd.to_numeric(pd.Series(sl), errors="coerce").to_numpy(dtype=float)
    if len(arr) < size:
        arr = np.concatenate([arr, np.full(size - len(arr), np.nan)])
    return arr[:size]


def nan_to_none_list(arr, digits=2):
    return [None if np.isnan(x) else round(float(x), digits) + 0.0 for x in arr]


def read_sheet(content, preferred):
    xls = pd.ExcelFile(io.BytesIO(content))
    names = xls.sheet_names
    if preferred is None:                      # πρώτο φύλλο, χωρίς προειδοποίηση
        return xls.parse(names[0], header=None), names[0]
    name = next((n for n in names if norm(n) == norm(preferred)), None)
    if name is None:
        log(f"   ! φύλλο '{preferred}' δεν βρέθηκε (υπάρχουν: {names}) - χρήση του πρώτου")
        name = names[0]
    return xls.parse(name, header=None), name


def log_not_found(kind, missing, labels):
    log(f"   ! {kind}: δεν βρέθηκαν: {', '.join(missing)}")
    shown = sorted({l for l in labels if l})[:60]
    log(f"     διαθέσιμες ετικέτες: {shown}")


# ============================================================
# ADMIE: εύρεση + λήψη αρχείου
# ============================================================

def parse_admie_date(s):
    try:
        return datetime.strptime(str(s).strip(), "%d.%m.%Y").date()
    except ValueError:
        return None


def fetch_admie_file(category, d):
    """Επιστρέφει bytes του αρχείου ή None."""
    ds = d.isoformat()
    r = http_get(API_FILES, params={"dateStart": ds, "dateEnd": ds, "FileCategory": category},
                 what=f"ADMIE {category}")
    if r is None or r.status_code != 200:
        log(f"   - {category}: το API δεν απάντησε σωστά")
        return None
    try:
        data = r.json()
    except ValueError:
        log(f"   - {category}: μη έγκυρη JSON απάντηση")
        return None
    if not isinstance(data, list) or not data:
        log(f"   - {category}: δεν υπάρχει αρχείο για {ds}")
        return None

    exact, ranged, unknown = [], [], []
    for x in data:
        if not isinstance(x, dict) or not x.get("file_path"):
            continue
        f, t = parse_admie_date(x.get("file_fromdate")), parse_admie_date(x.get("file_todate"))
        if f == d and t == d:
            exact.append(x)
        elif f and t and f <= d <= t:
            ranged.append(x)
        elif f is None or t is None:
            unknown.append(x)
    pick = (exact or ranged or unknown or [None])[0]
    if pick is None:
        log(f"   - {category}: υπάρχουν αρχεία αλλά κανένα δεν καλύπτει {ds}")
        return None
    if pick not in exact:
        log(f"   ! {category}: δεν βρέθηκε αρχείο με ακριβή ημερομηνία, χρήση του πιο κοντινού")

    url = urljoin(BASE_URL + "/", pick["file_path"])
    fr = http_get(url, what=f"ADMIE {category} αρχείο")
    if fr is None or fr.status_code != 200 or not fr.content:
        log(f"   - {category}: αποτυχία λήψης αρχείου")
        return None
    log(f"   + {category}: {len(fr.content):,} bytes")
    return fr.content


# ============================================================
# PARSERS
# ============================================================

def _sum_series(arrays):
    if not arrays:
        return None
    stack = np.vstack(arrays)
    tot = np.nansum(stack, axis=0)
    tot[np.isnan(stack).all(axis=0)] = np.nan
    return tot


def parse_scada(content):
    """-> ({unit_key: [24]|None}, pump[24]|None, {"OtherHydro": [24]|None, "TotalHydro": [24]|None})
    Ώρες: ώρα Ελλάδας (όπως δημοσιεύονται)."""
    df, _ = read_sheet(content, "System_Production")
    labels = [norm(x) for x in df[SCADA_LABEL_COL]] if df.shape[1] > SCADA_LABEL_COL else []
    out, missing = {}, []
    for key, scada_names, _isp in HYDRO_UNITS:
        idx, how = find_row(labels, scada_names, exclude=("PUMP", "ΑΝΤΛ"))
        if idx is None:
            out[key] = None
            missing.append(key)
            continue
        if how == "contains":
            log(f"   ~ SCADA {key}: ταίριασμα 'περιέχει' -> '{labels[idx]}'")
        out[key] = nan_to_none_list(to_numeric_array(df.iloc[idx, SCADA_H0:SCADA_H1], 24))
    if missing:
        log_not_found("SCADA", missing, labels)
    pidx, _ = find_row(labels, ["TOTAL PUMPING"])
    pump = None
    if pidx is not None:
        pump = nan_to_none_list(to_numeric_array(df.iloc[pidx, SCADA_H0:SCADA_H1], 24))
    else:
        log("   ! SCADA: δεν βρέθηκε γραμμή 'TOTAL PUMPING'")

    # άλλα υδροηλεκτρικά (δεν υπάρχουν στο ISP)
    arrs, miss_o = [], []
    for key, aliases in OTHER_HYDRO_SCADA:
        idx, _ = find_row(labels, aliases, contains=False)
        if idx is None:
            miss_o.append(key)
        else:
            arrs.append(to_numeric_array(df.iloc[idx, SCADA_H0:SCADA_H1], 24))
    if miss_o:
        log_not_found("SCADA άλλα υδροηλεκτρικά", miss_o, labels)
    other = _sum_series(arrs)

    tidx, _ = find_row(labels, ["TOTAL HYDRO"], contains=False)
    total = None
    if tidx is None:
        log("   ! SCADA: δεν βρέθηκε γραμμή 'TOTAL HYDRO'")
    else:
        total = to_numeric_array(df.iloc[tidx, SCADA_H0:SCADA_H1], 24)
        # συμφωνία: TOTAL HYDRO ~ Σ(16 μονάδες) + άλλα υδροηλεκτρικά
        worst, worst_h = 0.0, None
        for h in range(24):
            if np.isnan(total[h]):
                continue
            ssum = sum(v[h] for v in out.values() if v is not None and v[h] is not None)
            ssum += 0.0 if other is None or np.isnan(other[h]) else float(other[h])
            gap = float(total[h]) - ssum
            if abs(gap) > abs(worst):
                worst, worst_h = gap, h
        if abs(worst) > RECON_TOL:
            log(f"   ! SCADA TOTAL HYDRO ασυμφωνία: μέγιστη διαφορά {worst:+.1f} MW στην ώρα H{worst_h + 1:02d} "
                f"(πιθανή νέα/άγνωστη μονάδα στο υδροηλεκτρικό μπλοκ)")
    extra = {
        "OtherHydro": None if other is None else nan_to_none_list(other),
        "TotalHydro": None if total is None else nan_to_none_list(total),
    }
    return out, pump, extra


def _isp_rows_to_hourly(df, labels, names, exact_only=False):
    """Αθροίζει τεταρτάωρα από πολλές γραμμές και δίνει ωριαίο μέσο όρο (MW)."""
    arrays = []
    for nm in names:
        idx, _ = find_row(labels, [nm], exclude=() if exact_only else ("PUMP",),
                          contains=not exact_only)
        if idx is not None:
            arrays.append(to_numeric_array(df.iloc[idx, ISP_Q0:ISP_Q1], 96))
    if not arrays:
        return None
    stack = np.vstack(arrays)
    total = np.nansum(stack, axis=0)
    total[np.isnan(stack).all(axis=0)] = np.nan
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        hourly = np.nanmean(total.reshape(24, 4), axis=1)
    return hourly


def parse_isp(content):
    """-> ({unit_key: [24]|None}, pump[24]|None)  (MW, μέσος όρος τεταρτάωρων)"""
    df, _ = read_sheet(content, None)  # πρώτο φύλλο (όνομα YYYYMMDD_ISP)
    labels = [norm(x) for x in df[ISP_LABEL_COL]] if df.shape[1] > ISP_LABEL_COL else []
    out, missing = {}, []
    for key, _scada, isp_names in HYDRO_UNITS:
        h = _isp_rows_to_hourly(df, labels, isp_names)
        if h is None:
            out[key] = None
            missing.append(key)
        else:
            out[key] = nan_to_none_list(h)
    if missing:
        log_not_found("ISP", missing, labels)
    hp = _isp_rows_to_hourly(df, labels, ISP_PUMP_UNITS, exact_only=True)
    pump = None
    if hp is not None:
        # στο ISP οι αντλήσεις είναι αρνητικές: αντιστροφή ώστε να συμφωνούν με το SCADA
        pump = nan_to_none_list(-hp)
    else:
        log("   ! ISP: δεν βρέθηκαν γραμμές pump")
    return out, pump


def parse_resmv(content):
    """-> [24] MWh ή None"""
    df = pd.read_excel(io.BytesIO(content))
    cols = [c for c in df.columns if "ΜΥΗΣ ΕΝΕΡΓΕΙΑ" in norm(c)]
    if not cols:
        log(f"   ! RESMV: δεν βρέθηκε στήλη 'ΜΥΗΣ ΕΝΕΡΓΕΙΑ' (στήλες: {list(df.columns)[:12]})")
        return None
    vals = pd.to_numeric(df[cols[0]], errors="coerce").dropna().to_numpy(dtype=float)[:24]
    if len(vals) < 24:
        log(f"   ! RESMV: μόνο {len(vals)} τιμές (αναμένονται 24)")
    arr = np.concatenate([vals, np.full(24 - len(vals), np.nan)])
    return nan_to_none_list(arr / 1000.0)      # kWh -> MWh


def normalize_reservoir_name(v):
    t = norm(v)
    return "THESAVROS" if t.startswith("THESAVROS") else t


def parse_reservoir(content):
    """-> ({RESERVOIR: percent}, official_total_percent|None)"""
    xls = pd.ExcelFile(io.BytesIO(content))
    df = xls.parse(xls.sheet_names[0], header=None)

    reservoirs = {}
    for _, row in df.iterrows():
        if len(row) < 3:
            continue
        name = normalize_reservoir_name(row.iloc[1])
        if name not in RESERVOIRS:
            continue
        try:
            reservoirs[name] = round(float(row.iloc[2]) * 100.0, 2)
        except (TypeError, ValueError):
            continue

    official = None
    for _, row in df.iterrows():
        cells = list(row)
        for ci, val in enumerate(cells):
            if "FILLING RATE (%) TOTAL" in norm(val):
                cand = []
                if ci + 3 < len(cells):
                    cand.append(cells[ci + 3])
                cand += cells[ci + 1:]
                for c in cand:
                    try:
                        f = float(c)
                        if not np.isnan(f):
                            official = round(f * 100.0, 2)
                            break
                    except (TypeError, ValueError):
                        continue
                break
        if official is not None:
            break

    missing = [n for n in RESERVOIRS if n not in reservoirs]
    if missing:
        log(f"   ! Reservoir: λείπουν {missing}")
    if official is None:
        log("   ! Reservoir: δεν βρέθηκε το επίσημο 'Filling Rate (%) Total'")
    over = {k: v for k, v in reservoirs.items() if v > 100}
    if over:
        log(f"   ~ Reservoir: τιμές >100% (όπως δημοσιεύονται από ADMIE): {over}")
    if not reservoirs:
        return None
    return reservoirs, official


# ============================================================
# ENTSO-E MCP (day-ahead, GR) - υποστηρίζει PT60M και PT15M
# ============================================================

def entsoe_window(d, tz=BRUSSELS):
    """Ημέρα παράδοσης d = 00:00-24:00 ώρα Κεντρικής Ευρώπης (όπως ορίζεται η αγορά).
    Τα ωριαία πεδία του ADMIE (ISP/SCADA) ακολουθούν αυτή την ημέρα: H01 = πρώτη ώρα της ημέρας αγοράς.
    Επαληθεύτηκε με την άντληση (pump), που τρέχει μόνο στις ώρες με αρνητική τιμή.
    Ημέρες αλλαγής ώρας έχουν 23/25 ώρες: κρατάμε τις πρώτες 24."""
    start = datetime.combine(d, dtime(0, 0), tzinfo=tz).astimezone(timezone.utc)
    end = datetime.combine(d + timedelta(days=1), dtime(0, 0), tzinfo=tz).astimezone(timezone.utc)
    return start, end


def parse_entsoe_xml(text, start_utc):
    """-> [24] ωριαίες τιμές (€/MWh) ή None. Μέσος όρος όταν η ανάλυση είναι <60'."""
    root = ET.fromstring(text)
    ns = {"ns": root.tag.split("}")[0].strip("{")} if root.tag.startswith("{") else {}
    q = (lambda t: f"ns:{t}") if ns else (lambda t: t)

    prices = {}
    for ts in root.findall(q("TimeSeries"), ns):
        for period in ts.findall(q("Period"), ns):
            ti = period.find(q("timeInterval"), ns)
            res = period.find(q("resolution"), ns).text
            m = re.fullmatch(r"PT(\d+)M", res)
            if not m:
                log(f"   ! MCP: άγνωστη ανάλυση {res}")
                continue
            step = int(m.group(1))
            p_start = datetime.strptime(ti.find(q("start"), ns).text, "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc)
            p_end = datetime.strptime(ti.find(q("end"), ns).text, "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc)
            n = int((p_end - p_start).total_seconds() // 60 // step)
            pts = {int(p.find(q("position"), ns).text): float(p.find(q("price.amount"), ns).text)
                   for p in period.findall(q("Point"), ns)}
            last = None
            for pos in range(1, n + 1):          # forward-fill (A03 curves παραλείπουν επαναλαμβανόμενες τιμές)
                if pos in pts:
                    last = pts[pos]
                if last is not None:
                    prices[p_start + timedelta(minutes=(pos - 1) * step)] = last
    if not prices:
        return None
    hourly = []
    for h in range(24):
        a = start_utc + timedelta(hours=h)
        b = a + timedelta(hours=1)
        vals = [v for t, v in prices.items() if a <= t < b]
        hourly.append(round(sum(vals) / len(vals), 2) if vals else None)
    return hourly if any(v is not None for v in hourly) else None


def fetch_mcp(d):
    """Ωριαίο MCP σε ώρα Ελλάδας: ζητάμε παράθυρο από τα ελληνικά μεσάνυχτα, οπότε το ENTSO-E επιστρέφει
    και την προηγούμενη ημέρα αγοράς (η H01 της τοπικής ημέρας = τελευταία ώρα αγοράς της D-1)."""
    if not ENTSOE_TOKEN:
        log("   - MCP: δεν υπάρχει ENTSOE_TOKEN, παραλείπεται")
        return None
    start, end = entsoe_window(d, ATHENS)
    params = {
        "securityToken": ENTSOE_TOKEN, "documentType": "A44",
        "in_Domain": ENTSOE_GR, "out_Domain": ENTSOE_GR,
        "periodStart": start.strftime("%Y%m%d%H%M"), "periodEnd": end.strftime("%Y%m%d%H%M"),
    }
    r = http_get(ENTSOE_URL, params=params, what="ENTSO-E MCP", use_session=False)
    if r is None or r.status_code != 200:
        reason = ""
        if r is not None:
            m = re.search(r"<text>(.*?)</text>", r.text, re.S)
            reason = f" ({m.group(1).strip()[:120]})" if m else ""
        log(f"   - MCP: καμία απάντηση / HTTP {getattr(r, 'status_code', None)}{reason}")
        return None
    try:
        hourly = parse_entsoe_xml(r.text, start)
    except Exception as e:
        log(f"   ! MCP parse: {type(e).__name__}: {e}")
        return None
    if hourly is None:
        log("   - MCP: η απάντηση δεν περιείχε τιμές")
    else:
        log(f"   + MCP: {sum(v is not None for v in hourly)}/24 ώρες")
    return hourly


# ============================================================
# ΑΠΟΘΗΚΕΥΣΗ: ένα αρχείο ανά ημέρα + παράγωγα
# ============================================================

def day_path(d):
    return os.path.join(DAYS_DIR, f"{d.isoformat()}.json")


def atomic_write_json(path, obj, indent=2):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=indent)
        f.write("\n")
    os.replace(tmp, path)


def load_day(d):
    """Επιστρέφει dict ή None. Αν το αρχείο υπάρχει αλλά είναι χαλασμένο -> exception (σταματάμε)."""
    p = day_path(d)
    if not os.path.exists(p) or os.path.getsize(p) == 0:
        return None
    with open(p, "r", encoding="utf-8") as f:
        rec = json.load(f)
    if not isinstance(rec, dict):
        raise ValueError(f"{p}: αναμενόταν αντικείμενο")
    return rec


def load_all_days():
    out = []
    if os.path.isdir(DAYS_DIR):
        for name in sorted(os.listdir(DAYS_DIR)):
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}\.json", name):
                try:
                    with open(os.path.join(DAYS_DIR, name), "r", encoding="utf-8") as f:
                        out.append(json.load(f))
                except (OSError, ValueError) as e:
                    log(f"   ! {name}: δεν διαβάζεται ({type(e).__name__}) - παραλείπεται από τα παράγωγα, "
                        "το αρχείο δεν πειράζεται")
    return out


def blank_row(h):
    row = {"Hour": f"H{h + 1:02d}", "SCADA_Pump": None, "ISP_Pump": None,
           "SCADA_SmallHydro": None, "SCADA_OtherHydro": None, "SCADA_TotalHydro": None, "MCP_GR": None}
    for k in UNIT_KEYS:
        row[f"SCADA_{k}"] = None
        row[f"ISP_{k}"] = None
    return row


def build_rows(existing_hourly):
    old = {r.get("Hour"): r for r in (existing_hourly or []) if isinstance(r, dict)}
    rows = []
    for h in range(24):
        row = blank_row(h)
        row.update(old.get(row["Hour"], {}))
        rows.append(row)
    return rows


def apply_series(rows, key, series):
    """Γράφει τη σειρά. Μια νέα τιμή null ΔΕΝ σβήνει υπάρχουσα τιμή."""
    if series is None:
        return False
    for h in range(24):
        if series[h] is not None or rows[h].get(key) is None:
            rows[h][key] = series[h]
    return True


def isp_to_local(cur, prev):
    """cur/prev: [24] ώρες αγοράς (CET) των ημερών D και D-1 (ή None).
    -> [24] ώρα Ελλάδας της D:  H01 = τελευταία ώρα αγοράς της D-1,  H02.. = ώρες αγοράς 1..23 της D."""
    if cur is None:
        return None
    first = prev[23] if prev is not None else None
    return [first] + list(cur[:23])


def get_isp(d, cache):
    if d not in cache:
        cache[d] = None
        content = fetch_admie_file(CAT_ISP, d)
        if content:
            try:
                cache[d] = parse_isp(content)
            except Exception as e:
                log(f"   ! ISP parse ({d}): {type(e).__name__}: {e}")
    return cache[d]


def _share(values):
    vals = list(values)
    if not vals:
        return "missing"
    n = sum(v is not None for v in vals)
    return "missing" if n == 0 else ("ok" if n == len(vals) else "partial")


def source_status(rec):
    rows = rec.get("Hourly") or []

    def col(keys):
        return [r.get(k) for r in rows for k in keys]

    res = rec.get("Reservoir") or {}
    if not res:
        reservoir = "missing"
    elif len(res) == len(RESERVOIRS) and rec.get("ReservoirTotalRate") is not None:
        reservoir = "ok"
    else:
        reservoir = "partial"
    scada_keys = ([f"SCADA_{k}" for k in UNIT_KEYS]
                  + ["SCADA_Pump", "SCADA_OtherHydro", "SCADA_TotalHydro"])
    return {
        "reservoir": reservoir,
        "scada": _share(col(scada_keys)),
        "isp": _share(col([f"ISP_{k}" for k in UNIT_KEYS] + ["ISP_Pump"])),
        "resmv": _share(col(["SCADA_SmallHydro"])),
        "mcp": _share(col(["MCP_GR"])),
    }


ORDER = ["Date", "Reservoir", "ReservoirTotal", "ReservoirTotalRate", "Hourly", "Meta"]


def ordered(rec):
    out = {k: rec[k] for k in ORDER if k in rec}
    out.update({k: v for k, v in rec.items() if k not in out})
    return out


def content_key(rec):
    return json.dumps({k: v for k, v in rec.items() if k != "Meta"}, sort_keys=True, ensure_ascii=False)


def process_day(d, existing, isp_cache=None):
    """Επιστρέφει (record, got_anything)."""
    isp_cache = {} if isp_cache is None else isp_cache
    log()
    log("=" * 60)
    log(f"Επεξεργασία: {d}")
    log("=" * 60)

    rec = json.loads(json.dumps(existing)) if existing else {"Date": d.isoformat()}
    before = content_key(rec)
    got = False

    # --- Reservoir ---
    content = fetch_admie_file(CAT_RESERVOIR, d)
    if content:
        try:
            parsed = parse_reservoir(content)
            if parsed:
                reservoirs, official = parsed
                rec["Reservoir"] = reservoirs
                # ΠΡΟΣΟΧΗ: αριθμητικός μέσος 14 ταμιευτήρων, ΟΧΙ επίσημο ADMIE total.
                rec["ReservoirTotal"] = round(sum(reservoirs.values()) / len(reservoirs), 3)
                if official is not None:
                    rec["ReservoirTotalRate"] = official      # επίσημο ADMIE total
                got = True
        except Exception as e:
            log(f"   ! Reservoir parse: {type(e).__name__}: {e}")

    # --- Hourly sources (όλα σε ώρα Ελλάδας) ---
    rows = build_rows(rec.get("Hourly"))
    touched = False

    content = fetch_admie_file(CAT_SCADA, d)
    if content:
        try:
            units, pump, extra = parse_scada(content)
            for k, series in units.items():
                touched |= apply_series(rows, f"SCADA_{k}", series)
            touched |= apply_series(rows, "SCADA_Pump", pump)
            touched |= apply_series(rows, "SCADA_OtherHydro", extra["OtherHydro"])
            touched |= apply_series(rows, "SCADA_TotalHydro", extra["TotalHydro"])
        except Exception as e:
            log(f"   ! SCADA parse: {type(e).__name__}: {e}")

    cur = get_isp(d, isp_cache)
    if cur is not None:
        prev = get_isp(d - timedelta(days=1), isp_cache)
        if prev is None:
            log("   ! ISP: λείπει το αρχείο της προηγούμενης ημέρας -> H01 (00:00-01:00) = null")
        for k, series in cur[0].items():
            touched |= apply_series(rows, f"ISP_{k}", isp_to_local(series, prev[0].get(k) if prev else None))
        touched |= apply_series(rows, "ISP_Pump", isp_to_local(cur[1], prev[1] if prev else None))

    content = fetch_admie_file(CAT_RESMV, d)
    if content:
        try:
            touched |= apply_series(rows, "SCADA_SmallHydro", parse_resmv(content))
        except Exception as e:
            log(f"   ! RESMV parse: {type(e).__name__}: {e}")

    touched |= apply_series(rows, "MCP_GR", fetch_mcp(d))

    if touched or rec.get("Hourly"):
        rec["Hourly"] = rows
        got = got or touched

    # --- Meta ---
    rec = ordered(rec)
    changed = content_key(rec) != before
    status = source_status(rec)
    old_meta = rec.get("Meta") or {}
    meta = {"Schema": SCHEMA_VERSION, "Status": status, "Updated": old_meta.get("Updated")}
    if changed or not meta["Updated"]:
        meta["Updated"] = datetime.now(ATHENS).strftime("%Y-%m-%dT%H:%M:%S%z")
    rec["Meta"] = meta
    log(f"   Κατάσταση: {status}  ({'άλλαξε' if changed else 'χωρίς αλλαγές'})")
    return rec, got


# ---------- παράγωγα: index / reservoir history / monthly ----------

def _tot(H, key):
    v = [h.get(key) for h in H if h.get(key) is not None]
    return round(sum(v), 1) if v else None


def day_summary(rec):
    H = rec.get("Hourly") or []
    mcp = [h["MCP_GR"] for h in H if h.get("MCP_GR") is not None]
    return {
        "Date": rec["Date"],
        "SCADA_MWh": {k: _tot(H, f"SCADA_{k}") for k in UNIT_KEYS},
        "ISP_MWh": {k: _tot(H, f"ISP_{k}") for k in UNIT_KEYS},
        "SCADA_OtherHydro_MWh": _tot(H, "SCADA_OtherHydro"),
        "SCADA_TotalHydro_MWh": _tot(H, "SCADA_TotalHydro"),
        "SmallHydro_MWh": _tot(H, "SCADA_SmallHydro"),
        "Pump_MWh": {"SCADA": _tot(H, "SCADA_Pump"), "ISP": _tot(H, "ISP_Pump")},
        "MCP": ({"mean": round(sum(mcp) / len(mcp), 2), "min": min(mcp), "max": max(mcp),
                 "negative_hours": sum(m < 0 for m in mcp), "hours": len(mcp)} if mcp else None),
        "Reservoir": {"official": rec.get("ReservoirTotalRate"), "mean14": rec.get("ReservoirTotal")},
        "Status": (rec.get("Meta") or {}).get("Status"),
    }


def month_summary(month, recs):
    days = [day_summary(r) for r in sorted(recs, key=lambda r: r["Date"])]

    def acc(group):
        out = {}
        for k in UNIT_KEYS:
            vals = [dd[group][k] for dd in days if dd[group][k] is not None]
            out[k] = round(sum(vals), 1) if vals else None
        return out

    def acc_scalar(key):
        vals = [dd[key] for dd in days if dd[key] is not None]
        return round(sum(vals), 1) if vals else None

    return {
        "Schema": SCHEMA_VERSION, "Month": month, "Clock": CLOCK_NOTE, "DaysCount": len(days),
        "Totals": {
            "SCADA_MWh": acc("SCADA_MWh"), "ISP_MWh": acc("ISP_MWh"),
            "SCADA_OtherHydro_MWh": acc_scalar("SCADA_OtherHydro_MWh"),
            "SCADA_TotalHydro_MWh": acc_scalar("SCADA_TotalHydro_MWh"),
            "SmallHydro_MWh": acc_scalar("SmallHydro_MWh"),
            "Pump_MWh": {"SCADA": round(sum(dd["Pump_MWh"]["SCADA"] or 0 for dd in days), 1),
                         "ISP": round(sum(dd["Pump_MWh"]["ISP"] or 0 for dd in days), 1)},
        },
        "Days": days,
    }


def rebuild_derived(touched_months):
    days = load_all_days()
    by_date = sorted(days, key=lambda r: r["Date"])
    index = {
        "Schema": SCHEMA_VERSION, "Clock": CLOCK_NOTE, "Count": len(by_date),
        "First": by_date[0]["Date"] if by_date else None, "Last": by_date[-1]["Date"] if by_date else None,
        "Days": [{"Date": r["Date"], "Status": (r.get("Meta") or {}).get("Status"),
                  "Updated": (r.get("Meta") or {}).get("Updated")} for r in reversed(by_date)],
    }
    atomic_write_json(INDEX_FILE, index, indent=1)
    history = [{"Date": r["Date"], "ReservoirTotalRate": r.get("ReservoirTotalRate"),
                "ReservoirTotal": r.get("ReservoirTotal"), "Reservoir": r.get("Reservoir")}
               for r in by_date if r.get("Reservoir")]
    atomic_write_json(RES_HISTORY_FILE, history, indent=1)
    for m in sorted(touched_months):
        recs = [r for r in by_date if r["Date"].startswith(m)]
        if recs:
            atomic_write_json(os.path.join(MONTHLY_DIR, f"{m}.json"), month_summary(m, recs), indent=1)


# ============================================================
# DIAGNOSE
# ============================================================

def _entsoe_structure(text):
    """Περίληψη ανά TimeSeries/Period, για να φανεί γιατί τα σημεία δεν είναι 96."""
    root = ET.fromstring(text)
    strip = lambda t: t.split("}")[-1]
    n_ts = 0
    for ts in root.iter():
        if strip(ts.tag) != "TimeSeries":
            continue
        n_ts += 1
        info = {strip(c.tag): (c.text or "").strip() for c in ts if len(c) == 0 and (c.text or "").strip()}
        log(f"  TimeSeries #{n_ts}: {info}")
        for per in ts:
            if strip(per.tag) != "Period":
                continue
            d = {}
            pts = []
            for c in per.iter():
                t = strip(c.tag)
                if t in ("start", "end", "resolution"):
                    d[t] = (c.text or "").strip()
            for pt in per:
                if strip(pt.tag) == "Point":
                    v = {strip(x.tag): x.text for x in pt}
                    pts.append((v.get("position"), v.get("price.amount")))
            first = pts[0] if pts else None
            last = pts[-1] if pts else None
            log(f"    Period {d} points={len(pts)} first={first} last={last}")
    log(f"  σύνολο TimeSeries: {n_ts}")


def _entsoe_text(start, end, what="ENTSO-E"):
    r = http_get(ENTSOE_URL, params={
        "securityToken": ENTSOE_TOKEN, "documentType": "A44",
        "in_Domain": ENTSOE_GR, "out_Domain": ENTSOE_GR,
        "periodStart": start.strftime("%Y%m%d%H%M"), "periodEnd": end.strftime("%Y%m%d%H%M")},
        what=what, use_session=False)
    if r is None or r.status_code != 200:
        log(f"HTTP {getattr(r, 'status_code', None)}")
        return None
    return r.text


def diagnose(d):
    """Δεν γράφει JSON. Σειρά εκτύπωσης: τα πιο σημαντικά ΤΕΛΕΥΤΑΙΑ (αν κοπεί το paste, μένουν αυτά)."""
    log(f"=== DIAGNOSE {d} (δεν γράφεται JSON) ===")

    log(f"\n--- {CAT_RESERVOIR} ---")
    c = fetch_admie_file(CAT_RESERVOIR, d)
    if c:
        parsed = parse_reservoir(c)
        log(f"επίσημο total = {parsed[1] if parsed else None}")

    log(f"\n--- {CAT_RESMV} ---")
    pv_resmv = scada_res = None
    c = fetch_admie_file(CAT_RESMV, d)
    if c:
        small = parse_resmv(c)
        log(f"ΜΥΗΣ MWh ανά ώρα: {small}")
        rdf = pd.read_excel(io.BytesIO(c))
        pcols = [col for col in rdf.columns if "Φ/Β ΕΝΕΡΓΕΙΑ" in norm(col)]
        if pcols:
            pv = pd.to_numeric(rdf[pcols[0]], errors="coerce").dropna().to_numpy(dtype=float)[:24]
            pv_resmv = nan_to_none_list(pv / 1000.0)

    log("\n--- ENTSO-E ---")
    mcp_market = mcp_local = None
    if not ENTSOE_TOKEN:
        log("δεν υπάρχει ENTSOE_TOKEN")
    else:
        start, end = entsoe_window(d)
        log(f"παράθυρο αιτήματος (UTC): {start:%Y-%m-%d %H:%M} -> {end:%Y-%m-%d %H:%M}  (ημέρα αγοράς, CET)")
        text = _entsoe_text(start, end)
        if text:
            _entsoe_structure(text)
            mcp_market = parse_entsoe_xml(text, start)
        # για σύγκριση: ωριαία με ώρα Ελλάδας
        astart, aend = entsoe_window(d, ATHENS)
        text2 = _entsoe_text(astart, aend, "ENTSO-E (ώρα Ελλάδας)")
        if text2:
            mcp_local = parse_entsoe_xml(text2, astart)

    pumps = {}
    for cat, label_col, c0, pref in ((CAT_SCADA, SCADA_LABEL_COL, SCADA_H0, "System_Production"),
                                     (CAT_ISP, ISP_LABEL_COL, ISP_Q0, None)):
        log(f"\n--- {cat} ---")
        c = fetch_admie_file(cat, d)
        if not c:
            continue
        xls = pd.ExcelFile(io.BytesIO(c))
        df, name = read_sheet(c, pref)
        log(f"φύλλα: {xls.sheet_names} | φύλλο pipeline: '{name}' shape={df.shape}")
        if df.shape[1] <= label_col:
            log("   ! δεν υπάρχει η στήλη ετικετών")
            continue
        labels = [norm(x) for x in df[label_col]]
        for key, scada_names, isp_names in HYDRO_UNITS:
            idx, how = find_row(labels, scada_names if cat == CAT_SCADA else isp_names,
                                exclude=("PUMP", "ΑΝΤΛ"))
            if idx is None:
                log(f"   NOT FOUND  {key}")
            else:
                v = to_numeric_array(df.iloc[idx, c0:c0 + 4], 4)
                log(f"   {how:<8} {key:<13} r{idx:03d} {df.iloc[idx, label_col]!r} -> {nan_to_none_list(v)}")
        extra = [norm(x) for x in ("PUMP", "TOTAL", "ΑΝΤΛ", "ΕΔΕΣ", "EDES", "ΑΓΡΑ", "AGRA")]
        log("γραμμές pump/total/Εδεσσαίος/Άγρας:")
        for i, l in enumerate(labels):
            if l and any(k in l for k in extra):
                v = to_numeric_array(df.iloc[i, c0:c0 + 4], 4)
                log(f"   r{i:03d} {df.iloc[i, label_col]!r} -> {nan_to_none_list(v)}")
        if cat == CAT_SCADA:
            pi, _ = find_row(labels, ["TOTAL PUMPING"])
            if pi is not None:
                pumps["scada"] = nan_to_none_list(to_numeric_array(df.iloc[pi, SCADA_H0:SCADA_H1], 24))
            ti, _ = find_row(labels, ["TOTAL HYDRO"])
            matched = [find_row(labels, names, exclude=("PUMP", "ΑΝΤΛ"))[0] for _k, names, _i in HYDRO_UNITS]
            matched = [m for m in matched if m is not None]
            if ti is not None and matched:
                log("υδροηλεκτρικό μπλοκ (όλες οι γραμμές, [m] = έχει αντιστοιχιστεί σε μονάδα):")
                for i in range(max(0, min(matched) - 3), ti + 1):
                    v = to_numeric_array(df.iloc[i, SCADA_H0:SCADA_H0 + 4], 4)
                    log(f"   r{i:03d} {'[m]' if i in matched else '   '} {df.iloc[i, label_col]!r} -> {nan_to_none_list(v)}")
                tot = to_numeric_array(df.iloc[ti, SCADA_H0:SCADA_H1], 24)
                ssum = np.nansum([to_numeric_array(df.iloc[m, SCADA_H0:SCADA_H1], 24) for m in matched], axis=0)
                log(f"TOTAL HYDRO - Σ(αντιστοιχισμένες μονάδες), ανά ώρα: {nan_to_none_list(tot - ssum)}")
            ri, _ = find_row(labels, ["TOTAL RES"])
            if ri is not None:
                scada_res = nan_to_none_list(to_numeric_array(df.iloc[ri, SCADA_H0:SCADA_H1], 24))
        else:
            hp = _isp_rows_to_hourly(df, labels, ISP_PUMP_UNITS, exact_only=True)
            if hp is not None:
                pumps["isp"] = nan_to_none_list(-hp)

    log("\n--- ΕΛΕΓΧΟΣ ΩΡΩΝ RESMV: Φ/Β του RESMV (MWh) vs TOTAL RES του SCADA (MW) ---")
    log(f"RESMV Φ/Β : {pv_resmv}")
    log(f"SCADA RES : {scada_res}")

    log("\n--- ΕΛΕΓΧΟΣ ΩΡΩΝ: η άντληση πρέπει να τρέχει μόνο στις ώρες με αρνητική τιμή ---")
    log(" H   SCADA_pump  ISP_pump   MCP(ώρες αγοράς/CET)   MCP(ώρες Ελλάδας)")
    for h in range(24):
        def g(lst):
            return "-" if not lst or lst[h] is None else lst[h]
        log(f"H{h + 1:02d}  {str(g(pumps.get('scada'))):>10}  {str(g(pumps.get('isp'))):>8}   "
            f"{str(g(mcp_market)):>18}   {str(g(mcp_local)):>16}")


# ============================================================
# MAIN
# ============================================================

def parse_date(value, name):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError(f"{name}='{value}' δεν είναι έγκυρη ημερομηνία (YYYY-MM-DD)")


def get_date_range(args):
    if args:
        s = parse_date(args[0], "START")
        e = parse_date(args[1], "END") if len(args) > 1 else s
        return s, e
    sv, ev = os.environ.get("START_DATE"), os.environ.get("END_DATE")
    if sv:
        s = parse_date(sv, "START_DATE")
        return s, parse_date(ev, "END_DATE") if ev else s
    today = datetime.now(ATHENS).date()
    return today - timedelta(days=LOOKBACK_DAYS - 1), today


def main():
    argv = sys.argv[1:]
    diag = "--diagnose" in argv
    args = [a for a in argv if not a.startswith("--")]
    try:
        start, end = get_date_range(args)
    except ValueError as exc:
        log(f"Σφάλμα ημερομηνίας: {exc}")
        return 1
    if end < start:
        log("ΣΦΑΛΜΑ: END πριν από START")
        return 1

    if diag:
        diagnose(start)
        return 0

    log("=" * 60)
    log(f"HYDRO UPDATE v3  {start} -> {end}  ({(end - start).days + 1} ημέρες)")
    log("=" * 60)

    any_got, touched_months, isp_cache, written = False, set(), {}, 0
    d = start
    try:
        while d <= end:
            existing = load_day(d)           # χαλασμένο αρχείο -> exception -> σταματάμε
            rec, got = process_day(d, existing, isp_cache)
            any_got |= got
            if existing is None and not got:
                log("   - καμία πηγή δεν είχε δεδομένα: δεν δημιουργείται αρχείο ημέρας")
            elif existing is None or json.dumps(rec, sort_keys=True) != json.dumps(existing, sort_keys=True):
                atomic_write_json(day_path(d), rec)
                touched_months.add(d.strftime("%Y-%m"))
                written += 1
            d += timedelta(days=1)
    except Exception as exc:
        log(f"ΣΤΑΜΑΤΑΜΕ στην ημέρα {d}: {type(exc).__name__}: {exc}. "
            "Τα ήδη γραμμένα αρχεία ημερών παραμένουν έγκυρα, τίποτα δεν αντικαταστάθηκε από κενό.")
        rebuild_derived(touched_months)
        return 1

    rebuild_derived(touched_months)
    log()
    log("=" * 60)
    log(f"Ολοκληρώθηκε. Αρχεία ημερών που γράφτηκαν/ενημερώθηκαν: {written}")
    if not any_got:
        log("ΠΡΟΣΟΧΗ: δεν ανακτήθηκε ΚΑΝΕΝΑ δεδομένο για το διάστημα (έλεγξε ADMIE/ENTSO-E).")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
