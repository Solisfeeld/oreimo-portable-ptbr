"""Cliente mínimo da API de depuração remota do PPSSPP (WebSocket em /debugger).

Somente biblioteca padrão. Roda DENTRO do sandbox flatpak criado por
rodar_ppsspp.sh (rede isolada: só loopback), conectando em 127.0.0.1.
"""
import base64
import json
import os
import socket
import struct
import time


class WSError(RuntimeError):
    pass


class WebSocket:
    def __init__(self, host, port, path="/debugger", timeout=30):
        self.sock = socket.create_connection((host, port), timeout=timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        req = (f"GET {path} HTTP/1.1\r\nHost: {host}:{port}\r\nUpgrade: websocket\r\n"
               f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n")
        self.sock.sendall(req.encode())
        resp = b""
        while b"\r\n\r\n" not in resp:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise WSError("conexão fechada no handshake")
            resp += chunk
        head, self.buf = resp.split(b"\r\n\r\n", 1)
        if b" 101 " not in head.split(b"\r\n")[0]:
            raise WSError("handshake recusado: " + head.decode(errors="replace")[:200])

    def _recv_exact(self, n):
        while len(self.buf) < n:
            chunk = self.sock.recv(1 << 20)
            if not chunk:
                raise WSError("conexão fechada")
            self.buf += chunk
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def send_text(self, text):
        data = text.encode()
        hdr = bytearray([0x81])
        n = len(data)
        if n < 126:
            hdr.append(0x80 | n)
        elif n < 65536:
            hdr.append(0x80 | 126)
            hdr += struct.pack(">H", n)
        else:
            hdr.append(0x80 | 127)
            hdr += struct.pack(">Q", n)
        mask = os.urandom(4)
        hdr += mask
        self.sock.sendall(bytes(hdr) + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))

    def recv_text(self):
        parts = []
        while True:
            b1, b2 = self._recv_exact(2)
            fin, op = b1 & 0x80, b1 & 0x0F
            n = b2 & 0x7F
            if n == 126:
                n = struct.unpack(">H", self._recv_exact(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", self._recv_exact(8))[0]
            if b2 & 0x80:
                mask = self._recv_exact(4)
                payload = bytes(b ^ mask[i % 4] for i, b in enumerate(self._recv_exact(n)))
            else:
                payload = self._recv_exact(n)
            if op == 0x8:
                raise WSError("servidor fechou a conexão")
            if op == 0x9:  # ping -> pong
                self.sock.sendall(bytes([0x8A, 0x80]) + os.urandom(4))
                continue
            if op in (0x1, 0x0):
                parts.append(payload)
                if fin:
                    return b"".join(parts).decode("utf-8", errors="replace")


class PPSSPP:
    """Requisições com ticket; eventos assíncronos ficam em self.events."""

    def __init__(self, port, host="127.0.0.1", connect_timeout=60):
        t0 = time.time()
        while True:
            try:
                self.ws = WebSocket(host, port)
                break
            except (OSError, WSError):
                if time.time() - t0 > connect_timeout:
                    raise
                time.sleep(0.5)
        self.ticket = 0
        self.events = []
        self.request("version", name="oreimo-ptbr-teste", version="1")

    def request(self, event, timeout=60, **params):
        self.ticket += 1
        t = str(self.ticket)
        msg = dict(event=event, ticket=t, **params)
        self.ws.send_text(json.dumps(msg))
        self.ws.sock.settimeout(timeout)
        while True:
            m = json.loads(self.ws.recv_text())
            if m.get("ticket") == t:
                if m.get("event") == "error":
                    raise WSError(f"{event}: {m.get('message')}")
                return m
            self.events.append(m)

    def send_wait(self, event, wait_for, timeout=30, **params):
        """Envia um evento sem resposta direta e espera um evento assíncrono."""
        self.ticket += 1
        self.ws.send_text(json.dumps(dict(event=event, ticket=str(self.ticket), **params)))
        self.ws.sock.settimeout(timeout)
        for i, m in enumerate(self.events):
            if m.get("event") == wait_for:
                return self.events.pop(i)
        while True:
            m = json.loads(self.ws.recv_text())
            if m.get("event") == "error":
                raise WSError(f"{event}: {m.get('message')}")
            if m.get("event") == wait_for:
                return m
            self.events.append(m)

    def _send(self, event, **params):
        self.ticket += 1
        self.ws.send_text(json.dumps(dict(event=event, ticket=str(self.ticket), **params)))

    def _wait_state(self, stepping, timeout=15):
        t = time.time()
        while time.time() - t < timeout:
            if bool(self.request("cpu.status").get("stepping")) == stepping:
                self.events = [m for m in self.events if m.get("event") not in ("cpu.stepping", "cpu.resume")]
                return
            time.sleep(0.02)
        raise WSError(f"CPU não chegou ao estado stepping={stepping}")

    def pause(self, tentativas=3):
        if self.request("cpu.status").get("stepping"):
            return
        for k in range(tentativas):
            self._send("cpu.stepping")
            try:
                self._wait_state(True)
                return
            except WSError:
                if k == tentativas - 1:
                    raise

    def resume(self):
        self._send("cpu.resume")
        self._wait_state(False)

    # atalhos -------------------------------------------------------------
    def status(self):
        return self.request("game.status")

    def press(self, button, frames=4):
        return self.request("input.buttons.press", button=button, duration=frames)

    def hold(self, buttons: dict):
        return self.request("input.buttons.send", buttons=buttons)

    def screenshot_png(self, keep_paused=False):
        """Pausa a CPU (exigência da versão 1.20.x), captura e retoma."""
        self.pause()
        try:
            m = self.request("gpu.buffer.screenshot", type="uri")
        finally:
            if not keep_paused:
                self.resume()
        uri = m["uri"]
        return base64.b64decode(uri.split(",", 1)[1]), m["width"], m["height"]

    def read(self, addr, size):
        return base64.b64decode(self.request("memory.read", address=addr, size=size)["base64"])

    def write(self, addr, data: bytes):
        """Escreve na RAM emulada (só para experimentos em memória; nada vai para a ISO)."""
        return self.request("memory.write", address=addr, base64=base64.b64encode(data).decode())

    def modules(self):
        """Lista de módulos carregados (nome, endereço base, tamanho)."""
        return self.request("hle.module.list").get("modules", [])

    def dump_ram(self, addr=0x08800000, size=0x01800000, chunk=0x400000):
        return b"".join(self.read(a, min(chunk, addr + size - a)) for a in range(addr, addr + size, chunk))

    def search_bytes(self, pattern: bytes, addr=0x08800000, size=0x01800000, max_results=50, ram=None):
        """Busca no cliente (memory.search não existe no 1.20.x). Chamar com a CPU pausada."""
        ram = ram if ram is not None else self.dump_ram(addr, size)
        res, i = [], ram.find(pattern)
        while i >= 0 and len(res) < max_results:
            res.append(addr + i)
            i = ram.find(pattern, i + 1)
        return res


# ---------------------------------------------------------------------------
# Captura pela VRAM (gpu.buffer.screenshot falha no PPSSPP 1.20.x deste sistema)
# ---------------------------------------------------------------------------
import zlib  # noqa: E402

VRAM = 0x04000000
FB_STRIDE = 512
FB_SIZE = FB_STRIDE * 272 * 4      # 8888
FB_ADDRS = (VRAM, VRAM + FB_SIZE)  # buffer duplo


def rgba_to_png(raw, width=480, height=272, stride=FB_STRIDE):
    rows = []
    for y in range(height):
        line = bytearray(raw[y * stride * 4:(y * stride + width) * 4])
        line[3::4] = b"\xff" * width  # alfa do framebuffer é lixo: torna opaco
        rows.append(b"\x00" + bytes(line))
    def chunk(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(b"".join(rows), 6)) + chunk(b"IEND", b""))


def capture_framebuffers(p):
    """Pausa, lê os dois buffers de vídeo e retoma. -> [(endereço, bytes RGBA)]"""
    p.pause()
    try:
        return [(a, p.read(a, FB_SIZE)) for a in FB_ADDRS]
    finally:
        p.resume()
