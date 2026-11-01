"""Captura das telas de interface (strings do envpsp.dat) para revisão visual de largura/texto.

Carrega um checkpoint (ou partida nova) e captura: menu de sistema (START) com cada item
selecionado, tela de Opções (rolando), lista de saves, Histórico (△) e Lista O.R.E. (L).

Uso (via rodar_ppsspp.sh): --iso ISO [--checkpoint NOME | --novo-jogo]
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
from inicializacao import iniciar_novo_jogo, chegar_ao_titulo  # noqa: E402
import checkpoint as cp  # noqa: E402
import isofs  # noqa: E402
import oreimo_script as osc  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--porta", type=int, required=True)
    ap.add_argument("--saida", required=True)
    ap.add_argument("--iso", required=True)
    ap.add_argument("--checkpoint")
    ap.add_argument("--novo-jogo", action="store_true")
    a = ap.parse_args()
    out = Path(a.saida)
    out.mkdir(parents=True, exist_ok=True)
    p = PPSSPP(a.porta)
    log, rep = [], {"iso": a.iso}

    def shot(name, wait=1.5):
        time.sleep(wait)
        p.pause()
        try:
            fb = p.read(VRAM, FB_SIZE)
        finally:
            p.resume()
        (out / f"{name}.png").write_bytes(rgba_to_png(fb))

    def btn(b, wait=1.0):
        p.press(b, 6)
        time.sleep(wait)

    if a.checkpoint:
        rep["checkpoint"] = cp.restaurar(a.checkpoint)
        rep["titulo"] = chegar_ao_titulo(p, out, log)
        shot("00_titulo", 0)
        if rep["titulo"] != "OK":
            rep["resultado"] = "INCONCLUSIVO"
            (out / "relatorio.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1))
            return
        rep["bloco_apos_load"] = cp.carregar(p, rep["checkpoint"].get("slot", 1), log=log)
    else:
        rd = osc.ResDat(isofs.read_file(a.iso, "/PSP_GAME/INSDIR/RES.DAT"))
        first = osc.parse_obj(rd.obj("AKYO_0000A")).text_blocks((100,))[0][1].text
        rep["inicializacao"] = iniciar_novo_jogo(p, out, log, first)
    time.sleep(4)
    shot("01_dialogo", 0)
    # menu de sistema: cada item (descrição muda conforme o cursor)
    btn("start", 3)
    shot("10_sistema_save", 0)
    for i, nome in enumerate(["load", "qsave", "qload", "opcoes", "titulo"], 1):
        btn("down", 1.2)
        shot(f"1{i}_sistema_{nome}", 0)
    # Opções: volta 1 (de "título" para "opções") e entra
    btn("up", 1.2)
    btn("circle", 3)
    shot("20_opcoes", 0)
    for k in range(1, 12):
        btn("down", 0.8)
        if k % 4 == 0:
            shot(f"2{k // 4}_opcoes_rolagem", 0)
    btn("cross", 2.5)
    shot("28_opcoes_saida", 0)      # pode pedir "Salvar as alterações?"
    btn("right", 1)
    btn("circle", 2.5)              # escolhe "Não" se houver pergunta
    shot("29_apos_opcoes", 0)
    btn("cross", 2.5)
    btn("cross", 2.5)
    # lista de saves
    btn("start", 3)
    btn("circle", 3)
    shot("30_lista_saves", 0)
    btn("circle", 2.5)
    shot("31_pergunta_salvar", 0)
    btn("cross", 2)
    btn("cross", 2)
    btn("cross", 3)
    # Histórico e Lista O.R.E.
    btn("triangle", 3)
    shot("40_historico", 0)
    btn("cross", 3)
    btn("ltrigger", 3)
    shot("50_lista_ore", 0)
    btn("cross", 3)
    shot("99_fim", 0)
    rep["resultado"] = "CAPTURADO (revisão visual)"
    rep["eventos"] = log
    (out / "relatorio.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1))
    print("ok")


if __name__ == "__main__":
    main()
