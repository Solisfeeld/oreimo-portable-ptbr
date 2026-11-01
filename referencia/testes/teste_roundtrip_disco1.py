#!/usr/bin/env python3
"""Teste automatizado de extração e reinserção reversível — Disco 1.

Não altera nenhum original. Usa RES.DAT/first.dat extraídos em
build/extraido/disco1_{jp,en}/ (gerados por ferramentas/isofs.py) e,
no teste T7, grava uma ISO temporária em build/iso_teste/ e a apaga no fim
(use --manter-iso para conservá-la).

Testes:
  T1  GPDA: reconstrução recursiva sem mudanças == original (RES.DAT, first.dat)
  T2  OBJ: parse -> build == original, inclusive re-codificando TODOS os textos
  T3  seekmap: regenerado a partir do RES.DAT original == original
  T4  RES.DAT reconstruído com todas as cenas re-compactadas: conteúdo idêntico
  T5  inserção de blocos de continuação: referências 702/1301/1400 corretas
      e remoção das inserções devolve o OBJ original byte a byte
  T6  RES.DAT maior (transplante JP->EN + texto longo) + seekmap coerente
  T7  gravação na ISO EN (iso_grow) + releitura e comparação de todos os arquivos
"""
import argparse
import gzip
import hashlib
import os
import struct
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ferramentas"))
import isofs  # noqa: E402
import oreimo_script as osc  # noqa: E402
from oreimo_core import gpda, iso_grow, seekmap  # noqa: E402

EXT = ROOT / "build" / "extraido"
EN_ISO = ROOT / "Ore no Imouto (English v1) Disc 1" / "Ore no Imouto (English v1) Disc 1.iso"
RES = "/PSP_GAME/INSDIR/RES.DAT"
FIRST = "/PSP_GAME/USRDIR/first.dat"

results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"[{'OK ' if ok else 'FALHA'}] {name}" + (f" — {detail}" if detail else ""), flush=True)
    return ok


def sha(b):
    return hashlib.sha256(b).hexdigest()[:16]


def t1(tag, res_bytes, first_bytes):
    check(f"T1 {tag} RES.DAT GPDA identidade",
          osc.rebuild_gpda_identity(res_bytes, max_depth=4) == res_bytes)
    check(f"T1 {tag} first.dat GPDA identidade",
          osc.rebuild_gpda_identity(first_bytes, max_depth=4) == first_bytes)


def t2(tag, rd):
    bad_struct, bad_text, n_text = [], 0, 0
    for name, ob in rd.objs():
        o = osc.parse_obj(ob)
        if osc.build_obj(o) != ob:
            bad_struct.append(name)
        for b in o.blocks:
            if b.type in osc.TEXT_LAYOUT:
                b.orig_text = None  # força re-codificação
                n_text += 1
        rebuilt = osc.build_obj(o)
        if rebuilt != ob:
            o2 = osc.parse_obj(ob)
            o3 = osc.parse_obj(rebuilt)
            bad_text += sum(1 for a, c in zip(o2.blocks, o3.blocks) if a.raw != c.raw)
            if [b.text for b in o2.blocks] != [b.text for b in o3.blocks]:
                bad_struct.append(name + "(texto)")
    check(f"T2 {tag} OBJ parse/build identidade (300 cenas)", not bad_struct, ", ".join(bad_struct[:5]))
    ok = bad_text == 0
    detail = f"{n_text} blocos de texto re-codificados; {bad_text} com preenchimento diferente do original"
    if tag == "EN" and not ok:
        detail += " (esperado: o patch inglês usou outra regra de preenchimento; texto idêntico)"
        ok = True
    check(f"T2 {tag} re-codificação de texto", ok, detail)


def t3(tag, res_bytes, first_bytes):
    old = seekmap.extract_text(first_bytes)
    new = seekmap.regenerate(res_bytes, old)
    check(f"T3 {tag} seekmap regenerado == original", new == old, f"{len(old):,} bytes")
    check(f"T3 {tag} first.dat reconstruído == original",
          seekmap.update_for(res_bytes, first_bytes) == first_bytes)


def seekmap_leaves(first_bytes):
    """[(caminho, offset, tamanho)] das folhas do seekmap, na ordem da árvore."""
    out, stack = [], []
    for line in seekmap.extract_text(first_bytes).decode("cp932", "replace").split("\r\n"):
        if not line.strip():
            continue
        depth = len(line) - len(line.lstrip("\t"))
        parts = line.strip().split()
        del stack[depth:]
        stack.append(parts[0])
        if len(parts) == 4:
            out.append(("/".join(stack), int(parts[1]), int(parts[2])))
    return out


def seekmap_consistency(old_res, old_first, new_res, new_first):
    """Cada folha do seekmap novo deve conter exatamente os mesmos bytes que a
    folha correspondente do antigo, exceto as que mudaram de propósito.
    Retorna (folhas, iguais, diferentes[lista de caminhos])."""
    a, b = seekmap_leaves(old_first), seekmap_leaves(new_first)
    if [x[0] for x in a] != [x[0] for x in b]:
        return len(b), 0, ["ÁRVORE DIFERENTE"]
    same, diff = 0, []
    for (pa, oa, sa), (pb, ob, sb) in zip(a, b):
        if ob + sb > len(new_res):
            diff.append(pb + " (fora do arquivo)")
        elif old_res[oa:oa + sa] == new_res[ob:ob + sb]:
            same += 1
        else:
            diff.append(pb)
    return len(b), same, diff


def t4(tag, rd):
    allgz = {n: gzip.compress(rd.obj(n), compresslevel=9, mtime=0) for n in rd.scene_names()}
    new = rd.rebuild(new_obj_gz=allgz)
    rd2 = osc.ResDat(new)
    same = all(rd2.obj(n) == rd.obj(n) for n in rd.scene_names())
    others = all(gpda.parse_gpda(new)[i].data_size == e.data_size
                 for i, e in enumerate(rd.top) if e is not rd.script_entry)
    check(f"T4 {tag} RES.DAT re-compactado: 300 OBJ idênticos", same,
          f"{len(rd.data):,} -> {len(new):,} bytes")
    check(f"T4 {tag} demais seções preservadas", others)


def t5(rd):
    """Inserção de continuações numa cena com 702/1301/1400 e reversão."""
    tested = 0
    for name in ("BKIR_0103T", "CKUR_0175T", "BKIR_0000A", "AKYO_0030A", "EMAN_0056T"):
        ob = rd.obj(name)
        o = osc.parse_obj(ob)
        orig_blocks = list(o.blocks)
        # insere uma continuação após cada 7ª fala
        new_list, k = [], 0
        for b in o.blocks:
            new_list.append(b)
            if b.type == 100:
                k += 1
                if k % 7 == 0:
                    new_list.append(osc.new_dialogue_block("［continuação de teste］"))
        o.blocks = new_list
        built = osc.build_obj(o)
        p = osc.parse_obj(built)
        # mapa original->novo
        pos_new = {}
        j = 0
        for i, b in enumerate(new_list):
            if b.orig_index is not None:
                pos_new[b.orig_index] = i
        pos_new[len(orig_blocks)] = len(new_list)
        ok = True
        for b_old, b_new in zip(orig_blocks, [p.blocks[pos_new[i]] for i in range(len(orig_blocks))]):
            if b_old.type in osc.INDEX_FIELDS:
                for f in osc.INDEX_FIELDS[b_old.type]:
                    v = struct.unpack_from("<I", b_old.raw, f)[0]
                    w = struct.unpack_from("<I", b_new.raw, f)[0]
                    ok &= (pos_new.get(v, w) == w)
            elif b_old.type in osc.RANGE_FIELDS:
                fs, fc = osc.RANGE_FIELDS[b_old.type]
                v = struct.unpack_from("<I", b_old.raw, fs)[0]
                w = struct.unpack_from("<I", b_new.raw, fs)[0]
                ok &= (pos_new.get(v, w) == w)
            elif b_old.type not in osc.TEXT_LAYOUT:
                ok &= (b_old.raw == b_new.raw)
        # reversão: o OBJ com inserções vira a origem; removemos os inseridos
        q = osc.parse_obj(built)
        keep = [b for b in q.blocks if not (b.type == 100 and b.text == "［continuação de teste］")]
        q.blocks = keep
        reverted = osc.build_obj(q)
        ok_rev = reverted == ob
        tested += 1
        check(f"T5 inserção+remapeamento {name}", ok, f"{len(new_list) - len(orig_blocks)} blocos inseridos")
        check(f"T5 reversão {name} == original", ok_rev)
    return tested


def make_growth(rd_en, rd_jp):
    """RES.DAT EN com: AKYO_0000A = estrutura JP; demais cenas com texto 30% mais longo."""
    new_objs = {}
    new_objs["AKYO_0000A"] = rd_jp.obj("AKYO_0000A")
    for name in rd_en.scene_names():
        if name in new_objs or name in osc.DEBUG_SCENES:
            continue
        o = osc.parse_obj(rd_en.obj(name))
        for b in o.blocks:
            if b.type == 100:
                b.text = b.text + " " + "x" * (len(b.text) // 3)
        new_objs[name] = osc.build_obj(o)
    return new_objs


def t6_t7(rd_en, rd_jp, first_en, keep_iso):
    t0 = time.time()
    new_objs = make_growth(rd_en, rd_jp)
    new_res = rd_en.rebuild(new_objs)
    new_first = seekmap.update_for(new_res, first_en)
    rd_new = osc.ResDat(new_res)
    ok = all(rd_new.obj(n) == ob for n, ob in new_objs.items())
    check("T6 RES.DAT ampliado: OBJ relidos == esperados", ok,
          f"{len(rd_en.data):,} -> {len(new_res):,} bytes (+{len(new_res) - len(rd_en.data):,}), {time.time() - t0:.0f}s")
    leaves, same, diff = seekmap_consistency(rd_en.data, first_en, new_res, new_first)
    expected = {n for n in new_objs}
    changed_scenes = {p.split("/")[2].strip() for p in diff if p.count("/") >= 2}
    only_obj = all(p.lower().endswith(".obj.gz") for p in diff)
    check("T6 seekmap novo: folhas inalteradas apontam para os mesmos bytes",
          only_obj and changed_scenes <= expected,
          f"{leaves} folhas: {same} idênticas, {len(diff)} alteradas (só .obj.gz das cenas editadas: {only_obj})")
    ok_obj = True
    for path, off, size in seekmap_leaves(new_first):
        if path.lower().endswith(".obj.gz"):
            scene = path.split("/")[2].strip()
            if scene in new_objs:
                ok_obj &= gzip.decompress(new_res[off:off + size]) == new_objs[scene]
    check("T6 seekmap novo: .obj.gz editados descompactam para o OBJ esperado", ok_obj)
    old_lines = seekmap.extract_text(first_en).decode("cp932").split("\r\n")
    new_lines = seekmap.extract_text(new_first).decode("cp932").split("\r\n")
    check("T6 seekmap mantém a mesma árvore (nº de linhas)", len(old_lines) == len(new_lines))

    if not EN_ISO.exists():
        check("T7 ISO EN disponível", False, str(EN_ISO))
        return
    out = ROOT / "build" / "iso_teste" / "roundtrip_tmp.iso"
    out.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    report = iso_grow.write_files_into_iso(str(EN_ISO), {RES: new_res, FIRST: new_first}, str(out))
    check("T7 iso_grow gravou a ISO", out.exists(),
          f"movidos={[(p, a, b) for p, a, b in report['moved']]} recuperado={report['reclaimed']} "
          f"cresceu={report['image_grew_by']} bytes, {time.time() - t0:.0f}s")
    try:
        src = {e.path: e for e in isofs.entries(str(EN_ISO)) if not e.is_dir}
        dst = {e.path: e for e in isofs.entries(str(out)) if not e.is_dir}
        check("T7 mesma lista de arquivos", set(src) == set(dst))
        mism = []
        with open(EN_ISO, "rb") as fs, open(out, "rb") as fd:
            for p, e in src.items():
                d = dst[p]
                if p == RES:
                    fd.seek(d.extent * 2048)
                    if fd.read(d.length) != new_res:
                        mism.append(p)
                    continue
                if p == FIRST:
                    fd.seek(d.extent * 2048)
                    if fd.read(d.length) != new_first:
                        mism.append(p)
                    continue
                if p.upper().endswith("DUMMY.DAT"):
                    continue  # enchimento reaproveitado (conteúdo zero)
                fs.seek(e.extent * 2048)
                fd.seek(d.extent * 2048)
                left = e.length
                if d.length != e.length:
                    mism.append(p)
                    continue
                while left:
                    n = min(left, 1 << 24)
                    if fs.read(n) != fd.read(n):
                        mism.append(p)
                        break
                    left -= n
        check("T7 todos os arquivos da ISO conferidos byte a byte", not mism, ", ".join(mism))
        # sobreposição de extents
        spans = sorted((e.extent, e.extent + e.sectors, p) for p, e in dst.items() if e.length)
        overlap = [(a[2], b[2]) for a, b in zip(spans, spans[1:]) if a[1] > b[0]]
        check("T7 nenhum arquivo sobreposto na ISO", not overlap, str(overlap))
        info = isofs.volume_info(str(out))
        check("T7 tamanho do volume == tamanho do arquivo",
              info["volume_sectors"] * 2048 == info["file_size"],
              f"{info['file_size']:,} bytes")
    finally:
        if not keep_iso:
            out.unlink(missing_ok=True)
            print(f"(ISO temporária removida: {out})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manter-iso", action="store_true")
    ap.add_argument("--sem-iso", action="store_true", help="pula T7")
    a = ap.parse_args()
    data = {}
    for tag in ("jp", "en"):
        res_b = (EXT / f"disco1_{tag}" / "RES.DAT").read_bytes()
        first_b = (EXT / f"disco1_{tag}" / "first.dat").read_bytes()
        data[tag] = (osc.ResDat(res_b), first_b)
        T = tag.upper()
        print(f"== {T}: RES.DAT {len(res_b):,} bytes sha={sha(res_b)}")
        t1(T, res_b, first_b)
        t2(T, data[tag][0])
        t3(T, res_b, first_b)
        t4(T, data[tag][0])
    print("== Inserção de blocos (estrutura JP)")
    t5(data["jp"][0])
    print("== Ampliação + ISO")
    if a.sem_iso:
        global EN_ISO
        EN_ISO = Path("/inexistente")
    t6_t7(data["en"][0], data["jp"][0], data["en"][1], a.manter_iso)
    nf = sum(1 for r in results if not r[1])
    print(f"\nRESUMO: {len(results) - nf}/{len(results)} verificações OK" + (f", {nf} FALHAS" if nf else ""))
    sys.exit(1 if nf else 0)


if __name__ == "__main__":
    main()
