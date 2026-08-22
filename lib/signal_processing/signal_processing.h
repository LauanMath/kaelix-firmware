#pragma once

#include <cstddef>

// Funções puras de processamento de sinal — sem dependência de Arduino
// ou hardware, para poderem ser testadas no ambiente `native` (host) e
// depois reutilizadas em `src/sensors/vibration.cpp` sobre os dados
// reais do MPU6050. A mesma lógica deve ser replicada em Python na
// Fase 2.1 do treinamento, para não haver divergência entre treino e
// inferência embarcada.

namespace kaelix::sensors {

// RMS (root mean square) das amostras.
float compute_rms(const float* samples, size_t n);

// Curtose de excesso (Fisher: normal = 0) das amostras.
float compute_kurtosis(const float* samples, size_t n);

// Fator de crista: pico absoluto / RMS.
float compute_crest_factor(const float* samples, size_t n);

// FFT radix-2 Cooley-Tukey (decimação no tempo), in-place. `n` deve ser
// potência de 2; `real`/`imag` são sobrescritos com o resultado.
void fft_radix2(float* real, float* imag, size_t n);

// Banda de análise, em Hz — a mesma da ISO 10816-3. O limite inferior
// não é cosmético: a integração para velocidade pesa 1/f, então sem ele
// o bin mais baixo venceria sempre.
constexpr float DOMINANT_BAND_LO_HZ = 10.0f;
constexpr float DOMINANT_BAND_HI_HZ = 1000.0f;

// Frequência dominante do espectro de VELOCIDADE, band-limitado.
//
// Por que velocidade e não aceleração: aceleração escala com ω², então o
// espectro de aceleração é dominado pelo conteúdo de alta frequência —
// tipicamente um modo estrutural da montagem, que é o mesmo com a máquina
// sadia ou defeituosa. Medido no MAFAULDA: o pico de aceleração fica em
// 117 Hz independente da rotação (correlação com a rotação real: -0,018),
// enquanto no espectro de velocidade o pico cai sobre 1x rotação, que é a
// assinatura de desbalanceamento e desalinhamento.
//
// A conversão é feita na magnitude: |V(f)| = |A(f)| / (2*pi*f). A fase não
// importa para escolher o bin de pico, então não é preciso integrar o
// sinal completo — só reponderar o espectro que a FFT já produziu.
float dominant_frequency(const float* samples, size_t n, float sample_rate_hz,
                         float band_lo_hz = DOMINANT_BAND_LO_HZ,
                         float band_hi_hz = DOMINANT_BAND_HI_HZ);

} // namespace kaelix::sensors
