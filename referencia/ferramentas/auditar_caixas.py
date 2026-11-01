#!/usr/bin/env python3
"""Auditoria da divisão das falas em caixas/linhas (todas as unidades com PT).

Sinais (quebra.auditar):
  CURTA       caixa de continuação com 1–2 palavras (criada pela divisão)
  PREP        caixa termina em preposição/artigo/conjunção (separa do complemento)
  EXPR        divisão dentro de expressão fixa ("na mesma hora"...)
  MEIO        caixa termina no meio de oração (sem pontuação)
  REFORMULAR? a fala excede o limite por apenas 1 linha: candidata a reformulação
              fiel ao JP para caber em uma caixa a menos
  ORFA        última linha de uma caixa com uma palavra só
Falas curtas do original (uma caixa) nunca são sinalizadas como CURTA.

Uso: python3 ferramentas/auditar_caixas.py [--disco 1] [--cena X ...] [--mostrar SINAL]
Gera traducao/discoN/auditoria_caixas.tsv
"""
import argparse
import collections
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ferramentas"))
import construir  # noqa: E402
import quebra  # noqa: E402
import tradfile  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--disco", default="1")
    ap.add_argument("--cena", nargs="*")
    ap.add_argument("--mostrar", default="")
    a = ap.parse_args()
    files = sorted((ROOT / "traducao" / f"disco{a.disco}" / "cenas").glob("*.txt"))
    if a.cena:
        files = [f for f in files if f.stem in a.cena]
    cnt = collections.Counter()
    rows = []
    units = multi = 0
    for f in files:
        scene, ents = tradfile.parse(f)
        for e in ents:
            if not e.pt or e.type != 100:
                continue
            units += 1
            sp = e.speaker_jp is not None
            boxes = construir.layout(e.pt, sp)
            multi += len(boxes) > 1
            g = construir._LAYOUT.n_lines(e.pt.split(), sp) if "¶" not in e.pt and "＿" not in e.pt else 0
            sig = quebra.auditar(boxes, g)
            for s_ in sig:
                cnt[s_.split("(")[0]] += 1
            if sig:
                rows.append((scene, e.idx, sig, boxes, e))
    out = ROOT / "traducao" / f"disco{a.disco}" / ("auditoria_caixas.tsv" if not a.cena else "auditoria_caixas_parcial.tsv")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write("cena\tidx\tsinais\tcaixas\n")
        for scene, idx, sig, boxes, _e in rows:
            fh.write(f"{scene}\t{idx}\t{'; '.join(sig)}\t{' ¶ '.join('＿'.join(b) for b in boxes)}\n")
    print(f"unidades: {units}; com mais de uma caixa: {multi}")
    for k, v in sorted(cnt.items()):
        print(f"  {k}: {v}")
    if a.mostrar:
        for scene, idx, sig, boxes, e in rows:
            if any(s_.startswith(a.mostrar) for s_ in sig):
                print(f"\n{scene} @{idx} {sig}\n  JP: {e.jp}")
                for b in boxes:
                    print("  ▢ " + " / ".join(b))
    print(f"-> {out}")
    bad = sum(cnt[k] for k in ("CURTA", "PREP", "EXPR"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
