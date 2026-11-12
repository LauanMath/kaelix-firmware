#pragma once

#include <cstdint>

// Pinagem do transmissor. O C3 atual tem alimentação direta por USB/3V3,
// sem NTC nem load switch; o GPIO5 já pertence ao MISO do rádio.
#if defined(KAELIX_BOARD_C3) && KAELIX_BOARD_C3
#if !defined(CONFIG_IDF_TARGET_ESP32C3)
#error "KAELIX_BOARD_C3 requer um alvo ESP32-C3"
#endif
#if !defined(KAELIX_BENCH) || !KAELIX_BENCH || !defined(KAELIX_HAS_NTC) || KAELIX_HAS_NTC
#error "C3 atual requer KAELIX_BENCH=1 e KAELIX_HAS_NTC=0 (sem load switch/NTC)"
#endif
#endif

namespace kaelix::device {
#if defined(KAELIX_BOARD_C3) && KAELIX_BOARD_C3
inline constexpr const char* BOARD_NAME = "ESP32-C3 Super Mini";
inline constexpr uint8_t MPU_SDA = 20;
inline constexpr uint8_t MPU_SCL = 21;
inline constexpr uint8_t LORA_SCK = 4;
inline constexpr uint8_t LORA_MISO = 5;
inline constexpr uint8_t LORA_MOSI = 6;
inline constexpr uint8_t LORA_CS = 7;
inline constexpr uint8_t LORA_RST = 3;
inline constexpr uint8_t LORA_DIO0 = 1;
#else
inline constexpr const char* BOARD_NAME = "ESP32-S3";
inline constexpr uint8_t MPU_SDA = 8;
inline constexpr uint8_t MPU_SCL = 9;
inline constexpr uint8_t LORA_SCK = 12;
inline constexpr uint8_t LORA_MISO = 13;
inline constexpr uint8_t LORA_MOSI = 11;
inline constexpr uint8_t LORA_CS = 10;
inline constexpr uint8_t LORA_RST = 21;
inline constexpr uint8_t LORA_DIO0 = 14;
#endif
} // namespace kaelix::device
