#!/usr/bin/env python3
"""(SÓ TESTE) Cópia de uma ISO com uma textura visível no lugar de outra, para provar se o motor aceita um arquivo GIM.

    python3 ferramentas/iso_troca_textura.py <iso> <saida.iso> <textura trocada> <arquivo.gim | iso:caminho interno>

Ex.: bl_voiceon.gim (ícone do Histórico) recebe sg_hint_good.gim, que não aparece no jogo sem liberar a opção de dicas.
Nunca entra na entrega: grava em build/iso_teste/.
"""
import gzip
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import isofs  # noqa: E402
from oreimo_core import gpda, iso_grow, seekmap  # noqa: E402

RES, FIRST = "/PSP_GAME/INSDIR/RES.DAT", "/PSP_GAME/USRDIR/first.dat"


def trocar(blob, alvo, novo, achou):
    itens, mudou = [], False
    for x in gpda.parse_gpda(blob):
        d = blob[x.data_offset:x.data_offset + x.data_size]
        if d[:4] == b"GPDA":
            nd = trocar(d, alvo, novo, achou)
        elif x.name.strip() == alvo:
            nd = gzip.compress(novo, 9, mtime=0) if d[:2] == b"\x1f\x8b" else novo
            achou.append(x.name.strip())
        else:
            nd = d
        mudou |= nd is not d
        itens.append((x.name, nd))
    return gpda.build_gpda(itens) if mudou else blob


def main():
    iso, saida, alvo, fonte = sys.argv[1:5]
    novo = Path(fonte).read_bytes()
    if novo[:2] == b"\x1f\x8b":
        novo = gzip.decompress(novo)
    res, first = isofs.read_file(iso, RES), isofs.read_file(iso, FIRST)
    achou = []
    res2 = trocar(res, alvo, novo, achou)
    txt = seekmap.regenerate(res2, seekmap.extract_text(first))
    iso_grow.write_files_into_iso(iso, {RES: res2, FIRST: seekmap.rebuild_first_dat(first, txt)}, saida)
    print(f"{saida}: {alvo} <- {fonte} ({len(achou)} cópias, formato {novo[:4]!r})")


if __name__ == "__main__":
    main()
