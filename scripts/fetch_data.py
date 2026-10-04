"""Download every raw source into data/raw and record provenance.

Raw files are never edited after download. Each run appends a row per file to
data/raw/provenance.csv with URL, retrieval date, size and SHA-256, so any
processed table can be traced back to the exact bytes it came from.

Usage: python scripts/fetch_data.py [--force]
"""
import csv
import datetime as dt
import hashlib
import json
import sys
import zipfile
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
UA = {"User-Agent": "Mozilla/5.0 (datathon research; contact via repo)"}

HDX = "https://data.humdata.org/dataset"
DNEMIS = "https://emis.education.gov.ng/portal"

# (relative path under data/raw, URL, folder to unzip into or None)
SOURCES = [
    ("nbs/waec_results_2016_2018.pdf", "https://nigerianstat.gov.ng/download/1001", None),
    ("nbs/waec_results_2019_2021.pdf", "https://nigerianstat.gov.ng/download/1241213", None),
    *[
        (
            f"ubec/ubec_digest_2019_2020_vol_{v}.pdf",
            f"https://ubec.gov.ng/wp-content/uploads/2024/04/2019-AND-2020-Digest-of-Statistics-Volume-{v}.pdf",
            None,
        )
        for v in ("I", "II", "III")
    ],
    (
        "boundaries/nga_admin_boundaries.xlsx",
        f"{HDX}/81ac1d38-f603-4a98-804d-325c658599a3/resource/f1865f35-a07e-4de3-9183-e4222e475527/download/nga_admin_boundaries.xlsx",
        None,
    ),
    (
        "boundaries/nga_admin_boundaries.geojson.zip",
        f"{HDX}/81ac1d38-f603-4a98-804d-325c658599a3/resource/7e30ec96-7f29-4ee8-9f4c-77633b353cbb/download/nga_admin_boundaries.geojson.zip",
        "boundaries/geojson",
    ),
    (
        "grid3/nga_education_facilities.xlsx",
        f"{HDX}/ec228c18-8edc-4f3c-94c9-a6b946af7229/resource/073ac85c-25f0-49fc-bbfa-9530e5f36e2d/download/nga_education_facilities.xlsx",
        None,
    ),
    (
        "grid3/nga_education_shp.zip",
        f"{HDX}/ec228c18-8edc-4f3c-94c9-a6b946af7229/resource/1a064a21-ffcf-4fb8-a0a6-5cf811d94664/download/nga_education.zip",
        "grid3/nga_education_shp",
    ),
    (
        "population/nga_admpop_2020.xlsx",
        f"{HDX}/a7c3de5e-ff27-4746-99cd-05f2ad9b1066/resource/3597a93e-3b1d-4d06-ad2c-109c84a951b6/download/nga_admpop_2020.xlsx",
        None,
    ),
    (
        "population/nga_admpop_adm1_2022.csv",
        f"{HDX}/a7c3de5e-ff27-4746-99cd-05f2ad9b1066/resource/d9fc551a-b5e4-4bed-9d0d-b047b6961817/download/nga_admpop_adm1_2022.csv",
        None,
    ),
    (
        "population/nga_codps_qa_2023.pdf",
        f"{HDX}/a7c3de5e-ff27-4746-99cd-05f2ad9b1066/resource/562e7757-0683-4d61-87bd-a7c94af2ee38/download/nga_codps_qa_2023.pdf",
        None,
    ),
    (
        "mics/unicef_nigeria_education_fact_sheets_2023.pdf",
        "https://unicef.org/nigeria/media/9211/file/Nigeria%20Education%20Fact%20Sheets.pdf",
        None,
    ),
]


def dnemis_sources():
    """DNEMIS publishes its census tables as parquet files listed in a manifest."""
    manifest = requests.get(f"{DNEMIS}/data/manifest.json", headers=UA, timeout=60).json()
    out = [("dnemis/manifest.json", f"{DNEMIS}/data/manifest.json", None)]
    for p in manifest["renderedFiles"]["census"]:
        rel = p.removeprefix("static/")
        out.append((f"dnemis/{Path(rel).name}", f"{DNEMIS}/{rel}", None))
    return out


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main(force=False):
    log_path = RAW / "provenance.csv"
    new_log = not log_path.exists()
    logged = set() if new_log else {row["file"] for row in csv.DictReader(open(log_path, encoding="utf-8"))}
    today = dt.date.today().isoformat()
    with open(log_path, "a", newline="", encoding="utf-8") as log:
        w = csv.writer(log)
        if new_log:
            w.writerow(["file", "url", "retrieved", "bytes", "sha256"])
        for rel, url, unzip in SOURCES + dnemis_sources():
            dest = RAW / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists() and not force:
                if rel not in logged:
                    # Downloaded before logging existed: record it so provenance stays complete.
                    w.writerow([rel, url, today, dest.stat().st_size, sha256(dest)])
                print(f"skip  {rel} (exists)")
                continue
            r = requests.get(url, headers=UA, timeout=600, stream=True)
            r.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
            w.writerow([rel, url, today, dest.stat().st_size, sha256(dest)])
            print(f"fetch {rel} ({dest.stat().st_size:,} B)")
            if unzip:
                with zipfile.ZipFile(dest) as z:
                    z.extractall(RAW / unzip)


if __name__ == "__main__":
    main(force="--force" in sys.argv)
