#!/usr/bin/env python3
"""envpsp.dat: textos de sistema (avisos de save, mensagens de erro, opções...).

Formato (deduzido comparando JP x EN): fluxo de tokens little-endian sem tabela
de offsets — cada token é u32. Se o u32 for um comprimento plausível e os
2*n bytes seguintes forem UTF-16 "de texto", é uma string; senão é número.
A classificação é validada pelo fato de JP e EN produzirem a MESMA sequência
de números (só as strings mudam) — ver testes no fim (python3 envpsp.py --testar).

Uso:
  python3 ferramentas/envpsp.py --testar
  python3 ferramentas/envpsp.py --exportar build/extraido/disco1_jp/envpsp.dat build/extraido/disco1_en/envpsp.dat saida.tsv
"""
import argparse
import csv
import struct
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _is_text(s: str) -> bool:
    if not s:
        return False
    bad = 0
    for ch in s:
        if ch in "\n\t":
            continue
        cat = unicodedata.category(ch)
        if cat in ("Cc", "Cn", "Cs"):  # controles, não atribuídos, surrogates (Cf/Co são aceitos)
            bad += 1
    return bad == 0


def _string_at(d, pos, minlen):
    if pos + 4 > len(d):
        return False
    v = struct.unpack_from("<I", d, pos)[0]
    if not (minlen <= v < 4000) or pos + 4 + 2 * v > len(d):
        return False
    try:
        return _is_text(d[pos + 4:pos + 4 + 2 * v].decode("utf-16-le"))
    except UnicodeDecodeError:
        return False


def _readable(s: str) -> bool:
    """Critério estrito (só para ressincronizar): letras, números, pontuação, símbolos, espaço."""
    if not s or not any(ord(c) > 0x20 for c in s):
        return False
    for ch in s:
        if ch == "\n":
            continue
        if unicodedata.category(ch)[0] not in "LNPSZ" or 0xE000 <= ord(ch) <= 0xF8FF:
            return False
    return True


def tokenize(d: bytes):
    """-> (cabeçalho 4 bytes, [('n', int) | ('s', str) | ('raw', bytes)])

    Ressincronização: a seção de interface (rótulos do Backlog, opções...) perde o
    alinhamento de 4 bytes (há campos de 1–2 bytes). Quando não há string na posição
    atual mas há uma string legível começando 1–3 bytes adiante, os bytes do meio
    viram um token 'raw' e a leitura continua dali. Validado: JP e EN produzem a
    mesma estrutura fora da lista O.R.E. (FORMATOS.md §7)."""
    head = d[:4]
    pos, toks = 4, []
    while pos < len(d):
        if pos + 4 > len(d):
            toks.append(("raw", d[pos:]))
            break
        v = struct.unpack_from("<I", d, pos)[0]
        if 0 < v < 4000 and pos + 4 + 2 * v <= len(d):
            try:
                s = d[pos + 4:pos + 4 + 2 * v].decode("utf-16-le")
            except UnicodeDecodeError:
                s = None
            if s is not None and _is_text(s) and v <= 2 and _string_at(d, pos + 4, 3):
                s = None  # ambíguo: contagem pequena seguida de uma string de verdade
            if s is not None and _is_text(s):
                toks.append(("s", s))
                pos += 4 + 2 * v
                continue
        skip = 0
        for k in (1, 2, 3):
            q = pos + k
            if q + 4 > len(d):
                break
            w = struct.unpack_from("<I", d, q)[0]
            if 2 <= w < 200 and q + 4 + 2 * w <= len(d):
                try:
                    if _readable(d[q + 4:q + 4 + 2 * w].decode("utf-16-le")):
                        skip = k
                        break
                except UnicodeDecodeError:
                    pass
        if skip:
            toks.append(("raw", d[pos:pos + skip]))
            pos += skip
            continue
        toks.append(("n", v))
        pos += 4
    return head, toks


def build(head: bytes, toks) -> bytes:
    out = bytearray(head)
    for kind, v in toks:
        if kind == "n":
            out += struct.pack("<I", v)
        elif kind == "s":
            b = v.encode("utf-16-le")
            out += struct.pack("<I", len(b) // 2) + b
        else:
            out += v
    return bytes(out)


def compare(jp: bytes, en: bytes):
    hj, tj = tokenize(jp)
    he, te = tokenize(en)
    nums_j = [v for k, v in tj if k != "s"]
    nums_e = [v for k, v in te if k != "s"]
    kinds_j = [k for k, _ in tj]
    kinds_e = [k for k, _ in te]
    return {"tokens_jp": len(tj), "tokens_en": len(te),
            "strings_jp": kinds_j.count("s"), "strings_en": kinds_e.count("s"),
            "mesma_estrutura": kinds_j == kinds_e and nums_j == nums_e and hj == he,
            "roundtrip_jp": build(hj, tj) == jp, "roundtrip_en": build(he, te) == en}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--testar", action="store_true")
    ap.add_argument("--exportar", nargs=3, metavar=("JP", "EN", "TSV"))
    a = ap.parse_args()
    if a.testar:
        for disc in ("1", "2"):
            j = ROOT / "build" / "extraido" / f"disco{disc}_jp" / "envpsp.dat"
            e = ROOT / "build" / "extraido" / f"disco{disc}_en" / "envpsp.dat"
            if j.exists() and e.exists():
                print(f"disco {disc}:", compare(j.read_bytes(), e.read_bytes()))
    if a.exportar:
        jp, en, out = a.exportar
        exportar(Path(jp), Path(en), Path(out))


def align_strings(tj, te):
    """Mapa índice-de-token JP -> lista de strings EN (alinhamento pela estrutura)."""
    import difflib
    kj = [("s",) if k == "s" else (k, v) for k, v in tj]
    ke = [("s",) if k == "s" else (k, v) for k, v in te]
    sm = difflib.SequenceMatcher(None, kj, ke, autojunk=False)
    res = {}
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        js = [i for i in range(i1, i2) if tj[i][0] == "s"]
        es = [te[j][1] for j in range(j1, j2) if te[j][0] == "s"]
        if tag == "equal" or len(js) == len(es):
            for i, e in zip(js, es):
                res[i] = [e]
        elif js:
            # agrupamento diferente (o EN fundiu/dividiu descrições): tudo no 1º
            res[js[0]] = es
            for i in js[1:]:
                res[i] = []
    return res


def construir(jp: Path, en: Path, tsv: Path, fallback_en=True):
    """envpsp.dat PT: estrutura do JP; cada string recebe a tradução PT do TSV,
    ou (fallback) a string EN quando o alinhamento é 1:1, ou fica em JP.
    -> (bytes, relatório)"""
    hj, tj = tokenize(jp.read_bytes())
    _he, te = tokenize(en.read_bytes())
    amap = align_strings(tj, te)
    pt = {}
    if tsv.exists():
        with open(tsv, encoding="utf-8") as f:
            for r in csv.DictReader(f, delimiter="\t"):
                if r.get("pt"):
                    pt[int(r["token"])] = (r["jp"], r["pt"].replace("\\n", "\n"))
    rep = {"pt": 0, "en": 0, "jp": 0, "jp_divergente": [], "numeros": []}
    # números de layout sobrescritos (envpsp_numeros.tsv: token, original, novo, nota)
    nums = {}
    ntsv = tsv.with_name("envpsp_numeros.tsv")
    import os
    if os.environ.get("OREIMO_SEM_NUMEROS"):          # (SÓ TESTE) envpsp com os números originais do JP
        ntsv = tsv.with_name("__nao_existe__.tsv")
    if os.environ.get("OREIMO_NUMEROS"):              # (SÓ TESTE) outra tabela de números
        ntsv = Path(os.environ["OREIMO_NUMEROS"])
    if ntsv.exists():
        with open(ntsv, encoding="utf-8") as f:
            for r in csv.DictReader(f, delimiter="\t"):
                if r.get("token") and r.get("novo"):
                    nums[int(r["token"])] = (r["original"], r["novo"])
    out = []
    for i, (k, v) in enumerate(tj):
        if k == "n" and i in nums:
            orig, novo = nums[i]
            fv = lambda x: struct.unpack("<I", struct.pack("<f", float(x)))[0] if "." in x else int(x)
            if fv(orig) != v:
                raise ValueError(f"envpsp_numeros: token {i} vale {v}, esperado {orig}")
            v = fv(novo)
            rep["numeros"].append(i)
        if k == "s":
            if i in pt:
                if pt[i][0].replace("\\n", "\n") != v:
                    rep["jp_divergente"].append(i)
                v = pt[i][1]
                rep["pt"] += 1
            elif fallback_en and len(amap.get(i, [])) == 1:
                v = amap[i][0]
                rep["en"] += 1
            else:
                rep["jp"] += 1
        out.append((k, v))
    return build(hj, out), rep


def exportar(jp: Path, en: Path, out: Path):
    _hj, tj = tokenize(jp.read_bytes())
    _he, te = tokenize(en.read_bytes())
    amap = align_strings(tj, te)
    out.parent.mkdir(parents=True, exist_ok=True)
    old, old_occ, seen = {}, {}, {}
    if out.exists():
        with open(out, encoding="utf-8") as f:
            for r in csv.DictReader(f, delimiter="\t"):
                old[(r["token"], r["jp"])] = r
                n_ = seen[r["jp"]] = seen.get(r["jp"], 0) + 1
                old_occ[(r["jp"], n_)] = r   # migração se a numeração de tokens mudar
    seen = {}
    n = 0
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["token", "jp", "en", "pt", "nt"])
        for i, (k, v) in enumerate(tj):
            if k != "s":
                continue
            jv = v.replace("\n", "\\n")
            n_ = seen[jv] = seen.get(jv, 0) + 1
            prev = old.get((str(i), jv)) or old_occ.get((jv, n_), {})
            w.writerow([i, jv, " ⏎ ".join(e.replace("\n", "\\n") for e in amap.get(i, [])),
                        prev.get("pt", ""), prev.get("nt", "")])
            n += 1
    print(f"{n} strings -> {out} (traduções existentes preservadas)")


if __name__ == "__main__":
    sys.exit(main())
