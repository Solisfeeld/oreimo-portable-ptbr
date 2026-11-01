# Distribuição do Disco 1: situação

**Situação em 01/11/2026: download em preparação. Nenhum arquivo jogável foi publicado e não há data.**

A primeira análise mostrou que a versão traduzida dependia de arquivos do patch inglês. Essa dependência foi resolvida numa nova versão de teste, que ainda não foi aprovada nem publicada.

## O que já foi resolvido na versão de teste

| item | antes | agora |
|---|---|---|
| Fonte | `font.pgf` comercial, vinda do patch inglês | Fonte gerada da Noto Sans JP (SIL OFL 1.1), com as mesmas larguras |
| Executável | Baseado no do patch inglês | Baseado no japonês, com alterações próprias do projeto |
| Imagens de instalação | Do patch inglês | As originais japonesas |
| Dados de boca das vozes | 96 tabelas do patch inglês, sem dados de 33 falas | As tabelas originais japonesas, completas |
| Textos do `envpsp.dat` | 596 textos vindos da base inglesa | 595 eram iguais ao japonês; 1 título foi romanizado pelo projeto |

Nenhum arquivo da versão de teste é idêntico a um arquivo exclusivo da versão inglesa. Scripts, imagens traduzidas, vídeos e textos de interface são os mesmos da versão aprovada.

## O que ainda falta

1. Conferir e aprovar a nova versão, porque a fonte mudou.
2. Definir o formato de distribuição e confirmar que ele respeita os direitos sobre o jogo.
3. Incluir a licença SIL OFL 1.1 da fonte em qualquer pacote distribuído.
4. Testar em outros ambientes: Windows, Android e PSP real não foram testados.

Este documento é uma análise técnica, não um parecer jurídico.
