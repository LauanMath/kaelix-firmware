#pragma once

#include <cstdint>

#include "kaelix_status.h"

// =====================================================================
// Política de watchdog do Kaelix (docs/ANALISE-DE-FALHAS.md §6)
// =====================================================================
//
// Dois níveis, com papéis distintos:
//
//   WDT-1  RTC WDT, 20 s durante a fase ativa. Roda no domínio RTC, com
//          relógio próprio, e continua contando com a CPU parada ou com
//          as interrupções desabilitadas. É a rede de segurança absoluta.
//          DELIBERADAMENTE NÃO É ALIMENTADO durante o ciclo: assim ele
//          mede a fase ativa INTEIRA, e não cada fase isolada. É este
//          nível que sustenta o invariante do dispositivo — o Kaelix
//          nunca fica acordado por mais de 20 s consecutivos.
//
//   WDT-2  Task WDT, 6 s, inscrito na tarefa que roda setup(). Dispara
//          antes do WDT-1 e por pânico, o que dá ao firmware a chance de
//          deixar registro do reset. Alimentado APENAS por main.cpp,
//          entre fases.
//
// A regra que dá sentido ao resto: nenhuma função de src/ ou de lib/
// alimenta o watchdog, e nunca dentro de um laço. Alimentar o cão dentro
// do laço que pode travar é a forma clássica de neutralizá-lo — o laço
// trava alimentando. Concentrando a alimentação nas junções do ciclo, o
// watchdog passa a medir PROGRESSO, não atividade de CPU.
//
// O terceiro nível (WDT-3, prazos em software) não mora aqui: ele é a
// verificação de prazo do ciclo, e vive em main.cpp porque é decisão de
// L3 — é o nível que faz o dispositivo chegar ao estado seguro de forma
// ORDENADA, com o rádio adormecido, em vez de ser resetado com o rádio
// no estado em que estiver.
// =====================================================================

namespace kaelix::power {

inline constexpr uint32_t WATCHDOG_ACTIVE_RTC_MS = 20000U;
inline constexpr uint32_t WATCHDOG_TASK_TIMEOUT_S = 6U;

// Margem do WDT-1 sobre o período de sono, em porcentagem. 120% = a
// janela é 1,2x o período: folga suficiente para o despertar normal
// acontecer primeiro, e curta o bastante para que um timer de despertar
// que falhou não deixe o dispositivo mudo para sempre.
inline constexpr uint32_t WATCHDOG_SLEEP_MARGIN_PERCENT = 120U;

// Arma os dois níveis. Deve ser a primeira coisa do ciclo, antes de
// energizar qualquer periférico (REQ-SEG-32).
[[nodiscard]] kaelix::Status watchdog_arm_active_phase();

// Alimenta o WDT-2. Só main.cpp chama, e só entre fases.
[[nodiscard]] kaelix::Status watchdog_feed();

// Reprograma o WDT-1 para cobrir o sono e desinscreve o WDT-2 (a tarefa
// vai deixar de existir).
//
// O RTC WDT CONTINUA CONTANDO durante o deep sleep. Uma política ingênua
// que deixasse a janela de 20 s armada reiniciaria o chip 20 s depois de
// dormir, e o período de 10 minutos nunca aconteceria — o watchdog
// quebraria o produto. Reprogramado para 1,2x o período, ele vira
// despertador de último recurso: se o timer de despertar falhar, o
// dispositivo volta à vida em ~12 min em vez de ficar mudo com a bateria
// cheia (REQ-SEG-49).
[[nodiscard]] kaelix::Status watchdog_arm_for_sleep(uint32_t sleep_minutes);

// Causa do reset traduzida para o vocabulário de falha. `Ok` significa
// despertar normal do deep sleep ou primeira energização — os dois únicos
// motivos esperados.
[[nodiscard]] kaelix::Status reset_cause_status();

// Distingue a primeira energização de um despertar. Existe porque o
// conteúdo da RTC memory é ARBITRÁRIO depois de um power-on: o estado
// retido não conferir é esperado nesse caso, e é corrupção em qualquer
// outro. Sem essa distinção, todo dispositivo novo reportaria
// RtcStateCorrupt no primeiro pacote da vida.
[[nodiscard]] bool reset_was_power_on();

} // namespace kaelix::power
