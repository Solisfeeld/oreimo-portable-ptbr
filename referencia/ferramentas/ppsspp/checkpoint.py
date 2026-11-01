"""Checkpoints de teste com o SAVE DO PRÓPRIO JOGO, no memory stick isolado do projeto.

Fluxo (mapeado em testes/visuais/save1, FORMATOS.md §10):
  salvar:   START (menu de sistema) → ○ Save → ↓×(slot-1) → ○ → "Will you save?"
            (o cursor começa em No) → ← → ○ → espera gravar → × × (volta ao jogo)
  carregar: título → → (つづきから / Continue) → ○ → ↓×(slot-1) → ○ → ← → ○

Cada checkpoint é uma cópia da pasta SAVEDATA/NPJH50568 em
build/checkpoints/<nome>/ + checkpoint.json (cena, bloco do oráculo, ISO, data,
captura). Para continuar de um checkpoint, `restaurar()` copia a pasta de volta
para o SAVEDATA isolado e `carregar()` faz o Load pelo título.

Compatibilidade: um save do jogo guarda a posição no script. Se o script da cena
mudar (nova tradução com mais/menos caixas), o ponto pode não bater → o roteiro
confere o oráculo depois do Load e marca INCONCLUSIVO/INCOMPATIVEL se divergir.
Nunca apaga checkpoints; sobrescrever exige nome igual (decisão do roteiro).
"""
import json
import os
import shutil
import struct
import time
from pathlib import Path

ORACULO = 0x08B0D1E8
GAME_ID = "NPJH50568"


def savedata_dir() -> Path:
    return Path(os.environ["XDG_CONFIG_HOME"]) / "ppsspp" / "PSP" / "SAVEDATA" / GAME_ID


def checkpoints_dir() -> Path:
    # build/ppsspp/config -> build/checkpoints
    return Path(os.environ["XDG_CONFIG_HOME"]).parents[1] / "checkpoints"


def _sig():
    d = savedata_dir()
    return {f.name: (f.stat().st_size, f.stat().st_mtime_ns) for f in d.glob("*")} if d.exists() else {}


def oraculo(p):
    p.pause()
    try:
        return struct.unpack("<I", p.read(ORACULO, 4))[0]
    finally:
        p.resume()


def salvar(p, slot=1, shot=None, log=None):
    """Salva no slot (1–5). -> True se algum arquivo do SAVEDATA mudou."""
    antes = _sig()
    seq = [("start", 3.0), ("circle", 3.0)] + [("down", 0.8)] * (slot - 1) + \
          [("circle", 2.5), ("left", 1.0), ("circle", 10.0)]
    for i, (b, w) in enumerate(seq):
        p.press(b, 6)
        time.sleep(w)
        if shot:
            shot(f"cp_salvar_{i:02d}_{b}", 0)
    mudou = _sig() != antes
    if not mudou:            # talvez um diálogo "concluído" peça ○
        p.press("circle", 6)
        time.sleep(5)
        mudou = _sig() != antes
    for b in ("cross", "cross"):
        p.press(b, 6)
        time.sleep(2.5)
    if shot:
        shot("cp_salvar_fim", 0)
    if log is not None:
        log.append(("checkpoint_salvo", slot, mudou))
    return mudou


def registrar(nome, cena, bloco, iso, extra=None):
    """Copia o SAVEDATA atual para build/checkpoints/<nome>/ com metadados."""
    dst = checkpoints_dir() / nome
    if dst.exists():
        shutil.rmtree(dst / GAME_ID, ignore_errors=True)
    dst.mkdir(parents=True, exist_ok=True)
    shutil.copytree(savedata_dir(), dst / GAME_ID)
    meta = {"nome": nome, "cena": cena, "bloco": bloco, "iso": os.path.basename(iso),
            "data": time.strftime("%Y-%m-%d %H:%M:%S"), **(extra or {})}
    (dst / "checkpoint.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    return meta


def restaurar(nome):
    """Copia o checkpoint de volta para o SAVEDATA isolado. -> metadados."""
    src = checkpoints_dir() / nome
    meta = json.loads((src / "checkpoint.json").read_text())
    d = savedata_dir()
    d.mkdir(parents=True, exist_ok=True)
    for f in (src / GAME_ID).glob("*"):
        shutil.copy2(f, d / f.name)
    return meta


def carregar(p, slot=1, shot=None, log=None):
    """Na tela de título: Continue → slot → Yes. -> índice do oráculo depois do Load."""
    seq = [("right", 1.2), ("circle", 3.5)] + [("down", 0.8)] * (slot - 1) + \
          [("circle", 2.5), ("left", 1.0), ("circle", 12.0)]
    for i, (b, w) in enumerate(seq):
        p.press(b, 6)
        time.sleep(w)
        if shot:
            shot(f"cp_carregar_{i:02d}_{b}", 0)
    v = oraculo(p)
    if log is not None:
        log.append(("checkpoint_carregado", slot, v))
    return v
