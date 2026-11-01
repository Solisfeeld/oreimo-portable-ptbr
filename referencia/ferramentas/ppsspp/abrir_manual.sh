#!/usr/bin/env bash
# Abre o PPSSPP (flatpak) COM janela e som num ambiente ISOLADO, para os testes manuais (27/10).
#
#   ferramentas/ppsspp/abrir_manual.sh <ISO> <JP|PT>
#
# * Configuração, memory stick e saves ficam em build/ppsspp_manual/<JP|PT>/ (XDG_* redirecionados): a configuração
#   pessoal (~/.var/app/org.ppsspp.PPSSPP) não é lida nem alterada — mesma trava do rodar_ppsspp.sh (aborta com
#   código 99 se ela mudar).
# * Na 1ª vez, o memory stick do ambiente recebe uma CÓPIA dos saves preparados (testes/manuais/saves/NPJH50568);
#   depois disso o ambiente guarda o que você salvar. Para voltar ao ponto de partida: apague build/ppsspp_manual/<JP|PT>.
# * São saves do próprio jogo (SAVEDATA), não save states: o mesmo save carrega na ISO JP e na PT (conferido 26/10).
# * Não roda junto com um teste automático (mesma trava flock).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ISO="$(realpath "$1")"; AMB="${2:?use JP ou PT}"
P="$ROOT/build/ppsspp_manual/$AMB"
INI_DIR="$P/config/ppsspp/PSP/SYSTEM"
SD="$P/config/ppsspp/PSP/SAVEDATA"
mkdir -p "$INI_DIR" "$SD" "$P/cache" "$P/data"
exec 9>"$ROOT/build/ppsspp/.trava_execucao"
if ! flock -n 9; then
  echo "!!! um teste automático do PPSSPP está rodando — espere ele terminar"; exit 98
fi
if [ ! -f "$INI_DIR/ppsspp.ini" ]; then
  cp "$ROOT/ferramentas/ppsspp/ppsspp_base.ini" "$INI_DIR/ppsspp.ini"
  sed -i 's/^RemoteDebuggerOnStartup = .*/RemoteDebuggerOnStartup = False/' "$INI_DIR/ppsspp.ini"
fi
if [ ! -d "$SD/NPJH50568" ] && [ -d "$ROOT/testes/manuais/saves/NPJH50568" ]; then
  cp -a "$ROOT/testes/manuais/saves/NPJH50568" "$SD/"
fi
PESSOAL="$HOME/.var/app/org.ppsspp.PPSSPP"
assinatura() { [ -d "$PESSOAL" ] && find "$PESSOAL" -type f -printf "%p %s %T@\n" 2>/dev/null | sort | sha256sum || echo ausente; }
ANTES="$(assinatura)"
verificar() {
  if [ "$ANTES" != "$(assinatura)" ]; then
    echo "!!! ALERTA: a configuração pessoal do PPSSPP ($PESSOAL) foi modificada !!!"; exit 99
  fi
}
trap verificar EXIT
flatpak run --unshare=network --filesystem="$ROOT/build:rw" \
  --command=sh org.ppsspp.PPSSPP -c '
    export XDG_CONFIG_HOME="$2/config" XDG_CACHE_HOME="$2/cache" XDG_DATA_HOME="$2/data"
    PPSSPPSDL --windowed "$1"
  ' sh "$ISO" "$P"
