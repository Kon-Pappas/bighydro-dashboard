#!/usr/bin/env python3
"""
Αντλησιοταμίευση: νερό που ανακυκλώνεται έναντι νερού ποταμού  ->  data/psh_daily.json

Για κάθε ημέρα και για τους δύο σταθμούς με άντληση (Σφηκιά, Θησαυρός):
    Q   = E_παραγωγής / k_παραγωγής        νερό που στροβιλίστηκε στον σταθμό (hm3)   k_παραγωγής = 2,725·H_καθαρή·η_μέση (όπως στο ισοζύγιο νερού)
    P   = E_άντλησης  / k_άντλησης         νερό που αντλήθηκε (hm3)                    k_άντλησης  = 2,725·(H_μικτή·1,02)/0,87  (ΥΠΟΘΕΣΕΙΣ)
    Qc  = E_γειτονικού / k_γειτονικού      νερό που στροβίλισε ο «γειτονικός» σταθμός (hm3)
          Σφηκιά: ο ανάντη Πολύφυτος (το νερό ποταμού που φτάνει)·  Θησαυρός: η κατάντη Πλατανόβρυση

Παράγωγοι δείκτες (υπολογίζονται στη σελίδα από αθροίσματα περιόδου):
    ανακυκλωμένο ποσοστό = P / Q          (το νερό που στροβιλίστηκε και είχε αντληθεί πρώτα)
    κλείσιμο όγκων       = (Qc + P) / Q   (≈ 1 όταν ο υπολογισμός είναι συνεπής· > 1 όταν προστίθεται φυσική εισροή)

Η άντληση ανά σταθμό είναι ΕΚΤΙΜΗΣΗ (pump_daily.json: το σύνολο SCADA μοιρασμένο με το ISP). Η πτώση άντλησης και ο βαθμός
απόδοσης είναι υποθέσεις· ±10% στο k_άντλησης μετακινεί ανάλογα το ανακυκλωμένο ποσοστό.

Είσοδοι: data/days/*.json, data/pump_daily.json, data/plant_heads.json     Έξοδος: data/psh_daily.json
"""
import glob
import json
import os
import sys
from datetime import date, datetime
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_water_balance import k_values        # ίδιοι συντελεστές με το ισοζύγιο νερού (καθαρή/μικτή πτώση)

DATA = "data"
OUT = os.path.join(DATA, "psh_daily.json")
ATHENS = ZoneInfo("Europe/Athens")
G = 2.725
PUMP_HEAD_FACTOR = 1.02     # ανύψωση = μικτή πτώση × 1,02 (υδραυλικές απώλειες)
PUMP_ETA = 0.87             # βαθμός απόδοσης άντλησης (υπόθεση)

PLANTS = {
    "SFIKIA": {"unit": "Sfikia", "est": "EstSfikiaMWh", "isp": "IspSfikiaMWh", "comp": "POLYFYTO", "comp_unit": "Polyfyto",
               "lower": "ASOMATA", "comp_role": "upstream"},
    "THESAVROS": {"unit": "Thesavros", "est": "EstThesavrosMWh", "isp": "IspThesavrosMWh", "comp": "PLATANOVRYSI", "comp_unit": "Platanovrysi",
                  "lower": "PLATANOVRYSI", "comp_role": "lower"},
}


def log(m=""):
    print(m, flush=True)


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main():
    for f in ("plant_heads.json", "pump_daily.json"):
        if not os.path.exists(os.path.join(DATA, f)):
            log(f"Λείπει το data/{f}")
            return 1
    heads = load_json(os.path.join(DATA, "plant_heads.json"))["Plants"]
    pump = {x["Date"]: x for x in load_json(os.path.join(DATA, "pump_daily.json"))}
    dams = sorted({k for p, c in PLANTS.items() for k in (p, c["comp"])})
    net, _gross, est, _ratio = k_values(heads, dams)
    plants = {}
    for dam, c in PLANTS.items():
        kg, kc = net[dam], net[c["comp"]]
        kp = G * heads[dam]["GrossHeadM"] * PUMP_HEAD_FACTOR / PUMP_ETA
        plants[dam] = {"Unit": c["unit"], "Companion": c["comp"], "CompanionRole": c["comp_role"], "LowerDam": c["lower"],
                       "KGenNet": round(kg, 1), "KCompNet": round(kc, 1), "KPump": round(kp, 1), "CycleFactor": round(kg / kp, 3),
                       "NetHeadEstimatedFor": [k for k in (dam, c["comp"]) if k in est], "Daily": []}
    skipped = 0
    for f in sorted(glob.glob(os.path.join(DATA, "days", "*.json"))):
        try:
            rec = load_json(f)
            d = rec["Date"]
            date.fromisoformat(d)
        except (OSError, ValueError, KeyError) as e:
            log(f"   ! {os.path.basename(f)} δεν διαβάζεται ({type(e).__name__}) - παραλείπεται")
            skipped += 1
            continue
        H = rec.get("Hourly") or []
        pr = pump.get(d)
        if not H or (rec.get("Meta") or {}).get("Status", {}).get("scada") != "ok" or not pr:
            continue
        for dam, c in PLANTS.items():
            ep = pr.get(c["est"])
            if ep is None:
                continue
            try:
                eg = sum(h["SCADA_" + c["unit"]] for h in H)
                ec = sum(h["SCADA_" + c["comp_unit"]] for h in H)
            except (KeyError, TypeError):
                continue
            p = plants[dam]
            p["Daily"].append({"Date": d, "Eg": round(eg, 1), "Ep": round(ep, 1), "Ei": pr.get(c["isp"]),
                               "Q": round(eg / p["KGenNet"], 3), "P": round(ep / p["KPump"], 3), "Qc": round(ec / p["KCompNet"], 3)})
    for dam, p in plants.items():
        log(f"{dam}: {len(p['Daily'])} ημέρες | k παραγωγής {p['KGenNet']} · k άντλησης {p['KPump']} · συντελεστής κύκλου {p['CycleFactor']}")
    if not any(p["Daily"] for p in plants.values()):
        log("Δεν βρέθηκαν ημέρες με SCADA και εκτίμηση άντλησης")
        return 1
    doc = {"Schema": 1, "Generated": datetime.now(ATHENS).strftime("%Y-%m-%dT%H:%M:%S%z"),
           "Method": "ανακυκλωμένο ποσοστό = νερό που αντλήθηκε / νερό που στροβιλίστηκε· κλείσιμο όγκων = (νερό γειτονικού σταθμού + αντλούμενο) / νερό που στροβιλίστηκε",
           "Assumptions": {"PumpHeadFactor": PUMP_HEAD_FACTOR, "PumpEfficiency": PUMP_ETA,
                           "Note": "Η πτώση άντλησης (μικτή × 1,02) και ο βαθμός απόδοσης 0,87 είναι υποθέσεις· ±10% στο k άντλησης μετακινεί ανάλογα το ανακυκλωμένο ποσοστό. Η άντληση ανά σταθμό είναι εκτίμηση (SCADA σύνολο μοιρασμένο με ISP)."},
           "Plants": plants}
    os.makedirs(DATA, exist_ok=True)
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
