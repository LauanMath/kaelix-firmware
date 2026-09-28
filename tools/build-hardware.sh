#!/usr/bin/env bash
# Gera e VERIFICA a placa, do esquemático aos arquivos derivados.
#
# Por que existe: o BOM e a netlist deste projeto estavam obsoletos — listavam
# Q1/Q2 BC337 e R4/R5 que não existiam mais no esquemático. Arquivo derivado
# mantido à mão diverge em silêncio, e um BOM errado só aparece na bancada,
# quando chega a peça errada. Aqui todos saem da mesma fonte, sempre, e o
# script falha se ERC ou DRC acusarem qualquer coisa.
#
# A fonte da verdade é hardware/gen_schematic.py. Nada abaixo dele é editado
# à mão: .kicad_sch, .kicad_pcb, .kicad_pro, .net, o BOM e os renders são
# saída.
set -uo pipefail
RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HW="$RAIZ/hardware"
VERSAO="${KAELIX_PCB:-v1}"
PROJ="$HW/pcb/$VERSAO"
export KAELIX_PCB="$VERSAO"
CLI="/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"
[ -x "$CLI" ] || CLI="$(command -v kicad-cli)"
if [ ! -x "${CLI:-}" ]; then
  echo "kicad-cli não encontrado — instale o KiCad ou ajuste o caminho" >&2
  exit 127
fi

falhas=0
secao() { printf '\n\033[1m== %s ==\033[0m\n' "$1"; }
falhou() { printf '\033[31m%s\033[0m\n' "$1"; falhas=$((falhas+1)); }

printf 'versão da placa: %s  (KAELIX_PCB para trocar)\n' "$VERSAO"
mkdir -p "$PROJ"

secao "geração"
python3 "$HW/gen_schematic.py" || falhou "gen_schematic.py falhou"
python3 "$HW/gen_pcb.py"       || falhou "gen_pcb.py falhou"

secao "corpos 3D"
# Os modelos gerados vêm antes do PCB porque o .step exportado depende deles.
FC=/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd
if [ -x "$FC" ]; then
  # Código de saída, e NÃO grep de padrão: duas vezes esta etapa foi dada
  # como falha só porque o formato da saída mudou e o padrão deixou de casar.
  # Filtro serve para esconder o banner do FreeCAD, não para decidir sucesso.
  saida=$("$FC" "$HW/gen_3dmodels.py" 2>/dev/null); rc=$?
  printf '%s\n' "$saida" | grep -vE "^FreeCAD |^\(C\) |free and open-source|^$"
  [ "$rc" -eq 0 ] || falhou "gen_3dmodels.py: modelo ausente ou fora das cotas"
else
  printf 'pulado: freecadcmd não encontrado — usando os .step já versionados\n'
fi

secao "ERC"
if ! "$CLI" sch erc --output "$PROJ/erc.rpt" --severity-error --severity-warning \
        --exit-code-violations "$PROJ/kaelix.kicad_sch"; then
  falhou "ERC acusou violações — ver $PROJ/erc.rpt"
fi

secao "DRC"
# --refill-zones é obrigatório: sem preencher os planos, todo pad de GND
# aparece como desconectado e o relatório vira ruído.
#
# Violação de regra é falha dura. Item desconectado é contado contra uma
# LINHA DE BASE declarada: hoje resta 1, e ele está nomeado abaixo. Carregar
# um defeito conhecido com número explícito é diferente de escondê-lo — se
# aparecer o segundo, este script falha.
#
#   Hoje a linha de base é ZERO: nenhum pad, pista, via ou pedaço de plano
#   fica solto. Chegou a haver uma pendência (o pad 11 do MPU6050 ilhado
#   pelo passo de 0,5 mm do QFN), e ela fechou quando o corredor de cabo do
#   conector da bateria empurrou o furo M2 para fora do canto — o plano
#   ganhou o caminho que faltava. Se este número precisar subir de novo,
#   escreva aqui QUAL é a pendência e por que se aceita conviver com ela.
PENDENCIAS_CONHECIDAS=0

"$CLI" pcb drc --output "$PROJ/drc.rpt" --severity-error --refill-zones \
       "$PROJ/kaelix.kicad_pcb" >/dev/null 2>&1
viol=$(grep -c "^\[" "$PROJ/drc.rpt" 2>/dev/null | tr -d ' ')
desc=$(grep -c "^\[unconnected_items\]" "$PROJ/drc.rpt" 2>/dev/null | tr -d ' ')
regras=$(( viol - desc ))
if [ "$regras" -gt 0 ]; then
  falhou "DRC: $regras violação(ões) de regra — ver $PROJ/drc.rpt"
else
  printf 'DRC: 0 violações de regra\n'
fi
if [ "$desc" -gt "$PENDENCIAS_CONHECIDAS" ]; then
  falhou "conectividade: $desc itens desconectados, acima da linha de base ($PENDENCIAS_CONHECIDAS)"
elif [ "$desc" -gt 0 ]; then
  printf '\033[33mconectividade: %s item(ns) desconectado(s) — pendência conhecida:\033[0m\n' "$desc"
  grep -A3 "unconnected_items" "$PROJ/drc.rpt" | grep "@" | sed 's/^ */  /' | sort -u
else
  printf 'conectividade: nenhum item solto\n'
fi

secao "arquivos derivados"
"$CLI" sch export netlist --output "$PROJ/kaelix.net" "$PROJ/kaelix.kicad_sch" \
  || falhou "export da netlist falhou"
"$CLI" sch export bom --output "$PROJ/kaelix-bom.csv" \
  --fields 'Reference,Value,Footprint' --group-by 'Value,Footprint' \
  --labels 'Reference,Value,Footprint' \
  "$PROJ/kaelix.kicad_sch" || falhou "export do BOM falhou"
"$CLI" pcb render --output "$PROJ/render_top.png"    --side top    \
  --quality basic "$PROJ/kaelix.kicad_pcb" >/dev/null || falhou "render superior falhou"
"$CLI" pcb render --output "$PROJ/render_bottom.png" --side bottom \
  --quality basic "$PROJ/kaelix.kicad_pcb" >/dev/null || falhou "render inferior falhou"
# O .step é o arquivo que alguém abre para conferir encaixe mecânico. Ele
# estava fora deste script e ficou descrevendo a placa de Ø74 mm com a
# topologia antiga enquanto a placa real já era Ø40 com load switch — o
# mesmo tipo de envelhecimento silencioso que o BOM tinha.
"$CLI" pcb export step --output "$PROJ/kaelix.step" --subst-models --force \
  "$PROJ/kaelix.kicad_pcb" >/dev/null || falhou "export do STEP falhou"

secao "modelo mecânico"
if [ -x "$FC" ]; then
  saida=$("$FC" "$HW/check_3d.py" 2>/dev/null); rc=$?
  printf '%s\n' "$saida" | grep -vE "^FreeCAD |^\(C\) |free and open-source|^$"
  [ "$rc" -eq 0 ] || falhou "check_3d.py: modelo incompleto, interferência ou fora do vão"
else
  printf 'pulado: freecadcmd não encontrado\n'
fi

printf '\n%s\n' "-----------------------------------------------------------------"
if [ "$falhas" -eq 0 ]; then
  printf '\033[32mHARDWARE OK\033[0m  ERC e DRC limpos, derivados regenerados\n'
else
  printf '\033[31m%d ETAPA(S) FALHARAM\033[0m\n' "$falhas"
fi

printf '\nNão coberto por esta verificação:\n'
printf '  - se a pinagem confere com a peça física (só o datasheet responde)\n'
printf '  - numeração de pino do HT7333 em SOT-89-3, que varia por fabricante\n'
printf '  - desempenho de RF, consumo real e qualquer coisa medida em bancada\n'
printf '  - se o roteamento sobrevive a montagem: o gerador prova regras, nao fabricacao\n'
exit "$falhas"
