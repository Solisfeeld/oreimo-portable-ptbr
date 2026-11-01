#!/usr/bin/env python3
"""Monta uma folha de contato (grade) das capturas de uma pasta. Uso: folha_contato.py DIR [colunas] [filtro]"""
import sys
from pathlib import Path
from PIL import Image, ImageDraw
d = Path(sys.argv[1]); cols = int(sys.argv[2]) if len(sys.argv) > 2 else 4
filt = sys.argv[3] if len(sys.argv) > 3 else ""
files = sorted(f for f in d.glob("*.png") if filt in f.name and not f.name.startswith("_folha"))
w, h = 480, 272; lab = 14
rows = (len(files) + cols - 1) // cols
sheet = Image.new("RGB", (cols * w, rows * (h + lab)), "black")
dr = ImageDraw.Draw(sheet)
for i, f in enumerate(files):
    x, y = (i % cols) * w, (i // cols) * (h + lab)
    sheet.paste(Image.open(f).convert("RGB").resize((w, h)), (x, y + lab))
    dr.text((x + 2, y), f.name, fill="yellow")
out = d / f"_folha{('_' + filt) if filt else ''}.png"
sheet.save(out); print(out, len(files))
