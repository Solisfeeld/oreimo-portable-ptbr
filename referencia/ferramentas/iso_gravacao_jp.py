#!/usr/bin/env python3
"""(SÓ TESTE) ISO japonesa original em que "Initial start" abre direto outra cena.

  python3 ferramentas/iso_gravacao_jp.py BKIR_0083T build/iso_teste/Oreimo_JP_gravacao_BKIR_0083T.iso
  # PT (inspeção com a pasta inteira da cena, p.ex. para ver os balões de réplica):
  python3 ferramentas/iso_gravacao_jp.py DSAO_0003T build/iso_teste/Oreimo_D1_inspecao_DSAO_0003T.iso --base build/saida_img
     (--base = dir com RES.DAT/first.dat/envpsp.dat gerados por construir.py --dir-saida; a ISO-base vira a EN)

Copia a pasta INTEIRA da cena (OBJ, voicepack, cutin, tukkomi, fundos, personagens) para o
lugar de script/AKYO_0000A no RES.DAT do Disco 1 JP — o .obj.gz recebe o nome que o jogo
procura (000scriptAKYO_0000A.obj.gz). O seekmap é regenerado; o 4º campo (checksum que o jogo
não confere: os patches EN/ES o copiam sem recalcular) segue o arquivo de origem pelo caminho.
Nunca altera a ISO original: grava uma cópia em build/iso_teste/. Só para gravação/inspeção.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ferramentas"))
import io  # noqa: E402
import struct  # noqa: E402
import isofs  # noqa: E402
import oreimo_script as osc  # noqa: E402
from oreimo_core import gpda, iso_grow, seekmap  # noqa: E402

ISO_JP = ROOT / "Ore no Imouto (Japan) Disc 1" / "Ore no Imouto (Japan) Disc 1.iso"
ALVO = "AKYO_0000A"


def seekmap_por_caminho(res, old_text, troca):
    """Como seekmap.regenerate, mas o checksum vem do caminho de origem (troca: novo->origem)."""
    linhas = old_text.decode("cp932").split("\r\n")
    hashes, pilha = {}, []
    for ln in linhas:
        if not ln.strip():
            continue
        d = len(ln) - len(ln.lstrip("\t"))
        campos = ln.split()
        pilha[d:] = [campos[0]]
        hashes["/".join(pilha)] = campos[3]  # raiz e folhas: nome offset tamanho hash
    out = io.StringIO()

    def h(caminho):
        for novo, orig in troca.items():
            caminho = caminho.replace(novo, orig)
        return hashes.get(caminho, "0")

    def walk(off, nivel, caminho):
        _m, tam, _u, n = struct.unpack_from("<4sIII", res, off)
        out.write(f"{tam} {h(caminho)} 0 {n} \r\n")
        ents, p = [], off + 16
        for _ in range(n):
            eo, _r, es, _no = struct.unpack_from("<IIII", res, p)
            ents.append((eo, es))
            p += 16
        nomes = []
        for _ in range(n):
            ln_ = struct.unpack_from("<I", res, p)[0]
            nomes.append(res[p + 4:p + 4 + ln_].decode("cp932"))
            p += 4 + ln_
        for (eo, es), nm in zip(ents, nomes):
            t = off + eo
            out.write("\t" * nivel)
            c = f"{caminho}/{nm}"
            if res[t:t + 4] == b"GPDA":
                out.write(f"{nm} {t} ")
                walk(t, nivel + 1, c)
            else:
                out.write(f"{nm} {t} {es} {h(c)} \r\n")

    raiz = linhas[0].split()[0]
    out.write(f"{raiz} 0 ")
    walk(0, 1, raiz)
    return out.getvalue().encode("cp932")


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("cena")
    ap.add_argument("saida")
    ap.add_argument("--base", help="dir com RES.DAT/first.dat[/envpsp.dat] (padrão: extraído do JP original)")
    a = ap.parse_args()
    cena, saida = a.cena, a.saida
    base = Path(a.base) if a.base else ROOT / "build" / "extraido" / "disco1_jp"
    iso_base = ROOT / "Ore no Imouto (English v1) Disc 1" / "Ore no Imouto (English v1) Disc 1.iso" if a.base else ISO_JP
    rd = osc.ResDat.load(base / "RES.DAT")
    first = (base / "first.dat").read_bytes()
    sb, se, fb, fe, oe = rd.scene_parts(cena)
    nome_obj = f"000script{ALVO}.obj.gz"
    f000 = gpda.build_gpda([(nome_obj if x is oe else x.name, fb[x.data_offset:x.data_offset + x.data_size])
                            for x in fe])
    nova = gpda.build_gpda([(x.name, f000 if x.name.strip() == "000" else sb[x.data_offset:x.data_offset + x.data_size])
                            for x in se])
    cenas = [(e.name, nova if e.name.strip() == ALVO else rd.script_blob[e.data_offset:e.data_offset + e.data_size])
             for e in rd.scene_entries]
    script = gpda.build_gpda(cenas)
    res = gpda.build_gpda([(e.name, script if e is rd.script_entry else rd.data[e.data_offset:e.data_offset + e.data_size])
                           for e in rd.top])
    chk = osc.ResDat(res)
    assert chk.obj(ALVO) == rd.obj(cena)
    txt = seekmap_por_caminho(res, seekmap.extract_text(first), {f"/{ALVO}/": f"/{cena}/", nome_obj: f"000script{cena}.obj.gz"})
    first_novo = seekmap.rebuild_first_dat(first, txt)
    arqs = {"/PSP_GAME/INSDIR/RES.DAT": res, "/PSP_GAME/USRDIR/first.dat": first_novo}
    if a.base and (base / "envpsp.dat").exists():
        arqs["/PSP_GAME/USRDIR/envpsp.dat"] = (base / "envpsp.dat").read_bytes()
    if a.base:   # vídeos PT (construir.py os gera em build/video/), senão ficaria o PMF da ISO EN
        for v in sorted((ROOT / "build" / "video").glob("OIP_GEB0*.pmf")):
            arqs[f"/PSP_GAME/USRDIR/{v.name}"] = v.read_bytes()
    rep = iso_grow.write_files_into_iso(str(iso_base), arqs, saida)
    assert isofs.read_file(saida, "/PSP_GAME/INSDIR/RES.DAT") == res
    print(f"ISO de gravação/inspeção: {saida}  ({ALVO} <- {cena}; movidos={rep['moved']})")


if __name__ == "__main__":
    main()
