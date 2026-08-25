#include "watchdog.h"

#include "kaelix_status.h"

#include <Arduino.h>
#include <esp_idf_version.h>
#include <esp_system.h>
#include <esp_task_wdt.h>

#include <cstdint>

// O cabeçalho do RTC WDT mudou de lugar entre versões do ESP-IDF. Em vez
// de fixar uma versão, o build pergunta: se a API não estiver disponível,
// o WDT-1 não é armado e `watchdog_arm_active_phase` devolve
// Status::NotImplemented — o dispositivo continua protegido pelo WDT-2, e
// o gateway fica sabendo que a rede externa não existe naquele build.
// Silenciar isso seria pior: o invariante de 20 s deixaria de valer sem
// que ninguém soubesse.
#if defined(__has_include)
#  if __has_include(<soc/rtc_wdt.h>)
#    include <soc/rtc_wdt.h>
#    define KAELIX_HAS_RTC_WDT 1
#  endif
#endif
#if !defined(KAELIX_HAS_RTC_WDT)
#  define KAELIX_HAS_RTC_WDT 0
#endif

namespace kaelix::power {
namespace {

#if KAELIX_HAS_RTC_WDT
kaelix::Status rtc_watchdog_arm(uint32_t timeout_ms) {
    // Os registradores do RTC WDT são protegidos contra escrita acidental
    // (é o ponto de ele existir); a proteção é reposta ao final.
    rtc_wdt_protect_off();
    rtc_wdt_disable();
    rtc_wdt_set_length_of_reset_signal(RTC_WDT_SYS_RESET_SIG, RTC_WDT_LENGTH_3_2us);
    // Reset do sistema inteiro, inclusive o domínio digital: um estágio
    // que só interrompe não tira o dispositivo de um travamento com as
    // interrupções desabilitadas.
    rtc_wdt_set_stage(RTC_WDT_STAGE0, RTC_WDT_STAGE_ACTION_RESET_SYSTEM);
    const esp_err_t err = rtc_wdt_set_time(RTC_WDT_STAGE0, timeout_ms);
    if (err != ESP_OK) {
        rtc_wdt_protect_on();
        return kaelix::Status::Internal;
    }
    rtc_wdt_enable();
    rtc_wdt_protect_on();
    rtc_wdt_feed();
    return kaelix::Status::Ok;
}
#else
kaelix::Status rtc_watchdog_arm(uint32_t) {
    return kaelix::Status::NotImplemented;
}
#endif

kaelix::Status task_watchdog_arm(uint32_t timeout_s) {
#if ESP_IDF_VERSION_MAJOR >= 5
    esp_task_wdt_config_t config{};
    config.timeout_ms = timeout_s * 1000U;
    config.idle_core_mask = 0U;   // as tarefas ociosas não são o que se mede aqui
    config.trigger_panic = true;  // pânico → reset; interromper sem resetar não recupera nada
    esp_err_t err = esp_task_wdt_reconfigure(&config);
    if (err == ESP_ERR_INVALID_STATE) {
        // O core do Arduino pode não ter inicializado o Task WDT.
        err = esp_task_wdt_init(&config);
    }
#else
    esp_err_t err = esp_task_wdt_init(timeout_s, true);
#endif
    if (err != ESP_OK) {
        return kaelix::Status::Internal;
    }

    err = esp_task_wdt_add(nullptr);
    // ESP_ERR_INVALID_ARG aqui significa "esta tarefa já está inscrita",
    // que é exatamente o estado desejado.
    if (err != ESP_OK && err != ESP_ERR_INVALID_ARG) {
        return kaelix::Status::Internal;
    }
    return kaelix::Status::Ok;
}

} // namespace

kaelix::Status watchdog_arm_active_phase() {
    const kaelix::Status task = task_watchdog_arm(WATCHDOG_TASK_TIMEOUT_S);
    const kaelix::Status rtc = rtc_watchdog_arm(WATCHDOG_ACTIVE_RTC_MS);
    // O primeiro erro vence, mas os dois são armados: a falha de um não
    // pode servir de desculpa para o outro não existir.
    return kaelix::status_first_error(task, rtc);
}

kaelix::Status watchdog_feed() {
    // Só o WDT-2. O WDT-1 não é alimentado durante a fase ativa — é ele
    // que impõe o teto absoluto de 20 s ao ciclo inteiro.
    const esp_err_t err = esp_task_wdt_reset();
    return (err == ESP_OK) ? kaelix::Status::Ok : kaelix::Status::Internal;
}

kaelix::Status watchdog_arm_for_sleep(uint32_t sleep_minutes) {
    KAELIX_REQUIRE(sleep_minutes >= 1U, kaelix::Status::InvalidArgument);

    // A tarefa que roda setup() deixa de existir no deep sleep; mantê-la
    // inscrita no Task WDT não faria sentido.
    const esp_err_t err = esp_task_wdt_delete(nullptr);
    if (err != ESP_OK && err != ESP_ERR_INVALID_ARG) {
        return kaelix::Status::Internal;
    }

    // 1,2x o período de sono, em milissegundos. A conta é feita em
    // uint64_t porque 60 min já passam de 4,3e6 ms e a multiplicação
    // intermediária estouraria 32 bits com folga menor do que parece.
    const uint64_t window_ms =
        (static_cast<uint64_t>(sleep_minutes) * 60ULL * 1000ULL * WATCHDOG_SLEEP_MARGIN_PERCENT) / 100ULL;
    if (window_ms > UINT32_MAX) {
        return kaelix::Status::InvalidArgument;
    }
    return rtc_watchdog_arm(static_cast<uint32_t>(window_ms));
}

kaelix::Status reset_cause_status() {
    switch (esp_reset_reason()) {
        case ESP_RST_TASK_WDT:
        case ESP_RST_WDT:
        case ESP_RST_INT_WDT:
            return kaelix::Status::WatchdogResetDetected;
        case ESP_RST_BROWNOUT:
            return kaelix::Status::BrownoutResetDetected;
        case ESP_RST_PANIC:
        case ESP_RST_SW:
            // Pânico é defeito de firmware, e o reset por software só é
            // usado neste projeto no caminho de "não deveria acontecer" de
            // deep_sleep(). Internal é o código honesto para os dois: uma
            // falha que este modelo de erro ainda não classificou.
            return kaelix::Status::Internal;
        default:
            // ESP_RST_DEEPSLEEP (ciclo normal) e ESP_RST_POWERON (primeira
            // energização) são os dois motivos esperados.
            return kaelix::Status::Ok;
    }
}

bool reset_was_power_on() {
    return esp_reset_reason() == ESP_RST_POWERON;
}

} // namespace kaelix::power
