#!/usr/bin/env python3
"""
Ισοζύγιο νερού ανά ποταμό (Αχελώος, Αλιάκμονας, Νέστος, Άραχθος, Πλαστήρας, Λάδωνας)  ->  data/water_balance.json

Τα φράγματα ομαδοποιούνται (GROUPS). Για κάθε ομάδα g και ημέρα d (στάθμες ΑΔΜΗΕ στις 00:00):
    dV_g      = Σ_{φράγματα της g} [ V(d+1) - V(d) ]               μεταβολή αποθέματος (hm3)
    Q_g       = E_g / k_g                                           νερό που φεύγει από την ομάδα μέσω του σταθμού εξόδου (hm3)
                                                                    E_g = παραγωγή SCADA του σταθμού εξόδου (MWh), k_g = 2,725·H·η (MWh/hm3)
    εισροή_1  = dV_1 + Q_1                                          φαινόμενη εισροή της πρώτης ομάδας
    εισροή_g  = dV_g + Q_g - Q_(g-1)                                ενδιάμεση λεκάνη (g > 1)
    ποταμός   = Σ dV + Q_τελευταίας ομάδας

Γιατί ομάδες: στον Αλιάκμονα η Σφηκιά και τα Ασώματα ενώνονται, επειδή η άντληση (Ασώματα -> Σφηκιά) και το νερό που
στροβιλίζει η Σφηκιά απλοποιούνται αλγεβρικά και δεν χρειάζονται (ούτε ο όγκος άντλησης ούτε η εκτίμηση SCADA/ISP).

"Φαινόμενη" = φυσικές εισροές ΜΕΙΟΝ όσα δεν μετράμε (αρδεύσεις, εξάτμιση, υπερχειλίσεις, οικολογική παροχή).
Δύο εκδοχές συντελεστών: ΚΑΘΑΡΗ και ΜΙΚΤΗ πτώση (data/plant_heads.json, μη επίσημη πηγή).
Ο Στράτος ΙΙ (~6 m) ΔΕΝ μπαίνει στον όγκο. Τιμές 0,00% σε μεγάλο φράγμα θεωρούνται άκυρες και παρεμβάλλονται.

Είσοδοι: data/days/*.json, data/reservoirs.json, data/plant_heads.json   Έξοδος: data/water_balance.json
"""
import glob
import json
import os
import sys
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

DATA = "data"
OUT = os.path.join(DATA, "water_balance.json")
ATHENS = ZoneInfo("Europe/Athens")
G = 2.725
LARGE_DAM_HM3 = 100.0

# ομάδες φραγμάτων (ανάντη -> κατάντη) και ετικέτες εμφάνισης
GROUPS = {
    "acheloos": [(["KREMASTA"], "Κρεμαστά", "Kremasta"),
                 (["KASTRAKI"], "Καστράκι (Ίναχος και τοπική λεκάνη)", "Kastraki (Inachos and local basin)"),
                 (["STRATOS"], "Στράτος (ενδιάμεση λεκάνη)", "Stratos (intermediate basin)")],
    # Η Σφηκιά και τα Ασώματα ενώνονται λόγω της άντλησης (ο όγκος άντλησης αλγεβρικά δεν χρειάζεται).
    # Ο Ιλαρίων μένει ΞΕΧΩΡΙΣΤΟΣ (είναι σε βλάβη - πληροφορία χρήστη): όσο δεν στροβιλίζει, το νερό που τον διαβαίνει δεν μετριέται
    # και εμφανίζεται στον Πολύφυτο. Όταν επανέλθει σε λειτουργία, η διάσπαση Ιλαρίων/Πολύφυτο γίνεται ουσιαστική.
    "aliakmonas": [(["ILARIONAS"], "Ιλαρίων (ανάντη λεκάνη)", "Ilarionas (upstream basin)"),
                   (["POLYFYTO"], "Πολύφυτο (ενδιάμεση λεκάνη)", "Polyfyto (intermediate basin)"),
                   (["SFIKIA", "ASOMATA"], "Σφηκιά και Ασώματα (κάτω λεκάνη)", "Sfikia and Asomata (lower basin)")],
    # Νέστος: ένα σύνολο (η αντλία Πλατανόβρυση -> Θησαυρός ακυρώνεται, άρα η κατεύθυνσή της δεν επηρεάζει το αποτέλεσμα).
    "nestos": [(["THESAVROS", "PLATANOVRYSI"], "Θησαυρός και Πλατανόβρυση", "Thesavros and Platanovrysi")],
    # Άραχθος: η λεκάνη του Αώου ξεχωριστά· Πουρνάρι Ι και ΙΙ μαζί, γιατί το Πουρνάρι ΙΙ είναι μικρός κατάντη ταμιευτήρας με
    # πολύ μικρή (~12 m, εκτιμώμενη) πτώση και ο χωριστός υπολογισμός δίνει ψευδή αρνητικό όρο.
    "arachthos": [(["P_AOOU"], "Πηγές Αώου (λεκάνη Αώου)", "Pigai Aoou (Aoos basin)"),
                  (["POYRNARI1", "POYRNARI2"], "Πουρνάρι Ι και ΙΙ", "Pournari I and II")],
    # Πλαστήρας, Λάδωνας: ένα φράγμα ο καθένας. Το νερό που φεύγει για άλλες χρήσεις (π.χ. άρδευση) δεν μετριέται,
    # άρα το αποτέλεσμα είναι «καθαρό» από λήψεις και υποεκτιμά τη φυσική εισροή.
    "plastiras": [(["PLASTIRAS"], "Πλαστήρας", "Plastiras")],
    "ladonas": [(["LADONAS"], "Λάδωνας", "Ladonas")],
}
TURBINE_UNIT = {"STRATOS": "Stratos1"}       # ποια μονάδα μετράει το νερό που περνά από τον σταθμό (αλλιώς η πρώτη του reservoirs.json)


def log(m=""):
    print(m, flush=True)


def k_values(heads, dams, ratio=None):
    """ratio: ρητός λόγος μικτής/καθαρής πτώσης για σταθμούς ΧΩΡΙΣ τεκμηριωμένη καθαρή πτώση (plant_heads.json: GrossToNetRatio).
    Αν λείπει, υπολογίζεται ως μέσος όρος των σταθμών με τεκμηριωμένη καθαρή πτώση· αν δεν υπάρχουν, 1,125."""
    if ratio is None:
        ratios = [h["GrossHeadM"] / ((h["NetHeadMinM"] + h["NetHeadMaxM"]) / 2) for h in heads.values() if "NetHeadMinM" in h]
        if ratios:
            ratio = sum(ratios) / len(ratios)
        else:
            ratio = 1.125                # δεν υπάρχουν καθαρές πτώσεις στο plant_heads.json: μέσος λόγος των PDF
            log("   ! plant_heads.json χωρίς καθαρές πτώσεις: χρήση λόγου μικτής/καθαρής 1,125 για όλους τους σταθμούς")
    net, gross, est = {}, {}, []
    for k in dams:
        h = heads[k]
        eta = (h["EtaMin"] + h["EtaMax"]) / 2
        gross[k] = G * h["GrossHeadM"] * eta
        if "NetHeadMinM" in h:
            net[k] = G * (h["NetHeadMinM"] + h["NetHeadMaxM"]) / 2 * eta
        else:
            net[k] = G * h["GrossHeadM"] / ratio * eta
            est.append(k)
    return net, gross, est, ratio


def load_days():
    days = {}
    for f in glob.glob(os.path.join(DATA, "days", "*.json")):
        try:
            with open(f, encoding="utf-8") as fh:
                r = json.load(fh)
            days[date.fromisoformat(r["Date"])] = r
        except (OSError, ValueError) as e:
            log(f"   ! {os.path.basename(f)} δεν διαβάζεται ({type(e).__name__}) - παραλείπεται")
    return days


def sanitized_fill(days, dams, caps):
    """{(date, dam): fill%}. Ακριβώς 0,00% σε μεγάλο φράγμα = άκυρη μέτρηση -> γραμμική παρεμβολή. Επιστρέφει (fill, notes)."""
    dates = sorted(d for d in days if days[d].get("Reservoir"))
    fill = {(d, k): float(days[d]["Reservoir"][k]) for d in dates for k in dams}
    notes = []
    for k in dams:
        if caps[k] < LARGE_DAM_HM3:
            continue
        i = 0
        while i < len(dates):
            if fill[(dates[i], k)] == 0.0:
                j = i
                while j < len(dates) and fill[(dates[j], k)] == 0.0:
                    j += 1
                if i > 0 and j < len(dates):
                    va, vb = fill[(dates[i - 1], k)], fill[(dates[j], k)]
                    for q in range(i, j):
                        fill[(dates[q], k)] = va + (vb - va) * (q - (i - 1)) / (j - (i - 1))
                    notes.append({"Dam": k, "From": dates[i].isoformat(), "To": dates[j - 1].isoformat(), "Days": j - i,
                                  "Action": "0,00% θεωρήθηκε άκυρη τιμή, γραμμική παρεμβολή"})
                i = j
            else:
                i += 1
    return fill, notes


def build_river(river, meta, heads, days, ratio=None):
    rid = river["Id"]
    groups = GROUPS[rid]
    dams = [k for g, _a, _b in groups for k in g]
    caps = {k: float(meta["Reservoirs"][k]["CapacityHm3"]) for k in dams}
    outs = [g[-1] for g, _a, _b in groups]                              # σταθμός εξόδου κάθε ομάδας
    unit = {k: TURBINE_UNIT.get(k, meta["Reservoirs"][k]["Units"][0]) for k in outs}
    net, gross, est, ratio = k_values(heads, outs, ratio)
    fill, notes = sanitized_fill(days, dams, caps)
    vol = lambda d, k: fill[(d, k)] / 100.0 * caps[k]
    out = []
    for d in sorted(days):
        nxt = d + timedelta(days=1)
        rec = days[d]
        if (d, dams[0]) not in fill or (nxt, dams[0]) not in fill:
            continue
        if any(fill[(x, k)] == 0.0 for x in (d, nxt) for k in dams if caps[k] >= LARGE_DAM_HM3):
            continue                                      # 0,00% που δεν μπόρεσε να παρεμβληθεί (άκρο σειράς): παράλειψη
        if (rec.get("Meta") or {}).get("Status", {}).get("scada") != "ok" or not rec.get("Hourly"):
            continue
        try:
            E = [sum(h["SCADA_" + unit[k]] for h in rec["Hourly"]) for k in outs]
        except (KeyError, TypeError):
            continue
        dV = [sum(vol(nxt, k) - vol(d, k) for k in g) for g, _a, _b in groups]
        row = {"Date": d.isoformat(), "dV": dV, "E": E}
        for tag, kk in (("n", net), ("g", gross)):
            Q = [E[i] / kk[k] for i, k in enumerate(outs)]
            inflow = [dV[0] + Q[0]] + [dV[i] + Q[i] - Q[i - 1] for i in range(1, len(groups))]
            row["Q" + tag], row["In" + tag], row["River" + tag] = Q, inflow, sum(dV) + Q[-1]
        row = {k: ([round(x, 2) for x in v] if isinstance(v, list) else (round(v, 2) if isinstance(v, float) else v)) for k, v in row.items()}
        row["V"] = [round(sum(vol(d, k) for k in g), 1) for g, _a, _b in groups]
        out.append(row)
    return {"Name": river["Name"],
            "Groups": [{"Dams": g, "OutDam": g[-1], "OutUnit": unit[g[-1]], "LabelEl": a, "LabelEn": b} for g, a, b in groups],
            "KNet": {k: round(v, 1) for k, v in net.items()}, "KGross": {k: round(v, 1) for k, v in gross.items()},
            "NetHeadEstimatedFor": est, "GrossToNetRatio": round(ratio, 3), "Sanitized": notes, "Daily": out}


def main():
    for f in ("reservoirs.json", "plant_heads.json"):
        if not os.path.exists(os.path.join(DATA, f)):
            log(f"Λείπει το data/{f}")
            return 1
    with open(os.path.join(DATA, "reservoirs.json"), encoding="utf-8") as f:
        meta = json.load(f)
    with open(os.path.join(DATA, "plant_heads.json"), encoding="utf-8") as f:
        heads_doc = json.load(f)
    heads, ratio = heads_doc["Plants"], heads_doc.get("GrossToNetRatio")
    days = load_days()
    if not days:
        log("Δεν βρέθηκαν ημέρες")
        return 1
    res = {}
    for r in meta["Rivers"]:
        if r["Id"] in GROUPS:
            res[r["Id"]] = build_river(r, meta, heads, days, ratio)
            n = res[r["Id"]]
            log(f"{r['Id']}: {len(n['Daily'])} ημέρες" + "".join(f" | παρεμβλήθηκε {x['Dam']} {x['From']}→{x['To']}" for x in n["Sanitized"]))
    doc = {"Schema": 2, "Generated": datetime.now(ATHENS).strftime("%Y-%m-%dT%H:%M:%S%z"),
           "Method": "φαινόμενη εισροή = μεταβολή αποθέματος + νερό που φεύγει από την ομάδα - νερό που ήρθε από την ανάντη ομάδα (hm3/ημέρα)",
           "Caveats": ["Η φαινόμενη εισροή είναι φυσική εισροή ΜΕΙΟΝ αρδεύσεις, εξάτμιση, υπερχειλίσεις και οικολογική παροχή (δεν μετρώνται).",
                       "Στο Καστράκι πέφτει ο Ίναχος (πληροφορία χρήστη): η θετική ενδιάμεση εισροή είναι αναμενόμενη. Περιλαμβάνει όμως και ό,τι φτάνει από τα Κρεμαστά χωρίς να περάσει από στρόβιλο, άρα δεν είναι μόνο Ίναχος.",
                       "Το Καστράκι ξεπερνά συχνά το 100%: ο όγκος του (53 hm3 × πλήρωση) είναι αβέβαιος πάνω από το 100%.",
                       "Αλιάκμονας: η Σφηκιά και τα Ασώματα ενώνονται, ώστε η άντληση να μην επηρεάζει το αποτέλεσμα. Ο Ιλαρίων είναι σε βλάβη (πληροφορία χρήστη): το νερό που τον διαβαίνει δεν στροβιλίζεται και εμφανίζεται στον Πολύφυτο. Το νερό που φεύγει από την κάτω λεκάνη μετριέται από τον σταθμό των Ασωμάτων, του οποίου η καθαρή πτώση είναι ΕΚΤΙΜΗΣΗ.",
                       "Νέστος: ο Θησαυρός και η Πλατανόβρυση ενώνονται (η αντλία ακυρώνεται)· Άραχθος: η λεκάνη του Αώου ξεχωριστά, Πουρνάρι Ι και ΙΙ μαζί. Πλαστήρας και Λάδωνας: το νερό που φεύγει για άλλες χρήσεις (π.χ. άρδευση) δεν μετριέται, άρα το αποτέλεσμα είναι καθαρό από λήψεις.",
                       "Η αβεβαιότητα του συνόλου κάθε ποταμού κυριαρχείται από την πτώση του ΤΕΛΕΥΤΑΙΟΥ σταθμού (σταθμός εξόδου), που για αρκετούς είναι εκτίμηση: η διαφορά καθαρής/μικτής είναι η ένδειξη.",
                       "Δύο εκδοχές συντελεστών: καθαρή πτώση (n) και μικτή πτώση (g). Η διαφορά τους είναι ένδειξη της αβεβαιότητας."],
           "Rivers": res}
    os.makedirs(DATA, exist_ok=True)
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
