"""Explora o menu Extras (おまけ) a partir do título: entra em cada item, captura e volta.

Layout do menu do título (3×2): Conexão | Novo jogo | Continuar / Extras | Opções | Instalar; o cursor começa
em "Novo jogo" → ↓ (Opções) → ← (Extras) → ○.
Uso: --itens 8 --passo down   (como o cursor anda dentro de Extras: down ou right)
"""
import argparse
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[1]))
from ppsspp_api import PPSSPP, rgba_to_png, FB_SIZE, VRAM  # noqa: E402
from inicializacao import chegar_ao_titulo  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--porta", type=int, required=True)
    ap.add_argument("--saida", required=True)
    ap.add_argument("--itens", type=int, default=8)
    ap.add_argument("--passo", default="right")
    a = ap.parse_args()
    out = Path(a.saida)
    out.mkdir(parents=True, exist_ok=True)
    p = PPSSPP(a.porta)
    log = []

    def shot(n):
        p.pause()
        try:
            fb = p.read(VRAM, FB_SIZE)
        finally:
            p.resume()
        (out / f"{n}.png").write_bytes(rgba_to_png(fb))

    print("título:", chegar_ao_titulo(p, out, log), flush=True)
    time.sleep(2)
    for b in ("down", "left"):
        p.press(b, 4)
        time.sleep(1.0)
    shot("00_titulo_extras_selecionado")
    p.press("circle", 6)
    time.sleep(4)
    shot("01_extras")
    for i in range(a.itens):
        p.press("circle", 6)
        time.sleep(4)
        shot(f"{10 + i:02d}_item{i}_aberto")
        for k in range(2):                       # →: próximo item da grade (Álbum) / próxima coluna
            p.press("right", 4)
            time.sleep(1.2)
            shot(f"{10 + i:02d}_item{i}_dir{k + 1}")
        for k in range(3):          # dentro do item: ↓ duas vezes e captura (listas/páginas)
            p.press("down", 4)
            time.sleep(1.2)
        shot(f"{10 + i:02d}_item{i}_baixo")
        p.press("cross", 6)
        time.sleep(3)
        shot(f"{10 + i:02d}_item{i}_voltou")
        p.press(a.passo, 4)
        time.sleep(1.2)
    print("fim", flush=True)


if __name__ == "__main__":
    main()
