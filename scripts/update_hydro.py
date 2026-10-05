#!/usr/bin/env python3

import json
import os
import sys
import tempfile
from datetime import datetime, timedelta

import pandas as pd
import requests


# ============================================================
# CONFIG
# ============================================================

BASE_URL = "https://www.admie.gr"

API_FILES = (
    BASE_URL
    + "/getOperationMarketFile"
)

FILE_CATEGORY = "ReservoirFillingRate"

OUTPUT_FILE = "data/hydro_data.json"

TIMEOUT = 60


# ============================================================
# HTTP SESSION
# ============================================================

session = requests.Session()

session.headers.update(
    {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/154.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "application/json, "
            "application/vnd.ms-excel, "
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet, "
            "*/*"
        ),
        "Referer": BASE_URL + "/file-type/reservoirfillingrate",
    }
)


# ============================================================
# RESERVOIR NAMES
# ============================================================

RESERVOIRS = [
    "ASOMATA",
    "ILARIONAS",
    "KASTRAKI",
    "KREMASTA",
    "LADONAS",
    "PLASTIRAS",
    "PLATANOVRYSI",
    "POLYFYTO",
    "POYRNARI1",
    "POYRNARI2",
    "P_AOOU",
    "SFIKIA",
    "STRATOS",
    "THESAVROS",
]


# ============================================================
# DATE
# ============================================================

def get_target_date():
    """
    GitHub Actions can optionally provide TARGET_DATE.

    Example:
        TARGET_DATE=2026-10-05

    If not provided, use today's date.
    """

    value = os.environ.get("TARGET_DATE")

    if value:
        return datetime.strptime(value, "%Y-%m-%d").date()

    return datetime.now().date()


# ============================================================
# FIND ADMIE FILE
# ============================================================

def find_reservoir_file(target_date):
    """
    Ask ADMIE for the actual URL of the ReservoirFillingRate file.

    We deliberately DO NOT construct:

        /get-file/YYYYMMDD_ReservoirFillingRate_01.xls

    because ADMIE explicitly recommends using its web service
    to obtain the correct file URL.
    """

    date_string = target_date.strftime("%Y-%m-%d")

    params = {
        "dateStart": date_string,
        "dateEnd": date_string,
        "FileCategory": FILE_CATEGORY,
    }

    print()
    print("ADMIE API:")
    print(API_FILES)
    print("Παράμετροι:")
    print(params)

    response = session.get(
        API_FILES,
        params=params,
        timeout=TIMEOUT,
    )

    response.raise_for_status()

    data = response.json()

    print("API response type:", type(data).__name__)

    if not data:
        return None

    # --------------------------------------------------------
    # ADMIE normally returns a list.
    # Be slightly defensive because API formatting can change.
    # --------------------------------------------------------

    if isinstance(data, dict):
        if "data" in data:
            data = data["data"]
        elif "results" in data:
            data = data["results"]
        else:
            data = [data]

    if not isinstance(data, list):
        print("Μη αναμενόμενη μορφή απάντησης ADMIE.")
        print(str(data)[:1000])
        return None

    # --------------------------------------------------------
    # Find the record corresponding to our date.
    # --------------------------------------------------------

    candidates = []

    for item in data:

        if not isinstance(item, dict):
            continue

        filename = str(
            item.get("FileName")
            or item.get("filename")
            or item.get("Name")
            or ""
        )

        file_url = (
            item.get("FileURL")
            or item.get("fileURL")
            or item.get("URL")
            or item.get("url")
        )

        if not file_url:
            continue

        candidates.append(
            {
                "filename": filename,
                "url": file_url,
                "item": item,
            }
        )

    if not candidates:
        print("Το ADMIE API δεν επέστρεψε URL αρχείου.")
        print(str(data)[:2000])
        return None

    # Prefer filename containing our target date.
    target_token = target_date.strftime("%Y%m%d")

    dated = [
        item
        for item in candidates
        if target_token in item["filename"]
    ]

    if dated:
        selected = dated[0]
    else:
        selected = candidates[0]

    print()
    print("Βρέθηκε αρχείο ADMIE:")
    print("Filename:", selected["filename"])
    print("URL:", selected["url"])

    return selected["url"]


# ============================================================
# DOWNLOAD FILE
# ============================================================

def download_file(url):
    """
    Download the actual Excel file returned by ADMIE.
    """

    response = session.get(
        url,
        timeout=TIMEOUT,
        allow_redirects=True,
    )

    response.raise_for_status()

    if not response.content:
        raise RuntimeError("Το αρχείο ADMIE είναι κενό.")

    temp = tempfile.NamedTemporaryFile(
        suffix=".xls",
        delete=False,
    )

    temp.write(response.content)
    temp.close()

    print(
        "Downloaded:",
        len(response.content),
        "bytes"
    )

    return temp.name


# ============================================================
# NORMALIZE RESERVOIR NAME
# ============================================================

def normalize_name(value):
    if value is None:
        return ""

    text = str(value).strip().upper()

    # ADMIE uses THESAVROS1 / 2 / 3.
    # We collapse them into one THESAVROS.
    if text.startswith("THESAVROS"):
        return "THESAVROS"

    return text


# ============================================================
# PARSE RESERVOIR EXCEL
# ============================================================

def process_reservoir_file(file_path):
    """
    Read the actual ADMIE ReservoirFillingRate Excel file.

    The known ADMIE structure is:

        column 0 -> Entity
        column 1 -> Filling Rate

    Values are fractions:

        0.7196 -> 71.96%

    The total row is ignored for the individual-reservoir
    dataset because we calculate our own aggregate.
    """

    print()
    print("Άνοιγμα Reservoir Excel...")

    df = pd.read_excel(
        file_path,
        sheet_name=0,
        header=None,
    )

    print("Excel shape:", df.shape)

    reservoirs = {}

    for _, row in df.iterrows():

        if len(row) < 3:
            continue

        entity = normalize_name(row.iloc[1])

        if entity not in RESERVOIRS:
            continue

        raw_rate = row.iloc[2]

        try:
            raw_rate = float(raw_rate)
        except (TypeError, ValueError):
            continue

        # ADMIE publishes the value as a fraction.
        rate_percent = raw_rate * 100.0

        reservoirs[entity] = round(rate_percent, 2)

    # --------------------------------------------------------
    # Validation
    # --------------------------------------------------------

    missing = [
        name
        for name in RESERVOIRS
        if name not in reservoirs
    ]

    if missing:
        print()
        print("ΠΡΟΣΟΧΗ: λείπουν reservoirs:")
        for name in missing:
            print(" -", name)

    print()
    print("Reservoirs που βρέθηκαν:", len(reservoirs), "/", len(RESERVOIRS))

    for name in RESERVOIRS:
        if name in reservoirs:
            print(
                f"  {name:<15} "
                f"{reservoirs[name]:>7.2f}%"
            )

    if len(reservoirs) == 0:
        raise RuntimeError(
            "Δεν βρέθηκε κανένα reservoir στο Excel."
        )

    return reservoirs


# ============================================================
# LOAD EXISTING JSON
# ============================================================

def load_existing_data():
    if not os.path.exists(OUTPUT_FILE):
        return []

    try:
        with open(
            OUTPUT_FILE,
            "r",
            encoding="utf-8",
        ) as f:
            data = json.load(f)

        if isinstance(data, list):
            return data

        return []

    except Exception as exc:
        print(
            "Προειδοποίηση: δεν ήταν δυνατή η ανάγνωση "
            "του υπάρχοντος hydro_data.json:",
            exc,
        )
        return []


# ============================================================
# UPDATE JSON
# ============================================================

def update_json(target_date, reservoirs):

    os.makedirs(
        os.path.dirname(OUTPUT_FILE),
        exist_ok=True,
    )

    data = load_existing_data()

    date_string = target_date.strftime("%Y-%m-%d")

    # --------------------------------------------------------
    # Aggregate filling rate
    #
    # IMPORTANT:
    # This is the simple arithmetic mean of the 14 published
    # reservoir percentages.
    #
    # We are NOT converting to GWh here.
    # --------------------------------------------------------

    system_filling = (
        sum(reservoirs.values()) / len(reservoirs)
    )

    system_filling = round(system_filling, 3)

    new_record = {
        "Date": date_string,
        "Reservoir": reservoirs,
        "ReservoirTotal": system_filling,
    }

    # --------------------------------------------------------
    # Replace existing record for same date.
    # --------------------------------------------------------

    replaced = False

    for i, record in enumerate(data):

        if str(record.get("Date", "")) == date_string:

            # Preserve all existing fields.
            updated = dict(record)

            updated["Reservoir"] = reservoirs
            updated["ReservoirTotal"] = system_filling

            data[i] = updated
            replaced = True
            break

    if not replaced:
        data.append(new_record)

    # --------------------------------------------------------
    # Sort newest first.
    # --------------------------------------------------------

    data.sort(
        key=lambda x: str(x.get("Date", "")),
        reverse=True,
    )

    # --------------------------------------------------------
    # Keep the existing history window.
    #
    # The previous project used a relatively small rolling
    # history. We retain all currently existing records and
    # don't arbitrarily delete historical data.
    # --------------------------------------------------------

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2,
        )

        f.write("\n")

    print()
    print("hydro_data.json ενημερώθηκε.")
    print("Ημερομηνία:", date_string)
    print(
        "System Reservoir Filling:",
        f"{system_filling:.3f}%"
    )

    if replaced:
        print("Κατάσταση: ενημερώθηκε υπάρχουσα ημέρα.")
    else:
        print("Κατάσταση: προστέθηκε νέα ημέρα.")


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 60)
    print("HYDRO UPDATE")
    print("=" * 60)

    target_date = get_target_date()

    print()
    print("Επεξεργασία:", target_date)
    print("=" * 60)

    # --------------------------------------------------------
    # 1. Ask ADMIE for the real file URL.
    # --------------------------------------------------------

    print()
    print("Βήμα 1: Εύρεση Reservoir μέσω ADMIE API...")

    try:

        file_url = find_reservoir_file(
            target_date
        )

    except Exception as exc:

        print(
            "Σφάλμα ADMIE API:",
            exc,
        )

        return 1

    if not file_url:

        print(
            "Reservoir: δεν βρέθηκε αρχείο για",
            target_date,
        )

        return 0

    # --------------------------------------------------------
    # 2. Download actual file.
    # --------------------------------------------------------

    temp_file = None

    try:

        print()
        print("Βήμα 2: Λήψη Reservoir...")

        temp_file = download_file(
            file_url
        )

        # ----------------------------------------------------
        # 3. Parse Excel.
        # ----------------------------------------------------

        print()
        print("Βήμα 3: Ανάλυση Reservoir...")

        reservoirs = process_reservoir_file(
            temp_file
        )

        # ----------------------------------------------------
        # 4. Update hydro_data.json.
        # ----------------------------------------------------

        print()
        print("Βήμα 4: Ενημέρωση hydro_data.json...")

        update_json(
            target_date,
            reservoirs,
        )

        print()
        print("=" * 60)
        print("HYDRO UPDATE ΟΛΟΚΛΗΡΩΘΗΚΕ ΕΠΙΤΥΧΩΣ")
        print("=" * 60)

        return 0

    except Exception as exc:

        print()
        print("=" * 60)
        print("ΣΦΑΛΜΑ HYDRO UPDATE")
        print("=" * 60)
        print(exc)

        return 1

    finally:

        if temp_file and os.path.exists(temp_file):

            try:
                os.remove(temp_file)
            except Exception:
                pass


if __name__ == "__main__":
    sys.exit(main())
