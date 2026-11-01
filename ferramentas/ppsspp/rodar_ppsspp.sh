#!/usr/bin/env bash
# Executa o PPSSPP (flatpak) ISOLADO + um roteiro de teste automatizado.
#
#   ferramentas/ppsspp/rodar_ppsspp.sh <ISO> <roteiro.py> <dir_saida> [args do roteiro...]
#
# Por padrão roda SEM JANELA e SEM SOM (OREIMO_VIDEO=offscreen, OREIMO_AUDIO=0).
# Para ver a janela: OREIMO_VIDEO= ferramentas/ppsspp/rodar_ppsspp.sh ...
# Isolamento:
#  * --unshare=network: o sandbox só tem loopback; a interface de depuração
#    (porta 45700) é inacessível de fora — nem pela própria máquina fora do sandbox.
#    Também impede o anúncio em report.ppsspp.org que o servidor faz por padrão.
#  * RemoteDebuggerLocal=True no ini (restrição a localhost do próprio PPSSPP).
#  * Configuração, saves e savestates em build/ppsspp/ (XDG_* redirecionados):
#    a configuração pessoal (~/.var/app/org.ppsspp.PPSSPP) não é lida nem alterada.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ISO="$(realpath "$1")"; ROTEIRO="$(realpath "$2")"; OUT="$3"; shift 3
mkdir -p "$OUT"; OUT="$(realpath "$OUT")"
P="$ROOT/build/ppsspp"
INI_DIR="$P/config/ppsspp/PSP/SYSTEM"
mkdir -p "$INI_DIR" "$P/cache" "$P/data"
# Um teste por vez: duas instâncias disputam a porta 45700 e a configuração isolada
# (visto em 19/10: inspeção IYAN + teste do Histórico simultâneos → ambos inconclusivos).
exec 9>"$P/.trava_execucao"
if ! flock -n 9; then
  echo "!!! outro teste do PPSSPP está em andamento (trava $P/.trava_execucao) — abortado" | tee -a "$OUT/ABORTADO_CONCORRENCIA.txt"
  exit 98
fi
if [ ! -f "$INI_DIR/ppsspp.ini" ]; then
  cp "$ROOT/ferramentas/ppsspp/ppsspp_base.ini" "$INI_DIR/ppsspp.ini"
fi
PORT=45700
# OREIMO_GRAVAR=1: grava vídeo (AVI, PSP/VIDEO) e áudio (WAV, PSP/AUDIO) do jogo no memory stick
# isolado — liga DumpFrames/DumpAudio só nesta execução e restaura ao sair.
INI="$INI_DIR/ppsspp.ini"
if [ "${OREIMO_GRAVAR:-0}" = "1" ]; then
  sed -i 's/^DumpFrames = .*/DumpFrames = True/; s/^DumpAudio = .*/DumpAudio = True/' "$INI"
fi

# Trava de segurança: a configuração pessoal e os saves NÃO podem mudar.
PESSOAL="$HOME/.var/app/org.ppsspp.PPSSPP"
assinatura() { [ -d "$PESSOAL" ] && find "$PESSOAL" -type f -printf "%p %s %T@\n" 2>/dev/null | sort | sha256sum || echo ausente; }
ANTES="$(assinatura)"
verificar() {
  sed -i 's/^DumpFrames = .*/DumpFrames = False/; s/^DumpAudio = .*/DumpAudio = False/; s/^DumpVideoOutput = .*/DumpVideoOutput = False/' "$INI"
  DEPOIS="$(assinatura)"
  if [ "$ANTES" != "$DEPOIS" ]; then
    echo "!!! ALERTA: a configuração pessoal do PPSSPP ($PESSOAL) foi modificada nesta execução !!!" | tee -a "$OUT/ALERTA_CONFIG_PESSOAL.txt"
    exit 99
  fi
}
trap verificar EXIT

flatpak run --unshare=network \
  --filesystem="$ROOT/build:rw" --filesystem="$ROOT/testes:rw" \
  --env=PYTHONDONTWRITEBYTECODE=1 --env=OREIMO_VIDEO="${OREIMO_VIDEO-offscreen}" --env=OREIMO_AUDIO="${OREIMO_AUDIO:-0}" \
  --command=sh org.ppsspp.PPSSPP -c '
    ISO="$1"; ROTEIRO="$2"; OUT="$3"; PORT="$4"; P="$5"; shift 5
    # o flatpak força XDG_* para ~/.var/app/...; redefinimos aqui dentro
    export XDG_CONFIG_HOME="$P/config" XDG_CACHE_HOME="$P/cache" XDG_DATA_HOME="$P/data"
    # padrão: sem janela (SDL offscreen) -> sem foco a perder, sem interferência do teclado
    [ -n "$OREIMO_VIDEO" ] && export SDL_VIDEODRIVER="$OREIMO_VIDEO"
    # padrão: sem som (áudio/vozes são validados manualmente); OREIMO_AUDIO=1 liga
    [ "$OREIMO_AUDIO" = "1" ] || export SDL_AUDIODRIVER=dummy
    PPSSPPSDL --windowed "$ISO" > "$OUT/ppsspp_stdout.log" 2>&1 &
    PID=$!
    python3 -I "$ROTEIRO" --porta "$PORT" --saida "$OUT" "$@" ; RC=$?
    kill $PID 2>/dev/null; sleep 1; kill -9 $PID 2>/dev/null
    exit $RC
  ' sh "$ISO" "$ROTEIRO" "$OUT" "$PORT" "$P" "$@"
