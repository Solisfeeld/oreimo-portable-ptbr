#!/usr/bin/env python3
"""Verificações automáticas da tradução (Disco N).

  * 【palavras-chave O.R.E.】: a n-ésima 【…】 do JP corresponde à n-ésima do PT;
    o mesmo termo JP deve ter sempre a mesma tradução, e (quando preenchida) a
    mesma da lista O.R.E. em traducao/discoN/sistema/envpsp.tsv;
  * glifos ausentes na fonte do jogo (fontmap);
  * marcação de rubi 《…：…》 esquecida no PT; aspas tipográficas “ ” (largas);
  * quantidade de 【】 diferente entre JP e PT;
  * unidades sem tradução por cena.
Gera traducao/discoN/ore_termos.tsv e imprime um relatório.

Uso: python3 ferramentas/verificar.py [--disco 1]
"""
import argparse
import collections
import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ferramentas"))
import tradfile  # noqa: E402
from oreimo_core.fontmap import ADVANCE  # noqa: E402

KW = re.compile(r"【([^】]*)】")
OK_EXTRA = set("＿¶")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--disco", default="1")
    a = ap.parse_args()
    base = ROOT / "traducao" / f"disco{a.disco}"
    terms = collections.defaultdict(collections.Counter)
    where = collections.defaultdict(list)
    problems = []
    pending = {}
    for f in sorted((base / "cenas").glob("*.txt")):
        scene, ents = tradfile.parse(f)
        done = [e for e in ents if e.pt]
        if done:
            pending[scene] = len(ents) - len(done)
        for e in done:
            jk, pk = KW.findall(e.jp), KW.findall(e.pt)
            if len(jk) != len(pk):
                problems.append((scene, e.idx, f"【】: JP tem {len(jk)}, PT tem {len(pk)}"))
            for j, p in zip(jk, pk):
                terms[j][p] += 1
                where[j].append(f"{scene}@{e.idx}")
            missing = sorted({c for c in e.pt if c not in ADVANCE and c not in OK_EXTRA})
            if missing:
                problems.append((scene, e.idx, f"glifos fora da fonte: {missing}"))
            if "《" in e.pt or "：" in e.pt and "》" in e.pt:
                problems.append((scene, e.idx, "marcação de rubi no PT"))
            if "“" in e.pt or "”" in e.pt:
                problems.append((scene, e.idx, "aspas tipográficas “ ” (largas na fonte) — usar \"\""))
    ore_pt = {}
    env = base / "sistema" / "envpsp.tsv"
    if env.exists():
        with open(env, encoding="utf-8") as fh:
            for r in csv.DictReader(fh, delimiter="\t"):
                if r.get("pt"):
                    ore_pt[r["jp"]] = r["pt"]
    with open(base / "ore_termos.tsv", "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["jp", "pt", "variantes", "lista_ore_pt", "ocorrencias"])
        for j, cnt in sorted(terms.items()):
            main_pt = cnt.most_common(1)[0][0]
            variants = "; ".join(f"{p} ({n})" for p, n in cnt.items()) if len(cnt) > 1 else ""
            w.writerow([j, main_pt, variants, ore_pt.get(j, ""), " ".join(where[j][:8])])
            if len(cnt) > 1:
                problems.append(("O.R.E.", j, f"traduções diferentes: {variants}"))
            if j in ore_pt and ore_pt[j] != main_pt:
                problems.append(("O.R.E.", j, f"lista O.R.E. diz '{ore_pt[j]}', diálogo diz '{main_pt}'"))
    print(f"Cenas com tradução: {len(pending)}  (unidades pendentes nelas: {sum(pending.values())})")
    for s, n in pending.items():
        if n:
            print(f"  {s}: {n} pendentes")
    print(f"Termos O.R.E. nos diálogos: {len(terms)} -> {base / 'ore_termos.tsv'}")
    print(f"Problemas: {len(problems)}")
    for p in problems:
        print("  ", *p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
