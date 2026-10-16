import sys, io, os, json, tempfile, contextlib, runpy
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, os.path.join(ROOT, 'scripts'))
b=io.StringIO()
with contextlib.redirect_stdout(b): ns=runpy.run_path(os.path.join(HERE,'test_v3.py'))     # reuse fixtures
U=ns['U']; Resp=ns['Resp']; make_fake=ns['make_fake']; ALL=ns['ALL']; MCP_DOC=ns['MCP_DOC']
from datetime import date
PASS=FAIL=0
def check(n,c,e=""):
    global PASS,FAIL
    if c: PASS+=1; print("  PASS",n)
    else: FAIL+=1; print("  FAIL",n,e)
def cap(fn,*a,**k):
    s=io.StringIO()
    with contextlib.redirect_stdout(s): r=fn(*a,**k)
    return r,s.getvalue()
def recording(inner,log):
    def f(url,params=None,tries=3,what="",use_session=True):
        if url==U.API_FILES: log.append(params["FileCategory"])
        if url==U.ENTSOE_URL: log.append("ENTSOE")
        return inner(url,params,tries,what,use_session)
    return f
U.ENTSOE_TOKEN="x"; D=date(2026,10,4)

print("TEST 1: --only reservoir requests ONLY the reservoir file")
calls=[]; U.http_get=recording(make_fake(ALL,MCP_DOC),calls)
(rec,got),_=cap(U.process_day,D,None,{}, {"reservoir"})
check("only ReservoirFillingRate requested",set(calls)=={"ReservoirFillingRate"},calls)
check("record has reservoir data, no Hourly",rec["ReservoirTotalRate"]==43.62 and "Hourly" not in rec and got)
check("status: reservoir ok, others missing",rec["Meta"]["Status"]=={"reservoir":"ok","scada":"missing","isp":"missing","resmv":"missing","mcp":"missing"},rec["Meta"]["Status"])

print("TEST 2: --only reservoir on a full day keeps all hourly data")
U.http_get=make_fake(ALL,MCP_DOC); (full,_),_=cap(U.process_day,D,None,{})
calls=[]; U.http_get=recording(make_fake(ALL,MCP_DOC),calls)
(again,_),_=cap(U.process_day,D,json.loads(json.dumps(full)),{},{"reservoir"})
check("hourly untouched",U.content_key(again)==U.content_key(full))
check("only reservoir requested",set(calls)=={"ReservoirFillingRate"},calls)

print("TEST 3: --only scada,isp requests exactly those (+ previous-day ISP), no MCP")
calls=[]; U.http_get=recording(make_fake(ALL,MCP_DOC),calls)
(r3,_),_=cap(U.process_day,D,None,{},{"scada","isp"})
check("categories",set(calls)=={"SystemRealizationSCADA","ISP2ISPResults"} and "ENTSOE" not in calls and calls.count("ISP2ISPResults")==2,calls)
check("MCP/RESMV/Reservoir stay empty",r3["Hourly"][0]["MCP_GR"] is None and r3["Hourly"][0]["SCADA_SmallHydro"] is None and "Reservoir" not in r3)

print("TEST 4: main() with --only / ONLY env / bad value")
tmp=tempfile.mkdtemp(); os.chdir(tmp)
calls=[]; U.http_get=recording(make_fake(ALL,MCP_DOC),calls)
sys.argv=['x','--only=reservoir','2026-10-02','2026-10-04']; rc,lg=cap(U.main)
files=sorted(os.listdir('data/days'))
check("3 reservoir-only day files",rc==0 and files==['2026-10-02.json','2026-10-03.json','2026-10-04.json'] and set(calls)=={"ReservoirFillingRate"},(rc,files,set(calls)))
check("log shows the restriction","[μόνο: reservoir]" in lg)
check("reservoir_history built from reservoir-only days",len(json.load(open('data/reservoir_history.json')))==3)
os.environ['ONLY']='scada'; calls.clear(); sys.argv=['x','2026-10-04']; rc,_=cap(U.main)
check("ONLY env respected",rc==0 and set(calls)=={"SystemRealizationSCADA"},set(calls))
d4=json.load(open('data/days/2026-10-04.json'))
check("scada added, reservoir kept",d4["Hourly"][5]["SCADA_Kremasta"]==105.0 and d4["ReservoirTotalRate"]==43.62)
os.environ['ONLY']='reservoir,banana'; sys.argv=['x','2026-10-04']; rc,lg=cap(U.main)
check("unknown source -> rc 1 with message",rc==1 and "άγνωστη πηγή" in lg and "banana" in lg)
os.environ.pop('ONLY')
sys.argv=['x','2026-10-04']; calls.clear(); rc,_=cap(U.main)
check("default (no --only) still requests all sources",{"ReservoirFillingRate","SystemRealizationSCADA","ISP2ISPResults","RESMV","ENTSOE"}<=set(calls),set(calls))

print("TEST 5: fetch_entsoe_reservoir START_DATE/END_DATE env")
import fetch_entsoe_reservoir as F
F.TOKEN="x"; seen={}
NS='xmlns="urn:iec62325.351:tc57wg16:451-3:publicationdocument:7:3"'
xml=f'<?xml version="1.0"?><Publication_MarketDocument {NS}><TimeSeries><curveType>A01</curveType><Period><timeInterval><start>2026-08-23T21:00Z</start><end>2026-08-30T21:00Z</end></timeInterval><resolution>P7D</resolution><Point><position>1</position><quantity>1929840</quantity></Point></Period></TimeSeries></Publication_MarketDocument>'
class R:
    status_code=200; text=xml
F.http_get=lambda p,tries=3:(seen.update(p),R())[1]
os.chdir(tempfile.mkdtemp()); os.environ['START_DATE']='2026-01-01'; os.environ['END_DATE']='2026-05-31'; sys.argv=['x']
rc,_=cap(F.main)
check("env window used",rc==0 and seen["periodStart"]=="202512312200" and seen["periodEnd"]=="202605312100",(seen.get("periodStart"),seen.get("periodEnd")))
os.environ.pop('START_DATE'); os.environ.pop('END_DATE')
print(f"\n{PASS} passed, {FAIL} failed")
if __name__ == "__main__":
    sys.exit(1 if FAIL else 0)
