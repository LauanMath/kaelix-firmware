#include "temperature.h"

#include "kaelix_status.h"
#include "thermistor.h"

#include <Arduino.h>

#include <cstdint>

// Divisor de tensão: +3V3_SW -> R_FIXED -> NTC_ADC_PIN -> NTC -> GND.
//
// O topo do divisor está no rail comutado, não em +3V3 direto: fora da
// janela de leitura o divisor não drena nada, e VCC_MV continua sendo a
// saída do HT7333 (3300 mV), com a queda no canal de Q1 (~0,2 mV a 3,9 mA)
// abaixo de um LSB do ADC. Consequência para quem chama: só faz sentido ler
// depois de peripherals_power(true).
//
// LIMITE CONHECIDO, não resolvido aqui: com R_FIXED = 10 k e o NTC para
// GND, o nó sobe quando esfria — 3,22 V a -40 °C, acima da faixa útil do
// ADC do ESP32-S3 (~3,1 V com 12 dB de atenuação). Abaixo de ~-35 °C a
// leitura satura e a temperatura reportada fica otimista. Não dispara os
// limiares de curto/aberto de thermistor.h (ratio 0,94 contra o limiar de
// 0,99), então o valor sai como medição válida. Inverter o divisor
// resolveria o frio e refaria toda a derivação de limiares — decisão para
// a fase de calibração, com o equipamento monitorado definido.

namespace kaelix::sensors {
namespace {

constexpr uint8_t NTC_ADC_PIN = 4;
constexpr uint16_t VCC_MV = 3300;   // alimentação do divisor (HT7333)
constexpr float R_FIXED_OHM = 10000.0f;
constexpr float R_NOMINAL_OHM = 10000.0f;
constexpr float BETA = 3950.0f;
constexpr float T_NOMINAL_C = 25.0f;

// Teto de leitura aceitável do ADC, em mV. Acima de Vcc mais a margem de
// calibração do eFuse (~10%) não existe tensão possível neste divisor: o
// que existe é atenuação errada, pino não roteado ao ADC ou leitura de
// outro canal. É por isso que este valor serve como evidência de que o
// ADC ficou de fato configurado — `pinMode` e `analogSetPinAttenuation`
// são `void` e não têm nada a dizer sobre isso.
constexpr uint32_t ADC_MAX_PLAUSIBLE_MV = 3630;
static_assert(ADC_MAX_PLAUSIBLE_MV >= VCC_MV, "o teto do ADC não pode ficar abaixo de Vcc");

bool s_initialized = false;

} // namespace

kaelix::Status temperature_init() {
    s_initialized = false;

    pinMode(NTC_ADC_PIN, INPUT);
    // Atenuação de 11dB abre a faixa de entrada para ~0-3,3V, que é o
    // alcance do divisor. Sem isso o padrão satura bem antes.
    analogSetPinAttenuation(NTC_ADC_PIN, ADC_11db);

    // Uma leitura de conferência: é a única evidência disponível de que a
    // configuração pegou. Um resultado fora da escala física do divisor
    // não é temperatura nenhuma — é o ADC mal configurado, e o ciclo
    // precisa saber disso agora, não depois de converter.
    const uint32_t mv = analogReadMilliVolts(NTC_ADC_PIN);
    if (mv > ADC_MAX_PLAUSIBLE_MV) {
        return kaelix::Status::AdcNotConfigured;
    }

    s_initialized = true;
    return kaelix::Status::Ok;
}

kaelix::Status temperature_read_celsius(float* out_c) {
    KAELIX_REQUIRE(out_c != nullptr, kaelix::Status::NullPointer);
    KAELIX_REQUIRE(s_initialized, kaelix::Status::NotInitialized);

    // analogReadMilliVolts aplica a curva de calibração do eFuse; a
    // contagem crua do ADC do ESP32-S3 é sensivelmente não-linear e
    // produziria temperatura enviesada.
    //
    // A faixa é conferida ANTES do cast para uint16_t: truncar primeiro
    // esconderia exatamente o valor absurdo que a verificação procura.
    const uint32_t mv_raw = analogReadMilliVolts(NTC_ADC_PIN);
    if (mv_raw > ADC_MAX_PLAUSIBLE_MV) {
        return kaelix::Status::AdcOutOfRange;
    }
    const uint16_t mv = static_cast<uint16_t>(mv_raw);

    kaelix::Status status = kaelix::Status::Ok;
    const float resistance_ohm = ntc_resistance_from_millivolts(mv, VCC_MV, R_FIXED_OHM, &status);
    if (kaelix::is_error(status)) {
        return status; // ThermistorOpen / ThermistorShorted / contrato
    }

    const float celsius = ntc_resistance_to_celsius(resistance_ohm, R_NOMINAL_OHM,
                                                    BETA, T_NOMINAL_C, &status);
    if (kaelix::is_error(status)) {
        return status;
    }

    // Forma negada de propósito: `!(a >= lo && a <= hi)` recusa NaN, ao
    // contrário de `a < lo || a > hi`, que o deixa passar porque toda
    // comparação com NaN é falsa.
    if (!(celsius >= TEMPERATURE_MIN_C && celsius <= TEMPERATURE_MAX_C)) {
        return kaelix::Status::TemperatureImplausible;
    }

    *out_c = celsius;
    return kaelix::Status::Ok;
}

} // namespace kaelix::sensors
