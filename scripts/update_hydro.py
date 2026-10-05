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
    "AGRAS", "ASOMATA", "EDESSAIOS", "ILARIONAS", "KASTRAKI",
    "KREMASTA", "LADONAS", "PLASTIRAS", "PLATANOVRYSI", "POLYFYTO",
    "POURNARI 1", "POURNARI 2", "P. AOOU", "SFIKIA", "STRATOS 1", "THESAVROS"
]

# Αντιστοίχιση των ονομάτων από το αρχείο Reservoir στο τελικό ID (κοινό)
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
    "POYRNARI1": "Pournari1", # Πρόσεξε: Στο XLS το λέει POYRNARI με Y
    "POYRNARI2": "Pournari2",
    "P_AOOU": "PAoou",
    "SFIKIA": "Sfikia",
    "STRATOS": "Stratos1",
    "THESAVROS1": "Thesavros", # Θα ενώσουμε 1,2,3 σε ένα
    "THESAVROS2": "Thesavros",
    "THESAVROS3": "Thesavros"
}

# ==============================================================================
# ΒΟΗΘΗΤΙΚΕΣ ΣΥΝΑΡΤΗΣΕΙΣ ΛΗΨΗΣ ΑΡΧΕΙΩΝ
# ==============================================================================
def download_excel(url):
    """Κατεβάζει ένα αρχείο Excel από ένα URL."""
    try:
        response = requests.get(url, verify=False, timeout=30)
        response.raise_for_status()
        return response.content
    except Exception as e:
        print(f"Σφάλμα λήψης {url}: {e}")
        return None

# ==============================================================================
# ΑΝΑΛΥΣΗ ΑΡΧΕΙΟΥ RESERVOIR (Ταμιευτήρες)
# ==============================================================================
def process_reservoir_file(date_str):
    """Κατεβάζει και αναλύει το αρχείο ReservoirFillingRate."""
    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    date_format_url = date_obj.strftime("%Y%m%d")
    
    url = f"https://admie.gr/get-file/{date_format_url}_ReservoirFillingRate_01.xls"
    
    file_content = download_excel(url)
    if not file_content:
        return None
        
    try:
        # Γράφουμε το αρχείο προσωρινά για να το διαβάσει το pandas
        temp_file = f"temp_res_{date_format_url}.xls"
        with open(temp_file, "wb") as f:
            f.write(file_content)
            
        df = pd.read_excel(temp_file, sheet_name=0)
        os.remove(temp_file) # Καθαρίζουμε το προσωρινό αρχείο
        
        # 1. Εξαγωγή του Συνολικού Ποσοστού (Total)
        total_val = None
        for index, row in df.iterrows():
            if pd.notna(row.iloc[7]) and "Total" in str(row.iloc[7]):
                try:
                    total_val = float(row.iloc[10])
                except:
                    pass
                break
                
        # 2. Εξαγωγή ποσοστών ανά ταμιευτήρα
        raw_rates = {}
        for index, row in df.iterrows():
            entity = str(row.iloc[1]).strip()
            rate = row.iloc[2]
            
            if pd.notna(entity) and entity not in ['nan', 'Entity']:
                try:
                    raw_rates[entity] = float(rate)
                except ValueError:
                    pass
        
        # 3. Χαρτογράφηση στα δικά μας IDs
        clean_rates = {}
        for raw_name, rate in raw_rates.items():
            if raw_name in RESERVOIR_MAPPING:
                clean_id = RESERVOIR_MAPPING[raw_name]
                clean_rates[clean_id] = rate
                
        return {
            "Total": total_val,
            "Units": clean_rates
        }
    except Exception as e:
        print(f"Σφάλμα στην επεξεργασία του Reservoir για {date_str}: {e}")
        return None

# ==============================================================================
# ΑΝΑΛΥΣΗ ΑΡΧΕΙΟΥ ΠΑΡΑΓΩΓΗΣ (ISP & SCADA)
# ==============================================================================
def process_realization_file(date_str):
    """Κατεβάζει και αναλύει το αρχείο SystemRealization."""
    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    date_format_url = date_obj.strftime("%Y%m%d")
    
    url = f"https://admie.gr/get-file/{date_format_url}_SystemRealization_01.xls"
    
    file_content = download_excel(url)
    if not file_content:
        return None
        
    try:
        temp_file = f"temp_prod_{date_format_url}.xls"
        with open(temp_file, "wb") as f:
            f.write(file_content)
            
        df = pd.read_excel(temp_file, sheet_name=0, header=None)
        os.remove(temp_file)
        
        hourly_data = {hour: {} for hour in range(1, 25)}
        
        # Εντοπισμός μονάδων και Data Type (ISP/SCADA)
        unit_columns = {} 
        for col_idx in range(df.shape[1]):
            unit_name = str(df.iloc[2, col_idx]).strip()
            data_type = str(df.iloc[3, col_idx]).strip()
            
            if unit_name in HYDRO_UNITS:
                clean_id = unit_name.replace(" ", "").replace(".", "")
                key = f"{data_type}_{clean_id}"
                unit_columns[key] = col_idx
                
        if not unit_columns:
            return None
            
        # Εξαγωγή δεδομένων (Γραμμές 5 έως 28 είναι οι ώρες 1-24)
        for hour in range(1, 25):
            row_idx = hour + 3 
            if row_idx < len(df):
                for key, col_idx in unit_columns.items():
                    val = df.iloc[row_idx, col_idx]
                    try:
                        hourly_data[hour][key] = float(val) if pd.notna(val) else 0.0
                    except:
                        hourly_data[hour][key] = 0.0
                        
        # Μορφοποίηση σε λίστα
        hourly_list = []
        for h in range(1, 25):
            entry = {"Hour": h}
            entry.update(hourly_data[h])
            hourly_list.append(entry)
            
        return hourly_list
    except Exception as e:
        print(f"Σφάλμα στην επεξεργασία της Παραγωγής για {date_str}: {e}")
        return None

# ==============================================================================
# ΚΥΡΙΟ ΣΚΡΙΠΤ (MAIN)
# ==============================================================================
def main():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        
    # Φόρτωση υπαρχόντων δεδομένων
    all_data = []
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
                all_data = json.load(f)
        except Exception as e:
            print(f"Σφάλμα ανάγνωσης του {OUTPUT_FILE}: {e}")
            all_data = []
            
    existing_dates = {item["Date"] for item in all_data}
    
    # Επεξεργασία των τελευταίων 7 ημερών (για να καλύψουμε τυχόν κενά)
    today = datetime.now()
    dates_to_check = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
    
    updates_made = False
    
    for d in dates_to_check:
        if d in existing_dates:
            continue # Αν υπάρχει ήδη, το προσπερνάμε (εκτός αν θες να το ξανακατεβάζει)
            
        print(f"Λήψη δεδομένων για: {d}")
        
        # 1. Παραγωγή (ISP & SCADA)
        prod_data = process_realization_file(d)
        
        # 2. Ταμιευτήρες (Reservoirs) - Μπορεί να μην υπάρχει για την τρέχουσα μέρα, οπότε αντέχει τα errors
        res_data = process_reservoir_file(d)
        
        if prod_data:
            day_entry = {
                "Date": d,
                "Hourly": prod_data
            }
            if res_data:
                day_entry["Reservoir"] = res_data
                
            all_data.append(day_entry)
            updates_made = True
            print(f"  Επιτυχία: {d}")
        else:
            print(f"  Δεν βρέθηκαν δεδομένα παραγωγής για {d}.")
            
    # Αποθήκευση αν έγιναν αλλαγές
    if updates_made:
        # Ταξινόμηση από την πιο πρόσφατη στην παλαιότερη ημερομηνία
        all_data.sort(key=lambda x: x["Date"], reverse=True)
        
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(all_data, f, indent=2, ensure_ascii=False)
        print("\nΤο αρχείο hydro_data.json ενημερώθηκε επιτυχώς!")
    else:
        print("\nΔεν υπήρχαν νέα δεδομένα για προσθήκη.")

if __name__ == "__main__":
    main()