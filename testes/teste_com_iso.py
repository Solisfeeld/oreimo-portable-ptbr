#!/usr/bin/env python3
"""Testa as ferramentas com a sua própria cópia do jogo. Só lê a ISO; não grava nada.

    python3 testes/teste_com_iso.py CAMINHO/DA/ISO [--sem-texturas]
"""
import sys
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "ferramentas"))
import envpsp  # noqa: E402
import explorar  # noqa: E402
import gim  # noqa: E402
import gpda  # noqa: E402
import isofs  # noqa: E402
import oreimo_script as osc  # noqa: E402


def main():
    iso = sys.argv[1]
    arquivos = [e for e in isofs.entries(iso) if not e.is_dir]
    print("arquivos na ISO:", len(arquivos))
    res = isofs.read_file(iso, explorar.RES)
    print("arquivos no RES.DAT:", sum(1 for _ in gpda.percorrer(res)))
    rd = osc.ResDat(res)
    falas = blocos = 0
    for c in rd.scene_names():
        bruto = rd.obj(c)
        o = osc.parse_obj(bruto)
        if osc.build_obj(o) != bruto:
            print("ERRO: remontagem diferente em", c)
            return 1
        blocos += len(o.blocks)
        falas += sum(b.type == 100 for b in o.blocks)
    print(f"cenas: {len(rd.scene_names())}, blocos: {blocos:,}, falas: {falas:,} (remontagem idêntica em todas)")
    d = isofs.read_file(iso, explorar.ENV)
    cab, toks = envpsp.tokenize(d)
    if envpsp.build(cab, toks) != d:
        print("ERRO: envpsp.dat não remonta igual")
        return 1
    print(f"envpsp.dat: {len(toks):,} tokens (remontagem idêntica)")
    if "--sem-texturas" not in sys.argv:
        formatos, n = Counter(), 0
        for _c, g in explorar.texturas(res):
            im = gim.decodificar(g)
            i = gim.ler_info(g)
            if im.size != (i.largura, i.altura):
                print("ERRO: dimensões em", _c)
                return 1
            formatos[gim.NOMES[i.formato]] += 1
            n += 1
        print(f"texturas decodificadas: {n:,} {dict(formatos)}")
    print("RESUMO: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
