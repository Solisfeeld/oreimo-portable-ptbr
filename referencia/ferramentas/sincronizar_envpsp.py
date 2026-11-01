#!/usr/bin/env python3
"""Copia para traducao/disco1/sistema/envpsp.tsv as strings do envpsp que repetem texto das cenas.

* títulos (blocos não-diálogo das cenas: 700 = título da cena, "Rota X · …" etc.) — mesma string JP;
* palavras-chave O.R.E. (traducao/disco1/ore_termos.tsv, gerado por verificar.py).

Só preenche linhas com `pt` vazio, a menos que --atualizar seja passado (aí também corrige
linhas cujo PT divergiu da cena, desde que a nota seja das geradas por este script).

Uso: python3 ferramentas/sincronizar_envpsp.py [--atualizar]
"""
import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ferramentas"))
import tradfile  # noqa: E402

TSV = ROOT / "traducao" / "disco1" / "sistema" / "envpsp.tsv"
ORE = ROOT / "traducao" / "disco1" / "ore_termos.tsv"
NT_TIT = "título (= bloco da cena)"
NT_ORE = "palavra-chave O.R.E. (= diálogo)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--atualizar", action="store_true")
    a = ap.parse_args()
    tit = {}
    for f in sorted((ROOT / "traducao" / "disco1" / "cenas").glob("*.txt")):
        _s, ents = tradfile.parse(f)
        for e in ents:
            if e.type != 100 and e.pt:
                tit.setdefault(e.jp, set()).add(e.pt)
    conflitos = {k: v for k, v in tit.items() if len(v) > 1}
    ore = {}
    if ORE.exists():
        for r in csv.DictReader(open(ORE, encoding="utf-8"), delimiter="\t"):
            ore[r["jp"]] = r["pt"]
    rows = list(csv.reader(open(TSV, encoding="utf-8"), delimiter="\t"))
    n_t = n_o = 0
    for r in rows[1:]:
        jp, pt, nt = r[1], r[3], r[4]
        gerada = nt in (NT_TIT, NT_ORE) or nt.startswith("título da cena")
        if pt and not (a.atualizar and gerada):
            continue
        if jp in tit and jp not in conflitos:
            novo = next(iter(tit[jp]))
            if novo != pt:
                r[3] = novo
                r[4] = nt if nt else NT_TIT
                n_t += 1
        elif jp in ore and ore[jp]:
            if ore[jp] != pt:
                r[3], r[4] = ore[jp], nt if nt else NT_ORE
                n_o += 1
    with open(TSV, "w", newline="", encoding="utf-8") as f:
        csv.writer(f, delimiter="\t").writerows(rows)
    print(f"títulos: {n_t}; termos O.R.E.: {n_o}; conflitos (mesmo JP, PT diferente): {len(conflitos)}")
    for k, v in conflitos.items():
        print("  CONFLITO", k, "->", sorted(v))


if __name__ == "__main__":
    main()
