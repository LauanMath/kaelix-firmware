#pragma once

#include <cstdint>

// Inferência nativa de um Isolation Forest treinado em Python
// (scikit-learn) e exportado como arrays de dados (ver
// training/kaelix_ml/export_cpp.py) — evita depender de TensorFlow Lite
// Micro, que não tem um caminho de conversão confiável para ensembles
// de árvores (Isolation Forest não é uma rede neural).

namespace kaelix::ml {

struct IsolationTree {
    const int16_t* feature;       // índice da feature testada no nó; -1 = folha
    const float* threshold;       // limiar de decisão do nó
    const int16_t* left;          // índice do filho esquerdo
    const int16_t* right;         // índice do filho direito
    const float* leaf_correction; // c(n_amostras) da folha (0 para nós internos)
    int16_t root;
};

// c(n): comprimento médio de caminho esperado para isolar um ponto em
// uma árvore de busca binária com `n` amostras. Mesma fórmula usada
// internamente pelo scikit-learn (sklearn/ensemble/_iforest.py).
float isolation_path_length_correction(int n);

// Percorre uma árvore até a folha e retorna o comprimento de caminho
// (profundidade percorrida + correção da folha, para folhas que não
// foram isoladas até um único ponto durante o treino).
float isolation_tree_path_length(const IsolationTree& tree, const float* features);

// Score de anomalia do ensemble, em (0,1] — próximo de 1 = anômalo,
// em torno de 0,5 ou abaixo = normal. Calibrar o limiar de decisão com
// o valor exportado do treino (ANOMALY_THRESHOLD), não usar 0,5 cegamente.
float isolation_forest_score(const float* features, const IsolationTree* trees, int n_trees, int subsample_size);

} // namespace kaelix::ml
