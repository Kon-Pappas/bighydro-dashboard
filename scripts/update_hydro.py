import pandas as pd
import json
import os
import requests
from datetime import datetime, timedelta
import urllib3
import traceback

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==============================================================================
# ΡΥΘΜΙΣΕΙΣ & ΧΑΡΤΟΓΡΑΦΗΣΗ
# ==============================================================================

DATA_DIR = "data"
OUTPUT_FILE = os.path.join(DATA_DIR, "hydro_data.json")


# Ονόματα Μονάδων όπως εμφανίζονται στα αρχεία παραγωγής (Realization)
HYDRO_UNITS = [
    "AGRAS",
    "ASOMATA",
    "EDESSAIOS",
    "ILARIONAS",
    "KASTRAKI",
    "KREMASTA",
    "LADONAS",
    "PLASTIRAS",
    "PLATANOVRYSI",
    "POLYFYTO",
    "POURNARI 1",
    "POURNARI 2",
    "P. AOOU",
    "SFIKIA",
    "STRATOS 1",
    "THESAVROS"
]


# ==============================================================================
# ΑΝΤΙΣΤΟΙΧΙΣΗ RESERVOIR
# ==============================================================================

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

    # ADMIE χρησιμοποιεί POYRNARI
    "POYRNARI1": "Pournari1",
    "POYRNARI2": "Pournari2",

    "P_AOOU": "PAoou",

    "SFIKIA": "Sfikia",

    # Το STRATOS εμφανίζεται ως ένα reservoir
    "STRATOS": "Stratos1",

    # THESAVROS 1/2/3 είναι ο ίδιος ταμιευτήρας
    "THESAVROS1": "Thesavros",
    "THESAVROS2": "Thesavros",
    "THESAVROS3": "Thesavros"
}


# ==============================================================================
# ΒΟΗΘΗΤΙΚΕΣ ΣΥΝΑΡΤΗΣΕΙΣ
# ==============================================================================

def download_excel(url):
    """Κατεβάζει ένα αρχείο Excel από ADMIE."""

    try:

        response = requests.get(
            url,
            verify=False,
            timeout=30
        )

        response.raise_for_status()

        return response.content

    except Exception as e:

        print(
            f"Σφάλμα λήψης {url}: {e}"
        )

        return None


# ==============================================================================
# RESERVOIR FILLING RATE
# ==============================================================================

def process_reservoir_file(date_str):

    """
    Διαβάζει το ADMIE ReservoirFillingRate.

    Το πραγματικό format του ADMIE είναι:

        column 1 -> Entity
        column 2 -> Filling Rate
        column 7 -> "Filling Rate (%) Total"
        column 10 -> Total

    Οι τιμές του ADMIE είναι fractions:

        0.7196 -> 71.96%
        0.43623 -> 43.623%

    Επιστρέφει:

    {
        "Total": 43.623,
        "Units": {
            "Asomata": 71.96,
            "Ilarionas": 15.38,
            ...
        }
    }
    """

    date_obj = datetime.strptime(
        date_str,
        "%Y-%m-%d"
    )

    date_format_url = date_obj.strftime(
        "%Y%m%d"
    )

    url = (
        f"https://admie.gr/get-file/"
        f"{date_format_url}_ReservoirFillingRate_01.xls"
    )

    file_content = download_excel(url)

    if not file_content:
        return None

    temp_file = f"temp_res_{date_format_url}.xls"

    try:

        # --------------------------------------------------------------
        # Αποθήκευση προσωρινού αρχείου
        # --------------------------------------------------------------

        with open(
            temp_file,
            "wb"
        ) as f:

            f.write(file_content)


        # --------------------------------------------------------------
        # ΠΟΛΥ ΣΗΜΑΝΤΙΚΟ:
        #
        # header=None
        #
        # Το ADMIE Excel ΔΕΝ έχει την πραγματική header row
        # στην πρώτη γραμμή.
        # --------------------------------------------------------------

        df = pd.read_excel(
            temp_file,
            sheet_name=0,
            header=None
        )


        # --------------------------------------------------------------
        # 1. TOTAL
        # --------------------------------------------------------------

        total_val = None

        for index, row in df.iterrows():

            if len(row) <= 10:
                continue

            label = row.iloc[7]

            if (
                pd.notna(label)
                and "Total" in str(label)
            ):

                try:

                    raw_total = float(
                        row.iloc[10]
                    )

                    # ADMIE δίνει fraction.
                    # 0.43623 -> 43.623%
                    total_val = round(
                        raw_total * 100,
                        4
                    )

                except (
                    TypeError,
                    ValueError
                ):

                    pass

                break


        # --------------------------------------------------------------
        # 2. INDIVIDUAL RESERVOIRS
        # --------------------------------------------------------------

        raw_rates = {}

        for index, row in df.iterrows():

            if len(row) <= 2:
                continue

            entity_value = row.iloc[1]
            rate_value = row.iloc[2]

            if pd.isna(entity_value):
                continue

            entity = str(
                entity_value
            ).strip().upper()

            # Skip headers / empty rows
            if entity in (
                "",
                "NAN",
                "ENTITY"
            ):
                continue

            try:

                raw_rate = float(
                    rate_value
                )

            except (
                TypeError,
                ValueError
            ):

                continue

            # ADMIE fraction -> percentage
            rate_percent = round(
                raw_rate * 100,
                4
            )

            raw_rates[entity] = rate_percent


        # --------------------------------------------------------------
        # 3. MAPPING
        # --------------------------------------------------------------

        clean_rates = {}

        for raw_name, rate in raw_rates.items():

            if raw_name in RESERVOIR_MAPPING:

                clean_id = RESERVOIR_MAPPING[
                    raw_name
                ]

                # THESAVROS1/2/3 έχουν ίδια τιμή.
                # Το setdefault μας προστατεύει από
                # τυχόν διπλοεγγραφή.
                if clean_id not in clean_rates:

                    clean_rates[
                        clean_id
                    ] = rate


        # --------------------------------------------------------------
        # 4. ΕΛΕΓΧΟΣ
        # --------------------------------------------------------------

        print(
            f"  Reservoir {date_str}: "
            f"{len(clean_rates)} μονάδες"
        )

        if total_val is not None:

            print(
                f"  Total filling: "
                f"{total_val:.2f}%"
            )

        if clean_rates:

            for reservoir, rate in clean_rates.items():

                print(
                    f"    {reservoir}: "
                    f"{rate:.2f}%"
                )

        else:

            print(
                "  ΠΡΟΣΟΧΗ: Δεν βρέθηκαν "
                "individual reservoirs!"
            )


        # --------------------------------------------------------------
        # 5. RETURN
        # --------------------------------------------------------------

        return {
            "Total": total_val,
            "Units": clean_rates
        }


    except Exception as e:

        print(
            f"Σφάλμα στην επεξεργασία "
            f"του Reservoir για {date_str}: {e}"
        )

        traceback.print_exc()

        return None


    finally:

        # Καθαρισμός temporary file
        if os.path.exists(temp_file):

            try:
                os.remove(temp_file)
            except Exception:
                pass


# ==============================================================================
# SYSTEM REALIZATION
# ==============================================================================

def process_realization_file(date_str):

    """Κατεβάζει και αναλύει το SystemRealization."""

    date_obj = datetime.strptime(
        date_str,
        "%Y-%m-%d"
    )

    date_format_url = date_obj.strftime(
        "%Y%m%d"
    )

    url = (
        f"https://admie.gr/get-file/"
        f"{date_format_url}_SystemRealization_01.xls"
    )

    file_content = download_excel(url)

    if not file_content:
        return None

    temp_file = f"temp_prod_{date_format_url}.xls"

    try:

        with open(
            temp_file,
            "wb"
        ) as f:

            f.write(file_content)


        df = pd.read_excel(
            temp_file,
            sheet_name=0,
            header=None
        )

        hourly_data = {
            hour: {}
            for hour in range(1, 25)
        }


        # --------------------------------------------------------------
        # Εντοπισμός μονάδων και Data Type
        # --------------------------------------------------------------

        unit_columns = {}

        for col_idx in range(
            df.shape[1]
        ):

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

                key = (
                    f"{data_type}_{clean_id}"
                )

                unit_columns[
                    key
                ] = col_idx


        if not unit_columns:

            print(
                f"Δεν βρέθηκαν "
                f"hydro units για {date_str}"
            )

            return None


        # --------------------------------------------------------------
        # Ώρες 1-24
        # --------------------------------------------------------------

        for hour in range(
            1,
            25
        ):

            row_idx = hour + 3

            if row_idx >= len(df):
                continue

            for key, col_idx in unit_columns.items():

                value = df.iloc[
                    row_idx,
                    col_idx
                ]

                try:

                    hourly_data[
                        hour
                    ][key] = (
                        float(value)
                        if pd.notna(value)
                        else 0.0
                    )

                except (
                    TypeError,
                    ValueError
                ):

                    hourly_data[
                        hour
                    ][key] = 0.0


        # --------------------------------------------------------------
        # Λίστα
        # --------------------------------------------------------------

        hourly_list = []

        for hour in range(
            1,
            25
        ):

            entry = {
                "Hour": hour
            }

            entry.update(
                hourly_data[hour]
            )

            hourly_list.append(
                entry
            )


        return hourly_list


    except Exception as e:

        print(
            f"Σφάλμα στην επεξεργασία "
            f"της Παραγωγής για {date_str}: {e}"
        )

        traceback.print_exc()

        return None


    finally:

        if os.path.exists(temp_file):

            try:
                os.remove(temp_file)
            except Exception:
                pass


# ==============================================================================
# MAIN
# ==============================================================================

def main():

    if not os.path.exists(
        DATA_DIR
    ):

        os.makedirs(
            DATA_DIR
        )


    # ------------------------------------------------------------------
    # Φόρτωση υπάρχοντος JSON
    # ------------------------------------------------------------------

    all_data = []

    if os.path.exists(
        OUTPUT_FILE
    ):

        try:

            with open(
                OUTPUT_FILE,
                "r",
                encoding="utf-8"
            ) as f:

                all_data = json.load(f)

        except Exception as e:

            print(
                f"Σφάλμα ανάγνωσης "
                f"{OUTPUT_FILE}: {e}"
            )

            all_data = []


    # ------------------------------------------------------------------
    # INDEX ΑΝΑ ΗΜΕΡΟΜΗΝΙΑ
    #
    # Πολύ σημαντικό:
    # Δεν προσπερνάμε πλέον μια ημερομηνία
    # μόνο και μόνο επειδή υπάρχει.
    #
    # Έτσι μπορούμε να συμπληρώσουμε Reservoir
    # σε παλιά records.
    # ------------------------------------------------------------------

    data_by_date = {}

    for item in all_data:

        if (
            isinstance(item, dict)
            and "Date" in item
        ):

            data_by_date[
                item["Date"]
            ] = item


    # ------------------------------------------------------------------
    # ΗΜΕΡΟΜΗΝΙΕΣ
    #
    # Υποστηρίζουμε:
    #
    # START_DATE=2026-09-21
    # END_DATE=2026-10-05
    #
    # για backfill.
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
                    (
                        end_date
                        - start_date
                    ).days + 1
                )
            ]


        except ValueError:

            print(
                "Μη έγκυρο "
                "START_DATE / END_DATE."
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
    # PROCESS DAYS
    # ------------------------------------------------------------------

    for date_str in dates_to_check:

        print(
            f"\n===================================="
        )

        print(
            f"Επεξεργασία: {date_str}"
        )

        print(
            f"===================================="
        )


        # --------------------------------------------------------------
        # Υπάρχον record ή νέο
        # --------------------------------------------------------------

        if date_str in data_by_date:

            day_entry = data_by_date[
                date_str
            ]

        else:

            day_entry = {
                "Date": date_str
            }

            data_by_date[
                date_str
            ] = day_entry


        # --------------------------------------------------------------
        # 1. RESERVOIR
        #
        # ΠΑΝΤΑ το ξαναδιαβάζουμε.
        #
        # Αυτό διορθώνει τα ήδη υπάρχοντα records.
        # --------------------------------------------------------------

        print(
            "Λήψη Reservoir..."
        )

        res_data = process_reservoir_file(
            date_str
        )


        if res_data:

            day_entry[
                "Reservoir"
            ] = res_data


            # Backward compatibility
            if (
                res_data.get("Total")
                is not None
            ):

                day_entry[
                    "ReservoirTotalRate"
                ] = res_data[
                    "Total"
                ]


            updates_made = True


        else:

            print(
                "  Reservoir: "
                "δεν βρέθηκαν δεδομένα."
            )


        # --------------------------------------------------------------
        # 2. ΠΑΡΑΓΩΓΗ
        #
        # Αν υπάρχει ήδη Hourly,
        # δεν χρειάζεται να το ξανακατεβάσουμε.
        # --------------------------------------------------------------

        if not day_entry.get(
            "Hourly"
        ):

            print(
                "Λήψη SystemRealization..."
            )

            prod_data = process_realization_file(
                date_str
            )


            if prod_data:

                day_entry[
                    "Hourly"
                ] = prod_data

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
                "  Παραγωγή: υπάρχει ήδη."
            )


    # ------------------------------------------------------------------
    # ΑΠΟΘΗΚΕΥΣΗ
    # ------------------------------------------------------------------

    final_data = sorted(
        data_by_date.values(),
        key=lambda x: x["Date"],
        reverse=True
    )


    if updates_made:

        with open(
            OUTPUT_FILE,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                final_data,
                f,
                indent=2,
                ensure_ascii=False
            )


        print(
            "\n===================================="
        )

        print(
            "Το hydro_data.json "
            "ενημερώθηκε επιτυχώς!"
        )

        print(
            "===================================="
        )


    else:

        print(
            "\nΔεν υπήρχαν αλλαγές."
        )


# ==============================================================================
# EXECUTION
# ==============================================================================

if __name__ == "__main__":

    main()
