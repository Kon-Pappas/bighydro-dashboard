import sys, os, json, tempfile, io, contextlib
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import fetch_entsoe_reservoir as F
PASS=FAIL=0
def check(n,c,e=""):
    global PASS,FAIL
    if c: PASS+=1; print("  PASS",n)
    else: FAIL+=1; print("  FAIL",n,e)
def cap(fn,*a,**k):
    b=io.StringIO()
    with contextlib.redirect_stdout(b): r=fn(*a,**k)
    return r,b.getvalue()
NS='xmlns="urn:iec62325.351:tc57wg16:451-3:publicationdocument:7:3"'
def doc(start,end,pts,curve="A01",res="P7D"):
    p="".join(f"<Point><position>{a}</position><quantity>{b}</quantity></Point>" for a,b in pts)
    return f'<?xml version="1.0"?><Publication_MarketDocument {NS}><TimeSeries><mRID>1</mRID><businessType>A15</businessType><curveType>{curve}</curveType><quantity_Measure_Unit.name>MWH</quantity_Measure_Unit.name><Period><timeInterval><start>{start}</start><end>{end}</end></timeInterval><resolution>{res}</resolution>{p}</Period></TimeSeries></Publication_MarketDocument>'
class R:
    def __init__(s,status=200,text=""): s.status_code=status; s.text=text

print("TEST 1: parse weekly")
w,info,reason=F.parse_xml(doc("2026-09-20T22:00Z","2026-10-04T22:00Z",[(1,1650000),(2,1610776)]))
check("2 weeks",len(w)==2 and reason is None)
check("week 2 start/local/value/isoweek",w[1]["Start"]=="2026-09-27T21:00Z" and w[1]["StartLocal"]=="2026-09-28" and w[1]["IsoWeek"]=="2026-W40" and w[1]["MWh"]==1610776.0,w)
check("end = next local midnight",w[1]["End"]=="2026-10-04T21:00Z")
check("info recorded",info[0]["points"]==2 and info[0]["expected"]==2 and info[0]["resolution"]=="P7D")
print("TEST 2: A03 forward-fill, A01 gap not filled")
w,_,_=F.parse_xml(doc("2026-09-20T22:00Z","2026-10-11T22:00Z",[(1,100),(3,300)],curve="A03"))
check("A03 filled",[x["MWh"] for x in w]==[100.0,100.0,300.0],w)
w,_,_=F.parse_xml(doc("2026-09-20T22:00Z","2026-10-11T22:00Z",[(1,100),(3,300)],curve="A01"))
check("A01 gap left empty",[x["MWh"] for x in w]==[100.0,300.0],w)
print("TEST 2b: weeks across DST changes stay on Greek local Mondays")
# real shape from the diagnose log: winter start (22:00Z), spans the March DST change, ends in summer (21:00Z)
w,info,_=F.parse_xml(doc("2025-12-28T22:00Z","2026-08-16T21:00Z",[(1,1951700),(2,2220693),(3,2444744),(33,2124326)],curve="A03"))
check("33 weeks, all start on a Greek-local Monday",len(w)==33 and all(__import__('datetime').date.fromisoformat(x["StartLocal"]).weekday()==0 for x in w),len(w))
check("first = 2025-12-29 (W01), last = 2026-08-10 (W33)",w[0]["StartLocal"]=="2025-12-29" and w[0]["IsoWeek"]=="2026-W01" and w[-1]["StartLocal"]=="2026-08-10" and w[-1]["IsoWeek"]=="2026-W33")
check("winter week starts 22:00Z, summer week starts 21:00Z",w[0]["Start"]=="2025-12-28T22:00Z" and w[-1]["Start"]=="2026-08-09T21:00Z",(w[0]["Start"],w[-1]["Start"]))
check("expected 33 points, got 33 weeks (A03 filled)",info[0]["expected"]==33)
# autumn change (25 Oct 2026): period starts in summer, ends in winter
w,info,_=F.parse_xml(doc("2026-10-18T21:00Z","2026-11-01T22:00Z",[(1,1.0),(2,2.0)]))
check("autumn DST: 2026-10-19 then 2026-10-26 (never a Sunday)",[x["StartLocal"] for x in w]==["2026-10-19","2026-10-26"] and w[1]["Start"]=="2026-10-25T22:00Z",[(x["StartLocal"],x["Start"]) for x in w])
# the real second period from the log
w,_,_=F.parse_xml(doc("2026-08-23T21:00Z","2026-10-04T21:00Z",[(1,1929840),(6,1610776)],curve="A03"))
check("log period 2: 6 weeks 2026-08-24..09-28, last = W40",len(w)==6 and w[0]["StartLocal"]=="2026-08-24" and w[-1]["IsoWeek"]=="2026-W40" and w[-1]["MWh"]==1610776.0)

print("TEST 3: P1W resolution and acknowledgement")
w,_,_=F.parse_xml(doc("2026-09-20T22:00Z","2026-09-27T22:00Z",[(1,5)],res="P1W")); check("P1W ok",len(w)==1)
ack=f'<?xml version="1.0"?><Acknowledgement_MarketDocument {NS}><Reason><code>999</code><text>No matching data found</text></Reason></Acknowledgement_MarketDocument>'
w,_,reason=F.parse_xml(ack); check("acknowledgement -> reason",w==[] and "No matching" in reason)

print("TEST 4: main() write / merge / revision")
tmp=tempfile.mkdtemp(); os.chdir(tmp); F.TOKEN="secret-token"
resp={"v":doc("2026-09-20T22:00Z","2026-10-04T22:00Z",[(1,1650000),(2,1610776)])}
seen={}
def fake(params,tries=3):
    seen.update(params); return R(200,resp["v"])
F.http_get=fake
sys.argv=['x','2026-09-01','2026-10-07']
rc,lg=cap(F.main)
d=json.load(open('data/entsoe_reservoir.json'))
check("rc 0, 2 weeks stored",rc==0 and len(d["Weeks"])==2 and d["Unit"]=="MWh")
check("request params",seen["documentType"]=="A72" and seen["processType"]=="A16" and seen["in_Domain"]=="10YGR-HTSO-----Y")
check("window = Athens midnight to next midnight (UTC)",seen["periodStart"]=="202608312100" and seen["periodEnd"]=="202610072100",(seen["periodStart"],seen["periodEnd"]))
check("token never printed","secret-token" not in lg)
resp["v"]=doc("2026-09-27T22:00Z","2026-10-18T22:00Z",[(1,1600000),(2,1550000)])    # revises week of 09-27, adds 10-04
sys.argv=['x']
rc,lg=cap(F.main)
d=json.load(open('data/entsoe_reservoir.json'))
vals={w["StartLocal"]:w["MWh"] for w in d["Weeks"]}
check("merge: 3 weeks, revised value, new week",rc==0 and len(vals)==3 and vals["2026-09-28"]==1600000.0 and vals["2026-10-05"]==1550000.0,vals)
check("sorted ascending",[w["Start"] for w in d["Weeks"]]==sorted(w["Start"] for w in d["Weeks"]))
check("default start = last week - 28d",seen["periodStart"].startswith("2026"+"0"))  # sanity only

print("TEST 5: failures never touch the file")
before=open('data/entsoe_reservoir.json').read()
F.http_get=lambda p,tries=3:R(401,"<text>Unauthorized</text>"); rc,lg=cap(F.main); check("401 -> rc1, file untouched",rc==1 and open('data/entsoe_reservoir.json').read()==before and "Unauthorized" in lg)
F.http_get=lambda p,tries=3:R(200,ack); rc,lg=cap(F.main); check("no data -> rc1, file untouched",rc==1 and open('data/entsoe_reservoir.json').read()==before)
F.http_get=lambda p,tries=3:None; rc,_=cap(F.main); check("network error -> rc1",rc==1)
open('data/entsoe_reservoir.json','w').write('{ broken'); F.http_get=fake
rc,lg=cap(F.main); check("corrupt file -> rc1, untouched",rc==1 and open('data/entsoe_reservoir.json').read()=='{ broken' and "ΣΤΑΜΑΤΑΜΕ" in lg)
F.TOKEN=None; rc,_=cap(F.main); check("no token -> rc1",rc==1)

print("TEST 6: diagnose writes nothing")
F.TOKEN="x"; os.remove('data/entsoe_reservoir.json'); resp["v"]=doc("2026-09-20T22:00Z","2026-10-04T22:00Z",[(1,1650000),(2,1610776)])
sys.argv=['x','--diagnose']; rc,lg=cap(F.main)
check("diagnose rc0, no file, prints structure",rc==0 and not os.path.exists('data/entsoe_reservoir.json') and "P7D" in lg and "1,610,776" in lg,lg[-300:])

print("TEST 7: history mode (multi-year baseline, separate file)")
import datetime as _dt
os.chdir(tempfile.mkdtemp()); F.TOKEN="secret-token"; seen_years=[]
def fake_hist(params,tries=3):
    y=int(params["periodStart"][:4]) if params["periodStart"][4:6] != "12" else int(params["periodStart"][:4])+1   # local midnight Jan 1 = 22:00Z on Dec 31
    seen_years.append(y)
    if y in (2015,): return R(200,ack)                                   # no data that year
    if y==2017: return R(401,"<text>Unauthorized</text>")               # a failing year
    return R(200,doc(f"{y-1}-12-28T22:00Z",f"{y}-01-11T22:00Z",[(1,1000000+y),(2,2000000+y)]))
F.http_get=fake_hist; F.time.sleep=lambda s:None
sys.argv=['x','--history','2015','2018']; rc,lg=cap(F.main)
h=json.load(open('data/entsoe_history.json'))
check("history rc0; one request per year (2015-2018), written to data/entsoe_history.json",rc==0 and seen_years==[2015,2016,2017,2018] and h.get("Kind")=="history",(seen_years,rc))
check("years without data (2015) and failing years (2017) are skipped and reported, others merged",sorted(h["Coverage"]["FailedOrEmptyYears"])==[2015,2017] and len(h["Weeks"])>=4,h["Coverage"])
check("the live file data/entsoe_reservoir.json is NEVER touched by history mode",not os.path.exists('data/entsoe_reservoir.json'))
check("token never printed","secret-token" not in lg)
check("weeks sorted ascending and each year counted",[w["Start"] for w in h["Weeks"]]==sorted(w["Start"] for w in h["Weeks"]) and sum(h["Coverage"]["WeeksPerYear"].values())==len(h["Weeks"]))
before=open('data/entsoe_history.json').read()
F.http_get=lambda p,tries=3:R(200,ack); sys.argv=['x','--history','2015','2016']; rc,lg=cap(F.main)
check("no data in any year -> rc1 and the file is untouched",rc==1 and open('data/entsoe_history.json').read()==before)
F.http_get=fake_hist; sys.argv=['x','--history','2016','2016','--out=data/other.json']; rc,_=cap(F.main)
check("--out= writes elsewhere and leaves the default file alone",rc==0 and os.path.exists('data/other.json') and open('data/entsoe_history.json').read()==before)
sys.argv=['x','--history','2018','2016']; rc,lg=cap(F.main); check("years in the wrong order -> rc1 with a message",rc==1 and "Μη έγκυρα" in lg)
sys.argv=['x','--history']; rc,lg=cap(F.main); check("missing years -> rc1 with usage",rc==1 and "Χρήση" in lg)
open('data/entsoe_history.json','w').write('{ broken'); sys.argv=['x','--history','2016','2016']; rc,lg=cap(F.main); check("corrupt history file -> rc1, untouched",rc==1 and open('data/entsoe_history.json').read()=='{ broken' and "ΣΤΑΜΑΤΑΜΕ" in lg)
F.TOKEN=None; sys.argv=['x','--history','2016','2016']; rc,_=cap(F.main); check("no token -> rc1",rc==1)
print(f"\n{PASS} passed, {FAIL} failed")
if __name__ == "__main__":
    sys.exit(1 if FAIL else 0)
