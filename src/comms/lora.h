#pragma once

#include <cstddef>
#include <cstdint>
#include "../ml/model.h"

namespace kaelix::comms {

// Versão do formato do pacote. O gateway usa isto para saber interpretar
// os bytes seguintes — sem ele, qualquer mudança de layout vira leitura
// silenciosamente errada do outro lado.
inline constexpr uint8_t PACKET_VERSION = 1;

// Pacote de 20 bytes, little-endian (nativo do ESP32-S3).
//
// `device_id` vem do eFuse MAC: sem ele, um gateway com mais de um Kaelix
// na planta não tem como saber de quem é a leitura.
//
// `boot_count` substitui o `millis()` que havia aqui antes. millis() zera
// a cada deep sleep, então todo pacote chegava com ~3000 ms — não era um
// relógio. O contador vive em RTC memory e sobrevive ao sleep; o tempo de
// parede é responsabilidade do gateway, que carimba na recepção.
struct __attribute__((packed)) LoraPacket {
    uint8_t  version;
    uint32_t device_id;
    uint32_t boot_count;
    uint8_t  status;         // kaelix::ml::Status
    float    rms;
    float    temperature_c;
    uint16_t crc;            // CRC-16/CCITT sobre os 18 bytes anteriores
};

static_assert(sizeof(LoraPacket) == 20, "layout do pacote mudou — atualize PACKET_VERSION e o gateway");

// Identificador estável desta placa, derivado do eFuse MAC.
uint32_t device_id();

// Monta o pacote já com versão, device_id e CRC preenchidos.
LoraPacket make_packet(kaelix::ml::Status status, float rms, float temperature_c, uint32_t boot_count);

// Confere o CRC de um pacote recebido. Existe aqui para que o gateway
// (ou um teste) possa validar com exatamente a mesma lógica do emissor.
bool packet_is_valid(const LoraPacket& packet);

// Inicializa o rádio RA-02 (SX1278) via SPI usando RadioLib.
bool lora_init();

// Empacota e transmite a leitura atual.
bool lora_send(const LoraPacket& packet);

// Coloca o SX1278 em sleep (~0,2 µA contra ~1,5 mA em standby).
//
// OBRIGATÓRIO antes do deep sleep: o rádio não está no barramento cortado
// pelos BC337, então sem esta chamada ele fica em standby durante os 10
// minutos de sleep, consumindo 900 mA·s por ciclo — 5,5x o orçamento
// inteiro do dispositivo. Ver docs/ARQUITETURA.md.
bool lora_sleep();

} // namespace kaelix::comms
