#pragma once

#include <stdint.h>
#include <esp_err.h>

#ifdef __cplusplus
extern "C" {
#endif

esp_err_t kaelix_rtc_watchdog_arm(uint32_t timeout_ms);

#ifdef __cplusplus
}
#endif
