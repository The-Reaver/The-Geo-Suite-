"""ci_verify_geo.py, a self-contained GEO test battery for GitHub Actions.

A standalone copy of the relevant part of the monorepo's root verify.py, scoped to this
repository (projects/geo_platform) alone, since this repository has its own git remote
and its own CI checkout does not include the parent monorepo's verify.py. Keep this file's
detection logic in sync with root verify.py's run_one() if that function changes. The two
stay intentionally duplicated rather than shared, since this repo gets checked out standalone
in CI with no access to the parent monorepo's files.

    python ci_verify_geo.py

Exit code 0 means every test file in tests/ is green. Non-zero means at least one is red.
"""

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
TESTS_DIR = os.path.join(ROOT, "tests")

BOOTSTRAP = (
    "import sys, types; from unittest.mock import MagicMock; "
    "sys.modules['anthropic'] = MagicMock(); "
    "import runpy; runpy.run_path(sys.argv[1], run_name='__main__')"
)


def find_tests(directory):
    if not os.path.isdir(directory):
        return []
    return sorted(
        os.path.join(directory, f)
        for f in os.listdir(directory)
        if f.startswith("test_") and f.endswith(".py")
    )


def run_one(path):
    try:
        res = subprocess.run(
            [sys.executable, "-c", BOOTSTRAP, path],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=300,
        )
    except subprocess.TimeoutExpired:
        return False, "TIMEOUT after 300s"
    out = (res.stdout or "") + (res.stderr or "")
    if res.returncode != 0:
        # Prefer the last line of stdout: every standalone test runner in this
        # battery prints its own PASS/FAIL lines and summary there. Concatenating
        # stdout+stderr wholesale (as `out` does, for the marker scans below) put
        # a stray stderr-only warning (e.g. a DeprecationWarning emitted at import
        # time) after ALL of stdout, so it looked like the last line of output and
        # masked the real failure reason. Only fall back to stderr's tail when
        # stdout is empty, e.g. a crash before the file printed anything at all.
        stdout_stripped = (res.stdout or "").strip()
        if stdout_stripped:
            tail = stdout_stripped.splitlines()[-1]
        else:
            stderr_stripped = (res.stderr or "").strip()
            tail = stderr_stripped.splitlines()[-1] if stderr_stripped else "no output"
        return False, f"exit {res.returncode}: {tail}"
    for line in out.splitlines():
        stripped = line.strip()
        if stripped.startswith("FAIL") or stripped.startswith("Error:"):
            return False, f"output line starts with a red marker: {stripped[:120]!r}"
        if "Traceback (most recent call last)" in line:
            return False, f"output contained {'Traceback (most recent call last)'!r}"
    try:
        src = open(path, encoding="utf-8").read()
    except OSError:
        src = ""
    if "__main__" not in src:
        return False, "not standalone-runnable: no __main__ runner"
    has_pytest_import = any(
        line.strip().startswith("import pytest") or line.strip().startswith("from pytest")
        for line in src.splitlines()
    )
    if has_pytest_import:
        return False, "imports pytest: this battery is pytest-free and standalone"
    ran_evidence = any(m in out for m in ("passed", "PASS", "\nOK", "ok", "0 failed"))
    if not ran_evidence:
        return False, "exited 0 but printed no sign any test ran, possible false green"
    return True, "green"


def main():
    tests = find_tests(TESTS_DIR)
    if not tests:
        print(f"No test files found at {TESTS_DIR}")
        sys.exit(2)
    green = 0
    for path in tests:
        ok, detail = run_one(path)
        mark = "PASS" if ok else "FAIL"
        name = os.path.basename(path)
        line = f"  [{mark}] {name}"
        if not ok:
            line += f"  <- {detail}"
        print(line)
        green += 1 if ok else 0
    total = len(tests)
    red = total - green
    print("=" * 48)
    if red == 0:
        print(f"GREEN. {green}/{total} test files pass.")
        sys.exit(0)
    print(f"RED. {red} of {total} test files failed.")
    sys.exit(1)


if __name__ == "__main__":
    main()
