"""EBOOT PT: acentos nos textos cp932 (títulos do Álbum).

O jogo converte texto Shift-JIS com o mbtowc do newlib (locale "C-SJIS") e depois usa uma tabela própria
código→Unicode no EBOOT (offset de arquivo 0x23B870, u16 por código; 1 byte = índice 0x00–0xFF, 2 bytes = código
JIS). Os códigos de 1 byte 0xA1–0xDF são pontuação e katakana de meia largura (U+FF61…); nenhum arquivo cp932 do jogo
os usa (o único cp932 com texto é o AlbumList.txt), mas o motor converte 「 para ｢ na Conversa a Dois (ver CODIGOS).
Remapeamos 26 katakana para as letras
acentuadas do português, que a fonte do jogo (font.pgf) já tem — os diálogos usam as mesmas.
Base: EBOOT da ISO EN decifrado pelo PPSSPP (build/eboot/EBOOT_en_dec.elf; PRX, roda decifrado no PPSSPP).
"""
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "build" / "eboot" / "EBOOT_en_dec.elf"
TABELA = 0x23B870
ACENTOS = "áàâãéêíóôõúüçÁÀÂÃÉÊÍÓÔÕÚÜÇ"
# 25/10: os códigos 0xA1–0xA5 (｡｢｣､･) NÃO são livres — na Conversa a Dois o jogo converte o 「 da fala para ｢ (0xA2), e
# com a 1ª tabela (0xA1–0xBA) ele aparecia como "à". Agora só katakana de meia largura que não aparecem em nenhum texto
# exibido (PT: ﾉ ｼ ﾟ ･ em emoticons; nome do jogo em JP: ﾎ ﾟ ｰ ﾀ ﾌ ﾞ ﾙ) — fora também ｰ, ﾞ, ﾟ
CODIGOS = [c for c in range(0xB1, 0xDE) if c not in (0xBC, 0xC0, 0xC9, 0xCC, 0xCE, 0xD9)][:len(ACENTOS)]
MAPA = dict(zip(ACENTOS, CODIGOS))                               # letra → byte cp932 remapeado


def construir():
    d = bytearray(BASE.read_bytes())
    if d[:4] != b"\x7fELF":
        raise ValueError("EBOOT base não é o ELF decifrado")
    for c, b in MAPA.items():
        o = TABELA + 2 * b
        atual = struct.unpack_from("<H", d, o)[0]
        if atual not in (0xFF61 + (b - 0xA1), ord(c)):
            raise ValueError(f"tabela inesperada no código {b:#x}: {atual:#x}")
        struct.pack_into("<H", d, o, ord(c))
    return bytes(d), {"codigos_remapeados": len(MAPA)}


def codificar(texto: str) -> bytes:
    """cp932, com as letras acentuadas nos bytes remapeados."""
    out = bytearray()
    for c in texto:
        out += bytes([MAPA[c]]) if c in MAPA else c.encode("cp932")
    return bytes(out)
