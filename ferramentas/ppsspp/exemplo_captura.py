"""Roteiro de exemplo para rodar_ppsspp.sh: espera o jogo abrir e salva capturas da tela em PNG.

    ferramentas/ppsspp/rodar_ppsspp.sh ISO ferramentas/ppsspp/exemplo_captura.py PASTA --quantidade 3 --intervalo 20
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ppsspp_api import PPSSPP, rgba_to_png, FB_SIZE, VRAM  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--porta", type=int, required=True)
    ap.add_argument("--saida", required=True)
    ap.add_argument("--quantidade", type=int, default=3)
    ap.add_argument("--intervalo", type=float, default=20)
    a = ap.parse_args()
    saida = Path(a.saida)
    p = PPSSPP(a.porta)
    for i in range(a.quantidade):
        time.sleep(a.intervalo)
        p.pause()
        try:
            quadro = p.read(VRAM, FB_SIZE)
        finally:
            p.resume()
        (saida / f"captura_{i:02d}.png").write_bytes(rgba_to_png(quadro))
        print("captura", i, flush=True)


if __name__ == "__main__":
    main()
