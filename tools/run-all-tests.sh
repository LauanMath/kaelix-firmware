#!/usr/bin/env bash
# Ponto de entrada único de verificação do projeto.
#
# São três suítes em duas linguagens, e rodá-las separadamente é como as
# quebras de integração passam: um refactor em lib/ que muda assinatura
# aparece no teste C++, mas o gerador Python que consome a mesma struct só
# quebra na suíte de treino.
set -uo pipefail
RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$RAIZ"

falhas=0
secao() { printf '\n\033[1m== %s ==\033[0m\n' "$1"; }
py() { uv run --no-project --with numpy --with scipy --with scikit-learn --with pytest python "$@"; }

secao "firmware — lib/ (Unity, host)"
if ! ./tools/run-native-tests.sh; then falhas=$((falhas+1)); fi

secao "pipeline de treino"
if ! (cd training && py -m pytest tests/ -q); then falhas=$((falhas+1)); fi

secao "gateway"
if ! py -m pytest experiments/gateway/tests/ -q; then falhas=$((falhas+1)); fi

secao "hardware — esquemático e placa (KiCad)"
if command -v kicad-cli >/dev/null 2>&1 || [ -x /Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli ]; then
  # Todas as versões, não só a padrão: até aqui o runner construía apenas a
  # v1, e uma mudança no gerador ou no roteador podia quebrar a versão ativa
  # sem que nada acusasse. Com a v3 mudando o roteador, isso deixou de ser
  # hipotético.
  for v in v1 v2 v3; do
    if ! KAELIX_PCB=$v ./tools/build-hardware.sh; then falhas=$((falhas+1)); fi
  done
else
  printf 'pulado: kicad-cli não encontrado\n'
fi

printf '\n%s\n' "-----------------------------------------------------------------"
if [ "$falhas" -eq 0 ]; then
  printf '\033[32mTUDO PASSOU\033[0m  4 suítes\n'
else
  printf '\033[31m%d SUÍTE(S) FALHARAM\033[0m\n' "$falhas"
fi

printf '\nNão coberto por esta verificação:\n'
printf '  - a camada src/ do firmware (sem toolchain ESP32 aqui; use pio run -e esp32-s3)\n'
printf '  - qualquer comportamento em hardware real\n'
exit "$falhas"
