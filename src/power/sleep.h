#pragma once

#include <cstdint>

#include "kaelix_status.h"

namespace kaelix::power {

// Faixa aceita por deep_sleep(). O piso não é cosmético: dormir 0 minuto
// é um despertar imediato, ou seja, um ciclo contínuo a ~40 mA — o
// oposto exato do que esta função existe para fazer.
inline constexpr uint32_t SLEEP_MIN_MINUTES = 1U;
inline constexpr uint32_t SLEEP_MAX_MINUTES = 120U;

// Teto do deslocamento anticolisão. 60 s sobre um período de 600 s é
// ~10% de dispersão: suficiente para descorrelacionar dezenas de
// dispositivos com 185 ms de tempo no ar, e pequeno o bastante para não
// atrapalhar a leitura de tendência do lado do gateway.
inline constexpr uint32_t JITTER_MAX_SECONDS = 60U;

// Corta a alimentação do MPU6050/periféricos via transistor BC337 (GPIO).
//
// Devolve Status porque o `hold` do GPIO pode ser recusado pelo pino, e
// sem `hold` a base dos BC337 flutua durante os 10 minutos em que o corte
// precisa valer — o periférico pode continuar energizado no sono inteiro
// sem que nada acuse (Status::PeripheralPowerFault).
[[nodiscard]] kaelix::Status peripherals_power(bool on);

// Prepara o sono: hold do GPIO de corte, reprogramação do WDT-1 para
// cobrir o período e armação do timer de despertar.
//
// Existe separada de `deep_sleep_now()` por uma razão de projeto: uma
// função [[noreturn]] não tem canal para relatar erro, e estas três
// operações têm consequências reais e distintas (periférico energizado
// durante o sono, sono sem rede de segurança, sono sem despertador).
// Separando, L3 fica com a chance de gravar a causa na RTC memory ANTES
// de dormir — o que faz o próximo ciclo poder transmiti-la.
//
// `minutes` fora da faixa é SATURADO e relatado como InvalidArgument, não
// recusado: recusar deixaria o dispositivo sem timer de despertar armado,
// que é o pior desfecho possível desta função.
// `jitter_seconds` desloca o despertar dentro do período, para quebrar a
// sincronização entre dispositivos. Não altera o período médio: o
// deslocamento é somado uma vez e o ciclo seguinte recalcula o seu.
// Limitado a JITTER_MAX_SECONDS para não distorcer a cadência.
[[nodiscard]] kaelix::Status sleep_prepare(uint32_t minutes, uint32_t jitter_seconds = 0U);

// Entra em deep sleep e não retorna. Pressupõe `sleep_prepare()` chamado.
[[noreturn]] void deep_sleep_now();

} // namespace kaelix::power
