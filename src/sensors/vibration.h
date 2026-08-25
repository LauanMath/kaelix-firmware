#pragma once

#include <cstdint>

#include "kaelix_status.h"
#include "signal_processing.h"

namespace kaelix::sensors {

// O dimensionamento da cadeia de vibração tem UMA fonte: as constantes de
// lib/signal_processing (§4 do documento de arquitetura). Este módulo não
// escolhe um tamanho próprio — ele deriva o seu do mesmo lugar de onde a
// FFT deriva o dela, para que os dois não possam divergir.
inline constexpr uint16_t VIBRATION_MAX_SAMPLES = static_cast<uint16_t>(FFT_MAX_N);
inline constexpr uint16_t VIBRATION_MIN_SAMPLES = static_cast<uint16_t>(FFT_MIN_N);

static_assert(FFT_MAX_N <= UINT16_MAX, "o contador de amostras é uint16_t");
static_assert((VIBRATION_MAX_SAMPLES & (VIBRATION_MAX_SAMPLES - 1)) == 0,
              "FFT radix-2 exige potência de 2");

// Taxa ALVO de amostragem. É uma premissa de projeto, não uma medida: o
// eixo de frequência da FFT sai daqui, então um erro sistemático na taxa
// desloca proporcionalmente toda a frequência dominante estimada, e o
// jitter espalha o pico. Por isso `vibration_acquire` devolve a taxa
// EFETIVA em vez de deixar o chamador presumir esta — ver o comentário da
// função e Status::SampleRateMissed.
inline constexpr float VIBRATION_SAMPLE_RATE_HZ = 1000.0f;

// Tolerância da taxa efetiva contra a alvo. Acima disso a feature
// `dominant_freq_hz` deixa de corresponder ao eixo com que o modelo foi
// treinado, e o score passa a ser calculado sobre um espectro deslocado.
inline constexpr float VIBRATION_SAMPLE_RATE_TOLERANCE = 0.02f; // 2%

struct VibrationFeatures {
    float rms;
    float kurtosis;
    float crest_factor;
    float dominant_freq_hz;
};

// Inicializa o MPU6050 via I2C (endereço 0x68).
[[nodiscard]] kaelix::Status vibration_init();

// Preenche `dst` com `n` amostras do acelerômetro e escreve em
// `out_sample_rate_hz` a taxa EFETIVA medida durante a rajada.
//
// Em erro, `dst` NÃO é escrito. Esta é a regra que motivou partir a
// função em duas: a versão anterior preenchia o buffer com zeros e
// devolvia features calculadas sobre eles, com a mesma assinatura de uma
// medição real. RMS = 0, curtose = 0, fator de crista = 0 é um vetor que
// o Isolation Forest classifica como "máquina sadia" — indistinguível,
// byte a byte, de uma máquina parada de verdade.
[[nodiscard]] kaelix::Status vibration_acquire(float* dst, uint16_t n,
                                               float* out_sample_rate_hz);

// Parte PURA: extrai as quatro features de um bloco de amostras já
// adquirido. Sem I2C, sem Arduino — é aqui que moram as decisões
// perigosas (amostras congeladas, não finitas, `n` inválido), e é por
// isso que ela é separada: pode ser exercitada no host, alimentada com
// CSV do MAFAULDA, sem nenhum duplê de barramento (§2 da arquitetura).
//
// Em erro, `*out` NÃO é escrito.
[[nodiscard]] kaelix::Status vibration_features_from_samples(
    const float* samples, uint16_t n, float sample_rate_hz,
    VibrationFeatures* out);

// Compõe as duas acima sobre o buffer estático do módulo.
// Em erro, `*out` NÃO é escrito.
[[nodiscard]] kaelix::Status vibration_read_features(uint16_t n, VibrationFeatures* out);

} // namespace kaelix::sensors
