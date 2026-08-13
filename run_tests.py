""" Test runner for PE++.

Each test in tests/cases/ declares what it expects in header comments:

    // expect: 42          the value main() should return
    // out: hello          a line the program should print (repeat for more lines)
    // error: undefined    compilation must fail and stderr must contain this text

Run with: python run_tests.py
"""

import os
import re
import subprocess
import sys

REPO_DIR = os.path.dirname(os.path.abspath(__file__))
CASES_DIR = os.path.join(REPO_DIR, "tests", "cases")


def parse_directives(path: str) -> dict:
    expected = {"expect": None, "out": [], "error": None}

    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line.startswith("//"):
                continue

            if m := re.match(r"//\s*expect:\s*(-?\d+)", line):
                expected["expect"] = int(m.group(1))
            elif m := re.match(r"//\s*out:\s*(.*)", line):
                expected["out"].append(m.group(1).strip())
            elif m := re.match(r"//\s*error:\s*(.*)", line):
                expected["error"] = m.group(1).strip()

    return expected


def run_case(path: str) -> tuple[bool, str]:
    """ Runs one test file, returns (passed, reason if it failed) """
    expected = parse_directives(path)

    proc = subprocess.run(
        [sys.executable, os.path.join(REPO_DIR, "main.py"), path],
        capture_output=True, text=True, timeout=60
    )

    # Tests that expect a compile/parse error
    if expected["error"] is not None:
        if proc.returncode == 0:
            return False, "expected an error but compilation succeeded"
        if expected["error"] not in proc.stderr:
            return False, f"expected error containing '{expected['error']}', got:\n{proc.stderr.strip()}"
        return True, ""

    # Tests that expect to run
    if proc.returncode != 0:
        return False, f"compilation failed:\n{proc.stderr.strip()}"

    out_lines = proc.stdout.splitlines()

    returned = None
    program_output = []
    for line in out_lines:
        if m := re.match(r"Program returned: (-?\d+)", line):
            returned = int(m.group(1))
        else:
            program_output.append(line.strip())

    if expected["expect"] is not None and returned != expected["expect"]:
        return False, f"expected return value {expected['expect']}, got {returned}"

    if expected["out"] and program_output != expected["out"]:
        return False, f"expected output {expected['out']}, got {program_output}"

    return True, ""


def main() -> None:
    cases = sorted(f for f in os.listdir(CASES_DIR) if f.endswith(".pe"))

    if not cases:
        print("No test cases found")
        sys.exit(1)

    failures = []
    for name in cases:
        ok, reason = run_case(os.path.join(CASES_DIR, name))
        if ok:
            print(f"PASS  {name}")
        else:
            print(f"FAIL  {name}: {reason}")
            failures.append(name)

    print()
    print(f"{len(cases) - len(failures)}/{len(cases)} tests passed")

    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
