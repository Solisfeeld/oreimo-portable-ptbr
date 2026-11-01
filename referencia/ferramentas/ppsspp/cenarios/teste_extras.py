"""Extras: captura as 5 opções selecionadas e abre o Álbum, guardando só quadros completos (o PSP troca 2 framebuffers).

Uso (via rodar_ppsspp.sh): --iso ISO. Saída: sel_0..4.png (opção selecionada), album_*.png.
"""
import argparse
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[1]))
from ppsspp_api import PPSSPP, rgba_to_png, FB_SIZE, VRAM  # noqa: E402
from inicializacao import chegar_ao_titulo  # noqa: E402


def preto(fb):
    return fb[(5 * 512 + 5) * 4:(5 * 512 + 5) * 4 + 3] == b"\0\0\0"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--porta", type=int, required=True)
    ap.add_argument("--saida", required=True)
    ap.add_argument("--iso", default="")
    a = ap.parse_args()
    out = Path(a.saida)
    out.mkdir(parents=True, exist_ok=True)
    p = PPSSPP(a.porta)
    log = []

    def shot(nome):
        for _ in range(8):
            time.sleep(0.4)
            p.pause()
            try:
                f0, f1 = p.read(VRAM, FB_SIZE), p.read(VRAM + FB_SIZE, FB_SIZE)
            finally:
                p.resume()
            for fb in (f0, f1):
                if not preto(fb):
                    (out / f"{nome}.png").write_bytes(rgba_to_png(fb))
                    return
        print("sem quadro completo:", nome, flush=True)

    print("título:", chegar_ao_titulo(p, out, log), flush=True)
    time.sleep(2)
    for b in ("down", "left"):
        p.press(b, 4)
        time.sleep(1.0)
    p.press("circle", 6)
    time.sleep(4)
    for i in range(5):
        shot(f"sel_{i}")
        p.press("right", 4)
        time.sleep(1.6)
    for _ in range(5):                       # volta ao Álbum
        p.press("left", 4)
        time.sleep(1.0)
    p.press("circle", 6)
    time.sleep(4)
    shot("album_0")
    for i in range(1, 4):
        p.press("right", 4)
        time.sleep(1.5)
        shot(f"album_{i}")
    print("ok", flush=True)


if __name__ == "__main__":
    main()
