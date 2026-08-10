#include <unity.h>

#include <cmath>

#include "isolation_forest.h"

using namespace kaelix::ml;

void setUp(void) {}
void tearDown(void) {}

// c(n) — valores de referência calculados independentemente (mesma
// fórmula usada pelo scikit-learn: sklearn/ensemble/_iforest.py).
void test_path_length_correction_known_values(void) {
    TEST_ASSERT_FLOAT_WITHIN(1e-6f, 0.0f, isolation_path_length_correction(1));
    TEST_ASSERT_FLOAT_WITHIN(1e-6f, 1.0f, isolation_path_length_correction(2));
    TEST_ASSERT_FLOAT_WITHIN(1e-4f, 1.207392f, isolation_path_length_correction(3));
    TEST_ASSERT_FLOAT_WITHIN(1e-4f, 1.851656f, isolation_path_length_correction(4));
    TEST_ASSERT_FLOAT_WITHIN(1e-3f, 10.244771f, isolation_path_length_correction(256));
}

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
    return tree;
}

void test_tree_path_length_left_leaf(void) {
    IsolationTree tree = make_test_tree();
    float features[1] = {0.2f}; // < 0.5 -> folha esquerda (depth 1 + c(4))
    float path = isolation_tree_path_length(tree, features);
    TEST_ASSERT_FLOAT_WITHIN(1e-4f, 1.0f + 1.8516559f, path);
}

void test_tree_path_length_right_leaf(void) {
    IsolationTree tree = make_test_tree();
    float features[1] = {0.8f}; // >= 0.5 -> folha direita (depth 1 + c(1)=0)
    float path = isolation_tree_path_length(tree, features);
    TEST_ASSERT_FLOAT_WITHIN(1e-4f, 1.0f, path);
}

void test_forest_score_matches_manual_formula(void) {
    IsolationTree tree = make_test_tree();
    float features[1] = {0.8f}; // caminho curto (path=1) -> score mais alto (mais anômalo)

    const int subsample_size = 256;
    float score = isolation_forest_score(features, &tree, 1, subsample_size);

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

    float score_short = isolation_forest_score(features_short, &tree, 1, 256);
    float score_long = isolation_forest_score(features_long, &tree, 1, 256);

    TEST_ASSERT_TRUE(score_short > score_long);
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_path_length_correction_known_values);
    RUN_TEST(test_tree_path_length_left_leaf);
    RUN_TEST(test_tree_path_length_right_leaf);
    RUN_TEST(test_forest_score_matches_manual_formula);
    RUN_TEST(test_shorter_path_scores_higher_than_longer_path);
    return UNITY_END();
}
