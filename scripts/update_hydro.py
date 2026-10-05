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

API_FILES = BASE_URL + "/getOperationMarketFile"

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
        "Accept": "*/*",
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
# DATE RANGE
# ============================================================

def parse_date(value, variable_name):

    try:

        return datetime.strptime(
            value,
            "%Y-%m-%d"
        ).date()

    except ValueError:

        raise ValueError(
            f"{variable_name}='{value}' "
            "δεν είναι έγκυρη ημερομηνία. "
            "Χρησιμοποίησε YYYY-MM-DD."
        )


def get_date_range():

    # --------------------------------------------------------
    # GitHub Actions:
    #
    # START_DATE
    # END_DATE
    # --------------------------------------------------------

    start_value = os.environ.get("START_DATE")
    end_value = os.environ.get("END_DATE")

    # --------------------------------------------------------
    # Αν δόθηκε command-line argument:
    #
    # python scripts/update_hydro.py 2026-09-21
    #
    # τότε επεξεργαζόμαστε μόνο αυτή την ημέρα.
    # --------------------------------------------------------

    if len(sys.argv) > 1:

        start_date = parse_date(
            sys.argv[1],
            "DATE"
        )

        if len(sys.argv) > 2:

            end_date = parse_date(
                sys.argv[2],
                "END_DATE"
            )

        else:

            end_date = start_date

        return start_date, end_date

    # --------------------------------------------------------
    # GitHub Actions manual run
    # --------------------------------------------------------

    if start_value:

        start_date = parse_date(
            start_value,
            "START_DATE"
        )

        if end_value:

            end_date = parse_date(
                end_value,
                "END_DATE"
            )

        else:

            end_date = start_date

        return start_date, end_date

    # --------------------------------------------------------
    # Default:
    # σήμερα
    # --------------------------------------------------------

    today = datetime.now().date()

    return today, today


# ============================================================
# FIND ADMIE FILE
# ============================================================

def find_reservoir_file(target_date):

    date_string = target_date.strftime(
        "%Y-%m-%d"
    )

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

    print(
        "API response type:",
        type(data).__name__
    )

    if not data:
        return None

    if not isinstance(data, list):

        print(
            "Μη αναμενόμενη μορφή απάντησης ADMIE."
        )

        print(str(data)[:2000])

        return None

    candidates = []

    for item in data:

        if not isinstance(item, dict):
            continue

        file_path = item.get("file_path")

        if not file_path:
            continue

        candidates.append(item)

    if not candidates:

        print(
            "Το ADMIE API δεν επέστρεψε αρχείο."
        )

        print(str(data)[:2000])

        return None

    # --------------------------------------------------------
    # Επιλογή ακριβούς ημερομηνίας
    # --------------------------------------------------------

    target_date_text = target_date.strftime(
        "%d.%m.%Y"
    )

    dated_candidates = [
        item
        for item in candidates
        if (
            item.get("file_fromdate") == target_date_text
            and
            item.get("file_todate") == target_date_text
        )
    ]

    if dated_candidates:

        selected = dated_candidates[0]

    else:

        print(
            "ΠΡΟΣΟΧΗ: δεν βρέθηκε αρχείο "
            "με ακριβή ημερομηνία."
        )

        selected = candidates[0]

    file_url = selected["file_path"]

    print()
    print("Βρέθηκε αρχείο ADMIE:")
    print(
        "Description:",
        selected.get("file_description")
    )
    print(
        "From:",
        selected.get("file_fromdate")
    )
    print(
        "To:",
        selected.get("file_todate")
    )
    print(
        "Published:",
        selected.get("file_published")
    )
    print(
        "URL:",
        file_url
    )

    return file_url


# ============================================================
# DOWNLOAD FILE
# ============================================================

def download_file(url):

    print()
    print("Λήψη:")
    print(url)

    response = session.get(
        url,
        timeout=TIMEOUT,
        allow_redirects=True,
    )

    response.raise_for_status()

    if not response.content:

        raise RuntimeError(
            "Το αρχείο ADMIE είναι κενό."
        )

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

    print(
        "Content-Type:",
        response.headers.get(
            "Content-Type",
            ""
        )
    )

    return temp.name


# ============================================================
# NORMALIZE RESERVOIR NAME
# ============================================================

def normalize_name(value):

    if value is None:
        return ""

    text = str(value).strip().upper()

    # THESAVROS1 / THESAVROS2 / THESAVROS3
    # αντιστοιχούν στον ίδιο ταμιευτήρα.
    if text.startswith("THESAVROS"):
        return "THESAVROS"

    return text


# ============================================================
# PARSE RESERVOIR EXCEL
# ============================================================

def process_reservoir_file(file_path):

    print()
    print("Άνοιγμα Reservoir Excel...")

    df = pd.read_excel(
        file_path,
        sheet_name=0,
        header=None,
    )

    print(
        "Excel shape:",
        df.shape
    )

    reservoirs = {}

    for _, row in df.iterrows():

        if len(row) < 3:
            continue

        entity = normalize_name(
            row.iloc[1]
        )

        if entity not in RESERVOIRS:
            continue

        raw_rate = row.iloc[2]

        try:

            raw_rate = float(raw_rate)

        except (
            TypeError,
            ValueError
        ):

            continue

        # ADMIE:
        #
        # 0.7196 = 71.96%
        #

        rate_percent = raw_rate * 100.0

        reservoirs[entity] = round(
            rate_percent,
            2
        )

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
        print(
            "ΠΡΟΣΟΧΗ: λείπουν reservoirs:"
        )

        for name in missing:

            print(
                " -",
                name
            )

    print()
    print(
        "Reservoirs που βρέθηκαν:",
        len(reservoirs),
        "/",
        len(RESERVOIRS)
    )

    for name in RESERVOIRS:

        if name in reservoirs:

            print(
                f"  {name:<15}"
                f"{reservoirs[name]:>7.2f}%"
            )

    if len(reservoirs) == 0:

        raise RuntimeError(
            "Δεν βρέθηκε κανένα reservoir "
            "στο Excel."
        )

    return reservoirs


# ============================================================
# LOAD EXISTING JSON
# ============================================================

def load_existing_data():

    if not os.path.exists(
        OUTPUT_FILE
    ):

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
            "Προειδοποίηση: δεν ήταν δυνατή "
            "η ανάγνωση του υπάρχοντος "
            "hydro_data.json:",
            exc,
        )

        return []


# ============================================================
# UPDATE JSON
# ============================================================

def update_json(
    target_date,
    reservoirs
):

    os.makedirs(
        os.path.dirname(OUTPUT_FILE),
        exist_ok=True,
    )

    data = load_existing_data()

    date_string = target_date.strftime(
        "%Y-%m-%d"
    )

    # --------------------------------------------------------
    # Arithmetic mean of the 14 published percentages.
    #
    # ΠΡΟΣΟΧΗ:
    # Αυτό ΔΕΝ είναι το official ADMIE Total.
    # --------------------------------------------------------

    system_filling = (
        sum(reservoirs.values())
        /
        len(reservoirs)
    )

    system_filling = round(
        system_filling,
        3
    )

    # --------------------------------------------------------
    # Update existing record or create new one.
    # --------------------------------------------------------

    replaced = False

    for i, record in enumerate(data):

        if str(
            record.get("Date", "")
        ) == date_string:

            updated = dict(record)

            updated["Reservoir"] = reservoirs

            updated["ReservoirTotal"] = (
                system_filling
            )

            data[i] = updated

            replaced = True

            break

    if not replaced:

        new_record = {
            "Date": date_string,
            "Reservoir": reservoirs,
            "ReservoirTotal": system_filling,
        }

        data.append(new_record)

    # --------------------------------------------------------
    # Newest first.
    # --------------------------------------------------------

    data.sort(
        key=lambda x: str(
            x.get("Date", "")
        ),
        reverse=True,
    )

    # --------------------------------------------------------
    # Write JSON.
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
    print(
        "hydro_data.json ενημερώθηκε."
    )

    print(
        "Ημερομηνία:",
        date_string
    )

    print(
        "System Reservoir Filling:",
        f"{system_filling:.3f}%"
    )

    if replaced:

        print(
            "Κατάσταση: "
            "ενημερώθηκε υπάρχουσα ημέρα."
        )

    else:

        print(
            "Κατάσταση: "
            "προστέθηκε νέα ημέρα."
        )


# ============================================================
# PROCESS ONE DAY
# ============================================================

def process_one_day(target_date):

    print()
    print("=" * 60)
    print(
        "Επεξεργασία:",
        target_date
    )
    print("=" * 60)

    # --------------------------------------------------------
    # 1. Find actual ADMIE file.
    # --------------------------------------------------------

    print()
    print(
        "Βήμα 1: "
        "Εύρεση Reservoir μέσω ADMIE API..."
    )

    try:

        file_url = find_reservoir_file(
            target_date
        )

    except Exception as exc:

        print()
        print(
            "Σφάλμα ADMIE API:",
            exc
        )

        return False

    if not file_url:

        print(
            "Reservoir: δεν βρέθηκε αρχείο για",
            target_date
        )

        return False

    # --------------------------------------------------------
    # 2. Download.
    # --------------------------------------------------------

    temp_file = None

    try:

        print()
        print(
            "Βήμα 2: Λήψη Reservoir..."
        )

        temp_file = download_file(
            file_url
        )

        # ----------------------------------------------------
        # 3. Parse.
        # ----------------------------------------------------

        print()
        print(
            "Βήμα 3: Ανάλυση Reservoir..."
        )

        reservoirs = process_reservoir_file(
            temp_file
        )

        # ----------------------------------------------------
        # 4. JSON.
        # ----------------------------------------------------

        print()
        print(
            "Βήμα 4: Ενημέρωση "
            "hydro_data.json..."
        )

        update_json(
            target_date,
            reservoirs
        )

        print()
        print(
            "Ημέρα ολοκληρώθηκε επιτυχώς:",
            target_date
        )

        return True

    except Exception as exc:

        print()
        print(
            "ΣΦΑΛΜΑ για",
            target_date
        )

        print(
            type(exc).__name__,
            ":",
            exc
        )

        return False

    finally:

        if (
            temp_file
            and
            os.path.exists(temp_file)
        ):

            try:

                os.remove(temp_file)

            except Exception:

                pass


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 60)
    print("HYDRO UPDATE")
    print("=" * 60)

    try:

        start_date, end_date = get_date_range()

    except ValueError as exc:

        print()
        print(
            "Σφάλμα ημερομηνίας:",
            exc
        )

        return 1

    print()
    print(
        "START_DATE:",
        start_date
    )

    print(
        "END_DATE:",
        end_date
    )

    if end_date < start_date:

        print()
        print(
            "ΣΦΑΛΜΑ: END_DATE είναι "
            "πριν από START_DATE."
        )

        return 1

    total_days = (
        end_date - start_date
    ).days + 1

    print()
    print(
        "Ημέρες προς επεξεργασία:",
        total_days
    )

    # --------------------------------------------------------
    # Process each date independently.
    # --------------------------------------------------------

    current_date = start_date

    successful = 0
    failed = 0

    while current_date <= end_date:

        if process_one_day(current_date):

            successful += 1

        else:

            failed += 1

        current_date += timedelta(
            days=1
        )

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print("BACKFILL SUMMARY")
    print("=" * 60)

    print(
        "Από:",
        start_date
    )

    print(
        "Έως:",
        end_date
    )

    print(
        "Σύνολο ημερών:",
        total_days
    )

    print(
        "Επιτυχίες:",
        successful
    )

    print(
        "Αποτυχίες:",
        failed
    )

    if failed > 0:

        print()
        print(
            "HYDRO UPDATE ΟΛΟΚΛΗΡΩΘΗΚΕ "
            "ΜΕ ΑΠΟΤΥΧΙΕΣ ΣΕ ΚΑΠΟΙΕΣ ΗΜΕΡΕΣ."
        )

        return 1

    print()
    print(
        "HYDRO UPDATE "
        "ΟΛΕΣ ΟΙ ΗΜΕΡΕΣ ΟΛΟΚΛΗΡΩΘΗΚΑΝ ΕΠΙΤΥΧΩΣ"
    )

    return 0


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    sys.exit(
        main()
    )
