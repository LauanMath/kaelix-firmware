#include "sleep.h"
#include <Arduino.h>
#include <esp_sleep.h>

// Corte de energia via transistores BC337 (chave NPN low-side): um GPIO
// habilita a base de ambos os transistores em paralelo, cortando o
// retorno a GND do MPU6050 e do divisor de tensão do NTC durante o sleep.
// TODO: confirmar pino/polaridade contra o esquemático final (Fase 3).
static constexpr uint8_t PERIPHERALS_POWER_PIN = 5;

// ---------------------------------------------------------------------
// Estimativa teórica de consumo médio do ciclo (meta: <1mA)
//
// Ciclo: acordar -> ler MPU6050+NTC / processar (3s) -> transmitir LoRa
// (~150ms) -> deep sleep (10min) -> repete.
//
// Correntes assumidas (datasheets / valores típicos, a validar com
// multímetro/INA219 na Fase 3):
//   ESP32-S3 ativo (sem WiFi)     ~40    mA
//   MPU6050 em operação           ~3,9   mA  (datasheet InvenSense)
//   SX1278 TX @ ~17dBm            ~90    mA  (datasheet Semtech)
//   ESP32-S3 deep sleep           ~10    µA  (fornecido no roteiro)
//   HT7333 quiescente             ~8     µA  (fornecido no roteiro)
//
// Carga por ciclo (Q = I * t, em mA*s):
//   Fase ativa (3,0s):  (40 + 3,9 + 0,008) mA * 3,0s   = 131,72 mA*s
//   Fase TX    (0,15s): (40 + 3,9 + 90 + 0,008) mA * 0,15s = 20,09 mA*s
//   Fase sleep (600s):  (0,010 + 0,008) mA * 600s      = 10,80 mA*s
//   Total: 162,61 mA*s = 0,04517 mAh por ciclo de 603,15s
//
// Corrente média: 0,04517 mAh / (603,15s / 3600) = 0,2696 mA ≈ 270 µA
// -> dentro da meta de <1mA, com margem de ~3,7x.
// Autonomia estimada (bateria 18650, 3000mAh): ~464 dias (~15,5 meses).
// ---------------------------------------------------------------------

namespace kaelix::power {

void peripherals_power(bool on) {
    pinMode(PERIPHERALS_POWER_PIN, OUTPUT);
    digitalWrite(PERIPHERALS_POWER_PIN, on ? HIGH : LOW);
}

[[noreturn]] void deep_sleep(uint32_t minutes) {
    esp_sleep_enable_timer_wakeup((uint64_t)minutes * 60ULL * 1000000ULL);
    esp_deep_sleep_start();
}

} // namespace kaelix::power
