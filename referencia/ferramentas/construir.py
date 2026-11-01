#!/usr/bin/env python3
"""Constrói RES.DAT/first.dat (e opcionalmente a ISO) com a tradução PT-BR.

Base do disco: ISO inglesa v1 (EBOOT com suporte a texto ocidental, font.pgf,
imagens/menus já em inglês). Estrutura dos scripts: OBJ JAPONÊS (completo,
sem os cortes/realocações do patch inglês), com o texto PT-BR aplicado.

Para cada cena com arquivo traducao/discoN/cenas/<CENA>.txt:
  * pega o OBJ japonês da cena;
  * cada unidade com PT recebe "Nome「texto」" (nome via traducao/nomes.tsv);
  * o texto é quebrado com '＿' pela largura real dos glifos (fontmap);
  * se passar de 3 linhas, é dividido em caixas pelo quebra.py (pontuação, sintaxe,
    equilíbrio; nunca deixa caixa com 1–2 palavras se houver alternativa); as caixas
    extras viram blocos 100 novos (continuação, id 0xFFFF) inseridos logo depois —
    e as referências de índice (702/1301/1400) são remapeadas;
  * unidades sem PT: texto EN equivalente (se 1:1) ou JP (relatado).
Cenas sem arquivo de tradução ficam com o OBJ inglês original.

Uso:
  python3 ferramentas/construir.py --saida build/iso_teste/teste.iso [--cenas A B] \
      [--recompactar-todas N]   # (teste) re-gzipa as demais cenas com nível N
"""
import argparse
import gzip
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ferramentas"))
import isofs  # noqa: E402
import oreimo_script as osc  # noqa: E402
import tradfile  # noqa: E402
import quebra  # noqa: E402
import envpsp  # noqa: E402
from oreimo_core import iso_grow, seekmap  # noqa: E402
from oreimo_core.fontmap import ADVANCE, FALLBACK  # noqa: E402

MAX_WIDTH = 480      # caixa: termina em x≈424, antes das estrelas (x≈448), como o JP (≈427). O Histórico (△)
                     # re-quebra por caractere acima da sua largura: envpsp_numeros.tsv põe 0.75/490 (era
                     # 0.8/470, que cortava acima de ~446). Validado no PPSSPP em 19/10. Ver FORMATOS.md §6/§6b
MAX_UMA_LINHA = 484  # área segura, medida na captura e igual ao máximo do JP: x≈425; a 1ª estrelinha da caixa fica em x≈426 (31/10, pedido do autor)
LINES_PER_BOX = 3
LINE_BREAK = "＿"
BOX_BREAK = "¶"
BRACKET_W = ADVANCE.get("「", 18)

ISOS = {
    "1": {"en": ROOT / "Ore no Imouto (English v1) Disc 1" / "Ore no Imouto (English v1) Disc 1.iso",
          "jp": ROOT / "Ore no Imouto (Japan) Disc 1" / "Ore no Imouto (Japan) Disc 1.iso"},
    "2": {"en": ROOT / "Ore no Imouto (English v1) Disc 2" / "Ore no Imouto (English v1) Disc 2.iso"},
}
RES_PATH = "/PSP_GAME/INSDIR/RES.DAT"
ENVPSP_PATH = "/PSP_GAME/USRDIR/envpsp.dat"
FIRST_PATH = "/PSP_GAME/USRDIR/first.dat"
VIDEOS_APROVADOS = ROOT / "build" / "video_aprovado"
SEM_INGLES = False   # --base-jp: nada da ISO inglesa entra na imagem, nem como texto de reserva


def width(s: str, speech: bool) -> int:
    return sum(ADVANCE.get(c, FALLBACK) for c in s) + (BRACKET_W if speech else 0)


_LAYOUT = None  # definido após width()


def wrap_words(text: str, speech: bool, maxw: int = MAX_WIDTH) -> list[str]:
    words = text.split(" ")
    lines, cur = [], ""
    for w in words:
        cand = w if not cur else cur + " " + w
        if width(cand, speech) <= maxw:
            cur = cand
            continue
        if cur:
            lines.append(cur)
        # palavra maior que a linha inteira: corta por caractere
        while width(w, speech) > maxw:
            cut = len(w)
            while cut > 1 and width(w[:cut], speech) > maxw:
                cut -= 1
            lines.append(w[:cut])
            w = w[cut:]
        cur = w
    if cur or not lines:
        lines.append(cur)
    return lines


_LAYOUT = quebra.Layout(width, MAX_WIDTH, MAX_UMA_LINHA)
TITULO_MAX = 460     # cabeçalho do Histórico (o motor mede ~4% a mais; a largura do painel é 520)
_LAYOUT_TITULO = quebra.Layout(width, TITULO_MAX)
_SENT = re.compile(r'(?<=[.!?…♪」』"])\s+')


def layout(text: str, speech: bool) -> list[list[str]]:
    """Texto -> caixas (cada uma, lista de até 3 linhas). Divisão inteligente: ver quebra.py."""
    return _LAYOUT.layout(text, speech)


def load_names(path=ROOT / "traducao" / "nomes.tsv") -> dict:
    names = {}
    for ln in Path(path).read_text(encoding="utf-8").splitlines()[1:]:
        if ln.strip():
            parts = ln.split("\t")
            names[parts[0]] = parts[1]
    return names


def build_scene(jp_obj: bytes, entries: list, names: dict, report: dict) -> bytes:
    o = osc.parse_obj(jp_obj)
    by_idx = {e.idx: e for e in entries}
    new_blocks = []
    for i, b in enumerate(o.blocks):
        new_blocks.append(b)
        if b.type not in osc.GAME_TEXT_TYPES:
            continue
        e = by_idx.get(i)
        if e is None:
            report["sem_unidade"].append(i)
            continue
        spk_jp, _body = osc.split_speaker(b.text) if b.type == 100 else (None, b.text)
        if e.pt:
            body = e.pt
        elif len(e.en) == 1 and e.en[0] and not SEM_INGLES:
            report["fallback_en"] += 1
            b.text = e.en[0]
            continue
        else:
            report["fallback_jp"] += 1
            continue
        if b.type == 700 and LINE_BREAK not in body and width(body, False) > TITULO_MAX:
            # título longo: o Histórico mostra o título da cena como cabeçalho e re-quebra por caractere
            # ("…renegar o hobb|y otaku", 23/10) → quebra natural em 2 linhas, como o projeto espanhol já fazia
            linhas = _LAYOUT_TITULO.lines(body.split(" "), False) if hasattr(_LAYOUT_TITULO, "lines") else [body]
            body = LINE_BREAK.join(linhas)
            report["titulos_quebrados"] = report.get("titulos_quebrados", 0) + 1
        if b.type != 100:
            b.text = body
            continue
        speaker = None
        if spk_jp:
            speaker = names.get(spk_jp)
            if speaker is None:
                report["nome_sem_traducao"].add(spk_jp)
                speaker = spk_jp
        boxes = layout(body, speaker is not None)
        for k, lines in enumerate(boxes):
            for ln in lines:
                report["linha_max"] = max(report["linha_max"], width(ln, speaker is not None))
        texts = [osc.join_speaker(speaker, LINE_BREAK.join(lines)) for lines in boxes]
        b.text = texts[0]
        for t in texts[1:]:
            new_blocks.append(osc.new_dialogue_block(t))
            report["caixas_extras"] += 1
        report["unidades_pt"] += 1
    o.blocks = new_blocks
    return osc.build_obj(o)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--disco", default="1")
    ap.add_argument("--cenas", nargs="*", help="padrão: todas com arquivo de tradução")
    ap.add_argument("--saida", help="ISO de saída (sem isso, grava só RES.DAT/first.dat)")
    ap.add_argument("--dir-saida", default=str(ROOT / "build" / "saida"))
    ap.add_argument("--envpsp", action="store_true", default=True,
                    help="(padrão) reconstrói envpsp.dat (estrutura JP + traducao/discoN/sistema/envpsp.tsv)")
    ap.add_argument("--sem-envpsp", dest="envpsp", action="store_false",
                    help="mantém o envpsp.dat da ISO EN (interface em inglês)")
    ap.add_argument("--recompactar-todas", type=int, metavar="N",
                    help="(teste) re-gzipa todas as outras cenas com nível N")
    ap.add_argument("--largura", type=int, metavar="N",
                    help="(SÓ TESTE) largura máxima de linha em unidades (padrão MAX_WIDTH)")
    ap.add_argument("--sem-imagens", dest="imagens", action="store_false", default=True,
                    help="não troca as imagens com texto (balões de réplica etc.) pelas versões PT")
    ap.add_argument("--sem-videos", dest="videos", action="store_false", default=True,
                    help="mantém os vídeos OIP_GEB01/02 da ISO EN (sem legenda PT)")
    ap.add_argument("--regerar-videos", action="store_true",
                    help="recodifica os vídeos em vez de usar build/video_aprovado/ (muda os bytes)")
    ap.add_argument("--base-jp", action="store_true",
                    help="constrói sobre a ISO japonesa, com EBOOT e fonte próprios, sem arquivos do patch inglês")
    ap.add_argument("--inspecao", metavar="CENA",
                    help="(SÓ TESTE) copia o OBJ de CENA para o lugar de AKYO_0000A: 'Initial start' "
                         "começa direto nessa cena (ISO de inspeção visual; nunca usar no patch)")
    a = ap.parse_args()
    if a.largura:
        global _LAYOUT
        _LAYOUT = quebra.Layout(width, a.largura)
        print(f"LARGURA DE TESTE: {a.largura} unidades")
    t0 = time.time()
    ext = ROOT / "build" / "extraido"
    rd_jp = osc.ResDat.load(ext / f"disco{a.disco}_jp" / "RES.DAT")
    if a.base_jp:
        global SEM_INGLES
        SEM_INGLES = True
        rd_en = rd_jp
        first_en = (ext / f"disco{a.disco}_jp" / "first.dat").read_bytes()
    else:
        rd_en = osc.ResDat.load(ext / f"disco{a.disco}_en" / "RES.DAT")
        first_en = (ext / f"disco{a.disco}_en" / "first.dat").read_bytes()
    names = load_names()
    cdir = ROOT / "traducao" / f"disco{a.disco}" / "cenas"
    files = {p.stem: p for p in cdir.glob("*.txt")}
    scenes = a.cenas or [n for n, p in files.items() if any(e.pt for e in tradfile.parse(p)[1])]

    new_objs, reports = {}, {}
    for n in scenes:
        rep = dict(unidades_pt=0, caixas_extras=0, fallback_en=0, fallback_jp=0,
                   linha_max=0, sem_unidade=[], nome_sem_traducao=set())
        _s, entries = tradfile.parse(files[n])
        new_objs[n] = build_scene(rd_jp.obj(n), entries, names, rep)
        rep["nome_sem_traducao"] = sorted(rep["nome_sem_traducao"])
        reports[n] = rep
        print(f"{n}: {rep['unidades_pt']} unidades PT, {rep['caixas_extras']} caixas extras, "
              f"fallback EN={rep['fallback_en']} JP={rep['fallback_jp']}, linha mais larga={rep['linha_max']}px")

    if a.inspecao:
        alvo = new_objs.get(a.inspecao) or rd_en.obj(a.inspecao)
        new_objs["AKYO_0000A"] = alvo
        print(f"INSPEÇÃO: AKYO_0000A <- {a.inspecao} (ISO só para teste)")

    extra_gz = {}
    if a.recompactar_todas is not None:
        for n in rd_en.scene_names():
            if n not in new_objs:
                extra_gz[n] = gzip.compress(rd_en.obj(n), compresslevel=a.recompactar_todas, mtime=0)
    new_gz = {n: gzip.compress(ob, compresslevel=9, mtime=0) for n, ob in new_objs.items()}
    new_gz.update(extra_gz)
    new_res = rd_en.rebuild(new_obj_gz=new_gz)
    if a.imagens:
        import imagens_pt  # Pillow/numpy: importado só aqui (os roteiros do PPSSPP importam construir sem Pillow)
        new_res, img_rep = imagens_pt.aplicar(new_res, rd_jp.data)
        print(f"imagens PT: {img_rep}")
    # fluxograma (Extras): map.dat JP com as strings em PT (o da ISO EN está em inglês)
    import fluxograma
    mapa_pt, flux_rep = fluxograma.construir(rd_jp.data, a.disco)
    _t = []
    import album
    album_pt, alb_rep = album.construir(rd_jp.data, a.disco)
    new_res = imagens_pt._trocar(new_res, {"map.dat": mapa_pt, "AlbumList.txt": album_pt}, "", _t) if a.imagens else new_res
    print(f"álbum: {alb_rep["trocados"]}/{alb_rep["titulos"]} títulos PT (cp932 + acentos via EBOOT); JP divergente={alb_rep['jp_divergente'][:3]}")
    print(f"fluxograma: {flux_rep['strings_trocadas']} strings PT, sem PT={flux_rep['sem_pt'][:5]}, "
          f"tamanho {flux_rep['tamanho']}, entradas trocadas={_t}")
    new_first = seekmap.update_for(new_res, first_en)

    # verificação: relê tudo
    chk = osc.ResDat(new_res)
    for n, ob in new_objs.items():
        assert chk.obj(n) == ob, n
    for n in rd_en.scene_names():
        if n not in new_objs:
            assert chk.obj(n) == rd_en.obj(n), n
    print(f"RES.DAT: {len(rd_en.data):,} -> {len(new_res):,} bytes; first.dat "
          f"{'atualizado' if new_first != first_en else 'inalterado'} ({time.time() - t0:.1f}s)")

    out = Path(a.dir_saida)
    out.mkdir(parents=True, exist_ok=True)
    (out / "RES.DAT").write_bytes(new_res)
    (out / "first.dat").write_bytes(new_first)
    (out / "relatorio_construcao.json").write_text(json.dumps(reports, ensure_ascii=False, indent=1), encoding="utf-8")

    replacements = {RES_PATH: new_res, FIRST_PATH: new_first}
    if a.envpsp:
        env_bytes, env_rep = envpsp.construir(ext / f"disco{a.disco}_jp" / "envpsp.dat",
                                              ext / f"disco{a.disco}_en" / "envpsp.dat",
                                              ROOT / "traducao" / f"disco{a.disco}" / "sistema" / "envpsp.tsv",
                                              fallback_en=not a.base_jp)
        # sanidade: a releitura tem a mesma estrutura de tokens do JP
        _h, t_new = envpsp.tokenize(env_bytes)
        print(f"envpsp.dat: {len(env_bytes):,} bytes; strings PT={env_rep['pt']} EN={env_rep['en']} "
              f"JP={env_rep['jp']}; JP divergente={env_rep['jp_divergente'][:5]}; números={env_rep['numeros']}")
        (out / "envpsp.dat").write_bytes(env_bytes)
        replacements[ENVPSP_PATH] = env_bytes
    # EBOOT PT (tabela SJIS→Unicode com letras acentuadas para o Álbum; ver eboot_pt.py)
    import eboot_pt
    eboot, eb_rep = eboot_pt.construir(base_jp=a.base_jp)
    replacements["/PSP_GAME/SYSDIR/EBOOT.BIN"] = eboot
    print(f"EBOOT PT: {eb_rep}")
    if a.videos:
        import video_pmf
        for v in ("OIP_GEB01", "OIP_GEB02"):
            # o x264 não repete os mesmos bytes: reutiliza o vídeo aprovado para a reconstrução sair idêntica
            pv = VIDEOS_APROVADOS / f"{v}.pmf"
            if a.regerar_videos or not pv.exists():
                pv = video_pmf.gerar(v)
            replacements[f"/PSP_GAME/USRDIR/{v}.pmf"] = pv.read_bytes()
    if a.saida:
        src = ISOS[a.disco]["jp" if a.base_jp else "en"]
        rep = iso_grow.write_files_into_iso(str(src), replacements, a.saida)
        if a.base_jp:
            import iso_fonte
            fonte = (ROOT / "build" / "fonte" / "FONTE.PGF").read_bytes()
            print(f"fonte PT: {len(fonte):,} bytes no setor {iso_fonte.instalar(a.saida, fonte)}")
            assert isofs.read_file(a.saida, iso_fonte.NOME) == fonte
        for path, data in replacements.items():
            assert isofs.read_file(a.saida, path) == data, path
        # releitura
        assert isofs.read_file(a.saida, RES_PATH) == new_res
        assert isofs.read_file(a.saida, FIRST_PATH) == new_first
        info = isofs.volume_info(a.saida)
        print(f"ISO: {a.saida} ({info['file_size']:,} bytes) movidos={rep['moved']} "
              f"cresceu={rep['image_grew_by']} — RES.DAT e first.dat relidos e conferidos")


if __name__ == "__main__":
    main()
