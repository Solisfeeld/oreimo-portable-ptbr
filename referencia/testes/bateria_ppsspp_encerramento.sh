#!/usr/bin/env bash
# Bateria de regressão no PPSSPP isolado (um teste por vez), sobre a ISO de entrega.
# Uso: [ISO=x.iso] testes/bateria_ppsspp_encerramento.sh <prefixo>   -> testes/visuais/<prefixo>_*
set -u
cd "$(dirname "$0")/.."
PRE="$1"; ISO=$(realpath "${ISO:-entrega/Oreimo_Disco1_PTBR.iso}"); RUN=ferramentas/ppsspp/rodar_ppsspp.sh; C=ferramentas/ppsspp/cenarios
CP=AKYO_0010A_fim_t15
$RUN "$ISO" $C/teste_cena.py testes/visuais/${PRE}_inicio --iso "$ISO" --cenas AKYO_0000A AKYO_0010A --novo-jogo; echo "cena inicio exit=$?"
$RUN "$ISO" $C/teste_interface.py testes/visuais/${PRE}_interface --iso "$ISO" --checkpoint $CP; echo "interface exit=$?"
$RUN "$ISO" $C/teste_rodapes.py testes/visuais/${PRE}_rodapes --iso "$ISO" --checkpoint $CP; echo "rodapes exit=$?"
$RUN "$ISO" $C/teste_extras.py testes/visuais/${PRE}_extras --iso "$ISO"; echo "extras exit=$?"
$RUN "$ISO" $C/teste_avisos.py testes/visuais/${PRE}_avisos --iso "$ISO" --checkpoint $CP; echo "avisos exit=$?"
$RUN "$ISO" $C/capturar_titulo.py testes/visuais/${PRE}_titulo --seq right,right,down,left,left; echo "titulo exit=$?"
for CENA in BKIR_0000A CKUR_0000A DSAO_0009G EMAN_0000A FAYA_0001A GIFG_0000A JROC_0000E; do
  I=build/iso_teste/insp_encerramento.iso
  python3 ferramentas/iso_gravacao_jp.py $CENA "$I" --base build/saida > /dev/null || { echo "$CENA ISO falhou"; continue; }
  I=$(realpath "$I")
  $RUN "$I" $C/teste_cena.py testes/visuais/${PRE}_$CENA --iso "$I" --cenas AKYO_0000A --novo-jogo; echo "$CENA exit=$?"
  rm -f "$I"
done
AUD=build/ppsspp/config/ppsspp/PSP/AUDIO; VID=build/ppsspp/config/ppsspp/PSP/VIDEO
OREIMO_GRAVAR=1 $RUN "$ISO" $C/gravar_vozes.py testes/gravacao/${PRE}_vozes_AKYO_0000A_PT --iso "$ISO" --ate-bloco 179; echo "vozes exit=$?"
W=$(ls -t $AUD/*.wav 2>/dev/null | head -1); [ -n "$W" ] && mv "$W" testes/gravacao/${PRE}_vozes_AKYO_0000A_PT/gravacao.wav
A=$(ls -t $VID/*.avi 2>/dev/null | head -1); [ -n "$A" ] && rm -f "$A"
echo FIM
