#include "sleep.h"

#include "watchdog.h"

#include "kaelix_status.h"

#include <Arduino.h>
#include <driver/gpio.h>
#include <esp_sleep.h>
#include <esp_system.h>

#include <cstdint>

// Corte de energia por load switch HIGH-SIDE. GPIO5 em nível alto liga o
// rail +3V3_SW, que alimenta o MPU6050, os pull-ups do I2C e o topo do
// divisor do NTC. Em nível baixo (ou em alta impedância) o rail cai a zero.
//
//   GPIO5 -> R5 10k -> base de Q2 (BC847, NPN)
//   Q2 conduz -> gate de Q1 (SI2301, P-MOSFET) a ~0,1 V -> Q1 conduz
//   R8 100k segura a base em 0 se o pino ficar solto -> periféricos OFF
//
// A versão anterior deste comentário descrevia dois BC337 cortando o
// RETORNO A GND do MPU6050. Aquele circuito não desligava o sensor: os
// pull-ups de 4k7 ficavam em +3V3 e injetavam corrente em SDA/SCL, que
// entrava pelos diodos de ESD do MPU6050. O corte tem de ser do lado alto
// e tem de levar os pull-ups junto — é o que o esquemático faz hoje
// (hardware/gen_schematic.py, bloco "Corte de energia dos periféricos").
//
// A polaridade ativo-alto que esta função assume não mudou com a troca de
// topologia, e é por isso que peripherals_power() continua igual.
static constexpr gpio_num_t PERIPHERALS_POWER_PIN = GPIO_NUM_5;

// ---------------------------------------------------------------------
// Orçamento de energia do ciclo (meta: <1mA)
//
// Ciclo: acordar -> ler MPU6050+NTC / processar (3s) -> transmitir LoRa
// (185ms) -> deep sleep (12min) -> repete.
//
// Os 185 ms NAO sao estimativa: saem do calculo de tempo no ar para os
// parametros fixados em src/comms/lora.cpp (SF9, BW 125 kHz, CR 4/5,
// preambulo de 8 simbolos, 21 bytes de payload).
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
//   Load switch, com o rail LIGADO ~300   µA  (só na fase ativa)
//     R4 100k no gate:  3,3 V / 100k        =  33 µA
//     R5 10k na base:  (3,3 - 0,7) / 10k    = 260 µA
//     R8 100k no pull-down: 0,7 V / 100k    =   7 µA
//   Q1 (SI2301) em fuga, rail desligado ~1  µA  (Idss máx de folha de dados)
//   Divisor de medição da bateria ~1,85 µA  (3,7 V / 2 M, SEMPRE ligado)
//     Ele fica ANTES do load switch, na bateria, e por isso não pode ser
//     cortado — é a única carga do circuito que corre 24 h por dia. Foi por
//     isso que o divisor ficou em 1M/1M: com 100k/100k seriam 18,5 µA, 6% do
//     orçamento, contra os 0,6% de agora.
//
// O rádio NÃO está no rail comutado, então o estado em que ele fica
// durante o deep sleep é decidido por software. É a linha
// mais importante deste orçamento:
//
//   sem lora_sleep(): (1,5 + 0,018) mA * 720s = 1093,0 mA*s
//   com lora_sleep(): (0,0002 + 0,018) mA * 720s = 13,1 mA*s
//
// Carga por ciclo (Q = I * t, em mA*s), com o rádio dormindo:
//   Fase ativa (3,0s):  (40 + 3,9 + 1,5 + 0,008 + 0,300 + 0,002) * 3,0s = 137,13 mA*s
//                       (o rádio fica em standby depois do begin())
//   Fase TX   (0,185s): (40 + 3,9 + 90 + 0,008 + 0,300 + 0,002) * 0,185s =  24,83 mA*s
//   Fase sleep  (720s): (0,0002 + 0,010 + 0,008 + 0,001 + 0,00185) * 720 =  15,16 mA*s
//   Total: 177,12 mA*s = 0,04920 mAh por ciclo de 723,185s
//
// Corrente média do circuito: 177,12 / 723,185 = 0,2449 mA ~= 245 µA
//
// Autodescarga da bateria (LiPo, ~2,5%/mês sobre 2000mAh = 50mAh/mês)
// equivale a ~68,5 µA contínuos. É 28% do orçamento e estava faltando
// nas contas anteriores.
//
//   Consumo efetivo: 245 + 68,5 = ~314 µA  -> dentro da meta de <1mA
//   Autonomia (LiPo 2000mAh): 2000 / 0,314 = ~6380h = ~266 dias (~8,7 meses)
//   REQ-PWR-06 (>= 8 meses): atendido com ~23 dias de margem
//
// O divisor de medição custou 1 dia de autonomia. Vale: sem ele, REQ-SEG-29,
// REQ-SEG-53 e o heartbeat da QUARENTENA não têm como ser implementados, e
// FM-26 (o corte de energia não atuar) continua sendo uma falha silenciosa
// cuja única evidência é o dispositivo morrer antes da hora.
//
// O load switch custa 2 dias de autonomia sobre a conta anterior — e a conta
// anterior não fechava, porque supunha um corte que o circuito não fazia.
// Com o MPU6050 permanentemente alimentado, os 3,9 mA dele sozinhos dariam
// ~4 mA de média e ~20 dias de autonomia.
//
// Para comparação, sem lora_sleep() o consumo efetivo seria ~1,81 mA e a
// autonomia cairia para ~46 dias: 83% menos.
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

kaelix::Status sleep_prepare(uint32_t minutes, uint32_t jitter_seconds) {
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
    // deep sleep e a base de Q2 fica flutuando — justamente durante os 12
    // minutos em que o corte de energia precisa valer. O R8 de 100k garante
    // o estado seguro (periféricos DESLIGADOS) se o hold falhar, mas seguro
    // não é o mesmo que correto: sem hold o rail cai e o ciclo seguinte
    // acorda com o sensor frio.
    if (gpio_hold_en(PERIPHERALS_POWER_PIN) != ESP_OK) {
        result = kaelix::status_first_error(result, kaelix::Status::PeripheralPowerFault);
    }
    gpio_deep_sleep_hold_en();

    // O WDT-1 passa a cobrir o sono como despertador de último recurso.
    result = kaelix::status_first_error(result, watchdog_arm_for_sleep(sleep_minutes));

    uint32_t jitter = jitter_seconds;
    if (jitter > JITTER_MAX_SECONDS) {
        jitter = JITTER_MAX_SECONDS;
        result = kaelix::status_first_error(result, kaelix::Status::InvalidArgument);
    }

    const uint64_t sleep_us =
        (static_cast<uint64_t>(sleep_minutes) * 60ULL + static_cast<uint64_t>(jitter)) * 1000000ULL;

    if (esp_sleep_enable_timer_wakeup(sleep_us) != ESP_OK) {
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
