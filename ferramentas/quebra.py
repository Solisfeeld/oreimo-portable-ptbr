"""Divisão inteligente de falas em caixas (≤3 linhas) e linhas (largura real da fonte).

Problema que resolve: o algoritmo antigo enchia as linhas gulosamente e, quando uma
frase passava de 3 linhas, jogava o excedente numa caixa de continuação — gerando
caixas como "hora." (AKYO_0000A). Agora:

1. Número de caixas = o mínimo possível (nunca se corta conteúdo).
2. Onde dividir as caixas é escolhido por otimização (programação dinâmica) sobre
   todas as fronteiras de palavra, com custo que combina:
   * tipo de fronteira: fim de frase (. ! ? … ♪) < travessão < ; : < vírgula <
     antes de conjunção < meio de oração;
   * proibido na prática: terminar caixa em preposição/artigo/contração/clítico
     ("na", "de", "por", "que"...) ou dentro de expressão fixa ("na mesma hora",
     "de qualquer maneira", "por causa de"...);
   * caixa curta: 1–2 palavras ou menos de meia linha custa muito;
   * equilíbrio: caixas com quantidade de texto parecida.
3. Dentro de cada caixa, as linhas são escolhidas também por DP: o mesmo número de
   linhas da quebra gulosa, mas evitando última linha com uma palavra só e linha
   terminando em preposição/artigo.
Larguras: tabela real de avanço dos glifos (oreimo_core.fontmap), como o jogo desenha.
Marcadores manuais continuam valendo: '¶' força nova caixa, '＿' força nova linha.
"""
from __future__ import annotations

import re
from functools import lru_cache

LINES_PER_BOX = 3
CAUDA_CURTA = 76      # unidades: última linha menor que isto, sem pontuação antes, é sobra
LINHA_CURTA = 260     # unidades: linha do meio menor que isto, sem pontuação no fim, é minguada

# palavras que não podem terminar caixa/linha (exigem complemento à direita)
FRACAS = set("""
a o as os um uma uns umas de da do das dos em na no nas nos num numa nuns numas
dum duma por pela pelo pelas pelos para pra pro pras pros com sem sob sobre até
entre ao aos à às que e ou nem se me te lhe lhes vos meu minha meus minhas seu sua
seus suas teu tua teus tuas nosso nossa nossos nossas este esta estes estas esse
essa esses essas aquele aquela aqueles aquelas tão muito mais menos bem mal cada
qualquer quaisquer outro outra outros outras todo toda todos todas mesmo mesma
não já nunca
""".split())
CONJ = set("e mas que porque pois quando se ou então enquanto embora como onde aí "
           "senão porém contudo nem logo".split())
# expressões que não devem ser separadas (minúsculas, sem pontuação)
EXPRESSOES = [
    "na mesma hora", "de qualquer maneira", "de qualquer jeito", "de qualquer forma",
    "por causa de", "por causa da", "por causa do", "de repente", "de novo",
    "às vezes", "por favor", "pelo menos", "de jeito nenhum", "de jeito algum",
    "tudo bem", "por enquanto", "de propósito", "de verdade", "de vez", "de uma vez",
    "a gente", "o tempo todo", "o quanto antes", "em vez de", "ao invés de",
    "apesar de", "antes de", "depois de", "além de", "perto de", "longe de",
    "dentro de", "fora de", "em cima de", "embaixo de", "atrás de", "na frente de",
    "por isso", "por aí", "por acaso", "à toa", "a sós", "aos poucos", "de vez em quando",
    "de manhã", "de tarde", "de noite", "à noite", "hoje em dia", "ainda por cima",
    "nem que", "já que", "para que", "pra que", "assim que", "logo que", "desde que",
    "mesmo assim", "sei lá", "pois é", "é claro", "com certeza", "sem querer",
    "não é", "né", "de cara", "na hora", "de longe", "de perto", "um monte de",
    "um pouco", "um pouquinho", "cada vez mais", "o que", "do que", "o mais",
    "meruru regional", "conversa a dois", "viagem escolar", "conselho de vida",
    "irmãzinha tentáculo", "olhos de peixe morto", "rabo de olho", "de si mesma", "de si mesmo",
]
_EXP = [tuple(e.split()) for e in EXPRESSOES if " " in e]
_FIM_FRASE = re.compile(r'(\.\.\.|[.!?…♪])[」』"\')\]]*$')
_PONT_MEDIA = re.compile(r'[;:][」』"\')\]]*$')
_VIRG = re.compile(r',[」』"\')\]]*$')
_TRAV = re.compile(r'—[」』"\')\]]*$')
_LIMPA = re.compile(r"[^\wà-úâêôãõçÀ-ÚÂÊÔÃÕÇ-]")


def _base(w: str) -> str:
    return _LIMPA.sub("", w).lower()


def _expressao_cruza(words: list[str], k: int) -> bool:
    """Fronteira depois de words[k] cai dentro de uma expressão fixa?"""
    low = [_base(w) for w in words]
    for exp in _EXP:
        n = len(exp)
        for s in range(max(0, k - n + 2), k + 1):
            if s + n <= len(low) and tuple(low[s:s + n]) == exp and s <= k < s + n - 1:
                # só vale se não houver pontuação dentro da expressão
                if not any(re.search(r"[,.;:!?…—]", words[t]) for t in range(s, s + n - 1)):
                    return True
    return False


def _aspas(words: list[str], k: int) -> float:
    """Penalidade de quebrar logo depois de words[k] DENTRO de um trecho entre aspas
    ("God Eater Burst", "Garotas Otaku, Juntem-se!", a "turma divertida"): títulos e
    expressões citadas curtas não se partem; citações longas podem, com custo moderado."""
    abre = None
    for t in range(k + 1):
        q = words[t].count('"') + words[t].count('“') + words[t].count('”')
        if q % 2 == 1:
            abre = None if abre is not None else t
    if abre is None:
        return 0.0
    fecha = next((t for t in range(k + 1, len(words))
                  if (words[t].count('"') + words[t].count('”') + words[t].count('“')) % 2 == 1), None)
    if fecha is None:
        return 0.0
    return 50.0 if fecha - abre + 1 <= 4 else 12.0


def custo_fronteira(words: list[str], k: int) -> float:
    """Custo de quebrar (caixa ou linha) logo depois de words[k]."""
    w = words[k]
    nxt = words[k + 1] if k + 1 < len(words) else ""
    if _FIM_FRASE.search(w):
        c = 0.0
    elif _TRAV.search(w):
        c = 1.0
    elif _PONT_MEDIA.search(w):
        c = 2.0
    elif _VIRG.search(w):
        c = 4.0
    elif _base(nxt) in CONJ:
        c = 8.0
    else:
        c = 16.0
    if _base(w) in FRACAS and not re.search(r"[,.;:!?…—]", w):
        c += 45.0
    if _expressao_cruza(words, k):
        c += 60.0
    c += _aspas(words, k)
    # nomes compostos: "Sugawara no Michizane", "Abe no Seimei", "Kousaka Kirino"
    cap = lambda x: x[:1].isupper()
    if cap(w) and not re.search(r"[,.;:!?…—]", w):
        if cap(nxt) or (_base(nxt) in ("no", "de", "da", "do") and k + 2 < len(words)
                        and cap(words[k + 2])):
            c += 40.0
    if _base(w) in ("no", "de") and k > 0 and cap(words[k - 1]) and cap(nxt):
        c += 40.0
    return c


class Layout:
    def __init__(self, width_fn, maxw: int, maxw_uma: int | None = None):
        self.width_fn = width_fn
        self.maxw = maxw
        self.maxw_uma = maxw_uma or maxw     # limite da área segura: fala inteira em uma linha, ou para evitar artigo no fim da linha
        self.cauda = False

    # ---------- linhas ----------
    def _w(self, words, speech):
        return self.width_fn(" ".join(words), speech)

    def greedy_lines(self, words, speech):
        lines, cur = [], []
        for w in words:
            if cur and self._w(cur + [w], speech) > self.maxw:
                lines.append(cur)
                cur = [w]
            else:
                cur = cur + [w]
        if cur or not lines:
            lines.append(cur)
        return lines

    def lines(self, words: list[str], speech: bool, max_lines: int | None = None) -> list[str]:
        """Quebra em linhas APROVEITANDO A LARGURA (pedido do autor, 17/10): cada linha leva o
        maior trecho natural que couber; não se equilibram linhas nem se prioriza pontuação
        quando ainda há espaço. Custo por linha não final = espaço sobrando (linear, ≈ quebra
        gulosa) + penalidades só para quebras ruins: linha terminando em preposição/artigo/
        contração, expressão fixa ou nome composto partido, palavra solta abrindo frase nova
        no fim da linha, última linha com uma palavra só. Usa o nº mínimo de linhas; uma linha
        a mais só se o mínimo for impossível."""
        if not words:
            return [""]
        if self._w(words, speech) <= self.maxw_uma:        # 31/10: cabe inteira na área segura: uma linha só
            return [" ".join(words)]
        if any(self.width_fn(w, speech) > self.maxw for w in words):
            return [" ".join(l) for l in self.greedy_lines(words, speech)]  # palavra gigante
        linhas = self._lines_dp(words, speech, max_lines)
        if self.maxw_uma > self.maxw and self._fraca_no_fim(linhas):
            # 31/10: artigo/preposição no fim da linha por falta de 1–4 unidades na seguinte: usa a área segura inteira
            limite, self.maxw = self.maxw, self.maxw_uma
            try:
                nova = self._lines_dp(words, speech, max_lines)
            finally:
                self.maxw = limite
            if len(nova) <= len(linhas) and self._fraca_no_fim(nova) < self._fraca_no_fim(linhas):
                return nova
        return linhas

    @staticmethod
    def _fraca_no_fim(linhas):
        return sum(_base(l.split()[-1]) in FRACAS and not re.search(r"[,.;:!?…—]", l.split()[-1]) for l in linhas[:-1])

    def _lines_dp(self, words, speech, max_lines):
        k = len(self.greedy_lines(words, speech))
        if k == 1:
            return [" ".join(words)]
        n = len(words)
        INF = float("inf")

        def ruim(j):
            """penalidade de quebrar a linha logo depois de words[j-1]"""
            w = words[j - 1]
            c = 0.0
            if _base(w) in FRACAS and not re.search(r"[,.;:!?…—]", w):
                c += 60.0
            if _expressao_cruza(words, j - 1):
                c += 60.0
            c += _aspas(words, j - 1)                      # "God | Eater Burst"
            cap = lambda x: x[:1].isupper()
            nxt = words[j] if j < n else ""
            if cap(w) and not re.search(r"[,.;:!?…—]", w) and j >= 2 and \
                    not _FIM_FRASE.search(words[j - 2]) and \
                    (cap(nxt) or (_base(nxt) in ("no", "de", "da", "do") and j + 1 < n and cap(words[j + 1]))):
                c += 60.0                                  # "Kousaka | Kirino", "Abe no | Seimei"
            if j >= 2 and _FIM_FRASE.search(words[j - 2]) and not _FIM_FRASE.search(w):
                c += 30.0                                  # "...Kirino. É | uma estudante"
            if _base(w) in CONJ and not re.search(r"[,.;:!?…—]", w):
                c += 6.0                                   # "...meia-boca, mas | a": leve
            if _FIM_FRASE.search(w):
                c -= 1.0                                   # desempate leve, nunca decisivo
            if j < n and self._w(words[j:], speech) < CAUDA_CURTA and not re.search(r"[,.;:!?…—]", w):
                c += 40.0                                  # 31/10: última linha só com a sobra de 1–2 palavrinhas
            elif self.cauda and j < n and self._w(words[j:], speech) < 320:
                # ao corrigir a sobra, recua até uma pausa natural: fim de frase, depois vírgula
                c -= 70.0 if _FIM_FRASE.search(w) else (40.0 if w.endswith(",") else 0.0)
            return c

        # só há sobra a corrigir se a quebra gulosa deixa uma última linha curta sem pontuação antes
        g = self.greedy_lines(words, speech)
        self.cauda = self._w(g[-1], speech) < CAUDA_CURTA and not re.search(r"[,.;:!?…—]", g[-2][-1] if len(g) > 1 else "")

        @lru_cache(maxsize=None)
        def best(i, lines_left):
            """menor custo para words[i:] em exatamente lines_left linhas -> (custo, cortes)"""
            if lines_left == 1:
                wd = self._w(words[i:], speech)
                if wd > self.maxw:
                    return INF, ()
                return (90.0 if (n - i == 1 and n > 2) else 0.0), ()
            res = (INF, ())
            for j in range(i + 1, n - lines_left + 2):
                wd = self._w(words[i:j], speech)
                if wd > self.maxw:
                    break
                c = (self.maxw - wd) / 10.0 * lines_left + ruim(j)   # linhas de cima pesam mais: enche de cima para baixo
                if lines_left < k and wd < LINHA_CURTA and not re.search(r"[,.;:!?…—]", words[j - 1]):
                    c += 30.0                              # 31/10: linha do meio minguada
                sub = best(j, lines_left - 1)
                if c + sub[0] < res[0]:
                    res = (c + sub[0], (j,) + sub[1])
            return res

        cost, cuts = best(0, k)
        if cost == INF and max_lines and k + 1 <= max_lines:
            cost, cuts = best(0, k + 1)
        if cost == INF:
            return [" ".join(l) for l in self.greedy_lines(words, speech)]
        out, prev = [], 0
        for c in cuts + (n,):
            out.append(" ".join(words[prev:c]))
            prev = c
        return out

    def n_lines(self, words, speech):
        return len(self.greedy_lines(words, speech))

    # ---------- caixas ----------
    def boxes(self, words: list[str], speech: bool) -> list[list[str]]:
        """Divide as palavras em caixas de ≤3 linhas (nº mínimo de caixas)."""
        n = len(words)
        if n == 0:
            return [[""]]
        fits = {}

        def fit(i, j):
            if (i, j) not in fits:
                fits[(i, j)] = self.n_lines(words[i:j], speech) <= LINES_PER_BOX
            return fits[(i, j)]

        if fit(0, n):
            return [self.lines(words, speech, LINES_PER_BOX)]
        # nº mínimo de caixas (DP de viabilidade)
        INF = float("inf")
        minb = [INF] * (n + 1)
        minb[0] = 0
        for j in range(1, n + 1):
            for i in range(j - 1, -1, -1):
                if not fit(i, j):
                    break
                minb[j] = min(minb[j], minb[i] + 1)
        nbox = minb[n]
        total = self._w(words, speech)
        avg = total / nbox

        def seg_cost(i, j):
            wd = self._w(words[i:j], speech)
            c = ((wd - avg) / self.maxw) ** 2 * 3
            nw = j - i
            if nw <= 2:
                c += 400.0
            elif wd < 0.5 * self.maxw:
                c += 150.0
            elif wd < 0.75 * self.maxw:
                c += 10.0
            return c

        # best[b][j]: melhor custo para words[:j] em b caixas
        best = [[INF] * (n + 1) for _ in range(nbox + 1)]
        back = [[-1] * (n + 1) for _ in range(nbox + 1)]
        best[0][0] = 0.0
        for b in range(1, nbox + 1):
            for j in range(1, n + 1):
                for i in range(j - 1, -1, -1):
                    if not fit(i, j):
                        break
                    if best[b - 1][i] == INF:
                        continue
                    c = best[b - 1][i] + seg_cost(i, j)
                    if j < n:
                        c += custo_fronteira(words, j - 1) * 6
                    if c < best[b][j]:
                        best[b][j] = c
                        back[b][j] = i
        cuts, j = [], n
        for b in range(nbox, 0, -1):
            i = back[b][j]
            cuts.append((i, j))
            j = i
        cuts.reverse()
        return [self.lines(words[i:j], speech, LINES_PER_BOX) for i, j in cuts]

    def layout(self, text: str, speech: bool) -> list[list[str]]:
        """Texto PT -> lista de caixas (cada uma, lista de até 3 linhas)."""
        out = []
        for part in text.split("¶"):
            part = part.strip()
            if "＿" in part:   # quebras manuais: respeita; só re-quebra o que estourar
                lines = []
                for seg in part.split("＿"):
                    lines += self.lines(seg.split(), speech)
                out += [lines[i:i + LINES_PER_BOX] for i in range(0, len(lines), LINES_PER_BOX)]
                continue
            out += self.boxes(part.split(), speech)
        return out


# ---------- auditoria ----------
def auditar(boxes: list[list[str]], greedy_n_lines: int, maxw_fn=None) -> list[str]:
    """Sinais de divisão ruim numa unidade já diagramada."""
    sinais = []
    if len(boxes) > 1:
        for bi, box in enumerate(boxes):
            words = " ".join(box).split()
            if bi > 0 and len(words) <= 2:
                sinais.append(f"CURTA(caixa {bi + 1}: '{' '.join(words)}')")
            if bi < len(boxes) - 1:
                last = words[-1] if words else ""
                if _base(last) in FRACAS and not re.search(r"[,.;:!?…—]", last):
                    sinais.append(f"PREP(caixa {bi + 1} termina em '{last}')")
                elif not (_FIM_FRASE.search(last) or _TRAV.search(last) or _PONT_MEDIA.search(last)
                          or _VIRG.search(last)):
                    sinais.append(f"MEIO(caixa {bi + 1} termina em '{last}')")
                allw = " ".join(" ".join(b) for b in boxes).split()
                k = sum(len(" ".join(b).split()) for b in boxes[:bi + 1]) - 1
                if _expressao_cruza(allw, k):
                    sinais.append(f"EXPR(caixa {bi + 1})")
        # sobra pequena: com a quebra gulosa, a última caixa teria só 1 linha curta
        if greedy_n_lines == LINES_PER_BOX * (len(boxes) - 1) + 1:
            sinais.append("REFORMULAR?(excede por 1 linha)")
    for bi, box in enumerate(boxes):
        if len(box) > 1 and len(box[-1].split()) == 1 and len(" ".join(box).split()) > 3:
            sinais.append(f"ORFA(caixa {bi + 1}: '{box[-1]}')")
    return sinais
