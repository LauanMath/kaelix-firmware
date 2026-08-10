#include "lora.h"
#include <RadioLib.h>

// RA-02 (SX1278) via SPI. Pinos e potência de TX são placeholders — o
// código compila e a lógica pode ser revisada sem hardware, mas só
// será validado de fato (alcance, taxa de perda) na Fase 3, em campo.
// TODO: confirmar pinos contra o esquemático final.
static constexpr int LORA_CS_PIN = 10;   // NSS (SPI SS padrão do esp32-s3-devkitc-1)
static constexpr int LORA_DIO0_PIN = 14; // DIO0 (IRQ) — não usar 8/9 (I2C do MPU6050)
static constexpr int LORA_RST_PIN = 21;  // RESET — não usar 8/9 (I2C do MPU6050)
static constexpr float LORA_FREQUENCY_MHZ = 433.0f;
static constexpr int8_t LORA_TX_POWER_DBM = 17;

static SX1278 radio = new Module(LORA_CS_PIN, LORA_DIO0_PIN, LORA_RST_PIN);

namespace kaelix::comms {

bool lora_init() {
    int state = radio.begin(LORA_FREQUENCY_MHZ);
    if (state != RADIOLIB_ERR_NONE) return false;

    state = radio.setOutputPower(LORA_TX_POWER_DBM);
    return state == RADIOLIB_ERR_NONE;
}

bool lora_send(const LoraPacket& packet) {
    int state = radio.transmit(reinterpret_cast<const uint8_t*>(&packet), sizeof(packet));
    return state == RADIOLIB_ERR_NONE;
}

} // namespace kaelix::comms
