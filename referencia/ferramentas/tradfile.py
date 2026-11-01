"""Formato dos arquivos de tradução por cena (traducao/discoN/cenas/<CENA>.txt).

    # CENA AKYO_0000A
    @29 fala id=6026 locutor=京介 alinh=id
    JP: 俺の妹の名前は……
    EN: My little sister's name is ...
    HB: O nome da minha irmã ...
    ES: El nombre de mi hermanita ...
    PT: O nome da minha irmã mais nova é Kousaka Kirino.
    NT: observação livre (opcional)
    ST: estado opcional (ex.: duvida, revisar, ok)

* Chave da unidade = índice do bloco no OBJ japonês (@N). Nunca editar.
* JP/EN/HB/ES são gerados automaticamente (referência; ES = projeto oreimo-es-main,
  feito a partir do EN — ferramentas/espanhol.py). Só PT/NT/ST são do tradutor.
* Em PT vai só o texto falado, SEM nome e SEM 「」 (o nome vem de traducao/nomes.tsv).
* Quebras: '＿' força quebra de linha; '¶' força nova caixa (bloco de continuação).
  Sem marcadores, o construtor quebra automaticamente pela largura real da fonte.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

TYPE_NAMES = {100: "fala", 700: "titulo", 302: "aviso"}
TYPE_CODES = {v: k for k, v in TYPE_NAMES.items()}
TYPE_CODES["narracao"] = 100
USER_KEYS = ("PT", "NT", "ST")


@dataclass
class Entry:
    idx: int
    type: int
    msg_id: int | None = None
    speaker_jp: str | None = None
    jp: str = ""
    en: list[str] = field(default_factory=list)
    hb: list[str] = field(default_factory=list)
    es: list[str] = field(default_factory=list)
    method: str = ""
    pt: str = ""
    nt: str = ""
    st: str = ""

    @property
    def kind(self):
        if self.type == 100 and not self.speaker_jp:
            return "narracao"
        return TYPE_NAMES.get(self.type, str(self.type))


_HDR = re.compile(r"^@(\d+)\s+(\S+)(.*)$")


def parse(path: Path) -> tuple[str, list[Entry]]:
    scene = ""
    entries: list[Entry] = []
    cur: Entry | None = None
    for ln_no, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if line.startswith("# CENA "):
            scene = line.split()[2]
            continue
        if not line.strip() or line.startswith("#"):
            continue
        m = _HDR.match(line)
        if m:
            idx, kind, rest = int(m.group(1)), m.group(2), m.group(3)
            attrs = dict(kv.split("=", 1) for kv in rest.split() if "=" in kv)
            cur = Entry(idx=idx, type=TYPE_CODES.get(kind, 100),
                        msg_id=int(attrs["id"]) if attrs.get("id", "").isdigit() else None,
                        speaker_jp=attrs.get("locutor"), method=attrs.get("alinh", ""))
            entries.append(cur)
            continue
        if cur is None or len(line) < 3 or line[2] != ":":
            raise ValueError(f"{path}:{ln_no}: linha inesperada: {line!r}")
        key, val = line[:2], line[4:] if line[3:4] == " " else line[3:]
        if key == "JP":
            cur.jp = val
        elif key == "EN":
            cur.en.append(val)
        elif key == "HB":
            cur.hb.append(val)
        elif key == "ES":
            cur.es.append(val)
        elif key == "PT":
            cur.pt = val
        elif key == "NT":
            cur.nt = (cur.nt + " " + val).strip() if cur.nt else val
        elif key == "ST":
            cur.st = val
        else:
            raise ValueError(f"{path}:{ln_no}: chave desconhecida {key!r}")
    return scene, entries


def render(scene: str, entries: list[Entry]) -> str:
    out = [f"# CENA {scene}",
           "# Edite só PT/NT/ST. PT = texto sem nome e sem 「」. '＿' quebra linha, '¶' nova caixa.",
           ""]
    for e in entries:
        attrs = []
        if e.msg_id is not None and e.msg_id != 0xFFFF:
            attrs.append(f"id={e.msg_id}")
        if e.speaker_jp:
            attrs.append(f"locutor={e.speaker_jp}")
        if e.method:
            attrs.append(f"alinh={e.method}")
        out.append(f"@{e.idx} {e.kind} " + " ".join(attrs))
        out.append(f"JP: {e.jp}")
        for t in e.en or [""]:
            out.append(f"EN: {t}")
        for t in e.hb:
            if t:
                out.append(f"HB: {t}")
        for t in e.es:
            if t:
                out.append(f"ES: {t}")
        out.append(f"PT: {e.pt}")
        if e.nt:
            out.append(f"NT: {e.nt}")
        if e.st:
            out.append(f"ST: {e.st}")
        out.append("")
    return "\n".join(out)


def merge_write(path: Path, scene: str, fresh: list[Entry]) -> dict:
    """Escreve o arquivo com referências novas, preservando PT/NT/ST existentes.
    Se o JP de uma unidade mudou, mantém a tradução mas marca ST: jp_mudou."""
    kept = {}
    if path.exists():
        _s, old = parse(path)
        kept = {e.idx: e for e in old}
    changed = 0
    for e in fresh:
        o = kept.get(e.idx)
        if o:
            e.pt, e.nt, e.st = o.pt, o.nt, o.st
            if not e.es:
                e.es = o.es
            if o.jp and o.jp != e.jp:
                e.st = "jp_mudou"
                changed += 1
    missing = set(kept) - {e.idx for e in fresh}
    if missing:
        lost = [kept[i] for i in sorted(missing) if kept[i].pt]
        if lost:
            raise ValueError(f"{path}: unidades com tradução sumiram: {[e.idx for e in lost]}")
    path.write_text(render(scene, fresh), encoding="utf-8")
    return {"jp_mudou": changed}
