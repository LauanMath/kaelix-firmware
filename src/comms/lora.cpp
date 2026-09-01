#include "lora.h"

#include "../machine_state.h"

#include "crc16.h"
#include "kaelix_status.h"

#include <Arduino.h>
#include <RadioLib.h>

#include <cstdint>

// RA-02 (SX1278) via SPI. Pinos e potência de TX são placeholders — o
// código compila e a lógica pode ser revisada sem hardware, mas só
// será validado de fato (alcance, taxa de perda) na Fase 3, em campo.
// TODO: confirmar pinos contra o esquemático final.

namespace kaelix::comms {
namespace {

constexpr int8_t LORA_CS_PIN = 10;   // NSS (SPI SS padrão do esp32-s3-devkitc-1)
constexpr int8_t LORA_DIO0_PIN = 14; // DIO0 (IRQ) — não usar 8/9 (I2C do MPU6050)
constexpr int8_t LORA_RST_PIN = 21;  // RESET — não usar 8/9 (I2C do MPU6050)
constexpr float LORA_FREQUENCY_MHZ = 433.0f;
constexpr int8_t LORA_TX_POWER_DBM = 17;

// ---------------------------------------------------------------------
// Parâmetros do enlace, fixados explicitamente.
//
// Antes o código chamava begin() só com a frequência, e SF, largura de
// banda, coding rate, syncWord e preâmbulo ficavam nos defaults do
// RadioLib. Isso é ruim por dois motivos: o tempo no ar entra direto no
// orçamento de energia, e uma atualização da biblioteca mudaria o
// consumo do produto em silêncio.
//
// Alcance e autonomia são o mesmo botão. Para o pacote de 20 bytes,
// BW 125 kHz, CR 4/5, com LiPo de 2000 mAh:
//
//   SF7    57 ms no ar   256 dias    alcance de referência
//   SF8   103 ms         249 dias    +2,5 dB
//   SF9   185 ms         236 dias    +5,0 dB
//   SF10  371 ms         211 dias    +7,5 dB
//   SF12 1319 ms         138 dias    +12,5 dB
//
// SF9 é o meio-termo: 5 dB de margem sobre SF7 custando 20 dias de
// autonomia. A escolha definitiva depende da distância real entre os
// motores da Skala e o gateway, que ainda não foi medida — quando for,
// reveja esta tabela em vez de aceitar o default.
//
// CR 4/5 em vez do 4/7 default: menos redundância de canal, 18% menos
// tempo no ar. O pacote já tem CRC-16 próprio, então erro de bit é
// detectado na aplicação; gastar bateria com correção de canal para um
// payload de 20 bytes que pode ser reenviado no ciclo seguinte é troca
// ruim.
//
// syncWord separa esta rede de outras que compartilhem a frequência. O
// valor 0x12 é o de rede privada; 0x34 é reservado para LoRaWAN.
constexpr uint8_t LORA_SPREADING_FACTOR = 9U;
constexpr float LORA_BANDWIDTH_KHZ = 125.0f;
constexpr uint8_t LORA_CODING_RATE = 5U;    // 4/5
constexpr uint8_t LORA_SYNC_WORD = 0x12U;   // rede privada
constexpr uint16_t LORA_PREAMBLE_SYMBOLS = 8U;

// Tempo no ar calculado para os parâmetros acima, usado no orçamento de
// energia (ver README). Se qualquer parâmetro mudar, este número muda.
constexpr uint32_t LORA_AIRTIME_MS = 185U;

// Pulso de reset do SX1278: o datasheet pede RST em nível baixo por mais
// de 100 µs e 5 ms de espera antes do primeiro acesso.
constexpr uint32_t LORA_RESET_PULSE_MS = 1;
constexpr uint32_t LORA_RESET_SETTLE_MS = 5;

// Cota fixa de tentativas de adormecer o rádio. É um laço com limite
// constante, não um "tenta até dar certo": cada tentativa custa tempo na
// janela ativa, e um rádio que não responde a três tentativas com reset
// entre elas não vai responder à quarta.
constexpr uint8_t LORA_SLEEP_MAX_ATTEMPTS = 3;

// ---------------------------------------------------------------------
// Sem heap: por que estes dois objetos e não `new Module(...)`
// ---------------------------------------------------------------------
// O construtor do SX1278 exige um `Module*`, mas NÃO exige que ele venha
// de `new` — um objeto de duração estática serve, e é isto que elimina a
// única alocação dinâmica deste módulo. Avaliação registrada porque o
// desvio DEV-001 do documento de arquitetura dependia dela: a alocação
// era EVITÁVEL, então não há desvio a justificar, há código a corrigir.
//
// O que `new` custava: um ponteiro nunca conferido (com -fno-exceptions a
// falha vira abort() antes de qualquer log existir, indistinguível de um
// brick) e uma alocação durante a inicialização estática, antes de
// setup().
//
// Ordem de inicialização: ambos têm duração estática e são construídos na
// inicialização dinâmica desta unidade de tradução. Nenhuma outra unidade
// os toca — são `static` no escopo anônimo e só as funções abaixo os
// alcançam, todas chamadas a partir de setup(). A dependência de ordem
// entre unidades de tradução que JSF++ proíbe, portanto, não existe aqui
// por construção, e não por coincidência.
Module lora_module(LORA_CS_PIN, LORA_DIO0_PIN, LORA_RST_PIN);
SX1278 radio(&lora_module);

bool s_initialized = false;

// Traduz o código do RadioLib para o vocabulário de falha do projeto.
// `fallback` é o que o chamador considera a causa genérica da SUA fase:
// um código desconhecido durante o begin() não é uma falha de
// transmissão, e vice-versa — um mapeamento único e cego perderia essa
// distinção justamente onde ela orienta a manutenção.
kaelix::Status from_radiolib(int16_t state, kaelix::Status fallback) {
    switch (state) {
        case RADIOLIB_ERR_NONE:
            return kaelix::Status::Ok;
        case RADIOLIB_ERR_CHIP_NOT_FOUND:
            return kaelix::Status::RadioAbsent;      // sem VCC, sem antena de fato: chip mudo
#if defined(RADIOLIB_ERR_SPI_WRITE_FAILED)
        case RADIOLIB_ERR_SPI_WRITE_FAILED:
            return kaelix::Status::RadioBusSilent;   // CS/SCK/MOSI/MISO
#endif
#if defined(RADIOLIB_ERR_SPI_CMD_FAILED)
        case RADIOLIB_ERR_SPI_CMD_FAILED:
            return kaelix::Status::RadioBusSilent;
#endif
        case RADIOLIB_ERR_INVALID_FREQUENCY:
        case RADIOLIB_ERR_INVALID_OUTPUT_POWER:
        case RADIOLIB_ERR_INVALID_BANDWIDTH:
        case RADIOLIB_ERR_INVALID_SPREADING_FACTOR:
        case RADIOLIB_ERR_INVALID_CODING_RATE:
            return kaelix::Status::RadioConfigRejected; // bug de firmware, não defeito de peça
        case RADIOLIB_ERR_TX_TIMEOUT:
            return kaelix::Status::RadioTxTimeout;
        case RADIOLIB_ERR_PACKET_TOO_LONG:
            return kaelix::Status::PayloadTooLong;
        default:
            return fallback;
    }
}

// Pulso de reset por GPIO em vez de radio.reset(): o método existe na
// família SX127x, mas a superfície de API do RadioLib varia entre
// versões, e o pulso é uma linha do datasheet. Depender do datasheet é
// mais estável que depender da versão da biblioteca.
void lora_hardware_reset() {
    pinMode(LORA_RST_PIN, OUTPUT);
    digitalWrite(LORA_RST_PIN, LOW);
    delay(LORA_RESET_PULSE_MS);
    digitalWrite(LORA_RST_PIN, HIGH);
    delay(LORA_RESET_SETTLE_MS);
}

} // namespace

uint32_t device_id() {
    // eFuse MAC é único de fábrica por chip. Os 32 bits baixos bastam
    // para distinguir os dispositivos de uma planta.
    return static_cast<uint32_t>(ESP.getEfuseMac() & 0xFFFFFFFFULL);
}

kaelix::Status make_packet(kaelix::MachineState state, kaelix::Status diag,
                           float rms, float temperature_c,
                           uint32_t boot_count, LoraPacket* out) {
    KAELIX_REQUIRE(out != nullptr, kaelix::Status::NullPointer);

    LoraPacket packet{};
    packet.version = PACKET_VERSION;
    packet.device_id = device_id();
    packet.boot_count = boot_count;
    packet.state = static_cast<uint8_t>(state);
    packet.diag = kaelix::status_code(diag);
    // rms e temperature_c entram como vieram, NaN inclusive: a sentinela é
    // informação, e o gateway a lê junto com `diag`.
    packet.rms = rms;
    packet.temperature_c = temperature_c;
    packet.crc = crc16_ccitt(reinterpret_cast<const uint8_t*>(&packet),
                             sizeof(LoraPacket) - sizeof(packet.crc));
    *out = packet;
    return kaelix::Status::Ok;
}

bool packet_is_valid(const LoraPacket& packet) {
    return packet.crc == crc16_ccitt(reinterpret_cast<const uint8_t*>(&packet),
                                     sizeof(LoraPacket) - sizeof(packet.crc));
}

kaelix::Status lora_init() {
    s_initialized = false;

    const int16_t begin_state = radio.begin(LORA_FREQUENCY_MHZ);
    if (begin_state != RADIOLIB_ERR_NONE) {
        // Um código não mapeado durante o begin() é, por eliminação,
        // recusa de configuração do driver — nunca falha de transmissão.
        return from_radiolib(begin_state, kaelix::Status::RadioConfigRejected);
    }

    const int16_t power_state = radio.setOutputPower(LORA_TX_POWER_DBM);
    if (power_state != RADIOLIB_ERR_NONE) {
        return from_radiolib(power_state, kaelix::Status::RadioConfigRejected);
    }

    // Cada parâmetro é conferido: um enlace configurado pela metade
    // transmite, mas para um receptor que não vai estar escutando com os
    // mesmos parâmetros — falha que só aparece em campo, como ausência
    // total de pacotes, e é cara de diagnosticar de longe.
    const int16_t sf_state = radio.setSpreadingFactor(LORA_SPREADING_FACTOR);
    if (sf_state != RADIOLIB_ERR_NONE) {
        return from_radiolib(sf_state, kaelix::Status::RadioConfigRejected);
    }

    const int16_t bw_state = radio.setBandwidth(LORA_BANDWIDTH_KHZ);
    if (bw_state != RADIOLIB_ERR_NONE) {
        return from_radiolib(bw_state, kaelix::Status::RadioConfigRejected);
    }

    const int16_t cr_state = radio.setCodingRate(LORA_CODING_RATE);
    if (cr_state != RADIOLIB_ERR_NONE) {
        return from_radiolib(cr_state, kaelix::Status::RadioConfigRejected);
    }

    const int16_t sync_state = radio.setSyncWord(LORA_SYNC_WORD);
    if (sync_state != RADIOLIB_ERR_NONE) {
        return from_radiolib(sync_state, kaelix::Status::RadioConfigRejected);
    }

    const int16_t preamble_state = radio.setPreambleLength(LORA_PREAMBLE_SYMBOLS);
    if (preamble_state != RADIOLIB_ERR_NONE) {
        return from_radiolib(preamble_state, kaelix::Status::RadioConfigRejected);
    }

    s_initialized = true;
    return kaelix::Status::Ok;
}

kaelix::Status lora_send(const LoraPacket& packet) {
    KAELIX_REQUIRE(s_initialized, kaelix::Status::NotInitialized);

    // TODO (Fase 3): medir o tempo real de radio.transmit() para 21 bytes
    // no SF/BW configurados e comparar com os 0,15 s assumidos no
    // orçamento de energia de src/power/sleep.cpp. A ~226 ms previstos
    // para SF9/BW125/CR4-7, a premissa está otimista em ~50%. O WCET desta
    // chamada é quem define o pico de 90 mA do ciclo.
    const int16_t state = radio.transmit(reinterpret_cast<const uint8_t*>(&packet),
                                         sizeof(packet));
    return from_radiolib(state, kaelix::Status::RadioTxFailed);
}

kaelix::Status lora_sleep() {
    // Sem KAELIX_REQUIRE(s_initialized): esta função precisa funcionar
    // JUSTAMENTE quando o init falhou. Um chip alimentado que nunca foi
    // configurado ainda está consumindo standby, e adormecê-lo é o que
    // preserva a autonomia. Recusar por falta de init seria proteger o
    // contrato à custa da bateria.
    kaelix::Status status = kaelix::Status::RadioSleepFailed;

    for (uint8_t attempt = 0U; attempt < LORA_SLEEP_MAX_ATTEMPTS; ++attempt) {
        if (attempt > 0U) {
            // INV-1: se o sleep não confirma, o pino RST é acionado. Um
            // rádio preso num estado inesperado depois de um TX abortado
            // costuma voltar a aceitar comandos depois do reset.
            lora_hardware_reset();
        }
        const int16_t state = radio.sleep();
        status = from_radiolib(state, kaelix::Status::RadioSleepFailed);
        if (kaelix::is_ok(status)) {
            break;
        }
    }

    return status;
}

} // namespace kaelix::comms
