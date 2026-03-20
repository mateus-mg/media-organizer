#!/usr/bin/env python3
"""Run the full unittest battery for this project."""

import os
import subprocess
import sys
import time
from pathlib import Path


def run_all_tests() -> int:
    project_root = Path(__file__).resolve().parent.parent
    os.chdir(project_root)

    print("=" * 70)
    print("MEDIA ORGANIZER - UNIT TEST BATTERY")
    print("=" * 70)
    print(f"Project root: {project_root}")

    start = time.time()
    cmd = [
        sys.executable,
        "-m",
        "unittest",
        "discover",
        "-s",
        "tests",
        "-p",
        "test_*.py",
        "-v",
    ]

    result = subprocess.run(cmd, text=True)
    elapsed = time.time() - start

    print("-" * 70)
    print(f"Elapsed: {elapsed:.2f}s")
    print("Result:", "PASS" if result.returncode == 0 else "FAIL")
    print("=" * 70)

    return result.returncode


if __name__ == "__main__":
    sys.exit(run_all_tests())
