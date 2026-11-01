"""Grava uma cena (vídeo+áudio pelo dump do PPSSPP; use OREIMO_GRAVAR=1) seguindo o oráculo.

Feito para a ISO de gravação (ferramentas/iso_gravacao_jp.py): "Initial start" abre a cena
no lugar de AKYO_0000A. Conversa a Dois: --replica-em B1 B2 ... aperta □ (o ícone do balão) quando o oráculo
estiver no bloco 1400 indicado (ou na fala logo depois dele); nas outras janelas não aperta
nada (réplica perdida). Encerra quando o oráculo passar de --ate-bloco (+ --folga s).
Grava também quadros da VRAM (~3/s) com o bloco atual, como reserva/índice.

Uso: --iso ISO --replica-em 33 --ate-bloco 157 [--folga 10]
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
from ppsspp_api import PPSSPP, rgba_to_png, FB_SIZE, VRAM  # noqa: E402
from inicializacao import iniciar_novo_jogo  # noqa: E402
import isofs  # noqa: E402
import oreimo_script as osc  # noqa: E402

ORACULO = 0x08B0D1E8


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--porta", type=int, required=True)
    ap.add_argument("--saida", required=True)
    ap.add_argument("--iso", required=True)
    ap.add_argument("--replica-em", type=int, nargs="*", default=[])
    ap.add_argument("--ate-bloco", type=int, required=True)
    ap.add_argument("--folga", type=float, default=10)
    ap.add_argument("--parado", type=float, default=0, help="encerra se o bloco não mudar por S segundos (0 = nunca)")
    ap.add_argument("--escrever", default="", help="ENDEREÇO=HEX[,…] escritos na RAM logo depois de carregar")
    a = ap.parse_args()
    out = Path(a.saida)
    (out / "quadros").mkdir(parents=True, exist_ok=True)
    rd = osc.ResDat(isofs.read_file(a.iso, "/PSP_GAME/INSDIR/RES.DAT"))
    tb = list(osc.parse_obj(rd.obj("AKYO_0000A")).text_blocks((100,)))
    textos = {i: b.text for i, b in tb}
    p = PPSSPP(a.porta)
    log = []
    t0 = time.time()
    rep = {"iso": a.iso, "inicio_wall": t0}
    res = iniciar_novo_jogo(p, out, log, tb[0][1].text, so_ate_carregar=True)
    rep["inicializacao"] = res
    print("inicialização:", res, flush=True)
    if a.escrever:
        p.pause()
        try:
            for par in a.escrever.split(","):
                end, val = par.split("=")
                p.write(int(end, 16), bytes.fromhex(val))
        finally:
            p.resume()
    eventos, ultimo, apertos, fim = [], None, set(), None
    t_ini = time.time()
    k = 0

    def quadros_por(seg):
        # continua capturando durante a espera da réplica (é justamente quando o balão está na tela)
        ate = time.time() + seg
        while time.time() < ate:
            p.pause()
            try:
                pc_ = struct.unpack("<I", p.read(ORACULO, 4))[0]
                fb_ = p.read(VRAM, FB_SIZE)
            finally:
                p.resume()
            (out / "quadros" / f"{time.time() - t0:08.2f}_b{pc_:05d}.png").write_bytes(rgba_to_png(fb_))
            time.sleep(0.08)

    while time.time() - t_ini < 900:
        p.pause()
        try:
            pc = struct.unpack("<I", p.read(ORACULO, 4))[0]
            fb = p.read(VRAM, FB_SIZE) if k % 2 == 0 else None
        finally:
            p.resume()
        t = round(time.time() - t0, 2)
        if fb is not None:
            (out / "quadros" / f"{t:08.2f}_b{pc:05d}.png").write_bytes(rgba_to_png(fb))
        if pc != ultimo:
            mudou_em = time.time()
            eventos.append({"t": t, "bloco": pc, "texto": textos.get(pc)})
            print(t, pc, textos.get(pc) or "", flush=True)
            ultimo = pc
        for b in a.replica_em:
            if b not in apertos and pc in (b, b + 1):
                # o balão (com o ícone □) surge ~1,2 s depois da fala começar; janela de 3 s
                apertos.add(b)
                for tentativa in range(2):
                    quadros_por(1.6 if tentativa == 0 else 0.4)
                    p.press("square", 4)
                    eventos.append({"t": round(time.time() - t0, 2), "acao": f"□ réplica na janela do bloco {b}"})
                    print("□ réplica", b, flush=True)
                    quadros_por(0.5)
                    p.pause()
                    try:
                        novo = struct.unpack("<I", p.read(ORACULO, 4))[0]
                    finally:
                        p.resume()
                    if novo not in (b, b + 1):
                        break
        if fim is None and a.ate_bloco <= pc < 100000:
            fim = time.time()
        if fim and time.time() - fim > a.folga:
            break
        if a.parado and ultimo is not None and time.time() - mudou_em > a.parado:
            eventos.append({"t": t, "acao": f"bloco {pc} parado por {a.parado:.0f} s — fim da gravação"})
            break
        k += 1
        time.sleep(0.15)
    rep["eventos"] = eventos
    rep["log_inicializacao"] = log
    rep["fim_wall"] = time.time()
    (out / "relatorio.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1))
    print("fim", flush=True)


if __name__ == "__main__":
    main()
