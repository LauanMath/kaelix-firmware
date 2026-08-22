#!/usr/bin/env bash
# =====================================================================
# Kaelix — execução das suítes nativas de lib/
# =====================================================================
#
# Ponto de entrada único para rodar, no host, os testes dos módulos de
# matemática pura de lib/. É o que a banca deve conseguir executar numa
# máquina limpa, e o que um CI executa sem hardware.
#
# DOIS CAMINHOS, MESMO CONTRATO
#
#   1. PlatformIO presente  -> `pio test -e native`, com o Unity de
#      verdade (test_framework = unity em platformio.ini). É o caminho
#      canônico: o mesmo runner que roda no CI e o mesmo que roda os
#      testes no alvo quando houver hardware.
#
#   2. PlatformIO ausente   -> g++ direto, com o shim de Unity em
#      tools/unity-shim/. É contingência, não alternativa: o shim
#      implementa só as macros que test/ usa e não tem longjmp, então
#      uma asserção falha não interrompe o caso (ver o cabeçalho do
#      shim). O veredito passa/falha é o mesmo; o detalhe do relatório é
#      menos rico.
#
# DOIS MODOS DE BUILD, E POR QUE OS DOIS IMPORTAM
#
#   dev  (padrão do compilador)   KAELIX_ASSERT_ABORT == 1
#        Violação de contrato chama abort(). É o build de bancada.
#        Os testes de morte (fork + waitpid em test_crc16 e
#        test_thermistor) só têm o que verificar aqui.
#
#   prod (-D KAELIX_PRODUCTION)   KAELIX_ASSERT_ABORT == 0
#        Violação devolve Status e o ciclo segue degradado. É o build
#        que vai para a máquina.
#
#   Não é a mesma suíte compilada duas vezes: test_isolation_forest tem
#   um bloco `#if !KAELIX_ASSERT_ABORT` com 6 casos que SÓ existem em
#   produção (32 casos em dev, 38 em prod). Rodar só um dos modos deixa
#   metade do modelo de erro sem verificação — e é justamente o modo que
#   fica oito meses sozinho numa máquina.
#
# USO
#   tools/run-native-tests.sh                 # tudo, nos dois modos
#   tools/run-native-tests.sh --mode dev      # só bancada
#   tools/run-native-tests.sh --mode prod     # só produção
#   tools/run-native-tests.sh --filter crc16  # um módulo
#   tools/run-native-tests.sh --gcc           # ignora o PlatformIO
#   tools/run-native-tests.sh --no-werror     # não trata aviso como erro
#
# SAÍDA
#   0  todas as suítes compilaram sem aviso e todos os casos passaram
#   1  compilação, aviso ou caso de teste falhou
#   2  erro de uso ou ambiente sem compilador
# =====================================================================

set -euo pipefail

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

MODE="both"
FILTER=""
FORCE_GCC=0
WERROR=1

# ---------------------------------------------------------------------
# Cores só quando a saída é um terminal. Num log de CI, código ANSI é
# lixo que atrapalha o grep.
# ---------------------------------------------------------------------
if [ -t 1 ]; then
    C_RESET=$'\033[0m'; C_BOLD=$'\033[1m'
    C_RED=$'\033[31m';  C_GREEN=$'\033[32m'; C_YELLOW=$'\033[33m'; C_DIM=$'\033[2m'
else
    C_RESET=""; C_BOLD=""; C_RED=""; C_GREEN=""; C_YELLOW=""; C_DIM=""
fi

die() { printf '%s[erro]%s %s\n' "$C_RED" "$C_RESET" "$*" >&2; exit 2; }
info() { printf '%s\n' "$*"; }
rule() { printf '%s%s%s\n' "$C_DIM" "-----------------------------------------------------------------" "$C_RESET"; }

# Imprime o bloco de comentário do topo deste arquivo como ajuda: a
# documentação do script e o --help não podem divergir se são o mesmo
# texto.
usage() {
    awk 'NR > 1 { if ($0 ~ /^#/) { sub(/^# ?/, ""); print } else { exit } }' "${BASH_SOURCE[0]}"
    exit "${1:-0}"
}

while [ $# -gt 0 ]; do
    case "$1" in
        --mode)      [ $# -ge 2 ] || die "--mode exige um valor (dev|prod|both)"; MODE="$2"; shift 2 ;;
        --mode=*)    MODE="${1#*=}"; shift ;;
        --filter)    [ $# -ge 2 ] || die "--filter exige o nome de um módulo"; FILTER="$2"; shift 2 ;;
        --filter=*)  FILTER="${1#*=}"; shift ;;
        --gcc)       FORCE_GCC=1; shift ;;
        --no-werror) WERROR=0; shift ;;
        -h|--help)   usage 0 ;;
        *)           die "opção desconhecida: $1 (use --help)" ;;
    esac
done

case "$MODE" in
    dev|prod|both) ;;
    *) die "--mode precisa ser dev, prod ou both (recebi '$MODE')" ;;
esac

MODES=""
case "$MODE" in
    dev)  MODES="dev" ;;
    prod) MODES="prod" ;;
    both) MODES="dev prod" ;;
esac

# ---------------------------------------------------------------------
# Descoberta dos módulos
# ---------------------------------------------------------------------
# Nada de lista fixa: um módulo novo em lib/ com sua suíte em test/ passa
# a rodar sozinho. A convenção verificada é a do PlatformIO —
# test/test_<mod>/ é a suíte de lib/<mod>/ — e ela é CHECADA, não
# suposta: se a suíte existir sem a biblioteca correspondente, o script
# falha em vez de pular em silêncio (uma suíte que não roda é pior que
# uma suíte que não existe).
# ---------------------------------------------------------------------
discover_modules() {
    local d name
    for d in test/test_*/; do
        [ -d "$d" ] || continue
        name="$(basename "$d")"
        name="${name#test_}"
        [ -f "test/test_${name}/test_${name}.cpp" ] || continue
        if [ -n "$FILTER" ] && [ "$name" != "$FILTER" ]; then
            continue
        fi
        printf '%s\n' "$name"
    done
}

MODULES="$(discover_modules)"
[ -n "$MODULES" ] || die "nenhuma suíte encontrada em test/ (filtro: '${FILTER:-nenhum}')"

# ---------------------------------------------------------------------
# Caminho 1 — PlatformIO
# ---------------------------------------------------------------------
run_with_platformio() {
    local pio="$1" mode rc=0 overall=0
    info "${C_BOLD}Runner:${C_RESET} PlatformIO ($($pio --version 2>/dev/null | head -1))"
    info "${C_BOLD}Ambiente:${C_RESET} native (Unity real)"
    rule
    for mode in $MODES; do
        info "${C_BOLD}== modo ${mode} ==${C_RESET}"
        if [ "$mode" = "prod" ]; then
            # PLATFORMIO_BUILD_FLAGS é acrescentado ao build_flags do
            # ambiente, sem editar platformio.ini.
            PLATFORMIO_BUILD_FLAGS="-D KAELIX_PRODUCTION" "$pio" test -e native || rc=$?
        else
            "$pio" test -e native || rc=$?
        fi
        if [ "$rc" -ne 0 ]; then
            overall=1
            printf '%s[falhou]%s pio test -e native (modo %s) saiu com %s\n' \
                   "$C_RED" "$C_RESET" "$mode" "$rc"
        fi
        rc=0
    done
    return "$overall"
}

# ---------------------------------------------------------------------
# Caminho 2 — g++ direto
# ---------------------------------------------------------------------
SHIM_DIR="tools/unity-shim"
BUILD_DIR="${KAELIX_BUILD_DIR:-.pio/native-fallback}"   # .pio/ já está no .gitignore

# -Wall -Wextra -Wpedantic com -Werror: hoje as oito combinações
# (4 módulos x 2 modos) compilam sem um único aviso, então tratar aviso
# como erro não é aspiracional — é o estado atual, e o portão existe para
# que continue sendo. `--no-werror` é a saída para quem está no meio de
# uma refatoração.
CXXFLAGS_BASE="-std=gnu++17 -Wall -Wextra -Wpedantic"

run_with_gcc() {
    local cxx="$1" mode mod rc bin src_list out
    local overall=0 runs=0 cases_total=0 fails_total=0
    local -a includes=() sources=() defines=() warnflags=()

    includes=("-I${SHIM_DIR}")
    local d
    for d in lib/*/; do
        [ -d "$d" ] || continue
        includes+=("-I${d%/}")   # inclui também os headers-only (kaelix_status)
    done

    [ "$WERROR" -eq 1 ] && warnflags=(-Werror) || warnflags=()

    mkdir -p "$BUILD_DIR"

    local motivo="contingência — PlatformIO ausente"
    [ "$FORCE_GCC" -eq 1 ] && motivo="--gcc: PlatformIO ignorado por opção"
    info "${C_BOLD}Runner:${C_RESET} g++ direto (${motivo})"
    info "${C_BOLD}Compilador:${C_RESET} $($cxx --version 2>/dev/null | head -1)"
    info "${C_BOLD}Flags:${C_RESET} ${CXXFLAGS_BASE} ${warnflags[*]+${warnflags[*]}}"
    info "${C_BOLD}Unity:${C_RESET} shim mínimo em ${SHIM_DIR}/unity.h"
    info "${C_BOLD}Build:${C_RESET} ${BUILD_DIR}"
    rule

    for mode in $MODES; do
        info "${C_BOLD}== modo ${mode} ==${C_RESET}"
        if [ "$mode" = "prod" ]; then
            defines=(-DKAELIX_PRODUCTION)
        else
            defines=()
        fi

        for mod in $MODULES; do
            [ -d "lib/${mod}" ] || {
                printf '%s[falhou]%s suíte test/test_%s existe, mas lib/%s não\n' \
                       "$C_RED" "$C_RESET" "$mod" "$mod"
                overall=1
                continue
            }

            # Fontes do módulo sob teste. Um módulo header-only (sem
            # .cpp) é legítimo — kaelix_status é assim — e nesse caso só
            # o arquivo de teste é compilado.
            sources=()
            for src_list in lib/"${mod}"/*.cpp; do
                [ -f "$src_list" ] && sources+=("$src_list")
            done

            bin="${BUILD_DIR}/${mod}-${mode}"
            runs=$((runs + 1))

            # ${arr[@]+"${arr[@]}"}: o bash 3.2 que a Apple distribui
            # trata "${arr[@]}" de um array VAZIO como variável não
            # definida sob `set -u`. Sem esta forma, o modo dev (que não
            # tem -D nenhum) morre antes de compilar.
            if ! out="$("$cxx" $CXXFLAGS_BASE \
                            ${warnflags[@]+"${warnflags[@]}"} \
                            ${defines[@]+"${defines[@]}"} \
                            "${includes[@]}" \
                            "test/test_${mod}/test_${mod}.cpp" \
                            ${sources[@]+"${sources[@]}"} \
                            -o "$bin" 2>&1)"; then
                printf '%s[compilação falhou]%s %s (%s)\n' "$C_RED" "$C_RESET" "$mod" "$mode"
                printf '%s\n' "$out"
                overall=1
                continue
            fi
            # Com -Werror isto não deveria acontecer; sem ele, o aviso
            # aparece mesmo assim, em vez de sumir no buffer.
            if [ -n "$out" ]; then
                printf '%s[avisos]%s %s (%s)\n%s\n' "$C_YELLOW" "$C_RESET" "$mod" "$mode" "$out"
            fi

            rc=0
            out="$("$bin" 2>&1)" || rc=$?

            local n_cases n_fails
            n_cases="$(printf '%s\n' "$out" | sed -n 's/^\([0-9][0-9]*\) Tests .*/\1/p' | tail -1)"
            n_fails="$(printf '%s\n' "$out" | sed -n 's/^[0-9][0-9]* Tests \([0-9][0-9]*\) Failures.*/\1/p' | tail -1)"
            : "${n_cases:=0}" "${n_fails:=0}"
            cases_total=$((cases_total + n_cases))
            fails_total=$((fails_total + n_fails))

            if [ "$rc" -eq 0 ] && [ "$n_fails" -eq 0 ] && [ "$n_cases" -gt 0 ]; then
                printf '  %sok%s   %-20s %-4s %3s casos\n' \
                       "$C_GREEN" "$C_RESET" "$mod" "$mode" "$n_cases"
            else
                # Um binário que morre por sinal (abort não capturado)
                # sai com rc >= 128 e sem linha de resumo — por isso o
                # veredito olha rc E a contagem, nunca só uma das duas.
                printf '  %sFALHOU%s %-20s %-4s rc=%s casos=%s falhas=%s\n' \
                       "$C_RED" "$C_RESET" "$mod" "$mode" "$rc" "$n_cases" "$n_fails"
                printf '%s\n' "$out" | sed 's/^/      | /'
                overall=1
            fi
        done
    done

    rule
    if [ "$overall" -eq 0 ]; then
        printf '%s%sTUDO PASSOU%s  %s execuções (suíte x modo), %s casos, 0 falhas\n' \
               "$C_BOLD" "$C_GREEN" "$C_RESET" "$runs" "$cases_total"
    else
        printf '%s%sFALHOU%s  %s execuções (suíte x modo), %s casos, %s asserções falhas\n' \
               "$C_BOLD" "$C_RED" "$C_RESET" "$runs" "$cases_total" "$fails_total"
    fi
    return "$overall"
}

# ---------------------------------------------------------------------
# Seleção do caminho
# ---------------------------------------------------------------------
PIO_BIN=""
if [ "$FORCE_GCC" -eq 0 ]; then
    for candidate in pio platformio "$HOME/.platformio/penv/bin/pio"; do
        if command -v "$candidate" >/dev/null 2>&1; then
            PIO_BIN="$candidate"
            break
        elif [ -x "$candidate" ]; then
            PIO_BIN="$candidate"
            break
        fi
    done
fi

info "${C_BOLD}Kaelix — suítes nativas${C_RESET}  (repo: $REPO_ROOT)"
info "Módulos: $(printf '%s ' $MODULES) | modos: $(printf '%s ' $MODES)"
rule

if [ -n "$PIO_BIN" ]; then
    run_with_platformio "$PIO_BIN"
    exit $?
fi

if [ "$FORCE_GCC" -eq 0 ]; then
    printf '%s[aviso]%s PlatformIO não encontrado no PATH — usando o caminho de contingência.\n' \
           "$C_YELLOW" "$C_RESET"
    printf '        O caminho canônico é `pio test -e native` (Unity real). Para instalar:\n'
    printf '        pipx install platformio   ou   pip install -U platformio\n'
    rule
fi

[ -f "${SHIM_DIR}/unity.h" ] || die "shim do Unity ausente: ${SHIM_DIR}/unity.h"

CXX_BIN="${CXX:-}"
if [ -z "$CXX_BIN" ]; then
    for candidate in g++ c++ clang++; do
        if command -v "$candidate" >/dev/null 2>&1; then
            CXX_BIN="$candidate"
            break
        fi
    done
fi
[ -n "$CXX_BIN" ] || die "nenhum compilador C++ encontrado (defina CXX=...)"

run_with_gcc "$CXX_BIN"
