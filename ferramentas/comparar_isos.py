#!/usr/bin/env python3
"""Lista os arquivos internos que diferem entre duas ISOs do jogo (folhas do RES.DAT + EBOOT, first.dat, envpsp.dat).

    python3 ferramentas/comparar_isos.py <iso_a> <iso_b>
"""
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import isofs  # noqa: E402
import gpda  # noqa: E402


def folhas(blob, path="", d=0, out=None):
    out = {} if out is None else out
    try:
        es = gpda.parse_gpda(blob) if d < 5 and blob[:4] == b"GPDA" else []
    except Exception:
        es = []
    if not es:
        out[path] = hashlib.md5(blob).hexdigest()
        return out
    for e in es:
        folhas(blob[e.data_offset:e.data_offset + e.data_size], f"{path}/{e.name.strip()}", d + 1, out)
    return out


def main():
    a, b = sys.argv[1:3]
    fa = folhas(isofs.read_file(a, "/PSP_GAME/INSDIR/RES.DAT"))
    fb = folhas(isofs.read_file(b, "/PSP_GAME/INSDIR/RES.DAT"))
    dif = sorted(k for k in set(fa) | set(fb) if fa.get(k) != fb.get(k))
    print("folhas", len(fa), len(fb), "diferentes:", len(dif))
    for k in dif:
        print(" ", k)
    for f in ("/PSP_GAME/SYSDIR/EBOOT.BIN", "/PSP_GAME/USRDIR/first.dat", "/PSP_GAME/USRDIR/envpsp.dat", "/PSP_GAME/PARAM.SFO"):
        print(f, "igual" if isofs.read_file(a, f) == isofs.read_file(b, f) else "DIFERENTE")


if __name__ == "__main__":
    main()
