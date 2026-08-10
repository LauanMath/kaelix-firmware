#include "vibration.h"
#include "signal_processing.h"

#include <vector>

// TODO (passo 2 do roteiro): implementar a leitura I2C real do MPU6050
// (I2Cdevlib-MPU6050, endereço 0x68). O cálculo de RMS/curtose/fator de
// crista/frequência dominante já está pronto e testado isoladamente em
// lib/signal_processing — quando o sensor chegar, é só substituir o
// buffer de amostras abaixo pela leitura real do acelerômetro.

namespace kaelix::sensors {

static constexpr float SAMPLE_RATE_HZ = 1000.0f; // taxa de amostragem alvo do MPU6050

bool vibration_init() {
    return false;
}

VibrationFeatures vibration_read_features(uint16_t n_samples) {
    std::vector<float> samples(n_samples, 0.0f); // placeholder até a leitura I2C existir

    VibrationFeatures features{};
    features.rms = compute_rms(samples.data(), samples.size());
    features.kurtosis = compute_kurtosis(samples.data(), samples.size());
    features.crest_factor = compute_crest_factor(samples.data(), samples.size());
    features.dominant_freq_hz = dominant_frequency(samples.data(), samples.size(), SAMPLE_RATE_HZ);
    return features;
}

} // namespace kaelix::sensors
