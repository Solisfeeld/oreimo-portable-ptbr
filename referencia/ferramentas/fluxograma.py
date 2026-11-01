"""Fluxograma (Extras): main_resource/main_resource_data/flowmap/map.dat em PT-BR.

O map.dat JP é um fluxo binário com campos de tamanhos variados e strings "u32 n + n×UTF-16" (títulos dos
nós = títulos das cenas, mais alguns cabeçalhos). O patch EN reescreveu o arquivo inteiro em inglês (101 strings,
outra disposição), que é o que a ISO EN traz. Aqui: parte-se do JP e troca-se SÓ cada string pelo PT já revisado
(título da cena no arquivo de cena; senão a mesma string no envpsp.tsv), atualizando o u32 do comprimento; todo o
resto fica byte a byte. Sem a quebra ＿ (o campo do fluxograma é outro).
"""
import csv
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ferramentas"))
import tradfile  # noqa: E402
from oreimo_core import gpda  # noqa: E402

CAMINHO = ["main_resource", "main_resource_data", "flowmap", "map.dat"]
LIMITE = 621      # unidades que cabem no cabeçalho com escala 0,55 e x inicial 140 (envpsp 2993/2989)


def strings(d: bytes):
    out, p = [], 0
    while p < len(d) - 6:
        n = struct.unpack_from("<I", d, p)[0]
        if 1 <= n < 100 and p + 4 + 2 * n <= len(d):
            try:
                s = d[p + 4:p + 4 + 2 * n].decode("utf-16-le")
                if all(c.isprintable() for c in s) and (any(ord(c) >= 0x3000 for c in s)
                                                        or (n >= 4 and s.isascii() and any(c.isalpha() for c in s))):
                    out.append((p, n, s))
                    p += 4 + 2 * n
                    continue
            except UnicodeDecodeError:
                pass
        p += 1
    return out


def tabela(disco="1"):
    mapa = {}
    for f in (ROOT / "traducao" / f"disco{disco}" / "cenas").glob("*.txt"):
        for e in tradfile.parse(f)[1]:
            if e.type == 700 and e.pt:
                mapa.setdefault(e.jp.strip(), e.pt.replace("＿", " ").replace("¶", " "))
    with open(ROOT / "traducao" / f"disco{disco}" / "sistema" / "envpsp.tsv", encoding="utf-8") as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            if r.get("pt"):
                mapa.setdefault(r["jp"].strip(), r["pt"].replace("_", " ").replace("＿", " "))
    return mapa


def construir(res_jp: bytes, disco="1", quebra_px=None):
    """quebra_px: (TESTE) insere ＿ nas strings mais largas que isso (unidades da fonte)."""
    off, sz = gpda.find_path(res_jp, CAMINHO)
    d = res_jp[off:off + sz]
    mapa = tabela(disco)
    out, ult, trocadas, faltam, compactados = bytearray(), 0, 0, [], []
    for p, n, s in strings(d):
        if s == "header":
            continue
        pt = mapa.get(s)
        if pt is None:
            faltam.append(s)
            continue
        out += d[ult:p]
        import construir as _c
        if _c.width(pt, False) > LIMITE and pt.startswith("Rota "):
            # cabeçalho do Fluxograma = 1 linha (não aceita ＿; testado em 23/10). Só os títulos que não cabem nem
            # com a escala reduzida (envpsp 2993 0,7→0,55) perdem a palavra "Rota" do prefixo: a rota continua nomeada
            pt = pt[5:]
            compactados.append(pt)
        enc = pt.encode("utf-16-le")
        out += struct.pack("<I", len(enc) // 2) + enc
        ult = p + 4 + 2 * n
        trocadas += 1
    out += d[ult:]
    return bytes(out), {"strings_trocadas": trocadas, "sem_pt": faltam, "tamanho": (len(d), len(out)),
                        "compactados": compactados}
