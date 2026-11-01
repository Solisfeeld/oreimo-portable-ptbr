#!/usr/bin/env python3
"""Decodifica texturas GIM do PSP para PNG. Requer Pillow. Somente leitura: não grava GIM.

    python3 ferramentas/gim.py info ARQUIVO.gim
    python3 ferramentas/gim.py png ARQUIVO.gim saida.png

Aceita GIM cru ou compactado com gzip. Formatos suportados: RGBA8888, P4 e P8 (os únicos usados neste jogo), little-endian.
"""
import argparse
import gzip
import struct
import sys
from collections import namedtuple
from pathlib import Path

MAGICA = b"MIG."
Bloco = namedtuple("Bloco", "tipo ini dados")
Info = namedtuple("Info", "largura altura formato ordem bpp pixels")
RGBA8888, P4, P8 = 3, 4, 5
NOMES = {0: "RGBA5650", 1: "RGBA5551", 2: "RGBA4444", 3: "RGBA8888", 4: "P4", 5: "P8"}


def desembrulhar(b):
    return gzip.decompress(b) if b[:2] == b"\x1f\x8b" else b


def _blocos(g, p, fim):
    while p + 16 <= fim:
        tipo, _z, tam, prox, dados = struct.unpack_from("<HHIII", g, p)
        yield Bloco(tipo, p, p + dados)
        if tipo in (2, 3) and dados:
            yield from _blocos(g, p + dados, p + tam)
        if not prox:
            return
        p += prox


def _imagem(g, b):
    _h, _r, formato, ordem, largura, altura, bpp = struct.unpack_from("<HHHHHHH", g, b.dados)
    pixels = struct.unpack_from("<I", g, b.dados + 0x1C)[0]
    return Info(largura, altura, formato, ordem, bpp, b.dados + pixels)


def ler_info(g):
    if g[:4] != MAGICA:
        raise ValueError("não é um GIM little-endian")
    for b in _blocos(g, 16, len(g)):
        if b.tipo == 4:
            return _imagem(g, b)
    raise ValueError("GIM sem bloco de imagem")


def _desembaralhar(dados, largura_bytes, altura):
    """Ordem "rápida" do PSP: blocos de 16 × 8 bytes."""
    saida = bytearray(len(dados))
    i = 0
    for by in range(0, altura, 8):
        for bx in range(0, largura_bytes, 16):
            for y in range(by, min(by + 8, altura)):
                d = y * largura_bytes + bx
                saida[d:d + 16] = dados[i + (y - by) * 16:i + (y - by) * 16 + 16]
            i += 128
    return bytes(saida)


def decodificar(g):
    """-> PIL.Image RGBA."""
    from PIL import Image
    g = desembrulhar(g)
    info = ler_info(g)
    if info.formato not in (RGBA8888, P4, P8):
        raise ValueError(f"formato não suportado: {NOMES.get(info.formato, info.formato)}")
    palhetas = [_imagem(g, b) for b in _blocos(g, 16, len(g)) if b.tipo == 5]
    bits = {RGBA8888: 32, P8: 8, P4: 4}[info.formato]
    # linhas alinhadas a 16 bytes e altura a múltiplos de 8, como o PSP guarda
    passo = (info.largura * bits + 127) // 128 * 16
    altura = (info.altura + 7) // 8 * 8
    bruto = g[info.pixels:info.pixels + passo * altura]
    if info.ordem == 1:
        bruto = _desembaralhar(bruto, passo, altura)
    if info.formato == RGBA8888:
        linhas = b"".join(bruto[y * passo:y * passo + info.largura * 4] for y in range(info.altura))
        return Image.frombytes("RGBA", (info.largura, info.altura), linhas)
    if not palhetas or palhetas[0].formato != RGBA8888:
        raise ValueError("palheta ausente ou em formato não suportado")
    pal = palhetas[0]
    cores = g[pal.pixels:pal.pixels + pal.largura * 4]
    tabela = [cores[i:i + 4].ljust(4, b"\0") for i in range(0, 1024, 4)]
    if info.formato == P8:
        indices = [bruto[y * passo + x] for y in range(info.altura) for x in range(info.largura)]
    else:
        indices = [(bruto[y * passo + x // 2] >> (4 if x & 1 else 0)) & 15 for y in range(info.altura) for x in range(info.largura)]
    return Image.frombytes("RGBA", (info.largura, info.altura), b"".join(tabela[i] for i in indices))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="acao", required=True)
    p = sub.add_parser("info")
    p.add_argument("arquivo")
    p = sub.add_parser("png")
    p.add_argument("arquivo")
    p.add_argument("saida")
    a = ap.parse_args()
    g = desembrulhar(Path(a.arquivo).read_bytes())
    if a.acao == "info":
        i = ler_info(g)
        print(f"{i.largura}×{i.altura} {NOMES.get(i.formato, i.formato)} ordem={i.ordem}")
    else:
        decodificar(g).save(a.saida)
        print("->", a.saida)
    return 0


if __name__ == "__main__":
    sys.exit(main())
