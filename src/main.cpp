#include <Arduino.h>
#include "sensors/vibration.h"
#include "sensors/temperature.h"
#include "ml/model.h"
#include "comms/lora.h"
#include "power/sleep.h"

// Kaelix — ciclo principal: acordar → ler sensores (3s) → processar →
// inferir → transmitir (LoRa) → deep sleep (10 min).
// Ver README.md e docs/ARQUITETURA.md para a visão geral de cada módulo.

using namespace kaelix;

static constexpr uint16_t VIBRATION_SAMPLES = 512;
static constexpr uint32_t SLEEP_MINUTES = 10;

void setup() {
    Serial.begin(115200);

    power::peripherals_power(true);
    sensors::vibration_init();
    sensors::temperature_init();
    ml::model_init();
    comms::lora_init();

    auto features = sensors::vibration_read_features(VIBRATION_SAMPLES);
    float temperature_c = sensors::temperature_read_celsius();
    auto status = ml::model_infer(features, temperature_c);

    comms::LoraPacket packet{
        .status = static_cast<uint8_t>(status),
        .rms = features.rms,
        .temperature_c = temperature_c,
        .timestamp = millis(),
    };
    comms::lora_send(packet);

    power::peripherals_power(false);
    power::deep_sleep(SLEEP_MINUTES);
}

void loop() {
    // Não utilizado — o dispositivo nunca sai do deep_sleep() em setup().
}
