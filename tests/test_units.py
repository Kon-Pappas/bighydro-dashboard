import sys, os, json, tempfile, io, contextlib, shutil
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import build_unit_status as S
PASS = FAIL = 0
def check(n, c, e=""):
    global PASS, FAIL
    if c: PASS += 1; print("  PASS", n)
    else: FAIL += 1; print("  FAIL", n, e)
def cap(fn, *a, **k):
    s = io.StringIO()
    with contextlib.redirect_stdout(s): r = fn(*a, **k)
    return r, s.getvalue()
tmp = tempfile.mkdtemp(); os.chdir(tmp); os.makedirs('data/days')
meta = {"Reservoirs": {"STRATOS": {"Units": ["Stratos1", "Stratos2"]}, "ILARIONAS": {"Units": ["Ilarionas"]}}, "WithoutReservoir": [{"Name": "Εδεσσαίος", "Units": ["Edessaios"]}], "OtherHydro": ["Makrochori"]}
json.dump(meta, open('data/reservoirs.json', 'w', encoding='utf-8'), ensure_ascii=False)
def day(d, vals, scada='ok', drop=()):
    H = []
    for h in range(24):
        row = {"Hour": f"H{h+1:02d}"}
        for u, v in vals.items():
            if u in drop: continue
            row["SCADA_" + u] = v / 24 if v is not None else None
        H.append(row)
    json.dump({"Date": d, "Hourly": H, "Meta": {"Status": {"scada": scada}}}, open(f'data/days/{d}.json', 'w'))
print("TEST 1: daily sums")
day('2026-07-01', {"Stratos1": 240, "Stratos2": 24, "Ilarionas": 0, "Edessaios": 0, "Makrochori": 48})
day('2026-07-02', {"Stratos1": 120, "Stratos2": 0, "Ilarionas": 372, "Edessaios": 0, "Makrochori": 48})
day('2026-07-03', {"Stratos1": 1, "Stratos2": 1, "Ilarionas": 1, "Edessaios": 1, "Makrochori": 1}, scada='missing')
r, _ = cap(S.main); doc = json.load(open('data/unit_daily.json', encoding='utf-8')); U = doc['Units']
check("rc 0; only days with complete SCADA are kept, in ascending order", r == 0 and doc['Dates'] == ['2026-07-01', '2026-07-02'], doc['Dates'])
check("units come from reservoirs.json: dam units, plants without reservoir, small PPC plants", list(U) == ['Stratos1', 'Stratos2', 'Ilarionas', 'Edessaios', 'Makrochori'], list(U))
check("daily energy = sum of the 24 hours", U['Stratos1']['Mwh'] == [240.0, 120.0] and U['Ilarionas']['Mwh'] == [0.0, 372.0] and U['Makrochori']['Mwh'] == [48.0, 48.0], {k: v['Mwh'] for k, v in U.items()})
check("dam and name metadata are carried (dam key, Greek name for plants without a reservoir)", U['Ilarionas']['Dam'] == 'ILARIONAS' and U['Edessaios']['Dam'] is None and U['Edessaios']['Name'] == 'Εδεσσαίος' and U['Makrochori']['Dam'] is None)
check("a zero day is stored as 0.0, not as a missing value", U['Ilarionas']['Mwh'][0] == 0.0 and U['Ilarionas']['Mwh'][0] is not None)
print("TEST 2: missing data")
for f in os.listdir('data/days'): os.remove('data/days/' + f)
day('2026-07-01', {"Stratos1": 240, "Ilarionas": 0, "Edessaios": 0, "Makrochori": 48}, drop=("Stratos2",))
day('2026-07-02', {"Stratos1": 240, "Stratos2": 24, "Ilarionas": None, "Edessaios": 0, "Makrochori": 48})
r, _ = cap(S.main); U = json.load(open('data/unit_daily.json', encoding='utf-8'))['Units']
check("a unit absent from the file on a day is null (not zero)", U['Stratos2']['Mwh'] == [None, 24.0], U['Stratos2']['Mwh'])
check("a unit whose hours are null is null for that day", U['Ilarionas']['Mwh'] == [0.0, None], U['Ilarionas']['Mwh'])
print("TEST 3: robustness")
open('data/days/2026-07-09.json', 'w').write('{ broken'); r, lg = cap(S.main); check("a corrupt day file is skipped with a message", r == 0 and 'δεν διαβάζεται' in lg)
os.remove('data/days/2026-07-09.json')
for f in os.listdir('data/days'): os.remove('data/days/' + f)
r, _ = cap(S.main); check("no usable day -> rc 1", r == 1)
os.remove('data/reservoirs.json'); r, _ = cap(S.main); check("missing reservoirs.json -> rc 1", r == 1)
print(f"\n{PASS} passed, {FAIL} failed")
if __name__ == "__main__":
    sys.exit(1 if FAIL else 0)
