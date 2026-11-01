#!/usr/bin/env python3
"""Biblioteca central do projeto Oreimo PT-BR: RES.DAT -> cenas -> OBJ -> blocos.

Somente biblioteca padrão + oreimo_core (módulos vendorizados do projeto
espanhol, ver oreimo_core/ORIGEM.md). Documentação dos formatos: FORMATOS.md.

Conceitos
---------
* RES.DAT é um GPDA aninhado:  script/<CENA>/000/000script<CENA>.obj.gz
* O .obj (descompactado) = cabeçalho de 0x30 bytes + N blocos sequenciais.
  Cada bloco: u32 blockLen | u16 tipo | campos...  (blockLen múltiplo de 16)
* Blocos com texto traduzível no jogo real:
      100 (fala/narração)   u16 tipo, u8 0, u16 id_msg, u16 0xFFFF, u32 nchars, UTF-16LE
      700 (título da cena)  u16 tipo, u32 nchars, UTF-16LE, 6 bytes zero
      302 (aviso)           u16 tipo, u32 nchars, UTF-16LE, 2 bytes zero
  (104/105/103/1600/1700 só existem na cena de depuração AASTARTPOINT.)
* Alguns blocos guardam ÍNDICES DE BLOCO (posição do bloco na lista):
      702 @+6        destino de salto
      1301 @+14      início de janela (+18 = quantidade de blocos)
      1400 @+14,+18  início/fim de janela
  Inserir/remover blocos exige remapear esses campos (feito em build_obj).
"""
from __future__ import annotations

import gzip
import struct
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gpda  # noqa: E402

OBJ_HEADER_LEN = 0x30

# tipo -> (offset do campo nchars a partir do início do bloco, bytes zero após a string)
# Os bytes extras reproduzem exatamente o preenchimento do compilador original
# japonês: blockLen = round16(offset_nchars + 4 + 2*nchars + extra).
TEXT_LAYOUT = {
    100: (11, 4),
    104: (11, 4),
    700: (6, 6),
    302: (6, 2),
}
GAME_TEXT_TYPES = (100, 700, 302)
NO_MSG_ID = 0xFFFF

# Campos com índices de bloco (offset a partir do início do bloco)
INDEX_FIELDS = {
    702: (6,),
    1400: (14, 18),
}
RANGE_FIELDS = {1301: (14, 18)}  # (início, quantidade)

DEBUG_SCENES = ("AASTARTPOINT",)


def _round16(n: int) -> int:
    return (n + 15) // 16 * 16


@dataclass
class Block:
    type: int
    raw: bytes                    # bytes originais completos (inclui blockLen)
    orig_index: int | None        # índice no OBJ original (None = bloco inserido)
    text: str | None = None       # texto atual (None se o tipo não tem texto)
    orig_text: str | None = None
    msg_id: int | None = None     # só tipo 100/104

    @property
    def dirty(self) -> bool:
        return self.text != self.orig_text or self.orig_index is None


@dataclass
class Obj:
    header: bytes
    blocks: list[Block] = field(default_factory=list)

    def text_blocks(self, types=GAME_TEXT_TYPES):
        return [(i, b) for i, b in enumerate(self.blocks) if b.type in types]


def _u32(b, o):
    return struct.unpack_from("<I", b, o)[0]


def parse_obj(obj: bytes) -> Obj:
    count = _u32(obj, 0)
    hlen = _u32(obj, 4)
    if hlen != OBJ_HEADER_LEN:
        raise ValueError(f"cabeçalho OBJ inesperado: {hlen}")
    res = Obj(obj[:hlen])
    pos = hlen
    for idx in range(count):
        blen = _u32(obj, pos)
        if blen < 16 or blen % 16 or pos + blen > len(obj):
            raise ValueError(f"bloco inválido #{idx} em 0x{pos:X} (len={blen})")
        raw = obj[pos:pos + blen]
        btype = struct.unpack_from("<H", raw, 4)[0]
        blk = Block(btype, raw, idx)
        if btype in TEXT_LAYOUT:
            off, _extra = TEXT_LAYOUT[btype]
            n = _u32(raw, off)
            if off + 4 + 2 * n > blen:
                raise ValueError(f"string fora do bloco #{idx}")
            blk.text = blk.orig_text = raw[off + 4:off + 4 + 2 * n].decode("utf-16-le")
            if btype in (100, 104):
                blk.msg_id = struct.unpack_from("<H", raw, 7)[0]
        res.blocks.append(blk)
        pos += blen
    if pos != len(obj):
        raise ValueError(f"OBJ tem {len(obj) - pos} bytes sobrando")
    return res


def encode_text_block(btype: int, prefix: bytes, text: str) -> bytes:
    """prefix = bytes entre blockLen e o campo nchars (inclui o u16 tipo)."""
    off, extra = TEXT_LAYOUT[btype]
    assert len(prefix) == off - 4
    data = text.encode("utf-16-le")
    body = prefix + struct.pack("<I", len(data) // 2) + data
    total = _round16(4 + len(body) + extra)
    return struct.pack("<I", total) + body + b"\0" * (total - 4 - len(body))


def new_dialogue_block(text: str, msg_id: int = NO_MSG_ID) -> Block:
    """Bloco 100 novo (continuação), como o patch inglês faz: id 0xFFFF."""
    prefix = struct.pack("<HBHH", 100, 0, msg_id, 0xFFFF)
    raw = encode_text_block(100, prefix, text)
    return Block(100, raw, None, text, text, msg_id)


def build_obj(o: Obj) -> bytes:
    # mapa índice original -> novo índice
    remap = {}
    for new_i, b in enumerate(o.blocks):
        if b.orig_index is not None:
            remap[b.orig_index] = new_i
    n_orig = max(remap) + 1 if remap else 0
    remap[n_orig] = len(o.blocks)  # "fim"
    identity = all(k == v for k, v in remap.items())

    def m(v):
        if v in remap:
            return remap[v]
        # índice que não existe mais (bloco removido): próximo sobrevivente
        later = [k for k in remap if k > v]
        return remap[min(later)] if later else len(o.blocks)

    out = bytearray(o.header)
    for b in o.blocks:
        raw = b.raw
        if b.type in TEXT_LAYOUT and b.dirty:
            off, _ = TEXT_LAYOUT[b.type]
            raw = encode_text_block(b.type, raw[4:off], b.text)
        if not identity and (b.type in INDEX_FIELDS or b.type in RANGE_FIELDS):
            raw = bytearray(raw)
            for f in INDEX_FIELDS.get(b.type, ()):
                struct.pack_into("<I", raw, f, m(_u32(raw, f)))
            if b.type in RANGE_FIELDS:
                fs, fc = RANGE_FIELDS[b.type]
                start, cnt = _u32(raw, fs), _u32(raw, fc)
                ns = m(start)
                struct.pack_into("<I", raw, fs, ns)
                if cnt:
                    struct.pack_into("<I", raw, fc, m(start + cnt) - ns)
            raw = bytes(raw)
        out += raw
    struct.pack_into("<I", out, 0, len(o.blocks))
    return bytes(out)


# ---------------------------------------------------------------------------
# Falas: separação nome「texto」
# ---------------------------------------------------------------------------

def split_speaker(text: str):
    if text.endswith("」") and "「" in text:
        i = text.index("「")
        return text[:i], text[i + 1:-1]
    return None, text


def join_speaker(speaker, body):
    return body if speaker is None else f"{speaker}「{body}」"


# ---------------------------------------------------------------------------
# RES.DAT
# ---------------------------------------------------------------------------

def _entry_bytes(blob, e):
    return blob[e.data_offset:e.data_offset + e.data_size]


class ResDat:
    def __init__(self, data: bytes):
        self.data = data
        self.top = gpda.parse_gpda(data)
        self.script_entry = next(e for e in self.top if e.name.strip() == "script")
        self.script_blob = _entry_bytes(data, self.script_entry)
        self.scene_entries = gpda.parse_gpda(self.script_blob)

    @classmethod
    def load(cls, path):
        return cls(Path(path).read_bytes())

    def scene_names(self):
        return [e.name.strip() for e in self.scene_entries]

    def _scene(self, name):
        for e in self.scene_entries:
            if e.name.strip() == name:
                return e
        raise KeyError(name)

    def scene_parts(self, name):
        """-> (scene_blob, entradas da cena, blob '000', entradas '000', entrada obj.gz)"""
        sb = _entry_bytes(self.script_blob, self._scene(name))
        se = gpda.parse_gpda(sb)
        f0 = next(x for x in se if x.name.strip() == "000")
        fb = _entry_bytes(sb, f0)
        fe = gpda.parse_gpda(fb)
        objs = [x for x in fe if x.name.strip().lower().endswith(".obj.gz")]
        if len(objs) != 1:
            raise ValueError(f"{name}: {len(objs)} obj.gz")
        return sb, se, fb, fe, objs[0]

    def obj_gz(self, name) -> bytes:
        _sb, _se, fb, _fe, oe = self.scene_parts(name)
        return _entry_bytes(fb, oe)

    def obj(self, name) -> bytes:
        return gzip.decompress(self.obj_gz(name))

    def objs(self):
        for n in self.scene_names():
            yield n, self.obj(n)

    def rebuild(self, new_objs: dict[str, bytes] | None = None,
                new_obj_gz: dict[str, bytes] | None = None) -> bytes:
        """Reconstrói RES.DAT trocando o .obj.gz das cenas indicadas.
        Cenas não indicadas são copiadas byte a byte. Retorna os bytes novos."""
        new_obj_gz = dict(new_obj_gz or {})
        for n, ob in (new_objs or {}).items():
            new_obj_gz[n] = gzip.compress(ob, compresslevel=9, mtime=0)
        names = set(self.scene_names())
        unknown = set(new_obj_gz) - names
        if unknown:
            raise KeyError(f"cenas inexistentes: {sorted(unknown)}")
        scene_list = []
        for e in self.scene_entries:
            nm = e.name.strip()
            sb = _entry_bytes(self.script_blob, e)
            if nm in new_obj_gz:
                _sb, se, fb, fe, oe = self.scene_parts(nm)
                f000 = gpda.build_gpda([
                    (x.name, new_obj_gz[nm] if x is oe else _entry_bytes(fb, x)) for x in fe])
                sb = gpda.build_gpda([
                    (x.name, f000 if x.name.strip() == "000" else _entry_bytes(sb, x)) for x in se])
            scene_list.append((e.name, sb))
        new_script = gpda.build_gpda(scene_list)
        return gpda.build_gpda([
            (e.name, new_script if e is self.script_entry else _entry_bytes(self.data, e))
            for e in self.top])


def rebuild_gpda_identity(blob: bytes, depth: int = 0, max_depth: int = 3) -> bytes:
    """Reconstrói recursivamente um GPDA sem alterações (teste de fidelidade)."""
    entries = gpda.parse_gpda(blob)
    if not entries:  # GPDA vazio (existe em alguns contêineres): mantém como está
        return blob
    items = []
    for e in entries:
        d = _entry_bytes(blob, e)
        if depth < max_depth and d[:4] == b"GPDA":
            d = rebuild_gpda_identity(d, depth + 1, max_depth)
        items.append((e.name, d))
    return gpda.build_gpda(items)
