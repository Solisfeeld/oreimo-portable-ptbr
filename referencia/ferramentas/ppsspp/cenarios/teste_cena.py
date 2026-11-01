"""Teste visual automatizado de cenas (roda dentro do sandbox do PPSSPP).

Para cada cena pedida, lê da própria ISO em teste a lista ordenada de caixas
de texto (blocos 100, incluindo continuações) e avança o jogo com ○:

 * antes de cada ○ espera a caixa terminar de ser desenhada (região do texto
   estável por ~1 s), para que cada ○ seja exatamente UM avanço;
 * "oráculo" de posição: descobre dinamicamente na RAM a variável do motor que
   guarda o ÍNDICE DO BLOCO em execução (u32), filtrando candidatos a cada
   avanço; depois confere, caixa a caixa, que o motor está no bloco esperado;
 * grava uma captura de cada caixa (caixas/NNN_CENA_bNNN.png);
 * na troca de cena, redescobre o oráculo com os índices da cena seguinte.

Uso (via rodar_ppsspp.sh): --iso ISO --cenas AKYO_0000A AKYO_0010A [--novo-jogo]
                           [--parar-apos N]  (caixas da última cena)
                           [--checkpoint NOME] (começa de um save do jogo; ver checkpoint.py)
                           [--salvar-checkpoint NOME] (salva ao terminar)
Saída: relatorio.json
"""
import argparse
import json
import struct
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE.parents[2]))  # ferramentas/
from ppsspp_api import PPSSPP, rgba_to_png, FB_SIZE, VRAM  # noqa: E402
from inicializacao import iniciar_novo_jogo, chegar_ao_titulo, Estado  # noqa: E402
import checkpoint as cp  # noqa: E402
import hashlib  # noqa: E402
from navegacao import avancar_ate_texto  # noqa: E402
from construir import width as text_width, MAX_UMA_LINHA as MAX_WIDTH  # noqa: E402
import isofs  # noqa: E402
import oreimo_script as osc  # noqa: E402

RAM0, RAMSZ = 0x08800000, 0x01800000
# Endereços (u32) que guardam o índice do bloco em execução, achados por
# instantâneos em estados conhecidos (FORMATOS.md §10). Heap determinístico
# a partir de "Initial start"; validados a cada uso.
ORACULO_CONHECIDO = (0x08B0D1E8,)
# (0x08CE7298 também vale no prólogo, mas é realocado a cada cena — não usar)
TEXT_Y0, TEXT_Y1 = 200, 272


def scene_boxes(rd, scene):
    o = osc.parse_obj(rd.obj(scene))
    return [(i, b.text) for i, b in o.text_blocks((100,))]


class Runner:
    def __init__(self, p, out):
        self.p, self.out = p, out
        self.cands = None      # endereços candidatos do oráculo
        self.t0 = time.time()
        self.events = []
        self.diffs = []

    def ev(self, *x):
        self.events.append((round(time.time() - self.t0, 1),) + x)

    def frame(self):
        self.p.pause()
        try:
            return self.p.read(VRAM, FB_SIZE)
        finally:
            self.p.resume()

    @staticmethod
    def _diff_pixels(a, b):
        """Pixels diferentes (soma |ΔRGB| > 60) na região do texto, amostrando 1 a cada 2 linhas."""
        n = 0
        for y in range(TEXT_Y0, TEXT_Y1, 2):
            o = y * 2048 + 40 * 4
            ra, rb = a[o:o + 400 * 4], b[o:o + 400 * 4]
            if ra == rb:
                continue
            for x in range(0, 1600, 4):
                if abs(ra[x] - rb[x]) + abs(ra[x + 1] - rb[x + 1]) + abs(ra[x + 2] - rb[x + 2]) > 60:
                    n += 1
        return n

    def wait_stable(self, timeout=40, need=3, step=0.4, limiar=120):
        """Espera a caixa terminar de ser desenhada: `need` capturas seguidas com
        diferença pequena (o ícone animado de 'aguardando' mexe poucos pixels;
        a digitação mexe muitos). Amostragem de 1 a cada 2 linhas."""
        t = time.time()
        last, same, fb = None, 0, None
        while time.time() - t < timeout:
            fb = self.frame()
            dpx = self._diff_pixels(fb, last) if last is not None else None
            if dpx is not None:
                self.diffs.append(dpx)
            if dpx is not None and dpx <= limiar:
                same += 1
            else:
                same = 0
            if same >= need - 1:
                return fb, True
            last = fb
            time.sleep(step)
        return fb, False

    def wait_change(self, ref_fb, timeout=15, limiar=300, step=0.3):
        """Espera a região do texto ficar diferente da captura anterior
        (texto novo começou a ser desenhado). -> (fb, mudou)"""
        if ref_fb is None:
            return None, True
        t = time.time()
        fb = None
        while time.time() - t < timeout:
            fb = self.frame()
            if self._diff_pixels(fb, ref_fb) > limiar:
                return fb, True
            time.sleep(step)
        return fb, False

    def pc_values(self):
        if self.cands is None:
            return None
        self.p.pause()
        try:
            if len(self.cands) > 16:
                ram = self.p.dump_ram(RAM0, RAMSZ)
                return {a: struct.unpack_from("<I", ram, a - RAM0)[0] for a in self.cands}
            return {a: struct.unpack("<I", self.p.read(a, 4))[0] for a in self.cands}
        finally:
            self.p.resume()

    def known_values(self):
        self.p.pause()
        try:
            return [struct.unpack("<I", self.p.read(a, 4))[0] for a in ORACULO_CONHECIDO]
        finally:
            self.p.resume()

    def discover(self, value):
        kv = self.known_values()
        if all(v == value for v in kv):
            self.cands = list(ORACULO_CONHECIDO)
            self.ev("oraculo_conhecido_ok", value)
            return
        self.ev("oraculo_conhecido_nao_bate", value, kv)
        self.p.pause()
        try:
            ram = self.p.dump_ram(RAM0, RAMSZ)
        finally:
            self.p.resume()
        pat = struct.pack("<I", value)
        res, i = [], ram.find(pat)
        while i >= 0:
            if i % 4 == 0:
                res.append(RAM0 + i)
            i = ram.find(pat, i + 1)
        self.cands = res
        self.ev("descoberta", value, len(res))

    def filter(self, value):
        vals = self.pc_values()
        if vals is None:
            return
        self.cands = [a for a, v in vals.items() if v == value]
        self.ev("filtro", value, len(self.cands))

    def pc(self):
        """Valor do oráculo se os candidatos concordam (<=4), senão None."""
        if not self.cands or len(self.cands) > 4:
            return None
        vals = set(self.pc_values().values())
        return vals.pop() if len(vals) == 1 else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--porta", type=int, required=True)
    ap.add_argument("--saida", required=True)
    ap.add_argument("--iso", required=True)
    ap.add_argument("--cenas", nargs="+", required=True)
    ap.add_argument("--novo-jogo", action="store_true")
    ap.add_argument("--parar-apos", type=int, default=0)
    ap.add_argument("--pular-ate", action="store_true", help="avança rápido (sem verificar) até a 1ª cena de --cenas")
    ap.add_argument("--checkpoint", help="começa carregando este checkpoint (build/checkpoints/NOME)")
    ap.add_argument("--salvar-checkpoint", metavar="NOME", help="ao terminar, salva no jogo e registra o checkpoint")
    a = ap.parse_args()
    out = Path(a.saida)
    (out / "caixas").mkdir(parents=True, exist_ok=True)
    rd = osc.ResDat(isofs.read_file(a.iso, "/PSP_GAME/INSDIR/RES.DAT"))
    p = PPSSPP(a.porta)
    r = Runner(p, out)
    rep = {"iso": a.iso, "cenas": {}}

    if a.novo_jogo:
        # partida nova sempre começa no prólogo, mesmo que o teste comece mais adiante
        first = scene_boxes(rd, "AKYO_0000A")[0][1]
        res = iniciar_novo_jogo(p, out, r.events, first)
        rep["inicializacao"] = res
        r.ev("inicializacao", res)
        if res != "OK":
            rep["resultado"] = "INCONCLUSIVO"
            (out / "relatorio.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1))
            print("INICIALIZAÇÃO", res)
            return
    if a.checkpoint:
        meta = cp.restaurar(a.checkpoint)
        rep["checkpoint"] = meta
        atual = hashlib.md5(rd.obj(meta["cena"])).hexdigest()
        if meta.get("obj_md5") and meta["obj_md5"] != atual:
            rep["checkpoint_aviso"] = "script da cena mudou desde o checkpoint: posição pode não bater"
        res = chegar_ao_titulo(p, out, r.events)
        if res != "OK":
            rep["resultado"] = "INCONCLUSIVO"
            rep["erro_automacao"] = "titulo: " + res
            (out / "relatorio.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1))
            print("CHECKPOINT: título", res)
            return
        v = cp.carregar(p, meta.get("slot", 1), log=r.events)
        rep["checkpoint_bloco_apos_load"] = v
        if abs(v - meta["bloco"]) > 1:
            rep["resultado"] = "INCONCLUSIVO"
            rep["erro_automacao"] = f"checkpoint incompatível: bloco {v}, esperado {meta['bloco']}"
            (out / "relatorio.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1))
            print("CHECKPOINT INCOMPATÍVEL", v, meta["bloco"])
            return
        time.sleep(2)
    saude = Estado(p, out, r.events)
    if a.pular_ate:
        alvo = scene_boxes(rd, a.cenas[0])[0][1]
        ok = avancar_ate_texto(p, alvo, log=r.events)
        rep["pulo"] = {"ate": a.cenas[0], "ok": ok}
        if not ok:
            rep["resultado"] = "INCONCLUSIVO"
            (out / "relatorio.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1))
            print("PULO FALHOU")
            return
        time.sleep(3)

    try:
        run_scenes(a, rd, p, r, rep, saude, out)
    except Exception as e:  # noqa: BLE001
        rep["erro_automacao"] = f"{type(e).__name__}: {e}"
        rep["resultado"] = "INCONCLUSIVO"
        try:
            st = p.request("cpu.status")
            rep["estado_no_erro"] = {k: st.get(k) for k in ("stepping", "paused", "ticks")}
            fb = r.frame()
            (out / "caixas" / "ERRO_ultima_tela.png").write_bytes(rgba_to_png(fb))
        except Exception as e2:  # noqa: BLE001
            rep["estado_no_erro"] = f"indisponível: {e2}"
    if a.salvar_checkpoint and "checkpoint_salvo" not in rep:
        rep["checkpoint_salvo"] = "FALHOU (última caixa não alcançada)"
    rep["eventos"] = r.events
    rep["diferencas_px_amostra"] = r.diffs[:400]
    rep["duracao_s"] = round(time.time() - r.t0, 1)
    (out / "relatorio.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1))
    for s_, v in rep["cenas"].items():
        print(s_, v.get("resumo"), "divergências:", len(v["divergencias"]), "sem oráculo:", v["sem_oraculo"])
    if "erro_automacao" in rep:
        print("INCONCLUSIVO (automação):", rep["erro_automacao"])


def salvar_checkpoint_aqui(a, rd, p, r, rep, cena):
    try:
        time.sleep(2)
        bloco = cp.oraculo(p)
        if cp.salvar(p, 1, log=r.events):
            rep["checkpoint_salvo"] = cp.registrar(
                a.salvar_checkpoint, cena, bloco, a.iso,
                {"slot": 1, "obj_md5": hashlib.md5(rd.obj(cena)).hexdigest()})
        else:
            rep["checkpoint_salvo"] = "FALHOU (save não gravou)"
    except Exception as e:  # noqa: BLE001
        rep["checkpoint_salvo"] = f"FALHOU: {e}"


def run_scenes(a, rd, p, r, rep, saude, out):
    """Laço principal. Oráculo = índice do bloco em 0x08B0D1E8 (sem descoberta
    dinâmica, que se mostrou enganosa). Regras:
      * motor atrás do esperado -> espera sem apertar; no máximo 1 ○ extra, e só
        se a tela estiver parada há muito tempo;
      * motor à frente -> as caixas intermediárias são registradas como PULADAS;
      * oráculo fora da lista da cena -> INCONCLUSIVO (não aperta nada além do ○ normal)."""
    def pc_now():
        try:
            return r.known_values()[0]
        except Exception:  # noqa: BLE001
            return None

    for si, scene in enumerate(a.cenas):
        boxes = scene_boxes(rd, scene)
        idxs = [bi for bi, _t in boxes]
        if si == len(a.cenas) - 1 and a.parar_apos:
            boxes = boxes[:a.parar_apos]
        srep = {"esperadas": len(boxes), "caixas": [], "divergencias": [], "sem_oraculo": 0}
        rep["cenas"][scene] = srep
        k, prev_fb = 0, None

        # sincronização inicial: espera o oráculo apontar para uma caixa desta cena
        t = time.time()
        while time.time() - t < 120:
            v = pc_now()
            janela = idxs if (si == 0 and a.checkpoint) else idxs[:12]   # checkpoint: meio da cena
            if v in janela:
                k = idxs.index(v)
                break
            time.sleep(1.0)
        srep["sincronizacao"] = {"oraculo": pc_now(), "ordem_inicial": k, "s": round(time.time() - t, 1)}
        for j in range(k):
            srep["caixas"].append({"ordem": j, "bloco": boxes[j][0], "status": "NAO_VERIFICADA_inicio"})

        while k < len(boxes):
            idx, text = boxes[k]
            fb, stable = r.wait_stable()
            pc = pc_now()
            t_gate, extra = time.time(), 0
            while pc is not None and pc in idxs and pc < idx and time.time() - t_gate < 40:
                time.sleep(1.5)
                fb, stable = r.wait_stable()
                pc2 = pc_now()
                if pc2 == pc and stable and extra < 1 and time.time() - t_gate > 12:
                    p.press("circle", 4)
                    extra += 1
                    r.ev("circle_extra", scene, idx, pc)
                    time.sleep(0.8)
                pc = pc_now()
            if extra:
                srep.setdefault("avancos_extras", []).append({"bloco": idx, "extras": extra})
            emul_ok = stable or saude.emulacao_avancando(1.0)
            if pc == idx:
                status = "ok"
            elif pc is not None and pc in idxs and pc > idx:
                pos = idxs.index(pc)
                for j in range(k, min(pos, len(boxes))):
                    srep["caixas"].append({"ordem": j, "bloco": boxes[j][0], "status": "PULADA"})
                srep["divergencias"].append({"esperado": idx, "motor": pc})
                if pos >= len(boxes):
                    break
                k = pos
                idx, text = boxes[k]
                status = "ok_apos_pulo"
            else:
                status = "INCONCLUSIVO_oraculo" if emul_ok else "INCONCLUSIVO_emulacao_parada"
                srep["sem_oraculo"] += 1
            if status.startswith("ok"):
                _f, mudou = r.wait_change(prev_fb)
                if not mudou:
                    r.ev("tela_nao_mudou", scene, idx)
                fb, stable = r.wait_stable()
            spk, body = osc.split_speaker(text)
            linhas = body.split("＿")
            larg = max(text_width(ln, spk is not None) for ln in linhas)
            name = f"{k:03d}_{scene}_b{idx:03d}.png"
            (out / "caixas" / name).write_bytes(rgba_to_png(fb))
            prev_fb = fb
            srep["caixas"].append({
                "ordem": k, "bloco": idx, "status": status, "estavel": stable, "oraculo": pc,
                "largura_max": larg, "largura_ok": larg <= MAX_WIDTH, "linhas": len(linhas),
                "linhas_ok": len(linhas) <= 3,
                "acentos": sorted({c for c in body if ord(c) > 127 and c.isalpha()}),
                "continuacao": osc.parse_obj(rd.obj(scene)).blocks[idx].msg_id == osc.NO_MSG_ID,
                "texto": text, "captura": name, "t": round(time.time() - r.t0, 1)})
            k += 1
            if a.salvar_checkpoint and si == len(a.cenas) - 1 and k == len(boxes):
                # salva ainda na última caixa: depois dela pode vir vídeo ou Conversa a Dois,
                # onde o menu de sistema não abre
                salvar_checkpoint_aqui(a, rd, p, r, rep, scene)
                break
            p.press("circle", 4)
            time.sleep(0.6)

        if si + 1 < len(a.cenas):
            r.ev("fim_cena", scene)
            nb = scene_boxes(rd, a.cenas[si + 1])
            pat, first_idx = nb[0][1].encode("utf-16-le"), nb[0][0]
            t, got, last_change, last_pc = time.time(), False, time.time(), pc_now()
            while time.time() - t < 300:
                time.sleep(2)
                p.pause()
                try:
                    in_ram = pat in p.dump_ram(RAM0, RAMSZ)
                finally:
                    p.resume()
                v = pc_now()
                if in_ram and v == first_idx:
                    got = True
                    break
                if v != last_pc:
                    last_pc, last_change = v, time.time()
                elif time.time() - last_change > 15:
                    p.press("circle", 4)     # parado: talvez espere confirmação
                    last_change = time.time()
                    r.ev("circle_transicao", v)
            srep["transicao_detectada"] = got
            srep["transicao_s"] = round(time.time() - t, 1)

        ok = sum(1 for c in srep["caixas"] if c["status"].startswith("ok"))
        inc = sum(1 for c in srep["caixas"] if c["status"].startswith("INCONCLUSIVO"))
        bad = [c["bloco"] for c in srep["caixas"] if c["status"] == "PULADA"
               or not c.get("largura_ok", True) or not c.get("linhas_ok", True)]
        srep["resumo"] = f"{ok}/{len(boxes)} confirmadas pelo oráculo, {inc} inconclusivas, problemas: {bad}"
        srep["resultado"] = ("REPROVADO" if bad else "APROVADO" if ok == len(boxes)
                             else "APROVADO_COM_INCONCLUSIVAS")


if __name__ == "__main__":
    main()
