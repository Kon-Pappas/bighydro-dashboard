#!/usr/bin/env python3
"""Τρέχει όλα τα Python tests του pipeline. Έξοδος 0 μόνο αν περάσουν όλα.
Χρήση (από τη ρίζα του repo):  python tests/run_all.py"""
import os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
TESTS = ["test_v3.py", "test_only.py", "test_perunit.py", "test_pump.py", "test_wb.py", "test_psh.py", "test_units.py", "test_clim.py", "test_admie_diag.py", "test_entsoe.py"]


def main():
    total_pass = total_fail = 0
    failed = []
    for t in TESTS:
        r = subprocess.run([sys.executable, os.path.join(HERE, t)], capture_output=True, text=True, cwd=HERE)
        out = r.stdout + r.stderr
        m = re.findall(r"(\d+) passed, (\d+) failed", out)
        p, f = (int(m[-1][0]), int(m[-1][1])) if m else (0, 1)
        total_pass += p
        total_fail += f
        status = "OK " if r.returncode == 0 and f == 0 and m else "ΑΠΟΤΥΧΙΑ"
        print(f"{status:<9} {t:<18} {p} passed, {f} failed")
        if status != "OK ":
            failed.append(t)
            print("\n".join("      " + l for l in out.splitlines() if "FAIL" in l or "Traceback" in l or "Error" in l)[:3000])
    print(f"\nΣΥΝΟΛΟ: {total_pass} passed, {total_fail} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
