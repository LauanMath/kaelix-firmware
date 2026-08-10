"""Exporta um IsolationForest treinado (scikit-learn) para um header
C++ consumido por lib/isolation_forest (ver src/ml/isolation_forest_data.h).

Cada árvore do ensemble vira 5 arrays C (feature, threshold, left,
right, leaf_correction); folhas usam feature=-1 (convenção do C++,
diferente do -2 do sklearn) e leaf_correction = c(n_amostras_na_folha)
via a mesma fórmula usada internamente pelo sklearn.
"""

import math

TREE_LEAF = -1  # sklearn usa -1 para "sem filho" em children_left/right


def _path_length_correction(n: int) -> float:
    if n <= 1:
        return 0.0
    if n == 2:
        return 1.0
    euler_gamma = 0.5772156649015329
    return 2.0 * (math.log(n - 1) + euler_gamma) - 2.0 * (n - 1) / n


def _format_float(v: float) -> str:
    s = f"{v:.8g}"
    if "." not in s and "e" not in s and "E" not in s:
        s += ".0"  # "2f" não é um literal float válido em C++; precisa de "2.0f"
    return s + "f"


def _format_float_array(values) -> str:
    return ", ".join(_format_float(v) for v in values)


def _format_int_array(values) -> str:
    return ", ".join(str(int(v)) for v in values)


def _export_tree(estimator, index: int) -> tuple:
    """Retorna (declarações C++, nome das 5 arrays) para uma árvore."""
    tree = estimator.tree_
    n_nodes = tree.node_count

    feature_out = [0] * n_nodes
    leaf_correction = [0.0] * n_nodes

    for i in range(n_nodes):
        if tree.children_left[i] == TREE_LEAF:
            feature_out[i] = -1
            leaf_correction[i] = _path_length_correction(int(tree.n_node_samples[i]))
        else:
            feature_out[i] = int(tree.feature[i])

    names = {
        "feature": f"tree{index}_feature",
        "threshold": f"tree{index}_threshold",
        "left": f"tree{index}_left",
        "right": f"tree{index}_right",
        "leaf_correction": f"tree{index}_leaf_correction",
    }

    decl = (
        f"static const int16_t {names['feature']}[] = {{{_format_int_array(feature_out)}}};\n"
        f"static const float {names['threshold']}[] = {{{_format_float_array(tree.threshold)}}};\n"
        f"static const int16_t {names['left']}[] = {{{_format_int_array(tree.children_left)}}};\n"
        f"static const int16_t {names['right']}[] = {{{_format_int_array(tree.children_right)}}};\n"
        f"static const float {names['leaf_correction']}[] = {{{_format_float_array(leaf_correction)}}};\n"
    )
    return decl, names


def export_isolation_forest(
    clf,
    output_path,
    anomaly_threshold: float,
    subsample_size: int,
    n_features: int,
) -> None:
    """Escreve o header C++ com as árvores de `clf` (sklearn IsolationForest já treinado)."""
    tree_decls = []
    tree_struct_entries = []

    for i, estimator in enumerate(clf.estimators_):
        decl, names = _export_tree(estimator, i)
        tree_decls.append(decl)
        tree_struct_entries.append(
            f"    {{{names['feature']}, {names['threshold']}, {names['left']}, {names['right']}, {names['leaf_correction']}, 0}},"
        )

    header = f"""#pragma once

// AUTOGERADO por training/kaelix_ml/export_cpp.py — não editar manualmente.
// Isolation Forest treinado com {len(clf.estimators_)} árvores.

#include <cstdint>
#include "isolation_forest.h"

namespace kaelix::ml {{

inline constexpr int N_FEATURES = {n_features};
inline constexpr int N_TREES = {len(clf.estimators_)};
inline constexpr int SUBSAMPLE_SIZE = {subsample_size};
inline constexpr float ANOMALY_THRESHOLD = {anomaly_threshold:.8g}f;

{"".join(tree_decls)}
inline const IsolationTree isolation_forest_trees[] = {{
{chr(10).join(tree_struct_entries)}
}};

}} // namespace kaelix::ml
"""
    output_path = str(output_path)
    with open(output_path, "w") as f:
        f.write(header)
