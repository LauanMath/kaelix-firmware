#pragma once

#include <cstdint>
#include "../sensors/vibration.h"
#include "../ml/model.h"

namespace kaelix::comms {

// Pacote compacto (~50 bytes): status, RMS, temperatura, timestamp.
struct __attribute__((packed)) LoraPacket {
    uint8_t status;      // kaelix::ml::Status
    float rms;
    float temperature_c;
    uint32_t timestamp;
};

// Inicializa o rádio RA-02 (SX1278) via SPI usando RadioLib.
bool lora_init();

// Empacota e transmite a leitura atual.
bool lora_send(const LoraPacket& packet);

} // namespace kaelix::comms
