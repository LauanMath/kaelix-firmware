"""Valida o export_cpp.py compilando de verdade o header gerado com o
código C++ real (lib/isolation_forest) e comparando o score calculado
em C++ contra o score do próprio scikit-learn — o objetivo é fechar o
ciclo "não haver divergência entre treino e inferência" citado no
roteiro do projeto."""

import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest
from sklearn.ensemble import IsolationForest

from kaelix_ml import export_cpp

FIRMWARE_ROOT = Path(__file__).resolve().parents[2]
LIB_ISOLATION_FOREST = FIRMWARE_ROOT / "lib" / "isolation_forest"

MAIN_CPP_TEMPLATE = """
#include <cstdio>
#include "isolation_forest.h"
#include "isolation_forest_data.h"

using namespace kaelix::ml;

int main() {
    float x[N_FEATURES];
    while (true) {
        int filled = 0;
        for (int i = 0; i < N_FEATURES; ++i) {
            if (scanf("%f", &x[i]) != 1) { filled = -1; break; }
            filled = i + 1;
        }
        if (filled != N_FEATURES) break;
        float s = isolation_forest_score(x, isolation_forest_trees, N_TREES, SUBSAMPLE_SIZE);
        printf("%.8f\\n", s);
    }
    return 0;
}
"""


def _compiler_available():
    return shutil.which("g++") is not None or shutil.which("clang++") is not None


@pytest.mark.skipif(not _compiler_available(), reason="precisa de g++ ou clang++")
def test_cpp_score_matches_sklearn_score(tmp_path):
    rng = np.random.default_rng(0)
    X_train = rng.normal(0, 1, size=(300, 4))
    clf = IsolationForest(n_estimators=50, max_samples=256, contamination="auto", random_state=0)
    clf.fit(X_train)

    header_path = tmp_path / "isolation_forest_data.h"
    export_cpp.export_isolation_forest(
        clf, header_path, anomaly_threshold=0.5, subsample_size=clf.max_samples_, n_features=4
    )

    main_cpp = tmp_path / "main.cpp"
    main_cpp.write_text(MAIN_CPP_TEMPLATE)

    binary = tmp_path / "a.out"
    compiler = shutil.which("g++") or shutil.which("clang++")
    subprocess.run(
        [
            compiler, "-std=c++17", "-O2",
            "-I", str(LIB_ISOLATION_FOREST),
            "-I", str(tmp_path),
            str(main_cpp), str(LIB_ISOLATION_FOREST / "isolation_forest.cpp"),
            "-o", str(binary),
        ],
        check=True,
    )

    X_test = rng.normal(0, 1, size=(20, 4))
    # X_test com alguns outliers propositais, para cobrir scores altos e baixos.
    X_test[:5] *= 8.0

    stdin_text = "\n".join(" ".join(f"{v:.8f}" for v in row) for row in X_test)
    result = subprocess.run([str(binary)], input=stdin_text, capture_output=True, text=True, check=True)
    cpp_scores = np.array([float(line) for line in result.stdout.strip().splitlines()])

    python_scores = -clf.score_samples(X_test)  # ver kaelix_ml/train.py: sklearn usa o sinal oposto

    assert cpp_scores.shape == python_scores.shape
    np.testing.assert_allclose(cpp_scores, python_scores, atol=1e-4)
