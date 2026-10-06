"""Project paths shared by every pipeline step."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
INTERIM = ROOT / "data" / "interim"
PROCESSED = ROOT / "data" / "processed"
CONFIG = ROOT / "config"
REPORTS = ROOT / "reports"

for _d in (INTERIM, PROCESSED, REPORTS):
    _d.mkdir(parents=True, exist_ok=True)

DNEMIS_CONSTANTS = RAW / "dnemis" / "constants.parquet"
