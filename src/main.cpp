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

// O MPU6050 precisa estabilizar depois de energizado pelos BC337.
static constexpr uint32_t PERIPHERAL_SETTLE_MS = 100;

// Sobrevive ao deep sleep (millis() não sobrevive — zera a cada boot).
// É o que dá ao gateway uma noção de sequência e de pacote perdido.
RTC_DATA_ATTR static uint32_t boot_count = 0;

void setup() {
    Serial.begin(115200);
    ++boot_count;

    power::peripherals_power(true);
    delay(PERIPHERAL_SETTLE_MS);

    // Os retornos de init são conferidos: antes eram descartados, e o
    // dispositivo transmitia mesmo com o rádio fora do ar.
    if (!sensors::vibration_init()) {
        Serial.println("[kaelix] MPU6050 indisponível — leitura de vibração não é confiável");
    }
    if (!sensors::temperature_init()) {
        Serial.println("[kaelix] falha ao configurar o ADC do NTC");
    }
    if (!ml::model_init()) {
        Serial.println("[kaelix] sem modelo treinado embarcado — status sempre Normal");
    }
    const bool radio_ok = comms::lora_init();
    if (!radio_ok) {
        Serial.println("[kaelix] rádio LoRa não inicializou — leitura deste ciclo será perdida");
    }

    auto features = sensors::vibration_read_features(VIBRATION_SAMPLES);
    float temperature_c = sensors::temperature_read_celsius();
    auto status = ml::model_infer(features, temperature_c);

    if (radio_ok) {
        auto packet = comms::make_packet(status, features.rms, temperature_c, boot_count);
        if (!comms::lora_send(packet)) {
            Serial.println("[kaelix] falha na transmissão");
        }
    }

    // Obrigatório antes do deep sleep: o rádio não está no barramento
    // cortado pelos BC337, e em standby consome 1,5mA — 5,5x o orçamento
    // inteiro do ciclo. Ver docs/ARQUITETURA.md.
    comms::lora_sleep();

    power::peripherals_power(false);
    power::deep_sleep(SLEEP_MINUTES);
}

void loop() {
    // Não utilizado — o dispositivo nunca sai do deep_sleep() em setup().
}
