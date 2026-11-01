"""Teste do BACKLOG (△) e da Lista O.R.E. (L), que re-desenham o texto em outra largura.

Partida nova -> avança com ○ até a fala-alvo do prólogo estar na RAM -> abre o
backlog e captura página por página (direcional ↑), depois a Lista O.R.E.
O backlog mostra dezenas de falas por vez, então uma execução cobre muitas
linhas: serve para conferir quebras no meio de palavra e glifos.

Uso (via rodar_ppsspp.sh): --iso ISO [--ate-caixa 40] [--paginas 12]
Saída: capturas backlog_NN.png / ore_NN.png + relatorio.json
"""
import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE.parents[2]))  # ferramentas/
from ppsspp_api import PPSSPP, rgba_to_png, FB_SIZE, VRAM  # noqa: E402
from inicializacao import iniciar_novo_jogo  # noqa: E402
import struct  # noqa: E402
import isofs  # noqa: E402
import oreimo_script as osc  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--porta", type=int, required=True)
    ap.add_argument("--saida", required=True)
    ap.add_argument("--iso", required=True)
    ap.add_argument("--cena", default="AKYO_0000A")
    ap.add_argument("--ate-caixa", type=int, default=40, help="ordem da caixa-alvo na cena")
    ap.add_argument("--paginas", type=int, default=12)
    ap.add_argument("--sondar-largura", action="store_true",
                    help="lê a variável de largura do Histórico (seg1+0x17B90 do EBOOT; FORMATOS §6)")
    ap.add_argument("--forcar-largura", type=int, help="EXPERIMENTO em RAM: grava este valor na variável")
    a = ap.parse_args()
    out = Path(a.saida)
    out.mkdir(parents=True, exist_ok=True)
    rd = osc.ResDat(isofs.read_file(a.iso, "/PSP_GAME/INSDIR/RES.DAT"))
    tb = list(osc.parse_obj(rd.obj(a.cena)).text_blocks((100,)))
    boxes = [b.text for _i, b in tb]
    ORACULO = 0x08B0D1E8   # índice do bloco em execução (FORMATOS.md §10)
    p = PPSSPP(a.porta)
    log, rep = [], {"iso": a.iso}

    def shot(name):
        p.pause()
        try:
            fb = p.read(VRAM, FB_SIZE)
        finally:
            p.resume()
        (out / f"{name}.png").write_bytes(rgba_to_png(fb))
        log.append((round(time.time() - t0, 1), name))
        return fb

    t0 = time.time()
    res = iniciar_novo_jogo(p, out, log, boxes[0])
    rep["inicializacao"] = res
    if res != "OK":
        rep["resultado"] = "INCONCLUSIVO"
        (out / "relatorio.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1))
        print("INICIALIZAÇÃO", res)
        return
    if a.sondar_largura or a.forcar_largura:
        p.pause()
        try:
            # hle.module.list derruba o depurador no 1.20.4: acha a base pelo prólogo de 0x5AB8C (sem relocações)
            padrao = bytes.fromhex("e0ffbd270000b0af0400b1af0800b2af0c00b3af1000b4af1400b5af1800b6af"
                                   "25a080002580400125882001259000012598e00025a8c000ff007631")
            # base do módulo principal (mysis) = 0x08804000 (dump de RAM de 19/10); confere o prólogo de 0x5AB8C
            base0 = 0x08804000
            rep["prologo_confere"] = p.read(base0 + 0x5AB8C, len(padrao)) == padrao
            base = base0 if rep["prologo_confere"] else None
            if base is not None:
                rep["base_modulo"] = hex(base)
                var = base + 0x281358 + 0x17B90
                rep["var_largura"] = hex(var)
                rep["largura_lida"] = struct.unpack("<I", p.read(var, 4))[0]
                rep["vizinhanca"] = [struct.unpack_from("<I", p.read(var - 16, 32), 4 * i)[0] for i in range(8)]
                if a.forcar_largura:
                    p.write(var, struct.pack("<I", a.forcar_largura))
                    rep["largura_forcada"] = struct.unpack("<I", p.read(var, 4))[0]
        finally:
            p.resume()
        print("largura:", rep.get("largura_lida"), rep.get("vizinhanca"), rep.get("largura_forcada"))
    # o script inteiro da cena fica na RAM, então "texto na RAM" não serve aqui:
    # avança com ○ até o oráculo chegar ao bloco-alvo
    alvo_idx = tb[min(a.ate_caixa, len(tb) - 1)][0]
    rep["alvo_bloco"] = alvo_idx
    t1, ok = time.time(), False
    while time.time() - t1 < 600:
        p.pause()
        try:
            pc = struct.unpack("<I", p.read(ORACULO, 4))[0]
        finally:
            p.resume()
        if pc >= alvo_idx and pc < 100000:
            ok = True
            break
        p.press("circle", 3)
        time.sleep(1.3)
    rep["alvo_ok"] = ok
    time.sleep(6)          # termina de desenhar a caixa atual
    shot("00_dialogo")
    def historico_aberto():
        # cabeçalho verde "Histórico" no canto superior esquerdo (x 0–100, y 2–20)
        fb = p.read(VRAM, 512 * 24 * 4)
        verdes = 0
        for y in range(4, 20, 2):
            for x in range(4, 96, 4):
                o = (y * 512 + x) * 4
                r, g, b = fb[o], fb[o + 1], fb[o + 2]
                verdes += g > 150 and g - r > 40 and g - b > 60
        return verdes > 100
    for tentativa in range(6):
        p.press("triangle", 6)
        time.sleep(2.5)
        if historico_aberto():
            break
        time.sleep(2)
    rep["historico_aberto"] = historico_aberto()
    if not rep["historico_aberto"]:
        rep["resultado"] = "INCONCLUSIVO (Histórico não abriu)"
        (out / "relatorio.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1))
        print("HISTÓRICO NÃO ABRIU")
        return
    shot("backlog_00")
    for k in range(1, a.paginas + 1):
        for _ in range(3):   # ↑ rola uma fala; 3 por página para cobrir sem pular
            p.press("up", 4)
            time.sleep(0.5)
        time.sleep(1.0)
        shot(f"backlog_{k:02d}")
    p.press("cross", 6)
    time.sleep(2.5)
    shot("90_apos_fechar_backlog")
    time.sleep(4)
    # botões com a caixa visível: procura o menu de sistema
    for b in ("start", "square", "rtrigger", "ltrigger"):
        shot(f"91_{b}_antes")
        p.press(b, 6)
        time.sleep(3.0)
        shot(f"92_{b}_aberto")
        p.press("down", 4)
        time.sleep(1.0)
        shot(f"93_{b}_baixo")
        p.press("cross", 6)
        time.sleep(3.0)
        shot(f"94_{b}_fechado")
        time.sleep(3.0)
    shot("99_fim")
    rep["resultado"] = "CAPTURADO (revisão visual necessária)"
    rep["eventos"] = log
    (out / "relatorio.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1))
    print("ok", rep["alvo_ok"])


if __name__ == "__main__":
    main()
