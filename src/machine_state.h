#pragma once

#include <cstdint>

// =====================================================================
// Kaelix — veredito sobre a máquina monitorada
// =====================================================================
//
// `MachineState` é o que o dispositivo AFIRMA sobre a máquina.
// `kaelix::Status` (L0) é o porquê de ele poder ou não afirmar. São
// perguntas diferentes e por isso são tipos diferentes: antes desta
// separação existiam dois enums chamados `Status` — `kaelix::Status`
// (falha) e `kaelix::ml::Status` (veredito) —, e o campo `status` do
// pacote LoRa aceitava qualquer um dos dois sem o compilador reclamar.
// Trocar um pelo outro compilava e passava nos testes.
//
// `Unknown` não é um terceiro valor decorativo: é o valor que TODO
// caminho de falha produz. Sem ele, "não consegui medir" e "medi e está
// tudo bem" saem do dispositivo como o mesmo byte — que é a pior falha
// possível num equipamento de manutenção preditiva, porque induz
// confiança em vez de apenas faltar. Um pacote perdido é um buraco
// visível na sequência de `boot_count`; um "Normal" fabricado, não.
//
// Por que este tipo vive na raiz de src/ e não dentro de src/ml/:
// dois módulos de L2 precisam dele sem se enxergarem — `ml` o produz,
// `comms` o coloca no ar. Antes, src/comms/lora.h incluía ../ml/model.h
// só para alcançar o enum, e o formato de fio passava a depender do
// módulo de inferência (violação das regras 2 e 3 de
// docs/ARQUITETURA-SOFTWARE.md §1).
//
// PENDÊNCIA: o destino final deste tipo é L0 (lib/kaelix_status/), ao
// lado de `Status`, para que também o gateway possa compartilhá-lo. Ele
// está aqui, e não lá, apenas porque lib/ está sob posse de outro agente
// nesta rodada.
// =====================================================================

namespace kaelix {

enum class MachineState : uint8_t {
    Normal    = 0, // features válidas, score abaixo do limiar de anomalia
    Anomalous = 1, // features válidas, score acima do limiar
    Unknown   = 2, // não há evidência positiva para afirmar nenhum dos dois
};

static_assert(sizeof(MachineState) == 1, "MachineState precisa caber em 1 byte do pacote LoRa");

// Sem cláusula `default`, e isso é deliberado: acrescentar um valor ao
// enum sem tratá-lo aqui vira aviso de -Wswitch em vez de virar "?" em
// silêncio. Mesmo desvio já registrado para `status_to_string`.
constexpr const char* machine_state_to_string(MachineState state) {
    switch (state) {
        case MachineState::Normal:    return "NORMAL";
        case MachineState::Anomalous: return "ANOMALOUS";
        case MachineState::Unknown:   return "UNKNOWN";
    }
    // Byte fora do enum: só acontece com memória corrompida ou com um
    // pacote decodificado do ar. Não é um caso a esconder.
    return "INVALID";
}

} // namespace kaelix
