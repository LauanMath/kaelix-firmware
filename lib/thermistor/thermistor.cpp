#include "thermistor.h"

#include <cmath>

namespace kaelix::sensors {

float ntc_resistance_from_adc(uint16_t adc_raw, uint16_t adc_max, float r_fixed_ohm) {
    float ratio = float(adc_raw) / float(adc_max);
    // Evita divisão por zero/infinito nos extremos da escala do ADC.
    if (ratio < 0.001f) ratio = 0.001f;
    if (ratio > 0.999f) ratio = 0.999f;
    return r_fixed_ohm * ratio / (1.0f - ratio);
}

float ntc_resistance_to_celsius(float resistance_ohm, float r_nominal_ohm, float beta, float t_nominal_c) {
    constexpr float KELVIN_OFFSET = 273.15f;
    float t_nominal_k = t_nominal_c + KELVIN_OFFSET;
    float inv_t = 1.0f / t_nominal_k + (1.0f / beta) * std::log(resistance_ohm / r_nominal_ohm);
    return (1.0f / inv_t) - KELVIN_OFFSET;
}

} // namespace kaelix::sensors
