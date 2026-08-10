#include "temperature.h"
#include "thermistor.h"

#include <Arduino.h>

// Divisor de tensão: Vcc -> R_FIXED -> NTC_ADC_PIN -> NTC -> GND.
// TODO: confirmar pino, R_FIXED e topologia contra o esquemático final
// (Fase 3) — valores abaixo são os nominais do NTC 10K (beta 3950).

namespace kaelix::sensors {

static constexpr uint8_t NTC_ADC_PIN = 4;
static constexpr uint16_t ADC_MAX = 4095; // ADC de 12 bits do ESP32-S3
static constexpr float R_FIXED_OHM = 10000.0f;
static constexpr float R_NOMINAL_OHM = 10000.0f;
static constexpr float BETA = 3950.0f;
static constexpr float T_NOMINAL_C = 25.0f;

bool temperature_init() {
    pinMode(NTC_ADC_PIN, INPUT);
    return true;
}

float temperature_read_celsius() {
    uint16_t adc_raw = analogRead(NTC_ADC_PIN);
    float resistance = ntc_resistance_from_adc(adc_raw, ADC_MAX, R_FIXED_OHM);
    return ntc_resistance_to_celsius(resistance, R_NOMINAL_OHM, BETA, T_NOMINAL_C);
}

} // namespace kaelix::sensors
