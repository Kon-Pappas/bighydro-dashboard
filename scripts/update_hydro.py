import os
import io
import json
import time
import requests
import pandas as pd
import numpy as np
import warnings
from datetime import datetime, timedelta

warnings.filterwarnings("ignore", message="Workbook contains no default style")

# Το token παραμένει για το MCP_GR
ENTSOE_TOKEN = os.environ.get("ENTSOE_TOKEN")

# Η αντιστοίχιση των 16 Υδροηλεκτρικών μας (JSON_Key, SCADA_Name, ISP_Names_List)
HYDRO_UNITS = [
    ("Kremasta", "ΚΡΕΜΑΣΤΑ", ["KREMASTA"]),
    ("Kastraki", "ΚΑΣΤΡΑΚΙ", ["KASTRAKI"]),
    ("Stratos1", "ΣΤΡΑΤΟΣ 1", ["STRATOS1"]),
    ("Ilarionas", "ΙΛΑΡΙΩΝ", ["ILARIONAS"]),
    ("Polyfyto", "ΠΟΛΥΦΥΤΟ", ["POLYFYTO"]),
    ("Sfikia", "ΣΦΗΚΙΑ", ["SFIKIA"]),
    ("Asomata", "ΑΣΩΜΑΤΑ", ["ASOMATA"]),
    ("Thesavros", "ΘΗΣΑΥΡΟΣ", ["THESAVROS1", "THESAVROS2", "THESAVROS3"]),
    ("Platanovrysi", "ΠΛΑΤΑΝΟΒΡΥΣΗ", ["PLATANOVRYSI"]),
    ("PAoou", "ΑΩΟΣ", ["P_AOOU"]),
    ("Pournari1", "ΠΟΥΡΝΑΡΙ", ["POURNARI1"]),
    ("Pournari2", "ΠΟΥΡΝΑΡΙ 2", ["POURNARI2"]),
    ("Agras", "ΑΓΡΑΣ", ["AGRAS"]),
    ("Edessaios", "ΕΔΕΣΣΑΙΟΣ", ["EDESSAIOS"]),
    ("Ladonas", "ΛΑΔΩΝΑΣ", ["LADONAS"]),
    ("Plastiras", "ΠΛΑΣΤΗΡΑΣ", ["PLASTIRAS"])
]

ISP_PUMP_UNITS = ['SFIKIA_PUMP', 'THESAVROS1_PUMP', 'THESAVROS2_PUMP', 'THESAVROS3_PUMP']

def log(msg):
    print(msg, flush=True)

def http_get(url, headers=None, tries=3, what=""):
    for attempt in range(1, tries + 1):
        try:
            res = requests.get(url, headers=headers, timeout=20)
            return res
        except Exception as e:
            log(f"   ! {what}: αποτυχία σύνδεσης ({type(e).__name__}), προσπάθεια {attempt}/{tries}")
            time.sleep(2 * attempt)
    return None

# --- Λήψη Τιμών (ENTSO-E) ---
def get_entsoe_period(date_str):
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    start_utc = (dt - timedelta(days=1)).replace(hour=22, minute=0, second=0) # Απλοποιημένο για δοκιμή
    end_utc = dt.replace(hour=22, minute=0, second=0)
    return start_utc.strftime("%Y%m%d%H00"), end_utc.strftime("%Y%m%d%H00")

def fetch_entsoe_mcp_gr(date_str):
    empty = [None] * 24
    if not ENTSOE_TOKEN: return empty
    periodStart, periodEnd = get_entsoe_period(date_str)
    url = f"https://web-api.tp.entsoe.eu/api?securityToken={ENTSOE_TOKEN}&documentType=A44&in_Domain=10YGR-HTSO-----Y&out_Domain=10YGR-HTSO-----Y&periodStart={periodStart}&periodEnd={periodEnd}"
    res = http_get(url, what="MCP GR")
    if not res or res.status_code != 200: return empty
    try:
        import xml.etree.ElementTree as ET
        root = ET.fromstring(res.text)
        ns = {'ns': root.tag.split('}')[0].strip('{')}
        hourly = []
        for ts in root.findall('ns:TimeSeries', ns):
            period = ts.find('ns:Period', ns)
            if not period: continue
            points = {int(p.find('ns:position', ns).text): float(p.find('ns:price.amount', ns).text) for p in period.findall('ns:Point', ns)}
            
            # Απλοποιημένη ανάγνωση για 24 ώρες (αν το resolution είναι PT60M)
            for i in range(1, 25):
                hourly.append(points.get(i, None))
            if len(hourly) >= 24: break
        return hourly[:24] if len(hourly) >= 24 else empty
    except:
        return empty

# --- Λήψη ΑΔΜΗΕ ---
def fetch_admie_excel(date_str, category):
    url = f"https://www.admie.gr/getOperationMarketFile?dateStart={date_str}&dateEnd={date_str}&FileCategory={category}"
    headers = {"User-Agent": "Mozilla/5.0"}
    res = http_get(url, headers=headers, what=f"ADMIE {category}")
    if not res or res.status_code != 200: return None
    try:
        data = res.json()
        if not data: return None
        file_path = "https://www.admie.gr" + data[0].get("file_path") if data[0].get("file_path").startswith("/") else data[0].get("file_path")
        file_res = http_get(file_path, headers=headers, what=f"ADMIE {category} αρχείο")
        return io.BytesIO(file_res.content) if file_res and file_res.status_code == 200 else None
    except:
        return None

def extract_hourly_vals(df, keyword, col_index):
    try:
        row = df[df[col_index].astype(str).str.contains(keyword, case=False, na=False)]
        if row.empty: return [0.0] * 24
        return np.nan_to_num(row.iloc[0, 2:26].values.astype(float)).tolist()
    except: return [0.0] * 24

def extract_isp_hourly(df, keywords):
    total_quarters = np.zeros(96)
    found = False
    for kw in keywords:
        row = df[df[0].astype(str).str.contains(kw, case=False, na=False)]
        if not row.empty:
            found = True
            vals = np.nan_to_num(row.iloc[0, 1:97].values.astype(float))
            total_quarters += vals
    if not found: return [0.0] * 24
    return total_quarters.reshape(24, 4).mean(axis=1).tolist()

def none_list(): return [None] * 24

def process_day(date_str):
    log(f"Επεξεργασία: {date_str}")
    
    day = {
        "Date": date_str,
        "ReservoirTotalRate": None,
        "Hourly": []
    }
    
    # 1. SCADA (Πραγματικό)
    scada_data = {u[0]: none_list() for u in HYDRO_UNITS}
    scada_pump = none_list()
    scada_file = fetch_admie_excel(date_str, "SystemRealizationSCADA")
    if scada_file:
        try:
            df_scada = pd.read_excel(scada_file, sheet_name="System_Production", header=None)
            for unit in HYDRO_UNITS:
                scada_data[unit[0]] = extract_hourly_vals(df_scada, unit[1], 1)
            scada_pump = extract_hourly_vals(df_scada, "TOTAL PUMPING", 1)
        except Exception as e: log(f"   ! SCADA Error: {e}")

    # 2. ISP (Πρόγραμμα)
    isp_data = {u[0]: none_list() for u in HYDRO_UNITS}
    isp_pump = none_list()
    isp_file = fetch_admie_excel(date_str, "ISP2ISPResults")
    if isp_file:
        try:
            # Το φύλλο συνήθως έχει όνομα YYYYMMDD_ISP, διαβάζουμε το πρώτο φύλλο
            df_isp = pd.read_excel(isp_file, sheet_name=0, header=None)
            for unit in HYDRO_UNITS:
                isp_data[unit[0]] = extract_isp_hourly(df_isp, unit[2])
            isp_pump = extract_isp_hourly(df_isp, ISP_PUMP_UNITS)
            # Αντιστροφή προσήμου για το ISP Pump (να είναι αρνητικό όπως το SCADA)
            isp_pump = [v * -1 if v != 0 else 0 for v in isp_pump]
        except Exception as e: log(f"   ! ISP Error: {e}")

    # 3. RESMV (Μικρά Υδροηλεκτρικά)
    small_hydro = [0.0] * 24
    resmv_file = fetch_admie_excel(date_str, "RESMV")
    if resmv_file:
        try:
            df_resmv = pd.read_excel(resmv_file)
            cols = [c for c in df_resmv.columns if 'ΜΥΗΣ ΕΝΕΡΓΕΙΑ' in str(c)]
            if cols:
                vals = df_resmv[cols[0]].dropna().values[:24]
                small_hydro = [float(v) / 1000.0 for v in vals] # KWh to MWh
        except Exception as e: log(f"   ! RESMV Error: {e}")

    # 4. Ταμιευτήρες (Reservoir)
    res_file = fetch_admie_excel(date_str, "ReservoirFillingRate")
    if res_file:
        try:
            df_res = pd.read_excel(res_file, sheet_name="Reservoir Filling Rate", header=None)
            # Αναζήτηση του κελιού 'Filling Rate (%) Total'
            for idx, row in df_res.iterrows():
                for col_idx, val in enumerate(row):
                    if 'Filling Rate (%) Total' in str(val):
                        # Η τιμή είναι συνήθως 3 στήλες πιο δεξιά
                        day["ReservoirTotalRate"] = round(float(row[col_idx + 3]) * 100, 2)
                        break
        except Exception as e: log(f"   ! Reservoir Error: {e}")

    # 5. MCP (ENTSO-E)
    mcp_gr = fetch_entsoe_mcp_gr(date_str)

    # Συνένωση των δεδομένων
    for hour in range(24):
        row = {
            "Hour": f"H{hour + 1:02d}",
            "SCADA_Pump": round(scada_pump[hour], 2) if scada_pump[hour] is not None else None,
            "ISP_Pump": round(isp_pump[hour], 2) if isp_pump[hour] is not None else None,
            "SCADA_SmallHydro": round(small_hydro[hour], 2),
            "MCP_GR": mcp_gr[hour]
        }
        for unit in HYDRO_UNITS:
            key = unit[0]
            row[f"SCADA_{key}"] = round(scada_data[key][hour], 2) if scada_data[key][hour] is not None else None
            row[f"ISP_{key}"] = round(isp_data[key][hour], 2) if isp_data[key][hour] is not None else None
        day["Hourly"].append(row)

    return day

def load_existing(json_path):
    if os.path.exists(json_path) and os.path.getsize(json_path) > 0:
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

if __name__ == "__main__":
    start_env = os.environ.get("START_DATE")
    end_env = os.environ.get("END_DATE")

    if start_env and end_env:
        start_dt = datetime.strptime(start_env, "%Y-%m-%d")
        end_dt = datetime.strptime(end_env, "%Y-%m-%d")
        delta = end_dt - start_dt
        dates_to_fetch = [(start_dt + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(delta.days + 1)]
        log(f"--- Χειροκίνητη εκτέλεση: {start_env} έως {end_env} ---")
    else:
        dates_to_fetch = [(datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(3, -1, -1)]
        log("--- Κανονική εκτέλεση (τελευταίες 4 ημέρες) ---")

    json_path = "data/hydro_data.json"
    all_data = load_existing(json_path)
    by_date = {x["Date"]: x for x in all_data}

    for d in dates_to_fetch:
        new_day = process_day(d)
        # Απλό merge: αντικαθιστούμε τα δεδομένα της ημέρας με τα νέα
        by_date[d] = new_day

    result = sorted(by_date.values(), key=lambda x: x["Date"], reverse=True)
    
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2)
    log("Ολοκληρώθηκε η αποθήκευση στο hydro_data.json!")