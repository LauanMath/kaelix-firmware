#pragma once

#include <cstddef>
#include <cstdint>

#include "../machine_state.h"

#include "kaelix_status.h"

namespace kaelix::comms {

// Versão do formato do pacote. O gateway usa isto para saber interpretar
// os bytes seguintes — sem ele, qualquer mudança de layout vira leitura
// silenciosamente errada do outro lado.
//
// v1 -> v2: o campo `status` deixou de ser um enum de duas posições
// (Normal/Anomalous) e passou a ser `kaelix::MachineState`, que tem
// `Unknown`; e entrou o byte `diag`, que carrega a CAUSA. Sem ele, os 45
// códigos de `kaelix::Status` só existiam no log serial — que ninguém lê
// num dispositivo parafusado numa máquina — e todo o modelo de erro
// ficava sem consumidor. ATUALIZE O DECODIFICADOR DO GATEWAY JUNTO.
inline constexpr uint8_t PACKET_VERSION = 2;

// Pacote de 21 bytes, little-endian (nativo do ESP32-S3).
//
// `device_id` vem do eFuse MAC: sem ele, um gateway com mais de um Kaelix
// na planta não tem como saber de quem é a leitura.
//
// `boot_count` substitui o `millis()` que havia aqui antes. millis() zera
// a cada deep sleep, então todo pacote chegava com ~3000 ms — não era um
// relógio. O contador vive em RTC memory e sobrevive ao sleep; o tempo de
// parede é responsabilidade do gateway, que carimba na recepção.
//
// CONTRATO DE VALIDADE (o gateway precisa implementá-lo):
//   - `state` == Unknown significa que o dispositivo NÃO tem evidência
//     para afirmar nada. Não é "normal com ressalva".
//   - `rms` e `temperature_c` são NaN quando o valor não foi medido. NaN
//     é a sentinela porque 0.0 é uma leitura perfeitamente plausível — um
//     sentinela que se disfarça de medição é a falha silenciosa que este
//     firmware existe para eliminar. Um campo NaN NUNCA deve entrar na
//     série histórica; ele contaminaria qualquer retreino futuro.
//   - `diag` é `kaelix::status_code()` do primeiro erro do ciclo (0 = Ok).
//     O nibble alto identifica o subsistema, o que permite triar sem a
//     tabela completa.
struct __attribute__((packed)) LoraPacket {
    uint8_t  version;
    uint32_t device_id;
    uint32_t boot_count;
    uint8_t  state;          // kaelix::MachineState
    uint8_t  diag;           // kaelix::Status acumulado do ciclo
    float    rms;            // NaN = não medido
    float    temperature_c;  // NaN = não medido
    uint16_t crc;            // CRC-16/CCITT sobre os 19 bytes anteriores
};

static_assert(sizeof(LoraPacket) == 21,
              "layout do pacote mudou — atualize PACKET_VERSION e o gateway");

// lora.cpp calcula a região do CRC como `sizeof(LoraPacket) - sizeof(crc)`,
// o que assume que `crc` é o ÚLTIMO membro. Reordenar a struct passaria a
// calcular o CRC sobre a região errada — e emissor e receptor continuariam
// concordando entre si, o que torna o erro invisível em teste de laço
// fechado e visível só quando um decodificador independente aparecer.
static_assert(offsetof(LoraPacket, crc) == sizeof(LoraPacket) - sizeof(uint16_t),
              "o CRC precisa ser o último membro do pacote");

// PENDÊNCIA (REQ-SEG-16): não há campo de tensão de bateria.
// `Status::SupplyVoltageLow` existe no enum e hoje não tem como sair do
// dispositivo. Acrescentá-lo exige medir a bateria — hardware e código
// que ainda não existem —, então o campo não foi reservado às cegas: ele
// entra junto com a medição, num v3.

// Identificador estável desta placa, derivado do eFuse MAC.
[[nodiscard]] uint32_t device_id();

// Monta o pacote já com versão, device_id e CRC preenchidos.
// Em erro, `*out` NÃO é escrito.
[[nodiscard]] kaelix::Status make_packet(kaelix::MachineState state, kaelix::Status diag,
                                         float rms, float temperature_c,
                                         uint32_t boot_count, LoraPacket* out);

// Confere o CRC de um pacote recebido. Existe aqui para que o gateway
// (ou um teste) possa validar com exatamente a mesma lógica do emissor.
[[nodiscard]] bool packet_is_valid(const LoraPacket& packet);

// Inicializa o rádio RA-02 (SX1278) via SPI usando RadioLib.
//
// O `Status` devolvido distingue as causas que o RadioLib já sabia
// separar e que o `bool` anterior colapsava num único `false`:
// chip ausente, SPI mudo e parâmetro recusado são três deslocamentos de
// manutenção diferentes — e o terceiro nem sequer é defeito de hardware,
// é bug de firmware.
[[nodiscard]] kaelix::Status lora_init();

// Empacota e transmite a leitura atual.
[[nodiscard]] kaelix::Status lora_send(const LoraPacket& packet);

// Coloca o SX1278 em sleep (~0,2 µA contra ~1,5 mA em standby).
//
// OBRIGATÓRIO antes do deep sleep: o rádio não está no rail comutado
// (+3V3_SW), então sem esta chamada ele fica em standby durante os 10
// minutos de sleep, consumindo 900 mA·s por ciclo — 5,5x o orçamento
// inteiro do dispositivo. Ver o orçamento de energia no README.
//
// Tenta reafirmar o sleep com reset de hardware entre as tentativas
// (INV-1 da análise de falhas), com cota fixa de tentativas. O retorno
// NÃO pode ser descartado: se o rádio não adormeceu, o único sintoma é a
// bateria durar 45 dias em vez de 241, e ninguém percebe.
[[nodiscard]] kaelix::Status lora_sleep();

} // namespace kaelix::comms
