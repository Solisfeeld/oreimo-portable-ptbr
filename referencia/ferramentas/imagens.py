#!/usr/bin/env python3
"""Imagens (GIM) do RES.DAT: inventário e exportação para PNG.

  python3 ferramentas/imagens.py inventario [--disco 1]
      percorre RES.DAT JP e EN (todas as GPDAs aninhadas, gzip incluído), grava
      build/imagens/inventario.tsv (caminho, formato, tamanho, md5 JP/EN, igual?)
      e exporta PNGs únicos de tudo que NÃO é fundo/CG/personagem por cena:
      build/imagens/{jp,en}/<caminho com / trocado por __>.png
Os fundos/CGs/personagens das cenas (001image_bg, 002image_event, 003image_charactor)
não têm texto e são só contados.
"""
import argparse
import csv
import gzip
import hashlib
import io
import struct
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ferramentas"))
from oreimo_core import gpda  # noqa: E402
from oreimo_core.scene_images import peek_format, FORMAT_NAMES, GIM_MAGICS  # noqa: E402
from oreimo_core.vendor_gim.gim import gim2png  # noqa: E402

SEM_TEXTO = ("001image_bg", "002image_event", "003image_charactor")


def _entradas(blob):
    """GPDA com nomes ou sem nomes (variante dos personagens)."""
    try:
        return [(e.name, e.data_offset, e.data_size) for e in gpda.parse_gpda(blob)]
    except Exception:
        n = struct.unpack_from("<I", blob, 12)[0]
        out = []
        for i in range(n):
            o, _r, s, _no = struct.unpack_from("<IIII", blob, 16 + 16 * i)
            out.append((f"[{i}]", o, s))
        return out


def percorrer(blob, caminho=""):
    """-> [(caminho, bytes GIM)] recursivo."""
    if blob[:2] == b"\x1f\x8b":
        try:
            blob = gzip.decompress(blob)
        except OSError:
            return []
    if blob[:4] in GIM_MAGICS:
        return [(caminho, blob)]
    if blob[:4] != b"GPDA":
        return []
    out = []
    for nome, o, s in _entradas(blob):
        if s <= 0 or o + s > len(blob):
            continue
        out += percorrer(blob[o:o + s], f"{caminho}/{nome.strip()}" if caminho else nome.strip())
    return out


def png(gim):
    with gim2png(gim, SimpleNamespace(verbose=False)) as im:
        b = io.BytesIO()
        im.convert("RGBA").save(b, format="PNG")
        return b.getvalue(), im.size


def inventario(disco):
    ext = ROOT / "build" / "extraido"
    dst = ROOT / "build" / "imagens"
    res = {}
    for lado in ("jp", "en"):
        blob = (ext / f"disco{disco}_{lado}" / "RES.DAT").read_bytes()
        res[lado] = dict(percorrer(blob))
        print(lado, len(res[lado]), "imagens")
    linhas, md5_vistos = [], {"jp": set(), "en": set()}
    for c in sorted(set(res["jp"]) | set(res["en"])):
        g = {k: res[k].get(c) for k in res}
        h = {k: hashlib.md5(v).hexdigest() if v else "" for k, v in g.items()}
        ref = g["jp"] or g["en"]
        cena = c.startswith("script/")
        sem_texto = cena and any(s in c for s in SEM_TEXTO)
        larg = alt = 0
        if not sem_texto:
            for lado in ("jp", "en"):
                if g[lado] and h[lado] not in md5_vistos[lado]:
                    md5_vistos[lado].add(h[lado])
                    try:
                        b, (larg, alt) = png(g[lado])
                    except Exception as e:  # noqa: BLE001
                        print("falhou", lado, c, e)
                        continue
                    p = dst / lado / (c.replace("/", "__") + ".png")
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_bytes(b)
        linhas.append(dict(caminho=c, formato=FORMAT_NAMES.get(peek_format(ref), "?"), larg=larg, alt=alt,
                           md5_jp=h["jp"], md5_en=h["en"],
                           estado="igual" if h["jp"] == h["en"] else ("so_jp" if not h["en"] else
                                                                      "so_en" if not h["jp"] else "diferente"),
                           grupo="cena_sem_texto" if sem_texto else ("cena" if cena else "global")))
    dst.mkdir(parents=True, exist_ok=True)
    with open(dst / "inventario.tsv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0]), delimiter="\t")
        w.writeheader()
        w.writerows(linhas)
    from collections import Counter
    print(Counter((l["grupo"], l["estado"]) for l in linhas))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("acao", choices=["inventario"])
    ap.add_argument("--disco", default="1")
    a = ap.parse_args()
    if a.disco != "1":
        sys.exit("Disco 2 só com autorização explícita do autor")
    inventario(a.disco)
