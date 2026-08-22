#pragma once

#include <cstdint>

// Matemática pura de conversão do termistor NTC — sem dependência de
// Arduino, testável no ambiente `native`. A leitura ADC real fica em
// src/sensors/temperature.cpp.

namespace kaelix::sensors {

// Converte uma leitura ADC de um divisor de tensão (Vcc -> R_FIXED ->
// nó de leitura -> NTC -> GND) para a resistência do NTC, em ohms.
// Assume que `adc_raw` é proporcional a Vcc (adc_max = fundo de escala).
// TODO: confirmar topologia do divisor contra o esquemático final (Fase 3).
float ntc_resistance_from_adc(uint16_t adc_raw, uint16_t adc_max, float r_fixed_ohm);

// Mesma matemática, entrada em milivolts. É esta a forma correta no
// ESP32-S3: o ADC bruto é sensivelmente não-linear, e `analogReadMilliVolts`
// aplica a curva de calibração gravada no eFuse de fábrica. Usar a
// contagem crua assume uma linearidade que o hardware não tem.
float ntc_resistance_from_millivolts(uint16_t mv, uint16_t vcc_mv, float r_fixed_ohm);

// Equação B (Steinhart-Hart simplificada): converte a resistência do NTC
// para temperatura em °C, dados a resistência nominal, o beta e a
// temperatura nominal (datasheet: NTC 10K, beta 3950, nominal a 25°C).
float ntc_resistance_to_celsius(float resistance_ohm, float r_nominal_ohm, float beta, float t_nominal_c);

} // namespace kaelix::sensors
