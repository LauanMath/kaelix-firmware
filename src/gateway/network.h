#pragma once

#include "records.h"

// Tudo que não é rádio: configuração gravada, Wi-Fi, gravador em flash, envio à
// API e atualização remota. A tarefa do rádio só toca a flash e a rede por aqui,
// por funções que não bloqueiam.
namespace kaelix::gateway::net {

void begin();

const char* session();
uint32_t next_event_seq();
uint32_t utc_now(); // 0 enquanto o relógio não foi acertado pela API
int8_t tx_power_dbm();

void radio_health(bool initialized);
void reading_valid();
void rejected();
void spi_error();

// Não bloqueiam. Devolvem false e contam a perda se a fila estiver cheia.
bool store_reading(const ReadingRecord& record);
// `record` vem de ps_malloc, é um WaveRecord seguido das amostras, e passa a
// pertencer à tarefa de gravação, mesmo em falha.
bool store_wave(uint8_t* record, uint32_t size);

Pending pending_for(uint32_t device_id, uint16_t reported_config, uint16_t reported_command);
void mark_radiated(uint32_t device_id, uint16_t config_version, uint16_t command_seq);

} // namespace kaelix::gateway::net
