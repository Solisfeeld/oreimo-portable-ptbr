#!/usr/bin/env python3
"""Integridade dos recursos de uma ISO PT: gráficos, áudio/vozes e estrutura das cenas (encerramento do Disco 1).

  python3 testes/verificar_recursos_finais.py <iso> [--gravar-manifesto] [--manifesto ARQ]

Só lê as ISOs. Confere contra as ISOs JP e EN originais:
  G  gráficos: todo GIM abre e decodifica; mesmas dimensões e formato do JP; só mudou o que devia mudar;
  A  áudio: AWB, HCA e vídeos sem alteração; áudio dos PMF traduzidos == áudio JP, pack a pack;
  C  cenas: mesma sequência de blocos do JP (só caixas de continuação a mais), ids de voz na mesma ordem,
     saltos e janelas de réplica apontando para o bloco certo;
  M  manifesto: sha256 de tudo que difere do EN (o que foi aprovado), para provar que uma reconstrução não perdeu nada.

Não prova que a voz toca na hora certa nem o aspecto visual: isso é teste no PPSSPP ou manual.
"""
import gzip
import hashlib
import re
import struct
import sys
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ferramentas"))
import isofs  # noqa: E402
import oreimo_script as osc  # noqa: E402
import video_pmf  # noqa: E402
from oreimo_core import gpda  # noqa: E402
from oreimo_core.scene_images import _lenient_entries  # noqa: E402
from oreimo_core.vendor_gim.gim import gim2png  # noqa: E402

JP = ROOT / "Ore no Imouto (Japan) Disc 1" / "Ore no Imouto (Japan) Disc 1.iso"
EN = ROOT / "Ore no Imouto (English v1) Disc 1" / "Ore no Imouto (English v1) Disc 1.iso"
MANIFESTO = ROOT / "traducao" / "disco1" / "sistema" / "manifesto_aprovado.tsv"
RES = "/PSP_GAME/INSDIR/RES.DAT"
USR = "/PSP_GAME/USRDIR/"
# P4 no JP/EN, P8 no PT: a arte PT tem mais de 220 cores (P4 = 16) e o motor lê o formato do cabeçalho do GIM
FORMATO_DOCUMENTADO = {"/image_main/sg_hint_bad.gim", "/image_main/sg_hint_good.gim"}
JAPONES = re.compile(r"[぀-ヿ一-鿿]")


def folhas(blob, caminho="", prof=0, out=None):
    out = {} if out is None else out
    try:
        es = gpda.parse_gpda(blob) if prof < 5 and blob[:4] == b"GPDA" else []
    except Exception:
        es = []
    if not es:
        out[caminho] = blob
        return out
    for e in es:
        folhas(blob[e.data_offset:e.data_offset + e.data_size], f"{caminho}/{e.name.strip()}", prof + 1, out)
    return out


def info_gim(gim):
    """(largura, altura, formato) do 1º bloco de imagem do GIM, percorrendo a árvore de blocos."""
    if gim[:4] != b"MIG.":
        return None
    def bloco(p, fim):
        while p + 16 <= fim:
            tipo, _z, tam, prox, dados = struct.unpack_from("<HHIII", gim, p)
            if tipo == 4:
                d = p + dados
                formato, _ordem, w, h = struct.unpack_from("<HHHH", gim, d + 4)
                return w, h, formato
            if tipo in (2, 3) and dados:
                r = bloco(p + dados, p + tam)
                if r:
                    return r
            if not prox:
                return None
            p += prox
        return None
    return bloco(16, len(gim))


def desembrulhar(b):
    return gzip.decompress(b) if b[:2] == b"\x1f\x8b" else b


def gims(caminho, b):
    """Todos os GIM de uma folha, inclusive dentro de GPDA sem nomes compactado (personagens)."""
    d = desembrulhar(b)
    if d[:4] == b"MIG.":
        return [(caminho, d)]
    if d[:4] == b"GPDA":
        saida = []
        for i, (ini, tam) in enumerate(_lenient_entries(d)):
            saida += gims(f"{caminho}#{i}", d[ini:ini + tam])
        return saida
    return []


def chave(b):
    """O que não pode mudar num bloco: tudo, menos o texto e os campos de índice (estes são conferidos à parte)."""
    if b.type in osc.TEXT_LAYOUT:
        return (b.type, b.msg_id, bytes(b.raw[4:osc.TEXT_LAYOUT[b.type][0]]) if b.type not in (100, 104) else None)
    raw = bytearray(b.raw)
    for f in osc.INDEX_FIELDS.get(b.type, ()) + osc.RANGE_FIELDS.get(b.type, ()):
        struct.pack_into("<I", raw, f, 0)
    return (b.type, bytes(raw))


def conferir_cena(pt_obj, ref_obj):
    """-> (erros, nº de caixas inseridas, nº de ids de voz). A referência é o OBJ JP."""
    pt, ref = osc.parse_obj(pt_obj), osc.parse_obj(ref_obj)
    kp, kr = [chave(b) for b in pt.blocks], [chave(b) for b in ref.blocks]
    erros, mapa, j = [], {}, 0
    for i, k in enumerate(kp):
        if j < len(kr) and k == kr[j]:
            mapa[j] = i
            j += 1
        elif pt.blocks[i].type == 100 and pt.blocks[i].msg_id == osc.NO_MSG_ID:
            continue            # caixa de continuação criada pelo construtor
        else:
            erros.append(f"bloco PT {i} (tipo {pt.blocks[i].type}) sem par no JP (esperado bloco {j})")
            break
    if not erros and j != len(kr):
        erros.append(f"faltaram {len(kr) - j} blocos do JP")
    voz = lambda o: [b.msg_id for b in o.blocks if b.type in (100, 104) and b.msg_id != osc.NO_MSG_ID]
    if voz(pt) != voz(ref):
        erros.append("ids de voz diferentes do JP")

    def alvo(blocos, v):
        return chave(blocos[v]) if 0 <= v < len(blocos) else "FIM"
    if not erros:
        for jj, ii in mapa.items():
            br, bp = ref.blocks[jj], pt.blocks[ii]
            for f in osc.INDEX_FIELDS.get(br.type, ()):
                vr, vp = struct.unpack_from("<I", br.raw, f)[0], struct.unpack_from("<I", bp.raw, f)[0]
                if alvo(ref.blocks, vr) != alvo(pt.blocks, vp):
                    erros.append(f"bloco {jj} tipo {br.type}: índice aponta para outro bloco ({vr} → {vp})")
            if br.type in osc.RANGE_FIELDS:
                fs = osc.RANGE_FIELDS[br.type][0]
                vr, vp = struct.unpack_from("<I", br.raw, fs)[0], struct.unpack_from("<I", bp.raw, fs)[0]
                if alvo(ref.blocks, vr) != alvo(pt.blocks, vp):
                    erros.append(f"bloco {jj} tipo {br.type}: início de janela aponta para outro bloco ({vr} → {vp})")
    return erros, len(kp) - len(kr), len(voz(ref))


AJUSTES_POSTERIORES = {"/script/AKYO_0010A/000/000scriptAKYO_0010A.obj.gz"}   # @173: quebra de linha pedida pelo autor em 01/11/2026


def main():
    iso = sys.argv[1]
    ok, falhas = 0, []

    def check(cond, msg, detalhe=""):
        nonlocal ok
        if cond:
            ok += 1
            print("[OK ]", msg, f"— {detalhe}" if detalhe else "", flush=True)
        else:
            falhas.append(msg)
            print("[ERR]", msg, f"— {detalhe}" if detalhe else "", flush=True)

    res_pt, res_jp, res_en = (isofs.read_file(str(i), RES) for i in (iso, JP, EN))
    pt, jp, en = folhas(res_pt), folhas(res_jp), folhas(res_en)

    # ---- gráficos
    base_jp = "--base-jp" in sys.argv                  # ISO sobre a base japonesa: a referência da árvore é o JP, e a voicepack e o EBOOT mudam de propósito
    check(set(pt) == set(jp if base_jp else en), "G1 mesma árvore de arquivos internos da ISO base", f"{len(pt)} arquivos internos")
    n_gim, ruins, dif_dim, sem_jp = 0, [], [], 0
    formatos = Counter()
    for c, b in pt.items():
        ref = dict(gims(c, jp[c])) if c in jp else {}
        for nome, g in gims(c, b):
            n_gim += 1
            info = info_gim(g)
            try:
                with gim2png(g, SimpleNamespace(verbose=False)) as im:
                    tam = im.size
            except Exception as e:  # noqa: BLE001
                ruins.append(f"{nome}: {e}")
                continue
            if info is None or tam != info[:2]:
                ruins.append(f"{nome}: cabeçalho {info} × imagem {tam}")
                continue
            formatos[info[2]] += 1
            if nome not in ref:
                sem_jp += 1
                continue
            r = info_gim(ref[nome])
            if r[:2] != info[:2] or (r != info and nome not in FORMATO_DOCUMENTADO):
                dif_dim.append(f"{nome}: JP {r} × PT {info}")
    check(not ruins, "G2 todo GIM abre e decodifica", f"{n_gim} texturas; {ruins[:3] if ruins else dict(formatos)}")
    check(not dif_dim, "G3 mesmas dimensões e formato do JP", f"{n_gim - sem_jp} comparadas; {sem_jp} sem par no JP; {dif_dim[:3]}")
    mudou = {c for c in pt if pt[c] != en.get(c)}
    tipos = Counter((c.rsplit("/", 1)[-1].split(".", 1)[-1] if "." in c.rsplit("/", 1)[-1] else "(sem extensão)") for c in mudou)
    print("     diferentes do EN por tipo:", dict(tipos))
    inesperados = [c for c in mudou if not re.search(r"\.(gim|gim\.gz|obj\.gz|obj|txt|txt\.gz|dat|map|gz)$", c.rsplit("/", 1)[-1])]
    check(not inesperados, "G4 só imagens, scripts e tabelas mudaram", f"{len(mudou)} arquivos internos; {inesperados[:3]}")

    # ---- áudio e vídeo
    for nome in ("bgm", "comment", "music", "se", "voice"):
        a, j, e = (isofs.read_file(str(i), f"{USR}{nome}.awb") for i in (iso, JP, EN))
        check(a == j == e, f"A1 {nome}.awb idêntico ao JP e ao EN", f"{len(a):,} bytes")
    hca = [c for c, b in pt.items() if b[:4] == b"HCA\0"]
    check(len(hca) == 713 and all(pt[c] == jp.get(c) == en.get(c) for c in hca), "A2 HCA internos idênticos ao JP e ao EN", f"{len(hca)} arquivos")
    for nome in ("OIP_OP", "OIP_ED"):
        a, j = (isofs.read_file(str(i), f"{USR}{nome}.pmf") for i in (iso, JP))
        check(a == j, f"A3 {nome}.pmf idêntico ao JP")
    for nome in ("OIP_GEB01", "OIP_GEB02"):
        a, j = (video_pmf.ler(isofs.read_file(str(i), f"{USR}{nome}.pmf")) for i in (iso, JP))
        pa, pj = ([b for _pts, b, _d in video_pmf.audio_packs(x)] for x in (a, j))
        check(pa == pj, f"A4 {nome}: áudio idêntico ao JP, pack a pack", f"{len(pa)} packs")

    # ---- cenas
    rp, rj, re_ = osc.ResDat(res_pt), osc.ResDat(res_jp), osc.ResDat(res_en)
    nomes = rp.scene_names()
    com_erro, caixas, vozes, ingles, residuo = [], 0, 0, [], Counter()
    for nome in nomes:
        po = rp.obj(nome)
        if po == re_.obj(nome) and po != rj.obj(nome):
            ingles.append(nome)
            continue
        erros, ins, v = conferir_cena(po, rj.obj(nome))
        caixas += ins
        vozes += v
        if erros:
            com_erro.append(f"{nome}: {erros[0]}")
        for _i, b in osc.parse_obj(po).text_blocks():
            if JAPONES.search(osc.split_speaker(b.text)[1] if b.type == 100 else b.text):
                residuo[nome] += 1
    check(not com_erro, "C1 cenas: blocos, ids de voz e saltos iguais aos do JP",
          f"{len(nomes) - len(ingles)} cenas, {vozes} ids de voz, {caixas} caixas de continuação; {com_erro[:3]}")
    print("     cenas com o OBJ do EN (não traduzidas de propósito):", ingles)
    check(ingles == ["AASTARTPOINT"] or not ingles, "C2 nenhuma cena de jogo ficou com o OBJ do EN", str(ingles))
    print(f"     falas com caractere japonês no corpo: {sum(residuo.values())} em {len(residuo)} cenas {residuo.most_common(6)}")

    # ---- manifesto dos recursos aprovados
    linhas = {c: hashlib.sha256(pt[c]).hexdigest() for c in mudou}
    for nome in ("/PSP_GAME/SYSDIR/EBOOT.BIN", USR + "envpsp.dat", USR + "OIP_GEB01.pmf", USR + "OIP_GEB02.pmf"):
        linhas[nome] = hashlib.sha256(isofs.read_file(iso, nome)).hexdigest()
    if "--gravar-manifesto" in sys.argv:
        MANIFESTO.write_text("arquivo\tsha256\n" + "".join(f"{c}\t{h}\n" for c, h in sorted(linhas.items())), encoding="utf-8")
        print(f"manifesto gravado: {MANIFESTO} ({len(linhas)} arquivos)")
    if "--manifesto" in sys.argv or MANIFESTO.exists():
        arq = Path(sys.argv[sys.argv.index("--manifesto") + 1]) if "--manifesto" in sys.argv else MANIFESTO
        esperado = dict(ln.split("\t") for ln in arq.read_text(encoding="utf-8").splitlines()[1:])
        dif = [c for c in set(esperado) | set(linhas) if esperado.get(c) != linhas.get(c)]
        if base_jp:                                    # tudo o que continua aprovado tem de bater; estes vêm da base japonesa
            dif = [c for c in dif if not (c.endswith(("voicepack.gz", "EBOOT.BIN")) or "TKD0080E" in c or c in AJUSTES_POSTERIORES)]
        check(not dif, "M1 recursos aprovados idênticos ao manifesto", f"{len(esperado)} arquivos; {sorted(dif)[:3]}")
    print(f"\nRESUMO: {ok}/{ok + len(falhas)} verificações OK" + ("" if not falhas else f" — FALHAS: {falhas[:10]}"))
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
