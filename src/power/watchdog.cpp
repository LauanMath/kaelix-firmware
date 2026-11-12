#include "watchdog.h"

#include "kaelix_status.h"

#include <Arduino.h>
#include <esp_idf_version.h>
#include <esp_system.h>
#include <esp_task_wdt.h>

#include <cstdint>

// A ponte C mantém o HAL do watchdog compatível com o SDK do C3 e do S3.
#include "rtc_watchdog.h"

namespace kaelix::power {
namespace {

kaelix::Status rtc_watchdog_arm(uint32_t timeout_ms) {
    switch (kaelix_rtc_watchdog_arm(timeout_ms)) {
        case ESP_OK: return kaelix::Status::Ok;
        case ESP_ERR_INVALID_ARG: return kaelix::Status::InvalidArgument;
        case ESP_ERR_NOT_SUPPORTED: return kaelix::Status::NotImplemented;
        default: return kaelix::Status::Internal;
    }
}

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
