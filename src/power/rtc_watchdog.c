#include "rtc_watchdog.h"

#include <stdbool.h>
#include <stdint.h>

// O HAL do IDF 4.4 para o C3 copia registradores volatile em macros C.
// Compilar esta ponte em C evita o erro de cópia/atribuição em C++, sem
// modificar o SDK nem desabilitar a proteção RTC de 20 s.
#if defined(__has_include)
#  if __has_include(<hal/wdt_hal.h>) && __has_include(<soc/rtc.h>)
#    include <hal/wdt_hal.h>
#    include <soc/rtc.h>
#    define KAELIX_HAS_RTC_WDT 1
#  endif
#endif
#ifndef KAELIX_HAS_RTC_WDT
#define KAELIX_HAS_RTC_WDT 0
#endif

#if KAELIX_HAS_RTC_WDT
// Contexto do RWDT. `wdt_hal_init` grava aqui o endereço do bloco de
// registradores; nada mais neste arquivo o interpreta.
static wdt_hal_context_t s_rwdt;

esp_err_t kaelix_rtc_watchdog_arm(uint32_t timeout_ms) {
    // O RWDT conta em ticks do RTC_SLOW_CLK, cuja frequência depende da
    // fonte selecionada em boot (RC interno de ~136 kHz ou cristal de
    // 32768 Hz). Fixar a constante faria a janela de 20 s virar 4,8 s ou
    // 83 s conforme a placa, sem nenhum sintoma além do watchdog agindo na
    // hora errada — por isso a frequência é lida, não presumida.
    const uint32_t slow_hz = rtc_clk_slow_freq_get_hz();
    if (slow_hz == 0U) {
        return ESP_FAIL;
    }

    const uint64_t ticks = ((uint64_t)timeout_ms * (uint64_t)slow_hz) / 1000ULL;
    // Zero desarmaria o estágio em vez de armá-lo; acima de 32 bits o valor
    // seria truncado para uma janela arbitrariamente curta.
    if (ticks == 0ULL || ticks > (uint64_t)UINT32_MAX) {
        return ESP_ERR_INVALID_ARG;
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
    wdt_hal_config_stage(&s_rwdt, WDT_STAGE0, (uint32_t)ticks,
                         WDT_STAGE_ACTION_RESET_SYSTEM);
    // `wdt_hal_enable` alimenta o cão antes de habilitar: a janela começa
    // cheia, e não com o resto da contagem anterior.
    wdt_hal_enable(&s_rwdt);
    wdt_hal_write_protect_enable(&s_rwdt);
    return ESP_OK;
}
#else
esp_err_t kaelix_rtc_watchdog_arm(uint32_t timeout_ms) {
    (void)timeout_ms;
    return ESP_ERR_NOT_SUPPORTED;
}
#endif
