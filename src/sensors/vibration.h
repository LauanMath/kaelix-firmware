#pragma once

#include <cstdint>

namespace kaelix::sensors {

struct VibrationFeatures {
    float rms;
    float kurtosis;
    float crest_factor;
    float dominant_freq_hz;
};

// Inicializa o MPU6050 via I2C (endereço 0x68).
bool vibration_init();

// Lê `n_samples` amostras do acelerômetro e calcula RMS, curtose,
// fator de crista e frequência dominante (via FFT).
VibrationFeatures vibration_read_features(uint16_t n_samples);

} // namespace kaelix::sensors
