#pragma once

#include <cstdint>
#include "isolation_forest.h"

// Placeholder — será gerado por training/kaelix_ml/export_cpp.py depois
// que o Isolation Forest for treinado com dados reais do MAFAULDA/CWRU
// (Fase 2.1). Por enquanto, 0 árvores: isolation_forest_score() com
// n_trees=0 não deve ser chamado por model_infer() (ver model.cpp).

namespace kaelix::ml {

inline constexpr int N_FEATURES = 4;      // rms, kurtosis, crest_factor, dominant_freq_hz
inline constexpr int N_TREES = 0;
inline constexpr int SUBSAMPLE_SIZE = 256; // max_samples do IsolationForest (sklearn, default 'auto')
inline constexpr float ANOMALY_THRESHOLD = 0.5f; // recalibrado no treino (offset_ do sklearn)

inline const IsolationTree* const isolation_forest_trees = nullptr;

} // namespace kaelix::ml
