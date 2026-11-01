#!/usr/bin/env python3
"""Regressão do Histórico: detecta linhas re-quebradas pelo motor (palavra partida) em capturas reais do PPSSPP.

  python3 ferramentas/detectar_quebra_historico.py <dir com capturas do Histórico> --iso ISO [--cenas AKYO_0000A]

Cada captura é segmentada em linhas de texto (projeção horizontal dos pixels escuros na área do painel); a largura
de cada linha em pixels é convertida em unidades da fonte (PX_POR_U, medido em 23/10) e comparada com o conjunto
de larguras das linhas que o construtor produziu (OBJ da ISO + nomes). Uma linha re-quebrada gera pedaços que não
correspondem a nenhuma linha esperada (ex.: "…numa escol" + "a"): esses são listados como SUSPEITOS.
Sem OCR; serve como alarme automático + lista para revisão visual.
"""
import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ferramentas"))
import construir  # noqa: E402
import isofs  # noqa: E402
import oreimo_script as osc  # noqa: E402

PX_POR_U = 0.795                           # escala 0,8 do Histórico (medido 23/10: 380 px / 478 u); era 0,742 com 0,75
X0, X1, Y0, Y1 = 54, 446, 36, 246          # área de texto do painel do Histórico (480×272; texto começa em x=60)


def larguras_esperadas(iso, cenas):
    rd = osc.ResDat(isofs.read_file(iso, "/PSP_GAME/INSDIR/RES.DAT"))
    ws = set()
    for c in cenas:
        for _i, b in osc.parse_obj(rd.obj(c)).text_blocks((100,)):
            t = b.text
            if "「" in t:
                nome, corpo = t.split("「", 1)
                ws.add(construir.width(nome, False))
                linhas = corpo.rstrip("」").split("＿")
                for k, l in enumerate(linhas):
                    w = construir.width(l, False) + construir.BRACKET_W
                    ws.add(w + (construir.BRACKET_W if k == len(linhas) - 1 else 0))   # 「 … 」 na última
                    ws.add(w)
            else:
                for l in t.split("＿"):
                    ws.add(construir.width(l, False))
    return sorted(ws)


def linhas_da_captura(path):
    a = np.asarray(Image.open(path).convert("L"), dtype=int)[Y0:Y1, X0:X1]
    esc = a < 110
    prof = esc.sum(1)
    out, ini = [], None
    for y, v in enumerate(list(prof) + [0]):
        if v > 1 and ini is None:
            ini = y
        if v <= 1 and ini is not None:
            if y - ini >= 4:     # altura mínima: 4 px ("a" sozinho tem ~5 px; separadores pontilhados têm 1 px)
                cols = np.where(esc[ini:y].any(0))[0]
                out.append((ini + Y0, y + Y0, (cols.max() - cols.min() + 1) / PX_POR_U))
            ini = None
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--iso", required=True)
    ap.add_argument("--cenas", nargs="+", default=["AKYO_0000A"])
    ap.add_argument("--tol", type=float, default=7.0)
    a = ap.parse_args()
    esperadas = np.array(larguras_esperadas(a.iso, a.cenas))
    suspeitos, total = [], 0
    for f in sorted(Path(a.dir).glob("backlog_*.png")) or sorted(Path(a.dir).glob("w*.png")):
        for y0, y1, w in linhas_da_captura(f):
            if w > 500:          # borda do painel / linha divisória de largura total, não é texto
                continue
            total += 1
            d = np.abs(esperadas - w).min()
            if d > a.tol:
                suspeitos.append((f.name, y0, round(w), round(d)))
    print(f"linhas analisadas: {total}; SUSPEITAS (largura sem correspondência, tol {a.tol} u): {len(suspeitos)}")
    for s in suspeitos[:60]:
        print("  ", s)
    return 1 if suspeitos else 0


if __name__ == "__main__":
    sys.exit(main())
