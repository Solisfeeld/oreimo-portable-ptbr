#!/usr/bin/env python3
"""Leitura e montagem de contêineres GPDA (RES.DAT, first.dat e pacotes aninhados). Biblioteca padrão.

    python3 ferramentas/gpda.py listar ARQUIVO [--recursivo]
    python3 ferramentas/gpda.py extrair ARQUIVO CAMINHO/INTERNO destino

Formato em docs/FORMATOS.md §2. Entradas sem nome (variante dos pacotes de personagens) recebem o nome "#N".
"""
import argparse
import struct
import sys
from collections import namedtuple
from pathlib import Path

Entrada = namedtuple("Entrada", "name data_offset data_size")
MAGICA = b"GPDA"
ALINHAMENTO = 0x800


def parse_gpda(dados):
    if dados[:4] != MAGICA:
        raise ValueError("não é um GPDA")
    n = struct.unpack_from("<I", dados, 12)[0]
    if 16 + n * 16 > len(dados):
        raise ValueError("tabela de entradas fora do arquivo")
    entradas = []
    for i in range(n):
        ini, _zero, tam, nome = struct.unpack_from("<IIII", dados, 16 + i * 16)
        if ini + tam > len(dados):
            raise ValueError(f"entrada {i} fora do arquivo")
        rotulo = f"#{i}"
        if nome and nome + 4 <= len(dados):
            comp = struct.unpack_from("<I", dados, nome)[0]
            if nome + 4 + comp <= len(dados):
                rotulo = dados[nome + 4:nome + 4 + comp].decode("cp932", "replace")
        entradas.append(Entrada(rotulo, ini, tam))
    return entradas


def build_gpda(itens):
    """Monta um GPDA a partir de [(nome, bytes)]: dados alinhados em 0x800, tamanho total múltiplo de 0x800."""
    nomes = [n.encode("cp932") for n, _d in itens]
    p = 16 + 16 * len(itens)
    pos_nomes = []
    for n in nomes:
        pos_nomes.append(p)
        p += 4 + len(n)
    p = (p + ALINHAMENTO - 1) // ALINHAMENTO * ALINHAMENTO
    tabela, corpo = bytearray(), bytearray()
    inicio = p
    for pos, (_n, d) in zip(pos_nomes, itens):
        tabela += struct.pack("<IIII", p, 0, len(d), pos)
        corpo += d
        p += len(d)
        resto = -p % ALINHAMENTO
        corpo += bytes(resto)
        p += resto
    saida = bytearray(MAGICA + struct.pack("<III", p, 0, len(itens)) + tabela)
    for n in nomes:
        saida += struct.pack("<I", len(n)) + n
    saida += bytes(inicio - len(saida))
    return bytes(saida + corpo)


def percorrer(dados, caminho="", profundidade=6):
    """Gera (caminho, bytes) de cada folha, descendo por GPDAs aninhados."""
    if profundidade and dados[:4] == MAGICA:
        try:
            filhos = parse_gpda(dados)
        except ValueError:
            filhos = None
        if filhos:
            for e in filhos:
                yield from percorrer(dados[e.data_offset:e.data_offset + e.data_size],
                                     f"{caminho}/{e.name.strip()}", profundidade - 1)
            return
    yield caminho, dados


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="acao", required=True)
    p = sub.add_parser("listar")
    p.add_argument("arquivo")
    p.add_argument("--recursivo", action="store_true")
    p = sub.add_parser("extrair")
    p.add_argument("arquivo")
    p.add_argument("interno")
    p.add_argument("destino")
    a = ap.parse_args()
    dados = Path(a.arquivo).read_bytes()
    if a.acao == "listar":
        if a.recursivo:
            for c, b in percorrer(dados):
                print(f"{len(b):>12,}  {c}")
        else:
            for e in parse_gpda(dados):
                print(f"{e.data_size:>12,}  {e.name.strip()}")
        return 0
    alvo = "/" + a.interno.strip("/")
    for c, b in percorrer(dados):
        if c == alvo:
            Path(a.destino).write_bytes(b)
            print(f"{len(b):,} bytes -> {a.destino}")
            return 0
    print("caminho interno não encontrado:", alvo, file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
