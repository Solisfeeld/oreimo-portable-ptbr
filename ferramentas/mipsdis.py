#!/usr/bin/env python3
"""Desmontador MIPS (Allegrex/PSP) mínimo — só para investigar o EBOOT decifrado.

Uso:
  python3 ferramentas/mipsdis.py ELF VADDR [N]        # desmonta N instruções a partir de VADDR
  python3 ferramentas/mipsdis.py ELF --chamadores ALVO # lista os jal ALVO
Endereços = vaddr do segmento de código do PRX (offset no arquivo = vaddr + 0xC0).
"""
import struct
import sys

R = ["zero", "at", "v0", "v1", "a0", "a1", "a2", "a3", "t0", "t1", "t2", "t3", "t4", "t5", "t6", "t7",
     "s0", "s1", "s2", "s3", "s4", "s5", "s6", "s7", "t8", "t9", "k0", "k1", "gp", "sp", "fp", "ra"]
TEXT_OFF = 0xC0


def s16(x):
    return x - 0x10000 if x & 0x8000 else x


def dis(w, pc):
    op = w >> 26
    rs, rt, rd = (w >> 21) & 31, (w >> 16) & 31, (w >> 11) & 31
    sa, fn, imm = (w >> 6) & 31, w & 63, w & 0xFFFF
    if w == 0:
        return "nop"
    if op == 0:
        t = {0x21: "addu", 0x23: "subu", 0x24: "and", 0x25: "or", 0x26: "xor", 0x27: "nor",
             0x2A: "slt", 0x2B: "sltu", 0x0A: "movz", 0x0B: "movn", 0x2C: "max", 0x2D: "min",
             0x04: "sllv", 0x06: "srlv", 0x07: "srav"}
        if fn in t:
            return f"{t[fn]} {R[rd]},{R[rs]},{R[rt]}"
        if fn in (0, 2, 3):
            return f"{['sll', '', 'srl', 'sra'][fn]} {R[rd]},{R[rt]},{sa}"
        if fn == 8:
            return f"jr {R[rs]}"
        if fn == 9:
            return f"jalr {R[rd]},{R[rs]}"
        if fn in (0x18, 0x19, 0x1A, 0x1B):
            return f"{['mult', 'multu', 'div', 'divu'][fn - 0x18]} {R[rs]},{R[rt]}"
        if fn in (0x10, 0x12):
            return f"{'mfhi' if fn == 0x10 else 'mflo'} {R[rd]}"
        return f".word 0x{w:08x}"
    if op == 2 or op == 3:
        tgt = (pc & 0xF0000000) | ((w & 0x03FFFFFF) << 2)
        return f"{'j' if op == 2 else 'jal'} 0x{tgt:x}"
    if op == 1:
        name = {0: "bltz", 1: "bgez", 0x10: "bltzal", 0x11: "bgezal", 2: "bltzl", 3: "bgezl"}.get(rt, "regimm?")
        return f"{name} {R[rs]},0x{pc + 4 + (s16(imm) << 2):x}"
    if op in (4, 5, 0x14, 0x15):
        name = {4: "beq", 5: "bne", 0x14: "beql", 0x15: "bnel"}[op]
        return f"{name} {R[rs]},{R[rt]},0x{pc + 4 + (s16(imm) << 2):x}"
    if op in (6, 7, 0x16, 0x17):
        name = {6: "blez", 7: "bgtz", 0x16: "blezl", 0x17: "bgtzl"}[op]
        return f"{name} {R[rs]},0x{pc + 4 + (s16(imm) << 2):x}"
    if op in (8, 9, 0x0A, 0x0B):
        name = {8: "addi", 9: "addiu", 0x0A: "slti", 0x0B: "sltiu"}[op]
        return f"{name} {R[rt]},{R[rs]},{s16(imm)}"
    if op in (0x0C, 0x0D, 0x0E):
        return f"{['andi', 'ori', 'xori'][op - 0x0C]} {R[rt]},{R[rs]},0x{imm:x}"
    if op == 0x0F:
        return f"lui {R[rt]},0x{imm:x}"
    mem = {0x20: "lb", 0x21: "lh", 0x23: "lw", 0x24: "lbu", 0x25: "lhu", 0x28: "sb", 0x29: "sh", 0x2B: "sw",
           0x31: "lwc1", 0x39: "swc1"}
    if op in mem:
        reg = f"$f{rt}" if op in (0x31, 0x39) else R[rt]
        return f"{mem[op]} {reg},{s16(imm)}({R[rs]})"
    if op == 0x11:  # COP1
        fmt, ft, fs, fd = rs, rt, rd, sa
        if fmt == 0:
            return f"mfc1 {R[rt]},$f{fs}"
        if fmt == 4:
            return f"mtc1 {R[rt]},$f{fs}"
        if fmt == 8:
            return f"bc1{'t' if rt & 1 else 'f'} 0x{pc + 4 + (s16(imm) << 2):x}"
        if fmt == 0x10:
            t = {0: "add.s", 1: "sub.s", 2: "mul.s", 3: "div.s", 4: "sqrt.s", 5: "abs.s", 6: "mov.s", 7: "neg.s",
                 0x24: "cvt.w.s", 0x0D: "trunc.w.s", 0x0C: "round.w.s"}
            if fn in t:
                return f"{t[fn]} $f{fd},$f{fs},$f{ft}"
            if fn >= 0x30:
                return f"c.{fn & 15}.s $f{fs},$f{ft}"
        if fmt == 0x14 and fn == 0x20:
            return f"cvt.s.w $f{fd},$f{fs}"
        return f"cop1 0x{w:08x}"
    if op == 0x1F:  # SPECIAL3 (Allegrex)
        if fn == 0:
            return f"ext {R[rt]},{R[rs]},{sa},{rd + 1}"
        if fn == 4:
            return f"ins {R[rt]},{R[rs]},{sa},{rd - sa + 1}"
        if fn == 0x20:
            return {0x10: f"seb {R[rd]},{R[rt]}", 0x18: f"seh {R[rd]},{R[rt]}"}.get(sa, f".word 0x{w:08x}")
    return f".word 0x{w:08x}"


def carregar(path):
    return open(path, "rb").read()


def word(d, vaddr):
    return struct.unpack_from("<I", d, vaddr + TEXT_OFF)[0]


def listar(d, vaddr, n):
    for k in range(n):
        a = vaddr + 4 * k
        w = word(d, a)
        print(f"{a:06x}: {w:08x}  {dis(w, a)}")


def chamadores(d, alvo, fim=0x281358):
    out = []
    for a in range(0, fim, 4):
        w = word(d, a)
        if w >> 26 == 3 and ((w & 0x03FFFFFF) << 2) == alvo:
            out.append(a)
    return out


if __name__ == "__main__":
    d = carregar(sys.argv[1])
    if sys.argv[2] == "--chamadores":
        for a in chamadores(d, int(sys.argv[3], 16)):
            print(f"{a:06x}")
    else:
        listar(d, int(sys.argv[2], 16), int(sys.argv[3]) if len(sys.argv) > 3 else 24)
