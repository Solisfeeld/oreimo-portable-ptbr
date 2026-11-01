#!/usr/bin/env python3
"""Compara duas gravações do jogo (gravar_vozes.py) pela energia do áudio, fala a fala, alinhadas pelo bloco do script.

    python3 testes/comparar_vozes.py <dir_a> <dir_b> [--iso ISO]   # cada dir com um .wav e o relatorio.json da gravação
    (--iso: compara só os blocos de AKYO_0000A com locutor; a narração não tem voz e só acrescenta ruído)

Cada bloco presente nas duas gravações é comparado com ele mesmo nos primeiros segundos após entrar na tela, com folga
de ±1 s. Mostra voz ausente ou fora de lugar; NÃO prova que é a voz certa nem a qualidade do som: isso é conferência de ouvido.
"""
import json
import sys
import wave
from pathlib import Path

import numpy as np

PASSO = 0.05         # s por ponto do envelope
FOLGA = int(1.0 / PASSO)
SEG = 4.0            # s comparados em cada fala


def envelope(caminho):
    with wave.open(caminho, "rb") as w:
        n, canais, taxa = w.getnframes(), w.getnchannels(), w.getframerate()
        a = np.frombuffer(w.readframes(n), dtype="<i2").astype(np.float32)
    a = a.reshape(-1, canais).mean(1)
    p = int(taxa * PASSO)
    m = len(a) // p
    return np.sqrt((a[:m * p].reshape(m, p) ** 2).mean(1) + 1e-6), m * PASSO


def correlacao(x, y):
    x, y = x - x.mean(), y - y.mean()
    d = np.sqrt((x * x).sum() * (y * y).sum())
    return float((x * y).sum() / d) if d else 1.0


def blocos(rel):
    t = {}
    for e in rel["eventos"]:
        if "acao" not in e and e.get("bloco") is not None:
            t.setdefault(e["bloco"], e["t"])
    return t


def carregar(pasta):
    pasta = Path(pasta)
    wav = sorted(pasta.glob("*.wav"))[0]
    return envelope(str(wav))[0], blocos(json.loads((pasta / "relatorio.json").read_text(encoding="utf-8")))


def score(jp, pt, ti, tj):
    """Correlação do envelope no trecho que começa em ti (JP) e tj (PT), com folga de ±1 s no PT."""
    a, n = int(ti / PASSO), int(SEG / PASSO)
    if a < 0 or a + n > len(jp):
        return None
    x, melhor = jp[a:a + n], None
    for d in range(-FOLGA, FOLGA + 1, 2):
        b = int(tj / PASSO) + d
        if 0 <= b and b + n <= len(pt):
            c = correlacao(x, pt[b:b + n])
            melhor = c if melhor is None else max(melhor, c)
    return melhor


def main():
    jp, bj = carregar(sys.argv[1])
    pt, bp = carregar(sys.argv[2])
    comuns = sorted(set(bj) & set(bp))
    if "--iso" in sys.argv:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ferramentas"))
        import isofs
        import oreimo_script as osc
        iso = sys.argv[sys.argv.index("--iso") + 1]
        o = osc.parse_obj(osc.ResDat(isofs.read_file(iso, "/PSP_GAME/INSDIR/RES.DAT")).obj("AKYO_0000A"))
        comuns = [k for k in comuns if k < len(o.blocks) and o.blocks[k].type == 100
                  and osc.split_speaker(o.blocks[k].text)[0]]
    # o relógio do roteiro e o início do WAV têm uma diferença fixa e desconhecida em cada gravação
    amostra = comuns[::3]
    ds = np.arange(-20, 20, 0.5)

    def media(oj, op):
        v = [score(jp, pt, bj[k] + oj, bp[k] + op) for k in amostra]
        v = [x for x in v if x is not None]
        return np.mean(v) if v else -1
    oj = op = 0.0
    melhor = max(((media(d, 0.0), d) for d in ds), key=lambda r: r[0])
    oj = float(melhor[1])
    res = [(k, score(jp, pt, bj[k] + oj, bp[k] + op)) for k in comuns]
    res = [r for r in res if r[1] is not None]
    c = np.array([r[1] for r in res])
    print(f"blocos: JP {len(bj)}, PT {len(bp)}, comuns {len(comuns)}; deslocamento {oj:+.1f} s")
    print(f"{len(c)} falas comparadas: mediana {np.median(c):.3f}, ≥0,80 em {int((c >= .8).sum())}, "
          f"≥0,60 em {int((c >= .6).sum())}, mínimo {c.min():.3f}")
    for k, v in sorted(res, key=lambda r: r[1])[:8]:
        print(f"  bloco {k:4d}  correlação {v:.3f}")


if __name__ == "__main__":
    main()
