#pragma once

#include <cstddef>
#include <cstdint>

#include "kaelix_status.h"

// Rádio do transmissor, com a troca entre o canal de controle e a rajada.
namespace kaelix::transmitter::link {

[[nodiscard]] kaelix::Status init(int8_t tx_power_dbm);
[[nodiscard]] kaelix::Status set_power(int8_t tx_power_dbm);
[[nodiscard]] kaelix::Status use_control();
[[nodiscard]] kaelix::Status use_burst(uint8_t profile);
[[nodiscard]] kaelix::Status send(const uint8_t* bytes, size_t size);

// Espera início de quadro por `header_ms` e o quadro inteiro por `frame_ms`.
bool receive(uint8_t* bytes, size_t capacity, size_t* length, uint32_t header_ms, uint32_t frame_ms);

[[nodiscard]] kaelix::Status sleep();
void hold_pins_for_deep_sleep();
void release_pins_after_wake();

} // namespace kaelix::transmitter::link
