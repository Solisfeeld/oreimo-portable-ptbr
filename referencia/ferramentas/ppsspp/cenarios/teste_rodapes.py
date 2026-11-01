"""Rodapés de interface: captura a abertura do Histórico quadro a quadro e os rodapés
das demais telas (menu de sistema, lista de saves, Lista O.R.E.), para conferir margens.

Uso (via rodar_ppsspp.sh): --iso ISO --checkpoint NOME
Saída: hist_tNNN.png (abertura do Histórico, a cada ~0,25 s), *_estavel.png, rodapes.json
(caixa delimitadora dos pixels de texto claro na faixa inferior de cada captura estável).
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

W, H, STRIDE = 480, 272, 512


def extent(fb, y0=252, y1=270):
    """x mínimo/máximo de pixels quase brancos (texto/ícones do rodapé) nas linhas y0..y1."""
    xs = []
    for y in range(y0, y1):
        for x in range(W):
            o = (y * STRIDE + x) * 4
            r, g, b = fb[o], fb[o + 1], fb[o + 2]
            if r > 225 and g > 225 and b > 225:
                xs.append(x)
    return (min(xs), max(xs)) if xs else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--porta", type=int, required=True)
    ap.add_argument("--saida", required=True)
    ap.add_argument("--iso", required=True)
    ap.add_argument("--checkpoint", required=True)
    a = ap.parse_args()
    out = Path(a.saida)
    out.mkdir(parents=True, exist_ok=True)
    p = PPSSPP(a.porta)
    log, rep = [], {"iso": a.iso, "rodapes": {}}

    def grab():
        p.pause()
        try:
            return p.read(VRAM, FB_SIZE)
        finally:
            p.resume()

    def shot(name, wait=0.0):
        time.sleep(wait)
        fb = grab()
        (out / f"{name}.png").write_bytes(rgba_to_png(fb))
        return fb

    def btn(b, wait=1.0):
        p.press(b, 6)
        time.sleep(wait)

    rep["checkpoint"] = cp.restaurar(a.checkpoint)
    rep["titulo"] = chegar_ao_titulo(p, out, log)
    if rep["titulo"] != "OK":
        rep["resultado"] = "INCONCLUSIVO"
        (out / "rodapes.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1))
        return
    rep["bloco_apos_load"] = cp.carregar(p, rep["checkpoint"].get("slot", 1), log=log)
    time.sleep(4)
    # Histórico: abertura quadro a quadro
    p.press("triangle", 6)
    t0 = time.time()
    seq = []
    for k in range(20):
        fb = shot(f"hist_t{k:03d}")
        seq.append([round(time.time() - t0, 2), extent(fb)])
        time.sleep(0.2)
    rep["historico_sequencia"] = seq
    fb = shot("historico_estavel", 2.0)
    rep["rodapes"]["historico"] = extent(fb)
    # função real de cada botão do rodapé do Histórico
    btn("triangle", 2.0)
    shot("historico_apos_triangulo")
    btn("triangle", 2.0)
    shot("historico_apos_triangulo2")
    btn("up", 1.0)
    shot("historico_cursor_acima")
    btn("circle", 2.5)
    shot("historico_apos_circulo")
    btn("cross", 3)
    # menu de sistema e lista de saves
    btn("start", 3)
    fb = shot("sistema_estavel", 0.5)
    rep["rodapes"]["sistema"] = extent(fb)
    btn("circle", 3)
    fb = shot("saves_estavel", 0.5)
    rep["rodapes"]["saves"] = extent(fb)
    btn("cross", 2)
    btn("cross", 3)
    # Lista O.R.E.
    btn("ltrigger", 3)
    fb = shot("ore_estavel", 0.5)
    rep["rodapes"]["lista_ore"] = extent(fb)
    btn("cross", 3)
    rep["resultado"] = "CAPTURADO (revisão visual)"
    rep["eventos"] = log
    (out / "rodapes.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1))
    print(json.dumps(rep["rodapes"]))


if __name__ == "__main__":
    main()
