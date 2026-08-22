#include "vibration.h"

#include "kaelix_status.h"
#include "signal_processing.h"

#include <cmath>
#include <cstring>

// TODO (passo 2 do roteiro): implementar a leitura I2C real do MPU6050
// (I2Cdevlib-MPU6050, endereço 0x68) dentro de `vibration_acquire`. O
// restante deste arquivo já está no formato final: enquanto a aquisição
// não existir, ela devolve Status::NotImplemented e NADA é escrito no
// buffer — nenhum caminho produz features a partir de dado fabricado.

namespace kaelix::sensors {
namespace {

// Buffer de amostras em escopo de arquivo, dimensionado em tempo de
// compilação: 512 floats = 2048 bytes de `.bss`. Substitui um
// `std::vector<float>` que alocava e liberava o mesmo tamanho a cada
// ciclo — ~35 mil pares malloc/free por ano de campo, sem nenhum recurso
// para diagnosticar fragmentação numa máquina sem ninguém por perto, e
// com `-fno-exceptions` uma falha de alocação vira abort() → pânico →
// boot loop a ~40 mA (JSF++ AV-206; MISRA C++ 18-4-1).
float s_samples[VIBRATION_MAX_SAMPLES];

// Rascunho da FFT. Existe aqui — e não se usa a sobrecarga de
// `dominant_frequency` que traz o próprio rascunho estático — porque L2
// precisa da CAUSA da falha para nunca transmitir um veredito fabricado
// (§5): a sobrecarga simples devolve 0.0f sem dizer por quê, enquanto
// `dominant_frequency_scratch` devolve o Status. Custo: 2 × 2048 bytes de
// `.bss`, os mesmos que a sobrecarga simples usaria; como nada mais neste
// firmware a chama, o rascunho interno de lib/ deixa de ser referenciado.
float s_fft_re[VIBRATION_MAX_SAMPLES];
float s_fft_im[VIBRATION_MAX_SAMPLES];

// O init ainda não tem o que inicializar, mas o estado existe para que
// `vibration_read_features` possa recusar uma leitura antes dele — a
// ordem init → read é contrato, e contrato não verificado é convenção.
bool s_initialized = false;

constexpr bool is_power_of_two(uint16_t n) {
    return n != 0U && (static_cast<uint32_t>(n) & static_cast<uint32_t>(n - 1U)) == 0U;
}

} // namespace

kaelix::Status vibration_init() {
    s_initialized = false;

    // TODO (Fase 2): reset do MPU6050, conferência do WHO_AM_I (0x68),
    // fundo de escala do acelerômetro, sample-rate divider e — decisivo —
    // o DLPF ABAIXO de fs/2. Sem filtro anti-aliasing configurado, todo
    // conteúdo acima de 500 Hz dobra para dentro da banda de análise e
    // fica indistinguível de sinal legítimo; a validade da feature
    // `dominant_freq_hz` depende dessa configuração, que é decisão de
    // projeto e não detalhe de driver.
    //
    // Devolver NotImplemented (e não `false`, e muito menos Ok) é o que
    // impede o ciclo de seguir como se houvesse acelerômetro: o código
    // ainda não escrito precisa falhar alto, não silenciar.
    return kaelix::Status::NotImplemented;
}

kaelix::Status vibration_acquire(float* dst, uint16_t n, float* out_sample_rate_hz) {
    KAELIX_REQUIRE(dst != nullptr, kaelix::Status::NullPointer);
    KAELIX_REQUIRE(out_sample_rate_hz != nullptr, kaelix::Status::NullPointer);
    KAELIX_REQUIRE(n >= VIBRATION_MIN_SAMPLES && n <= VIBRATION_MAX_SAMPLES,
                   kaelix::Status::LengthOutOfRange);
    KAELIX_REQUIRE(is_power_of_two(n), kaelix::Status::LengthNotPowerOfTwo);
    KAELIX_REQUIRE(s_initialized, kaelix::Status::NotInitialized);

    // TODO (Fase 2): rajada de `n` amostras pelo FIFO do MPU6050, com o
    // sample-rate divider do próprio sensor (clock do sensor, não do
    // ESP32) ou por timer de hardware — não por laço de polling, que fica
    // sujeito à preempção do FreeRTOS e à latência variável do I2C.
    // Medir o intervalo real com esp_timer_get_time() nas duas pontas,
    // escrever fs_efetivo = (n-1)/Δt em *out_sample_rate_hz e devolver
    // Status::SampleRateMissed se o desvio exceder
    // VIBRATION_SAMPLE_RATE_TOLERANCE. O laço tem cota superior provável:
    // `n`, já validado acima.
    return kaelix::Status::NotImplemented;
}

kaelix::Status vibration_features_from_samples(const float* samples, uint16_t n,
                                               float sample_rate_hz,
                                               VibrationFeatures* out) {
    KAELIX_REQUIRE(samples != nullptr, kaelix::Status::NullPointer);
    KAELIX_REQUIRE(out != nullptr, kaelix::Status::NullPointer);
    KAELIX_REQUIRE(n >= VIBRATION_MIN_SAMPLES && n <= VIBRATION_MAX_SAMPLES,
                   kaelix::Status::LengthOutOfRange);
    KAELIX_REQUIRE(is_power_of_two(n), kaelix::Status::LengthNotPowerOfTwo);
    KAELIX_REQUIRE(std::isfinite(sample_rate_hz) && sample_rate_hz > 0.0f,
                   kaelix::Status::InvalidArgument);

    // Uma única varredura, cota superior `n`, responde às duas perguntas
    // que precisam ser feitas ANTES de qualquer matemática.
    bool all_finite = true;
    bool all_identical = true;
    for (uint16_t i = 0U; i < n; ++i) {
        if (!std::isfinite(samples[i])) {
            all_finite = false;
        }
        // Comparação bit a bit, e não `==`: igualdade de ponto flutuante é
        // proibida (MISRA C++ 6-2-2) e aqui seria além disso a pergunta
        // errada — o que se quer saber é se o sensor devolveu literalmente
        // o mesmo padrão de bits, não se dois valores são numericamente
        // próximos.
        if (std::memcmp(&samples[i], &samples[0], sizeof(float)) != 0) {
            all_identical = false;
        }
    }

    // Falhas de campo: não abortam em build nenhum. São o motivo de o
    // dispositivo existir, e acontecem com o firmware correto.
    if (!all_finite) {
        return kaelix::Status::NotFinite;
    }
    if (all_identical) {
        // N amostras bit a bit idênticas é sensor congelado (I2C devolvendo
        // o mesmo registrador, sensor sem clock, buffer nunca escrito), não
        // máquina parada: um acelerômetro vivo tem ruído no bit menos
        // significativo mesmo em repouso. Sem esta verificação, um buffer
        // de zeros vira RMS = 0 / curtose = 0 e sai como "máquina sadia".
        return kaelix::Status::SensorStuck;
    }

    // Calculado em locais e só depois publicado: nenhum caminho de erro
    // deixa `*out` meio escrito.
    const float rms = compute_rms(samples, n);
    const float kurtosis = compute_kurtosis(samples, n);
    const float crest_factor = compute_crest_factor(samples, n);

    float dominant_freq_hz = 0.0f;
    const FftScratch scratch{ s_fft_re, s_fft_im, VIBRATION_MAX_SAMPLES };
    KAELIX_CHECK(dominant_frequency_scratch(samples, n, sample_rate_hz,
                                            DOMINANT_BAND_LO_HZ, DOMINANT_BAND_HI_HZ,
                                            scratch, &dominant_freq_hz));

    if (!std::isfinite(rms) || !std::isfinite(kurtosis) ||
        !std::isfinite(crest_factor) || !std::isfinite(dominant_freq_hz)) {
        // Toda comparação com NaN é falsa, então uma feature não finita
        // atravessaria o limiar de anomalia como "Normal". Ela morre aqui.
        return kaelix::Status::NotFinite;
    }

    out->rms = rms;
    out->kurtosis = kurtosis;
    out->crest_factor = crest_factor;
    out->dominant_freq_hz = dominant_freq_hz;
    return kaelix::Status::Ok;
}

kaelix::Status vibration_read_features(uint16_t n, VibrationFeatures* out) {
    KAELIX_REQUIRE(out != nullptr, kaelix::Status::NullPointer);
    KAELIX_REQUIRE(n >= VIBRATION_MIN_SAMPLES && n <= VIBRATION_MAX_SAMPLES,
                   kaelix::Status::LengthOutOfRange);
    KAELIX_REQUIRE(is_power_of_two(n), kaelix::Status::LengthNotPowerOfTwo);

    // A taxa efetiva vem da aquisição; a constante é apenas o valor
    // inicial, para que nenhum caminho use uma taxa não escrita.
    float sample_rate_hz = VIBRATION_SAMPLE_RATE_HZ;
    KAELIX_CHECK(vibration_acquire(s_samples, n, &sample_rate_hz));
    return vibration_features_from_samples(s_samples, n, sample_rate_hz, out);
}

} // namespace kaelix::sensors
