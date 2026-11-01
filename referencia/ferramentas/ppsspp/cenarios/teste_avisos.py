"""Avisos da interface (sg_systex: autossalvar/pular/auto): avança com "Salvar rápido auto." no padrão (Sim), capturando os dois framebuffers.

Carrega o checkpoint → SELECT (pular) → segue a cena e a Conversa a Dois com ○.
Uso (via rodar_ppsspp.sh): --iso ISO --checkpoint NOME [--duracao 150]
"""
import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE.parents[2]))
from ppsspp_api import PPSSPP, rgba_to_png, FB_SIZE, VRAM  # noqa: E402
from inicializacao import chegar_ao_titulo  # noqa: E402
import checkpoint as cp  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--porta", type=int, required=True)
    ap.add_argument("--saida", required=True)
    ap.add_argument("--iso", required=True)
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--duracao", type=float, default=420)
    a = ap.parse_args()
    out = Path(a.saida)
    out.mkdir(parents=True, exist_ok=True)
    p = PPSSPP(a.porta)
    rep, log = {"iso": a.iso}, []
    n = [0]

    def shot(nome):
        p.pause()
        try:
            f0, f1 = p.read(VRAM, FB_SIZE), p.read(VRAM + FB_SIZE, FB_SIZE)
        finally:
            p.resume()
        n[0] += 1
        (out / f"{n[0]:03d}_{nome}_a.png").write_bytes(rgba_to_png(f0))
        (out / f"{n[0]:03d}_{nome}_b.png").write_bytes(rgba_to_png(f1))

    rep["checkpoint"] = cp.restaurar(a.checkpoint)
    rep["titulo"] = chegar_ao_titulo(p, out, log)
    rep["bloco_apos_load"] = cp.carregar(p, rep["checkpoint"].get("slot", 1), log=log)
    time.sleep(2)
    shot("antes")
    p.press("select", 6)
    for i in range(3):
        time.sleep(0.5)
        shot(f"pular{i}")
    p.press("select", 6)
    time.sleep(3)
    t0 = time.time()
    while time.time() - t0 < a.duracao:
        p.press("circle", 4)
        time.sleep(0.8)
        shot("seguindo")
    (out / "relatorio.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print("ok")


if __name__ == "__main__":
    main()
