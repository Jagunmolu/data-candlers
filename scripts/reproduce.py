"""Reproduce everything from raw data in one command.

Usage: python scripts/reproduce.py
Steps: download raw sources (skips files already present), extract and
reconcile, build both lenses and validation, run the tests, render figures.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STEPS = [
    [sys.executable, "scripts/fetch_data.py"],
    [sys.executable, "-m", "pipeline.build"],
    [sys.executable, "-m", "pytest", "-q"],
    [sys.executable, "scripts/render_figures.py"],
]

for cmd in STEPS:
    print(f"\n>>> {' '.join(cmd[1:])}", flush=True)
    if subprocess.run(cmd, cwd=ROOT).returncode != 0:
        sys.exit(f"Step failed: {' '.join(cmd[1:])}")
print("\nAll steps passed. Start the app with: streamlit run streamlit_app.py")
