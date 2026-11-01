# Créditos e avisos legais

## Aviso legal

Este é um projeto independente de fãs, sem fins comerciais. Não tem vínculo com os titulares da obra e não foi autorizado,
patrocinado nem revisado por eles.

*Ore no Imouto ga Konna ni Kawaii Wake ga Nai Portable ga Tsuzuku Wake ga Nai* foi publicado para PSP pela Bandai Namco Games em 2012.
A série *Ore no Imouto ga Konna ni Kawaii Wake ga Nai* é de autoria de Tsukasa Fushimi. Conforme a tela de título do jogo:
© Tsukasa Fushimi / ASCII Media Works / OIP, ©2012 NBGI. Todos os nomes, marcas, textos, imagens, músicas, vozes e vídeos pertencem
aos seus respectivos titulares.

Este repositório não contém nem distribui o jogo, partes dele, executáveis, arquivos extraídos dos discos, gravações ou capturas de
tela, e não aponta para cópias não autorizadas. Se você é titular de direitos e tem alguma objeção, abra uma issue neste repositório.

## Licença

**Nenhuma licença foi escolhida até agora.** Sem licença, o código segue com todos os direitos reservados ao autor; o GitHub apenas
permite ver e fazer fork pela plataforma. Essa decisão será registrada aqui quando for tomada.

| componente | situação |
|---|---|
| Ferramentas, testes e documentação deste repositório | escritos para este projeto; licença a definir |
| `referencia/` | código de trabalho deste projeto, só para estudo; licença a definir |
| Módulos de terceiros usados no projeto | **não incluídos** (ver abaixo) |
| Tradução, imagens traduzidas e demais recursos derivados do jogo | **não incluídos**; dependem de avaliação de direitos |
| Conteúdo do jogo | dos titulares; não incluído |

### Componentes não incluídos

* `oreimo_core`: módulos do projeto espanhol (licença declarada CC BY-NC-SA 4.0), parte deles com origem em ferramentas sem licença declarada.
  Os leitores de ISO, GPDA e GIM deste repositório são implementações próprias e não contêm esse código.
* Tabela de larguras de glifos: extraída da fonte do jogo.
* Decodificador/codificador GIM do projeto: origem em LibPSPThemes, sem arquivo de licença. O `ferramentas/gim.py` daqui é uma implementação própria.
* Fontes usadas nas artes: livres (SIL OFL 1.1 e Apache 2.0), mas não são necessárias neste repositório.

## Créditos

**Projeto**

* Solisfeeld: direção do projeto, decisões de tradução e de arte, revisão e conferência no jogo.
* Claude Code (Anthropic), ferramenta de IA: redação da tradução, das artes por script, do código, dos testes automáticos e da documentação, sob essa direção.

**Trabalhos de que este projeto depende**

* [Dizzy Ziddy / Rinjinbu Translations](https://dizzyziddy.xyz/2015/02/14/oreimo-tsuzuku-psp-disc-1-full-english-patch-release/):
  patch inglês do Disco 1, base técnica da reconstrução e referência de tradução.
* [christ-gm / Oreimo Portable — Traducción al Español](https://github.com/christ-gm/oreimo-es): referência de tradução e
  módulos de formato usados localmente.
* HanabiWorks: tradução PT-BR anterior, usada como referência de comparação.
* [zapan/FastAsyncOreimoTranslateTool](https://github.com/zapan/FastAsyncOreimoTranslateTool),
  [computer-catt/FastAsyncToradoraTranslateTool](https://github.com/computer-catt/FastAsyncToradoraTranslateTool) e
  [IchinichiQ/ToradoraTranslateTool](https://github.com/IchinichiQ/ToradoraTranslateTool): conhecimento dos formatos.
* [GeofrontTeam/LibPSPThemes](https://github.com/GeofrontTeam/LibPSPThemes): formato GIM.
* [PPSSPP](https://www.ppsspp.org/): emulador usado nos testes e na investigação.

**Fontes usadas nas imagens em português**

M PLUS Rounded 1c, Zen Maru Gothic, Barlow Condensed, Noto Sans JP, Knewave, Kaushan Script, Anton, Big Shoulders Display e
Six Caps (SIL OFL 1.1); Permanent Marker (Apache 2.0). Obtidas em [google/fonts](https://github.com/google/fonts).
