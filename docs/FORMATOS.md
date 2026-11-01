# Formatos do jogo — documentação técnica

Notas de engenharia reversa de *Ore no Imouto ga Konna ni Kawaii Wake ga Nai Portable ga Tsuzuku Wake ga Nai* (PSP, Disco 1).
Foram verificadas em cópias locais do jogo; itens não verificados estão marcados como **[não verificado]**. Este documento
descreve estruturas e não inclui dados do jogo. Caminhos como `traducao/` e `build/` são do ambiente de trabalho local e
não existem neste repositório.

## 1. ISOs

| ISO | MD5 | tamanho | serial |
|---|---|---|---|
| Ore no Imouto (Japan) Disc 1.iso | 0bf0132e8a5a6efdcffde355a35a3ff8 | 1.493.139.456 | NPJH-50568 |
| Ore no Imouto (English v1) Disc 1.iso | 0400f6093f9edfc7a0b6e9f54357da08 | 1.405.437.952 | NPJH-50568 |
| Ore no Imouto (Japan) Disc 2.iso | 1b774694d0a93cabf79296c0ddf28a91 | 1.498.316.800 | NPJH-50569 |
| Ore no Imouto (English v1) Disc 2.iso | 03bdd2cd522db608a4a49c5d828213b5 | 1.423.763.456 | NPJH-50569 |

ISO9660 simples, sem Joliet/Rock Ridge. A ISO inglesa foi remasterizada
(arquivos contíguos, sem lacunas) e tem um arquivo a mais: `/font.pgf`.

### Disco 1 — arquivos que o patch inglês alterou

| arquivo | JP | EN | observação |
|---|---|---|---|
| PSP_GAME/SYSDIR/EBOOT.BIN | 3.524.608 | 3.524.608 | conteúdo diferente (ambos com cabeçalho `~PSP`; EN modificado) |
| PSP_GAME/INSDIR/RES.DAT | 203.726.848 | 205.791.232 | scripts traduzidos + imagens (image_main, image_title, main_resource) |
| PSP_GAME/USRDIR/first.dat | 1.742.848 | 1.730.560 | seekmap (+ entradas `text`, `script` etc. — **a investigar**) |
| PSP_GAME/USRDIR/envpsp.dat | 104.164 | 148.734 | provável texto de sistema/menus — **a investigar** |
| PSP_GAME/USRDIR/OIP_GEB01.pmf / GEB02.pmf | — | — | vídeos diferentes (legendas/créditos?) **[não verificado]** |
| PIC1.PNG, INSDIR/ICON0.PNG | — | — | arte do XMB |
| /font.pgf (só EN) | — | 1.476.536 | FTT-NewRodin Pro DB |

Iguais: UMD_DATA.BIN, PARAM.SFO, BOOT.BIN, OPNSSMP.BIN, libfont.prx, psmf.prx, áudio (.awb).

Final do disco: `/PSP_GAME/INSDIR/DUMMY.DAT` (64.356.352 bytes, só zeros) —
enchimento que o `iso_grow` reaproveita para acomodar arquivos maiores.

## 2. GPDA (contêiner de RES.DAT e first.dat)

```
0x00 "GPDA"   0x04 u32 tamanho_total   0x08 u32 0   0x0C u32 n_entradas
0x10 n × {u32 offset_rel, u32 0, u32 tamanho, u32 offset_nome}
tabela de nomes: u32 len + bytes (ASCII/cp932)
```
* dados alinhados em 0x800 a partir do início do GPDA;
* **o tamanho total é sempre múltiplo de 0x800** (zeros no fim) — regra
  descoberta neste projeto; o construtor espanhol não preenchia;
* existem GPDAs vazios (0 entradas);
* nomes podem ter espaços no fim → usar `strip()`.

Árvore de RES.DAT: `image_bg, image_block, image_charactor, image_cutin,
image_event, image_main, image_ornament, image_title, image_tukkomi, live2d,
main_resource, omake, script`.
Scripts: `script/<CENA>/000/000script<CENA>.obj.gz` (gzip). 300 cenas no Disco 1
(299 + `AASTARTPOINT`, cena de depuração).

## 3. Seekmap (first.dat → seekmap → res.map.gz)

Texto cp932, CRLF, uma linha por entrada de RES.DAT com **offset absoluto**,
tamanho e um hash opaco (copiado). O jogo procura dados por esse índice;
se RES.DAT muda de layout, o seekmap tem de ser regenerado
(`oreimo_core/seekmap.py`). Nome da raiz: `res.dat` (JP) / `resource.dat` (EN)
— preservado. Regenerar a partir do RES.DAT original reproduz o seekmap
byte a byte (JP e EN).

## 4. Script .obj

```
0x00 u32 n_blocos   0x04 u32 0x30 (tamanho do cabeçalho)   ... cabeçalho até 0x30
blocos em sequência: u32 blockLen | u16 tipo | campos   (blockLen % 16 == 0)
```
O motor avança `pos += blockLen`; ao mudar texto, recalcular blockLen.

### Blocos com texto

| tipo | uso | layout | preenchimento original |
|---|---|---|---|
| 100 | fala/narração | u16 tipo, u8 0, **u16 id_msg**, u16 FFFF, u32 n, UTF-16LE | round16(15+2n+4) |
| 700 | título da cena | u16 tipo, u32 n, UTF-16LE | round16(10+2n+6) |
| 302 | aviso ("…foi adicionado às opções") | u16 tipo, u32 n, UTF-16LE | round16(10+2n+2) |
| 104, 105, 103, 1600, 1700 | só em AASTARTPOINT (menu de depuração) | — | — |

* `id_msg` é igual no JP e no EN (âncora de alinhamento). 0xFFFF = sem id
  (403 falas JP; e todas as continuações inseridas pelo EN).
* Falas: `Nome「texto」`; narração: só o texto.
* As escolhas do jogador **não** estão nos OBJ (as 571 "opções" dos CSV antigos
  são todas da cena de depuração). Provavelmente imagens/`envpsp.dat` — Fase 4.

### Marcadores dentro do texto

| marcador | significado |
|---|---|
| `＿` (U+FF3F) | quebra de linha (o EBOOT inglês não quebra sozinho) |
| `《base：leitura》` | rubi (furigana) — 228 ocorrências no JP; o EN não usa |
| `【…】` | destaque (nomes de lugares/eventos) |

### Blocos que guardam índices de bloco (posição na lista)

Descoberto comparando JP×EN (o EN inseriu blocos e corrigiu estes campos):

| tipo | campo (offset no bloco) | significado |
|---|---|---|
| 702 | +6 u32 | destino de salto (índice do bloco) |
| 1301 | +14 u32 início, +18 u32 quantidade | janela (provavelmente reação/"tukkomi") |
| 1400 | +14 u32 destino COM réplica, +18 u32 destino SEM réplica | janela de "réplica" da Conversa a Dois; +22 u32 = prazo em ms (5000, 4000…) |

Exemplo: num bloco 1400, se o jogador dá a réplica dentro do prazo, a cena segue pelo destino COM réplica; senão, vai para o
destino SEM réplica. Pular blocos ali é legítimo.
O 407 (+10 u32 = 1000) aparece antes das falas da Conversa a Dois (avanço automático?).

O 703 **não** é índice de bloco (o EN não o alterou): é **salto para outra cena**,
+6 u32 = posição em `first.dat/text/scriptname.txt`. Grafo de cenas:
`python3 ferramentas/fluxo.py` → `traducao/disco1/fluxo_cenas.tsv` (300 cenas, 60 com ramificação). `oreimo_script.build_obj`
remapeia esses campos ao inserir/remover blocos; reversão testada byte a byte.

## 5. Diferenças estruturais JP × EN nos scripts (Disco 1)

* 255 cenas: idênticas fora o texto.
* 45 cenas: o EN dividiu falas longas em blocos de continuação (100 com id
  FFFF), às vezes movendo trechos para o fim do script com rótulos/saltos.
* **BKIR_0125A: o EN removeu ~36 falas.**
* Por isso o patch PT-BR usa **o OBJ japonês como estrutura** (completo) e
  aplica o PT-BR nele; o resto do disco vem da ISO inglesa.

## 6. Fonte e largura da caixa

* Larguras dos glifos em unidades da tabela de avanço da fonte. Latin-1 completo
  (ã õ ç â ê ô à á é í ó ú etc.). `… — “ ” ☆ ♪ 「」` têm largura 18 (largura cheia).
* Calibração com capturas do projeto espanhol: 1 unidade ≈ 0,75 px de tela
  (480×272); o texto começa em x≈64.
* Caixa de diálogo: cabem 512 unidades (linha termina em x≈448; o EN nunca passa
  de 513). Os 570 do projeto espanhol terminariam em x≈491, fora da tela.
* **Backlog (△) re-quebra cada linha por caractere** (no meio da palavra) quando ela passa de ~446–456 unidades. O EN tem
  17% das linhas acima de 450, ou seja, o patch inglês tem esse defeito no Backlog.
* Largura adotada: **480 unidades** por linha: termina em x≈424. Uma fala que caiba inteira vai até **484 unidades** (x≈425, igual ao máximo do JP): a primeira estrelinha da caixa fica em x≈426. O
  Histórico recebeu largura própria (§6c), então nada é re-quebrado. Falas em 2+ caixas: 50, todas divididas em fim de frase.
* 3 linhas por caixa. Excedente vai para blocos de continuação (id FFFF).
* Nas falas, o `「` conta na largura de cada linha (recuo das linhas seguintes).

### 6b. Histórico (Backlog): de onde vêm a escala e a largura (investigação de 19/10)

* **EBOOT**: o PPSSPP grava o EBOOT decifrado com `DumpFileTypes = 1` (bit EBOOT) na config isolada →
  `PSP/SYSTEM/DUMP/NPJH50568_EBOOT.BIN`. PRX relocável, texto em vaddr 0,
  offset de arquivo = vaddr + 0xC0; base em RAM **0x08804000**; seg1 em vaddr 0x281358). Desmontador:
  `ferramentas/mipsdis.py`. Diferenças EN × JP (407 bytes): 6× `ori a2/a3,zero,0x1D6` (470) → `0x500`
  (desliga a quebra automática da caixa de diálogo; o EN quebra à mão com ＿) e um gancho que carrega
  `disc0:/font.pgf`. Nada do Histórico foi alterado pelo EN.
* A rotina de layout `0x5AB8C → 0x5B4BC` recebe a largura (em unidades da fonte) e quebra por caractere
  quando `largura < x + glifo` (`0x5C3C0`). No Histórico a largura vem de uma variável global
  (`seg1 + 0x17B90`, RAM 0x08A9CEE8), preenchida na inicialização pelo leitor do envpsp (`0x1CFB78…`).
* **Config do texto do Histórico = envpsp tokens JP 4010–4022** (logo após "SECRET×2"):
  `68` x do texto · `30` · **`0.8` escala da fonte (4012)** · cor · `0` · `14` · `230` · **`470` largura de
  quebra (4017)** · `20 5 30 10 30`. Confirmado lendo a RAM na tela de título. A caixa de diálogo usa escala **0.75** (token 386; área 372 px).
* Consequência: o Histórico desenha ~8% maior (0.8 × 0.75) e corta por caractere acima de ~450–470
  unidades das nossas métricas. Os 470 de 4234–4237 e o 0.8 de 4129 são de outras áreas (rodapé/rótulos):
  experimentos reprovados.

### 6c. Histórico: medição real da largura de quebra (23/10)

* O motor do Histórico **re-quebra cada linha toda vez que o painel abre**, por caractere, comparando com a variável de
  largura (envpsp 4017 → `seg1+0x17B90`). Confirmado gravando valores na RAM e reabrindo.
* A medida do motor **não é** a soma da tabela de larguras (ceil do advance): é maior e depende dos glifos; sobra máxima
  observada: +4,3%. Por isso 490 ainda cortava. Largura do Histórico adotada: **520**.
* **Escala do texto: tem de ficar no valor original 0,8.** Qualquer outra escala testada (0,75 e 0,78) faz o PPSSPP cair para
  ~0,7% de velocidade ao rolar o Histórico para baixo (o jogo fica preso no painel); com 0,8 é normal (variantes C/D/E/F/G,
  23/10). Com 0,8 as letras ficam maiores (0,795 px/u) e as linhas de 480 u iriam até x≈450, sobre a linha da barra de
  rolagem (x=447) → o x inicial do texto (token 4010) passou de 68 para **60**: terminam em x≈440.
* Configuração adotada: 4010 68→60, 4017 470→520, escala 4012 inalterada (0,8). Caixas normais: 480.
* **Título da cena** (bloco 700) é o cabeçalho de cada cena no Histórico e passa pela mesma re-quebra por caractere:
  títulos > 460 u recebem quebra natural (`＿`) em `construir.py`. As cópias no envpsp (menu/saves) ficam em 1 linha.
* Regressão: `ferramentas/detectar_quebra_historico.py` segmenta capturas reais do Histórico em linhas, mede a largura de
  cada uma (0,742 px/u) e acusa as que não correspondem a nenhuma linha produzida pelo construtor.

## 7. envpsp.dat (textos de sistema, O.R.E., Barrage, títulos de capítulo)

Fluxo de tokens u32 sem tabela de offsets: número, ou string = u32 n + n×UTF-16LE.
Cabeçalho de 4 bytes (`01 00 01 00`). Registros do tipo *título, contagem, N linhas*
(o EN muda a contagem ao fundir linhas → o leitor do jogo é genérico).
**A seção de interface perde o alinhamento de 4 bytes** (há campos de 1–2 bytes,
p. ex. floats/bytes de cor): strings começam em offsets ímpares. O tokenizador
ressincroniza — se não há string na posição, mas há uma string legível 1–3 bytes
adiante, os bytes do meio viram token `raw`. Com isso JP e EN têm a mesma
estrutura fora da lista O.R.E. (antes, ~1.090 strings de interface ficavam
invisíveis e, ao montar o envpsp com estrutura JP, os rótulos do Backlog voltavam
ao japonês — visto no teste 5, corrigido e revalidado no PPSSPP).
Tokenizador: `ferramentas/envpsp.py` (round-trip byte a byte JP e EN; ambiguidade
"contagem 1 + string" resolvida por lookahead).

| região (token) | conteúdo | EN traduziu? |
|---|---|---|
| 0–14 | IDs, nome do jogo/save, mensagens de erro de instalação | sim |
| ~15–2480 | comentários do **TwoShot Barrage** (estilo niconico) | **não** |
| ~2528–2744 | **lista O.R.E.**: palavra-chave + descrições (`_` = quebra de linha) | sim |
| ~2732–2840 | interface da lista O.R.E. | parcial |
| ~2930–3070 | Fluxograma | sim |
| ~3200–3350 | Galeria | parcial |
| ~3356–3580 | **menu de sistema** (START), confirmações, lista de saves | sim |
| ~3581–3990 | nomes de cenários (código BGxx + nome) | sim |
| ~3993–4009 | nomes das músicas | — |
| ~4124–4230 | **Backlog** | sim |
| ~4300–4530 | **Opções** | quase tudo |
| ~4539–4546 | dados de instalação (caminho `/PSP/SAVEDATA/…`: **não traduzir**) | — |
| ~8447–12243 | por cena: títulos de capítulo por rota | sim |

Strings técnicas que **nunca** se traduzem: IDs, caminhos, códigos BGxx, nomes de arquivo `*.txt`, dígitos de fonte.

## 8. Gráficos de interface (RES.DAT `image_main` / `image_title`, first.dat)

* **Texturas GIM**: 13.649 no JP e 13.650 no EN, quase todas P8. O jogo recorta atlas por coordenadas fixas: um item traduzido
  fica dentro do retângulo do item original, com as mesmas dimensões e o mesmo formato.
* **Balões de réplica** (`image_tukkomi/TK*.gim` + cópia por cena em `script/<CENA>/000/003image_tukkomi/`, 512×128 P8): 241 usados
  + 1 só global. O bloco 1400 tem em +6 (u16) um **id global** de balão: id k = k-ésimo nome da lista ordenada de `image_tukkomi`
  (conferido nas 250 janelas do Disco 1; ids são reaproveitados entre cenas). O balão é desenhado a ~0,5 de escala.
* **Ícones O.R.E.**: cada palavra-chave tem a mesma arte em 3 imagens: `image_ornament/ORNk` 128×128 (lista), `image_cutin/CUT_ORNk`
  (= ORNk + camada "Get!") e `image_main/ORN(k-1)` 64×48 (= ORNk reduzido + barra de cor). Há nomes repetidos com imagens diferentes
  em pastas diferentes.
* **Codificação**: GIM no formato do JP, com gzip quando a entrada original é gzip. O EN gravou os balões em RGBA8888 (4× a memória
  do original). Exceção documentada: `sg_hint_good/bad`, as únicas texturas P4 do jogo, são P8 na versão traduzida; o motor aceita os dois formatos
  no mesmo espaço (testado no PPSSPP).
* **P4**: cada byte guarda dois pixels, nibble baixo primeiro. Ler ao contrário troca cada par de pixels e embaralha a imagem.
* `first.dat/text` contém só listas internas (scriptname, loadscriptimage, selist): nada a traduzir.

### 8b. Extras: Álbum e Fluxograma (24/10)
* `omake/omake_cg/data/AlbumList.txt`: texto cp932 pré-processado (#line…), uma linha por CG: `"título",(índices…)`. O jogo
  decodifica com o mbtowc do newlib ("C-SJIS") + **tabela código→Unicode no EBOOT** (offset de arquivo 0x23B870, u16 por
  código; 1 byte = índice 0x00–0xFF, 2 bytes = código JIS). `eboot_pt.py` remapeia 0xA1–0xBA (katakana de meia largura,
  sem uso no jogo) para letras acentuadas; `album.py` grava os títulos PT com esses bytes. A ISO leva o EBOOT EN decifrado.
* `main_resource/main_resource_data/flowmap/map.dat`: fluxo binário com strings `u32 n + n×UTF-16` (títulos dos nós);
  comprimento variável é aceito (o EN reescreveu tudo). Gerado por `ferramentas/fluxograma.py` (JP + strings PT).
  Cabeçalho do Fluxograma: envpsp 2989 (x) / 2990 (y) / 2993 (escala, era 0,7); linha única.
* Painel do Fluxograma: 4 cópias idênticas (image_main/fl_info(2).gim, image_title/fl_info(2).gim.gz); os Extras usam a do image_title.

## 9. Reconstrução (pipeline)

```
ISO EN ─► RES.DAT/first.dat (ferramentas/isofs.py)
OBJ JP + traducao/discoN/cenas/*.txt ─► OBJ PT (construir.py)
RES.DAT EN com OBJ PT ─► GPDA reconstruído (oreimo_script.ResDat.rebuild)
seekmap regenerado ─► first.dat
iso_grow ─► cópia da ISO EN com RES.DAT/first.dat novos (realoca bgm.awb para o
            espaço do DUMMY.DAT se RES.DAT crescer; tamanho da ISO não muda)
```

## 10. Comportamento em execução (observado no PPSSPP)

* Botões: ○ avança/confirma (padrão japonês); × oculta a caixa / volta; START pula vídeos
  e, no jogo, abre o **menu de sistema** (Save, Load, Quick Save, Quick Load, Options,
  Title; ↓ navega; mostra título da cena, cenário e música atuais); △ = **Backlog**
  (□ Backlog Jump, △ alterna exibição, ○ repete a voz, × volta); L = **Lista O.R.E.**;
  SELECT = liga o **modo pular** (cuidado na automação).
* **Save** (START → Save): lista No.01–05; ○ escolhe o espaço; "Will you save? Yes / No" com o
  cursor em **No** (precisa ← antes do ○). Grava em SAVEDATA/NPJH50568 (SAVE0/SAVE1/SYSTEM.DAT).
* **Tela de título**: depois de existir save, o jogo mostra antes uma tela "push start button"
  com personagem sorteado (Meruru, Kirino...) → START → menu (Data Integration / Initial start /
  Continue / Omake / Option / Install). O menu é reconhecido pela região dos botões (direita/baixo)
  da assinatura, que não depende do personagem (`inicializacao.regiao_menu`). **Load** = → (Continue)
  → ○ → espaço → ← (Yes) → ○.
* Conversa a Dois (cenas `*T`): roda em **modo automático** ("auto mode" na tela) — as falas
  avançam sozinhas; **□** dentro da janela do bloco 1400 = réplica (o balão mostra o ícone □ e aparece
  ~1,2 s depois de a fala começar; ○ NÃO dá réplica — confirmado na gravação de 19/10). Nela o texto aparece com o
  `「` no início (estilo do modo).
* As strings de todas as falas da cena ficam na RAM ao carregar a cena: procurar texto na
  RAM só detecta troca de cena; dentro da cena, usar o oráculo (índice do bloco).
* O motor **pré-carrega a próxima fala** na RAM antes de exibi-la; cada fala exibida
  aparece em ~4 cópias na RAM (buffers de renderização) em endereços variáveis.
* Índice do bloco em execução (u32): **0x08B0D1E8** após "Initial start" (heap
  determinístico; vale em todas as cenas testadas). 0x08CE7298 só vale no prólogo.
  O índice muda um pouco antes de o texto novo aparecer na tela.
* O script .obj não fica na RAM no formato do arquivo (convertido em estruturas internas).
* "Initial start" pré-carrega a 1ª fala e toca o vídeo de abertura antes do prólogo.
* AKYO_0010A começa com o vídeo OIP_GEB01.pmf; a versão EN tem legenda gravada na imagem.
* Velocidade de texto padrão: ~10 caracteres/s.

## 11. Vídeos PMF

PSMF com packs de 2048 bytes; vídeo H.264 Main@2.1, 480×272, sem quadros B; áudio ATRAC3plus no fluxo privado 0xBD. Para legendar
sem mexer no áudio: reencodar só o vídeo com os mesmos IDR do original (mesma estrutura de GOP → mesmos PTS), copiar o áudio pack a
pack e recalcular o cabeçalho PSMF e o mapa EP (`ferramentas/video_pmf.py`).
