#!/usr/bin/env python3
"""
ENTSO-E 16.1.D "Water Reservoirs and Hydro Storage Plants"  ->  data/entsoe_reservoir.json

Εβδομαδιαία αποθηκευμένη ενέργεια (MWh) για την ελληνική ζώνη προσφορών.
Χρησιμοποιείται για βαθμονόμηση της εκτίμησης "όγκος νερού -> ενέργεια".

ΠΡΟΣΟΧΗ (δεν έχει επαληθευτεί σε ζωντανό API από αυτό το περιβάλλον):
  * documentType=A72, processType=A16, ανάλυση P7D (εβδομαδιαία) - από την τεκμηρίωση του API.
  * Η σύμβαση "σε ποια μέρες αναφέρεται η κάθε εβδομάδα" (μέσος όρος, αρχή ή τέλος) ΔΕΝ υποτίθεται εδώ.
    Αποθηκεύουμε τα ακατέργαστα χρονικά όρια και αποφασίζουμε στην ανάλυση.
  * Τρέξε πρώτα με --diagnose και έλεγξε τη δομή της απάντησης.

Χρήση:
  python scripts/fetch_entsoe_reservoir.py                       # από το τελευταίο δεδομένο (-4 εβδομάδες) ως σήμερα
  python scripts/fetch_entsoe_reservoir.py 2026-01-01 2026-10-07
  python scripts/fetch_entsoe_reservoir.py --diagnose            # δεν γράφει τίποτα

Env: ENTSOE_TOKEN
"""

import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import date, datetime, time as dtime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests

URL = "https://web-api.tp.entsoe.eu/api"
EIC_GR = "10YGR-HTSO-----Y"
OUT = os.path.join("data", "entsoe_reservoir.json")
ATHENS = ZoneInfo("Europe/Athens")
TOKEN = os.environ.get("ENTSOE_TOKEN")
DEFAULT_START = date(2026, 1, 1)
SOURCE = "ENTSO-E Transparency 16.1.D (documentType A72, processType A16)"


def log(msg=""):
    print(msg, flush=True)


def http_get(params, tries=3):
    for attempt in range(1, tries + 1):
        try:
            r = requests.get(URL, params=params, timeout=60)
            if r.status_code >= 500 and attempt < tries:
                log(f"   ! HTTP {r.status_code}, προσπάθεια {attempt}/{tries}")
                time.sleep(2 * attempt)
                continue
            return r
        except requests.RequestException as e:
            # ΜΗΝ τυπώνεις το exception: μπορεί να περιέχει URL με token.
            log(f"   ! {type(e).__name__}, προσπάθεια {attempt}/{tries}")
            time.sleep(2 * attempt)
    return None


def _strip(tag):
    return tag.split("}")[-1]


def _dt(s):
    return datetime.strptime(s.strip(), "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc)


def _iso(d):
    return d.strftime("%Y-%m-%dT%H:%MZ")


def parse_xml(text):
    """-> (weeks[list], series_info[list], reason|None).
    weeks: [{"Start","End","StartLocal","MWh"}]  (Start/End σε UTC)."""
    root = ET.fromstring(text)
    if _strip(root.tag).startswith("Acknowledgement"):
        reason = " ".join((e.text or "").strip() for e in root.iter() if _strip(e.tag) == "text")
        return [], [], reason or "Acknowledgement χωρίς κείμενο"

    weeks, info = {}, []
    for ts in root.iter():
        if _strip(ts.tag) != "TimeSeries":
            continue
        meta = {_strip(c.tag): (c.text or "").strip() for c in ts if len(c) == 0 and (c.text or "").strip()}
        curve = meta.get("curveType")
        for per in ts:
            if _strip(per.tag) != "Period":
                continue
            start = end = res = None
            pts = {}
            for c in per:
                t = _strip(c.tag)
                if t == "timeInterval":
                    for x in c:
                        if _strip(x.tag) == "start":
                            start = (x.text or "").strip()
                        elif _strip(x.tag) == "end":
                            end = (x.text or "").strip()
                elif t == "resolution":
                    res = (c.text or "").strip()
                elif t == "Point":
                    v = {_strip(x.tag): (x.text or "").strip() for x in c}
                    pts[int(v["position"])] = float(v["quantity"])
            m = re.fullmatch(r"P(\d+)([DW])", res or "")
            if not (start and end and m):
                log(f"   ! Period με άγνωστη δομή/ανάλυση: start={start} end={end} res={res}")
                continue
            step = timedelta(days=int(m.group(1)) * (7 if m.group(2) == "W" else 1))
            p_start, p_end = _dt(start), _dt(end)
            n = int(round((p_end - p_start) / step))
            info.append({"series": meta, "start": start, "end": end, "resolution": res,
                         "points": len(pts), "expected": n,
                         "first": sorted(pts.items())[:3], "last": sorted(pts.items())[-2:]})
            last = None
            for pos in range(1, n + 1):
                if pos in pts:
                    last = pts[pos]
                elif curve == "A03" and last is not None:      # A03: οι επαναλαμβανόμενες τιμές παραλείπονται
                    pass
                else:
                    continue
                w_start = p_start + (pos - 1) * step
                key = _iso(w_start)
                if key in weeks:
                    log(f"   ! διπλή εβδομάδα {key} (διαφορετικές σειρές) - κρατάω την πρώτη")
                    continue
                weeks[key] = {"Start": key, "End": _iso(w_start + step),
                              "StartLocal": w_start.astimezone(ATHENS).date().isoformat(), "MWh": last}
    return [weeks[k] for k in sorted(weeks)], info, None


def fetch(start, end):
    ps = datetime.combine(start, dtime(0, 0), tzinfo=ATHENS).astimezone(timezone.utc)
    pe = datetime.combine(end + timedelta(days=1), dtime(0, 0), tzinfo=ATHENS).astimezone(timezone.utc)
    params = {"securityToken": TOKEN, "documentType": "A72", "processType": "A16", "in_Domain": EIC_GR,
              "periodStart": ps.strftime("%Y%m%d%H%M"), "periodEnd": pe.strftime("%Y%m%d%H%M")}
    r = http_get(params)
    if r is None or r.status_code != 200:
        reason = ""
        if r is not None:
            m = re.search(r"<text>(.*?)</text>", r.text, re.S)
            reason = f" ({m.group(1).strip()[:160]})" if m else ""
        log(f"   - ENTSO-E: HTTP {getattr(r, 'status_code', None)}{reason}")
        return None
    try:
        weeks, info, reason = parse_xml(r.text)
    except Exception as e:
        log(f"   ! parse: {type(e).__name__}: {e}")
        log(f"   πρώτοι 400 χαρακτήρες απάντησης: {r.text[:400]!r}")
        return None
    if reason:
        log(f"   - ENTSO-E: χωρίς δεδομένα ({reason[:200]})")
        return None
    return weeks, info


def load():
    if not os.path.exists(OUT) or os.path.getsize(OUT) == 0:
        return {"Weeks": []}
    with open(OUT, "r", encoding="utf-8") as f:
        data = json.load(f)         # χαλασμένο αρχείο -> exception -> σταματάμε
    if not isinstance(data, dict) or not isinstance(data.get("Weeks"), list):
        raise ValueError(f"{OUT}: μη αναμενόμενη δομή")
    return data


def write(weeks):
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    doc = {"Schema": 1, "Source": SOURCE, "Domain": EIC_GR, "Unit": "MWh",
           "Updated": datetime.now(ATHENS).strftime("%Y-%m-%dT%H:%M:%S%z"),
           "Note": "Start/End σε UTC. Η αντιστοίχιση εβδομάδας -> ημέρες (μέσος όρος/αρχή/τέλος) δεν υποτίθεται εδώ.",
           "Weeks": sorted(weeks, key=lambda w: w["Start"])}
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
        f.write("\n")
    os.replace(tmp, OUT)


def diagnose(start, end):
    log("=== ENTSO-E 16.1.D diagnose (δεν γράφεται τίποτα) ===")
    log(f"παράθυρο: {start} -> {end} | ζώνη {EIC_GR}")
    res = fetch(start, end)
    if res is None:
        return 1
    weeks, info = res
    log(f"σειρές/περίοδοι: {len(info)}")
    for i in info:
        log(f"  series={i['series']}")
        log(f"  period {i['start']} -> {i['end']} res={i['resolution']} points={i['points']}/{i['expected']}")
        log(f"  πρώτα σημεία={i['first']}  τελευταία={i['last']}")
    log(f"εβδομάδες συνολικά: {len(weeks)}")
    for w in weeks[-8:]:
        log(f"  {w['StartLocal']}  ({w['Start']} -> {w['End']})  {w['MWh']:,.0f} MWh")
    return 0


def main():
    argv = sys.argv[1:]
    diag = "--diagnose" in argv
    args = [a for a in argv if not a.startswith("--")]
    if not TOKEN:
        log("ENTSOE_TOKEN δεν υπάρχει: παραλείπεται")
        return 1
    existing = {"Weeks": []}
    if not diag:
        try:
            existing = load()
        except Exception as e:
            log(f"ΣΤΑΜΑΤΑΜΕ: το {OUT} δεν διαβάζεται ({type(e).__name__}: {e}). Δεν γράφω τίποτα.")
            return 1
    try:
        today = datetime.now(ATHENS).date()
        if args:
            start = datetime.strptime(args[0], "%Y-%m-%d").date()
            end = datetime.strptime(args[1], "%Y-%m-%d").date() if len(args) > 1 else today
        else:
            start, end = DEFAULT_START, today
            if existing["Weeks"]:
                last = max(w["StartLocal"] for w in existing["Weeks"])
                start = max(DEFAULT_START, datetime.strptime(last, "%Y-%m-%d").date() - timedelta(days=28))
    except ValueError as e:
        log(f"Σφάλμα ημερομηνίας: {e}")
        return 1
    if diag:
        return diagnose(start, end)

    log(f"ENTSO-E weekly reservoir: {start} -> {end}")
    res = fetch(start, end)
    if res is None:
        return 1
    weeks, _ = res
    if not weeks:
        log("   - καμία εβδομάδα στην απάντηση")
        return 1
    merged = {w["Start"]: w for w in existing["Weeks"]}
    new = sum(1 for w in weeks if w["Start"] not in merged)
    revised = sum(1 for w in weeks if w["Start"] in merged and merged[w["Start"]]["MWh"] != w["MWh"])
    for w in weeks:
        merged[w["Start"]] = w                    # το ENTSO-E μπορεί να αναθεωρεί τιμές
    write(list(merged.values()))
    log(f"   + εβδομάδες: {len(weeks)} στην απάντηση, {new} νέες, {revised} αναθεωρημένες, {len(merged)} συνολικά")
    log(f"   τελευταία: {weeks[-1]['StartLocal']}  {weeks[-1]['MWh']:,.0f} MWh")
    return 0


if __name__ == "__main__":
    sys.exit(main())
