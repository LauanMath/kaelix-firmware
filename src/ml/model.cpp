#include "model.h"
#include "isolation_forest.h"
#include "isolation_forest_data.h"

namespace kaelix::ml {

bool model_init() {
    return N_TREES > 0; // false até o treino real (Fase 2.1) gerar as árvores
}

Status model_infer(const kaelix::sensors::VibrationFeatures& features, float temperature_c) {
    (void)temperature_c; // não usado como feature do modelo por enquanto — ver TODO no header

    if (N_TREES == 0) return Status::Normal; // sem modelo treinado ainda

    float x[N_FEATURES] = {
        features.rms,
        features.kurtosis,
        features.crest_factor,
        features.dominant_freq_hz,
    };

    float score = isolation_forest_score(x, isolation_forest_trees, N_TREES, SUBSAMPLE_SIZE);
    return score > ANOMALY_THRESHOLD ? Status::Anomalous : Status::Normal;
}

} // namespace kaelix::ml
