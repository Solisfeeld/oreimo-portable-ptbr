#!/usr/bin/env python3
"""Acrescenta a tradução espanhola (oreimo-es-main) como referência ES: em cada unidade.

O projeto espanhol indexa as falas pela ordem do EN em cada cena
(translation/corpus/<cena>.obj.tsv = índice, _, texto EN sem nome/「」;
translation/Translation.json = índice -> ES). Aqui o ES é casado com as nossas
unidades pelo texto EN (normalizado), respeitando a ordem quando há repetição.

Uso: python3 ferramentas/espanhol.py [--disco 1]
"""
import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ferramentas"))
import oreimo_script as osc  # noqa: E402
import tradfile  # noqa: E402

ES = ROOT / "oreimo-es-main" / "translation"


def norm(t: str) -> str:
    t = t.replace("＿", " ").replace("\\n", " ")
    return re.sub(r"\s+", " ", t).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--disco", default="1")
    a = ap.parse_args()
    tr = json.loads((ES / ("Translation.json" if a.disco == "1" else "Translation_disc2.json")).read_text(encoding="utf-8"))
    corpus_dir = ES / ("corpus" if a.disco == "1" else "corpus_disc2")
    tot = hit = 0
    for f in sorted((ROOT / "traducao" / f"disco{a.disco}" / "cenas").glob("*.txt")):
        scene, ents = tradfile.parse(f)
        cands = list(corpus_dir.glob(f"*{scene}.obj.tsv"))
        key = next((k for k in tr if k.endswith(f"{scene}.obj")), None)
        if not cands or key is None:
            print("sem ES:", scene)
            continue
        es_by = defaultdict(list)
        with open(cands[0], encoding="utf-8") as fh:
            for row in csv.reader(fh, delimiter="\t", quoting=csv.QUOTE_NONE):
                if len(row) >= 3 and row[0].isdigit() and tr[key].get(row[0]):
                    es_by[norm(row[2])].append(tr[key][row[0]])
        used = defaultdict(int)
        for e in ents:
            e.es = []
            for en in e.en:
                if not en:
                    continue
                _spk, body = osc.split_speaker(en) if "「" in en else (None, en)
                k = norm(body)
                lst = es_by.get(k)
                if lst:
                    e.es.append(lst[min(used[k], len(lst) - 1)])
                    used[k] += 1
            tot += 1
            hit += bool(e.es)
        f.write_text(tradfile.render(scene, ents), encoding="utf-8")
    print(f"unidades: {tot}; com ES: {hit} ({100 * hit / max(tot, 1):.1f}%)")


if __name__ == "__main__":
    main()
