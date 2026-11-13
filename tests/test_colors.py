import sys, os, re
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
PASS = FAIL = 0
def check(n, c, e=""):
    global PASS, FAIL
    if c: PASS += 1; print("  PASS", n)
    else: FAIL += 1; print("  FAIL", n, e)

HTML = open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
CSS = "\n".join(re.findall(r"<style[^>]*>(.*?)</style>", HTML, re.S))
JS = HTML[HTML.index("<script>"):HTML.rindex("</script>")]

# Η παλέτα της σελίδας (D108): ένα χρώμα, μία σημασία.
ACCENT = {"#a78bfa", "#7c3aed", "#c4b5fd"}                     # διακόσμηση ΜΟΝΟ: τίτλος, tabs, κουμπιά, focus, «Last Update»
STATUS = {"#34d399", "#fbbf24", "#f87171"}                      # κατάσταση ΜΟΝΟ: πλήρες ✓ / προειδοποίηση / σφάλμα
DATA = {"#38bdf8", "#fb923c", "#f472b6", "#94a3b8", "#f1f5f9", "#cbd5e1", "#e2e8f0", "#2563eb", "#e0f2fe", "#60a5fa"}

def var(name):
    m = re.search(r"--" + re.escape(name) + r"\s*:\s*([^;}]+)", CSS)
    return m.group(1).strip().lower() if m else None
def resolve(v):
    v = (v or "").strip().lower()
    m = re.fullmatch(r"var\(--([a-z0-9]+)\)", v)
    return var(m.group(1)) if m else v
def rule(sel):
    """Όλοι οι κανόνες με αυτόν τον επιλογέα συγχωνεύονται (ο ίδιος επιλογέας εμφανίζεται και σε ομαδοποιημένους κανόνες, π.χ. .sc1,.sc2,…{fill:none})."""
    out = None
    for m in re.finditer(r"(?<![\w.#-])" + re.escape(sel) + r"(?![\w-])\s*\{([^}]*)\}", CSS):
        out = out or {}
        out.update({k.strip(): v.strip() for k, v in (d.split(":", 1) for d in m.group(1).split(";") if ":" in d)})
    return out
def colour_of(sel):
    r = rule(sel)
    if r is None: return None
    for k in ("stroke", "fill", "background", "color"):
        if k in r and r[k] != "none": return resolve(r[k])
    return None

print("TEST 1: the variables — the data colours are not the accent and not a status colour")
c1, c2, c3 = var("c1"), var("c2"), var("c3")
check("--c1 (measured / official) is sky blue, --c2 (plan / model / assumption) is orange, --c3 (recycled water) is pink", (c1, c2, c3) == ("#38bdf8", "#fb923c", "#f472b6"), (c1, c2, c3))
check("none of --c1/--c2/--c3 is the accent or a status colour", not ({c1, c2, c3} & (ACCENT | STATUS)), (c1, c2, c3))
check("--c2 is not the warning colour and --c3 is not the ok colour (they used to be, and meant nine things)", c2 != var("warn") and c3 != var("ok") and c1 != var("acc"))
check("the status colours keep their meaning: ok green, warn yellow, bad red", (var("ok"), var("warn"), var("bad")) == ("#34d399", "#fbbf24", "#f87171"))
print("TEST 2: every chart class (lines, bars, bands, scenario lines, bars of the days of cover) uses a data colour")
CLS = ["s1", "s2", "s3", "s4", "b1", "b2", "b3", "bd1", "bd2", "smed", "s1l", "s2l", "sc1", "sc2", "sc3", "sc4", "sc5", "dbar"]
cols = {c: colour_of("." + c) for c in CLS}
check("all chart classes exist and have a colour", all(cols.values()), [c for c, v in cols.items() if not v])
check("…and each colour belongs to the data palette (no accent, no yellow / red / green)", all(v in DATA for v in cols.values() if v), {c: v for c, v in cols.items() if v and v not in DATA})
check("the reference band (« normal of previous years ») is neutral grey, not the accent", cols["bd1"] == cols["bd2"] == "#94a3b8")
check("the zero-day marker keeps the status red (it IS a status)", colour_of(".sz") == "#f87171" or resolve(rule(".sz")["fill"]) == "#f87171")
check("the legend dots follow the three data variables", [resolve(rule(".dot.c%d" % i)["background"]) for i in (1, 2, 3)] == [c1, c2, c3])
print("TEST 3: the script — no accent in any chart code, and only two deliberate uses of a status colour")
check("no accent colour (hex, rgba or var(--acc)) anywhere in the script", not re.search(r"#a78bfa|167,\s*139,\s*250|#c4b5fd|#7c3aed|var\(--acc", JS, re.I), re.findall(r".{30}(?:#a78bfa|167,139,250|#c4b5fd|#7c3aed|var\(--acc).{20}", JS)[:3])
check("no status hex colour in the script (#fbbf24, #34d399, #f87171)", not re.search(r"#fbbf24|#34d399|#f87171", JS, re.I), re.findall(r".{30}(?:#fbbf24|#34d399|#f87171).{20}", JS)[:3])
st = re.findall(r"var\(--(?:ok|warn|bad)\)", JS)
check("the script uses a status variable in exactly two places: the zero-day legend (bad) and the over-100 % fill (warn)", sorted(st) == ["var(--bad)", "var(--warn)"] and "['var(--bad)',t('av_zero_day')]" in JS and "(over?'background:var(--warn)':'')" in JS, st)
check("the day the user picked is drawn in white, not in a data colour (line and dot)", 'fill="#f1f5f9" stroke="none"/>' in JS and 'stroke="#f1f5f9" stroke-dasharray="3 3"/>' in JS)
print("TEST 4: the six rivers (all-rivers chart) and the pumping bars")
m = re.search(r"var RCOL=\[([^\]]*)\]", JS); rc = [x.lower() for x in re.findall(r"'(#[0-9a-fA-F]{6})'", m.group(1))] if m else []
check("six different river colours, all from the data palette (the accepted limit: they are closer to each other than before)", len(rc) == 6 and len(set(rc)) == 6 and set(rc) <= DATA, rc)
check("the recycled water of the pumped-storage plants is pink in the bars AND in the legend (and the bar class b3 is --c3)", "cls:'b3',color:'#f472b6',name:t('psh_rec')" in JS and "['#f472b6',t('psh_rec')]" in JS and cols["b3"] == "#f472b6")
print("TEST 5: the inflow scenarios — the colour in the legend and in the tooltip equals the colour of the line")
sc = {}
for i, id_ in enumerate(["zero", "recent", "dry", "typ", "wet"], 1):
    mm = re.search(r"\{id:'" + id_ + r"',cls:'sc" + str(i) + r"',col:'(#[0-9a-fA-F]{6})'", JS); sc[id_] = (mm.group(1).lower() if mm else None, cols["sc%d" % i])
check("each of the five scenarios has the same colour in the script (legend, tooltip) and in the CSS (line)", all(a and a == b for a, b in sc.values()), sc)
check("the five scenario colours are all different", len({a for a, b in sc.values()}) == 5)
check("« recent » (an assumption) is the orange of plan / model / assumption, « zero » is neutral grey, the three others are the blue scale", sc["recent"][0] == c2 and sc["zero"][0] == "#94a3b8" and {sc[k][0] for k in ("dry", "typ", "wet")} == {"#2563eb", "#38bdf8", "#e0f2fe"})
print("TEST 5b: the header and the decoration")
check("« Next Update » is neutral (as in the BESS page), not the ok green; « Last Update » stays in the accent", colour_of(".upd .nx") == "#e2e8f0" and re.search(r"\.upd strong\{color:var\(--acc\)\}", CSS) is not None, colour_of(".upd .nx"))
check("the accent is still used for what it is for (over-correction guard): the title, the active tab, the focus ring", re.search(r"h1\{[^}]*color:var\(--acc\)", CSS) and re.search(r"nav\.tabs button\.on\{[^}]*var\(--acc2\)", CSS) and "outline:2px solid var(--acc)" in CSS)
print(f"\n{PASS} passed, {FAIL} failed")
if __name__ == "__main__":
    sys.exit(1 if FAIL else 0)
