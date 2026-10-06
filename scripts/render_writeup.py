"""Render docs/WRITEUP.md to docs/WRITEUP.pdf (A4) with headless Chrome or Edge, and
fail unless the PDF is exactly one page.

Usage: python scripts/render_writeup.py [--app URL] [--repo URL]
"""
import shutil
import subprocess
import sys
from pathlib import Path

import markdown
import pandas as pd
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
SRC, HTML, PDF = ROOT / "docs" / "WRITEUP.md", ROOT / "docs" / "WRITEUP.html", ROOT / "docs" / "WRITEUP.pdf"
BROWSERS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "google-chrome", "chromium", "chrome", "msedge",
]
CSS = """
@page { size: A4; margin: 11mm 13mm; }
body { font-family: "Segoe UI", system-ui, -apple-system, sans-serif; font-size: 8.9pt; line-height: 1.34; color: #0b0b0b; }
h1 { font-size: 15pt; margin: 0 0 2px; color: #0d366b; }
h2 { font-size: 10.2pt; margin: 7px 0 2px; color: #184f95; border-bottom: 1px solid #e1e0d9; padding-bottom: 1px; }
p { margin: 0 0 4px; }
a { color: #184f95; }
ul { margin: 0; padding-left: 14px; } li { margin: 0 0 3px; }
.ev { display: flex; gap: 10px; align-items: flex-start; margin: 4px 0 2px; }
.ev figure { margin: 0; width: 50%; } .ev img { width: 100%; }
figcaption { font-size: 7.4pt; color: #52514e; }
.ev table { width: 50%; border-collapse: collapse; font-size: 8pt; font-variant-numeric: tabular-nums; }
.ev th { text-align: left; border-bottom: 1px solid #c3c2b7; padding: 2px 4px; color: #52514e; font-weight: 600; }
.ev td { border-bottom: 1px solid #e1e0d9; padding: 2px 4px; }
"""


def evidence_block():
    """Map and top-10 table, built from the processed data so the numbers never drift."""
    lga = pd.read_parquet(ROOT / "data" / "processed" / "lga_index.parquet")
    top = lga[lga.confidence != "Not ranked"].sort_values("need_score", ascending=False).head(10)
    rows = "".join(
        f"<tr><td>{int(r['rank'])}</td><td>{r.adm2_name}</td><td>{r.adm1_name}</td>"
        f"<td>{r.ltr:.0f}</td><td>{int(r.teachers_needed):,}</td><td>{r.confidence}</td></tr>"
        for _, r in top.iterrows()
    )
    return (
        '<div class="ev"><figure><img src="img/map_writeup.png" alt="Need score map">'
        "<figcaption>Need score by LGA, 2024. Darker = further from 35:1; outlined = top 20; grey = not ranked.</figcaption></figure>"
        "<table><thead><tr><th>#</th><th>LGA</th><th>State</th><th>Learners per teacher</th><th>Teachers needed</th><th>Grade</th></tr></thead>"
        f"<tbody>{rows}</tbody></table></div>"
    )


def main():
    args = dict(zip(sys.argv[1::2], sys.argv[2::2]))
    text = SRC.read_text(encoding="utf-8")
    text = text.replace("[LIVE_APP_URL]", args.get("--app", "[LIVE_APP_URL]")).replace("[REPO_URL]", args.get("--repo", "[REPO_URL]"))
    text = text.replace("[EVIDENCE_BLOCK]", evidence_block())
    body = markdown.markdown(text)
    HTML.write_text(f"<!doctype html><meta charset='utf-8'><style>{CSS}</style>{body}", encoding="utf-8")
    browser = next((b for b in BROWSERS if Path(b).exists() or shutil.which(b)), None)
    if not browser:
        sys.exit("No Chrome or Edge found")
    subprocess.run([browser, "--headless", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={PDF}", HTML.as_uri()], check=True, capture_output=True)
    pages = len(PdfReader(PDF).pages)
    print(f"{PDF.name}: {pages} page(s)")
    if pages != 1:
        sys.exit("Write-up must be exactly one page")


if __name__ == "__main__":
    main()
