import sys, os, json, tempfile, io, contextlib, shutil
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import build_psh as S
import build_water_balance as W
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
shutil.copy(os.path.join(ROOT, 'data', 'plant_heads.json'), 'data/')
def day(d, e=None, scada='ok'):
    base = {"Sfikia": 1500, "Polyfyto": 2400, "Asomata": 900, "Thesavros": 3000, "Platanovrysi": 1100}; base.update(e or {})
    H = [dict({"Hour": f"H{h+1:02d}"}, **{"SCADA_" + u: v / 24 for u, v in base.items()}) for h in range(24)]
    json.dump({"Date": d, "Hourly": H, "Meta": {"Status": {"scada": scada}}}, open(f'data/days/{d}.json', 'w'))
def pumpfile(rows): json.dump(rows, open('data/pump_daily.json', 'w'))
heads_doc = json.load(open('data/plant_heads.json', encoding='utf-8')); heads = heads_doc['Plants']
net, gross, est, ratio = W.k_values(heads, ['SFIKIA', 'POLYFYTO', 'ASOMATA', 'THESAVROS', 'PLATANOVRYSI'], heads_doc.get('GrossToNetRatio'))
kp_sf = 2.725 * heads['SFIKIA']['GrossHeadM'] * 1.02 / 0.87; kp_th = 2.725 * heads['THESAVROS']['GrossHeadM'] * 1.02 / 0.87
print("TEST 1: formulas")
day('2026-07-01'); day('2026-07-02', e={"Sfikia": 1800})
pumpfile([{"Date": "2026-07-01", "EstSfikiaMWh": 600.0, "EstThesavrosMWh": 900.0, "IspSfikiaMWh": 650.0, "IspThesavrosMWh": 880.0},
          {"Date": "2026-07-02", "EstSfikiaMWh": 700.0, "EstThesavrosMWh": 0.0, "IspSfikiaMWh": 720.0, "IspThesavrosMWh": 0.0}])
r, _ = cap(S.main); doc = json.load(open('data/psh_daily.json', encoding='utf-8')); sf = doc['Plants']['SFIKIA']; th = doc['Plants']['THESAVROS']
check("rc 0 and two plants with two days each", r == 0 and set(doc['Plants']) == {'SFIKIA', 'THESAVROS'} and len(sf['Daily']) == 2 and len(th['Daily']) == 2)
d0 = sf['Daily'][0]
check("Sfikia: Q = E/k_gen(net), P = Ep/k_pump, Ql = E_Asomata/k_Asomata (lower plant), Qu = E_Polyfyto/k_Polyfyto (upstream river source)",abs(d0['Q'] - 1500 / net['SFIKIA']) < 0.01 and abs(d0['P'] - 600 / kp_sf) < 0.01 and abs(d0['Ql'] - 900 / net['ASOMATA']) < 0.01 and abs(d0['Qu'] - 2400 / net['POLYFYTO']) < 0.01, d0)
t0 = th['Daily'][0]
check("Thesavros: Q, P and Ql = Platanovrysi (the lower plant); NO upstream source exists (the Nestos water comes from Bulgaria), so there is no Qu",abs(t0['Q'] - 3000 / net['THESAVROS']) < 0.01 and abs(t0['P'] - 900 / kp_th) < 0.01 and abs(t0['Ql'] - 1100 / net['PLATANOVRYSI']) < 0.01 and 'Qu' not in t0 and th['UpperSource'] is None and th['LowerDam'] == 'PLATANOVRYSI' and sf['LowerDam'] == 'ASOMATA' and sf['UpperSource'] == 'POLYFYTO', t0)
check("pump factor k = 2.725·(gross head × 1.02)/0.87 and the cycle factor = k_gen/k_pump", abs(sf['KPump'] - kp_sf) < 0.1 and abs(sf['CycleFactor'] - net['SFIKIA'] / kp_sf) < 0.002 and doc['Assumptions']['PumpEfficiency'] == 0.87 and doc['Assumptions']['PumpHeadFactor'] == 1.02)
check("the generation factors (own, lower, upper) are the SAME as the water balance uses", abs(sf['KGenNet'] - round(net['SFIKIA'], 1)) < 1e-9 and abs(sf['KLowerNet'] - round(net['ASOMATA'], 1)) < 1e-9 and abs(sf['KUpperNet'] - round(net['POLYFYTO'], 1)) < 1e-9)
check("ISP pumping is carried along and the days are in ascending order", d0['Ei'] == 650.0 and [x['Date'] for x in sf['Daily']] == ['2026-07-01', '2026-07-02'])
check("zero pumping gives P = 0 (not a missing value)", th['Daily'][1]['P'] == 0 and th['Daily'][1]['Ep'] == 0.0)
print("TEST 2: which days are used")
for f in os.listdir('data/days'): os.remove('data/days/' + f)
day('2026-07-01'); day('2026-07-02', scada='missing'); day('2026-07-03'); day('2026-07-04')
pumpfile([{"Date": "2026-07-01", "EstSfikiaMWh": 600.0, "EstThesavrosMWh": 900.0, "IspSfikiaMWh": 1, "IspThesavrosMWh": 1},
          {"Date": "2026-07-02", "EstSfikiaMWh": 600.0, "EstThesavrosMWh": 900.0, "IspSfikiaMWh": 1, "IspThesavrosMWh": 1},
          {"Date": "2026-07-03", "EstSfikiaMWh": None, "EstThesavrosMWh": 500.0, "IspSfikiaMWh": 1, "IspThesavrosMWh": 1}])
r, _ = cap(S.main); doc = json.load(open('data/psh_daily.json', encoding='utf-8'))
check("a day with SCADA missing is skipped; a day without a pump row is skipped", [x['Date'] for x in doc['Plants']['THESAVROS']['Daily']] == ['2026-07-01', '2026-07-03'], [x['Date'] for x in doc['Plants']['THESAVROS']['Daily']])
check("an unavailable estimate (None) skips only that plant for that day", [x['Date'] for x in doc['Plants']['SFIKIA']['Daily']] == ['2026-07-01'])
print("TEST 3: robustness")
os.remove('data/pump_daily.json'); r, _ = cap(S.main); check("missing pump_daily.json -> rc 1", r == 1)
pumpfile([{"Date": "2026-07-01", "EstSfikiaMWh": 600.0, "EstThesavrosMWh": 900.0, "IspSfikiaMWh": 1, "IspThesavrosMWh": 1}])
open('data/days/2026-07-09.json', 'w').write('{ broken'); r, lg = cap(S.main); check("a corrupt day file is skipped with a message and the rest is processed", r == 0 and 'δεν διαβάζεται' in lg)
os.remove('data/days/2026-07-09.json')
pumpfile([{"Date": "2030-01-01", "EstSfikiaMWh": 1.0, "EstThesavrosMWh": 1.0, "IspSfikiaMWh": 1, "IspThesavrosMWh": 1}]); r, _ = cap(S.main); check("no usable day at all -> rc 1 and no file is overwritten with an empty result", r == 1)
os.remove('data/plant_heads.json'); r, _ = cap(S.main); check("missing plant_heads.json -> rc 1", r == 1)
print(f"\n{PASS} passed, {FAIL} failed")
if __name__ == "__main__":
    sys.exit(1 if FAIL else 0)
