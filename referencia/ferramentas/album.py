"""Álbum (Extras): títulos das CGs em omake/omake_cg/data/AlbumList.txt.

O arquivo é texto Shift-JIS (cp932) lido pelo jogo como cp932 — confirmado no PPSSPP em 24/10: UTF-8 e Latin-1
saem como lixo, cp932 aparece certo. O cp932 NÃO tem letras acentuadas latinas (á, ã, ç…), então os títulos PT
(traducao/disco1/sistema/album.tsv) são gravados com as letras acentuadas em bytes cp932 de katakana de meia
largura que o EBOOT PT remapeia para á, ã, ç… (eboot_pt.py) — acentuação correta no jogo. Só a string entre aspas de cada linha muda;
o resto (índices das CGs) fica byte a byte.
"""
import csv
import os
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ferramentas"))
from oreimo_core import gpda  # noqa: E402
import eboot_pt  # noqa: E402

CAMINHO = ["omake", "omake_cg", "data", "AlbumList.txt"]


def sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if not unicodedata.combining(c))


def construir(res_jp: bytes, disco="1"):
    off, sz = gpda.find_path(res_jp, CAMINHO)
    original = res_jp[off:off + sz]
    with open(ROOT / "traducao" / f"disco{disco}" / "sistema" / "album.tsv", encoding="utf-8") as fh:
        pt = {int(r["n"]): (r["jp"], r["pt"]) for r in csv.DictReader(fh, delimiter="\t")}
    teste = os.environ.get("OREIMO_ALBUM_TESTE")
    if teste and 0 in pt:                     # SÓ ISO de teste: título da 1ª CG com todos os acentos, para conferir no jogo
        pt[0] = (pt[0][0], teste)
    linhas = original.split(b"\n")
    k, trocadas, divergentes = 0, 0, []
    for i, l in enumerate(linhas):
        if not l.startswith(b'"'):
            continue
        fim = l.index(b'"', 1)
        jp = l[1:fim].decode("cp932")
        if k in pt:
            if pt[k][0] != jp:
                divergentes.append((k, jp, pt[k][0]))
            else:
                linhas[i] = b'"' + eboot_pt.codificar(pt[k][1]) + l[fim:]
                trocadas += 1
        k += 1
    return b"\n".join(linhas), {"titulos": k, "trocados": trocadas, "jp_divergente": divergentes}
