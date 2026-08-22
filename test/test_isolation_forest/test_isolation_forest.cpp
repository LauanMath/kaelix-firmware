#include <unity.h>

#include "isolation_forest.h"
#include "kaelix_status.h"

#include <cmath>

using namespace kaelix::ml;

// Comparação de Status legível no relatório do Unity (o código é 1 byte,
// então HEX16 imprime "esperado 0x31, obtido 0x00" em vez de "falhou").
#define ASSERT_STATUS(expected, actual) \
    TEST_ASSERT_EQUAL_HEX16(kaelix::status_code(expected), kaelix::status_code(actual))

// Igualdade exata de float. Os valores de referência foram capturados da
// implementação anterior a esta rodada de blindagem e são impressos com
// %.9g, que faz round-trip exato em float: se qualquer verificação
// acrescentada mudar um bit do resultado, estes casos falham. É a
// tradução, para o lado C++, do invariante de paridade numérica
// (docs/ARQUITETURA-SOFTWARE.md §7) — o score é validado contra
// sklearn.score_samples a 1e-4 em training/tests/test_export_cpp.py, e
// nada aqui pode deslocá-lo.
#define ASSERT_FLOAT_BIT_EXACT(expected, actual) TEST_ASSERT_FLOAT_WITHIN(0.0f, expected, actual)

void setUp(void) {}
void tearDown(void) {}

// =====================================================================
// Fixtures
// =====================================================================

// Árvore de 1 split (3 nós: raiz interna + 2 folhas):
//   raiz: feature[0] < 0.5 ? esquerda : direita
//   folha esquerda: recebeu 4 amostras no treino (não isolada) -> c(4)
//   folha direita:  recebeu 1 amostra no treino (isolada)      -> c(1) = 0
static const int16_t kFeature[3] = {0, -1, -1};
static const float kThreshold[3] = {0.5f, 0.0f, 0.0f};
static const int16_t kLeft[3] = {1, 0, 0};
static const int16_t kRight[3] = {2, 0, 0};
static const float kLeafCorrection[3] = {0.0f, 1.8516559f, 0.0f}; // c(4), c(1)

static IsolationTree make_test_tree() {
    IsolationTree tree{};
    tree.feature = kFeature;
    tree.threshold = kThreshold;
    tree.left = kLeft;
    tree.right = kRight;
    tree.leaf_correction = kLeafCorrection;
    tree.root = 0;
    tree.n_nodes = 3;
    tree.max_depth = 1;
    return tree;
}

// Floresta de regressão numérica: 2 árvores, 4 features, profundidade 2.
// Os mesmos arrays alimentaram a implementação anterior para gerar os
// valores esperados mais abaixo.
static const int16_t kF0[7] = {0, 2, -1, -1, 1, -1, -1};
static const float kT0[7] = {0.30f, -1.25f, 0.0f, 0.0f, 2.75f, 0.0f, 0.0f};
static const int16_t kL0[7] = {1, 2, 0, 0, 5, 0, 0};
static const int16_t kR0[7] = {4, 3, 0, 0, 6, 0, 0};
static const float kC0[7] = {0.0f, 0.0f, 1.8516559f, 1.2073922f, 0.0f, 0.0f, 3.7488308f};

static const int16_t kF1[5] = {3, -1, 1, -1, -1};
static const float kT1[5] = {12.5f, 0.0f, 0.125f, 0.0f, 0.0f};
static const int16_t kL1[5] = {1, 0, 3, 0, 0};
static const int16_t kR1[5] = {2, 0, 4, 0, 0};
static const float kC1[5] = {0.0f, 2.9074516f, 0.0f, 1.0f, 5.1234567f};

static const IsolationTree kForest[2] = {
    {kF0, kT0, kL0, kR0, kC0, 0, 7, 2},
    {kF1, kT1, kL1, kR1, kC1, 0, 5, 2},
};

// O último caso cai exatamente sobre os limiares: é o que fixa o lado do
// "<" na fronteira, que uma reescrita da travessia poderia inverter sem
// que nenhum outro caso percebesse.
static const float kCases[6][4] = {
    {0.10f, 0.00f, -2.00f, 5.00f},
    {0.10f, 0.00f, 0.50f, 5.00f},
    {0.90f, 1.00f, 0.00f, 20.0f},
    {0.90f, 3.00f, 0.00f, 0.05f},
    {-4.5f, 9.75f, 7.25f, 100.0f},
    {0.30f, 0.125f, -1.25f, 12.5f},
};

// Árvore mutável, reconstruída por cada teste de robustez a partir da
// árvore boa e depois corrompida em um único campo — assim o teste isola
// exatamente qual corrupção produz qual Status.
static int16_t g_feature[4];
static float g_threshold[4];
static int16_t g_left[4];
static int16_t g_right[4];
static float g_leaf_correction[4];

// Árvore de 3 nós idêntica em forma à de make_test_tree(), mas em
// memória gravável.
static IsolationTree make_mutable_tree() {
    g_feature[0] = 0;
    g_feature[1] = -1;
    g_feature[2] = -1;
    g_threshold[0] = 0.5f;
    g_threshold[1] = 0.0f;
    g_threshold[2] = 0.0f;
    g_left[0] = 1;
    g_left[1] = 0;
    g_left[2] = 0;
    g_right[0] = 2;
    g_right[1] = 0;
    g_right[2] = 0;
    g_leaf_correction[0] = 0.0f;
    g_leaf_correction[1] = 1.8516559f;
    g_leaf_correction[2] = 0.0f;

    IsolationTree tree{};
    tree.feature = g_feature;
    tree.threshold = g_threshold;
    tree.left = g_left;
    tree.right = g_right;
    tree.leaf_correction = g_leaf_correction;
    tree.root = 0;
    tree.n_nodes = 3;
    tree.max_depth = 1;
    return tree;
}

// =====================================================================
// Matemática — c(n) e travessia (comportamento nominal)
// =====================================================================

// c(n) — valores de referência calculados independentemente (mesma
// fórmula usada pelo scikit-learn: sklearn/ensemble/_iforest.py).
void test_path_length_correction_known_values(void) {
    TEST_ASSERT_FLOAT_WITHIN(1e-6f, 0.0f, isolation_path_length_correction(1));
    TEST_ASSERT_FLOAT_WITHIN(1e-6f, 1.0f, isolation_path_length_correction(2));
    TEST_ASSERT_FLOAT_WITHIN(1e-4f, 1.207392f, isolation_path_length_correction(3));
    TEST_ASSERT_FLOAT_WITHIN(1e-4f, 1.851656f, isolation_path_length_correction(4));
    TEST_ASSERT_FLOAT_WITHIN(1e-3f, 10.244771f, isolation_path_length_correction(256));
}

void test_path_length_correction_regression_bit_exact(void) {
    ASSERT_FLOAT_BIT_EXACT(0.0f, isolation_path_length_correction(1));
    ASSERT_FLOAT_BIT_EXACT(1.0f, isolation_path_length_correction(2));
    ASSERT_FLOAT_BIT_EXACT(1.20739233f, isolation_path_length_correction(3));
    ASSERT_FLOAT_BIT_EXACT(10.244771f, isolation_path_length_correction(256));
    ASSERT_FLOAT_BIT_EXACT(15.7899628f, isolation_path_length_correction(4096));
}

void test_tree_path_length_left_leaf(void) {
    IsolationTree tree = make_test_tree();
    float features[1] = {0.2f}; // < 0.5 -> folha esquerda (depth 1 + c(4))
    float path = 0.0f;
    ASSERT_STATUS(kaelix::Status::Ok, isolation_tree_path_length(tree, features, 1, &path));
    TEST_ASSERT_FLOAT_WITHIN(1e-4f, 1.0f + 1.8516559f, path);
}

void test_tree_path_length_right_leaf(void) {
    IsolationTree tree = make_test_tree();
    float features[1] = {0.8f}; // >= 0.5 -> folha direita (depth 1 + c(1)=0)
    float path = 0.0f;
    ASSERT_STATUS(kaelix::Status::Ok, isolation_tree_path_length(tree, features, 1, &path));
    TEST_ASSERT_FLOAT_WITHIN(1e-4f, 1.0f, path);
}

void test_tree_path_length_regression_bit_exact(void) {
    static const float kExpected0[6] = {3.85165596f, 3.20739222f, 2.0f,
                                        5.7488308f, 3.20739222f, 2.0f};
    static const float kExpected1[6] = {3.90745163f, 3.90745163f, 7.12345648f,
                                        3.90745163f, 7.12345648f, 7.12345648f};
    for (int i = 0; i < 6; ++i) {
        float path0 = 0.0f;
        float path1 = 0.0f;
        ASSERT_STATUS(kaelix::Status::Ok,
                      isolation_tree_path_length(kForest[0], kCases[i], 4, &path0));
        ASSERT_STATUS(kaelix::Status::Ok,
                      isolation_tree_path_length(kForest[1], kCases[i], 4, &path1));
        ASSERT_FLOAT_BIT_EXACT(kExpected0[i], path0);
        ASSERT_FLOAT_BIT_EXACT(kExpected1[i], path1);
    }
}

// =====================================================================
// Score do ensemble (comportamento nominal)
// =====================================================================

void test_forest_score_matches_manual_formula(void) {
    IsolationTree tree = make_test_tree();
    float features[1] = {0.8f}; // caminho curto (path=1) -> score mais alto (mais anômalo)

    const int32_t subsample_size = 256;
    float score = 0.0f;
    ASSERT_STATUS(kaelix::Status::Ok,
                  isolation_forest_score(features, 1, &tree, 1, subsample_size, &score));

    float c = isolation_path_length_correction(subsample_size);
    float expected = std::pow(2.0f, -1.0f / c);
    TEST_ASSERT_FLOAT_WITHIN(1e-4f, expected, score);
}

void test_shorter_path_scores_higher_than_longer_path(void) {
    // Propriedade fundamental do Isolation Forest: pontos isolados com
    // caminhos mais curtos são "mais anômalos" (score mais próximo de 1).
    IsolationTree tree = make_test_tree();
    float features_short[1] = {0.8f}; // path = 1
    float features_long[1] = {0.2f};  // path = 1 + c(4), bem maior

    float score_short = 0.0f;
    float score_long = 0.0f;
    ASSERT_STATUS(kaelix::Status::Ok,
                  isolation_forest_score(features_short, 1, &tree, 1, 256, &score_short));
    ASSERT_STATUS(kaelix::Status::Ok,
                  isolation_forest_score(features_long, 1, &tree, 1, 256, &score_long));

    TEST_ASSERT_TRUE(score_short > score_long);
}

// 24 scores (6 vetores de feature x 4 tamanhos de subamostra) conferidos
// bit a bit contra a implementação anterior à blindagem.
void test_forest_score_regression_bit_exact(void) {
    static const int32_t kSubsample[4] = {2, 8, 256, 4096};
    static const float kExpected[24] = {
        0.0679419413f, 0.0849394202f, 0.0423431247f, 0.0352034047f, 0.0278645698f, 0.0423431247f,
        0.442282677f,  0.473280519f,  0.383177847f,  0.362301588f,  0.337495416f,  0.383177847f,
        0.769137681f,  0.786085069f,  0.734444916f,  0.72132504f,   0.705050707f,  0.734444916f,
        0.843407929f,  0.855419278f,  0.818525612f,  0.809008718f,  0.797118783f,  0.818525612f,
    };

    int index = 0;
    for (int s = 0; s < 4; ++s) {
        for (int i = 0; i < 6; ++i) {
            float score = 0.0f;
            ASSERT_STATUS(kaelix::Status::Ok,
                          isolation_forest_score(kCases[i], 4, kForest, 2, kSubsample[s], &score));
            ASSERT_FLOAT_BIT_EXACT(kExpected[index], score);
            ++index;
        }
    }
}

// =====================================================================
// Robustez da travessia — REQ-ML-002
// =====================================================================

// O caso que motivou a cota: filho apontando para o próprio nó. Antes
// desta rodada o `while` girava para sempre e o dispositivo ficava
// acordado a ~40 mA até a bateria acabar. Se a cota sumir, este teste
// não falha — ele TRAVA, que é exatamente o defeito sendo demonstrado.
void test_tree_path_length_self_referencing_child_returns_depth_exceeded(void) {
    IsolationTree tree = make_mutable_tree();
    g_left[0] = 0;
    g_right[0] = 0;

    float features[1] = {0.2f};
    float path = 0.0f;
    ASSERT_STATUS(kaelix::Status::ModelDepthExceeded,
                  isolation_tree_path_length(tree, features, 1, &path));
    ASSERT_FLOAT_BIT_EXACT(0.0f, path); // nenhum caminho plausível é escrito
}

// max_depth corrompida não pode alargar a cota: o teto do projeto
// (ISOLATION_TREE_MAX_DEPTH) continua limitando a travessia.
void test_tree_path_length_corrupt_max_depth_still_terminates(void) {
    IsolationTree tree = make_mutable_tree();
    g_left[0] = 0;
    g_right[0] = 0;
    tree.max_depth = 32767;

    float features[1] = {0.2f};
    float path = 0.0f;
    ASSERT_STATUS(kaelix::Status::ModelDepthExceeded,
                  isolation_tree_path_length(tree, features, 1, &path));
}

void test_tree_path_length_child_beyond_n_nodes_returns_malformed(void) {
    IsolationTree tree = make_mutable_tree();
    g_left[0] = 99; // fora dos 3 nós: antes indexava memória alheia

    float features[1] = {0.2f};
    float path = 0.0f;
    ASSERT_STATUS(kaelix::Status::ModelMalformed,
                  isolation_tree_path_length(tree, features, 1, &path));
}

void test_tree_path_length_negative_child_returns_malformed(void) {
    IsolationTree tree = make_mutable_tree();
    g_left[0] = -7; // índice com sinal: lia ANTES do início do array

    float features[1] = {0.2f};
    float path = 0.0f;
    ASSERT_STATUS(kaelix::Status::ModelMalformed,
                  isolation_tree_path_length(tree, features, 1, &path));
}

void test_tree_path_length_root_out_of_range_returns_malformed(void) {
    IsolationTree tree = make_mutable_tree();
    tree.root = 3; // n_nodes == 3, logo o índice válido máximo é 2

    float features[1] = {0.2f};
    float path = 0.0f;
    ASSERT_STATUS(kaelix::Status::ModelMalformed,
                  isolation_tree_path_length(tree, features, 1, &path));
}

// Índice de feature vindo do dado, maior que o vetor que o firmware
// monta em src/ml/model.cpp: lia fora do vetor de features do chamador.
void test_tree_path_length_feature_index_beyond_vector_returns_index_out_of_range(void) {
    IsolationTree tree = make_mutable_tree();
    g_feature[0] = 4; // o chamador passa n_features = 1

    float features[1] = {0.2f};
    float path = 0.0f;
    ASSERT_STATUS(kaelix::Status::IndexOutOfRange,
                  isolation_tree_path_length(tree, features, 1, &path));
}

// -1 é folha; qualquer outro negativo é corrupção. Tratá-lo como folha
// devolveria um caminho curto, isto é, anomalia inventada.
void test_tree_path_length_corrupt_leaf_marker_returns_malformed(void) {
    IsolationTree tree = make_mutable_tree();
    g_feature[0] = -7;

    float features[1] = {0.2f};
    float path = 0.0f;
    ASSERT_STATUS(kaelix::Status::ModelMalformed,
                  isolation_tree_path_length(tree, features, 1, &path));
}

void test_tree_path_length_null_array_returns_malformed(void) {
    IsolationTree tree = make_mutable_tree();
    tree.threshold = nullptr;

    float features[1] = {0.2f};
    float path = 0.0f;
    ASSERT_STATUS(kaelix::Status::ModelMalformed,
                  isolation_tree_path_length(tree, features, 1, &path));
}

void test_tree_path_length_zero_nodes_returns_malformed(void) {
    IsolationTree tree = make_mutable_tree();
    tree.n_nodes = 0; // é o que uma árvore exportada por um gerador antigo produz

    float features[1] = {0.2f};
    float path = 0.0f;
    ASSERT_STATUS(kaelix::Status::ModelMalformed,
                  isolation_tree_path_length(tree, features, 1, &path));
}

// =====================================================================
// Robustez do score
// =====================================================================

// n_trees = 0 devolvia NaN (0/0), e NaN comparado com o limiar de
// anomalia é sempre falso: o detector saía classificando "Normal".
void test_forest_score_zero_trees_returns_model_absent(void) {
    IsolationTree tree = make_test_tree();
    float features[1] = {0.8f};
    float score = -1.0f;

    ASSERT_STATUS(kaelix::Status::ModelAbsent,
                  isolation_forest_score(features, 1, &tree, 0, 256, &score));
    ASSERT_FLOAT_BIT_EXACT(-1.0f, score); // nenhum score é escrito no erro
}

// n_trees negativo fazia o laço não executar e a função devolver
// exatamente 1.0 — anomalia máxima a partir de um argumento inválido.
void test_forest_score_negative_trees_returns_model_absent(void) {
    IsolationTree tree = make_test_tree();
    float features[1] = {0.8f};
    float score = -1.0f;

    ASSERT_STATUS(kaelix::Status::ModelAbsent,
                  isolation_forest_score(features, 1, &tree, -1, 256, &score));
    ASSERT_FLOAT_BIT_EXACT(-1.0f, score);
}

void test_forest_score_malformed_tree_propagates_error(void) {
    IsolationTree tree = make_mutable_tree();
    g_left[0] = 99;
    float features[1] = {0.2f};
    float score = -1.0f;

    ASSERT_STATUS(kaelix::Status::ModelMalformed,
                  isolation_forest_score(features, 1, &tree, 1, 256, &score));
    ASSERT_FLOAT_BIT_EXACT(-1.0f, score);
}

void test_forest_score_cyclic_tree_propagates_depth_exceeded(void) {
    IsolationTree tree = make_mutable_tree();
    g_left[0] = 0;
    g_right[0] = 0;
    float features[1] = {0.2f};
    float score = -1.0f;

    ASSERT_STATUS(kaelix::Status::ModelDepthExceeded,
                  isolation_forest_score(features, 1, &tree, 1, 256, &score));
    ASSERT_FLOAT_BIT_EXACT(-1.0f, score);
}

// =====================================================================
// Validação de modelo (roda uma vez em model_init, não no caminho quente)
// =====================================================================

void test_validate_accepts_wellformed_forest(void) {
    ASSERT_STATUS(kaelix::Status::Ok, isolation_forest_validate(kForest, 2, 4));
}

void test_validate_rejects_zero_trees_as_model_absent(void) {
    ASSERT_STATUS(kaelix::Status::ModelAbsent, isolation_forest_validate(kForest, 0, 4));
}

// Filho apontando para trás é a assinatura de um ciclo: os nós do
// sklearn são numerados em profundidade, logo todo filho vem depois do
// pai. É esta verificação que prova a ausência de ciclo na
// inicialização, sem memória auxiliar.
void test_validate_rejects_backward_child_as_malformed(void) {
    IsolationTree tree = make_mutable_tree();
    g_left[0] = 0;
    ASSERT_STATUS(kaelix::Status::ModelMalformed, isolation_forest_validate(&tree, 1, 4));
}

void test_validate_rejects_child_beyond_n_nodes_as_malformed(void) {
    IsolationTree tree = make_mutable_tree();
    g_right[0] = 3; // n_nodes == 3
    ASSERT_STATUS(kaelix::Status::ModelMalformed, isolation_forest_validate(&tree, 1, 4));
}

// Índice de feature além do que o firmware monta é desalinhamento entre
// treino e inferência, não corrupção genérica — daí um status próprio.
void test_validate_rejects_feature_index_beyond_n_features(void) {
    IsolationTree tree = make_mutable_tree();
    g_feature[0] = 9; // o firmware monta 4 features em src/ml/model.cpp
    ASSERT_STATUS(kaelix::Status::ModelFeatureMismatch, isolation_forest_validate(&tree, 1, 4));
}

void test_validate_rejects_non_finite_threshold(void) {
    IsolationTree tree = make_mutable_tree();
    g_threshold[0] = NAN;
    ASSERT_STATUS(kaelix::Status::ModelMalformed, isolation_forest_validate(&tree, 1, 4));
}

void test_validate_rejects_non_finite_leaf_correction(void) {
    IsolationTree tree = make_mutable_tree();
    g_leaf_correction[1] = INFINITY;
    ASSERT_STATUS(kaelix::Status::ModelMalformed, isolation_forest_validate(&tree, 1, 4));
}

void test_validate_rejects_null_array_as_malformed(void) {
    IsolationTree tree = make_mutable_tree();
    tree.left = nullptr;
    ASSERT_STATUS(kaelix::Status::ModelMalformed, isolation_forest_validate(&tree, 1, 4));
}

// O caso concreto de hoje: um header gerado pelo exportador antigo não
// emite n_nodes, o campo fica em 0 e a árvore inteira é irrastreável.
void test_validate_rejects_zero_nodes_as_malformed(void) {
    IsolationTree tree = make_mutable_tree();
    tree.n_nodes = 0;
    ASSERT_STATUS(kaelix::Status::ModelMalformed, isolation_forest_validate(&tree, 1, 4));
}

void test_validate_rejects_root_out_of_range_as_malformed(void) {
    IsolationTree tree = make_mutable_tree();
    tree.root = -1;
    ASSERT_STATUS(kaelix::Status::ModelMalformed, isolation_forest_validate(&tree, 1, 4));
}

void test_validate_rejects_max_depth_beyond_project_limit(void) {
    IsolationTree tree = make_mutable_tree();
    tree.max_depth = static_cast<int16_t>(ISOLATION_TREE_MAX_DEPTH + 1);
    ASSERT_STATUS(kaelix::Status::ModelMalformed, isolation_forest_validate(&tree, 1, 4));
}

// =====================================================================
// Violações de contrato (bug do chamador, não dado corrompido)
// =====================================================================
//
// No build de desenvolvimento KAELIX_REQUIRE aborta de propósito
// (docs/ARQUITETURA-SOFTWARE.md §5), então estes casos só podem ser
// exercitados com a semântica de produção: compile com
// -D KAELIX_PRODUCTION ou -D KAELIX_ASSERT_ABORT=0. Fora dela, os casos
// não são registrados — não são silenciados, simplesmente não existem
// naquele build.
#if !KAELIX_ASSERT_ABORT
void test_tree_path_length_null_features_returns_null_pointer(void) {
    IsolationTree tree = make_test_tree();
    float path = 0.0f;
    ASSERT_STATUS(kaelix::Status::NullPointer,
                  isolation_tree_path_length(tree, nullptr, 1, &path));
}

void test_tree_path_length_null_out_returns_null_pointer(void) {
    IsolationTree tree = make_test_tree();
    float features[1] = {0.2f};
    ASSERT_STATUS(kaelix::Status::NullPointer,
                  isolation_tree_path_length(tree, features, 1, nullptr));
}

void test_forest_score_null_trees_returns_null_pointer(void) {
    float features[1] = {0.8f};
    float score = 0.0f;
    ASSERT_STATUS(kaelix::Status::NullPointer,
                  isolation_forest_score(features, 1, nullptr, 1, 256, &score));
}

void test_forest_score_zero_features_returns_invalid_argument(void) {
    IsolationTree tree = make_test_tree();
    float features[1] = {0.8f};
    float score = 0.0f;
    ASSERT_STATUS(kaelix::Status::InvalidArgument,
                  isolation_forest_score(features, 0, &tree, 1, 256, &score));
}

// subsample_size <= 1 daria c(n) = 0 e divisão por zero no expoente.
void test_forest_score_subsample_one_returns_invalid_argument(void) {
    IsolationTree tree = make_test_tree();
    float features[1] = {0.8f};
    float score = 0.0f;
    ASSERT_STATUS(kaelix::Status::InvalidArgument,
                  isolation_forest_score(features, 1, &tree, 1, 1, &score));
}

void test_validate_null_trees_returns_null_pointer(void) {
    ASSERT_STATUS(kaelix::Status::NullPointer, isolation_forest_validate(nullptr, 1, 4));
}
#endif // !KAELIX_ASSERT_ABORT

int main(void) {
    UNITY_BEGIN();

    RUN_TEST(test_path_length_correction_known_values);
    RUN_TEST(test_path_length_correction_regression_bit_exact);
    RUN_TEST(test_tree_path_length_left_leaf);
    RUN_TEST(test_tree_path_length_right_leaf);
    RUN_TEST(test_tree_path_length_regression_bit_exact);

    RUN_TEST(test_forest_score_matches_manual_formula);
    RUN_TEST(test_shorter_path_scores_higher_than_longer_path);
    RUN_TEST(test_forest_score_regression_bit_exact);

    RUN_TEST(test_tree_path_length_self_referencing_child_returns_depth_exceeded);
    RUN_TEST(test_tree_path_length_corrupt_max_depth_still_terminates);
    RUN_TEST(test_tree_path_length_child_beyond_n_nodes_returns_malformed);
    RUN_TEST(test_tree_path_length_negative_child_returns_malformed);
    RUN_TEST(test_tree_path_length_root_out_of_range_returns_malformed);
    RUN_TEST(test_tree_path_length_feature_index_beyond_vector_returns_index_out_of_range);
    RUN_TEST(test_tree_path_length_corrupt_leaf_marker_returns_malformed);
    RUN_TEST(test_tree_path_length_null_array_returns_malformed);
    RUN_TEST(test_tree_path_length_zero_nodes_returns_malformed);

    RUN_TEST(test_forest_score_zero_trees_returns_model_absent);
    RUN_TEST(test_forest_score_negative_trees_returns_model_absent);
    RUN_TEST(test_forest_score_malformed_tree_propagates_error);
    RUN_TEST(test_forest_score_cyclic_tree_propagates_depth_exceeded);

    RUN_TEST(test_validate_accepts_wellformed_forest);
    RUN_TEST(test_validate_rejects_zero_trees_as_model_absent);
    RUN_TEST(test_validate_rejects_backward_child_as_malformed);
    RUN_TEST(test_validate_rejects_child_beyond_n_nodes_as_malformed);
    RUN_TEST(test_validate_rejects_feature_index_beyond_n_features);
    RUN_TEST(test_validate_rejects_non_finite_threshold);
    RUN_TEST(test_validate_rejects_non_finite_leaf_correction);
    RUN_TEST(test_validate_rejects_null_array_as_malformed);
    RUN_TEST(test_validate_rejects_zero_nodes_as_malformed);
    RUN_TEST(test_validate_rejects_root_out_of_range_as_malformed);
    RUN_TEST(test_validate_rejects_max_depth_beyond_project_limit);

#if !KAELIX_ASSERT_ABORT
    RUN_TEST(test_tree_path_length_null_features_returns_null_pointer);
    RUN_TEST(test_tree_path_length_null_out_returns_null_pointer);
    RUN_TEST(test_forest_score_null_trees_returns_null_pointer);
    RUN_TEST(test_forest_score_zero_features_returns_invalid_argument);
    RUN_TEST(test_forest_score_subsample_one_returns_invalid_argument);
    RUN_TEST(test_validate_null_trees_returns_null_pointer);
#endif

    return UNITY_END();
}
