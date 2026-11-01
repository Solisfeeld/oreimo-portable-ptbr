"""Percorre uma cena (ISO de inspeção/gravação: "Initial start" abre a cena) caixa a caixa com tempo fixo por caixa,
para gravar áudio (OREIMO_GRAVAR=1) e comparar vozes/música/sincronia JP × PT. Em --rapido-em B1 B2 … aperta ○
depois de --rapido s (ex.: avançar para a caixa de continuação com a voz ainda tocando). Registra o instante (relógio do
roteiro) de cada troca de bloco e de cada ○ em relatorio.json.

Uso (via rodar_ppsspp.sh, com OREIMO_GRAVAR=1): --iso ISO --ate-bloco N [--espera 6] [--rapido-em 139] [--rapido 1.0]
"""
import argparse
import json
import struct
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE.parents[2]))
from ppsspp_api import PPSSPP  # noqa: E402
from inicializacao import iniciar_novo_jogo  # noqa: E402
import isofs  # noqa: E402
import oreimo_script as osc  # noqa: E402

ORACULO = 0x08B0D1E8


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--porta", type=int, required=True)
    ap.add_argument("--saida", required=True)
    ap.add_argument("--iso", required=True)
    ap.add_argument("--ate-bloco", type=int, required=True)
    ap.add_argument("--espera", type=float, default=6.0)
    ap.add_argument("--rapido-em", type=int, nargs="*", default=[])
    ap.add_argument("--rapido", type=float, default=1.0)
    ap.add_argument("--max", type=float, default=900)
    ap.add_argument("--lento-em", type=int, nargs="*", default=[], help="blocos em que espera --lento s (voz até o fim)")
    ap.add_argument("--lento", type=float, default=14.0)
    ap.add_argument("--botao-inicial", default="", help="botão apertado uma vez no início (ex.: liga o modo auto)")
    ap.add_argument("--sem-avancar", action="store_true", help="não aperta ○ (o jogo avança sozinho, modo auto)")
    a = ap.parse_args()
    out = Path(a.saida)
    out.mkdir(parents=True, exist_ok=True)
    rd = osc.ResDat(isofs.read_file(a.iso, "/PSP_GAME/INSDIR/RES.DAT"))
    tb = list(osc.parse_obj(rd.obj("AKYO_0000A")).text_blocks((100,)))
    p = PPSSPP(a.porta)
    rep = {"iso": a.iso, "inicializacao": iniciar_novo_jogo(p, out, [], tb[0][1].text, so_ate_carregar=True)}
    if a.botao_inicial:
        time.sleep(2)
        p.press(a.botao_inicial, 6)
    t0 = time.time()
    ev, ultimo, desde = [], None, time.time()
    while time.time() - t0 < a.max:
        p.pause()
        try:
            pc = struct.unpack("<I", p.read(ORACULO, 4))[0]
        finally:
            p.resume()
        agora = time.time()
        if pc != ultimo:
            ev.append({"t": round(agora - t0, 2), "bloco": pc})
            ultimo, desde = pc, agora
        if a.ate_bloco <= pc < 100000:
            break
        limite = a.rapido if pc in a.rapido_em else (a.lento if pc in a.lento_em else a.espera)
        if not a.sem_avancar and agora - desde > limite:
            p.press("circle", 4)
            ev.append({"t": round(time.time() - t0, 2), "acao": "○", "bloco": pc})
            desde = time.time() + 0.5            # não reapertar antes de o bloco trocar
        time.sleep(0.05)
    rep["eventos"] = ev
    (out / "relatorio.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1))
    print("fim", len(ev))


if __name__ == "__main__":
    main()
