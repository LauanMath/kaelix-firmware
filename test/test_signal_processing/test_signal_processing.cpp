#include <unity.h>

#include <cmath>
#include <vector>

#include "signal_processing.h"

// Testes com sinais sintéticos (senoide de frequência/amplitude conhecidas)
// para validar a matemática do pipeline antes de termos o MPU6050 físico.
// TODO: quando o CSV do MAFAULDA estiver em data/, adicionar um teste que
// lê as amostras reais e compara com os valores de referência do dataset.

using namespace kaelix::sensors;

void setUp(void) {}
void tearDown(void) {}

static std::vector<float> make_sine(size_t n, float amplitude, float freq_hz, float sample_rate_hz) {
    std::vector<float> samples(n);
    for (size_t i = 0; i < n; ++i) {
        samples[i] = amplitude * std::sin(2.0f * float(M_PI) * freq_hz * float(i) / sample_rate_hz);
    }
    return samples;
}

void test_rms_of_sine_wave(void) {
    auto samples = make_sine(1024, 2.0f, 50.0f, 1000.0f);
    float expected_rms = 2.0f / std::sqrt(2.0f); // RMS de uma senoide pura = amplitude/sqrt(2)
    TEST_ASSERT_FLOAT_WITHIN(0.01f, expected_rms, compute_rms(samples.data(), samples.size()));
}

void test_rms_of_constant_signal(void) {
    std::vector<float> samples(100, 3.0f);
    TEST_ASSERT_FLOAT_WITHIN(1e-5f, 3.0f, compute_rms(samples.data(), samples.size()));
}

void test_crest_factor_of_sine_wave(void) {
    auto samples = make_sine(1024, 5.0f, 60.0f, 2000.0f);
    float expected_crest = std::sqrt(2.0f); // pico/RMS de uma senoide pura
    TEST_ASSERT_FLOAT_WITHIN(0.02f, expected_crest, compute_crest_factor(samples.data(), samples.size()));
}

void test_kurtosis_of_two_point_distribution(void) {
    // Distribuição de dois pontos (+1/-1 alternado): curtose de excesso
    // analítica = -2 (E[X^4]/E[X^2]^2 - 3 = 1/1 - 3).
    std::vector<float> samples;
    for (int i = 0; i < 500; ++i) {
        samples.push_back(1.0f);
        samples.push_back(-1.0f);
    }
    TEST_ASSERT_FLOAT_WITHIN(1e-4f, -2.0f, compute_kurtosis(samples.data(), samples.size()));
}

void test_kurtosis_of_uniform_like_signal(void) {
    // Rampa periódica ~ distribuição uniforme discreta: curtose de
    // excesso deve ser negativa (uniforme contínua ideal = -1.2).
    const size_t n = 1000;
    std::vector<float> samples(n);
    for (size_t i = 0; i < n; ++i) {
        samples[i] = float(i % 100) / 100.0f - 0.5f;
    }
    TEST_ASSERT_TRUE(compute_kurtosis(samples.data(), samples.size()) < 0.0f);
}

void test_dominant_frequency_of_sine_wave(void) {
    // sample_rate/n = 1 Hz por bin, então 50 Hz cai exatamente no bin 50
    // (sem espalhamento espectral / leakage).
    const size_t n = 1024;
    const float sample_rate_hz = 1024.0f;
    const float freq_hz = 50.0f;

    auto samples = make_sine(n, 1.0f, freq_hz, sample_rate_hz);
    float detected = dominant_frequency(samples.data(), samples.size(), sample_rate_hz);
    TEST_ASSERT_FLOAT_WITHIN(0.5f, freq_hz, detected);
}


// Regressão do achado no MAFAULDA: no espectro de ACELERAÇÃO o pico fica
// na componente de alta frequência (tipicamente um modo estrutural da
// montagem, igual com máquina sadia ou defeituosa); no de VELOCIDADE ele
// cai sobre a linha de 1x rotação, que é a assinatura de desbalanceamento.
//
// Amplitudes escolhidas para que as duas leituras discordem:
//   aceleração: 5,0 (200 Hz) > 1,0 (20 Hz)          -> pico em 200 Hz
//   velocidade: 1,0/20 = 0,050 > 5,0/200 = 0,025    -> pico em 20 Hz
void test_dominant_frequency_uses_velocity_not_acceleration(void) {
    const size_t n = 1024;
    const float fs = 1024.0f;

    auto low = make_sine(n, 1.0f, 20.0f, fs);
    auto high = make_sine(n, 5.0f, 200.0f, fs);
    std::vector<float> mixed(n);
    for (size_t i = 0; i < n; ++i) mixed[i] = low[i] + high[i];

    TEST_ASSERT_FLOAT_WITHIN(1.0f, 20.0f, dominant_frequency(mixed.data(), n, fs));
}

// Sem o limite inferior da banda, a ponderação 1/f faria qualquer
// componente de baixíssima frequência vencer. A ISO 10816-3 mede a partir
// de 10 Hz, e é esse corte que torna a reponderação utilizável.
void test_dominant_frequency_ignores_below_band(void) {
    const size_t n = 1024;
    const float fs = 1024.0f;

    auto sub = make_sine(n, 3.0f, 3.0f, fs);    // abaixo de 10 Hz
    auto in_band = make_sine(n, 1.0f, 50.0f, fs);
    std::vector<float> mixed(n);
    for (size_t i = 0; i < n; ++i) mixed[i] = sub[i] + in_band[i];

    TEST_ASSERT_FLOAT_WITHIN(1.0f, 50.0f, dominant_frequency(mixed.data(), n, fs));
}

void test_dominant_frequency_ignores_above_band(void) {
    const size_t n = 4096;
    const float fs = 8192.0f;

    auto acima = make_sine(n, 50.0f, 2000.0f, fs);  // acima de 1000 Hz
    auto in_band = make_sine(n, 1.0f, 60.0f, fs);
    std::vector<float> mixed(n);
    for (size_t i = 0; i < n; ++i) mixed[i] = acima[i] + in_band[i];

    TEST_ASSERT_FLOAT_WITHIN(2.0f, 60.0f, dominant_frequency(mixed.data(), n, fs));
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_rms_of_sine_wave);
    RUN_TEST(test_rms_of_constant_signal);
    RUN_TEST(test_crest_factor_of_sine_wave);
    RUN_TEST(test_kurtosis_of_two_point_distribution);
    RUN_TEST(test_kurtosis_of_uniform_like_signal);
    RUN_TEST(test_dominant_frequency_of_sine_wave);
    RUN_TEST(test_dominant_frequency_uses_velocity_not_acceleration);
    RUN_TEST(test_dominant_frequency_ignores_below_band);
    RUN_TEST(test_dominant_frequency_ignores_above_band);
    return UNITY_END();
}
