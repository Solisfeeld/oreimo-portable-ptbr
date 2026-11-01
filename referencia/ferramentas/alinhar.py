#!/usr/bin/env python3
"""Extrai e alinha os textos JP (fonte) com EN e HanabiWorks (referências).

Unidade de tradução = bloco de texto do OBJ JAPONÊS (100 fala/narração,
700 título, 302 aviso). A estrutura JP é a base do patch (ver FORMATOS.md).

Alinhamento JP -> EN, por cena:
  1. id_msg (u16 do bloco 100) compartilhado entre JP e EN — âncora forte;
  2. blocos sem id (0xFFFF): alinhamento de sequência (difflib) usando o
     locutor (nome JP convertido para o nome EN aprendido nas âncoras);
  3. blocos extras do EN (continuações id 0xFFFF que o patch inglês inseriu)
     ficam anexados ao bloco JP anterior.
HanabiWorks: mesma estrutura do EN (índice de bloco EN = 'registro' do CSV).

Saídas (nunca sobrescreve traduções existentes):
  traducao/disco1/alinhamento.csv        auditoria completa (todas as cenas)
  traducao/disco1/cenas/<CENA>.txt       arquivos de tradução (só cria se não existir;
                                         se existir, atualiza referências e preserva PT/NT)

Uso: python3 ferramentas/alinhar.py [--disco 1] [--cenas AKYO_0000A ...]
"""
import argparse
import collections
import csv
import difflib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ferramentas"))
import oreimo_script as osc  # noqa: E402
import tradfile  # noqa: E402

TEXT_TYPES = osc.GAME_TEXT_TYPES


def text_blocks(obj_bytes):
    o = osc.parse_obj(obj_bytes)
    out = []
    for i, b in o.text_blocks(TEXT_TYPES):
        spk, body = osc.split_speaker(b.text) if b.type == 100 else (None, b.text)
        out.append(dict(idx=i, type=b.type, id=b.msg_id, text=b.text, spk=spk, body=body))
    return out


def learn_names(pairs):
    """pairs: [(jp_spk, en_spk)] de blocos ancorados por id."""
    c = collections.defaultdict(collections.Counter)
    for j, e in pairs:
        if j is not None:
            c[j][e] += 1
    return {j: cnt.most_common(1)[0][0] for j, cnt in c.items()}


def align(J, E, names):
    """Retorna lista paralela a J: ([índices em E], método).

    1. id_msg: casamento em qualquer posição (o EN às vezes realoca falas
       para o fim do script e salta até elas);
    2. blocos restantes: difflib por (tipo, locutor) DENTRO do segmento
       delimitado pelas âncoras vizinhas;
    3. blocos EN que sobram (continuações inseridas pelo EN) são anexados à
       unidade JP dona do bloco EN imediatamente anterior."""
    def key_j(b):
        if b["type"] != 100:
            return ("t", b["type"])
        return ("spk", names.get(b["spk"], b["spk"]) if b["spk"] else None)

    def key_e(b):
        if b["type"] != 100:
            return ("t", b["type"])
        return ("spk", b["spk"])

    res = [None] * len(J)
    owner = {}  # índice E -> índice J
    eid = {}
    for k, b in enumerate(E):
        if b["type"] == 100 and b["id"] != osc.NO_MSG_ID:
            eid.setdefault(b["id"], k)
    for k, b in enumerate(J):
        if b["type"] == 100 and b["id"] != osc.NO_MSG_ID and b["id"] in eid and eid[b["id"]] not in owner:
            res[k] = ([eid[b["id"]]], "id")
            owner[eid[b["id"]]] = k

    k = 0
    while k < len(J):
        if res[k] is not None:
            k += 1
            continue
        a = k
        while k < len(J) and res[k] is None:
            k += 1
        b = k  # J[a:b] sem par
        lo = max(res[a - 1][0]) + 1 if a > 0 and res[a - 1][0] else 0
        if a == 0:
            lo = 0
        hi = lo
        while hi < len(E) and hi not in owner:
            hi += 1
        cand = list(range(lo, hi))
        kj = [key_j(J[i]) for i in range(a, b)]
        ke = [key_e(E[i]) for i in cand]
        sm = difflib.SequenceMatcher(None, kj, ke, autojunk=False)
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "equal":
                for t in range(i2 - i1):
                    res[a + i1 + t] = ([cand[j1 + t]], "seq")
                    owner[cand[j1 + t]] = a + i1 + t
            elif tag == "replace" and (i2 - i1) == (j2 - j1):
                for t in range(i2 - i1):
                    res[a + i1 + t] = ([cand[j1 + t]], "seq?")
                    owner[cand[j1 + t]] = a + i1 + t
        for i in range(a, b):
            if res[i] is None:
                res[i] = ([], "sem_EN")

    def spk_ok(e_idx, j_idx):
        js = J[j_idx]["spk"]
        return E[e_idx]["spk"] == (names.get(js, js) if js else None)

    unmatched = [i for i in range(len(J)) if not res[i][0]]
    last = None
    cur_target = None  # unidade JP 'sem_EN' que recebe um trecho realocado
    for e in range(len(E)):
        o = owner.get(e)
        if o is not None:
            last, cur_target = o, None
            continue
        if cur_target is not None and spk_ok(e, cur_target) and E[e]["id"] == osc.NO_MSG_ID:
            res[cur_target][0].append(e)
            continue
        cur_target = None
        tgt = next((i for i in unmatched if not res[i][0] and spk_ok(e, i)), None)
        prev_txt = E[res[last][0][-1]]["body"].rstrip() if last is not None and res[last][0] else ""
        complete = prev_txt.endswith((".", "!", "?", "…", "』", '"', ")", "～", "~"))
        if last is not None and spk_ok(e, last) and not (tgt is not None and complete):
            lst, meth = res[last]
            lst.append(e)
            if E[e]["id"] != osc.NO_MSG_ID or E[e]["type"] != 100:
                meth += "+?"
            res[last] = (lst, meth)
            continue
        # locutor não confere (ou frase anterior completa): fala realocada pelo EN
        if tgt is not None:
            res[tgt] = ([e], "realocado?")
            cur_target = tgt
        elif last is not None:
            lst, meth = res[last]
            lst.append(e)
            res[last] = (lst, meth + "+?")
    return res


def load_hanabi(path):
    hb = collections.defaultdict(dict)
    if not path.exists():
        return hb
    with open(path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if r["tipo"] in ("dialogo", "titulo", "aviso"):
                hb[r["cena"].strip()][int(r["registro"])] = r["texto_origem"]
    return hb


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--disco", default="1")
    ap.add_argument("--cenas", nargs="*")
    ap.add_argument("--sem-arquivos", action="store_true", help="só gera alinhamento.csv")
    a = ap.parse_args()
    ext = ROOT / "build" / "extraido"
    rd_jp = osc.ResDat.load(ext / f"disco{a.disco}_jp" / "RES.DAT")
    rd_en = osc.ResDat.load(ext / f"disco{a.disco}_en" / "RES.DAT")
    hb = load_hanabi(ROOT / "Hanabi_textos.csv") if a.disco == "1" else {}
    outdir = ROOT / "traducao" / f"disco{a.disco}"
    (outdir / "cenas").mkdir(parents=True, exist_ok=True)

    scenes = [n for n in rd_jp.scene_names() if n not in osc.DEBUG_SCENES]
    data = {}
    pairs = []
    for n in scenes:
        J = text_blocks(rd_jp.obj(n))
        E = text_blocks(rd_en.obj(n))
        data[n] = (J, E)
        eid = {b["id"]: b for b in E if b["type"] == 100 and b["id"] != osc.NO_MSG_ID}
        for b in J:
            if b["type"] == 100 and b["id"] in eid:
                pairs.append((b["spk"], eid[b["id"]]["spk"]))
    names = learn_names(pairs)
    (outdir / "nomes_aprendidos.tsv").write_text(
        "jp\ten\n" + "".join(f"{j}\t{e}\n" for j, e in sorted(names.items(), key=lambda x: str(x))),
        encoding="utf-8")

    stats = collections.Counter()
    rows = []
    for n in scenes:
        J, E = data[n]
        res = align(J, E, names)
        entries = []
        for b, (eidx, meth) in zip(J, res):
            en_txt = [E[k]["text"] for k in eidx]
            hb_txt = [hb.get(n, {}).get(E[k]["idx"], "") for k in eidx]
            stats[meth] += 1
            rows.append(dict(cena=n, idx=b["idx"], tipo=b["type"],
                             id_msg="" if b["id"] in (None, osc.NO_MSG_ID) else b["id"],
                             metodo=meth, blocos_en=" ".join(str(E[k]["idx"]) for k in eidx),
                             jp=b["text"], en=" ⏎ ".join(en_txt), hanabi=" ⏎ ".join(hb_txt)))
            entries.append(tradfile.Entry(idx=b["idx"], type=b["type"], msg_id=b["id"],
                                          speaker_jp=b["spk"], jp=b["body"],
                                          en=en_txt, hb=hb_txt, method=meth))
        if not a.sem_arquivos and (not a.cenas or n in a.cenas):
            tradfile.merge_write(outdir / "cenas" / f"{n}.txt", n, entries)

    with open(outdir / "alinhamento.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    total = sum(stats.values())
    print(f"Cenas: {len(scenes)}  unidades JP: {total}")
    for k, v in stats.most_common():
        print(f"  {k:8s} {v:6d}  ({v / total:.1%})")
    print(f"Nomes aprendidos: {len(names)} -> {outdir / 'nomes_aprendidos.tsv'}")


if __name__ == "__main__":
    main()
