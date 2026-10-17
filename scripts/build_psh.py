#!/usr/bin/env python3
"""
Αντλησιοταμίευση: νερό που ανακυκλώνεται έναντι νερού ποταμού  ->  data/psh_daily.json

Ο κύκλος γίνεται ανάμεσα στον ΑΝΩ και τον ΚΑΤΩ ταμιευτήρα του ίδιου σταθμού:
    Σφηκιά   <-> Ασώματα          (ο Πολύφυτος ΔΕΝ ανήκει στον κύκλο· είναι μόνο πηγή νερού ποταμού που φτάνει στη Σφηκιά)
    Θησαυρός <-> Πλατανόβρυση     (το νερό του Νέστου έρχεται από τη Βουλγαρία: δεν υπάρχει μετρημένος σταθμός ανάντη)

Για κάθε ημέρα και σταθμό:
    Q   = E_παραγωγής / k_παραγωγής       νερό που στροβιλίστηκε στον άνω σταθμό (hm3)    k = 2,725·H_καθαρή·η_μέση (όπως στο ισοζύγιο νερού)
    P   = E_άντλησης  / k_άντλησης        νερό που αντλήθηκε (hm3)                        k_άντλησης = 2,725·(H_μικτή·1,02)/0,87  (ΥΠΟΘΕΣΕΙΣ)
    Ql  = E_κάτω σταθμού / k_κάτω         νερό που στροβίλισε ο κάτω σταθμός (Ασώματα / Πλατανόβρυση): φεύγει προς το ποτάμι
    Qu  = E_ανάντη σταθμού / k_ανάντη     (μόνο Σφηκιά) νερό που στροβίλισε ο Πολύφυτος: φτάνει στον ταμιευτήρα της Σφηκιάς

Δείκτες (υπολογίζονται στη σελίδα από αθροίσματα περιόδου):
    ανακυκλωμένο ποσοστό      = P / Q          (σε ΟΓΚΟ νερού, όχι ενέργεια)
    έλεγχος ΚΑΤΩ ταμιευτήρα   = (Ql + P) / Q   νερό που μπαίνει στον κάτω ταμιευτήρα = νερό που φεύγει προς το ποτάμι + νερό που αντλείται πίσω
    έλεγχος ΑΝΩ ταμιευτήρα    = (Qu + P) / Q   (μόνο όπου υπάρχει μετρημένη ανάντη πηγή)
Κοντά στο 1: οι ανεξάρτητες εκτιμήσεις συμφωνούν· > 1: προστίθεται φυσική εισροή· < 1: νερό φεύγει χωρίς να περάσει από στρόβιλο ή να αντληθεί.

Η άντληση ανά σταθμό είναι ΕΚΤΙΜΗΣΗ (pump_daily.json: το σύνολο SCADA μοιρασμένο με το ISP). Η πτώση άντλησης και ο βαθμός
απόδοσης είναι υποθέσεις· ο «συντελεστής κύκλου» k_παραγωγής/k_άντλησης είναι υποπροϊόν τους, ΟΧΙ μετρημένος βαθμός απόδοσης.

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
    "SFIKIA": {"unit": "Sfikia", "est": "EstSfikiaMWh", "isp": "IspSfikiaMWh", "lower": "ASOMATA", "lower_unit": "Asomata",
               "upper": "POLYFYTO", "upper_unit": "Polyfyto"},
    "THESAVROS": {"unit": "Thesavros", "est": "EstThesavrosMWh", "isp": "IspThesavrosMWh", "lower": "PLATANOVRYSI", "lower_unit": "Platanovrysi",
                  "upper": None, "upper_unit": None},
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
    heads_doc = load_json(os.path.join(DATA, "plant_heads.json"))
    heads, ratio = heads_doc["Plants"], heads_doc.get("GrossToNetRatio")
    pump = {x["Date"]: x for x in load_json(os.path.join(DATA, "pump_daily.json"))}
    dams = sorted({k for p, c in PLANTS.items() for k in (p, c["lower"], c["upper"]) if k})
    net, _gross, est, _ratio = k_values(heads, dams, ratio)
    plants = {}
    for dam, c in PLANTS.items():
        kg, kl = net[dam], net[c["lower"]]
        ku = net[c["upper"]] if c["upper"] else None
        kp = G * heads[dam]["GrossHeadM"] * PUMP_HEAD_FACTOR / PUMP_ETA
        plants[dam] = {"Unit": c["unit"], "LowerDam": c["lower"], "UpperSource": c["upper"],
                       "KGenNet": round(kg, 1), "KLowerNet": round(kl, 1), "KUpperNet": round(ku, 1) if ku else None,
                       "KPump": round(kp, 1), "CycleFactor": round(kg / kp, 3),
                       "NetHeadEstimatedFor": [k for k in (dam, c["lower"], c["upper"]) if k and k in est], "Daily": []}
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
                el = sum(h["SCADA_" + c["lower_unit"]] for h in H)
                eu = sum(h["SCADA_" + c["upper_unit"]] for h in H) if c["upper_unit"] else None
            except (KeyError, TypeError):
                continue
            p = plants[dam]
            row = {"Date": d, "Eg": round(eg, 1), "Ep": round(ep, 1), "Ei": pr.get(c["isp"]),
                   "Q": round(eg / p["KGenNet"], 3), "P": round(ep / p["KPump"], 3), "Ql": round(el / p["KLowerNet"], 3)}
            if eu is not None:
                row["Qu"] = round(eu / p["KUpperNet"], 3)
            p["Daily"].append(row)
    for dam, p in plants.items():
        log(f"{dam}: {len(p['Daily'])} ημέρες | k παραγωγής {p['KGenNet']} · k άντλησης {p['KPump']} · συντελεστής κύκλου {p['CycleFactor']}")
    if not any(p["Daily"] for p in plants.values()):
        log("Δεν βρέθηκαν ημέρες με SCADA και εκτίμηση άντλησης")
        return 1
    doc = {"Schema": 2, "Generated": datetime.now(ATHENS).strftime("%Y-%m-%dT%H:%M:%S%z"),
           "Method": "ανακυκλωμένο ποσοστό = νερό που αντλήθηκε / νερό που στροβιλίστηκε (όγκος νερού)· έλεγχος κάτω ταμιευτήρα = (νερό κάτω σταθμού + αντλούμενο) / νερό που στροβιλίστηκε· έλεγχος άνω ταμιευτήρα = (νερό ανάντη σταθμού + αντλούμενο) / νερό που στροβιλίστηκε (μόνο Σφηκιά)",
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
