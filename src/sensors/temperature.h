#pragma once

#include "kaelix_status.h"

namespace kaelix::sensors {

// Janela de plausibilidade FÍSICA do equipamento monitorado. É a segunda
// metade da divisão de responsabilidade descrita em lib/thermistor:
// L1 recusa o que é ELETRICAMENTE impossível (divisor saturado ⇒ NTC em
// curto ou fio rompido), L2 recusa o que é FISICAMENTE implausível. Os
// limiares de L1 ([-51,8; +149,0] °C) contêm estritamente esta janela, de
// modo que as duas verificações não se sobrepõem nem deixam buraco.
inline constexpr float TEMPERATURE_MIN_C = -40.0f;
inline constexpr float TEMPERATURE_MAX_C = 125.0f;

// Inicializa o ADC para leitura do termistor NTC 10K (curva beta 3950).
[[nodiscard]] kaelix::Status temperature_init();

// Lê o ADC e converte para °C pela equação B.
//
// Em erro, `*out_c` NÃO é escrito: quem chama decide o que colocar no
// pacote, e a decisão do Kaelix é a sentinela NaN acompanhada do código
// de diagnóstico. Devolver um número plausível para uma falha de sensor
// é a mentira que este projeto existe para eliminar — um NTC com o fio
// rompido produzia, antes, +349,7 °C ou -77,2 °C transmitidos com CRC
// válido.
[[nodiscard]] kaelix::Status temperature_read_celsius(float* out_c);

} // namespace kaelix::sensors
