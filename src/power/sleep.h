#pragma once

#include <cstdint>

namespace kaelix::power {

// Corta a alimentação do MPU6050/periféricos via transistor BC337 (GPIO).
void peripherals_power(bool on);

// Entra em deep sleep por `minutes` minutos (esp_deep_sleep_start()).
[[noreturn]] void deep_sleep(uint32_t minutes);

} // namespace kaelix::power
