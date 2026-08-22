#pragma once

#include "../machine_state.h"
#include "../sensors/vibration.h"

#include "kaelix_status.h"

// PENDÊNCIA de arquitetura: incluir `../sensors/vibration.h` a partir de
// `ml` é o caso da regra 2/3 de docs/ARQUITETURA-SOFTWARE.md §1 — dois
// módulos de L2 compartilhando um tipo. O destino de `VibrationFeatures`
// é L1, ao lado de lib/signal_processing, que é quem produz os quatro
// números. Não foi movido nesta rodada porque lib/ está sob posse de
// outro agente. `MachineState` já desceu para a raiz de src/ pelo mesmo
// motivo, e foi o que permitiu a `comms` parar de incluir este header.

namespace kaelix::ml {

// Confere que o modelo embarcado existe e é internamente consistente.
// Roda UMA vez por boot: validar aqui, e não a cada travessia de árvore,
// é o que mantém o caminho quente determinístico.
[[nodiscard]] kaelix::Status model_init();

// Roda a inferência sobre as features de vibração.
//
// `*out_state` é escrito com Unknown ANTES de qualquer coisa poder
// falhar, de modo que nenhum caminho de erro consiga produzir `Normal`.
// Essa é a única propriedade desta função que não pode ser negociada: um
// detector de anomalia que falha na direção "máquina sadia" é pior que um
// detector ausente, porque induz confiança.
[[nodiscard]] kaelix::Status model_infer(const kaelix::sensors::VibrationFeatures& features,
                                         float temperature_c,
                                         kaelix::MachineState* out_state);

} // namespace kaelix::ml
