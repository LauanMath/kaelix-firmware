#include "watchdog.h"

#include "kaelix_status.h"

#include <Arduino.h>
#include <esp_idf_version.h>
#include <esp_system.h>
#include <esp_task_wdt.h>

#include <cstdint>

// Via de acesso ao WDT-1.
//
// A guarda anterior perguntava se <soc/rtc_wdt.h> EXISTIA. `__has_include`
// prova apenas presença do arquivo, não que ele compile: no ESP32-S3 esse
// cabeçalho está presente e referencia RTC_WDT_STG_SEL_*, definidos apenas
// na árvore do ESP32 original. A guarda admitia o caso e o build do alvo
// quebrava — exatamente o desfecho que ela existia para evitar. Testar
// existência de cabeçalho no lugar de capacidade do alvo é o defeito, e a
// lição vale além deste arquivo.
//
// hal/wdt_hal.h expõe o mesmo periférico (RWDT) de forma portátil entre
// ESP32, S2, S3 e C3, e é a via que o próprio ESP-IDF usa para armar o RTC
// WDT no bootloader. Um caminho só, sem condicional por alvo.
//
// Se a API não existir (IDF antigo demais), o WDT-1 não é armado e
// `watchdog_arm_active_phase` devolve Status::NotImplemented — o
// dispositivo segue protegido pelo WDT-2 e o gateway fica sabendo que a
// rede externa não existe naquele build. Silenciar isso seria pior: o
// invariante de 20 s deixaria de valer sem que ninguém soubesse.
#if defined(__has_include)
#  if __has_include(<hal/wdt_hal.h>) && __has_include(<soc/rtc.h>)
#    include <hal/wdt_hal.h>
#    include <soc/rtc.h>
#    define KAELIX_HAS_RTC_WDT 1
#  endif
#endif
#if !defined(KAELIX_HAS_RTC_WDT)
#  define KAELIX_HAS_RTC_WDT 0
#endif

namespace kaelix::power {
namespace {

#if KAELIX_HAS_RTC_WDT
// Contexto do RWDT. `wdt_hal_init` grava aqui o endereço do bloco de
// registradores; nada mais neste arquivo o interpreta.
wdt_hal_context_t s_rwdt{};

kaelix::Status rtc_watchdog_arm(uint32_t timeout_ms) {
    // O RWDT conta em ticks do RTC_SLOW_CLK, cuja frequência depende da
    // fonte selecionada em boot (RC interno de ~136 kHz ou cristal de
    // 32768 Hz). Fixar a constante faria a janela de 20 s virar 4,8 s ou
    // 83 s conforme a placa, sem nenhum sintoma além do watchdog agindo na
    // hora errada — por isso a frequência é lida, não presumida.
    const uint32_t slow_hz = rtc_clk_slow_freq_get_hz();
    if (slow_hz == 0U) {
        return kaelix::Status::Internal;
    }

    const uint64_t ticks = (static_cast<uint64_t>(timeout_ms) * static_cast<uint64_t>(slow_hz)) / 1000ULL;
    // Zero desarmaria o estágio em vez de armá-lo; acima de 32 bits o valor
    // seria truncado para uma janela arbitrariamente curta.
    if (ticks == 0ULL || ticks > static_cast<uint64_t>(UINT32_MAX)) {
        return kaelix::Status::InvalidArgument;
    }

    // `wdt_hal_init` desabilita o WDT e todos os estágios, e cuida da
    // própria proteção de escrita. A proteção é reposta ao final: os
    // registradores do RWDT são protegidos contra escrita acidental, que é
    // o ponto de ele existir.
    wdt_hal_init(&s_rwdt, WDT_RWDT, 0U, false);
    wdt_hal_write_protect_disable(&s_rwdt);
    // RESET_SYSTEM e não RESET_RTC: o primeiro reinicia CPU e periféricos
    // preservando o domínio RTC, onde vive o estado retido (boot_count,
    // contagem de resets anormais). RESET_RTC apagaria justamente a
    // evidência de que o dispositivo estava instável — a informação de
    // manutenção mais valiosa que ele tem a dar (FM-33). Um estágio que só
    // interrompe não tira o dispositivo de um travamento com as
    // interrupções desabilitadas, então também não serve.
    wdt_hal_config_stage(&s_rwdt, WDT_STAGE0, static_cast<uint32_t>(ticks),
                         WDT_STAGE_ACTION_RESET_SYSTEM);
    // `wdt_hal_enable` alimenta o cão antes de habilitar: a janela começa
    // cheia, e não com o resto da contagem anterior.
    wdt_hal_enable(&s_rwdt);
    wdt_hal_write_protect_enable(&s_rwdt);
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
