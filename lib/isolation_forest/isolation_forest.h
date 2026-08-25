#pragma once

#include <cstdint>

#include "kaelix_status.h"

// Inferência nativa de um Isolation Forest treinado em Python
// (scikit-learn) e exportado como arrays de dados (ver
// training/kaelix_ml/export_cpp.py) — evita depender de TensorFlow Lite
// Micro, que não tem um caminho de conversão confiável para ensembles
// de árvores (Isolation Forest não é uma rede neural).
//
// Sobre a qualificação `kaelix::Status` em todas as assinaturas abaixo:
// dentro de `namespace kaelix::ml` o nome curto `Status` resolve para
// `kaelix::ml::Status` (o veredito Normal/Anomalous de src/ml/model.h)
// sempre que aquele header já tiver sido incluído — e a troca compila
// sem um aviso sequer. Enquanto os dois enums existirem, aqui se
// escreve o nome completo.

namespace kaelix::ml {

// Cota superior de profundidade da travessia — a constante que o §4 de
// docs/ARQUITETURA-SOFTWARE.md chama de KAELIX_MAX_TREE_DEPTH.
//
// Derivação: o sklearn limita cada árvore de isolamento a
// ceil(log2(max_samples)) níveis. Com SUBSAMPLE_SIZE = 256 são 8; mesmo
// um subsample de 65 536 amostras (muito além do que cabe na flash do
// alvo, ver §4) daria 16. 32 é o dobro desse pior caso — folga para
// crescer o treino sem tocar no firmware, e ainda assim uma cota
// CONSTANTE, conhecida em tempo de compilação, que limita o pior caso
// da fase ativa mesmo se a árvore em flash estiver corrompida.
inline constexpr int32_t ISOLATION_TREE_MAX_DEPTH = 32;

struct IsolationTree {
    const int16_t* feature;       // índice da feature testada no nó; -1 = folha
    const float* threshold;       // limiar de decisão do nó
    const int16_t* left;          // índice do filho esquerdo
    const int16_t* right;         // índice do filho direito
    const float* leaf_correction; // c(n_amostras) da folha (0 para nós internos)
    int16_t root;
    // Sem estes dois campos nenhuma função consegue verificar se um
    // índice de nó cai dentro dos arrays: o comprimento dos cinco
    // arrays só existia no gerador Python. São eles que tornam a
    // travessia blindável — e é por isso que a struct, não o laço, era
    // o defeito estrutural (ver isolation_forest_validate).
    int16_t n_nodes;              // comprimento dos cinco arrays acima
    int16_t max_depth;            // profundidade real da árvore, medida no treino
};

// c(n): comprimento médio de caminho esperado para isolar um ponto em
// uma árvore de busca binária com `n` amostras. Mesma fórmula usada
// internamente pelo scikit-learn (sklearn/ensemble/_iforest.py).
float isolation_path_length_correction(int32_t n);

// Confere, UMA ÚNICA VEZ na inicialização (model_init), que os arrays
// gerados são internamente consistentes: ponteiros não nulos, raiz e
// filhos dentro de [0, n_nodes), índices de feature dentro de
// [0, n_features), limiares e correções finitos, e ausência de ciclo.
//
// Validar aqui, e não a cada inferência, é o que mantém o caminho
// quente determinístico: o ciclo de 10 min roda a travessia N_TREES
// vezes, a inicialização roda esta varredura uma vez por boot.
[[nodiscard]] kaelix::Status isolation_forest_validate(const IsolationTree* trees,
                                                       int32_t n_trees,
                                                       int32_t n_features);

// Percorre uma árvore até a folha e escreve em `out_path` o comprimento
// de caminho (profundidade percorrida + correção da folha, para folhas
// que não foram isoladas até um único ponto durante o treino).
//
// REQ-ML-002: a travessia tem cota de profundidade provável. Ao
// estourá-la devolve ModelDepthExceeded em vez de girar para sempre —
// um dispositivo travado acordado consome ~40 mA e mata a bateria em
// ~2 dias, contra os ~241 dias de projeto.
[[nodiscard]] kaelix::Status isolation_tree_path_length(const IsolationTree& tree,
                                                        const float* features,
                                                        int32_t n_features,
                                                        float* out_path);

// Score de anomalia do ensemble, em (0,1] — próximo de 1 = anômalo,
// em torno de 0,5 ou abaixo = normal. Calibrar o limiar de decisão com
// o valor exportado do treino (ANOMALY_THRESHOLD), não usar 0,5 cegamente.
//
// O score só é escrito em `out_score` quando o retorno é Ok: nenhum
// caminho de erro deixa um número plausível para trás, porque quem
// consome isso (src/ml/model.cpp) compara com um limiar, e toda
// comparação com NaN é falsa — o que classificaria uma falha como
// "máquina sadia" (ver Status::ScoreNotFinite).
[[nodiscard]] kaelix::Status isolation_forest_score(const float* features,
                                                    int32_t n_features,
                                                    const IsolationTree* trees,
                                                    int32_t n_trees,
                                                    int32_t subsample_size,
                                                    float* out_score);

} // namespace kaelix::ml
