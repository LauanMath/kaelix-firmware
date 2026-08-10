#include "isolation_forest.h"

#include <cmath>

namespace kaelix::ml {

float isolation_path_length_correction(int n) {
    if (n <= 1) return 0.0f;
    if (n == 2) return 1.0f;
    constexpr float EULER_GAMMA = 0.5772156649f;
    return 2.0f * (std::log(float(n - 1)) + EULER_GAMMA) - 2.0f * float(n - 1) / float(n);
}

float isolation_tree_path_length(const IsolationTree& tree, const float* features) {
    int16_t node = tree.root;
    int depth = 0;
    while (tree.feature[node] != -1) {
        node = (features[tree.feature[node]] < tree.threshold[node]) ? tree.left[node] : tree.right[node];
        ++depth;
    }
    return float(depth) + tree.leaf_correction[node];
}

float isolation_forest_score(const float* features, const IsolationTree* trees, int n_trees, int subsample_size) {
    float total_path = 0.0f;
    for (int i = 0; i < n_trees; ++i) {
        total_path += isolation_tree_path_length(trees[i], features);
    }
    float mean_path = total_path / float(n_trees);
    float c = isolation_path_length_correction(subsample_size);
    if (c <= 0.0f) return 0.5f;
    return std::pow(2.0f, -mean_path / c);
}

} // namespace kaelix::ml
