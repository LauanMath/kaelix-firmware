#pragma once

#include <cstdint>

#include "kaelix_protocol.h"
#include "kaelix_status.h"

// Aquisição bruta. Diferente de src/sensors/vibration.cpp, guarda todos os
// canais e não descarta a janela saturada: quem analisa depois decide.
namespace kaelix::transmitter::imu {

struct Capture {
    float sample_rate_hz = 0.0f;
    float temperature_c = 0.0f;
    bool saturated = false;
};

[[nodiscard]] kaelix::Status configure(const kaelix::protocol::DeviceConfig& config);

// `out` recebe window_samples quadros, com os canais de config.channels
// intercalados na ordem dos bits.
[[nodiscard]] kaelix::Status capture(const kaelix::protocol::DeviceConfig& config, int16_t* out, Capture* result);

void sleep();

} // namespace kaelix::transmitter::imu
