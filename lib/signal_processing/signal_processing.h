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

// Roda a FFT sobre `samples` (n deve ser potência de 2) e retorna a
// frequência do bin de maior magnitude, ignorando o bin DC (k=0).
float dominant_frequency(const float* samples, size_t n, float sample_rate_hz);

} // namespace kaelix::sensors
