# Patch público do Disco 1: situação

**Situação em 31/10/2026: patch público em preparação. Nenhum patch foi publicado e não há data.**

A ISO em português do projeto é local e não será distribuída. Antes de publicar um patch, foi medido o que ele carregaria de fato.

## Por que um patch comum não serve

Um arquivo de diferenças do tipo xdelta, da ISO japonesa para a ISO em português, teria **71,7 MB**. Esse volume não é só tradução:

| conteúdo que entraria | situação |
|---|---|
| Executável do jogo (EBOOT, 3,5 MB) | O original é cifrado e o usado é decifrado, então a diferença traz o executável inteiro em claro. |
| 2 vídeos recodificados (20,7 MB) | Com a recodificação, imagem e áudio dos vídeos entram quase inteiros. |
| `font.pgf` (1,5 MB) | Fonte comercial FTT-NewRodin Pro DB, trazida pelo patch inglês, sem permissão conhecida de redistribuição. |
| Material do patch inglês | EBOOT modificado, tabelas de voz de 96 cenas, imagens de instalação e 596 strings do `envpsp.dat`. Dizzy Ziddy / Rinjinbu não publicaram termos de redistribuição. |
| 846 arquivos de imagem alterados, contando as cópias | São derivados da arte do jogo; um patch carregaria boa parte dessa arte. |
| Textos traduzidos | Trabalho derivado do texto do jogo, sem autorização dos titulares. |

Um arquivo de diferenças não fica livre de conteúdo protegido só por não ser a ISO. Por isso, **nenhum pacote foi publicado**.

## O que precisa ser resolvido

1. Obter permissão dos autores do patch inglês ou deixar de depender desse material.
2. Trocar `font.pgf` por uma fonte de licença livre, sem perder a largura do texto, e aprovar o resultado no jogo.
3. Parar de levar o EBOOT inteiro: alterar o executável na máquina do usuário, ou usar outra forma de instalar a fonte e os acentos.
4. Refazer as legendas dos 2 vídeos sem incluir os vídeos no patch.
5. Levar para o patch só o necessário das imagens alteradas.
6. Decidir, com consciência do risco, sobre a publicação da tradução, que continua sendo um trabalho derivado não autorizado.
7. Criar o instalador simples, com conferência da ISO de origem por hash, e testar com arquivos válidos e inválidos.

Cada item dessa lista muda o que foi testado. O resultado será uma nova versão de distribuição, que precisa de novos testes. A ISO aprovada do projeto não muda.

Este documento é uma análise técnica, não um parecer jurídico.
