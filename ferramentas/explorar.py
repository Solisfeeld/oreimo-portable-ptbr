#!/usr/bin/env python3
"""Explora a sua própria cópia do Disco 1, sem modificá-la. Requer Pillow só para exportar texturas.

    python3 ferramentas/explorar.py info ISO                 # arquivos, cenas e texturas
    python3 ferramentas/explorar.py cenas ISO                # cena, nº de blocos, falas e título
    python3 ferramentas/explorar.py blocos ISO CENA          # tipos de bloco de uma cena (não mostra o texto)
    python3 ferramentas/explorar.py grafo ISO saida.tsv      # destinos de cada cena (blocos 703)
    python3 ferramentas/explorar.py envpsp ISO               # contagem de tokens do envpsp.dat
    python3 ferramentas/explorar.py texturas ISO PASTA [FILTRO]  # exporta texturas para PNG
"""
import argparse
import gzip
import struct
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import envpsp  # noqa: E402
import gim  # noqa: E402
import gpda  # noqa: E402
import isofs  # noqa: E402
import oreimo_script as osc  # noqa: E402

RES, FIRST, ENV = "/PSP_GAME/INSDIR/RES.DAT", "/PSP_GAME/USRDIR/first.dat", "/PSP_GAME/USRDIR/envpsp.dat"


def nomes_cena(first):
    texto = next(e for e in gpda.parse_gpda(first) if e.name.strip() == "text")
    bloco = first[texto.data_offset:texto.data_offset + texto.data_size]
    for e in gpda.parse_gpda(bloco):
        if e.name.strip() == "scriptname.txt":
            d = gim.desembrulhar(bloco[e.data_offset:e.data_offset + e.data_size])
            return [ln.strip().replace(".txt", "") for ln in d.decode("cp932").splitlines() if ln.strip()]
    raise KeyError("scriptname.txt")


def texturas(res):
    """Gera (caminho, GIM) de cada textura, inclusive dentro dos pacotes de personagem."""
    for c, b in gpda.percorrer(res):
        d = gim.desembrulhar(b) if b[:2] == b"\x1f\x8b" else b
        if d[:4] == gim.MAGICA:
            yield c, d
        elif d[:4] == gpda.MAGICA:
            for c2, b2 in gpda.percorrer(d, c):
                d2 = gim.desembrulhar(b2) if b2[:2] == b"\x1f\x8b" else b2
                if d2[:4] == gim.MAGICA:
                    yield c2, d2


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("acao", choices=("info", "cenas", "blocos", "grafo", "envpsp", "texturas"))
    ap.add_argument("iso")
    ap.add_argument("resto", nargs="*")
    a = ap.parse_args()
    if a.acao == "envpsp":
        _cab, toks = envpsp.tokenize(isofs.read_file(a.iso, ENV))
        print(f"{len(toks):,} tokens:", dict(Counter(t[0] for t in toks)))
        return 0
    res = isofs.read_file(a.iso, RES)
    if a.acao == "texturas":
        pasta = Path(a.resto[0])
        pasta.mkdir(parents=True, exist_ok=True)
        filtro = a.resto[1] if len(a.resto) > 1 else ""
        n = 0
        for c, g in texturas(res):
            if filtro in c:
                gim.decodificar(g).save(pasta / (c.strip("/").replace("/", "__").replace("#", "_") + ".png"))
                n += 1
        print(f"{n} texturas -> {pasta}")
        return 0
    rd = osc.ResDat(res)
    if a.acao == "info":
        print("arquivos na ISO:", sum(not e.is_dir for e in isofs.entries(a.iso)))
        print("arquivos no RES.DAT:", sum(1 for _ in gpda.percorrer(res)))
        print("cenas:", len(rd.scene_names()))
        print("texturas:", Counter(gim.NOMES.get(gim.ler_info(g).formato) for _c, g in texturas(res)))
    elif a.acao == "cenas":
        for c in rd.scene_names():
            o = osc.parse_obj(rd.obj(c))
            falas = sum(b.type == 100 for b in o.blocks)
            print(f"{c}\t{len(o.blocks)}\t{falas}\t{next((b.text for b in o.blocks if b.type == 700), '')}")
    elif a.acao == "blocos":
        o = osc.parse_obj(rd.obj(a.resto[0]))
        for i, b in enumerate(o.blocks):
            print(i, b.type, f"voz={b.msg_id}" if b.msg_id is not None else "", f"{len(b.text)} car." if b.text else "")
    else:
        nomes = nomes_cena(isofs.read_file(a.iso, FIRST))
        with open(a.resto[0], "w", encoding="utf-8") as f:
            for c in rd.scene_names():
                ds = [(i, struct.unpack_from("<I", b.raw, 6)[0]) for i, b in enumerate(osc.parse_obj(rd.obj(c)).blocks) if b.type == 703]
                f.write(c + "\t" + " ".join(f"{i}:{nomes[n] if n < len(nomes) else n}" for i, n in ds) + "\n")
        print("->", a.resto[0])
    return 0


if __name__ == "__main__":
    sys.exit(main())
