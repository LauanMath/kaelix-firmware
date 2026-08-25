#pragma once

// =====================================================================
// Kaelix — shim mínimo do Unity
// =====================================================================
//
// O QUE ISTO É: um substituto de emergência para o Unity, usado APENAS
// pelo caminho de contingência de tools/run-native-tests.sh, quando o
// PlatformIO não está instalado na máquina. Quando o PlatformIO existe,
// `pio test -e native` usa o Unity de verdade (test_framework = unity em
// platformio.ini) e este arquivo não é sequer incluído.
//
// O QUE ISTO NÃO É: uma reimplementação do Unity. Ele implementa
// exatamente as oito macros que test/ usa hoje, verificadas por
//
//     grep -ohE 'TEST_ASSERT[A-Z_0-9]*|UNITY_[A-Z_]+|RUN_TEST' test/*/*.cpp \
//         | sort | uniq -c
//
//     76  RUN_TEST
//     22  TEST_ASSERT_FLOAT_WITHIN
//     14  TEST_ASSERT_TRUE
//      7  TEST_ASSERT_EQUAL_HEX16
//      6  TEST_ASSERT_EQUAL_HEX8
//      4  UNITY_BEGIN / UNITY_END
//      3  TEST_ASSERT_NOT_EQUAL
//
// Mais TEST_ASSERT_FALSE e TEST_ASSERT_EQUAL_UINT16, que não aparecem
// hoje mas são o par imediato de duas das acima e custam duas linhas.
// Usar uma macro do Unity que não esteja aqui dá erro de compilação — e
// isso é deliberado: falhar alto é melhor que um teste que não roda.
//
// DIFERENÇAS DE COMPORTAMENTO EM RELAÇÃO AO UNITY (importam na leitura
// do resultado):
//
//   - o Unity ABORTA o caso de teste na primeira asserção que falha
//     (longjmp); este shim REGISTRA a falha e continua o caso. Uma
//     falha real pode portanto aparecer aqui como várias linhas. A
//     contagem de "Failures" conta asserções falhas, não casos falhos;
//   - não há TEST_IGNORE, TEST_PROTECT nem detecção de crash: se o
//     código sob teste chamar abort(), o processo inteiro morre e o
//     script acusa isso pelo código de saída (os testes de morte de
//     test_crc16/test_thermistor já fazem fork por causa disso);
//   - não há UNITY_OUTPUT_CHAR nem saída em cor.
//
// Nomes internos usam o prefixo `kaelix_unity_` e não `_u_`: um
// identificador que começa com sublinhado no escopo global é reservado
// à implementação ([lex.name]/3.2), e o projeto não usa nome reservado
// nem em código de teste.
// =====================================================================

#include <cmath>
#include <cstdio>

// Definidas por cada arquivo de teste, como no Unity de verdade.
void setUp(void);
void tearDown(void);

static int kaelix_unity_failures = 0;
static int kaelix_unity_tests = 0;
[[maybe_unused]] static const char* kaelix_unity_current = "";

#define UNITY_BEGIN() (kaelix_unity_failures = 0, kaelix_unity_tests = 0, 0)

#define UNITY_END()                                                                    \
    (std::printf("-----------------------\n%d Tests %d Failures 0 Ignored\n%s\n",      \
                 kaelix_unity_tests, kaelix_unity_failures,                            \
                 (kaelix_unity_failures == 0) ? "OK" : "FAIL"),                        \
     std::fflush(stdout), kaelix_unity_failures)

// Imprime uma linha por caso (o Unity só imprime as falhas). Num
// superloop de um disparo com 76 casos, ver o nome do caso que travou
// vale mais que a economia de linhas.
#define RUN_TEST(f)                                                                    \
    do {                                                                               \
        kaelix_unity_current = #f;                                                     \
        const int kaelix_unity_before = kaelix_unity_failures;                         \
        ++kaelix_unity_tests;                                                          \
        std::fflush(stdout);                                                           \
        setUp();                                                                       \
        f();                                                                           \
        tearDown();                                                                    \
        std::printf("  %-4s %s\n",                                                     \
                    (kaelix_unity_failures == kaelix_unity_before) ? "ok" : "FAIL",    \
                    #f);                                                               \
        std::fflush(stdout);                                                           \
    } while (0)

#define KAELIX_UNITY_FAIL_(fmt, ...)                                                   \
    do {                                                                               \
        std::printf("FAIL %s:%d %s -> " fmt "\n", __FILE__, __LINE__,                  \
                    kaelix_unity_current, __VA_ARGS__);                                \
        ++kaelix_unity_failures;                                                       \
    } while (0)

#define TEST_ASSERT_TRUE(c)                                                            \
    do {                                                                               \
        if (!(c)) {                                                                    \
            KAELIX_UNITY_FAIL_("TEST_ASSERT_TRUE(%s)", #c);                            \
        }                                                                              \
    } while (0)

#define TEST_ASSERT_FALSE(c)                                                           \
    do {                                                                               \
        if ((c)) {                                                                     \
            KAELIX_UNITY_FAIL_("TEST_ASSERT_FALSE(%s)", #c);                           \
        }                                                                              \
    } while (0)

// Ordem dos parâmetros igual à do Unity: (delta, esperado, obtido).
// Comparação em double para que TEST_ASSERT_FLOAT_WITHIN(0.0f, ...) —
// o teste de igualdade exata de bits usado em test_isolation_forest —
// continue sendo exato.
#define TEST_ASSERT_FLOAT_WITHIN(d, e, a)                                              \
    do {                                                                               \
        const double kaelix_unity_e = (e);                                             \
        const double kaelix_unity_a = (a);                                             \
        const double kaelix_unity_d = (d);                                             \
        if (!(std::fabs(kaelix_unity_e - kaelix_unity_a) <= kaelix_unity_d)) {         \
            KAELIX_UNITY_FAIL_("esperado %.9g, obtido %.9g (delta %.9g)",              \
                               kaelix_unity_e, kaelix_unity_a, kaelix_unity_d);        \
        }                                                                              \
    } while (0)

#define TEST_ASSERT_EQUAL_HEX16(e, a)                                                  \
    do {                                                                               \
        const unsigned kaelix_unity_e = static_cast<unsigned>(e);                      \
        const unsigned kaelix_unity_a = static_cast<unsigned>(a);                      \
        if (kaelix_unity_e != kaelix_unity_a) {                                        \
            KAELIX_UNITY_FAIL_("esperado 0x%04X, obtido 0x%04X", kaelix_unity_e,       \
                               kaelix_unity_a);                                        \
        }                                                                              \
    } while (0)

#define TEST_ASSERT_EQUAL_HEX8(e, a)                                                   \
    do {                                                                               \
        const unsigned kaelix_unity_e = static_cast<unsigned>(e) & 0xFFU;              \
        const unsigned kaelix_unity_a = static_cast<unsigned>(a) & 0xFFU;              \
        if (kaelix_unity_e != kaelix_unity_a) {                                        \
            KAELIX_UNITY_FAIL_("esperado 0x%02X, obtido 0x%02X", kaelix_unity_e,       \
                               kaelix_unity_a);                                        \
        }                                                                              \
    } while (0)

#define TEST_ASSERT_EQUAL_UINT16(e, a) TEST_ASSERT_EQUAL_HEX16(e, a)

#define TEST_ASSERT_NOT_EQUAL(e, a)                                                    \
    do {                                                                               \
        const long long kaelix_unity_e = static_cast<long long>(e);                    \
        const long long kaelix_unity_a = static_cast<long long>(a);                    \
        if (kaelix_unity_e == kaelix_unity_a) {                                        \
            KAELIX_UNITY_FAIL_("valores iguais (%lld), esperava-se diferentes",        \
                               kaelix_unity_e);                                        \
        }                                                                              \
    } while (0)
