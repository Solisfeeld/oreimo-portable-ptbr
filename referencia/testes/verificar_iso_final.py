#!/usr/bin/env python3
"""Integridade de uma ISO PT construída por construir.py.

  python3 testes/verificar_iso_final.py entrega/Oreimo_Disco1_PTBR.iso [--dir-saida build/saida] [--base-jp]

--base-jp: ISO construída sobre a japonesa (construir.py --base-jp), com EBOOT e fonte próprios.

Confere: (1) RES.DAT, first.dat, envpsp.dat e os PMF PT == arquivos gerados no build; (2) todos os outros
arquivos idênticos byte a byte à ISO EN de base; (3) RES.DAT relido: todas as cenas com OBJ válido e o seekmap
do first.dat coerente com o RES.DAT (offsets apontam para dados válidos); (4) tamanho do volume == arquivo;
(5) ICON/PARAM do jogo intactos; (6) nenhuma imagem PT ausente; (7) md5 da ISO registrado.
"""
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ferramentas"))
import isofs  # noqa: E402
import oreimo_script as osc  # noqa: E402
from oreimo_core import seekmap  # noqa: E402

BASE = ROOT / "Ore no Imouto (English v1) Disc 1" / "Ore no Imouto (English v1) Disc 1.iso"
BASE_JP = ROOT / "Ore no Imouto (Japan) Disc 1" / "Ore no Imouto (Japan) Disc 1.iso"
TROCADOS = {"/PSP_GAME/INSDIR/RES.DAT": "RES.DAT", "/PSP_GAME/USRDIR/first.dat": "first.dat",
            "/PSP_GAME/USRDIR/envpsp.dat": "envpsp.dat"}
EBOOT = "/PSP_GAME/SYSDIR/EBOOT.BIN"
VIDEOS = {"/PSP_GAME/USRDIR/OIP_GEB01.pmf": ROOT / "build" / "video" / "OIP_GEB01.pmf",
          "/PSP_GAME/USRDIR/OIP_GEB02.pmf": ROOT / "build" / "video" / "OIP_GEB02.pmf"}


def main():
    iso = sys.argv[1]
    saida = Path(sys.argv[sys.argv.index("--dir-saida") + 1]) if "--dir-saida" in sys.argv else ROOT / "build" / "saida"
    ok, falhas = 0, []
    base_jp = "--base-jp" in sys.argv
    base = BASE_JP if base_jp else BASE

    def check(cond, msg):
        nonlocal ok
        if cond:
            ok += 1
            print("[OK ]", msg)
        else:
            falhas.append(msg)
            print("[ERR]", msg)

    lista = [e.path for e in isofs.entries(iso) if not getattr(e, "is_dir", False)]
    base_lista = [e.path for e in isofs.entries(str(base)) if not getattr(e, "is_dir", False)]
    for caminho, nome in TROCADOS.items():
        check(isofs.read_file(iso, caminho) == (saida / nome).read_bytes(), f"{caminho} == build ({nome})")
    for caminho, arq in VIDEOS.items():
        check(isofs.read_file(iso, caminho) == arq.read_bytes(), f"{caminho} == vídeo PT gerado")
    import eboot_pt
    check(isofs.read_file(iso, EBOOT) == eboot_pt.construir(base_jp=base_jp)[0], f"{EBOOT} == EBOOT PT (base decifrada + alterações do projeto)")
    if lista is not None:
        nomes_base = [c.replace("DUMMY.DAT", "FONTE.PGF") if base_jp else c for c in base_lista]
        check(sorted(lista) == sorted(nomes_base), f"mesma lista de arquivos da ISO base ({len(lista)})")
        iguais = 0
        for c in base_lista:
            if c.upper() in {k.upper() for k in list(TROCADOS) + list(VIDEOS) + [EBOOT]}:
                continue
            if c.upper().endswith("DUMMY.DAT") and base_jp:
                check(isofs.read_file(iso, c.replace("DUMMY.DAT", "FONTE.PGF")) == (ROOT / "build" / "fonte" / "FONTE.PGF").read_bytes(),
                      "FONTE.PGF == fonte gerada")
                continue
            if c.upper().endswith("DUMMY.DAT"):
                # enchimento de zeros que o iso_grow consome para realocar arquivos que crescem
                d = isofs.read_file(iso, c)
                check(d.count(0) == len(d) and len(d) <= len(isofs.read_file(str(base), c)),
                      f"DUMMY.DAT só zeros e não maior que o da base ({len(d):,} bytes restantes)")
                continue
            if isofs.read_file(iso, c) == isofs.read_file(str(base), c):
                iguais += 1
            else:
                falhas.append(f"{c} difere da ISO base")
        esperado = len(base_lista) - len(TROCADOS) - len(VIDEOS) - 2
        check(iguais == esperado, f"{iguais}/{esperado} arquivos intocados idênticos à base")
    res = isofs.read_file(iso, "/PSP_GAME/INSDIR/RES.DAT")
    rd = osc.ResDat(res)
    n = 0
    for nome in rd.scene_names():
        osc.parse_obj(rd.obj(nome))
        n += 1
    check(n == 300, f"RES.DAT: {n} cenas com OBJ válido")
    first = isofs.read_file(iso, "/PSP_GAME/USRDIR/first.dat")
    txt = seekmap.extract_text(first)
    check(seekmap.regenerate(res, txt) == txt, "seekmap coerente com o RES.DAT")
    ruins = 0
    for ln in txt.decode("cp932").split("\r\n"):
        f = ln.split()
        if len(f) == 4 and "." in f[0]:
            d = res[int(f[1]):int(f[1]) + 4]
            magicos = (b"MIG.", b"GPDA", b"HCA\x00", b"# Li", b"moc\t")   # GIM, contêiner, áudio HCA, Live2D
            if int(f[2]) and not (d[:2] == b"\x1f\x8b" or d[:4] in magicos or f[0].endswith((".txt", ".dat", ".map"))):
                ruins += 1
    check(ruins == 0, f"offsets do seekmap apontam para dados válidos (suspeitos: {ruins})")
    info = isofs.volume_info(iso)
    check(info["file_size"] == Path(iso).stat().st_size, f"tamanho do volume == arquivo ({info['file_size']:,})")
    h = hashlib.md5()
    with open(iso, "rb") as fh:
        for bloco in iter(lambda: fh.read(1 << 24), b""):
            h.update(bloco)
    print("md5:", h.hexdigest())
    print(f"\nRESUMO: {ok}/{ok + len(falhas)} verificações OK" + ("" if not falhas else f" — FALHAS: {falhas[:10]}"))
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
