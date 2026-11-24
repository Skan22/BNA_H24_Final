"""Markdown -> PDF (A4, numéroté), avec Chromium via Playwright.

    python tools/build_pdf.py [source.md] [sortie.pdf]        (défaut : docs/GUIDE-EQUIPE.md -> docs/GUIDE-EQUIPE.pdf)

Prérequis : `make install` (paquet `markdown`, Playwright dans web/) et un Chromium (CHROMIUM_PATH, sinon /usr/bin/chromium).
"""
from __future__ import annotations

import html
import os
import pathlib
import re
import subprocess
import sys

import markdown

ROOT = pathlib.Path(__file__).resolve().parents[1]
source = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs" / "GUIDE-EQUIPE.md"
sortie = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else source.with_suffix(".pdf")

texte = source.read_text(encoding="utf-8")


def aerer_les_listes(md: str) -> str:
    """Python-Markdown ne voit une liste qu'après une ligne vide ; GitHub, lui, la voit tout de suite.
    On insère la ligne vide manquante (hors blocs de code)."""
    sortie, dans_code, precedente = [], False, ""
    puce = re.compile(r"^\s*([-*+]|\d+[.)])\s+")
    for ligne in md.split("\n"):
        if ligne.lstrip().startswith("```"):
            dans_code = not dans_code
        elif (not dans_code and puce.match(ligne) and precedente.strip()
              and not puce.match(precedente) and not precedente.startswith((" ", "\t", "|", ">", "#"))):
            sortie.append("")
        sortie.append(ligne)
        precedente = ligne
    return "\n".join(sortie)


texte = aerer_les_listes(texte)
titre = re.search(r"^# (.+)$", texte, re.M).group(1)
corps = markdown.markdown(texte, extensions=["tables", "fenced_code", "sane_lists"])
corps = re.sub(r"<li>\[ \] ", '<li class="case">☐ ', corps)
corps = re.sub(r"<li>\[x\] ", '<li class="case">☑ ', corps)

CSS = """
@page { size: A4; margin: 18mm 16mm 20mm 16mm; }
* { box-sizing: border-box; }
body { font: 10.2pt/1.5 "Noto Sans", "DejaVu Sans", "Liberation Sans", Arial, sans-serif; color: #14181d; }
h1 { font-size: 21pt; margin: 0 0 4pt; color: #0f6b47; line-height: 1.2; }
h2 { font-size: 14.5pt; margin: 20pt 0 6pt; padding-bottom: 3pt; border-bottom: 2px solid #0f6b47; color: #0f6b47; break-after: avoid; }
h3 { font-size: 11.5pt; margin: 14pt 0 4pt; break-after: avoid; }
p { margin: 5pt 0; orphans: 3; widows: 3; }
em { color: #4a5460; }
hr { border: 0; border-top: 1px solid #d5dae0; margin: 14pt 0; }
a { color: #1c5b8a; text-decoration: none; }
ul, ol { margin: 4pt 0 4pt 16pt; padding: 0; }
li { margin: 2pt 0; }
li.case { list-style: none; margin-left: -12pt; }
blockquote { margin: 8pt 0; padding: 6pt 12pt; background: #e6f2ec; border-left: 4px solid #0f6b47; border-radius: 3pt; }
blockquote p { margin: 3pt 0; }
code { font: 8.6pt/1.4 "DejaVu Sans Mono", "Liberation Mono", monospace; background: #eef1f4; padding: 0.5pt 3pt; border-radius: 2pt; word-break: break-word; }
pre { background: #f3f5f7; border: 1px solid #dde2e7; border-radius: 4pt; padding: 7pt 9pt; margin: 7pt 0; white-space: pre-wrap; break-inside: avoid; }
pre code { background: none; padding: 0; font-size: 7pt; word-break: normal; }
table { border-collapse: collapse; width: 100%; margin: 8pt 0; font-size: 9pt; }
th { background: #0f6b47; color: #fff; text-align: left; padding: 4pt 6pt; border: 1px solid #0f6b47; }
td { padding: 4pt 6pt; border: 1px solid #d5dae0; vertical-align: top; word-break: break-word; }
tr { break-inside: avoid; }
tr:nth-child(even) td { background: #f6f8f9; }
strong { color: #000; }
"""

page = f"""<!doctype html><html lang="en"><meta charset="utf-8"><title>{html.escape(titre)}</title>
<style>{CSS}</style><body>{corps}</body></html>"""
tmp = ROOT / "artifacts" / "_guide.html"
tmp.parent.mkdir(exist_ok=True)
tmp.write_text(page, encoding="utf-8")

env = {**os.environ, "CHROMIUM_PATH": os.environ.get("CHROMIUM_PATH", "/usr/bin/chromium")}
subprocess.run(["node", "pdf.mjs", str(tmp), str(sortie.resolve()), titre], cwd=ROOT / "web", env=env, check=True)
tmp.unlink()
print(f"{sortie}  ({sortie.stat().st_size // 1024} Ko)")
