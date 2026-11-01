"""Troca imagens (GIM) dentro do RES.DAT pelas versões PT-BR — usado por construir.py.

Fontes dos PNGs PT:
  * balões de réplica da Conversa a Dois  -> ferramentas/tukkomi.py      (build/imagens/tukkomi/pt/)
  * interface, cut-ins, minigame, aviso   -> ferramentas/imagens_texto.py (build/imagens/pt_ui/)
Cada imagem substitui TODAS as entradas com o mesmo nome em qualquer nível do RES.DAT (o jogo tem
cópias globais e por cena — p.ex. CG200A em 34 cenas, CUT_PCUT03 em 60, cada TK* em 2 lugares).
Codificação no formato do ORIGINAL JAPONÊS (P8, 256 cores: mesma memória de textura do jogo; o EN
gravou parte em RGBA8888), regravada com gzip se a entrada original era gzip. Só as GPDAs que mudam
são reconstruídas; o resto é copiado byte a byte.
Nome de PNG "pasta@NOME.gim.png" = troca só as entradas NOME.gim sob a pasta raiz `pasta` (há nomes repetidos com
imagens diferentes: image_main/ORN21.gim é o ícone O.R.E. 64×48, image_ornament/ORN21.gim outro ícone, 128×128).
"""
import gzip
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ferramentas"))
from oreimo_core import gpda  # noqa: E402
from oreimo_core.scene_images import encode_to_gim, peek_format  # noqa: E402

DIR_TK = ROOT / "build" / "imagens" / "tukkomi" / "pt"
DIR_UI = ROOT / "build" / "imagens" / "pt_ui"


def _pngs():
    """{nome da entrada no RES.DAT: caminho do PNG PT}"""
    # gera com o venv do projeto (OpenCV para o inpaint) — o mesmo ambiente das comparações revisadas
    import subprocess
    py = ROOT / "build" / "venv" / "bin" / "python"
    if py.exists():
        for script, args in (("tukkomi.py", ["gerar"]), ("imagens_texto.py", [])):
            subprocess.run([str(py), str(ROOT / "ferramentas" / script)] + args, check=True)
    else:
        print("AVISO: build/venv ausente — imagens geradas sem OpenCV (reconstrução de fundo inferior)")
        import tukkomi
        import imagens_texto
        tukkomi.gerar()
        imagens_texto.gerar()
    out = {p.stem + ".gim": p for p in sorted(DIR_TK.glob("*.png"))}
    out.update({p.name[:-4].replace("@", "/"): p for p in sorted(DIR_UI.glob("*.png"))})
    return out


def _chave(caminho_completo: str, novos) -> str | None:
    """Chave de `novos` que vale para a entrada: "pasta_raiz/nome" (qualificada) ou só o nome."""
    partes = caminho_completo.split("/")
    q = f"{partes[0]}/{partes[-1]}"
    if q in novos:
        return q
    return partes[-1] if partes[-1] in novos else None


def _formatos(res_jp: bytes, nomes: set) -> dict:
    fmt = {}

    def walk(blob, caminho):
        for x in gpda.parse_gpda(blob):
            d = blob[x.data_offset:x.data_offset + x.data_size]
            n = x.name.strip()
            c = f"{caminho}/{n}" if caminho else n
            if d[:4] == b"GPDA":
                walk(d, c)
            else:
                k = _chave(c, nomes)
                if k and k not in fmt:
                    fmt[k] = peek_format(gzip.decompress(d) if d[:2] == b"\x1f\x8b" else d)
    walk(res_jp, "")
    return fmt


def _trocar(blob: bytes, novos: dict, caminho: str, rep: list) -> bytes:
    itens, mudou = [], False
    for x in gpda.parse_gpda(blob):
        d = blob[x.data_offset:x.data_offset + x.data_size]
        nome = x.name.strip()
        c = f"{caminho}/{nome}" if caminho else nome
        if d[:4] == b"GPDA":
            nd = _trocar(d, novos, c, rep)
        elif _chave(c, novos):
            k = _chave(c, novos)
            nd = gzip.compress(novos[k], 9, mtime=0) if d[:2] == b"\x1f\x8b" else novos[k]
            rep.append(c)
        else:
            nd = d
        mudou |= nd is not d
        itens.append((x.name, nd))
    return gpda.build_gpda(itens) if mudou else blob


def aplicar(res: bytes, res_jp: bytes):
    """-> (RES.DAT novo, relatório)"""
    pngs = _pngs()
    fmt = _formatos(res_jp, set(pngs))
    faltam = sorted(set(pngs) - set(fmt))
    if faltam:
        raise KeyError(f"imagens PT sem original no RES.DAT JP: {faltam}")
    novos, quant = {}, 0
    for nome, p in pngs.items():
        gim, w = encode_to_gim(p.read_bytes(), fmt[nome])
        quant += bool(w)
        novos[nome] = gim
    trocadas = []
    novo = _trocar(res, novos, "", trocadas)
    usadas = {_chave(c, novos) for c in trocadas}
    sem_uso = sorted(set(novos) - usadas)
    return novo, {"imagens_pt": len(novos), "entradas_trocadas": len(trocadas),
                  "quantizadas_256": quant, "nao_encontradas_no_EN": sem_uso}
