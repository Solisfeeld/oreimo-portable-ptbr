#!/usr/bin/env python3
"""Testa as ferramentas independentes com dados sintéticos: não precisa do jogo.

    python3 testes/teste_independente.py
"""
import gzip
import os
import struct
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "ferramentas"))
import envpsp  # noqa: E402
import gim  # noqa: E402
import gpda  # noqa: E402
import isofs  # noqa: E402
import mipsdis  # noqa: E402
import oreimo_script as osc  # noqa: E402
import quebra  # noqa: E402

ok = falhas = 0


def confere(condicao, nome):
    global ok, falhas
    if condicao:
        ok += 1
    else:
        falhas += 1
    print(f"[{'OK ' if condicao else 'ERR'}] {nome}")


def registro(nome, lba, tam, e_dir=False):
    corpo = bytearray(33 + len(nome) + (1 - len(nome) % 2))
    corpo[0] = len(corpo)
    struct.pack_into("<I", corpo, 2, lba)
    struct.pack_into(">I", corpo, 6, lba)
    struct.pack_into("<I", corpo, 10, tam)
    struct.pack_into(">I", corpo, 14, tam)
    corpo[25] = 2 if e_dir else 0
    corpo[32] = len(nome)
    corpo[33:33 + len(nome)] = nome
    return bytes(corpo)


def iso_sintetica(caminho):
    """ISO9660 mínima: /PSP_GAME/TESTE.BIN."""
    S = isofs.SETOR
    conteudo = b"conteudo de teste"
    img = bytearray(24 * S)
    img[16 * S:16 * S + 6] = b"\x01CD001"
    raiz = registro(b"\0", 20, S, True) + registro(b"\1", 20, S, True) + registro(b"PSP_GAME", 21, S, True)
    sub = registro(b"\0", 21, S, True) + registro(b"\1", 20, S, True) + registro(b"TESTE.BIN;1", 22, len(conteudo))
    img[16 * S + 156:16 * S + 156 + 34] = registro(b"\0", 20, S, True)
    img[20 * S:20 * S + len(raiz)] = raiz
    img[21 * S:21 * S + len(sub)] = sub
    img[22 * S:22 * S + len(conteudo)] = conteudo
    Path(caminho).write_bytes(img)
    return conteudo


def bloco_gim(tipo, tam_dados_filhos, corpo=b""):
    return struct.pack("<HHIII", tipo, 0, 16 + tam_dados_filhos + len(corpo), 16 + tam_dados_filhos + len(corpo), 16) + corpo


def imagem_gim(formato, ordem, largura, altura, pixels, tipo=4):
    cab = struct.pack("<HHHHHHH", 0x40, 0, formato, ordem, largura, altura, {3: 32, 4: 4, 5: 8}[formato])
    cab = cab.ljust(0x1C, b"\0") + struct.pack("<I", 0x40)
    return bloco_gim(tipo, 0, cab.ljust(0x40, b"\0") + pixels)


def gim_sintetico(imagem, palheta=b""):
    filhos = imagem + palheta
    foto = bloco_gim(3, 0, filhos)
    raiz = bloco_gim(2, 0, foto)
    return b"MIG.00.1PSP\0" + bytes(4) + raiz


def testar_iso():
    with tempfile.TemporaryDirectory() as t:
        p = os.path.join(t, "x.iso")
        c = iso_sintetica(p)
        nomes = [e.path for e in isofs.entries(p)]
        confere(nomes == ["/PSP_GAME", "/PSP_GAME/TESTE.BIN"], "isofs lista arquivos e diretórios")
        confere(isofs.read_file(p, "/PSP_GAME/TESTE.BIN") == c, "isofs lê o conteúdo")


def testar_gpda():
    dentro = gpda.build_gpda([("a.bin", b"abc"), ("b.bin", b"defg")])
    fora = gpda.build_gpda([("pasta", dentro), ("c.bin", b"x" * 5000)])
    confere(len(fora) % 0x800 == 0, "gpda: tamanho múltiplo de 0x800")
    confere({c: b for c, b in gpda.percorrer(fora)} == {"/pasta/a.bin": b"abc", "/pasta/b.bin": b"defg", "/c.bin": b"x" * 5000},
            "gpda: montagem e leitura aninhada")
    confere(all(e.data_offset % 0x800 == 0 for e in gpda.parse_gpda(fora)), "gpda: dados alinhados")
    invalido = False
    try:
        gpda.parse_gpda(b"NADA" * 8)
    except ValueError:
        invalido = True
    confere(invalido, "gpda: recusa arquivo inválido")


def testar_gim():
    from PIL import Image
    rgba = bytes((10, 20, 30, 255)) * 16 * 8
    g = gim_sintetico(imagem_gim(3, 0, 16, 8, rgba))
    im = gim.decodificar(g)
    confere(im.size == (16, 8) and im.getpixel((3, 3)) == (10, 20, 30, 255), "gim: RGBA8888")
    pal = bytes(c for i in range(256) for c in (i, 255 - i, 0, 255))
    p = imagem_gim(3, 0, 256, 1, pal, tipo=5)
    idx = bytes(range(16)) * 8
    confere(gim.decodificar(gim_sintetico(imagem_gim(5, 0, 16, 8, idx), p)).getpixel((5, 2)) == (5, 250, 0, 255), "gim: P8")
    p4 = bytes((0x21,)) * 32
    im = gim.decodificar(gim_sintetico(imagem_gim(4, 0, 16, 8, p4.ljust(128, b"\x21")), p))
    confere(im.getpixel((0, 0))[:2] == (1, 254) and im.getpixel((1, 0))[:2] == (2, 253), "gim: P4, nibble baixo primeiro")
    # ordem rápida: 32×8 em P8 = 2 blocos de 16×8 guardados em sequência
    a, b = bytes((1,)) * 128, bytes((2,)) * 128
    im = gim.decodificar(gim_sintetico(imagem_gim(5, 1, 32, 8, a + b), p))
    confere(im.getpixel((3, 3))[0] == 1 and im.getpixel((20, 3))[0] == 2, "gim: blocos da ordem rápida")
    confere(gim.ler_info(gzip.compress(g)[:0] or g).largura == 16, "gim: leitura do cabeçalho")
    confere(isinstance(im, Image.Image), "gim: devolve imagem Pillow")


def testar_obj():
    b1 = osc.new_dialogue_block("Nome「Olá」", 7)
    salto = struct.pack("<IHB", 16, 702, 0) + bytes(9)
    cab = struct.pack("<II", 2, osc.OBJ_HEADER_LEN).ljust(osc.OBJ_HEADER_LEN, b"\0")
    obj = cab + b1.raw + salto
    o = osc.parse_obj(obj)
    confere([b.type for b in o.blocks] == [100, 702] and o.blocks[0].msg_id == 7, "obj: leitura dos blocos")
    confere(osc.split_speaker(o.blocks[0].text) == ("Nome", "Olá"), "obj: separa nome e fala")
    confere(osc.build_obj(o) == obj, "obj: remontagem idêntica")
    cont = osc.new_dialogue_block("continuação")
    o.blocks.insert(1, cont)
    confere(len(osc.parse_obj(osc.build_obj(o)).blocks) == 3, "obj: inserção de caixa")


def testar_envpsp():
    d = b"\x01\x00\x01\x00" + struct.pack("<I", 42) + struct.pack("<I", 6) + "Opções".encode("utf-16-le") + struct.pack("<I", 7)
    cab, toks = envpsp.tokenize(d)
    confere(("s", "Opções") in toks, "envpsp: acha a string")
    confere(envpsp.build(cab, toks) == d, "envpsp: remontagem idêntica")


def testar_quebra():
    largura = lambda s, fala: 10 * len(s)
    lay = quebra.Layout(largura, 200)
    caixas = lay.layout("uma frase bem comum que precisa de duas linhas para caber aqui", False)
    linhas = [ln for c in caixas for ln in c]
    confere(all(largura(ln, False) <= 200 for ln in linhas), "quebra: respeita a largura")
    confere(" ".join(linhas).split() == "uma frase bem comum que precisa de duas linhas para caber aqui".split(), "quebra: não perde palavras")


def testar_mips():
    confere("addiu" in str(mipsdis.dis(0x27BDFFF0, 0)), "mipsdis: desmonta addiu")


if __name__ == "__main__":
    for f in (testar_iso, testar_gpda, testar_gim, testar_obj, testar_envpsp, testar_quebra, testar_mips):
        f()
    print(f"\nRESUMO: {ok}/{ok + falhas} verificações OK")
    sys.exit(1 if falhas else 0)
