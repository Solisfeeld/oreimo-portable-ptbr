"""Teste do sistema de checkpoints (save do jogo no memory stick isolado).

Partida nova → avança pelo oráculo até a caixa --ate-caixa → salva no slot → registra
build/checkpoints/<nome>/ → game.reset → título → Continue → slot → confere que o
oráculo voltou ao mesmo bloco (±1: o Load reexibe a fala salva).

Modo --so-carregar NOME: restaura o checkpoint, vai ao título e carrega (sem partida nova).

Uso (via rodar_ppsspp.sh): --iso ISO [--cena AKYO_0000A] [--ate-caixa 12] [--slot 1]
                           [--nome AKYO_0000A_b012] [--so-carregar NOME]
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
from inicializacao import iniciar_novo_jogo, chegar_ao_titulo  # noqa: E402
import checkpoint as cp  # noqa: E402
import isofs  # noqa: E402
import oreimo_script as osc  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--porta", type=int, required=True)
    ap.add_argument("--saida", required=True)
    ap.add_argument("--iso", required=True)
    ap.add_argument("--cena", default="AKYO_0000A")
    ap.add_argument("--ate-caixa", type=int, default=12)
    ap.add_argument("--slot", type=int, default=1)
    ap.add_argument("--nome")
    ap.add_argument("--so-carregar")
    a = ap.parse_args()
    out = Path(a.saida)
    out.mkdir(parents=True, exist_ok=True)
    rd = osc.ResDat(isofs.read_file(a.iso, "/PSP_GAME/INSDIR/RES.DAT"))
    tb = osc.parse_obj(rd.obj(a.cena)).text_blocks((100,))
    p = PPSSPP(a.porta)
    log, rep = [], {"iso": a.iso}

    def shot(name, wait=2.0):
        time.sleep(wait)
        p.pause()
        try:
            fb = p.read(VRAM, FB_SIZE)
        finally:
            p.resume()
        (out / f"{name}.png").write_bytes(rgba_to_png(fb))

    def fim(res):
        rep["resultado"] = res
        rep["eventos"] = log
        (out / "relatorio.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1))
        print(res, json.dumps({k: v for k, v in rep.items() if k != "eventos"}, ensure_ascii=False)[:800])

    if a.so_carregar:
        meta = cp.restaurar(a.so_carregar)
        rep["checkpoint"] = meta
        alvo = meta["bloco"]
    else:
        res = iniciar_novo_jogo(p, out, log, tb[0][1].text)
        rep["inicializacao"] = res
        if res != "OK":
            return fim("INCONCLUSIVO:" + res)
        alvo = tb[min(a.ate_caixa, len(tb) - 1)][0]
        t1 = time.time()
        while time.time() - t1 < 600 and cp.oraculo(p) < alvo:
            p.press("circle", 3)
            time.sleep(1.3)
        time.sleep(5)
        bloco = cp.oraculo(p)
        shot("10_antes_de_salvar", 0)
        rep["bloco_salvo"] = bloco
        if not cp.salvar(p, a.slot, shot, log):
            return fim("REPROVADO:save_nao_gravou")
        nome = a.nome or f"{a.cena}_b{bloco:03d}"
        import hashlib
        rep["checkpoint"] = cp.registrar(nome, a.cena, bloco, a.iso,
                                         {"slot": a.slot, "obj_md5": hashlib.md5(rd.obj(a.cena)).hexdigest()})
        alvo = bloco
        p.request("game.reset")
        time.sleep(5)
    res = chegar_ao_titulo(p, out, log)
    rep["titulo"] = res
    if res != "OK":
        return fim("INCONCLUSIVO:titulo:" + res)
    v = cp.carregar(p, a.slot, shot, log)
    time.sleep(4)
    shot("90_apos_carregar", 0)
    v = cp.oraculo(p)
    rep["bloco_apos_load"] = v
    if abs(v - alvo) <= 1 or v == alvo:
        fim("APROVADO")
    elif v > 100000:
        fim("INCONCLUSIVO:oraculo_invalido_apos_load")
    else:
        fim(f"REPROVADO:bloco_{v}_esperado_{alvo}")


if __name__ == "__main__":
    main()
