# Compatibilidade

Resultados do Disco 1 de 31/10/2026. Referem-se à ISO de trabalho do projeto, que não é distribuída aqui.

| ambiente | situação |
|---|---|
| PPSSPP 1.20.4, flatpak, Linux, renderizador por software | testado por automação |
| Outras versões do PPSSPP, Windows, macOS, Android | não testado |
| PSP real | não testado |

**Atenção sobre PSP real:** a imagem usa um EBOOT decifrado, que roda no PPSSPP. O funcionamento em hardware real não foi avaliado.

## O que foi testado

| verificação | resultado |
|---|---|
| Integridade da imagem | 13/13 |
| Textos: 299 cenas | 0 unidades pendentes, 0 problemas |
| Quebra de texto, 18.475 falas | 73.916/73.916 |
| Extração e reconstrução | 35/35 |
| Reconstrução a partir das fontes | byte a byte idêntica |
| 13.650 texturas | abrem, com dimensões iguais às do original |
| Áudio e vozes | arquivos idênticos ao original; 18.132 ids de voz na ordem original |
| Extras no PPSSPP | 5 opções capturadas; fora dos rótulos, 0 pixels diferentes do original no menu |
| Interface no PPSSPP | menus, Opções, Salvar, Histórico, Lista O.R.E., Extras e título revisados por capturas |
| Cenas no PPSSPP | 9 cenas, uma amostra de cada rota e um extra: 472 caixas confirmadas |

A cena CKUR_0000A confirmou 23 de 33 caixas: o teste é linear e a cena tem um ramo que ele não percorre. A ISO japonesa original tem o mesmo desvio.

## O que não foi testado

* Partida completa em todas as rotas: as 299 cenas passaram por verificações sobre os dados; a conferência manual cobriu menus, Extras, diálogos, balões, vozes e músicas no PPSSPP, sem jogar tudo até o fim.
* Finais de todas as rotas em jogo real.
* Dicas BOA♥/RUIM!, aviso de autossalvamento, minijogo e balões amarelos: conferidos só como imagem.

## Ferramentas públicas

Em cópia limpa, sem nenhum outro arquivo do projeto: 21/21 verificações sem o jogo; com a ISO japonesa, 300 cenas e o `envpsp.dat` remontados idênticos, `RES.DAT` e `first.dat`
remontados byte a byte. As 13.649 texturas do JP decodificaram com sucesso; 13.647 iguais às de outro decodificador, e as 2 diferentes (P4) foram conferidas no PPSSPP, que mostra a
leitura deste repositório como a correta.
