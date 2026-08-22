#include "temperature.h"
#include "thermistor.h"

#include <Arduino.h>

// Divisor de tensão: Vcc -> R_FIXED -> NTC_ADC_PIN -> NTC -> GND.
// TODO: confirmar pino, R_FIXED e topologia contra o esquemático final
// (Fase 3) — valores abaixo são os nominais do NTC 10K (beta 3950).

namespace kaelix::sensors {

static constexpr uint8_t NTC_ADC_PIN = 4;
static constexpr uint16_t VCC_MV = 3300;   // alimentação do divisor (HT7333)
static constexpr float R_FIXED_OHM = 10000.0f;
static constexpr float R_NOMINAL_OHM = 10000.0f;
static constexpr float BETA = 3950.0f;
static constexpr float T_NOMINAL_C = 25.0f;

bool temperature_init() {
    pinMode(NTC_ADC_PIN, INPUT);
    // Atenuação de 11dB abre a faixa de entrada para ~0-3,3V, que é o
    // alcance do divisor. Sem isso o padrão satura bem antes.
    analogSetPinAttenuation(NTC_ADC_PIN, ADC_11db);
    return true;
}

float temperature_read_celsius() {
    // analogReadMilliVolts aplica a curva de calibração do eFuse; a
    // contagem crua do ADC do ESP32-S3 é sensivelmente não-linear e
    // produziria temperatura enviesada.
    uint16_t mv = static_cast<uint16_t>(analogReadMilliVolts(NTC_ADC_PIN));
    float resistance = ntc_resistance_from_millivolts(mv, VCC_MV, R_FIXED_OHM);
    return ntc_resistance_to_celsius(resistance, R_NOMINAL_OHM, BETA, T_NOMINAL_C);
}

} // namespace kaelix::sensors
