#!/usr/bin/env python3
"""Render docs/DATA-ATLAS.md to a styled docs/DATA-ATLAS.pdf.

markdown -> HTML (python-markdown) -> headless Chrome --print-to-pdf. The GitHub-rendered
Mermaid diagram is swapped for a print-safe ASCII pipeline so the PDF is deterministic and
needs no network/JS. Re-run after editing the atlas:  python docs/build_atlas_pdf.py
"""

from __future__ import annotations

import pathlib
import re
import subprocess

import markdown

ROOT = pathlib.Path(__file__).resolve().parent
MD = ROOT / "DATA-ATLAS.md"
HTML = ROOT / "_atlas.html"
PDF = ROOT / "DATA-ATLAS.pdf"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

ASCII_PIPELINE = """<pre class="diagram">
  FREE PUBLIC SOURCES         WEEKLY GITHUB ACTION (ingest -> compute)      STATIC JSON -> THE APP
  -------------------         ----------------------------------------      ----------------------

  IMF PortWatch ------+
   ports + chokepoints|        +--> change-point detection + FDR --+
  FRED / BLS / Census +------> [  DuckDB  ] --> rolling z-scores ---+---->  [ 3-D globe + Monitor feed ]
   rates/macro/commod.|         warehouse  --> stress index --------+                  |
  AISStream ----------+                                                                v
  USGS/NASA/GDACS ----+                                                  [ AI briefing (offline reasoner) ]
  GDELT / Google News +                                                   connects measured facts <-> cited
                                                                          context  -  association only
</pre>"""

CSS = """
@page { size: A4; margin: 16mm 14mm; }
* { box-sizing: border-box; }
body { font-family: -apple-system, 'Helvetica Neue', Arial, sans-serif; color: #1a1a1a;
       font-size: 10.5px; line-height: 1.5; max-width: 100%; }
h1 { font-size: 23px; letter-spacing: -0.5px; margin: 0 0 4px; }
h2 { font-size: 15px; margin: 22px 0 6px; padding-bottom: 4px; border-bottom: 2px solid #2f5d99;
     color: #1a2b3c; }
h3 { font-size: 12.5px; margin: 14px 0 4px; color: #2f5d99; }
p { margin: 6px 0; }
a { color: #2f5d99; text-decoration: none; }
blockquote { margin: 8px 0; padding: 6px 12px; border-left: 3px solid #c9a227;
             background: #faf7ee; color: #3a3a3a; }
code { font-family: 'SF Mono', Menlo, monospace; font-size: 9px; background: #f1f1f4;
       padding: 1px 4px; border-radius: 3px; }
pre.diagram { font-family: 'SF Mono', Menlo, monospace; font-size: 8.2px; line-height: 1.35;
              background: #0f1b2d; color: #cfe0f5; padding: 14px; border-radius: 8px;
              overflow: hidden; white-space: pre; }
table { width: 100%; border-collapse: collapse; margin: 8px 0; font-size: 9px; }
th { background: #1a2b3c; color: #fff; text-align: left; padding: 5px 7px; font-weight: 600; }
td { padding: 5px 7px; border-bottom: 1px solid #e3e3e8; vertical-align: top; }
tr:nth-child(even) td { background: #f7f8fa; }
strong { color: #111; }
hr { border: none; border-top: 1px solid #ddd; margin: 16px 0; }
h2, h3 { page-break-after: avoid; }
table, pre { page-break-inside: avoid; }
"""


def build() -> None:
    text = MD.read_text()
    text = re.sub(r"```mermaid.*?```", ASCII_PIPELINE, text, flags=re.S)
    body = markdown.markdown(text, extensions=["tables", "fenced_code", "sane_lists"])
    HTML.write_text(f"<!doctype html><html><head><meta charset='utf-8'><style>{CSS}</style>"
                    f"</head><body>{body}</body></html>")
    subprocess.run(
        [CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
         f"--print-to-pdf={PDF}", HTML.as_uri()],
        check=True, timeout=120,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    HTML.unlink(missing_ok=True)
    print(f"wrote {PDF} ({PDF.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    build()
