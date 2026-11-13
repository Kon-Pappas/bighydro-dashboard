import sys, os, re, glob
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import write_meta as M
PASS = FAIL = 0
def check(n, c, e=""):
    global PASS, FAIL
    if c: PASS += 1; print("  PASS", n)
    else: FAIL += 1; print("  FAIL", n, e)
WF = sorted(glob.glob(os.path.join(ROOT, ".github", "workflows", "*.yml")))
def code_lines(path):
    """Οι γραμμές του workflow ΧΩΡΙΣ τα σχόλια (το σχόλιο της κορυφής αναφέρει σκόπιμα το `schedule:`)."""
    return [l for l in open(path, encoding="utf-8").read().split("\n") if not l.lstrip().startswith("#")]
print("TEST 1: hub rules for every workflow (D104)")
check("there are workflows to check", len(WF) >= 9, len(WF))
check("NO workflow has a native schedule or cron: runs start only from cron-job.org (comments are ignored)", all(not re.search(r"^\s*(schedule|cron)\s*:|-\s*cron\s*:", "\n".join(code_lines(p)), re.M) for p in WF), [os.path.basename(p) for p in WF if re.search(r"^\s*(schedule|cron)\s*:|-\s*cron\s*:", "\n".join(code_lines(p)), re.M)])
DATA = [p for p in WF if os.path.basename(p) != "tests.yml"]
check("every data workflow can be started with workflow_dispatch (cron-job.org calls it through the API) — tests.yml is the only one that runs on pushes", len(DATA) >= 8 and all(re.search(r"^\s*workflow_dispatch\s*:", "\n".join(code_lines(p)), re.M) for p in DATA), [os.path.basename(p) for p in DATA if not re.search(r"^\s*workflow_dispatch\s*:", "\n".join(code_lines(p)), re.M)])
used = {}
for p in WF:
    for u in re.findall(r"uses:\s*(actions/[a-z-]+@v\d+)", "\n".join(code_lines(p))): used.setdefault(u, []).append(os.path.basename(p))
check("actions: only checkout@v5, setup-python@v6, setup-node@v5 (the hub standard; nothing on the Node 20 versions)", set(used) <= {"actions/checkout@v5", "actions/setup-python@v6", "actions/setup-node@v5"}, used)
check("…and every workflow that checks out uses v5, every one that sets up Python uses v6", all("actions/checkout@v5" in "\n".join(code_lines(p)) for p in WF if "actions/checkout@" in "\n".join(code_lines(p))) and all("actions/setup-python@v6" in "\n".join(code_lines(p)) for p in WF if "setup-python@" in "\n".join(code_lines(p))))
print("TEST 2: the fetch workflow")
fp = os.path.join(ROOT, ".github", "workflows", "fetch_data.yml"); raw = open(fp, encoding="utf-8").read(); cl = "\n".join(code_lines(fp))
check("it keeps one run at a time (concurrency group, no cancelling)", "group: bighydro-fetch" in cl and "cancel-in-progress: false" in cl)
check("it keeps the manual inputs (start_date, end_date, only, diagnose)", all(re.search(r"^\s{6}" + k + r":", cl, re.M) for k in ("start_date", "end_date", "only", "diagnose")))
i_meta, i_commit = cl.find("scripts/write_meta.py"), cl.find("Commit and push changes")
i_last_build = max(cl.find("scripts/" + s) for s in ("update_hydro.py", "fetch_entsoe_reservoir.py", "build_water_balance.py", "build_psh.py", "build_unit_status.py", "build_climatology.py", "build_inflow.py", "build_energy_climatology.py"))
check("meta.json is written AFTER every fetching and building step and BEFORE the commit", 0 < i_last_build < i_meta < i_commit, (i_last_build, i_meta, i_commit))
blk = cl[cl.rfind("- name:", 0, i_meta):i_commit]
check("the meta step is non-blocking (a failure there must never lose the data of the run) and passes DIAGNOSE", "continue-on-error: true" in blk and "DIAGNOSE: ${{ inputs.diagnose }}" in blk, blk)
check("the fetching steps are NOT non-blocking (a failed fetch must stop the run before meta.json and the commit)", "continue-on-error" not in cl[cl.find("Run Python script"):cl.find("Fetch ENTSO-E weekly")])
head = "\n".join(l for l in raw.split("\n") if l.lstrip().startswith("#"))
check("the header comment lists the same run times as write_meta.UPDATE_TIMES_ATHENS (one source of truth, the comment cannot drift)", all("%02d:%02d" % t in head for t in M.UPDATE_TIMES_ATHENS), head)
check("the header comment names cron-job.org and says there is no schedule", "cron-job.org" in head and "schedule" in head)
print(f"\n{PASS} passed, {FAIL} failed")
if __name__ == "__main__":
    sys.exit(1 if FAIL else 0)
