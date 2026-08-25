#include "sleep.h"

#include "watchdog.h"

#include "kaelix_status.h"

#include <Arduino.h>
#include <driver/gpio.h>
#include <esp_sleep.h>
#include <esp_system.h>

#include <cstdint>

// Corte de energia via transistores BC337 (chave NPN low-side): um GPIO
// habilita a base de ambos os transistores em paralelo, cortando o
// retorno a GND do MPU6050 e do divisor de tensão do NTC durante o sleep.
// TODO: confirmar pino/polaridade contra o esquemático final (Fase 3).
static constexpr gpio_num_t PERIPHERALS_POWER_PIN = GPIO_NUM_5;

// ---------------------------------------------------------------------
// Orçamento de energia do ciclo (meta: <1mA)
//
// Ciclo: acordar -> ler MPU6050+NTC / processar (3s) -> transmitir LoRa
// (~150ms) -> deep sleep (10min) -> repete.
//
// Correntes assumidas (datasheets / valores típicos, a validar com
// multímetro/INA219 na Fase 3):
//   ESP32-S3 ativo (sem WiFi)     ~40    mA
//   MPU6050 em operação           ~3,9   mA  (datasheet InvenSense)
//   SX1278 TX @ ~17dBm            ~90    mA  (datasheet Semtech)
//   SX1278 standby (STDBY)        ~1,5   mA  (datasheet Semtech)
//   SX1278 sleep                  ~0,2   µA  (datasheet Semtech)
//   ESP32-S3 deep sleep           ~10    µA  (fornecido no roteiro)
//   HT7333 quiescente             ~8     µA  (fornecido no roteiro)
//
// O rádio NÃO está no barramento cortado pelos BC337, então o estado em
// que ele fica durante o deep sleep é decidido por software. É a linha
// mais importante deste orçamento:
//
//   sem lora_sleep(): (1,5 + 0,018) mA * 600s = 910,8 mA*s
//   com lora_sleep(): (0,0002 + 0,018) mA * 600s = 10,9 mA*s
//
// Carga por ciclo (Q = I * t, em mA*s), com o rádio dormindo:
//   Fase ativa (3,0s):  (40 + 3,9 + 1,5 + 0,008) mA * 3,0s      = 136,22 mA*s
//                       (o rádio fica em standby depois do begin())
//   Fase TX    (0,15s): (40 + 3,9 + 90 + 0,008) mA * 0,15s      =  20,09 mA*s
//   Fase sleep (600s):  (0,0002 + 0,010 + 0,008) mA * 600s      =  10,92 mA*s
//   Total: 167,23 mA*s = 0,04645 mAh por ciclo de 603,15s
//
// Corrente média do circuito: 167,23 / 603,15 = 0,2772 mA ~= 277 µA
//
// Autodescarga da bateria (LiPo, ~2,5%/mês sobre 2000mAh = 50mAh/mês)
// equivale a ~68,5 µA contínuos. É 25% do orçamento e estava faltando
// nas contas anteriores.
//
//   Consumo efetivo: 277 + 68,5 = ~346 µA  -> dentro da meta de <1mA
//   Autonomia (LiPo 2000mAh): 2000 / 0,346 = ~5780h = ~241 dias (~8 meses)
//
// Para comparação, sem lora_sleep() o consumo efetivo seria ~1,84 mA e a
// autonomia cairia para ~45 dias: 84% menos.
// ---------------------------------------------------------------------

namespace kaelix::power {

kaelix::Status peripherals_power(bool on) {
    // O hold do sleep anterior sobrevive ao boot e travaria o pino; é
    // preciso soltá-lo antes de reconfigurar.
    const esp_err_t released = gpio_hold_dis(PERIPHERALS_POWER_PIN);

    pinMode(PERIPHERALS_POWER_PIN, OUTPUT);
    digitalWrite(PERIPHERALS_POWER_PIN, on ? HIGH : LOW);

    // pinMode e digitalWrite são void e não têm nada a dizer. O único
    // retorno verificável desta função é o do hold — e ele importa: um
    // pino que recusa hold não mantém o corte de energia durante o sono.
    if (released != ESP_OK) {
        return kaelix::Status::PeripheralPowerFault;
    }
    return kaelix::Status::Ok;
}

kaelix::Status sleep_prepare(uint32_t minutes) {
    kaelix::Status result = kaelix::Status::Ok;

    uint32_t sleep_minutes = minutes;
    if (sleep_minutes < SLEEP_MIN_MINUTES) {
        sleep_minutes = SLEEP_MIN_MINUTES;
        result = kaelix::Status::InvalidArgument;
    }
    if (sleep_minutes > SLEEP_MAX_MINUTES) {
        sleep_minutes = SLEEP_MAX_MINUTES;
        result = kaelix::Status::InvalidArgument;
    }

    // Sem o hold, GPIOs não-RTC vão para alta impedância ao entrar em
    // deep sleep e a base dos BC337 fica flutuando — justamente durante
    // os 10 minutos em que o corte de energia precisa valer.
    if (gpio_hold_en(PERIPHERALS_POWER_PIN) != ESP_OK) {
        result = kaelix::status_first_error(result, kaelix::Status::PeripheralPowerFault);
    }
    gpio_deep_sleep_hold_en();

    // O WDT-1 passa a cobrir o sono como despertador de último recurso.
    result = kaelix::status_first_error(result, watchdog_arm_for_sleep(sleep_minutes));

    if (esp_sleep_enable_timer_wakeup(static_cast<uint64_t>(sleep_minutes) * 60ULL * 1000000ULL) != ESP_OK) {
        // Sem fonte de despertar, quem traz o dispositivo de volta é o
        // WDT-1, ~2 min depois do previsto. É por isso que ele é
        // reprogramado em vez de desligado antes do sono.
        result = kaelix::status_first_error(result, kaelix::Status::Internal);
    }

    return result;
}

[[noreturn]] void deep_sleep_now() {
    esp_deep_sleep_start();

    // esp_deep_sleep_start() não deve retornar. Se retornar, cair pelo fim
    // de uma função [[noreturn]] é comportamento indefinido — o compilador
    // pode ter omitido o epílogo e a execução continuaria num endereço
    // arbitrário. O estado seguro aqui é reiniciar: o novo boot lê a causa
    // do reset, registra e volta ao ciclo de forma declarada.
    esp_restart();

    // esp_restart() também não retorna. Este laço existe para que esta
    // função não termine por caminho nenhum, nem mesmo o impossível.
    for (;;) {
    }
}

} // namespace kaelix::power
