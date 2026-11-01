#!/usr/bin/env python3
"""Vídeos PMF (PSMF) com legenda PT-BR gravada na imagem.

  python3 ferramentas/video_pmf.py audio OIP_GEB01          # áudio JP -> build/video/OIP_GEB01_jp.wav
  python3 ferramentas/video_pmf.py gerar [OIP_GEB01 ...]    # -> build/video/OIP_GEBxx.pmf (PT)
  python3 ferramentas/video_pmf.py conferir build/video/OIP_GEB01.pmf

Fonte: o PMF JAPONÊS (sem legenda). Legendas: traducao/disco1/sistema/videos.tsv (tempos medidos na
legenda do EN, que foi sincronizada com o mesmo áudio). Passos:
  1. vídeo JP + legenda (ASS) -> H.264 Main@2.1, 480x272, sem quadros B, 1 referência, AUD em cada
     quadro, IDR exatamente nos mesmos quadros que o JP (mesma estrutura de GOP -> mesmos PTS);
  2. multiplexação PSMF: packs de 2048 bytes; o áudio ATRAC3plus é copiado do JP pack a pack;
     cada GOP começa num pack com cabeçalho de sistema (0xBB) + tabela de navegação (0xBF:
     packs até o fim das 4 primeiras imagens + tamanho de cada imagem do GOP, FORMATOS §11);
     cabeçalho PSMF do JP com tamanho do fluxo e mapa EP (PTS e pack de cada GOP) recalculados.
"""
import csv
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "build" / "extraido" / "disco1_jp"
OUT = ROOT / "build" / "video"
TSV = ROOT / "traducao" / "disco1" / "sistema" / "videos.tsv"
PACK = 2048


# ------------------------------------------------------------------ leitura do PSMF
def ts_ler(b):
    return ((b[0] >> 1) & 7) << 30 | (b[1] << 22) | ((b[2] >> 1) << 15) | (b[3] << 7) | (b[4] >> 1)


def ts_gravar(v, prefixo):
    return bytes([(prefixo << 4) | (((v >> 30) & 7) << 1) | 1, (v >> 22) & 0xFF, (((v >> 15) & 0x7F) << 1) | 1,
                  (v >> 7) & 0xFF, ((v & 0x7F) << 1) | 1])


def scr_gravar(base, ext=0):
    return bytes([0x44 | (((base >> 30) & 7) << 3) | ((base >> 28) & 3), (base >> 20) & 0xFF,
                  (((base >> 15) & 0x1F) << 3) | 0x04 | ((base >> 13) & 3), (base >> 5) & 0xFF,
                  ((base & 0x1F) << 3) | 0x04 | ((ext >> 7) & 3), ((ext & 0x7F) << 1) | 1])


def ler(pmf: bytes):
    """-> dict com cabeçalho, packs (lista de [(sid, bytes do PES inteiro)]), SCR, mux_rate."""
    off = struct.unpack(">I", pmf[8:12])[0]
    packs, p = [], off
    while p < len(pmf):
        assert pmf[p:p + 4] == b"\x00\x00\x01\xba", hex(p)
        q = p + 14 + (pmf[p + 13] & 7)
        pes = []
        while q < p + PACK and pmf[q:q + 3] == b"\x00\x00\x01":
            L = struct.unpack(">H", pmf[q + 4:q + 6])[0]
            pes.append((pmf[q + 3], pmf[q:q + 6 + L]))
            q += 6 + L
        packs.append(pes)
        p += PACK
    return {"cab": pmf[:off], "packs": packs, "mux": pmf[off + 10:off + 13], "raw": pmf}


def gops_e_au(info):
    """Tamanhos de GOP (nº de imagens, da tabela 0xBF), PTS da 1ª imagem e PTS/DTS iniciais."""
    gops, sys_hdr, pts0, dts0 = [], None, None, None
    for pes in info["packs"]:
        for sid, b in pes:
            if sid == 0xBB and sys_hdr is None:
                sys_hdr = b
            if sid == 0xBF:
                gops.append(struct.unpack(">H", b[6 + 16:6 + 18])[0])
            if sid == 0xE0 and pts0 is None and b[7] & 0x80:
                pts0 = ts_ler(b[9:14])
                dts0 = ts_ler(b[14:19]) if b[7] & 0x40 else pts0
    return gops, sys_hdr, pts0, dts0


def audio_packs(info):
    """[(PTS ou None, PES 0xBD inteiro)] na ordem; + DTS do último quadro de vídeo iniciado antes."""
    out, ult_dts = [], None
    for pes in info["packs"]:
        for sid, b in pes:
            if sid == 0xE0 and b[7] & 0x40:
                ult_dts = ts_ler(b[14:19])
            if sid == 0xBD:
                pts = ts_ler(b[9:14]) if b[7] & 0x80 else None
                out.append((pts, b, ult_dts))
    return out


def extrair_audio(nome):
    info = ler((EXT / f"{nome}.pmf").read_bytes())
    pay = bytearray()
    for pes in info["packs"]:
        for sid, b in pes:
            if sid == 0xBD:
                hl = b[8]
                pay += b[9 + hl + 4:]
    params = struct.unpack(">H", pay[2:4])[0]
    fsz = ((params & 0x3FF) + 1) * 8
    frames, i = [], 0
    while i + fsz + 8 <= len(pay):
        assert pay[i:i + 2] == b"\x0f\xd0"
        frames.append(bytes(pay[i + 8:i + 8 + fsz]))
        i += fsz + 8
    oma = bytearray(96)
    oma[0:8] = b"EA3\x01\x00\x60\xff\xff"
    oma[32] = 1
    oma[34:36] = struct.pack(">H", params)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{nome}_jp.oma").write_bytes(bytes(oma) + b"".join(frames))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(OUT / f"{nome}_jp.oma"), str(OUT / f"{nome}_jp.wav")],
                   check=True)
    return OUT / f"{nome}_jp.wav"


# ------------------------------------------------------------------ legenda + codificação
def ass(nome):
    with open(TSV, encoding="utf-8") as f:
        linhas = [r for r in csv.DictReader(f, delimiter="\t") if r["video"] == nome]

    def t(s):
        s = float(s)
        return f"0:{int(s // 60):02d}:{s % 60:05.2f}"
    cab = ["[Script Info]", "ScriptType: v4.00+", "PlayResX: 480", "PlayResY: 272", "WrapStyle: 0", "",
           "[V4+ Styles]",
           "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, "
           "Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
           "Alignment, MarginL, MarginR, MarginV, Encoding",
           "Style: Leg,Noto Sans,17,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,1.6,0.8,"
           "2,20,20,14,1", "", "[Events]",
           "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    ev = [f"Dialogue: 0,{t(r['inicio'])},{t(r['fim'])},Leg,,0,0,0,,{r['pt']}" for r in linhas]
    return "\n".join(cab + ev) + "\n"


def codificar(nome, gops, tmp: Path):
    """-> bytes do fluxo H.264 (Annex B) com legenda; IDR nos mesmos quadros do JP."""
    (tmp / "leg.ass").write_text(ass(nome), encoding="utf-8")
    inicio, idx = [], 0
    for g in gops:
        inicio.append(idx)
        idx += g
    total = idx
    expr = "+".join(f"eq(n,{i})" for i in inicio)
    es = tmp / "video.264"
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", str(EXT / f"{nome}.pmf"), "-an",
           "-vf", f"ass={tmp / 'leg.ass'}", "-frames:v", str(total),
           "-c:v", "libx264", "-profile:v", "main", "-level", "2.1", "-pix_fmt", "yuv420p",
           "-preset", "slow", "-b:v", "2400k", "-maxrate", "3800k", "-bufsize", "3000k",
           "-g", "600", "-keyint_min", "1", "-sc_threshold", "0", "-bf", "0", "-refs", "1",
           "-force_key_frames", f"expr:{expr}",
           "-x264-params", "aud=1:repeat-headers=1:open-gop=0", "-f", "h264", str(es)]
    subprocess.run(cmd, check=True)
    return es.read_bytes(), total


def dividir_au(es: bytes):
    pos, i = [], es.find(b"\x00\x00\x00\x01\x09")
    while i >= 0:
        pos.append(i)
        i = es.find(b"\x00\x00\x00\x01\x09", i + 1)
    return [es[pos[k]:(pos[k + 1] if k + 1 < len(pos) else len(es))] for k in range(len(pos))]


# ------------------------------------------------------------------ multiplexação
def pes_video(dados, pts=None, dts=None):
    if pts is None:
        cab = b"\x81\x00\x00"
    else:
        cab = b"\x81\xc1\x0d" + ts_gravar(pts, 3) + ts_gravar(dts, 1) + b"\xff\xff\xff"
    corpo = cab + dados
    return b"\x00\x00\x01\xe0" + struct.pack(">H", len(corpo)) + corpo


def pes_padding(n):
    """n bytes no total (n >= 6)."""
    return b"\x00\x00\x01\xbe" + struct.pack(">H", n - 6) + b"\xff" * (n - 6)


def nav(packs_ate, tamanhos):
    v = (list(packs_ate) + [0, 0, 0, 0])[:4]
    n = len(tamanhos)
    corpo = b"\x01\xe0" + b"".join(struct.pack(">H", x) for x in v) + b"\x00\x00\x00\x00" + \
        struct.pack(">HH", 4 * n + 2, n) + b"".join(struct.pack(">I", 0x00800000 | t) for t in tamanhos)
    return b"\x00\x00\x01\xbf" + struct.pack(">H", len(corpo)) + corpo


def multiplexar(info, aus, gops, sys_hdr, pts0, dts0):
    audio = audio_packs(info)
    # avanço do áudio em relação ao vídeo no JP (mediana): PTS do áudio - DTS do último quadro antes dele
    leads = sorted(a[0] - a[2] for a in audio if a[0] is not None and a[2] is not None)
    lead = leads[len(leads) // 2] if leads else 0
    packs, gop_ini_pack, nav_info = [], [], []
    estado = {"buf": bytearray(), "ia": 0}
    passo = 3003

    def fechar():
        buf = estado["buf"]
        if not buf:
            return
        resto = PACK - 14 - len(buf)
        if resto:
            buf += pes_padding(resto)
        packs.append(bytes(buf))
        estado["buf"] = bytearray()

    def audio_ate(dts):
        while estado["ia"] < len(audio) and (audio[estado["ia"]][0] is None or audio[estado["ia"]][0] - lead <= dts):
            fechar()
            pes = audio[estado["ia"]][1]
            resto = PACK - 14 - len(pes)
            packs.append(pes + (pes_padding(resto) if resto else b""))
            estado["ia"] += 1

    k = 0
    for n in gops:
        tam = [len(a) for a in aus[k:k + n]]
        fim_imagem = []
        for j in range(n):
            au = aus[k + j]
            pts, dts = pts0 + (k + j) * passo, dts0 + (k + j) * passo
            audio_ate(dts)
            if j == 0:                      # GOP novo: pack próprio com 0xBB + 0xBF (provisória) + vídeo
                fechar()
                gop_ini_pack.append(len(packs))
                estado["buf"] = bytearray(sys_hdr) + b"\x00" * (6 + 18 + 4 * n)
            pos, primeiro = 0, True
            while pos < len(au):
                livre = PACK - 14 - len(estado["buf"])
                cab = 22 if primeiro else 9   # 6 + 3 + PTS(5) + DTS(5) + 3 de preenchimento
                if livre < cab + 1:
                    fechar()
                    continue
                n_dados = min(len(au) - pos, livre - cab)
                sobra = livre - cab - n_dados
                if 0 < sobra < 6:          # não cabe um padding: encurta este PES
                    if n_dados <= 6 - sobra:
                        fechar()
                        continue
                    n_dados -= 6 - sobra
                estado["buf"] += pes_video(au[pos:pos + n_dados], pts if primeiro else None, dts if primeiro else None)
                pos += n_dados
                primeiro = False
                if pos < len(au):
                    fechar()
            fim_imagem.append(len(packs))    # pack aberto = o que contém o último byte desta imagem
        k += n
        nav_info.append((fim_imagem, tam))
    fechar()
    audio_ate(1 << 40)
    for g, ini in enumerate(gop_ini_pack):
        fim_imagem, tam = nav_info[g]
        nv = nav([f - ini for f in fim_imagem[:4]], tam)
        p, L = packs[ini], len(sys_hdr)
        assert p[L:L + len(nv)] == b"\x00" * len(nv)
        packs[ini] = p[:L] + nv + p[L + len(nv):]
    scr0, passo_scr = 30147, 147.45     # mesmo ritmo de SCR do JP
    saida = bytearray()
    for i, conteudo in enumerate(packs):
        assert len(conteudo) == PACK - 14, (i, len(conteudo))
        saida += b"\x00\x00\x01\xba" + scr_gravar(int(scr0 + i * passo_scr)) + info["mux"] + b"\xf8" + conteudo
    return bytes(saida), gop_ini_pack


def cabecalho(info, tam_fluxo, gop_ini_pack):
    """Cabeçalho PSMF do JP com o tamanho do fluxo e o pack de cada entrada do mapa EP atualizados.
    Descritor do vídeo em 0x82: [4:8] offset do mapa EP, [8:12] nº de entradas; entrada de 10 bytes =
    índice, offset da imagem, PTS (u32), pack (u32) — como lido pelo PPSSPP (psmf.cpp)."""
    cab = bytearray(info["cab"])
    cab[0x0C:0x10] = struct.pack(">I", tam_fluxo)
    ep_off = struct.unpack(">I", cab[0x86:0x8A])[0]
    n_ep = struct.unpack(">I", cab[0x8A:0x8E])[0]
    if n_ep != len(gop_ini_pack):
        raise ValueError(f"mapa EP do JP tem {n_ep} entradas; GOPs: {len(gop_ini_pack)}")
    for i, pk in enumerate(gop_ini_pack):
        e = ep_off + 10 * i
        cab[e + 6:e + 10] = struct.pack(">I", pk)
    return bytes(cab)


def gerar(nome):
    info = ler((EXT / f"{nome}.pmf").read_bytes())
    gops, sys_hdr, pts0, dts0 = gops_e_au(info)
    with tempfile.TemporaryDirectory(dir=str(ROOT / "build")) as td:
        es, total = codificar(nome, gops, Path(td))
    aus = dividir_au(es)
    if len(aus) != sum(gops):
        raise ValueError(f"{nome}: {len(aus)} imagens codificadas, esperado {sum(gops)}")
    fluxo, gop_ini = multiplexar(info, aus, gops, sys_hdr, pts0, dts0)
    cab = cabecalho(info, len(fluxo), gop_ini)
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / f"{nome}.pmf"
    out.write_bytes(cab + fluxo)
    print(f"{nome}: {len(aus)} imagens, {len(gops)} GOPs, {len(fluxo) // PACK} packs -> {out} ({len(cab) + len(fluxo):,} bytes)")
    return out


def mp4(nome):
    """MP4 de conferência a partir do PMF PT gerado (o mesmo arquivo que vai para a ISO): vídeo H.264 do PMF +
    áudio ATRAC3+ JP do PMF, alinhados pelos PTS (o áudio começa antes do vídeo)."""
    info = ler((OUT / f"{nome}.pmf").read_bytes())
    es, pay, vpts, apts = bytearray(), bytearray(), None, None
    for pes in info["packs"]:
        for sid, b in pes:
            if sid == 0xE0:
                if vpts is None and b[7] & 0x80:
                    vpts = ts_ler(b[9:14])
                es += b[9 + b[8]:]
            if sid == 0xBD:
                if apts is None and b[7] & 0x80:
                    apts = ts_ler(b[9:14])
                pay += b[9 + b[8] + 4:]
    params = struct.unpack(">H", pay[2:4])[0]
    fsz = ((params & 0x3FF) + 1) * 8
    fr = [bytes(pay[i + 8:i + 8 + fsz]) for i in range(0, len(pay) - fsz - 7, fsz + 8)]
    oma = bytearray(96)
    oma[0:8] = b"EA3\x01\x00\x60\xff\xff"
    oma[32] = 1
    oma[34:36] = struct.pack(">H", params)
    with tempfile.TemporaryDirectory(dir=str(ROOT / "build")) as td:
        (Path(td) / "v.264").write_bytes(bytes(es))
        (Path(td) / "a.oma").write_bytes(bytes(oma) + b"".join(fr))
        dest = ROOT / "testes" / "gravacao" / "videos_GEB" / f"{nome}_PT_legendado_audioJP.mp4"
        dest.parent.mkdir(parents=True, exist_ok=True)
        atraso = (vpts - apts) / 90000
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-r", "30000/1001", "-i", str(Path(td) / "v.264"),
                        "-i", str(Path(td) / "a.oma"), "-map", "0:v", "-map", "1:a",
                        "-vf", f"tpad=start_duration={atraso:.4f}:start_mode=clone,scale=960:544:flags=lanczos",
                        "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                        str(dest)], check=True)
    print(f"{nome}: {dest} (vídeo começa em {atraso:.4f} s)")
    return dest


def conferir(caminho):
    info = ler(Path(caminho).read_bytes())
    gops, _s, pts0, dts0 = gops_e_au(info)
    a = audio_packs(info)
    print(f"{caminho}: {len(info['packs'])} packs, GOPs {len(gops)} ({sum(gops)} imagens), áudio {len(a)} packs, "
          f"PTS0 {pts0} DTS0 {dts0}")


if __name__ == "__main__":
    acao = sys.argv[1]
    nomes = sys.argv[2:] or ["OIP_GEB01", "OIP_GEB02"]
    for n in nomes:
        {"audio": extrair_audio, "gerar": gerar, "conferir": conferir, "mp4": mp4}[acao](n)
