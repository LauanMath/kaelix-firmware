#include <unity.h>

#include <cstring>

#include "crc16.h"

using namespace kaelix::comms;

void setUp(void) {}
void tearDown(void) {}

// Testar a guarda de ponteiro nulo exige um processo separado: em build de
// desenvolvimento ela chama abort(), e um abort() dentro da suíte levaria
// a suíte junto. Mesmo mecanismo usado em test_thermistor — ver o bloco
// de justificativa lá. É POSIX, existe só no ambiente `native`, e nada
// disso é compilado para o ESP32.
#if defined(__unix__) || defined(__APPLE__)
#  define KAELIX_TEST_TEM_FORK 1
#  include <sys/wait.h>
#  include <unistd.h>
#  include <csignal>
#  include <cstdio>
#else
#  define KAELIX_TEST_TEM_FORK 0
#endif

// O teste de morte só faz sentido no build que realmente aborta.
#define KAELIX_TEST_DEATH (KAELIX_TEST_TEM_FORK && KAELIX_ASSERT_ABORT)

namespace {

#if KAELIX_TEST_DEATH
bool aborta(uint16_t (*chamada)(void)) {
    std::fflush(nullptr);
    const pid_t pid = fork();
    if (pid < 0) {
        return false;
    }
    if (pid == 0) {
        (void)std::freopen("/dev/null", "w", stderr); // o texto da asserção é esperado
        volatile uint16_t sink = chamada();
        (void)sink;
        _exit(0);
    }
    int wstatus = 0;
    if (waitpid(pid, &wstatus, 0) < 0) {
        return false;
    }
    return WIFSIGNALED(wstatus) && WTERMSIG(wstatus) == SIGABRT;
}
#endif

// Violação de contrato: aborta na bancada, devolve 0x0000 em campo.
void checa_violacao_de_contrato(uint16_t (*chamada)(void)) {
#if KAELIX_ASSERT_ABORT
#  if KAELIX_TEST_DEATH
    TEST_ASSERT_TRUE(aborta(chamada));
#  else
    (void)chamada;
#  endif
#else
    TEST_ASSERT_EQUAL_HEX16(0x0000, chamada());
#endif
}

} // namespace

// =====================================================================
// Caminho válido — estes valores NÃO PODEM mudar
// =====================================================================
// O CRC é um contrato de fio: emissor e receptor precisam concordar bit a
// bit. Qualquer alteração aqui invalida todo pacote já em trânsito e o
// decodificador do gateway.

void test_crc16_check_vector(void) {
    // Vetor de conferência padrão do CRC-16/CCITT-FALSE.
    const char* s = "123456789";
    TEST_ASSERT_EQUAL_HEX16(0x29B1, crc16_ccitt(reinterpret_cast<const uint8_t*>(s), 9));
}

void test_crc16_empty_is_initial_value(void) {
    // n == 0 com ponteiro nulo é legítimo: "nada a checar".
    TEST_ASSERT_EQUAL_HEX16(0xFFFF, crc16_ccitt(nullptr, 0));
}

void test_crc16_detects_single_bit_flip(void) {
    uint8_t a[8] = {0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08};
    uint8_t b[8];
    std::memcpy(b, a, sizeof(a));
    b[3] ^= 0x01; // um bit

    TEST_ASSERT_NOT_EQUAL(crc16_ccitt(a, 8), crc16_ccitt(b, 8));
}

void test_crc16_detects_byte_swap(void) {
    // Troca de ordem: um checksum por soma não pegaria isso.
    uint8_t a[4] = {0xDE, 0xAD, 0xBE, 0xEF};
    uint8_t b[4] = {0xAD, 0xDE, 0xBE, 0xEF};

    TEST_ASSERT_NOT_EQUAL(crc16_ccitt(a, 4), crc16_ccitt(b, 4));
}

void test_crc16_valores_de_referencia_do_pacote_de_20_bytes(void) {
    // Congela o CRC de um pacote do tamanho real do Kaelix. As conversões
    // explícitas exigidas por MISRA (5-0-6, 5-0-13) mudam o texto do
    // código e não podem mudar o número — é isto que prova.
    uint8_t buf[20];
    for (size_t i = 0; i < sizeof(buf); ++i) {
        buf[i] = static_cast<uint8_t>(i * 7 + 3);
    }
    TEST_ASSERT_EQUAL_HEX16(0x8CBB, crc16_ccitt(buf, 20));
    TEST_ASSERT_EQUAL_HEX16(0xD193, crc16_ccitt(buf, 1));
    TEST_ASSERT_EQUAL_HEX16(0xC71C, crc16_ccitt(buf, 9));
}

void test_crc16_no_comprimento_maximo_ainda_calcula(void) {
    // A cota superior é inclusiva: 255 bytes é o maior payload LoRa
    // legítimo e precisa passar, não ser recusado pela própria guarda.
    uint8_t buf[CRC16_MAX_LEN_BYTES];
    for (size_t i = 0; i < sizeof(buf); ++i) {
        buf[i] = static_cast<uint8_t>(i);
    }
    const uint16_t crc = crc16_ccitt(buf, CRC16_MAX_LEN_BYTES);
    // Não é o valor que importa aqui, e sim que a guarda não recusou o
    // caso legítimo do limite — devolver 0x0000 seria o sintoma disso.
    TEST_ASSERT_NOT_EQUAL(0x0000, crc);
}

// =====================================================================
// Violações de contrato
// =====================================================================

void test_crc16_ponteiro_nulo_com_n_maior_que_zero_viola_contrato(void) {
    // Sem a guarda isto é dereferência de nulo. Não é alcançável pelos
    // dois chamadores de hoje (ambos passam &packet), mas crc16 é função
    // pública de biblioteca destinada a ser reusada pelo gateway, onde os
    // dados vêm de um buffer de recepção fora do nosso controle.
    checa_violacao_de_contrato([] { return crc16_ccitt(nullptr, 1); });
    checa_violacao_de_contrato([] { return crc16_ccitt(nullptr, 20); });
}

void test_crc16_acima_da_cota_de_comprimento_viola_contrato(void) {
    // Dá ao laço um limite máximo provável: 255 * 8 = 2040 iterações.
    // Sem a cota, um campo de tamanho corrompido lido do ar faria o laço
    // percorrer megabytes de memória alheia antes de "terminar".
    static uint8_t buf[CRC16_MAX_LEN_BYTES + 1] = {0};
    checa_violacao_de_contrato([] { return crc16_ccitt(buf, CRC16_MAX_LEN_BYTES + 1); });
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_crc16_check_vector);
    RUN_TEST(test_crc16_empty_is_initial_value);
    RUN_TEST(test_crc16_detects_single_bit_flip);
    RUN_TEST(test_crc16_detects_byte_swap);
    RUN_TEST(test_crc16_valores_de_referencia_do_pacote_de_20_bytes);
    RUN_TEST(test_crc16_no_comprimento_maximo_ainda_calcula);
    RUN_TEST(test_crc16_ponteiro_nulo_com_n_maior_que_zero_viola_contrato);
    RUN_TEST(test_crc16_acima_da_cota_de_comprimento_viola_contrato);
    return UNITY_END();
}
