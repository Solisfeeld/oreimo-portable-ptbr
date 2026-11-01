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
BASE_JP = ROOT / "build" / "eboot" / "EBOOT_jp_dec.elf"
ELF = 0xC0                                       # offset no arquivo = vaddr + 0xC0
BASE_RAM = 0x08804000
LARGURA_AUTO = (0x367E0, 0x36808, 0x44C60, 0x44D4C, 0x4EF1C, 0x61EB8)   # `ori rX,zero,470`: largura da quebra automática do motor
SCE_FONT_OPEN, SCE_FONT_OPEN_USER_FILE = 0xA834319D, 0x57FCB733
NID_FONT_OPEN = 0x20ACEC                         # entrada de importação da chamada em 0xACCF4 (única)
ARGUMENTO = 0xACCE0                              # lw a0,44(sp) / bne a0,zero / or a1,v0,zero: entre FindOptimumFont e sceFontOpen
TEXTO_LIVRE = 0x216634                           # mensagem de erro de sceFontOpenUserMemory, que o jogo não usa
FONTE_DISCO = b"disc0:/PSP_GAME/INSDIR/FONTE.PGF\0"
TABELA = 0x23B870
ACENTOS = "áàâãéêíóôõúüçÁÀÂÃÉÊÍÓÔÕÚÜÇ"
# 25/10: os códigos 0xA1–0xA5 (｡｢｣､･) NÃO são livres — na Conversa a Dois o jogo converte o 「 da fala para ｢ (0xA2), e
# com a 1ª tabela (0xA1–0xBA) ele aparecia como "à". Agora só katakana de meia largura que não aparecem em nenhum texto
# exibido (PT: ﾉ ｼ ﾟ ･ em emoticons; nome do jogo em JP: ﾎ ﾟ ｰ ﾀ ﾌ ﾞ ﾙ) — fora também ｰ, ﾞ, ﾟ
CODIGOS = [c for c in range(0xB1, 0xDE) if c not in (0xBC, 0xC0, 0xC9, 0xCC, 0xCE, 0xD9)][:len(ACENTOS)]
MAPA = dict(zip(ACENTOS, CODIGOS))                               # letra → byte cp932 remapeado


def fonte_propria(d):
    """Sobre o EBOOT japonês: sem quebra automática (o texto PT já traz as quebras) e sceFontOpen trocado por sceFontOpenUserFile,
    com o caminho da fonte PT no 2º argumento. Os demais argumentos e o tratamento de erro são os do próprio jogo."""
    for v in LARGURA_AUTO:
        if struct.unpack_from("<H", d, v + ELF)[0] != 0x1D6:
            raise ValueError(f"constante inesperada em {v:#x}")
        struct.pack_into("<H", d, v + ELF, 0x500)
    if struct.unpack_from("<I", d, NID_FONT_OPEN + ELF)[0] != SCE_FONT_OPEN:
        raise ValueError("importação de sceFontOpen não encontrada")
    struct.pack_into("<I", d, NID_FONT_OPEN + ELF, SCE_FONT_OPEN_USER_FILE)
    if struct.unpack_from("<3I", d, ARGUMENTO + ELF) != (0x8FA4002C, 0x14800008, 0x00402825):
        raise ValueError("ponto da chamada inesperado")
    end = BASE_RAM + TEXTO_LIVRE
    struct.pack_into("<3I", d, ARGUMENTO + ELF, 0x3C050000 | end >> 16, 0x34A50000 | end & 0xFFFF, 0)
    if not bytes(d[TEXTO_LIVRE + ELF:TEXTO_LIVRE + ELF + 29]) == b"Error (sceFontOpenUserMemory)":
        raise ValueError("texto inesperado")
    d[TEXTO_LIVRE + ELF:TEXTO_LIVRE + ELF + len(FONTE_DISCO)] = FONTE_DISCO


def construir(base_jp=False):
    d = bytearray((BASE_JP if base_jp else BASE).read_bytes())
    if d[:4] != b"\x7fELF":
        raise ValueError("EBOOT base não é o ELF decifrado")
    if base_jp:
        fonte_propria(d)
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
