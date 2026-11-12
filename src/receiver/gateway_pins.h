#pragma once

#include <cstdint>
#include <sdkconfig.h>

// Pinagem do RA-02 no gateway. O S3 mantém a ligação que usava como
// transmissor; o C3 preserva a montagem anterior à inversão de papéis.
namespace kaelix::receiver::pins {
#if defined(CONFIG_IDF_TARGET_ESP32S3)
inline constexpr const char* BOARD_NAME = "S3";
inline constexpr uint8_t SCK_PIN = 12;
inline constexpr uint8_t MISO_PIN = 13;
inline constexpr uint8_t MOSI_PIN = 11;
inline constexpr uint8_t CS_PIN = 10;
inline constexpr uint8_t RESET_PIN = 21;
inline constexpr uint8_t DIO0_PIN = 14;
#elif defined(CONFIG_IDF_TARGET_ESP32C3)
inline constexpr const char* BOARD_NAME = "C3";
inline constexpr uint8_t SCK_PIN = 4;
inline constexpr uint8_t MISO_PIN = 5;
inline constexpr uint8_t MOSI_PIN = 6;
inline constexpr uint8_t CS_PIN = 7;
inline constexpr uint8_t RESET_PIN = 3;
inline constexpr uint8_t DIO0_PIN = 1;
#else
#error "Gateway sem pinagem para este alvo"
#endif
} // namespace kaelix::receiver::pins
