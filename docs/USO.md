# Uso e instalação

## Para jogar

**Ainda não é possível jogar em português a partir deste repositório.** Não há ISO, patch, instalador nem aplicador automático, e os
textos traduzidos não estão aqui. Esta página será atualizada se isso mudar. Qualquer forma futura de instalação vai exigir a sua
própria cópia legalmente obtida do jogo.

Não peça nem envie ISOs ou links para cópias do jogo nas issues deste repositório.

## Para usar as ferramentas

Requisitos: Python 3.10 ou mais novo. Pillow só para texturas (`pip install pillow`) e NumPy só para `comparar_vozes.py`.

```bash
git clone https://github.com/Solisfeeld/oreimo-portable-ptbr.git
cd oreimo-portable-ptbr
python3 testes/teste_independente.py        # não precisa do jogo
```

Com a sua cópia do Disco 1:

```bash
ISO="/caminho/da/sua/copia.iso"

python3 testes/teste_com_iso.py "$ISO"                  # confere tudo; só lê a ISO (alguns minutos)
python3 ferramentas/explorar.py info "$ISO"             # arquivos, cenas e texturas
python3 ferramentas/explorar.py cenas "$ISO"            # cenas, blocos, falas e título
python3 ferramentas/explorar.py blocos "$ISO" AKYO_0000A
python3 ferramentas/explorar.py grafo "$ISO" grafo.tsv  # destinos de cada cena
python3 ferramentas/explorar.py texturas "$ISO" pngs image_title   # exporta para PNG, com filtro opcional
```

Arquivos avulsos:

```bash
python3 ferramentas/isofs.py listar "$ISO"
python3 ferramentas/isofs.py extrair "$ISO" /PSP_GAME/USRDIR/first.dat first.dat
python3 ferramentas/gpda.py listar first.dat --recursivo
python3 ferramentas/gim.py png textura.gim textura.png
python3 ferramentas/comparar_isos.py copia_a.iso copia_b.iso
```

Nenhuma dessas ferramentas modifica a ISO. Os resultados são para uso pessoal: não redistribua arquivos extraídos do jogo.

## Automação no PPSSPP

Requer o PPSSPP pelo flatpak (`org.ppsspp.PPSSPP`) no Linux.

```bash
ferramentas/ppsspp/rodar_ppsspp.sh "$ISO" ferramentas/ppsspp/exemplo_captura.py build/capturas --quantidade 3 --intervalo 20
```

Roda sem janela, sem som e sem rede, com configuração própria em `build/ppsspp/`, e aborta se a sua configuração pessoal do PPSSPP mudar.
A ISO precisa estar em um local que o flatpak consiga ler, como a sua pasta pessoal.

## O que não funciona só com este repositório

A pasta `referencia/` é para leitura: é o código de trabalho do projeto e depende de componentes que não são publicados.

| falta | por quê |
|---|---|
| ISO japonesa e ISO com o patch inglês v1 | conteúdo do jogo; cada pessoa usa a sua |
| módulos `oreimo_core` | de terceiros, com situação de licença não resolvida |
| textos e tradução | conteúdo do jogo e obra derivada |
| artes, fontes e EBOOT de base | conteúdo derivado do jogo ou de terceiros |
