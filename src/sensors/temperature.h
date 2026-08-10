#pragma once

#include <cstdint>

namespace kaelix::sensors {

// Inicializa o ADC para leitura do termistor NTC 10K (curva beta 3950).
bool temperature_init();

// Lê o ADC e converte para °C via equação de Steinhart-Hart.
float temperature_read_celsius();

} // namespace kaelix::sensors
