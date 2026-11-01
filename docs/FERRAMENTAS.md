# Ferramentas

Este repositório traz ferramentas de leitura de ISO, GPDA e texturas GIM, leitura e remontagem de scripts, tokenizador do `envpsp.dat`, grafo de cenas, comparação de ISOs, desmontador MIPS e automação isolada do PPSSPP. Requisitos e comandos estão em [USO.md](USO.md).

**Não fazem parte do repositório:** ISOs, patch, EBOOT, arquivos dos discos, músicas, vozes, vídeos, fontes, textos do jogo, a tradução, referências de terceiros e os módulos de terceiros usados no projeto.

## Funcionam com este repositório

Testadas numa cópia limpa, sem nenhum outro arquivo do projeto. As implementações de ISO, GPDA e GIM foram escritas para este repositório, a
partir dos formatos em `docs/FORMATOS.md` e da norma ISO9660.

| arquivo | função | requer |
|---|---|---|
| `ferramentas/explorar.py` | informações, cenas, blocos, grafo, envpsp e texturas de uma ISO | Python; Pillow para exportar texturas |
| `ferramentas/isofs.py` | lista e extrai arquivos de uma ISO9660 | Python |
| `ferramentas/gpda.py` | lista, extrai e monta contêineres GPDA | Python |
| `ferramentas/gim.py` | decodifica texturas GIM (RGBA8888, P8, P4) para PNG | Pillow |
| `ferramentas/oreimo_script.py` | lê e remonta RES.DAT e scripts `.obj`, remapeando índices ao inserir blocos | Python |
| `ferramentas/envpsp.py` | tokenizador do `envpsp.dat` | Python |
| `ferramentas/comparar_isos.py` | lista o que difere entre duas ISOs do jogo | Python |
| `ferramentas/quebra.py` | divide textos em linhas e caixas; recebe a sua função de largura | Python |
| `ferramentas/mipsdis.py` | desmontador MIPS mínimo: `mipsdis.py ELF VADDR [N]` | Python e um ELF decifrado |
| `ferramentas/ppsspp/rodar_ppsspp.sh` | executa o PPSSPP isolado com um roteiro Python | PPSSPP flatpak |
| `ferramentas/ppsspp/ppsspp_api.py` | cliente da interface de depuração do PPSSPP | Python |
| `ferramentas/ppsspp/exemplo_captura.py` | roteiro de exemplo: captura a tela em PNG | PPSSPP flatpak |
| `ferramentas/ppsspp/folha_contato.py` | monta uma grade com capturas | Pillow |
| `testes/teste_independente.py` | testa tudo acima com dados sintéticos | Pillow |
| `testes/teste_com_iso.py` | testa tudo acima com a sua cópia do jogo | Pillow |
| `testes/comparar_vozes.py` | compara a energia do áudio de duas gravações do jogo | NumPy |

## Somente para estudo (`referencia/`)

Código de trabalho que gerou a versão do projeto. **Não executa aqui**: depende de módulos de terceiros, textos e artes que não são publicados, e
os caminhos são os do ambiente local. Serve para entender o método: reconstrução com estrutura japonesa (`construir.py`), vídeos legendados
com áudio preservado (`video_pmf.py`), tabela de acentos (`eboot_pt.py`) e testes no PPSSPP confirmados pelo índice do bloco em RAM (`ppsspp/cenarios/`).

As ferramentas que geram as artes traduzidas e os testes que contêm trechos da tradução ficaram de fora.
