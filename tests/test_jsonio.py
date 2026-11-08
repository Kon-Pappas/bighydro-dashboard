import sys, os, json, tempfile, time
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import jsonio as J
PASS = FAIL = 0
def check(n, c, e=""):
    global PASS, FAIL
    if c: PASS += 1; print("  PASS", n)
    else: FAIL += 1; print("  FAIL", n, e)
d = tempfile.mkdtemp(); p = os.path.join(d, "sub", "x.json")
print("TEST 1: first write, identical content, timestamps")
doc = {"Schema": 1, "Generated": "2026-11-08T10:00:00", "Rows": [1, 2, 3], "Note": "ελληνικά"}
check("a missing file (and its folder) is created; returns True", J.write_json_if_changed(p, doc) is True and json.load(open(p, encoding="utf-8")) == doc)
raw1 = open(p, "rb").read()
check("the text is UTF-8 and ends with a newline", "ελληνικά".encode("utf-8") in raw1 and raw1.endswith(b"\n"))
time.sleep(0.05)
check("same content with a NEWER Generated -> not rewritten (False), bytes and timestamp unchanged", J.write_json_if_changed(p, dict(doc, Generated="2026-11-08T11:00:00")) is False and open(p, "rb").read() == raw1)
print("TEST 2: real changes are written")
check("a changed value -> written (True) with the new timestamp", J.write_json_if_changed(p, dict(doc, Rows=[1, 2, 4], Generated="2026-11-08T12:00:00")) is True and json.load(open(p, encoding="utf-8"))["Generated"] == "2026-11-08T12:00:00")
check("a new top-level key is a change", J.write_json_if_changed(p, dict(doc, Rows=[1, 2, 4], Extra=1, Generated="2026-11-08T13:00:00")) is True and json.load(open(p, encoding="utf-8")).get("Extra") == 1)
check("a removed key is a change", J.write_json_if_changed(p, {"Schema": 1, "Generated": "z", "Rows": [1, 2, 4]}) is True and "Extra" not in json.load(open(p, encoding="utf-8")))
print("TEST 3: only the TOP level timestamps are ignored")
n = {"Schema": 1, "Generated": "a", "Weeks": [{"Updated": "t1", "MWh": 1}]}
J.write_json_if_changed(p, n)
check("a nested 'Updated' is DATA: changing it is a change", J.write_json_if_changed(p, {"Schema": 1, "Generated": "a", "Weeks": [{"Updated": "t2", "MWh": 1}]}) is True)
check("key order is irrelevant", J.write_json_if_changed(p, {"Weeks": [{"MWh": 1, "Updated": "t2"}], "Generated": "b", "Schema": 1}) is False)
check("a list in the new doc equals the tuple it was written from", J.write_json_if_changed(p, {"Schema": 1, "Generated": "c", "Weeks": ({"Updated": "t2", "MWh": 1},)}) is False)
print("TEST 4: broken files, indent, no leftovers")
open(p, "w").write("{ broken"); check("a corrupt existing file is rewritten", J.write_json_if_changed(p, n) is True and json.load(open(p, encoding="utf-8")) == n)
open(p, "w").write(""); check("an empty existing file is rewritten", J.write_json_if_changed(p, n) is True)
J.write_json_if_changed(p, {"a": [1]}, indent=1); check("indent is honoured", b'\n "a"' in open(p, "rb").read())
check("no .tmp file is left behind", not [f for f in os.listdir(os.path.dirname(p)) if f.endswith(".tmp")])
J.write_json_if_changed(os.path.join(d, "list.json"), [1, 2]); check("a top-level list is supported (no timestamps to ignore)", J.write_json_if_changed(os.path.join(d, "list.json"), [1, 2]) is False and J.write_json_if_changed(os.path.join(d, "list.json"), [1, 3]) is True)
print(f"\n{PASS} passed, {FAIL} failed")
if __name__ == "__main__":
    sys.exit(1 if FAIL else 0)
