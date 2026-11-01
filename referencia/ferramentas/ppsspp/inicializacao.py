"""Inicialização automática do Oreimo no PPSSPP, guiada por estado (sem teclas às cegas).

Mapeamento: os botões são injetados no CONTROLE EMULADO pela API de depuração
(input.buttons.*), não pelo teclado — independe de foco/janela. Para referência,
no teclado padrão do projeto: X = ○ (circle), Enter = SELECT, Espaço = START.
No jogo (japonês), ○ confirma; × cancela/oculta a caixa.

Sequência equivalente à manual (X, Enter, Enter, X), mas condicionada:
  * aviso/pergunta estática (não é título nem jogo)  -> ○   (no máx. 3 vezes)
  * logotipos/vídeo de abertura (imagem mudando)      -> espera; START
    só após 25 s sem chegar ao título (no máx. 3 vezes)
  * tela de título reconhecida (referência)          -> ○ = "Initial start"
  * partida iniciada = texto da 1ª caixa esperada presente na RAM E tela parada
    (o jogo pré-carrega a fala e toca o vídeo de abertura; START pula o vídeo)
Antes de concluir qualquer coisa, confere que a emulação está avançando
(cpu.status: ticks crescendo) e que a CPU não está pausada.
"""
import struct
import time
import zlib
from pathlib import Path

from ppsspp_api import FB_SIZE, VRAM, rgba_to_png

REF = Path(__file__).resolve().parent / "referencias"
RAM0, RAMSZ = 0x08800000, 0x01800000


def _png_rgb(path):
    """Decodificador PNG mínimo (8 bits RGB/RGBA, sem entrelaçamento) -> (w, h, bytes RGB)."""
    data = Path(path).read_bytes()
    pos, idat, w, h = 8, b"", 0, 0
    ct = 6
    while pos < len(data):
        n = struct.unpack(">I", data[pos:pos + 4])[0]
        t = data[pos + 4:pos + 8]
        d = data[pos + 8:pos + 8 + n]
        if t == b"IHDR":
            w, h, _bd, ct = struct.unpack(">IIBB", d[:10])
        elif t == b"IDAT":
            idat += d
        pos += 12 + n
    bpp = 4 if ct == 6 else 3
    raw = zlib.decompress(idat)
    stride = w * bpp
    out, prev = bytearray(), bytearray(stride)
    i = 0
    for _y in range(h):
        f = raw[i]
        line = bytearray(raw[i + 1:i + 1 + stride])
        i += 1 + stride
        for x in range(stride):
            a = line[x - bpp] if x >= bpp else 0
            b = prev[x]
            c = prev[x - bpp] if x >= bpp else 0
            if f == 1:
                line[x] = (line[x] + a) & 255
            elif f == 2:
                line[x] = (line[x] + b) & 255
            elif f == 3:
                line[x] = (line[x] + (a + b) // 2) & 255
            elif f == 4:
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                line[x] = (line[x] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        prev = line
        for x in range(w):
            out += line[x * bpp:x * bpp + 3]
    return w, h, bytes(out)


def signature_fb(fb, gw=24, gh=17):
    """Assinatura 24x17 de luminância média a partir do framebuffer RGBA (stride 512)."""
    sig = []
    cw, chh = 480 // gw, 272 // gh
    for gy in range(gh):
        for gx in range(gw):
            s = 0
            for y in range(gy * chh, gy * chh + chh, 4):
                row = y * 2048
                for x in range(gx * cw, gx * cw + cw, 4):
                    o = row + x * 4
                    s += fb[o] + fb[o + 1] + fb[o + 2]
            sig.append(s)
    m = max(sig) or 1
    return [v / m for v in sig]


def signature_png(path):
    w, h, rgb = _png_rgb(path)
    fb = bytearray(512 * 272 * 4)
    for y in range(min(h, 272)):
        for x in range(min(w, 480)):
            o, q = (y * 512 + x) * 4, (y * w + x) * 3
            fb[o:o + 3] = rgb[q:q + 3]
    return signature_fb(bytes(fb))


def regiao_menu(sig, gw=24):
    """Células da assinatura na área dos botões do menu de título (direita/baixo),
    que não muda com o personagem sorteado da tela de título."""
    return [sig[gy * gw + gx] for gy in range(9, 17) for gx in range(12, 24)]


def barra_titulo(fb, stride=512):
    """Fração de pixels verdes da faixa de copyright (y 258–269) — existe na tela "push start button" e no
    menu do título (≈0,57), nunca no vídeo de abertura (≈0,0). Medido em 23/10 (testes/visuais/ref_titulo17)."""
    n = verdes = 0
    for y in range(258, 270, 3):
        base = y * stride * 4
        for x in range(340, 480, 2):        # só a ponta direita: o personagem sorteado pode cobrir o centro
            r, g, b = fb[base + 4 * x], fb[base + 4 * x + 1], fb[base + 4 * x + 2]
            n += 1
            verdes += g > 180 and g - r > 40 and g - b > 80     # verde do menu (90,213,0) e da tela push (143,197,87)
    return verdes / n


def dist(a, b):
    return sum(abs(x - y) for x, y in zip(a, b)) / len(a)


class Estado:
    def __init__(self, p, out, log):
        self.p, self.out, self.log = p, Path(out), log
        self.t0 = time.time()
        self.ref_titulo = signature_png(REF / "titulo.png")
        # menu do título em PT (imagem sg_title_select traduzida em 19/10): referência adicional
        self.refs_titulo = [self.ref_titulo] + [signature_png(p) for p in sorted(REF.glob("titulo_*.png"))]
        self.last_ticks = None

    def ev(self, *x):
        self.log.append((round(time.time() - self.t0, 1),) + x)

    def frame(self):
        self.p.pause()
        try:
            return self.p.read(VRAM, FB_SIZE)
        finally:
            self.p.resume()

    def emulacao_avancando(self, espera=1.0):
        """True se os ticks da CPU emulada crescem (e não está em stepping)."""
        st1 = self.p.request("cpu.status")
        if st1.get("stepping"):
            self.p.resume()
            st1 = self.p.request("cpu.status")
        time.sleep(espera)
        st2 = self.p.request("cpu.status")
        ok = st2.get("ticks", 0) > st1.get("ticks", 0) and not st2.get("paused")
        if not ok:
            self.ev("EMULACAO_PARADA", st1.get("ticks"), st2.get("ticks"), st2.get("paused"))
        return ok

    def ram_contem(self, texto):
        self.p.pause()
        try:
            return texto.encode("utf-16-le") in self.p.dump_ram(RAM0, RAMSZ)
        finally:
            self.p.resume()

    def salvar(self, nome, fb):
        d = self.out / "inicio"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{nome}.png").write_bytes(rgba_to_png(fb))


def iniciar_novo_jogo(p, out, log, primeira_fala, prazo=300, so_ate_carregar=False):
    """Leva o jogo da inicialização até a 1ª fala. -> 'OK' | 'INCONCLUSIVO:<motivo>'
    so_ate_carregar: devolve 'OK' assim que a 1ª fala estiver na RAM (sem pular o vídeo de
    abertura com START — usado na gravação de Conversa a Dois, que não para de se mexer)."""
    e = Estado(p, out, log)
    titulo_vezes = aviso_vezes = pulo_vezes = 0
    ultimo_sig, estatico_desde, mudando_desde = None, None, time.time()
    texto_carregado, parado_n, pulo_video, ultimo_pulo = None, 0, 0, 0.0
    k = 0
    while time.time() - e.t0 < prazo:
        if k % 5 == 0 and not e.emulacao_avancando(0.3):
            if not e.emulacao_avancando(2.0):
                return "INCONCLUSIVO:emulacao_parada"
        if not texto_carregado and (titulo_vezes or aviso_vezes or pulo_vezes or k % 6 == 5) \
                and e.ram_contem(primeira_fala):
            texto_carregado = time.time()
            e.ev("1a_fala_carregada_na_RAM")
            if so_ate_carregar:
                return "OK"
        if texto_carregado:
            # o jogo pré-carrega a fala e toca o vídeo de abertura antes do prólogo:
            # só conclui quando a tela parar de mudar (sem vídeo)
            fb = e.frame()
            sig = signature_fb(fb)
            parado = ultimo_sig is not None and dist(sig, ultimo_sig) < 0.004
            ultimo_sig = sig
            parado_n = parado_n + 1 if parado else 0
            if parado_n >= 3:
                e.ev("partida_iniciada")
                e.salvar(f"{k:02d}_partida_iniciada", fb)
                return "OK"
            if not parado and time.time() - texto_carregado > 8 and pulo_video < 2 \
                    and time.time() - ultimo_pulo > 8:
                e.salvar(f"{k:02d}_video_abertura", fb)
                p.press("start", 6)
                pulo_video += 1
                ultimo_pulo = time.time()
                e.ev("START (pular vídeo de abertura)")
            k += 1
            time.sleep(0.7)
            continue
        fb = e.frame()
        sig = signature_fb(fb)
        # tela inteira OU só a região do menu (o personagem do título é sorteado)
        d_tit = min(min(dist(sig, r), dist(regiao_menu(sig), regiao_menu(r)) * 0.04 / 0.095)
                    for r in e.refs_titulo)
        estatico = ultimo_sig is not None and dist(sig, ultimo_sig) < 0.004
        ultimo_sig = sig
        now = time.time()
        if estatico:
            estatico_desde = estatico_desde or now
            mudando_desde = None
        else:
            estatico_desde = None
            mudando_desde = mudando_desde or now
        # tela de título sem o menu ("push start button"): o personagem pisca, então nem "parado" nem
        # "vídeo" detectam — reconhece pela faixa verde e aperta START (antes ficava no laço da abertura)
        if d_tit >= 0.04 and barra_titulo(fb) > 0.4 and now - getattr(e, "ult_start_titulo", 0) > 4:
            e.salvar(f"{k:02d}_push_start", fb)
            p.press("start", 6)
            e.ult_start_titulo = now
            e.ev("START (tela push start reconhecida pela faixa verde)")
            time.sleep(2.5)
            k += 1
            continue
        if d_tit < 0.04:
            if titulo_vezes >= 3:
                return "INCONCLUSIVO:titulo_nao_responde"
            e.salvar(f"{k:02d}_titulo", fb)
            e.ev("titulo_reconhecido", round(d_tit, 4))
            p.press("circle", 6)
            titulo_vezes += 1
            e.ev("○ (Initial start)")
            time.sleep(4)
        elif estatico and estatico_desde and now - estatico_desde > 6 and sum(sig) > 1:
            # tela parada que não é o título nem a partida: aviso/pergunta
            if aviso_vezes >= 3:
                e.salvar(f"{k:02d}_aviso_persistente", fb)
                return "INCONCLUSIVO:aviso_nao_dispensado"
            e.salvar(f"{k:02d}_aviso", fb)
            p.press("circle", 6)
            aviso_vezes += 1
            e.ev("○ (aviso)", round(d_tit, 4))
            estatico_desde = None
            time.sleep(3)
        elif mudando_desde and now - mudando_desde > 15:
            if pulo_vezes < 3:
                e.salvar(f"{k:02d}_video", fb)
                p.press("start", 6)
                pulo_vezes += 1
                e.ev("START (pular vídeo/logos)")
                mudando_desde = now
        k += 1
        time.sleep(0.5)
    return "INCONCLUSIVO:prazo_esgotado"


def chegar_ao_titulo(p, out, log, prazo=150):
    """Da inicialização (ou de um game.reset) até a tela de título, sem escolher nada.
    -> 'OK' | 'INCONCLUSIVO:<motivo>'. Usado para Load de checkpoint (Continue)."""
    e = Estado(p, out, log)
    ultimo_sig, estatico_desde, mudando_desde = None, None, time.time()
    avisos = pulos = 0
    k, menu_seguidos = 0, 0
    refs_reg = [regiao_menu(r) for r in e.refs_titulo]
    while time.time() - e.t0 < prazo:
        if k % 5 == 0 and not e.emulacao_avancando(0.3) and not e.emulacao_avancando(2.0):
            return "INCONCLUSIVO:emulacao_parada"
        fb = e.frame()
        sig = signature_fb(fb)
        now = time.time()
        estatico = ultimo_sig is not None and dist(sig, ultimo_sig) < 0.004
        ultimo_sig = sig
        if estatico:
            estatico_desde, mudando_desde = estatico_desde or now, None
        else:
            estatico_desde, mudando_desde = None, mudando_desde or now
        d = min(dist(regiao_menu(sig), r) for r in refs_reg)
        if k % 10 == 0:
            e.ev("dist_menu", round(d, 4), estatico)
        menu_seguidos = menu_seguidos + 1 if d < 0.095 else 0
        if menu_seguidos >= 2:
            e.salvar(f"{k:02d}_titulo", fb)
            e.ev("titulo_reconhecido", round(d, 4))
            return "OK"
        if estatico and estatico_desde and now - estatico_desde > 6 and sum(sig) > 1:
            if avisos >= 3:
                e.salvar(f"{k:02d}_aviso_persistente", fb)
                return "INCONCLUSIVO:aviso_nao_dispensado"
            e.salvar(f"{k:02d}_aviso", fb)
            p.press("circle", 6)
            avisos += 1
            e.ev("○ (aviso)", round(d, 4))
            estatico_desde = None
            time.sleep(3)
        elif mudando_desde and now - mudando_desde > 8 and pulos < 10:
            # logos/vídeo ou tela "push start button" (animada, personagem aleatório)
            p.press("start", 6)
            pulos += 1
            e.ev("START (pular vídeo/logos)")
            mudando_desde = now
        k += 1
        time.sleep(0.5)
    e.salvar("titulo_prazo_esgotado", e.frame())
    return "INCONCLUSIVO:prazo_esgotado"
