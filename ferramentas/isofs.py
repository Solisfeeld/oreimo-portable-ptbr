#!/usr/bin/env python3
"""Leitura de imagens ISO9660 de PSP. Biblioteca padrão, somente leitura: nunca grava na ISO.

    python3 ferramentas/isofs.py listar ISO
    python3 ferramentas/isofs.py extrair ISO /PSP_GAME/INSDIR/RES.DAT destino
    python3 ferramentas/isofs.py info ISO
"""
import argparse
import struct
import sys
from collections import namedtuple
from pathlib import Path

SETOR = 2048
Item = namedtuple("Item", "path lba size is_dir")


def _registros(f, lba, tam):
    f.seek(lba * SETOR)
    bloco = f.read(tam)
    p = 0
    while p < len(bloco):
        comp = bloco[p]
        if comp == 0:                                  # o restante do setor não tem registros
            p = (p // SETOR + 1) * SETOR
            continue
        extensao = struct.unpack_from("<I", bloco, p + 2)[0]
        tamanho = struct.unpack_from("<I", bloco, p + 10)[0]
        flags = bloco[p + 25]
        n = bloco[p + 32]
        nome = bloco[p + 33:p + 33 + n]
        yield nome, extensao, tamanho, bool(flags & 2)
        p += comp


def entries(iso):
    """Lista de Item (arquivos e diretórios), com caminhos absolutos."""
    with open(iso, "rb") as f:
        f.seek(16 * SETOR)
        pvd = f.read(SETOR)
        if pvd[1:6] != b"CD001":
            raise ValueError("não é uma ISO9660")
        raiz = struct.unpack_from("<I", pvd, 156 + 2)[0], struct.unpack_from("<I", pvd, 156 + 10)[0]
        saida, pilha = [], [("", *raiz)]
        while pilha:
            base, lba, tam = pilha.pop()
            for nome, ext, tamanho, e_dir in _registros(f, lba, tam):
                if nome in (b"\0", b"\1"):
                    continue
                texto = nome.decode("ascii", "replace").split(";")[0]
                caminho = f"{base}/{texto}"
                saida.append(Item(caminho, ext, tamanho, e_dir))
                if e_dir:
                    pilha.append((caminho, ext, tamanho))
    return sorted(saida, key=lambda i: i.path)


def read_file(iso, interno):
    for e in entries(iso):
        if e.path.upper() == interno.upper() and not e.is_dir:
            with open(iso, "rb") as f:
                f.seek(e.lba * SETOR)
                return f.read(e.size)
    raise FileNotFoundError(interno)


def volume_info(iso):
    with open(iso, "rb") as f:
        f.seek(16 * SETOR)
        pvd = f.read(SETOR)
    return {"volume": pvd[40:72].decode("ascii", "replace").strip(),
            "setores": struct.unpack_from("<I", pvd, 80)[0],
            "file_size": Path(iso).stat().st_size}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="acao", required=True)
    p = sub.add_parser("listar")
    p.add_argument("iso")
    p = sub.add_parser("extrair")
    p.add_argument("iso")
    p.add_argument("interno")
    p.add_argument("destino")
    p = sub.add_parser("info")
    p.add_argument("iso")
    a = ap.parse_args()
    if a.acao == "listar":
        for e in entries(a.iso):
            print(f"{'<dir>' if e.is_dir else format(e.size, ','):>16}  {e.path}")
    elif a.acao == "extrair":
        dados = read_file(a.iso, a.interno)
        Path(a.destino).write_bytes(dados)
        print(f"{len(dados):,} bytes -> {a.destino}")
    else:
        for k, v in volume_info(a.iso).items():
            print(f"{k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
