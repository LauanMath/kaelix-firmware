#!/usr/bin/env bash
# =====================================================================
# Kaelix — análise estática
# =====================================================================
#
# Roda clang-tidy (.clang-tidy) e cppcheck sobre lib/, src/ e test/, e
# opcionalmente confere a formatação contra .clang-format.
#
# REGRA DESTE SCRIPT: ferramenta ausente é AVISO ALTO, nunca silêncio.
# Um script de verificação que sai com 0 porque não achou o analisador é
# pior que não ter script: ele produz um "passou" que não verificou
# nada. Aqui, cada ferramenta ausente imprime um bloco de aviso com o
# comando de instalação, e o resumo final diz explicitamente o que NÃO
# foi verificado. Com --require-tools, ausência vira erro (é o modo do
# CI, onde não existe "não estava instalado").
#
# O QUE CADA FERRAMENTA COBRE, E POR QUE AS DUAS
#   clang-tidy  entende C++ de verdade (AST + análise de fluxo do
#               clang-analyzer). É quem verifica as regras do
#               .clang-tidy: conversões estreitas, bounds, modelo de
#               erro, nomenclatura.
#   cppcheck    não precisa compilar. É a única das duas que consegue
#               olhar src/ nesta máquina, onde <Arduino.h>, <RadioLib.h>
#               e os cabeçalhos do ESP-IDF não existem. Acha coisas que
#               o clang não acha (estouro de buffer por índice
#               constante, valores não usados, redundância).
#
# LIMITE CONHECIDO — src/ e o clang-tidy
#   clang-tidy precisa dos cabeçalhos do alvo. Sem toolchain do ESP32
#   instalado, src/ não é analisável por ele, e este script diz isso em
#   vez de fingir. Para habilitar:
#       pio run -t compiledb      # gera compile_commands.json
#   Havendo compile_commands.json na raiz, o script passa a analisar
#   src/ também, automaticamente.
#
# USO
#   tools/run-static-analysis.sh                  # relatório, sai 0
#   tools/run-static-analysis.sh --strict         # achado => sai 1
#   tools/run-static-analysis.sh --require-tools  # ausência => sai 2
#   tools/run-static-analysis.sh --format         # confere .clang-format
#   tools/run-static-analysis.sh --only clang-tidy|cppcheck|format
#
# SAÍDA
#   0  nada bloqueou (achados podem existir; veja o resumo)
#   1  --strict e houve achado
#   2  --require-tools e faltou ferramenta, ou erro de uso
# =====================================================================

set -uo pipefail

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

STRICT=0
REQUIRE_TOOLS=0
RUN_FORMAT=0
ONLY=""

if [ -t 1 ]; then
    C_RESET=$'\033[0m'; C_BOLD=$'\033[1m'
    C_RED=$'\033[31m';  C_GREEN=$'\033[32m'; C_YELLOW=$'\033[33m'; C_DIM=$'\033[2m'
else
    C_RESET=""; C_BOLD=""; C_RED=""; C_GREEN=""; C_YELLOW=""; C_DIM=""
fi

die() { printf '%s[erro]%s %s\n' "$C_RED" "$C_RESET" "$*" >&2; exit 2; }
rule() { printf '%s%s%s\n' "$C_DIM" "-----------------------------------------------------------------" "$C_RESET"; }
head2() { printf '\n%s== %s ==%s\n' "$C_BOLD" "$*" "$C_RESET"; }

# Imprime o bloco de comentário do topo deste arquivo como ajuda: a
# documentação do script e o --help não podem divergir se são o mesmo
# texto.
show_help() {
    awk 'NR > 1 { if ($0 ~ /^#/) { sub(/^# ?/, ""); print } else { exit } }' "${BASH_SOURCE[0]}"
}

while [ $# -gt 0 ]; do
    case "$1" in
        --strict)        STRICT=1; shift ;;
        --require-tools) REQUIRE_TOOLS=1; shift ;;
        --format)        RUN_FORMAT=1; shift ;;
        --only)          [ $# -ge 2 ] || die "--only exige um valor"; ONLY="$2"; shift 2 ;;
        --only=*)        ONLY="${1#*=}"; shift ;;
        -h|--help)       show_help; exit 0 ;;
        *)               die "opção desconhecida: $1 (use --help)" ;;
    esac
done

case "$ONLY" in
    ""|clang-tidy|cppcheck|format) ;;
    *) die "--only precisa ser clang-tidy, cppcheck ou format" ;;
esac
[ "$ONLY" = "format" ] && RUN_FORMAT=1

# ---------------------------------------------------------------------
# Localização das ferramentas
# ---------------------------------------------------------------------
# Não basta procurar no PATH: no macOS o clang-format vem dentro das
# Command Line Tools e NÃO é exposto no PATH, e o LLVM do Homebrew é
# keg-only pelo mesmo motivo. Procurar nesses lugares é a diferença
# entre "a ferramenta não existe" e "a ferramenta existe e você não
# sabia" — e a primeira mensagem, se falsa, faz o projeto inteiro passar
# sem análise.
# ---------------------------------------------------------------------
EXTRA_DIRS="
/opt/homebrew/opt/llvm/bin
/usr/local/opt/llvm/bin
/opt/homebrew/bin
/usr/local/bin
/Library/Developer/CommandLineTools/usr/bin
"

find_tool() {
    local name="$1" override="${2:-}" d p
    if [ -n "$override" ]; then
        if command -v "$override" >/dev/null 2>&1; then command -v "$override"; return 0; fi
        if [ -x "$override" ]; then printf '%s\n' "$override"; return 0; fi
        return 1
    fi
    if command -v "$name" >/dev/null 2>&1; then command -v "$name"; return 0; fi
    for d in $EXTRA_DIRS; do
        p="$d/$name"
        [ -x "$p" ] && { printf '%s\n' "$p"; return 0; }
    done
    return 1
}

warn_missing() {
    local tool="$1" install="$2" cobre="$3"
    printf '%s\n' "$C_YELLOW"
    printf '  #################################################################\n'
    printf '  #  FERRAMENTA AUSENTE: %-40s#\n' "$tool"
    printf '  #################################################################\n'
    printf '%s' "$C_RESET"
    printf '  NÃO foi verificado: %s\n' "$cobre"
    printf '  Instalar com:       %s\n' "$install"
    printf '  Depois: tools/run-static-analysis.sh\n\n'
}

CLANG_TIDY_BIN="$(find_tool clang-tidy "${CLANG_TIDY:-}" || true)"
CPPCHECK_BIN="$(find_tool cppcheck "${CPPCHECK:-}" || true)"
CLANG_FORMAT_BIN="$(find_tool clang-format "${CLANG_FORMAT:-}" || true)"

# ---------------------------------------------------------------------
# Escopo
# ---------------------------------------------------------------------
INCLUDES=("-Itools/unity-shim")
for d in lib/*/; do
    [ -d "$d" ] && INCLUDES+=("-I${d%/}")
done
# KAELIX_TIDY_DEFINES permite analisar o build de produção:
#   KAELIX_TIDY_DEFINES=-DKAELIX_PRODUCTION tools/run-static-analysis.sh
# O padrão é o build de bancada, que é o que tem o caminho do abort().
EXTRA_DEFINES=(${KAELIX_TIDY_DEFINES:-})

TU_LIB=()
for f in lib/*/*.cpp; do [ -f "$f" ] && TU_LIB+=("$f"); done
TU_TEST=()
for f in test/*/*.cpp; do [ -f "$f" ] && TU_TEST+=("$f"); done
TU_SRC=()
for f in src/*.cpp src/*/*.cpp; do [ -f "$f" ] && TU_SRC+=("$f"); done

MISSING=0
FINDINGS=0
SUMMARY=""
add_summary() { SUMMARY="${SUMMARY}$1"$'\n'; }

# ---------------------------------------------------------------------
# clang-tidy
# ---------------------------------------------------------------------
if [ -z "$ONLY" ] || [ "$ONLY" = "clang-tidy" ]; then
    head2 "clang-tidy"
    if [ -z "$CLANG_TIDY_BIN" ]; then
        MISSING=$((MISSING + 1))
        warn_missing "clang-tidy" \
            "brew install llvm   (macOS)  |  apt install clang-tidy   (Debian/Ubuntu)" \
            "regras do .clang-tidy: conversões estreitas, bounds, modelo de erro, nomenclatura"
        add_summary "  clang-tidy .... ${C_YELLOW}AUSENTE — nada verificado${C_RESET}"
    else
        printf '  binário: %s\n' "$CLANG_TIDY_BIN"
        printf '  versão:  %s\n' "$("$CLANG_TIDY_BIN" --version 2>/dev/null | sed -n 's/.*version //p' | head -1)"
        # Sanidade do .clang-tidy: se a lista de Checks estivesse
        # corrompida (ver o comentário sobre YAML no .clang-tidy), o
        # número abaixo despencaria e o relatório limpo seria mentira.
        n_checks="$("$CLANG_TIDY_BIN" --list-checks 2>/dev/null | grep -c '^    ' || true)"
        printf '  checks ativos pelo .clang-tidy: %s\n' "${n_checks:-?}"
        if [ "${n_checks:-0}" -lt 100 ]; then
            printf '  %s[aviso]%s poucos checks ativos — confira o campo Checks do .clang-tidy\n' \
                   "$C_YELLOW" "$C_RESET"
        fi

        # ${arr[@]+...}: bash 3.2 + set -u trata array vazio como não definido.
        TIDY_TARGETS=(${TU_LIB[@]+"${TU_LIB[@]}"} ${TU_TEST[@]+"${TU_TEST[@]}"})
        if [ -f compile_commands.json ]; then
            printf '  compile_commands.json encontrado — src/ incluído na análise\n'
            TIDY_TARGETS+=(${TU_SRC[@]+"${TU_SRC[@]}"})
        else
            printf '  %s[nota]%s src/ FORA da análise do clang-tidy: sem compile_commands.json\n' \
                   "$C_YELLOW" "$C_RESET"
            printf '         e sem os cabeçalhos do ESP32 (Arduino.h, RadioLib.h, esp_sleep.h).\n'
            printf '         Gere com: pio run -t compiledb\n'
            add_summary "  clang-tidy .... ${C_YELLOW}src/ não analisado (sem compile_commands.json)${C_RESET}"
        fi

        rule
        [ ${#TIDY_TARGETS[@]} -gt 0 ] || die "nenhuma unidade de tradução para analisar"
        tidy_out="$("$CLANG_TIDY_BIN" --quiet "${TIDY_TARGETS[@]}" -- \
                        -std=gnu++17 ${EXTRA_DEFINES[@]+"${EXTRA_DEFINES[@]}"} \
                        "${INCLUDES[@]}" 2>&1)" || true
        printf '%s\n' "$tidy_out"
        n="$(printf '%s\n' "$tidy_out" | grep -cE '\[[a-z0-9-]+\]$|warning:|error:' || true)"
        FINDINGS=$((FINDINGS + n))
        if [ "$n" -eq 0 ]; then
            add_summary "  clang-tidy .... ${C_GREEN}0 achados${C_RESET}"
        else
            add_summary "  clang-tidy .... ${C_RED}${n} achados${C_RESET}"
        fi
    fi
fi

# ---------------------------------------------------------------------
# cppcheck
# ---------------------------------------------------------------------
if [ -z "$ONLY" ] || [ "$ONLY" = "cppcheck" ]; then
    head2 "cppcheck"
    if [ -z "$CPPCHECK_BIN" ]; then
        MISSING=$((MISSING + 1))
        warn_missing "cppcheck" \
            "brew install cppcheck   (macOS)  |  apt install cppcheck   (Debian/Ubuntu)" \
            "lib/ e src/ — a ÚNICA análise que hoje alcança src/ nesta máquina"
        add_summary "  cppcheck ...... ${C_YELLOW}AUSENTE — nada verificado${C_RESET}"
    else
        printf '  binário: %s\n' "$CPPCHECK_BIN"
        printf '  versão:  %s\n' "$("$CPPCHECK_BIN" --version 2>/dev/null)"

        # --platform=unix32: o alvo é um ESP32-S3, 32 bits little-endian.
        # Analisar com o modelo de 64 bits do host esconderia justamente
        # os estouros de int e as conversões que só aparecem no alvo.
        CPPCHECK_ARGS=(
            --std=c++17
            --platform=unix32
            --enable=warning,style,performance,portability
            --inline-suppr
            --suppress=missingInclude
            --suppress=missingIncludeSystem
            --suppress=unusedFunction
            --quiet
        )
        # --check-level=exhaustive só existe a partir do cppcheck 2.11.
        if "$CPPCHECK_BIN" --help 2>&1 | grep -q -- '--check-level'; then
            CPPCHECK_ARGS+=(--check-level=exhaustive)
        fi
        # unusedFunction fica suprimido porque a análise é por arquivo:
        # toda função pública de lib/ pareceria não usada.
        rule
        cppcheck_out="$("$CPPCHECK_BIN" "${CPPCHECK_ARGS[@]}" \
                            ${EXTRA_DEFINES[@]+"${EXTRA_DEFINES[@]}"} \
                            "${INCLUDES[@]}" \
                            lib/ src/ 2>&1)" || true
        printf '%s\n' "$cppcheck_out"
        n="$(printf '%s\n' "$cppcheck_out" | grep -cE '^[^ ].*: (error|warning|style|performance|portability):' || true)"
        FINDINGS=$((FINDINGS + n))
        if [ "$n" -eq 0 ]; then
            add_summary "  cppcheck ...... ${C_GREEN}0 achados${C_RESET} (lib/ + src/)"
        else
            add_summary "  cppcheck ...... ${C_RED}${n} achados${C_RESET} (lib/ + src/)"
        fi
    fi
fi

# ---------------------------------------------------------------------
# clang-format (opcional, --format)
# ---------------------------------------------------------------------
if [ "$RUN_FORMAT" -eq 1 ]; then
    head2 "clang-format (.clang-format)"
    if [ -z "$CLANG_FORMAT_BIN" ]; then
        MISSING=$((MISSING + 1))
        warn_missing "clang-format" \
            "brew install clang-format   |   já vem nas Command Line Tools do macOS" \
            "conformidade de formatação com .clang-format"
        add_summary "  clang-format .. ${C_YELLOW}AUSENTE — nada verificado${C_RESET}"
    else
        printf '  binário: %s\n' "$CLANG_FORMAT_BIN"
        printf '  divergência por arquivo (linhas que clang-format reescreveria):\n'
        total=0
        for f in lib/*/*.h lib/*/*.cpp src/*.h src/*.cpp src/*/*.h src/*/*.cpp test/*/*.cpp; do
            [ -f "$f" ] || continue
            n="$("$CLANG_FORMAT_BIN" --style=file "$f" | diff -u "$f" - | grep -cE '^[+-][^+-]' || true)"
            total=$((total + n))
            [ "$n" -gt 0 ] && printf '    %5d  %s\n' "$n" "$f"
        done
        printf '  total: %s linhas\n' "$total"
        printf '  %s[nota]%s ~170 dessas linhas são as duas tabelas alinhadas à mão\n' "$C_DIM" "$C_RESET"
        printf '         (enum Status, struct LoraPacket) — exceção documentada no .clang-format.\n'
        add_summary "  clang-format .. ${total} linhas divergentes (~170 são exceção conhecida)"
    fi
fi

# ---------------------------------------------------------------------
# Resumo
# ---------------------------------------------------------------------
printf '\n'
rule
printf '%sResumo da análise estática%s\n' "$C_BOLD" "$C_RESET"
printf '%s' "$SUMMARY"
rule

if [ "$MISSING" -gt 0 ]; then
    printf '%s%s ferramenta(s) ausente(s): a verificação está INCOMPLETA.%s\n' \
           "$C_YELLOW" "$MISSING" "$C_RESET"
    if [ "$REQUIRE_TOOLS" -eq 1 ]; then
        printf '%s--require-tools: tratando ausência como falha.%s\n' "$C_RED" "$C_RESET"
        exit 2
    fi
fi

if [ "$FINDINGS" -gt 0 ] && [ "$STRICT" -eq 1 ]; then
    printf '%s--strict: %s achado(s) => falha.%s\n' "$C_RED" "$FINDINGS" "$C_RESET"
    exit 1
fi

exit 0
