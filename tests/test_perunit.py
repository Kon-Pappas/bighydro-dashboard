import sys, io, os, json, tempfile, contextlib, runpy
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, os.path.join(ROOT, 'scripts'))
b=io.StringIO()
with contextlib.redirect_stdout(b): ns=runpy.run_path(os.path.join(HERE,'test_v3.py'))
U=ns['U']; make_fake=ns['make_fake']; ALL=ns['ALL']; MCP_DOC=ns['MCP_DOC']; xlsx_bytes=ns['xlsx_bytes']; Resp=ns['Resp']
import numpy as np, pandas as pd
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
U.ENTSOE_TOKEN="x"; D=date(2026,10,4)

print("TEST 1: small hydro units stored separately; OtherHydro still their sum")
U.http_get=make_fake(ALL,MCP_DOC); (rec,got),_=cap(U.process_day,D,None,{}); H=rec["Hourly"]
check("Stratos II / Makrochori / Louros / Gkiona",all(h["SCADA_Stratos2"]==1.0 and h["SCADA_Makrochori"]==4.0 and h["SCADA_Louros"]==0.0 and h["SCADA_Gkiona"]==1.0 for h in H),H[0])
check("OtherHydro unchanged (= sum = 6)",all(h["SCADA_OtherHydro"]==6.0 for h in H))
check("key layout contains the new fields",all(k in H[0] for k in ("ISP_PumpSfikia","ISP_PumpThesavros","SCADA_Stratos2")))
check("scada status counts the new fields (all present)",rec["Meta"]["Status"]["scada"] in("ok","partial"))

print("TEST 2: ISP pump per plant, shifted to Greek local clock like the other ISP series")
check("ISP_PumpSfikia = 5 MW every hour incl. H01 (prev-day file used)",all(h["ISP_PumpSfikia"]==5.0 for h in H),[h["ISP_PumpSfikia"] for h in H][:3])
check("ISP_PumpThesavros = 40 MW (only THESAVROS1_PUMP in the fixture)",all(h["ISP_PumpThesavros"]==40.0 for h in H))
check("ISP_Pump total still = Sfikia + Thesavros",all(h["ISP_Pump"]==h["ISP_PumpSfikia"]+h["ISP_PumpThesavros"] for h in H))
U.http_get=make_fake(ALL,MCP_DOC,missing={("ISP2ISPResults","2026-10-03")}); (r2,_),_=cap(U.process_day,D,None,{})
check("missing D-1 ISP file -> H01 null for the new pump fields too",r2["Hourly"][0]["ISP_PumpSfikia"] is None and r2["Hourly"][1]["ISP_PumpSfikia"]==5.0)

print("TEST 3: ISP file without a Sfikia pump row")
rows=[]
def add(l,q): rows.append([l]+list(q))
add("THESAVROS1_PUMP",[-40]*96); add("THESAVROS1",[10]*96); add("KREMASTA",list(np.repeat(np.arange(24)*10.0,4)))
isp_nosf=xlsx_bytes({"ISP":pd.DataFrame(rows)})
orig=make_fake(ALL,MCP_DOC)
def fake(url,params=None,tries=3,what="",use_session=True):
    if url.endswith(".xlsx") and "ISP2ISPResults" in url: return Resp(content=isp_nosf)
    return orig(url,params,tries,what,use_session)
U.http_get=fake; (r3,lg),log3=cap(U.process_day,D,None,{})
check("Sfikia pump None, Thesavros present, total = Thesavros",r3["Hourly"][3]["ISP_PumpSfikia"] is None and r3["Hourly"][3]["ISP_PumpThesavros"]==40.0 and r3["Hourly"][3]["ISP_Pump"]==40.0)

print("TEST 4: --only isp adds the pump fields without touching SCADA / reservoir data; existing values kept")
U.http_get=make_fake(ALL,MCP_DOC); (full,_),_=cap(U.process_day,D,None,{})
old=json.loads(json.dumps(full))
for h in old["Hourly"]:                       # simulate a file written before this change
    for k in ("ISP_PumpSfikia","ISP_PumpThesavros","SCADA_Stratos2","SCADA_Makrochori","SCADA_Louros","SCADA_Gkiona"): h[k]=None
(upd,_),_=cap(U.process_day,D,old,{},{"isp"})
check("pump fields filled by --only isp",upd["Hourly"][5]["ISP_PumpSfikia"]==5.0 and upd["Hourly"][5]["ISP_PumpThesavros"]==40.0)
check("SCADA small-hydro fields NOT touched by --only isp",upd["Hourly"][5]["SCADA_Stratos2"] is None)
(upd2,_),_=cap(U.process_day,D,upd,{},{"scada"})
check("--only scada fills the small hydro units",upd2["Hourly"][5]["SCADA_Stratos2"]==1.0 and upd2["Hourly"][5]["SCADA_Gkiona"]==1.0)
check("everything else identical to a full run",U.content_key(upd2)==U.content_key(full))

print("TEST 5: small hydro inside the renewables block (rows ending in (ΜΥΗΣ))")
U.http_get=make_fake(ALL,MCP_DOC); (rr,_),_=cap(U.process_day,D,None,{})
check("SCADA_ResSmallHydro = sum of both (ΜΥΗΣ) rows = 2.0 MW every hour",all(h["SCADA_ResSmallHydro"]==2.0 for h in rr["Hourly"]),rr["Hourly"][0].get("SCADA_ResSmallHydro"))
check("it is NOT part of TotalHydro reconciliation (OtherHydro unchanged = 6)",all(h["SCADA_OtherHydro"]==6.0 for h in rr["Hourly"]))
check("scada status unaffected by the optional field",rr["Meta"]["Status"]["scada"] in ("ok","partial"))
print(f"\n{PASS} passed, {FAIL} failed")
if __name__ == "__main__":
    sys.exit(1 if FAIL else 0)
