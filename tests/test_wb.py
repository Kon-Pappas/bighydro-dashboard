import sys, os, json, tempfile, io, contextlib, shutil
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import build_water_balance as W
PASS=FAIL=0
def check(n,c,e=""):
    global PASS,FAIL
    if c: PASS+=1; print("  PASS",n)
    else: FAIL+=1; print("  FAIL",n,e)
def cap(fn,*a,**k):
    s=io.StringIO()
    with contextlib.redirect_stdout(s): r=fn(*a,**k)
    return r,s.getvalue()
tmp=tempfile.mkdtemp(); os.chdir(tmp); os.makedirs('data/days')
shutil.copy(os.path.join(ROOT,'data','reservoirs.json'),'data/'); shutil.copy(os.path.join(ROOT,'data','plant_heads.json'),'data/')
def day(d,fill,e=None,scada='ok'):
    e=e or {}
    units=["Kremasta","Kastraki","Stratos1","Stratos2","Ilarionas","Polyfyto","Sfikia","Asomata","Thesavros","Platanovrysi","PAoou","Pournari1","Pournari2","Plastiras","Ladonas"]
    base={"Kremasta":3540,"Kastraki":1990,"Stratos1":820,"Stratos2":50,"Ilarionas":100,"Polyfyto":2400,"Sfikia":1500,"Asomata":900,"Thesavros":3000,"Platanovrysi":1100,"PAoou":1200,"Pournari1":4000,"Pournari2":600,"Plastiras":500,"Ladonas":400}; base.update(e)
    H=[dict({"Hour":f"H{h+1:02d}"},**{"SCADA_"+u:base[u]/24 for u in units}) for h in range(24)]
    full={"KREMASTA":50.0,"KASTRAKI":100.0,"STRATOS":50.0,"ILARIONAS":15.0,"POLYFYTO":40.0,"SFIKIA":50.0,"ASOMATA":50.0,"THESAVROS":60.0,"PLATANOVRYSI":50.0,"P_AOOU":50.0,"POYRNARI1":60.0,"POYRNARI2":50.0,"PLASTIRAS":70.0,"LADONAS":40.0}; full.update(fill)
    json.dump({"Date":d,"Reservoir":full,"Hourly":H,"Meta":{"Status":{"scada":scada}}},open(f'data/days/{d}.json','w'))
day('2026-07-01',{}); day('2026-07-02',{"KREMASTA":49.0,"KASTRAKI":99.0,"POLYFYTO":39.0,"SFIKIA":60.0,"ASOMATA":45.0}); day('2026-07-03',{},scada='missing')
r,_=cap(W.main); wb=json.load(open('data/water_balance.json',encoding='utf-8')); A=wb['Rivers']['acheloos']; L=wb['Rivers']['aliakmonas']
print("TEST 1: Acheloos formulas (groups of one dam)")
D=A['Daily']; d=D[0]; kn=A['KNet']
check("rc 0; days with SCADA ok and a next-day reading (07-01, 07-02)",r==0 and [x['Date'] for x in D]==['2026-07-01','2026-07-02'],[x['Date'] for x in D])
dv=[(49-50)/100*2805,(99-100)/100*53,0.0]; Q=[3540/kn['KREMASTA'],1990/kn['KASTRAKI'],820/kn['STRATOS']]
check("dV = V(d+1)-V(d)",all(abs(a-b)<0.01 for a,b in zip(d['dV'],dv)),d['dV'])
check("turbined volume = E/k (net)",all(abs(a-b)<0.01 for a,b in zip(d['Qn'],Q)))
inflow=[dv[0]+Q[0],dv[1]+Q[1]-Q[0],dv[2]+Q[2]-Q[1]]
check("apparent inflow: head = dV+Q, others subtract upstream Q",all(abs(a-b)<0.02 for a,b in zip(d['Inn'],inflow)),(d['Inn'],inflow))
check("river inflow = ΣdV + Q_last = sum of group inflows",abs(d['Rivern']-(sum(dv)+Q[2]))<0.02 and abs(d['Rivern']-sum(d['Inn']))<0.03)
check("groups and out units",[g['OutUnit'] for g in A['Groups']]==['Kremasta','Kastraki','Stratos1'] and A['NetHeadEstimatedFor']==['STRATOS'])
print("TEST 2: Aliakmonas groups (Ilarionas | Polyfyto | Sfikia+Asomata) - Ilarionas stays separate")
L0=L['Daily'][0]; kl=L['KNet']
check("3 groups with out plants Ilarionas, Polyfyto, Asomata",[g['Dams'] for g in L['Groups']]==[['ILARIONAS'],['POLYFYTO'],['SFIKIA','ASOMATA']] and [g['OutUnit'] for g in L['Groups']]==['Ilarionas','Polyfyto','Asomata'],L['Groups'])
dvA=[(15-15)/100*412,(39-40)/100*1020,(60-50)/100*16+(45-50)/100*10]; QA=[100/kl['ILARIONAS'],2400/kl['POLYFYTO'],900/kl['ASOMATA']]
check("group dV (Sfikia + Asomata summed)",all(abs(a-b)<0.01 for a,b in zip(L0['dV'],dvA)),(L0['dV'],dvA))
check("inflows: Il = dV+Q ; Po = dV+Q-Q_Il ; SfAs = dV+Q_As-Q_Po",abs(L0['Inn'][0]-(dvA[0]+QA[0]))<0.02 and abs(L0['Inn'][1]-(dvA[1]+QA[1]-QA[0]))<0.02 and abs(L0['Inn'][2]-(dvA[2]+QA[2]-QA[1]))<0.02,(L0['Inn'],dvA,QA))
check("river = ΣdV + Q_Asomata = sum of the three inflows",abs(L0['Rivern']-(sum(dvA)+QA[2]))<0.02 and abs(L0['Rivern']-sum(L0['Inn']))<0.03)
day('2026-07-01',{},e={"Sfikia":9999}); day('2026-07-02',{"KREMASTA":49.0,"KASTRAKI":99.0,"POLYFYTO":39.0,"SFIKIA":60.0,"ASOMATA":45.0},e={"Sfikia":9999})
cap(W.main); L2=json.load(open('data/water_balance.json',encoding='utf-8'))['Rivers']['aliakmonas']['Daily'][0]
check("PUMP INDEPENDENCE: changing Sfikia generation leaves every result unchanged",L2['Inn']==L0['Inn'] and L2['Rivern']==L0['Rivern'],(L2['Inn'],L0['Inn']))
day('2026-07-01',{},e={"Ilarionas":0}); day('2026-07-02',{"KREMASTA":49.0,"KASTRAKI":99.0,"POLYFYTO":39.0,"SFIKIA":60.0,"ASOMATA":45.0},e={"Ilarionas":0})
cap(W.main); L3=json.load(open('data/water_balance.json',encoding='utf-8'))['Rivers']['aliakmonas']['Daily'][0]
check("ILARIONAS OUTAGE: river total and (Ilarionas+Polyfyto) sum unchanged, only the split moves",abs(L3['Rivern']-L0['Rivern'])<0.02 and abs((L3['Inn'][0]+L3['Inn'][1])-(L0['Inn'][0]+L0['Inn'][1]))<0.02 and abs(L3['Inn'][0]-L0['Inn'][0])>0.3,(L3['Inn'],L0['Inn']))
print("TEST 2b: the remaining rivers (Nestos, Arachthos, Plastiras, Ladonas)")
CH=json.load(open(os.path.join(ROOT,'data','reservoirs.json'),encoding='utf-8'))
def two_days(fill2,e1=None,e2=None):
    for f in os.listdir('data/days'): os.remove('data/days/'+f)
    day('2026-07-01',{},e=e1); day('2026-07-02',fill2,e=e2 if e2 is not None else e1)
    cap(W.main); return json.load(open('data/water_balance.json',encoding='utf-8'))['Rivers']
F2={"THESAVROS":58.0,"PLATANOVRYSI":70.0,"P_AOOU":48.0,"POYRNARI1":57.0,"POYRNARI2":40.0,"PLASTIRAS":69.0,"LADONAS":38.0}
R=two_days(F2); capm={k:v['CapacityHm3'] for k,v in CH['Reservoirs'].items()}
check("all six river systems are produced",sorted(R)==['acheloos','aliakmonas','arachthos','ladonas','nestos','plastiras'],sorted(R))
N=R['nestos']; n0=N['Daily'][0]; kN=N['KNet']
dvN=(58-60)/100*capm['THESAVROS']+(70-50)/100*capm['PLATANOVRYSI']; QN=1100/kN['PLATANOVRYSI']
check("Nestos: ONE group (Thesavros+Platanovrysi) whose exit plant is Platanovrysi",[g['Dams'] for g in N['Groups']]==[['THESAVROS','PLATANOVRYSI']] and N['Groups'][0]['OutUnit']=='Platanovrysi',N['Groups'])
check("Nestos: river inflow = dV(both dams) + Q_Platanovrysi",abs(n0['Rivern']-(dvN+QN))<0.02 and abs(n0['Inn'][0]-n0['Rivern'])<0.02,(n0['Rivern'],dvN+QN))
n1=two_days(F2,e1={"Thesavros":9999})['nestos']['Daily'][0]
check("Nestos: PUMP/THESAVROS GENERATION INDEPENDENCE - changing Thesavros output leaves the result unchanged",abs(n1['Rivern']-n0['Rivern'])<1e-6,(n1['Rivern'],n0['Rivern']))
A2=R['arachthos']; a0=A2['Daily'][0]; kA=A2['KNet']
dvA0=(48-50)/100*capm['P_AOOU']; dvA1=(57-60)/100*capm['POYRNARI1']+(40-50)/100*capm['POYRNARI2']; QA0=1200/kA['P_AOOU']; QA1=600/kA['POYRNARI2']
check("Arachthos: groups Aoos | Pournari I+II with exit plants PAoou and Pournari2",[g['Dams'] for g in A2['Groups']]==[['P_AOOU'],['POYRNARI1','POYRNARI2']] and [g['OutUnit'] for g in A2['Groups']]==['PAoou','Pournari2'],A2['Groups'])
# tolerance 0.06: KNet is stored with one decimal and Pournari II has a small factor (~26 MWh/hm3), so rounding weighs more
check("Arachthos: Aoos = dV+Q ; Pournari block = dV+Q_II-Q_Aoos ; river = sum",abs(a0['Inn'][0]-(dvA0+QA0))<0.02 and abs(a0['Inn'][1]-(dvA1+QA1-QA0))<0.06 and abs(a0['Rivern']-(dvA0+dvA1+QA1))<0.06,(a0['Inn'],dvA0+QA0,dvA1+QA1-QA0))
a1=two_days(F2,e1={"Pournari1":9999})['arachthos']['Daily'][0]
check("Arachthos: Pournari I generation cancels inside the merged block (river total unchanged)",abs(a1['Rivern']-a0['Rivern'])<1e-6)
for rid,dam,fl,unit,e in (('plastiras','PLASTIRAS',69.0,'Plastiras',500),('ladonas','LADONAS',38.0,'Ladonas',400)):
    r=R[rid]; x=r['Daily'][0]; k=r['KNet'][dam]; dv=(fl-({'PLASTIRAS':70.0,'LADONAS':40.0}[dam]))/100*capm[dam]
    check(f"{rid}: single group, inflow = dV + E/k (net)",len(r['Groups'])==1 and abs(x['Rivern']-(dv+e/k))<0.02 and abs(x['Inn'][0]-x['Rivern'])<0.02,(x['Rivern'],dv+e/k))
check("the net-head estimates are flagged for the exit plants without a published net head",set(R['arachthos']['NetHeadEstimatedFor'])>={'P_AOOU','POYRNARI2'} and 'PLATANOVRYSI' in R['nestos']['NetHeadEstimatedFor'],(R['arachthos']['NetHeadEstimatedFor'],R['nestos']['NetHeadEstimatedFor']))
for f in os.listdir('data/days'): os.remove('data/days/'+f)
day('2026-07-01',{}); day('2026-07-02',{"KREMASTA":49.0,"KASTRAKI":99.0,"POLYFYTO":39.0,"SFIKIA":60.0,"ASOMATA":45.0}); day('2026-07-03',{},scada='missing')

print("TEST 3: invalid 0.00% readings")
for f in os.listdir('data/days'): os.remove('data/days/'+f)
day('2026-07-04',{"ILARIONAS":15.0}); day('2026-07-05',{"ILARIONAS":0.0}); day('2026-07-06',{"ILARIONAS":15.4}); day('2026-07-07',{"ILARIONAS":15.4})
r,lg=cap(W.main); wb=json.load(open('data/water_balance.json',encoding='utf-8')); L=wb['Rivers']['aliakmonas']
check("interior 0.00% is interpolated, note recorded, no day dropped",len(L['Daily'])==3 and L['Sanitized'] and L['Sanitized'][0]['Days']==1 and 'παρεμβλήθηκε' in lg,(len(L['Daily']),L['Sanitized']))
check("interpolated ΔV for Ilarionas is small (no −60 hm³ glitch)",abs(L['Daily'][0]['dV'][0])<10,L['Daily'][0]['dV'])
for f in os.listdir('data/days'): os.remove('data/days/'+f)
day('2026-07-04',{"ILARIONAS":15.0}); day('2026-07-05',{"ILARIONAS":0.0})
cap(W.main); L=json.load(open('data/water_balance.json',encoding='utf-8'))['Rivers']['aliakmonas']
check("0.00% at the end of the series (cannot interpolate): the day is skipped, not a huge ΔV",len(L['Daily'])==0,L['Daily'])
print("TEST 4: missing inputs / corrupt file / no net heads")
os.remove('data/plant_heads.json'); r,_=cap(W.main); check("missing plant_heads.json -> rc 1",r==1)
d=json.load(open(os.path.join(ROOT,'data','plant_heads.json'),encoding='utf-8'))
for k in d['Plants'].values(): k.pop('NetHeadMinM',None); k.pop('NetHeadMaxM',None)
d.pop('GrossToNetRatio',None)
json.dump(d,open('data/plant_heads.json','w',encoding='utf-8')); day('2026-07-04',{}); day('2026-07-05',{})
r,lg=cap(W.main); check("plant_heads without net heads: falls back to ratio 1.125 with a message (no crash)",r==0 and '1,125' in lg,lg)
print("TEST 5: explicit gross/net ratio")
hd=json.load(open(os.path.join(ROOT,'data','plant_heads.json'),encoding='utf-8')); hp=hd['Plants']
n_def,_g,est_def,r_def=W.k_values(hp,['SFIKIA','THESAVROS'],None)
n_exp,_g2,est_exp,r_exp=W.k_values(hp,['SFIKIA','THESAVROS'],1.20)
check("an explicit ratio is used for plants WITHOUT a documented net head (Sfikia) and reported back",r_exp==1.20 and abs(n_exp['SFIKIA']-2.725*hp['SFIKIA']['GrossHeadM']/1.20*((hp['SFIKIA']['EtaMin']+hp['SFIKIA']['EtaMax'])/2))<1e-6 and 'SFIKIA' in est_exp)
check("plants WITH a documented net head (Thesavros) ignore the ratio",abs(n_exp['THESAVROS']-n_def['THESAVROS'])<1e-9 and 'THESAVROS' not in est_exp)
check("the file's frozen GrossToNetRatio equals the mean of the four documented plants before the Thesavros correction (1.1254)",abs(hd['GrossToNetRatio']-1.125424)<1e-5)
check("the Thesavros correction does not move Sfikia: k(Sfikia) with the file's ratio = k with the old four-plant mean",abs(W.k_values(hp,['SFIKIA'],hd['GrossToNetRatio'])[0]['SFIKIA']-2.725*54/1.125424*0.875)<0.05)
shutil.copy(os.path.join(ROOT,'data','plant_heads.json'),'data/'); open('data/days/2026-07-09.json','w').write('{ broken')
r,lg=cap(W.main); check("corrupt day file is skipped with a message",r==0 and 'δεν διαβάζεται' in lg)
print(f"\n{PASS} passed, {FAIL} failed")
if __name__ == "__main__":
    sys.exit(1 if FAIL else 0)
