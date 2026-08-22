#include "machine_state.h"
#include "comms/lora.h"
#include "ml/model.h"
#include "power/sleep.h"
#include "power/watchdog.h"
#include "sensors/temperature.h"
#include "sensors/vibration.h"

#include "crc16.h"
#include "kaelix_status.h"

#include <Arduino.h>

#include <cstddef>
#include <cstdint>
#include <limits>

// Kaelix — ciclo principal: acordar → ler sensores → processar → inferir
// → transmitir (LoRa) → dormir o rádio → cortar periféricos → deep sleep.
// Ver README.md para a visão geral de cada módulo e o porquê das decisões,
// docs/ARQUITETURA-SOFTWARE.md §5-§6 para a política de erro e o estado
// seguro, e docs/ANALISE-DE-FALHAS.md §5-§6 para os modos de falha que
// cada verificação daqui fecha.
//
// Este arquivo é a ÚNICA camada que decide. `sensors`, `ml`, `comms` e
// `power` relatam com `kaelix::Status`; o que fazer com cada relato —
// degradar, pular fase, transmitir, entrar no estado seguro — é decisão
// de L3 e mora aqui.

// Sem `using namespace`: main.cpp inclui todos os módulos e é o arquivo
// mais exposto a colisão de nomes (MISRA C++ 7-3-4). Aliases mantêm a
// origem de cada nome visível sem a verbosidade.
namespace ksens = kaelix::sensors;
namespace kml = kaelix::ml;
namespace kcomms = kaelix::comms;
namespace kpower = kaelix::power;

using kaelix::MachineState;
using kaelix::Status;

// O log serial é bancada e Fase 3, não operação: em campo não há ninguém
// com um cabo USB, e a UART custa energia na janela ativa que o orçamento
// de src/power/sleep.cpp não contabiliza. O canal de diagnóstico de
// produção é o byte `diag` do pacote LoRa.
#if !defined(KAELIX_LOG_SERIAL)
#  if defined(KAELIX_PRODUCTION)
#    define KAELIX_LOG_SERIAL 0
#  else
#    define KAELIX_LOG_SERIAL 1
#  endif
#endif

namespace {

// ---------------------------------------------------------------------
// Configuração do ciclo
// ---------------------------------------------------------------------

// O tamanho do bloco vem da constante que governa a cadeia inteira, em
// lib/signal_processing — não de um número solto repetido aqui.
constexpr uint16_t VIBRATION_SAMPLES_PER_CYCLE = static_cast<uint16_t>(ksens::VIBRATION_SAMPLES);
static_assert((VIBRATION_SAMPLES_PER_CYCLE & (VIBRATION_SAMPLES_PER_CYCLE - 1U)) == 0U,
              "FFT radix-2 exige potência de 2");
static_assert(VIBRATION_SAMPLES_PER_CYCLE <= ksens::VIBRATION_MAX_SAMPLES,
              "o bloco pedido não cabe no buffer estático de amostras");

constexpr uint32_t SLEEP_MINUTES = 10U;

// Período estendido do estado seguro por escalada. Ver ESCALADA, abaixo.
constexpr uint32_t QUARANTINE_SLEEP_MINUTES = 60U;
constexpr uint16_t MAX_ABNORMAL_RESETS = 4U;

// O MPU6050 precisa estabilizar depois de energizado pelos BC337.
constexpr uint32_t PERIPHERAL_SETTLE_MS = 100U;

// WDT-3: cota de software da fase ativa. Fica ABAIXO da janela do Task
// WDT (6 s) de propósito — é a rede que pega o atraso ANTES do watchdog,
// para que o dispositivo chegue ao estado seguro de forma ordenada, com o
// rádio adormecido, em vez de ser resetado com o rádio em standby a
// 1,5 mA. O nominal da fase ativa é ~1,6 s, então há mais de 3x de folga.
constexpr uint32_t CYCLE_DEADLINE_MS = 5000U;
static_assert(CYCLE_DEADLINE_MS < kpower::WATCHDOG_TASK_TIMEOUT_S * 1000U,
              "a cota de software precisa disparar antes do Task WDT");

// Uma retentativa, não um laço até funcionar: cada tentativa custa o pico
// de ~90 mA do orçamento, e o gateway percebe a ausência pela lacuna na
// sequência de boot_count.
constexpr uint8_t TX_MAX_ATTEMPTS = 2U;

// Sentinela de "não medido". NaN e não 0.0f porque 0 é uma leitura
// perfeitamente plausível tanto de RMS quanto de temperatura — um
// sentinela que se disfarça de medição é a falha silenciosa que este
// firmware existe para eliminar.
constexpr float MEASUREMENT_INVALID = std::numeric_limits<float>::quiet_NaN();

// ---------------------------------------------------------------------
// Estado que atravessa o sono
// ---------------------------------------------------------------------
//
// RTC_NOINIT_ATTR e não RTC_DATA_ATTR: o bootloader RECARREGA a seção
// .rtc.data a partir da imagem em qualquer boot que não seja despertar de
// deep sleep. Ou seja, um reset por watchdog, brownout ou pânico zerava o
// boot_count — o contador apagava justamente a evidência de que o
// dispositivo estava instável, que é a informação de manutenção mais
// valiosa que ele tem a dar (FM-33).
//
// Em troca, .noinit tem conteúdo ARBITRÁRIO depois de um power-on, e
// precisa ser reconhecido como inválido: daí a palavra mágica e o CRC-16,
// calculado com o mesmo lib/crc16 já testado que protege o pacote.
struct RetainedState {
    uint32_t magic;
    uint32_t boot_count;
    uint16_t abnormal_reset_count; // resets anormais consecutivos
    uint8_t  last_status;          // Status do ciclo anterior, para o próximo pacote
    uint8_t  reserved;             // alinhamento explícito: o CRC só cobre bytes definidos
    uint16_t crc;                  // CRC-16/CCITT sobre os campos acima
};

constexpr uint32_t RETAINED_MAGIC = 0x4B4C5831UL; // "KLX1"
static_assert(offsetof(RetainedState, crc) == 12U,
              "a região coberta pelo CRC mudou — o estado retido de campo deixaria de conferir");

RTC_NOINIT_ATTR RetainedState s_retained;

uint16_t retained_crc() {
    return kcomms::crc16_ccitt(reinterpret_cast<const uint8_t*>(&s_retained),
                               offsetof(RetainedState, crc));
}

void retained_seal() {
    s_retained.crc = retained_crc();
}

// Devolve RtcStateCorrupt quando o bloco não confere SEM ser a primeira
// energização. Distinguir os dois casos importa: sem isso, todo
// dispositivo novo reportaria corrupção no primeiro pacote da vida, e o
// código perderia o significado justamente por excesso de uso.
Status retained_load(bool power_on) {
    if (s_retained.magic == RETAINED_MAGIC && s_retained.crc == retained_crc()) {
        return Status::Ok;
    }

    s_retained.magic = RETAINED_MAGIC;
    s_retained.boot_count = 0U;
    s_retained.abnormal_reset_count = 0U;
    s_retained.last_status = kaelix::status_code(Status::Ok);
    s_retained.reserved = 0U;
    retained_seal();

    return power_on ? Status::Ok : Status::RtcStateCorrupt;
}

// ---------------------------------------------------------------------
// Log
// ---------------------------------------------------------------------
// Formato fixo, uma linha por fase, sem texto livre: a string vem de
// status_to_string() e é literal em .rodata. Texto livre num log de
// campo é o que fazia "rádio LoRa não inicializou" cobrir quatro
// deslocamentos de manutenção diferentes.

#if KAELIX_LOG_SERIAL
void log_phase(const char* phase, Status status) {
    Serial.print("[kaelix] ");
    Serial.print(phase);
    Serial.print(' ');
    Serial.println(kaelix::status_to_string(status));
}

void log_cycle(Status status, MachineState state, uint32_t boot_count) {
    Serial.print("[kaelix] cycle ");
    Serial.print(kaelix::status_to_string(status));
    Serial.print(' ');
    Serial.print(kaelix::machine_state_to_string(state));
    Serial.print(" boot=");
    Serial.println(boot_count);
    // Sem flush, a UART é cortada no meio da última linha pelo deep
    // sleep — justamente a linha que diz por que o ciclo terminou assim.
    Serial.flush();
}
#else
void log_phase(const char*, Status) {}
void log_cycle(Status, MachineState, uint32_t) {}
#endif

// Alimenta o WDT-2 numa junção de fases. O retorno entra no acumulador
// como qualquer outro: um watchdog que não aceita ser alimentado é um
// watchdog que vai resetar o dispositivo no meio do ciclo.
Status feed_watchdog(Status accumulated) {
    return kaelix::status_first_error(accumulated, kpower::watchdog_feed());
}

// ---------------------------------------------------------------------
// Estado seguro (ESK)
// ---------------------------------------------------------------------
// Não é "desligado": um dispositivo desligado para de monitorar a máquina,
// e a máquina continua girando. É quieto, de baixíssimo consumo e
// reagendado — preserva a bateria, preserva a capacidade de tentar de
// novo no próximo período, e não afirma nada enquanto isso.
[[noreturn]] void enter_safe_state(Status cycle_status, MachineState state,
                                   uint32_t sleep_minutes) {
    Status status = cycle_status;

    // ESK passo 1: o rádio precisa CONFIRMAR que dormiu. Sem isso ele fica
    // em standby a 1,5 mA durante o período inteiro — 910 mA·s por ciclo,
    // 5,5x o orçamento do dispositivo — e o único sintoma é a bateria
    // durar ~45 dias em vez de ~241.
    const Status radio_sleep = kcomms::lora_sleep();
    log_phase("rf_sleep", radio_sleep);
    status = kaelix::status_first_error(status, radio_sleep);

    // ESK passo 2: trilha dos periféricos cortada.
    const Status peripherals = kpower::peripherals_power(false);
    log_phase("pwr_off", peripherals);
    status = kaelix::status_first_error(status, peripherals);

    // ESK passo 3: hold do GPIO, WDT-1 cobrindo o sono, timer armado.
    const Status prepared = kpower::sleep_prepare(sleep_minutes);
    log_phase("sleep", prepared);
    status = kaelix::status_first_error(status, prepared);

    // Este ciclo já não tem como contar o que houve daqui para a frente —
    // o rádio está dormindo. Fica registrado para o PRÓXIMO pacote: é
    // assim que um RadioSleepFailed chega ao gateway.
    s_retained.last_status = kaelix::status_code(status);
    retained_seal();

    log_cycle(status, state, s_retained.boot_count);

    kpower::deep_sleep_now();
}

} // namespace

void setup() {
#if KAELIX_LOG_SERIAL
    Serial.begin(115200);
#endif

    // Primeira coisa do ciclo, antes de energizar qualquer periférico
    // (REQ-SEG-32): a partir daqui, um travamento em qualquer ponto — I2C
    // sem resposta, radio.transmit() bloqueado, laço de árvore corrompida
    // — tem quem o interrompa. Sem watchdog, o dispositivo fica acordado a
    // ~40 mA e esvazia 2000 mAh em ~2 dias, contra os ~241 dias de
    // projeto, sem nenhum caminho de volta.
    const Status watchdog = kpower::watchdog_arm_active_phase();
    log_phase("wdt", watchdog);

    // O status do watchdog entra no acumulador só no fim do ciclo, e não
    // aqui: ele é uma propriedade do BUILD (a API do RTC WDT existe ou não
    // existe no core instalado), não um evento deste ciclo. Somado
    // primeiro, ele venceria o "primeiro erro vence" em todos os pacotes e
    // esconderia justamente as falhas de sensor que o campo precisa ver.
    Status cycle = Status::Ok;

    const uint32_t started_ms = millis();

    // Causa do reset e estado retido, antes de qualquer decisão.
    const Status reset_cause = kpower::reset_cause_status();
    log_phase("reset", reset_cause);
    const Status rtc_state = retained_load(kpower::reset_was_power_on());
    log_phase("rtc", rtc_state);

    ++s_retained.boot_count;
    if (kaelix::is_error(reset_cause)) {
        ++s_retained.abnormal_reset_count;
    } else {
        s_retained.abnormal_reset_count = 0U;
    }
    retained_seal();

    cycle = kaelix::status_first_error(cycle, reset_cause);
    cycle = kaelix::status_first_error(cycle, rtc_state);

    // O status do ciclo ANTERIOR entra no diagnóstico deste pacote, mas
    // não no acumulador: se entrasse, ele voltaria a ser gravado no estado
    // retido ao final e seria retransmitido para sempre.
    const Status carried = static_cast<Status>(s_retained.last_status);

    // ESCALADA (REQ-SEG-33): quatro resets anormais seguidos significam
    // que repetir o ciclo a cada 10 min não está resolvendo. O período
    // estendido é o que torna o estado seguro SUSTENTÁVEL — o dispositivo
    // sobrevive semanas anunciando o próprio defeito, em vez de horas
    // tentando. Um reset em laço a ~40 mA esvazia a bateria em ~50 h:
    // watchdog sem escalada troca um travamento por uma morte mais rápida.
    const uint32_t sleep_minutes = (s_retained.abnormal_reset_count >= MAX_ABNORMAL_RESETS)
                                       ? QUARANTINE_SLEEP_MINUTES
                                       : SLEEP_MINUTES;

    cycle = kaelix::status_first_error(cycle, kpower::peripherals_power(true));
    delay(PERIPHERAL_SETTLE_MS);
    cycle = feed_watchdog(cycle);

    // RECUPERAÇÃO: um boot que veio de watchdog, pânico ou brownout NÃO
    // repete o ciclo que acabou de travar — repetir é o laço de reset. A
    // fase de medição é pulada; o pacote sai mesmo assim, porque um
    // dispositivo que se cala é indistinguível de um dispositivo fora de
    // alcance (INV-5, "sempre audível").
    const bool recovery = kaelix::is_error(reset_cause);

    MachineState state = MachineState::Unknown;
    float rms = MEASUREMENT_INVALID;
    float temperature_c = MEASUREMENT_INVALID;

    if (!recovery) {
        ksens::VibrationFeatures features{};

        Status vibration = ksens::vibration_init();
        log_phase("vib_init", vibration);
        if (kaelix::is_ok(vibration)) {
            vibration = ksens::vibration_read_features(VIBRATION_SAMPLES_PER_CYCLE, &features);
            log_phase("vib_read", vibration);
        }
        cycle = kaelix::status_first_error(cycle, vibration);
        cycle = feed_watchdog(cycle);

        Status temperature = ksens::temperature_init();
        if (kaelix::is_ok(temperature)) {
            temperature = ksens::temperature_read_celsius(&temperature_c);
        }
        log_phase("temp", temperature);
        cycle = kaelix::status_first_error(cycle, temperature);
        cycle = feed_watchdog(cycle);

        Status model = kml::model_init();
        log_phase("model", model);
        // A inferência só roda com features VÁLIDAS. Sem elas não há
        // veredito: `state` fica Unknown e o pacote carrega o porquê. É
        // este `if` que impede o pior desfecho possível deste projeto —
        // um pacote bem formado, com CRC correto, dizendo "máquina sadia"
        // a partir de um buffer de zeros de um acelerômetro que não
        // existe.
        if (kaelix::is_ok(model) && kaelix::is_ok(vibration)) {
            model = kml::model_infer(features, temperature_c, &state);
            log_phase("infer", model);
        }
        cycle = kaelix::status_first_error(cycle, model);

        if (kaelix::is_ok(vibration)) {
            rms = features.rms;
        }
        cycle = feed_watchdog(cycle);
    }

    // WDT-3. A subtração de unsigned é segura na volta do contador, e
    // millis() zera a cada boot — o que se mede aqui é a fase ativa deste
    // ciclo, não tempo de parede.
    const bool deadline_exceeded = (millis() - started_ms) > CYCLE_DEADLINE_MS;
    if (deadline_exceeded) {
        cycle = kaelix::status_first_error(cycle, Status::CycleDeadlineExceeded);
        log_phase("deadline", Status::CycleDeadlineExceeded);
    }

    // O rádio é inicializado MESMO com o prazo estourado, e isso é
    // deliberado: `lora_sleep()` fala com o SX1278 pelo SPI, e quem
    // configura o SPI é o begin() do RadioLib. Pular a inicialização para
    // "economizar tempo" deixaria o rádio em standby a 1,5 mA durante os
    // 10 minutos de sono — 5,5x o orçamento do ciclo, para poupar ~100 ms.
    // O que o prazo estourado corta é a TRANSMISSÃO, não o caminho que
    // leva ao estado seguro.
    Status radio = kcomms::lora_init();
    log_phase("rf_init", radio);

    // Prazo estourado ⇒ estado seguro imediato, sem transmitir: a fase
    // ativa é cortada onde estiver, e o que ficou pendente aparece no
    // pacote do próximo ciclo.
    if (kaelix::is_ok(radio) && !deadline_exceeded) {
        // O diagnóstico do pacote é o primeiro erro DESTE ciclo, ou o do
        // anterior se este correu limpo.
        const Status diag = kaelix::status_first_error(cycle, carried);

        kcomms::LoraPacket packet{};
        radio = kcomms::make_packet(state, diag, rms, temperature_c,
                                    s_retained.boot_count, &packet);
        if (kaelix::is_ok(radio)) {
            for (uint8_t attempt = 0U; attempt < TX_MAX_ATTEMPTS; ++attempt) {
                radio = kcomms::lora_send(packet);
                if (kaelix::is_ok(radio)) {
                    break;
                }
            }
            log_phase("tx", radio);
        }
    }
    cycle = kaelix::status_first_error(cycle, radio);
    cycle = feed_watchdog(cycle);
    cycle = kaelix::status_first_error(cycle, watchdog);

    enter_safe_state(cycle, state, sleep_minutes);
}

void loop() {
    // Não utilizado — o dispositivo nunca sai do estado seguro em setup(),
    // que termina em deep sleep.
}
