#!/usr/bin/env bash
# Bateria estática de encerramento: testes sobre a ISO de entrega e reconstrução completa a partir das fontes.
# Uso: [ISO=x.iso] [REF=y.iso] testes/bateria_encerramento.sh <dir_relatorios>   (padrão: ISO de entrega × reserva)
set -u
cd "$(dirname "$0")/.."
R="$1"; mkdir -p "$R"
ISO=${ISO:-entrega/Oreimo_Disco1_PTBR.iso}; REF=${REF:-build/iso_teste/estavel_92831eb6.iso}
assinatura() { find traducao ferramentas/*.py ferramentas/oreimo_core testes/*.py -type f -not -path '*/__pycache__/*' -not -name manifesto_aprovado.tsv -not -name imagens_qa.tsv -not -name 'ore_termos.tsv' -print0 | sort -z | xargs -0 sha256sum | sha256sum; }
A="$(assinatura)"
python3 testes/verificar_iso_final.py "$ISO"            > "$R/01_integridade_iso.txt" 2>&1;        echo "01 integridade exit=$?"
python3 ferramentas/verificar.py                        > "$R/02_scripts_dialogos.txt" 2>&1;       echo "02 verificar exit=$?"
python3 testes/teste_quebra.py                          > "$R/03_quebras.txt" 2>&1;                echo "03 quebras exit=$?"
python3 testes/teste_roundtrip_disco1.py                > "$R/04_roundtrip.txt" 2>&1;              echo "04 roundtrip exit=$?"
python3 ferramentas/comparar_isos.py "$REF" "$ISO" > "$R/09_comparacao_estavel_anterior.txt" 2>&1; echo "09 comparacao exit=$?"
python3 testes/verificar_recursos_finais.py "$ISO" --gravar-manifesto > "$R/05_recursos_audio_cenas.txt" 2>&1; echo "05 recursos exit=$?"
python3 ferramentas/construir.py --saida build/iso_teste/repro_encerramento.iso --dir-saida build/saida_repro > "$R/10_reconstrucao.txt" 2>&1; echo "10 construir exit=$?"
{ md5sum "$ISO" build/iso_teste/repro_encerramento.iso; cmp "$ISO" build/iso_teste/repro_encerramento.iso && echo "BYTE A BYTE IGUAIS"; } > "$R/10_reconstrucao_comparacao.txt" 2>&1; echo "10 comparacao exit=$?"
rm -f build/iso_teste/repro_encerramento.iso; rm -rf build/saida_repro
D="$(assinatura)"
[ "$A" = "$D" ] && echo "fontes intactas durante a bateria" || echo "ATENCAO: fontes mudaram durante a bateria"
echo FIM
