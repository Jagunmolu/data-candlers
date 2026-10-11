"""Assemble a Hugging Face Space (Docker) folder for the Dash app.

Usage: python scripts/build_space.py [OUT_DIR]   (default: build/space)
Then push OUT_DIR to the Space's git repo. The folder holds only what the app
needs at runtime, plus a README with the Space settings Hugging Face reads.
"""
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "build" / "space"

FILES = ["Dockerfile", "requirements-dash.txt", "dash_app.py", "figures.py", "pipeline/__init__.py",
         "pipeline/insights.py", "config/settings.yaml"]
DIRS = ["dashapp", "data/processed"]

README = """---
title: Where Should the Next Teacher Go?
emoji: 🏫
colorFrom: blue
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
---

Decision tool ranking Nigeria's 774 LGAs by their gap to the UBE standard of 35 learners per teacher and per
classroom, with confidence grades. Built from public data (Federal Ministry of Education Annual School Census 2024
and others). Source code, method and data audit: {repo}
"""


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    for f in FILES:
        (OUT / f).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / f, OUT / f)
    for d in DIRS:
        shutil.copytree(ROOT / d, OUT / d, ignore=shutil.ignore_patterns("__pycache__", ".gitkeep"))
    # Linux containers need LF line endings in the Dockerfile, whatever the local checkout uses.
    df = OUT / "Dockerfile"
    df.write_bytes(df.read_bytes().replace(bytes([13, 10]), bytes([10])))
    repo = "https://github.com/Jagunmolu/data-candlers"
    (OUT / "README.md").write_text(README.format(repo=repo), encoding="utf-8")
    size = sum(p.stat().st_size for p in OUT.rglob("*") if p.is_file()) / 1e6
    print(f"Space folder ready: {OUT} ({size:.1f} MB)")


if __name__ == "__main__":
    main()
