#pragma once

#include "../sensors/vibration.h"

namespace kaelix::ml {

enum class Status {
    Normal,
    Anomalous,
};

// "Carrega" o modelo (as árvores do Isolation Forest já estão embarcadas
// como constantes em isolation_forest_data.h — não há alocação dinâmica).
bool model_init();

// Roda a inferência sobre as features de vibração + temperatura.
Status model_infer(const kaelix::sensors::VibrationFeatures& features, float temperature_c);

} // namespace kaelix::ml
