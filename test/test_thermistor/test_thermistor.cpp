#include <unity.h>

#include <cmath>

#include "thermistor.h"

using namespace kaelix::sensors;
using kaelix::Status;

void setUp(void) {}
void tearDown(void) {}

// =====================================================================
// Infraestrutura: como se testa uma guarda que aborta
// =====================================================================
//
// O modelo de erro do Kaelix tem dois modos (arquitetura §5): em
// desenvolvimento uma violação de contrato chama abort(); em produção ela
// devolve a sentinela e segue. São comportamentos diferentes indo para
// lugares diferentes — bancada e campo — e ambos precisam falhar na
// direção segura, então ambos precisam de teste.
//
// Testar o modo que aborta dentro do próprio processo é impossível: o
// abort() levaria a suíte inteira junto. A saída é o teste de morte
// (death test, o mesmo mecanismo do GoogleTest): a chamada roda num
// processo filho e o pai verifica como o filho terminou. É POSIX e só
// existe no ambiente `native`; nada disso é compilado para o ESP32.
//
// O ganho concreto: sem isso, a suíte teria de ser compilada inteira com
// -D KAELIX_PRODUCTION, e o build que a equipe realmente usa na bancada
// ficaria sem cobertura nenhuma das guardas.

#if defined(__unix__) || defined(__APPLE__)
#  define KAELIX_TEST_TEM_FORK 1
#  include <sys/wait.h>
#  include <unistd.h>
#  include <csignal>
#  include <cstdio>
#else
#  define KAELIX_TEST_TEM_FORK 0
#endif

// O teste de morte só faz sentido no build que realmente aborta; no build
// de produção o helper não é compilado, e é por isso que a condição é
// composta em vez de só `TEM_FORK`.
#define KAELIX_TEST_DEATH (KAELIX_TEST_TEM_FORK && KAELIX_ASSERT_ABORT)

#if KAELIX_TEST_DEATH
namespace {

// Como o filho terminou.
enum class Desfecho { Abortou, Retornou, Falhou };

Desfecho roda_isolado(float (*chamada)(Status*)) {
    std::fflush(nullptr); // senão o filho reemite o buffer de saída do pai
    const pid_t pid = fork();
    if (pid < 0) {
        return Desfecho::Falhou;
    }
    if (pid == 0) {
        // O texto da asserção é esperado neste caminho, não é um erro:
        // deixá-lo no terminal faria uma suíte verde parecer quebrada.
        (void)std::freopen("/dev/null", "w", stderr);
        Status st = Status::Ok;
        volatile float sink = chamada(&st); // volatile: nada de otimizar a chamada
        (void)sink;
        _exit(0);
    }
    int wstatus = 0;
    if (waitpid(pid, &wstatus, 0) < 0) {
        return Desfecho::Falhou;
    }
    if (WIFSIGNALED(wstatus) && WTERMSIG(wstatus) == SIGABRT) {
        return Desfecho::Abortou;
    }
    return WIFEXITED(wstatus) ? Desfecho::Retornou : Desfecho::Falhou;
}

} // namespace
#endif

namespace {

// Violação de contrato: em desenvolvimento precisa abortar, em produção
// precisa devolver a sentinela COM o status certo. Um único ponto de
// verificação para os dois modos.
void checa_violacao_de_contrato(float (*chamada)(Status*), Status esperado) {
#if KAELIX_ASSERT_ABORT
    // No modo que aborta, o único desfecho observável é o sinal: o
    // `esperado` só pode ser conferido no modo que retorna.
    (void)esperado;
#  if KAELIX_TEST_DEATH
    TEST_ASSERT_TRUE(roda_isolado(chamada) == Desfecho::Abortou);
#  else
    (void)chamada;
#  endif
#else
    Status st = Status::Ok;
    const float v = chamada(&st);
    TEST_ASSERT_TRUE(std::isnan(v));
    TEST_ASSERT_EQUAL_HEX8(kaelix::status_code(esperado), kaelix::status_code(st));
#endif
}

// Defeito de campo: NUNCA aborta, em modo nenhum. Um NTC com o fio
// rompido não é bug de software, e se a bancada abortasse a cada fio solto
// a equipe desligaria a asserção — que é como um modelo de erro morre.
void checa_defeito_de_campo(float (*chamada)(Status*), Status esperado) {
#if KAELIX_TEST_DEATH
    TEST_ASSERT_TRUE(roda_isolado(chamada) == Desfecho::Retornou);
#endif
    Status st = Status::Ok;
    const float v = chamada(&st);
    TEST_ASSERT_TRUE(std::isnan(v));
    TEST_ASSERT_EQUAL_HEX8(kaelix::status_code(esperado), kaelix::status_code(st));
}

} // namespace

// =====================================================================
// Caminho válido — estes valores NÃO PODEM mudar
// =====================================================================
// A validação acrescentada não tem licença para mexer em nenhum resultado
// dentro da faixa de operação. Estes casos são a barreira contra isso.

void test_celsius_at_nominal_resistance(void) {
    // R = R_nominal -> ln(1) = 0 -> T = T_nominal exatamente.
    Status st = Status::NotImplemented;
    float t = ntc_resistance_to_celsius(10000.0f, 10000.0f, 3950.0f, 25.0f, &st);
    TEST_ASSERT_FLOAT_WITHIN(0.001f, 25.0f, t);
    TEST_ASSERT_EQUAL_HEX8(kaelix::status_code(Status::Ok), kaelix::status_code(st));
}

void test_celsius_decreases_as_resistance_increases(void) {
    // NTC: resistência cai quando a temperatura sobe (coeficiente negativo).
    float t_low_r = ntc_resistance_to_celsius(5000.0f, 10000.0f, 3950.0f, 25.0f);
    float t_nominal = ntc_resistance_to_celsius(10000.0f, 10000.0f, 3950.0f, 25.0f);
    float t_high_r = ntc_resistance_to_celsius(20000.0f, 10000.0f, 3950.0f, 25.0f);
    TEST_ASSERT_TRUE(t_low_r > t_nominal);
    TEST_ASSERT_TRUE(t_nominal > t_high_r);
}

void test_celsius_sanity_bounds(void) {
    // Resistência bem abaixo da nominal -> temperatura bem acima de 25°C.
    float t_hot = ntc_resistance_to_celsius(1000.0f, 10000.0f, 3950.0f, 25.0f);
    TEST_ASSERT_TRUE(t_hot > 70.0f);

    // Resistência bem acima da nominal -> temperatura bem abaixo de 25°C.
    float t_cold = ntc_resistance_to_celsius(50000.0f, 10000.0f, 3950.0f, 25.0f);
    TEST_ASSERT_TRUE(t_cold < 5.0f);
}

void test_resistance_from_adc_midscale(void) {
    // adc_raw/adc_max = 0.5 -> R_ntc = R_fixed * 0.5/0.5 = R_fixed.
    float r = ntc_resistance_from_adc(2000, 4000, 10000.0f);
    TEST_ASSERT_FLOAT_WITHIN(1.0f, 10000.0f, r);
}

void test_resistance_from_adc_quarter_scale(void) {
    // ratio = 0.25 -> R_ntc = R_fixed * 0.25/0.75 = R_fixed/3.
    float r = ntc_resistance_from_adc(1000, 4000, 10000.0f);
    TEST_ASSERT_FLOAT_WITHIN(1.0f, 10000.0f / 3.0f, r);
}

void test_resistance_from_millivolts_matches_divider(void) {
    // Metade da alimentação -> NTC com a mesma resistência do fixo.
    float r = ntc_resistance_from_millivolts(1650, 3300, 10000.0f);
    TEST_ASSERT_FLOAT_WITHIN(1.0f, 10000.0f, r);
}

void test_from_adc_extremos_da_faixa_util_convertem_e_reportam_ok(void) {
    // Os limiares de curto/aberto precisam ficar FORA da faixa de operação
    // do equipamento, senão a proteção viraria censura de medição válida.
    // -40 °C e +125 °C são os extremos declarados; ambos têm de passar.
    struct Caso { uint16_t adc; float t_esperado; };
    const Caso casos[] = {
        {  142, 125.0f }, // ratio 0,0347 -> R ~359 ohm
        {  267, 100.0f },
        { 2048,  25.0f },
        { 3996, -40.0f }, // ratio 0,9758 -> R ~402 kohm
    };
    for (const Caso& c : casos) {
        Status st = Status::NotImplemented;
        const float r = ntc_resistance_from_adc(c.adc, 4095, 10000.0f, &st);
        TEST_ASSERT_EQUAL_HEX8(kaelix::status_code(Status::Ok), kaelix::status_code(st));
        const float t = ntc_resistance_to_celsius(r, 10000.0f, 3950.0f, 25.0f, &st);
        TEST_ASSERT_EQUAL_HEX8(kaelix::status_code(Status::Ok), kaelix::status_code(st));
        // 0,3 °C é a quantização de 1 LSB no extremo quente (ver thermistor.h).
        TEST_ASSERT_FLOAT_WITHIN(0.35f, c.t_esperado, t);
    }
}

// =====================================================================
// Defeitos de campo — as duas falhas mais prováveis do NTC
// =====================================================================

void test_from_adc_curto_reporta_thermistor_shorted(void) {
    checa_defeito_de_campo([](Status* st) { return ntc_resistance_from_adc(0, 4095, 10000.0f, st); },
                           Status::ThermistorShorted);
    checa_defeito_de_campo([](Status* st) { return ntc_resistance_from_adc(1, 4095, 10000.0f, st); },
                           Status::ThermistorShorted);
}

void test_from_adc_aberto_reporta_thermistor_open(void) {
    checa_defeito_de_campo([](Status* st) { return ntc_resistance_from_adc(4095, 4095, 10000.0f, st); },
                           Status::ThermistorOpen);
    checa_defeito_de_campo([](Status* st) { return ntc_resistance_from_adc(4094, 4095, 10000.0f, st); },
                           Status::ThermistorOpen);
}

void test_from_adc_acima_do_fundo_de_escala_reporta_thermistor_open(void) {
    // adc_raw > adc_max é eletricamente impossível no divisor; cai como
    // "aberto" porque ratio > 1 e é para lá que o hardware saturado vai.
    checa_defeito_de_campo([](Status* st) { return ntc_resistance_from_adc(5000, 4095, 10000.0f, st); },
                           Status::ThermistorOpen);
}

void test_from_adc_falha_de_campo_nao_produz_temperatura_plausivel(void) {
    // REGRESSÃO da falha que motivou esta mudança. O clamp em
    // [0,001; 0,999] devolvia +349,72 °C para curto e -77,17 °C para
    // circuito aberto — dois floats que o gateway recebia com CRC válido
    // e registrava como medição. O teste falha se qualquer um voltar.
    const uint16_t defeitos[] = {0, 1, 4094, 4095};
    for (uint16_t adc : defeitos) {
        Status st = Status::Ok;
        const float r = ntc_resistance_from_adc(adc, 4095, 10000.0f, &st);
        TEST_ASSERT_TRUE(kaelix::is_error(st));
        TEST_ASSERT_TRUE(std::isnan(r));

        // E a sentinela não pode virar número na etapa seguinte.
        Status st_t = Status::Ok;
        const float t = ntc_resistance_to_celsius(r, 10000.0f, 3950.0f, 25.0f, &st_t);
        TEST_ASSERT_TRUE(std::isnan(t));
        TEST_ASSERT_EQUAL_HEX8(kaelix::status_code(Status::NotFinite),
                               kaelix::status_code(st_t));
    }
}

void test_from_millivolts_extremos_sao_defeito_de_campo(void) {
    checa_defeito_de_campo([](Status* st) { return ntc_resistance_from_millivolts(0, 3300, 10000.0f, st); },
                           Status::ThermistorShorted);
    checa_defeito_de_campo([](Status* st) { return ntc_resistance_from_millivolts(3300, 3300, 10000.0f, st); },
                           Status::ThermistorOpen);
}

void test_to_celsius_entrada_nao_finita_propaga_sem_abortar(void) {
    // Propagação do sentinela: o chamador já foi avisado uma vez, abortar
    // aqui puniria quem herdou uma falha de campo. Vale para NaN e inf.
    checa_defeito_de_campo(
        [](Status* st) {
            return ntc_resistance_to_celsius(NTC_READING_INVALID, 10000.0f, 3950.0f, 25.0f, st);
        },
        Status::NotFinite);
    checa_defeito_de_campo(
        [](Status* st) {
            return ntc_resistance_to_celsius(INFINITY, 10000.0f, 3950.0f, 25.0f, st);
        },
        Status::NotFinite);
}

// =====================================================================
// Violações de contrato — bug de software, não defeito de campo
// =====================================================================

void test_from_adc_adc_max_zero_viola_contrato(void) {
    // Era 0/0 = NaN atravessando as guardas por clamp, que são cegas a NaN.
    checa_violacao_de_contrato([](Status* st) { return ntc_resistance_from_adc(0, 0, 10000.0f, st); },
                               Status::InvalidArgument);
}

void test_from_adc_r_fixed_nao_positivo_viola_contrato(void) {
    checa_violacao_de_contrato([](Status* st) { return ntc_resistance_from_adc(2000, 4095, 0.0f, st); },
                               Status::InvalidArgument);
    checa_violacao_de_contrato([](Status* st) { return ntc_resistance_from_adc(2000, 4095, -10000.0f, st); },
                               Status::InvalidArgument);
}

void test_from_millivolts_vcc_zero_viola_contrato(void) {
    checa_violacao_de_contrato([](Status* st) { return ntc_resistance_from_millivolts(1650, 0, 10000.0f, st); },
                               Status::InvalidArgument);
}

void test_to_celsius_resistencia_nao_positiva_viola_contrato(void) {
    // R = 0 devolvia exatamente -273,15 °C: o resultado de log(0) = -inf
    // com aparência de física.
    checa_violacao_de_contrato(
        [](Status* st) { return ntc_resistance_to_celsius(0.0f, 10000.0f, 3950.0f, 25.0f, st); },
        Status::InvalidArgument);
    checa_violacao_de_contrato(
        [](Status* st) { return ntc_resistance_to_celsius(-1.0f, 10000.0f, 3950.0f, 25.0f, st); },
        Status::InvalidArgument);
}

void test_to_celsius_r_nominal_nao_positivo_viola_contrato(void) {
    checa_violacao_de_contrato(
        [](Status* st) { return ntc_resistance_to_celsius(10000.0f, 0.0f, 3950.0f, 25.0f, st); },
        Status::InvalidArgument);
}

void test_to_celsius_beta_zero_viola_contrato(void) {
    // 1/beta divergia; a função devolvia nan sem dizer nada.
    checa_violacao_de_contrato(
        [](Status* st) { return ntc_resistance_to_celsius(10000.0f, 10000.0f, 0.0f, 25.0f, st); },
        Status::InvalidArgument);
}

void test_to_celsius_t_nominal_no_zero_absoluto_viola_contrato(void) {
    // t_nominal_c = -273,15 zera o kelvin e faz 1/t_nominal_k divergir.
    checa_violacao_de_contrato(
        [](Status* st) { return ntc_resistance_to_celsius(10000.0f, 10000.0f, 3950.0f, -273.15f, st); },
        Status::InvalidArgument);
}

void test_parametros_nao_finitos_violam_contrato(void) {
    checa_violacao_de_contrato(
        [](Status* st) { return ntc_resistance_to_celsius(10000.0f, 10000.0f, NAN, 25.0f, st); },
        Status::InvalidArgument);
    checa_violacao_de_contrato(
        [](Status* st) { return ntc_resistance_from_adc(2000, 4095, INFINITY, st); },
        Status::InvalidArgument);
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_celsius_at_nominal_resistance);
    RUN_TEST(test_celsius_decreases_as_resistance_increases);
    RUN_TEST(test_celsius_sanity_bounds);
    RUN_TEST(test_resistance_from_adc_midscale);
    RUN_TEST(test_resistance_from_adc_quarter_scale);
    RUN_TEST(test_resistance_from_millivolts_matches_divider);
    RUN_TEST(test_from_adc_extremos_da_faixa_util_convertem_e_reportam_ok);

    RUN_TEST(test_from_adc_curto_reporta_thermistor_shorted);
    RUN_TEST(test_from_adc_aberto_reporta_thermistor_open);
    RUN_TEST(test_from_adc_acima_do_fundo_de_escala_reporta_thermistor_open);
    RUN_TEST(test_from_adc_falha_de_campo_nao_produz_temperatura_plausivel);
    RUN_TEST(test_from_millivolts_extremos_sao_defeito_de_campo);
    RUN_TEST(test_to_celsius_entrada_nao_finita_propaga_sem_abortar);

    RUN_TEST(test_from_adc_adc_max_zero_viola_contrato);
    RUN_TEST(test_from_adc_r_fixed_nao_positivo_viola_contrato);
    RUN_TEST(test_from_millivolts_vcc_zero_viola_contrato);
    RUN_TEST(test_to_celsius_resistencia_nao_positiva_viola_contrato);
    RUN_TEST(test_to_celsius_r_nominal_nao_positivo_viola_contrato);
    RUN_TEST(test_to_celsius_beta_zero_viola_contrato);
    RUN_TEST(test_to_celsius_t_nominal_no_zero_absoluto_viola_contrato);
    RUN_TEST(test_parametros_nao_finitos_violam_contrato);
    return UNITY_END();
}
