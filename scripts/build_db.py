"""Build data/processed/wazobia.sqlite from data/processed (schema: db/schema.sql).

Usage: python scripts/build_db.py [output path]
"""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline import database  # noqa: E402

path = database.build(Path(sys.argv[1]) if len(sys.argv) > 1 else database.DEFAULT_PATH)
con = sqlite3.connect(path)
tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")]
for t in tables:
    print(f"{t:26s} {con.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]:>6,}")
con.close()
print(f"Wrote {path.relative_to(Path.cwd()) if path.is_relative_to(Path.cwd()) else path}")
