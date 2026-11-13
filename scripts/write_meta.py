#!/usr/bin/env python3
"""
data/meta.json — πότε έτρεξε η λήψη και πότε είναι η επόμενη προγραμματισμένη (D105).

Ο ΜΟΝΑΔΙΚΟΣ writer του αρχείου. Η σελίδα το διαβάζει για τα «Τελευταία / Επόμενη ενημέρωση» (δεν έχει πια δική της λίστα ωρών).
Οι ώρες των runs είναι γραμμένες ΕΔΩ και πουθενά αλλού (UPDATE_TIMES_ATHENS): τα runs τα ξεκινά το εξωτερικό cron-job.org και το repo δεν μπορεί να τα διαβάσει.
Αν αλλάξεις job στο cron-job.org, άλλαξε και αυτή τη σταθερά (και το σχόλιο στην κορυφή του fetch_data.yml· ένα test το ελέγχει).

Η «επόμενη» υπολογίζεται σε ώρα Αθήνας με τη ζώνη ώρας, άρα είναι σωστή πριν και μετά την αλλαγή ώρας· γράφεται σε UTC («Z»).
Γράφεται ΣΕ ΚΑΘΕ run (εξαίρεση του D98: το `next_update` προχωρά ακόμα κι όταν δεν υπάρχουν νέα δεδομένα), ατομικά (προσωρινό αρχείο + os.replace), και ΜΟΝΟ αφού
έχουν τρέξει επιτυχώς τα βήματα λήψης. Στα runs διάγνωσης (DIAGNOSE=true) δεν γράφεται, γιατί δεν έγινε λήψη.
"""
import json
import os
import sys
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

ATHENS = ZoneInfo("Europe/Athens")
UPDATE_TIMES_ATHENS = ((7, 15), (9, 15), (10, 15), (13, 30))        # ώρες Ελλάδας των jobs του cron-job.org
META_PATH = os.path.join("data", "meta.json")


def next_update_utc(now_utc):
    """Η πρώτη προγραμματισμένη εκτέλεση ΑΥΣΤΗΡΑ μετά το now_utc, σε UTC (ή None αν δεν υπάρχουν ώρες)."""
    now_ath = now_utc.astimezone(ATHENS)
    day = now_ath.date()
    for _ in range(3):
        for h, m in sorted(UPDATE_TIMES_ATHENS):
            cand = datetime.combine(day, time(h, m), tzinfo=ATHENS)
            if cand > now_ath:
                return cand.astimezone(timezone.utc)
        day = day + timedelta(days=1)
    return None


def iso_z(dt):
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_meta(now_utc):
    nxt = next_update_utc(now_utc)
    return {"fetched": iso_z(now_utc), "next_update": iso_z(nxt) if nxt else None}


def write_meta(path=META_PATH, now_utc=None):
    meta = build_meta(now_utc or datetime.now(timezone.utc))
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)
    return meta


def main():
    if (os.environ.get("DIAGNOSE") or "").strip().lower() == "true":
        print("meta.json: run διάγνωσης, δεν γράφεται")
        return 0
    meta = write_meta()
    print(f"meta.json: fetched={meta['fetched']} next_update={meta['next_update']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
