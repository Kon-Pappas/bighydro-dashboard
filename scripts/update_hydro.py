import io
import json
import os
from datetime import datetime, timedelta

import pandas as pd
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==============================================================================
# ΡΥΘΜΙΣΕΙΣ & ΧΑΡΤΟΓΡΑΦΗΣΗ
# ==============================================================================
DATA_DIR = "data"
OUTPUT_FILE = os.path.join(DATA_DIR, "hydro_data.json")

HYDRO_UNITS = [
    "AGRAS", "ASOMATA", "EDESSAIOS", "ILARIONAS", "KASTRAKI",
    "KREMASTA", "LADONAS", "PLASTIRAS", "PLATANOVRYSI", "POLYFYTO",
    "POURNARI 1", "POURNARI 2", "P. AOOU", "SFIKIA", "STRATOS 1", "THESAVROS"
]

RESERVOIR_MAPPING = {
    "AGRAS": "Agras",
    "ASOMATA": "Asomata",
    "EDESSAIOS": "Edessaios",
    "ILARIONAS": "Ilarionas",
    "KASTRAKI": "Kastraki",
    "KREMASTA": "Kremasta",
    "LADONAS": "Ladonas",
    "PLASTIRAS": "Plastiras",
    "PLATANOVRYSI": "Platanovrysi",
    "POLYFYTO": "Polyfyto",
    "POURNARI1": "Pournari1",
    "POYRNARI1": "Pournari1",
    "POURNARI2": "Pournari2",
    "POYRNARI2": "Pournari2",
    "PAOOU": "PAoou",
    "P_AOOU": "PAoou",
    "SFIKIA": "Sfikia",
    "STRATOS": "Stratos1",
    "STRATOS1": "Stratos1",
    "THESAVROS": "Thesavros",
    "THESAVROS1": "Thesavros",
    "THESAVROS2": "Thesavros",
    "THESAVROS3": "Thesavros",
}


def normalize_name(value):
    """Καθαρίζει ένα όνομα για ασφαλή αντιστοίχιση."""
    if value is None or pd.isna(value):
        return ""

    text = str(value).strip().upper()

    for char in (" ", ".", "-", "_", "/"):
        text = text.replace(char, "")

    return text


NORMALIZED_RESERVOIR_MAPPING = {
    normalize_name(key): value
    for key, value in RESERVOIR_MAPPING.items()
}


# ==============================================================================
# ΒΟΗΘΗΤΙΚΗ ΣΥΝΑΡΤΗΣΗ ΛΗΨΗΣ ΑΡΧΕΙΩΝ
# ==============================================================================
def download_excel(url):
    """Κατεβάζει ένα αρχείο Excel από URL και επιστρέφει τα bytes."""
    try:
        response = requests.get(
            url,
            verify=False,
            timeout=30
        )

        response.raise_for_status()
        return response.content

    except Exception as exc:
        print(f"Σφάλμα λήψης {url}: {exc}")
        return None


# ==============================================================================
# ΑΝΑΛΥΣΗ ΑΡΧΕΙΟΥ RESERVOIR
# ==============================================================================
def process_reservoir_file(date_str):
    """
    Κατεβάζει και αναλύει το ReservoirFillingRate.

    Επιστρέφει:

    {
        "Total": 45.27,
        "Units": {
            "Kremasta": 43.87,
            "Kastraki": 108.54,
            ...
        }
    }
    """

    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    date_format_url = date_obj.strftime("%Y%m%d")

    url = (
        f"https://admie.gr/get-file/"
        f"{date_format_url}_ReservoirFillingRate_01.xls"
    )

    file_content = download_excel(url)

    if not file_content:
        return None

    try:
        # Διαβάζουμε απευθείας από memory.
        df = pd.read_excel(
            io.BytesIO(file_content),
            sheet_name=0,
            header=None
        )

        if df.empty:
            print(f"  Reservoir {date_str}: κενό αρχείο.")
            return None

        # ------------------------------------------------------------------
        # ΕΝΤΟΠΙΣΜΟΣ ΣΤΗΛΩΝ ENTITY / FILLING RATE
        # ------------------------------------------------------------------
        entity_col = None
        rate_col = None

        for r in range(min(len(df), 20)):

            for c in range(df.shape[1]):

                cell = normalize_name(df.iat[r, c])

                if cell == "ENTITY":
                    entity_col = c

                if (
                    "FILLINGRATE" in cell
                    or "FILLING" in cell
                    or "RATE" in cell
                ):
                    if "TOTAL" not in cell and rate_col is None:
                        rate_col = c

            if entity_col is not None and rate_col is not None:
                break

        # Fallback στην γνωστή διάταξη του ADMIE Excel.
        if entity_col is None and df.shape[1] > 1:
            entity_col = 1

        if rate_col is None and df.shape[1] > 2:
            rate_col = 2

        if entity_col is None or rate_col is None:

            print(
                f"  Reservoir {date_str}: "
                f"δεν εντοπίστηκαν οι στήλες Entity/Filling Rate."
            )

            return None

        # ------------------------------------------------------------------
        # ΕΞΑΓΩΓΗ ΠΟΣΟΣΤΩΝ ΑΝΑ ΤΑΜΙΕΥΤΗΡΑ
        # ------------------------------------------------------------------
        mapped_values = {}

        for row_idx in range(len(df)):

            raw_entity = df.iat[row_idx, entity_col]
            entity_norm = normalize_name(raw_entity)

            if not entity_norm or entity_norm == "ENTITY":
                continue

            clean_id = NORMALIZED_RESERVOIR_MAPPING.get(entity_norm)

            if clean_id is None:
                continue

            raw_rate = df.iat[row_idx, rate_col]

            try:
                rate = float(raw_rate)
            except (TypeError, ValueError):
                continue

            mapped_values.setdefault(clean_id, []).append(rate)

        # Σε THESAVROS1/2/3 κρατάμε τον μέσο όρο.
        clean_rates = {
            reservoir_id: round(
                sum(values) / len(values),
                4
            )
            for reservoir_id, values in mapped_values.items()
            if values
        }

        # ------------------------------------------------------------------
        # ΕΞΑΓΩΓΗ ΣΥΝΟΛΙΚΟΥ ΠΟΣΟΣΤΟΥ
        # ------------------------------------------------------------------
        total_val = None

        for row_idx in range(len(df)):

            total_columns = []

            for col_idx in range(df.shape[1]):

                cell = str(
                    df.iat[row_idx, col_idx]
                ).strip().upper()

                if "TOTAL" in cell:
                    total_columns.append(col_idx)

            if not total_columns:
                continue

            # Στο γνωστό ADMIE format το total βρίσκεται στη στήλη 10.
            candidate_columns = []

            if df.shape[1] > 10:
                candidate_columns.append(10)

            # Fallback: ψάχνουμε αριθμητικές τιμές από δεξιά προς τα αριστερά.
            candidate_columns.extend(
                c
                for c in range(df.shape[1] - 1, -1, -1)
                if c not in candidate_columns
            )

            for c in candidate_columns:

                value = df.iat[row_idx, c]

                try:
                    numeric_value = float(value)
                except (TypeError, ValueError):
                    continue

                if 0 <= numeric_value <= 150:

                    total_val = round(
                        numeric_value,
                        4
                    )

                    break

            if total_val is not None:
                break

        # Αν δεν βρέθηκε τίποτα, το αρχείο δεν μας χρησιμεύει.
        if not clean_rates and total_val is None:

            print(
                f"  Reservoir {date_str}: "
                f"δεν βρέθηκαν αναγνωρισμένοι ταμιευτήρες."
            )

            return None

        print(
            f"  Reservoir {date_str}: "
            f"{len(clean_rates)} reservoirs"
            +
            (
                f", total={total_val:.2f}%"
                if total_val is not None
                else ", total=N/A"
            )
        )

        return {
            "Total": total_val,
            "Units": clean_rates
        }

    except Exception as exc:

        print(
            f"Σφάλμα στην επεξεργασία του Reservoir "
            f"για {date_str}: {exc}"
        )

        return None


# ==============================================================================
# ΑΝΑΛΥΣΗ ΑΡΧΕΙΟΥ ΠΑΡΑΓΩΓΗΣ
# ==============================================================================
def process_realization_file(date_str):
    """Κατεβάζει και αναλύει το αρχείο SystemRealization."""

    date_obj = datetime.strptime(
        date_str,
        "%Y-%m-%d"
    )

    date_format_url = date_obj.strftime("%Y%m%d")

    url = (
        f"https://admie.gr/get-file/"
        f"{date_format_url}_SystemRealization_01.xls"
    )

    file_content = download_excel(url)

    if not file_content:
        return None

    try:

        df = pd.read_excel(
            io.BytesIO(file_content),
            sheet_name=0,
            header=None
        )

        hourly_data = {
            hour: {}
            for hour in range(1, 25)
        }

        # Εντοπισμός μονάδων και Data Type.
        unit_columns = {}

        for col_idx in range(df.shape[1]):

            unit_name = str(
                df.iloc[2, col_idx]
            ).strip()

            data_type = str(
                df.iloc[3, col_idx]
            ).strip()

            if unit_name in HYDRO_UNITS:

                clean_id = (
                    unit_name
                    .replace(" ", "")
                    .replace(".", "")
                )

                key = f"{data_type}_{clean_id}"

                unit_columns[key] = col_idx

        if not unit_columns:

            print(
                f"  Παραγωγή {date_str}: "
                f"δεν βρέθηκαν υδροηλεκτρικές μονάδες."
            )

            return None

        # Ώρες 1-24.
        for hour in range(1, 25):

            row_idx = hour + 3

            if row_idx >= len(df):
                continue

            for key, col_idx in unit_columns.items():

                value = df.iloc[row_idx, col_idx]

                try:

                    hourly_data[hour][key] = (
                        float(value)
                        if pd.notna(value)
                        else 0.0
                    )

                except (TypeError, ValueError):

                    hourly_data[hour][key] = 0.0

        return [
            {
                "Hour": hour,
                **hourly_data[hour]
            }
            for hour in range(1, 25)
        ]

    except Exception as exc:

        print(
            f"Σφάλμα στην επεξεργασία της Παραγωγής "
            f"για {date_str}: {exc}"
        )

        return None


# ==============================================================================
# ΚΥΡΙΟ SCRIPT
# ==============================================================================
def main():

    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

    # ------------------------------------------------------------------
    # ΦΟΡΤΩΣΗ ΥΠΑΡΧΟΝΤΩΝ ΔΕΔΟΜΕΝΩΝ
    # ------------------------------------------------------------------
    all_data = []

    if os.path.exists(OUTPUT_FILE):

        try:

            with open(
                OUTPUT_FILE,
                "r",
                encoding="utf-8"
            ) as file:

                all_data = json.load(file)

        except Exception as exc:

            print(
                f"Σφάλμα ανάγνωσης του "
                f"{OUTPUT_FILE}: {exc}"
            )

            all_data = []

    data_by_date = {
        item.get("Date"): item
        for item in all_data
        if isinstance(item, dict)
        and item.get("Date")
    }

    # ------------------------------------------------------------------
    # ΗΜΕΡΟΜΗΝΙΕΣ
    #
    # Αν δοθούν START_DATE / END_DATE από GitHub Actions,
    # κάνουμε backfill ακριβώς αυτού του διαστήματος.
    #
    # Αλλιώς χρησιμοποιούμε τις τελευταίες 7 ημέρες.
    # ------------------------------------------------------------------
    start_env = os.getenv(
        "START_DATE",
        ""
    ).strip()

    end_env = os.getenv(
        "END_DATE",
        ""
    ).strip()

    if start_env or end_env:

        try:

            start_date = datetime.strptime(
                start_env or end_env,
                "%Y-%m-%d"
            )

            end_date = datetime.strptime(
                end_env or start_env,
                "%Y-%m-%d"
            )

            if start_date > end_date:
                start_date, end_date = (
                    end_date,
                    start_date
                )

            dates_to_check = [
                (
                    start_date
                    + timedelta(days=i)
                ).strftime("%Y-%m-%d")
                for i in range(
                    (end_date - start_date).days + 1
                )
            ]

            print(
                f"\nManual date range: "
                f"{dates_to_check[0]} -> "
                f"{dates_to_check[-1]}"
            )

        except ValueError:

            print(
                "Μη έγκυρο START_DATE/END_DATE. "
                "Χρησιμοποιούνται οι τελευταίες 7 ημέρες."
            )

            today = datetime.now()

            dates_to_check = [
                (
                    today
                    - timedelta(days=i)
                ).strftime("%Y-%m-%d")
                for i in range(7)
            ]

    else:

        today = datetime.now()

        dates_to_check = [
            (
                today
                - timedelta(days=i)
            ).strftime("%Y-%m-%d")
            for i in range(7)
        ]

    updates_made = False

    # ------------------------------------------------------------------
    # ΕΠΕΞΕΡΓΑΣΙΑ ΗΜΕΡΩΝ
    # ------------------------------------------------------------------
    for date_str in dates_to_check:

        print(
            f"\nΕπεξεργασία: {date_str}"
        )

        day_entry = data_by_date.get(
            date_str
        )

        if day_entry is None:

            day_entry = {
                "Date": date_str
            }

            data_by_date[date_str] = day_entry

        # --------------------------------------------------------------
        # 1. ΠΑΡΑΓΩΓΗ
        #
        # Αν υπάρχει ήδη Hourly, δεν το ξανακατεβάζουμε.
        # --------------------------------------------------------------
        if not day_entry.get("Hourly"):

            prod_data = process_realization_file(
                date_str
            )

            if prod_data:

                day_entry["Hourly"] = prod_data

                updates_made = True

                print(
                    "  Παραγωγή: OK"
                )

            else:

                print(
                    "  Παραγωγή: "
                    "δεν βρέθηκαν δεδομένα."
                )

        else:

            print(
                "  Παραγωγή: υπάρχει ήδη, "
                "δεν ξανακατεβαίνει."
            )

        # --------------------------------------------------------------
        # 2. RESERVOIR
        #
        # ΠΑΝΤΑ ζητάμε το Reservoir.
        #
        # Αυτό είναι το βασικό fix:
        # ακόμα κι αν η ημερομηνία υπάρχει ήδη,
        # ενημερώνουμε το Reservoir.Units.
        # --------------------------------------------------------------
        res_data = process_reservoir_file(
            date_str
        )

        if res_data:

            old_reservoir = day_entry.get(
                "Reservoir"
            )

            if old_reservoir != res_data:

                day_entry["Reservoir"] = res_data

                updates_made = True

            # Κρατάμε το παλιό flat πεδίο
            # για backward compatibility.
            if res_data.get("Total") is not None:

                old_total = day_entry.get(
                    "ReservoirTotalRate"
                )

                new_total = res_data["Total"]

                if old_total != new_total:

                    day_entry[
                        "ReservoirTotalRate"
                    ] = new_total

                    updates_made = True

        else:

            # Αν το ADMIE αρχείο δεν είναι διαθέσιμο,
            # δεν σβήνουμε υπάρχοντα δεδομένα.
            if day_entry.get("Reservoir"):

                print(
                    "  Reservoir: κρατάμε "
                    "το ήδη αποθηκευμένο data."
                )

            elif day_entry.get(
                "ReservoirTotalRate"
            ) is not None:

                print(
                    "  Reservoir: υπάρχει μόνο "
                    "legacy TotalRate."
                )

    # ------------------------------------------------------------------
    # ΑΠΟΘΗΚΕΥΣΗ
    # ------------------------------------------------------------------
    final_data = sorted(
        data_by_date.values(),
        key=lambda item: item.get(
            "Date",
            ""
        ),
        reverse=True
    )

    if updates_made:

        with open(
            OUTPUT_FILE,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                final_data,
                file,
                indent=2,
                ensure_ascii=False
            )

        print(
            f"\nΤο {OUTPUT_FILE} "
            f"ενημερώθηκε επιτυχώς!"
        )

    else:

        print(
            "\nΔεν υπήρχαν νέες αλλαγές."
        )


if __name__ == "__main__":
    main()