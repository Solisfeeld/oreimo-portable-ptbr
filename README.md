# Oreimo Portable PT-BR

Tradução brasileira de ***Ore no Imouto ga Konna ni Kawaii Wake ga Nai Portable ga Tsuzuku Wake ga Nai***
(俺の妹がこんなに可愛いわけがない ポータブルが続くわけがない), visual novel para PSP lançada em 2 discos.

Projeto independente, feito por fãs e sem fins comerciais. Não tem vínculo com os titulares da obra nem foi autorizado por eles.

> [!IMPORTANT]
> **Ainda não dá para jogar em português a partir deste repositório.** Não há ISO, patch, instalador nem os textos da tradução, e nada disso
> deve ser pedido aqui. O que existe é documentação técnica e ferramentas que funcionam com a sua própria cópia do jogo.

## Objetivo

Oferecer o jogo em português do Brasil com uma tradução nova **a partir do japonês**, fiel ao original e natural em PT-BR, preservando
humor, registro e o jeito de falar de cada personagem. Inglês e outras traduções serviram apenas como referência de comparação.

## Estado do projeto

| disco | estado |
|---|---|
| **Disco 1** | Tradução, testes técnicos e conferência manual no PPSSPP concluídos. |
| **Disco 2** | Ainda não iniciado. |

## O que foi feito no Disco 1

* **Diálogos**: 299 cenas e 18.852 unidades de texto traduzidas e revisadas, com todas as rotas e os extras.
* **Falas que faltavam**: a estrutura dos scripts vem do original japonês, o que recupera as cerca de 36 falas de uma cena cortadas
  no patch inglês.
* **Interface**: menus, Opções, Histórico, Lista O.R.E., Fluxograma, Álbum, títulos de cena e comentários do modo Barrage.
* **Imagens com texto**: 362 recursos, incluindo os 242 balões de réplica da Conversa a Dois, cut-ins e ícones O.R.E., refeitos no
  estilo do original.
* **Vídeos**: legendas em português nos 2 vídeos que precisavam, com o áudio original preservado.
* **Áudio**: vozes e músicas japonesas originais, sem alteração.
* **Técnica**: quebra de texto pela largura real da fonte, novas caixas quando a fala não cabe, acentos também nos textos do Álbum e
  Histórico sem palavras cortadas.

## Compatibilidade

Testado no **PPSSPP 1.20.4** (flatpak, Linux) por automação. **Não testado em PSP real** nem em outros sistemas ou versões do PPSSPP.
Detalhes em [docs/COMPATIBILIDADE.md](docs/COMPATIBILIDADE.md).

## O que está disponível

* **Ferramentas que funcionam**: leitura de ISO, GPDA e texturas GIM, leitura e remontagem de scripts, tokenizador do `envpsp.dat`, grafo de cenas,
  comparação de ISOs, desmontador MIPS e automação isolada do PPSSPP.
* **Testes**: um que roda sem o jogo e outro que usa a sua cópia.
* **Documentação**: formatos do jogo, uso e compatibilidade.
* **`referencia/`**: o código de trabalho do projeto, só para estudo. Não executa aqui.

## O que não está disponível

ISOs, patch, EBOOT, arquivos dos discos, músicas, vozes, vídeos, imagens, fontes, textos do jogo, a tradução, referências de terceiros e os módulos
de terceiros usados no projeto.

## Como usar

**Requisitos:** Python 3.10 ou mais novo; Pillow para texturas; NumPy para comparar áudio; PPSSPP via flatpak para a automação.

```bash
python3 testes/teste_independente.py                       # não precisa do jogo
python3 ferramentas/explorar.py info "/caminho/da/sua/copia.iso"
```

Passo a passo em [docs/USO.md](docs/USO.md) e descrição de cada script em [docs/FERRAMENTAS.md](docs/FERRAMENTAS.md).

## Sua cópia do jogo

Este repositório não contém o jogo e nunca vai indicar onde obtê-lo. As ferramentas e qualquer uso futuro exigem a sua própria cópia legalmente
obtida. Não publique nem peça ISOs, arquivos extraídos ou links para cópias do jogo nas issues.

## Limitações conhecidas

* **Falas dubladas divididas em 2 caixas (50 casos)**: se você avançar para a segunda caixa antes de a voz acabar, a voz é cortada,
  porque o motor do jogo corta a voz em todo avanço. Basta esperar a voz terminar.
* **Créditos finais em japonês**: mantidos assim por decisão do projeto.
* **Ícones de palavra-chave**: parte da arte fica em japonês de propósito, como placas, logotipos e textos que fazem parte da ilustração.
* **BOA♥ e RUIM!**: as imagens estão prontas e o motor aceita o formato usado, mas o uso real não foi reproduzido, pois depende de uma opção liberada com progresso.
* **Aviso de autossalvamento**: traduzido, mas não apareceu nos testes.
* **Minijogo e balões amarelos**: traduzidos, mas não localizamos nenhum caminho que os mostre no Disco 1.

## Desenvolvimento futuro

1. Avaliar se um patch redistribuível é viável sem incluir conteúdo protegido. Ainda não existe patch.
2. Definir a licença do código próprio.
3. Iniciar o Disco 2.

Nenhuma dessas etapas tem data prevista.

## Créditos e licença

Créditos, avisos legais e a situação de licença de cada componente estão em [docs/CREDITOS_E_AVISOS.md](docs/CREDITOS_E_AVISOS.md).
**Nenhuma licença foi definida até agora.** O histórico de versões está em [CHANGELOG.md](CHANGELOG.md).
