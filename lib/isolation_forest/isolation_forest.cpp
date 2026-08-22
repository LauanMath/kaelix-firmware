#include "isolation_forest.h"

#include "kaelix_status.h"

#include <cmath>

namespace kaelix::ml {

// ---------------------------------------------------------------------
// Por que a maioria das verificações abaixo NÃO usa KAELIX_ENSURE
// ---------------------------------------------------------------------
// KAELIX_REQUIRE/KAELIX_ENSURE abortam no build de desenvolvimento — e
// abortar é a resposta certa para um bug NOSSO (ponteiro nulo, argumento
// fora do domínio), que é como este arquivo as usa.
//
// Árvore inconsistente é outra coisa: é DADO. Vem de um header gerado
// mal formado ou de um bit invertido na flash em campo, e o §5 de
// docs/ARQUITETURA-SOFTWARE.md classifica ModelMalformed e
// ModelDepthExceeded como falhas em que "o ciclo continua" — estado da
// máquina = Desconhecido, diagnóstico no pacote. Uma macro que aborta
// não consegue implementar um status cuja política é seguir degradado, e
// um abort no build nativo tornaria intestáveis exatamente os casos de
// robustez que esta rodada precisa cobrir. Por isso essas condições são
// `if` explícito com retorno de Status, em qualquer build.
// ---------------------------------------------------------------------

float isolation_path_length_correction(int32_t n) {
    if (n <= 1) { return 0.0f; }
    if (n == 2) { return 1.0f; }
    constexpr float EULER_GAMMA = 0.5772156649f;
    return 2.0f * (std::log(static_cast<float>(n - 1)) + EULER_GAMMA)
           - 2.0f * static_cast<float>(n - 1) / static_cast<float>(n);
}

namespace {

// Convenção do exportador (training/kaelix_ml/export_cpp.py): nó folha
// tem feature = -1. O sklearn usa -2; a conversão é feita no Python.
constexpr int32_t LEAF_FEATURE = -1;

// Os cinco arrays de uma árvore são independentes no header gerado: se
// um deles não for emitido, o ponteiro fica nulo e a travessia
// desreferencia nulo no primeiro nó.
bool tree_arrays_present(const IsolationTree& tree) {
    return tree.feature != nullptr && tree.threshold != nullptr
           && tree.left != nullptr && tree.right != nullptr
           && tree.leaf_correction != nullptr;
}

// Cota efetiva da travessia: a profundidade declarada pela árvore quando
// ela é plausível, a constante do projeto quando não é. Nos dois casos é
// um limite finito conhecido antes de entrar no laço — que é o que o
// determinismo temporal exige. Uma max_depth corrompida (negativa ou
// absurda) não pode alargar a cota; no máximo cai no teto do projeto.
int32_t traversal_depth_limit(const IsolationTree& tree) {
    const int32_t declared = static_cast<int32_t>(tree.max_depth);
    if (declared >= 0 && declared < ISOLATION_TREE_MAX_DEPTH) {
        return declared;
    }
    return ISOLATION_TREE_MAX_DEPTH;
}

} // namespace

// REQ-ML-002
kaelix::Status isolation_tree_path_length(const IsolationTree& tree,
                                          const float* features,
                                          int32_t n_features,
                                          float* out_path) {
    KAELIX_REQUIRE(features != nullptr, kaelix::Status::NullPointer);
    KAELIX_REQUIRE(out_path != nullptr, kaelix::Status::NullPointer);
    KAELIX_REQUIRE(n_features > 0, kaelix::Status::InvalidArgument);

    if (!tree_arrays_present(tree) || tree.n_nodes <= 0) {
        return kaelix::Status::ModelMalformed;
    }

    const int32_t depth_limit = traversal_depth_limit(tree);
    int32_t node = static_cast<int32_t>(tree.root);

    // `depth <= depth_limit` porque uma folha pode legitimamente estar NO
    // último nível: a cota conta níveis, não passos rejeitados.
    for (int32_t depth = 0; depth <= depth_limit; ++depth) {
        // Antes de qualquer indexação. Sem este teste um índice corrompido
        // (ou negativo — `root`, `left` e `right` são int16_t com sinal)
        // lê memória fora dos arrays, e no ESP32-S3 não há MPU para
        // transformar isso em falha visível.
        if (node < 0 || node >= static_cast<int32_t>(tree.n_nodes)) {
            return kaelix::Status::ModelMalformed;
        }

        const int32_t feature_index = static_cast<int32_t>(tree.feature[node]);
        if (feature_index == LEAF_FEATURE) {
            // Fim do caminho. Mesma aritmética de antes: profundidade
            // percorrida + c(n) da folha medido no treino.
            *out_path = static_cast<float>(depth) + tree.leaf_correction[node];
            return kaelix::Status::Ok;
        }
        // Qualquer outro negativo não é a convenção de folha — é dado
        // corrompido, e tratá-lo como folha devolveria um caminho curto,
        // isto é, um score ALTO: falha na direção de inventar anomalia.
        if (feature_index < 0) {
            return kaelix::Status::ModelMalformed;
        }
        // `feature_index` vem do dado, não do código: indexar `features`
        // com ele sem comparar com n_features é leitura fora do vetor de
        // features do chamador.
        if (feature_index >= n_features) {
            return kaelix::Status::IndexOutOfRange;
        }

        node = (features[feature_index] < tree.threshold[node])
                   ? static_cast<int32_t>(tree.left[node])
                   : static_cast<int32_t>(tree.right[node]);
    }

    // Cota estourada: árvore mais profunda que o declarado, ou com ciclo.
    // Sair por aqui é o que substitui o travamento permanente do laço
    // `while` anterior.
    return kaelix::Status::ModelDepthExceeded;
}

kaelix::Status isolation_forest_score(const float* features,
                                      int32_t n_features,
                                      const IsolationTree* trees,
                                      int32_t n_trees,
                                      int32_t subsample_size,
                                      float* out_score) {
    KAELIX_REQUIRE(features != nullptr, kaelix::Status::NullPointer);
    KAELIX_REQUIRE(trees != nullptr, kaelix::Status::NullPointer);
    KAELIX_REQUIRE(out_score != nullptr, kaelix::Status::NullPointer);
    KAELIX_REQUIRE(n_features > 0, kaelix::Status::InvalidArgument);
    KAELIX_REQUIRE(subsample_size > 1, kaelix::Status::InvalidArgument);

    // Firmware sem modelo treinado é condição de build, não bug do
    // chamador: devolve status, não aborta. n_trees negativo cai aqui
    // também — antes ele fazia o laço não executar e a função devolver
    // exatamente 1.0, ou seja, anomalia máxima a partir de lixo.
    if (n_trees <= 0) {
        return kaelix::Status::ModelAbsent;
    }

    float total_path = 0.0f;
    for (int32_t i = 0; i < n_trees; ++i) {
        float path = 0.0f;
        KAELIX_CHECK(isolation_tree_path_length(trees[i], features, n_features, &path));
        total_path += path;
    }

    // Divisão protegida pela guarda de n_trees acima; sem ela, n_trees = 0
    // devolvia NaN, e NaN comparado com o limiar de anomalia é sempre
    // falso — o detector saía classificando "normal".
    const float mean_path = total_path / static_cast<float>(n_trees);
    const float c = isolation_path_length_correction(subsample_size);
    if (!(c > 0.0f)) {
        // subsample_size > 1 já garante c >= 1. Chegar aqui é o modelo
        // exportado estar inconsistente — e devolver 0.5f, como antes,
        // era entregar um score plausível para uma condição de erro.
        return kaelix::Status::ModelMalformed;
    }

    const float score = std::pow(2.0f, -mean_path / c);
    // Última barreira: nenhum NaN/inf sai daqui como se fosse score.
    if (!std::isfinite(score)) {
        return kaelix::Status::ScoreNotFinite;
    }

    *out_score = score;
    return kaelix::Status::Ok;
}

kaelix::Status isolation_forest_validate(const IsolationTree* trees,
                                         int32_t n_trees,
                                         int32_t n_features) {
    KAELIX_REQUIRE(trees != nullptr, kaelix::Status::NullPointer);
    KAELIX_REQUIRE(n_features > 0, kaelix::Status::InvalidArgument);

    if (n_trees <= 0) {
        return kaelix::Status::ModelAbsent;
    }

    for (int32_t t = 0; t < n_trees; ++t) {
        const IsolationTree& tree = trees[t];

        if (!tree_arrays_present(tree) || tree.n_nodes <= 0) {
            return kaelix::Status::ModelMalformed;
        }
        if (tree.max_depth < 0 || tree.max_depth > ISOLATION_TREE_MAX_DEPTH) {
            return kaelix::Status::ModelMalformed;
        }
        if (tree.root < 0 || tree.root >= tree.n_nodes) {
            return kaelix::Status::ModelMalformed;
        }

        for (int32_t i = 0; i < static_cast<int32_t>(tree.n_nodes); ++i) {
            const int32_t feature_index = static_cast<int32_t>(tree.feature[i]);

            if (feature_index == LEAF_FEATURE) {
                const float correction = tree.leaf_correction[i];
                if (!std::isfinite(correction) || correction < 0.0f) {
                    return kaelix::Status::ModelMalformed;
                }
                continue;
            }
            if (feature_index < 0) {
                return kaelix::Status::ModelMalformed;
            }

            // Feature fora da faixa treinada significa que o header foi
            // gerado com outro conjunto de features que o firmware monta
            // em src/ml/model.cpp — é desalinhamento treino/inferência,
            // não corrupção genérica.
            if (feature_index >= n_features) {
                return kaelix::Status::ModelFeatureMismatch;
            }
            if (!std::isfinite(tree.threshold[i])) {
                return kaelix::Status::ModelMalformed;
            }

            // Filho sempre à frente do pai. É invariante da ordem em
            // profundidade com que o sklearn numera os nós (conferido
            // sobre o ensemble exportado), e é o que prova AQUI, em uma
            // varredura O(n_nodes) e sem memória auxiliar, que a árvore
            // é acíclica — logo que a travessia termina. A cota de
            // profundidade continua existindo como segunda linha, para o
            // caso de a flash se corromper depois desta verificação.
            const int32_t left = static_cast<int32_t>(tree.left[i]);
            const int32_t right = static_cast<int32_t>(tree.right[i]);
            if (left <= i || left >= static_cast<int32_t>(tree.n_nodes)) {
                return kaelix::Status::ModelMalformed;
            }
            if (right <= i || right >= static_cast<int32_t>(tree.n_nodes)) {
                return kaelix::Status::ModelMalformed;
            }
        }
    }

    return kaelix::Status::Ok;
}

} // namespace kaelix::ml
