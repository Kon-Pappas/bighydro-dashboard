import sys, io, json, os, shutil, tempfile, contextlib, copy
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import update_hydro as U
from datetime import date, timedelta

PASS=FAIL=0
def check(name,cond,extra=""):
    global PASS,FAIL
    if cond: PASS+=1; print("  PASS",name)
    else: FAIL+=1; print("  FAIL",name,extra)

def xlsx_bytes(sheets):
    bio=io.BytesIO()
    with pd.ExcelWriter(bio,engine='openpyxl') as w:
        for n,df in sheets.items(): df.to_excel(w,sheet_name=n,header=False,index=False)
    return bio.getvalue()

# ---------------- fixtures ----------------
EXTRA=6  # Stratos2 1 + Makrochori 4 + Louros 0 + Gkiona 1
def make_scada(total_shift=0):
    rows=[["hdr"]+["x"]*25]
    def add(label,vals): rows.append(["id",label]+list(vals))
    add("ΚΡΕΜΑΣΤΆ",[100+h for h in range(24)])
    add("ΚΑΣΤΡΑΚΙ",[50]*24); add("ΣΤΡΑΤΟΣ 1",[75]*24)
    add("ΣΤΡΑΤΟΣ 2",[1]*24); add("ΜΑΚΡΟΧΩΡΙ",[4]*24); add("ΛΟΥΡΟΣ",[0]*24); add("ΓΚΙΩΝΑ",[1]*24)
    add("ΠΟΥΡΝΑΡΙ",[10]*24); add("ΠΟΥΡΝΑΡΙ 2",[2]*24)
    add("ΑΓΡΑΣ",[1.0]*20+[np.nan]*4)
    add("ΘΗΣΑΥΡΟΣ",[0]*24)
    add("TOTAL PUMPING",[300]*24)
    add("ΑΥΛΑΚΙ (ΜΥΗΣ)",[1.5]*24); add("ΒΟΡΕΙΟ ΜΥΗΣ (ΜΥΗΣ)",[0.5]*24)
    add("TOTAL HYDRO",[100+h+50+75+10+2+(1 if h<20 else 0)+EXTRA+total_shift for h in range(24)])
    return xlsx_bytes({"System_Production":pd.DataFrame(rows)})

def make_isp(tag):
    rows=[]
    def add(label,q): rows.append([label]+list(q))
    add("THESAVROS1_PUMP",[-40]*96)
    add("THESAVROS1",[10]*96); add("THESAVROS2",[20]*96); add("THESAVROS3",[30]*96)
    add("KREMASTA",list(np.repeat(tag*1000+np.arange(24)*10.0,4)))
    add("SFIKIA_PUMP",[-5]*96)
    add("STRATOS1",[60]*96)
    return xlsx_bytes({"ISP":pd.DataFrame(rows)})

def make_resmv():
    df=pd.DataFrame({"ΩΡΑ":range(1,25),"ΜΥΗΣ ΕΝΕΡΓΕΙΑ KWh":[24000+h*1000 for h in range(24)]})
    bio=io.BytesIO(); df.to_excel(bio,index=False); return bio.getvalue()

def make_reservoir():
    rows=[["","Reservoir","Rate","","","","",""]]
    vals={"ASOMATA":.777,"ILARIONAS":.1536,"KASTRAKI":1.2515,"KREMASTA":.4194,"LADONAS":.281,"PLASTIRAS":.5485,
          "PLATANOVRYSI":.7105,"POLYFYTO":.4627,"POYRNARI1":.1395,"POYRNARI2":.8369,"P_AOOU":.6935,"SFIKIA":.3929,
          "STRATOS":.3748,"THESAVROS1":.5806}
    for k,v in vals.items(): rows.append(["",k,v,"","","","",""])
    rows.append(["","Filling Rate (%) Total","","",0.4362,"","",""])
    return xlsx_bytes({"Reservoir Filling Rate":pd.DataFrame(rows)})

def series(start,end,pts,res="PT15M"):
    body="".join(f"<Point><position>{p}</position><price.amount>{v}</price.amount></Point>" for p,v in pts)
    return f"<TimeSeries><curveType>A03</curveType><Period><timeInterval><start>{start}</start><end>{end}</end></timeInterval><resolution>{res}</resolution>{body}</Period></TimeSeries>"
def entsoe_doc(*ts):
    return '<?xml version="1.0"?><Publication_MarketDocument xmlns="urn:iec62325.351:tc57wg16:451-3:publicationdocument:7:3">'+"".join(ts)+'</Publication_MarketDocument>'
# real-structure doc for market day 2026-10-04: prev day all 900, current day: h0=100, h1=200, h2.. = 300 (forward-filled)
MCP_DOC=entsoe_doc(series("2026-10-02T22:00Z","2026-10-03T22:00Z",[(1,900)]),
                   series("2026-10-03T22:00Z","2026-10-04T22:00Z",[(1,100),(5,200),(9,300)]))

class Resp:
    def __init__(s,status=200,content=b"",text="",js=None): s.status_code=status;s.content=content;s.text=text;s._js=js
    def json(s): return s._js

ALL={"SystemRealizationSCADA","ISP2ISPResults","RESMV","ReservoirFillingRate"}
def make_fake(cats, entsoe=None, missing=(), total_shift=0):
    def fake(url,params=None,tries=3,what="",use_session=True):
        if url==U.API_FILES:
            c=params["FileCategory"]; ds=params["dateStart"]
            if c not in cats or (c,ds) in missing: return Resp(js=[])
            dd=date.fromisoformat(ds).strftime("%d.%m.%Y")
            return Resp(js=[{"file_path":f"/files/{c}__{ds}.xlsx","file_fromdate":dd,"file_todate":dd}])
        if url.startswith(U.BASE_URL) and "/files/" in url:
            c,ds=os.path.basename(url)[:-5].split("__"); day=date.fromisoformat(ds)
            data={"SystemRealizationSCADA":lambda:make_scada(total_shift),"ISP2ISPResults":lambda:make_isp(day.day),
                  "RESMV":make_resmv,"ReservoirFillingRate":make_reservoir}[c]()
            return Resp(content=data)
        if url==U.ENTSOE_URL:
            return Resp(text=entsoe) if entsoe else Resp(status=401,text="<text>Unauthorized</text>")
        raise AssertionError(url)
    return fake

def capture(fn,*a,**k):
    buf=io.StringIO()
    with contextlib.redirect_stdout(buf): r=fn(*a,**k)
    return r,buf.getvalue()

U.ENTSOE_TOKEN="x"
D=date(2026,10,4)

# ================= 1. clock normalisation =================
print("TEST 1: ISP shifted to Greek local clock, MCP local")
U.http_get=make_fake(ALL,MCP_DOC)
(rec,got),_=capture(U.process_day,D,None,{})
H=rec["Hourly"]
check("ISP H01 = previous market day hour 24 (3230)",H[0]["ISP_Kremasta"]==3*1000+230,H[0]["ISP_Kremasta"])
check("ISP H02 = market hour 1 of D (4000)",H[1]["ISP_Kremasta"]==4000.0)
check("ISP H24 = market hour 23 of D (4220)",H[23]["ISP_Kremasta"]==4000+220.0,H[23]["ISP_Kremasta"])
check("ISP pump constant incl. H01",all(h["ISP_Pump"]==45.0 for h in H))
check("SCADA left on native clock (H06 = 105)",H[5]["SCADA_Kremasta"]==105.0)
check("RESMV left on native clock",H[0]["SCADA_SmallHydro"]==24.0)
check("MCP H01 = previous period last hour (900)",H[0]["MCP_GR"]==900.0,H[0]["MCP_GR"])
check("MCP H02 = market hour 0 (100)",H[1]["MCP_GR"]==100.0)
check("MCP H03 = market hour 1 (200)",H[2]["MCP_GR"]==200.0)
check("MCP H04 = forward-filled (300)",H[3]["MCP_GR"]==300.0)
check("Thesavros ISP summed over 3 units, not pump",H[5]["ISP_Thesavros"]==60.0)

# ================= 2. missing previous ISP =================
print("TEST 2: missing D-1 ISP file")
U.http_get=make_fake(ALL,MCP_DOC,missing={("ISP2ISPResults","2026-10-03")})
(r2,_),log2=capture(U.process_day,D,None,{})
check("ISP H01 null when D-1 missing",r2["Hourly"][0]["ISP_Kremasta"] is None and r2["Hourly"][1]["ISP_Kremasta"]==4000.0)
check("warning logged","λείπει το αρχείο της προηγούμενης" in log2)
U.http_get=make_fake(ALL,MCP_DOC)
(r3,_),_=capture(U.process_day,D,r2,{})
check("later run fills H01",r3["Hourly"][0]["ISP_Kremasta"]==3230.0,r3["Hourly"][0]["ISP_Kremasta"])
U.http_get=make_fake(ALL,MCP_DOC,missing={("ISP2ISPResults","2026-10-03")})
(r4,_),_=capture(U.process_day,D,r3,{})
check("D-1 missing again does NOT erase H01",r4["Hourly"][0]["ISP_Kremasta"]==3230.0)

# ================= 3. extra hydro units + reconciliation =================
print("TEST 3: OtherHydro / TotalHydro / reconciliation")
U.http_get=make_fake(ALL,MCP_DOC)
(rec,_),lg=capture(U.process_day,D,None,{})
H=rec["Hourly"]
check("OtherHydro = 1+4+0+1",all(h["SCADA_OtherHydro"]==6.0 for h in H))
check("TotalHydro stored",H[0]["SCADA_TotalHydro"]==100+50+75+10+2+1+6)
check("no reconciliation warning when consistent","ασυμφωνία" not in lg,lg[-400:])
U.http_get=make_fake(ALL,MCP_DOC,total_shift=10)
(_,_),lg=capture(U.process_day,D,None,{})
check("reconciliation warning when TOTAL HYDRO is 10 MW higher","ασυμφωνία" in lg and "+10.0" in lg)

# ================= 4. storage: per-day files, index, history, monthly =================
print("TEST 4: per-day storage")
tmp=tempfile.mkdtemp(); os.chdir(tmp)
U.http_get=make_fake(ALL,MCP_DOC)
sys.argv=['x','2026-10-02','2026-10-04']
rc,_=capture(U.main)
files=sorted(os.listdir('data/days'))
check("rc 0 and 3 day files",rc==0 and files==['2026-10-02.json','2026-10-03.json','2026-10-04.json'],files)
d4=json.load(open('data/days/2026-10-04.json'))
check("day record schema",list(d4.keys())==["Date","Reservoir","ReservoirTotal","ReservoirTotalRate","Hourly","Meta"] and d4["Meta"]["Schema"]==3)
check("every day has H01 ISP (prev-day file fetched)",all(json.load(open(f'data/days/{f}'))['Hourly'][0]['ISP_Kremasta'] is not None for f in files))
idx=json.load(open('data/index.json'))
check("index desc + count + status",idx["Count"]==3 and [x["Date"] for x in idx["Days"]]==['2026-10-04','2026-10-03','2026-10-02'] and idx["Days"][0]["Status"]["reservoir"]=="ok")
hist=json.load(open('data/reservoir_history.json'))
check("reservoir history ascending",[h["Date"] for h in hist]==['2026-10-02','2026-10-03','2026-10-04'] and hist[0]["ReservoirTotalRate"]==43.62)
mo=json.load(open('data/monthly/2026-10.json'))
exp=sum(100+h for h in range(24))
check("monthly: 3 days, Kremasta SCADA total",mo["DaysCount"]==3 and mo["Totals"]["SCADA_MWh"]["Kremasta"]==round(3*exp,1),mo["Totals"]["SCADA_MWh"]["Kremasta"])
check("monthly: MCP stats present",mo["Days"][2]["MCP"]["max"]==900.0 and mo["Days"][2]["MCP"]["hours"]==24)
check("monthly: other hydro total",mo["Totals"]["SCADA_OtherHydro_MWh"]==round(3*24*6,1))
before={f:open(f'data/days/{f}','rb').read() for f in files}; ib=open('data/index.json','rb').read()
rc,_=capture(U.main)
after={f:open(f'data/days/{f}','rb').read() for f in files}
check("rerun with same data: day files byte-identical (Updated stable)",before==after)
check("index unchanged",ib==open('data/index.json','rb').read())

# ================= 5. failures never erase data =================
print("TEST 5: failing sources")
U.http_get=make_fake(set(),None)
sys.argv=['x','2026-10-02','2026-10-04']
rc,_=capture(U.main)
after2={f:open(f'data/days/{f}','rb').read() for f in files}
check("nothing available -> rc 1, files untouched",rc==1 and after2==before)
U.http_get=make_fake({"SystemRealizationSCADA"},None)
rc,_=capture(U.main)
d4b=json.load(open('data/days/2026-10-04.json'))
check("only SCADA up: ISP/MCP/Reservoir preserved",d4b["Hourly"][0]["ISP_Kremasta"]==3230.0 and d4b["Hourly"][0]["MCP_GR"]==900.0 and d4b["ReservoirTotalRate"]==43.62)

# ================= 6. empty day creates no file =================
print("TEST 6: day with no data")
U.http_get=make_fake(set(),None); sys.argv=['x','2026-10-10']
rc,lg=capture(U.main)
check("no file created, rc 1",rc==1 and not os.path.exists('data/days/2026-10-10.json'))

# ================= 7. corrupt day file =================
print("TEST 7: corrupt day file")
open('data/days/2026-10-03.json','w').write('{ broken')
U.http_get=make_fake(ALL,MCP_DOC); sys.argv=['x','2026-10-02','2026-10-04']
rc,lg=capture(U.main)
check("rc 1 and corrupt file untouched",rc==1 and open('data/days/2026-10-03.json').read()=='{ broken')
check("message explains",'ΣΤΑΜΑΤΑΜΕ' in lg)
check("derived files still rebuilt from the good days",json.load(open('data/index.json'))["Count"]==2)

# ================= 8. dates =================
print("TEST 8: date range")
os.environ.pop('START_DATE',None); os.environ.pop('END_DATE',None)
s,e=U.get_date_range([]); check("default 4 days",(e-s).days==3)
os.environ['START_DATE']='2026-09-16'; os.environ['END_DATE']=''
s,e=U.get_date_range([]); check("START only -> single day",s==e==date(2026,9,16))
print(f"\n{PASS} passed, {FAIL} failed")
if __name__ == "__main__":
    sys.exit(1 if FAIL else 0)
