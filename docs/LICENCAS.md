# Licenças

Cada parte do repositório tem uma situação própria. **Os arquivos `LICENSE` e `LICENSE-DOCS` valem só para o que está listado aqui.**

| parte | licença |
|---|---|
| Código próprio: `ferramentas/`, `testes/`, `.github/workflows/` e o código do site (`site/*.html`, `site/assets/site.css`, `site/assets/site.js`, `site/robots.txt`, `site/sitemap.xml`) | [MIT](../LICENSE) |
| Documentação própria: `README.md`, `CHANGELOG.md`, `docs/`, `.github/notas/` e os textos do site | [CC BY 4.0](../LICENSE-DOCS) |
| Arte original do site e do README: `site/assets/*.svg`, `site/assets/compartilhar.png`, `docs/imagens/` | [CC BY 4.0](../LICENSE-DOCS) |
| Capturas do jogo: `site/assets/capturas/` | **Sem licença**: pertencem aos titulares do jogo |
| `referencia/` | **Sem licença**: todos os direitos reservados, só para leitura |

Atribuição para CC BY 4.0: "Oreimo Portable PT-BR, de Solisfeeld", com link para o repositório e para a licença.

## O que estas licenças não cobrem

* **O jogo e tudo o que vem dele**: nomes, personagens, marcas, títulos, textos, imagens, músicas, vozes e vídeos continuam dos titulares. Isso vale também para nomes de arquivos do jogo e para as citações curtas em `docs/FORMATOS.md`.
* **A tradução e as imagens traduzidas**: são derivadas do jogo, não estão neste repositório e não têm licença.
* **Módulos de terceiros usados localmente**: `oreimo_core`, decodificador GIM e tabela de larguras de glifos não estão neste repositório.
* **Marcas de terceiros** citadas nos créditos e na documentação.

## Por que `referencia/` ficou de fora

O código é de trabalho do projeto, mas boa parte importa `oreimo_core`, de licença CC BY-NC-SA 4.0 e com partes de origem sem licença declarada. Sem esses módulos ele não executa, e não está resolvido se esse código é independente deles. Na dúvida, nada de `referencia/` foi licenciado.

## Como foi feita a auditoria

Em 31/10/2026, os 61 arquivos públicos foram comparados, linha a linha, com o projeto `oreimo-es`, com `oreimo_core` e com o extrator GPDA local.

* **`ferramentas/` e `testes/` (17 arquivos)**: nenhum importa `oreimo_core`. As linhas iguais são genéricas, como `from pathlib import Path` e `if __name__ == "__main__":`, além de uma condição trivial sobre as aspas japonesas.
* **`referencia/` (35 arquivos)**: 11 importam `oreimo_core` diretamente. Por isso a pasta inteira ficou fora.
* **Texto do jogo**: `ferramentas/publicacao/auditar.py`, que não é publicado, compara cada arquivo com o texto do jogo e com as traduções de referência. Resultado: nenhuma coincidência.

## Dúvidas que continuam abertas

1. **Autoria com IA.** Grande parte do código e da documentação foi redigida com o Claude Code, sob direção humana. A proteção autoral desse tipo de material pode ser limitada e varia por país. As licenças valem na medida dos direitos que existirem.
2. **Conhecimento técnico de terceiros.** Os formatos foram entendidos também com a ajuda de ferramentas de terceiros, citadas em [CREDITOS_E_AVISOS.md](CREDITOS_E_AVISOS.md). Foram aproveitados fatos sobre os formatos, não código. A engenharia reversa pode ter regras próprias, conforme o país.
3. **Este documento não é parecer jurídico.**
