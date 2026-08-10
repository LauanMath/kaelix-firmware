"""Orquestra o treino do Isolation Forest: carrega dados (MAFAULDA/CWRU
se presentes em data/, senão cai para dados sintéticos com aviso claro),
extrai as mesmas features do firmware, treina sobre o subconjunto
"normal" (semi-supervisionado — prática padrão para Isolation Forest),
avalia contra rótulos de referência e exporta para C++.

Uso: python -m kaelix_ml.train [--out ARQUIVO_SAIDA.h]
"""

import argparse
import sys
from pathlib import Path

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.metrics import classification_report, confusion_matrix

from . import dataset, export_cpp
from .features import FEATURE_ORDER, extract_features, features_to_vector
from .labeling import label_from_acceleration

DEFAULT_OUTPUT = Path(__file__).resolve().parents[2] / "src" / "ml" / "isolation_forest_data.h"


def load_real_or_synthetic():
    """Tenta carregar MAFAULDA/CWRU de data/; se não houver, gera dados
    sintéticos (com rótulo já conhecido) para validar o pipeline."""
    try:
        mafaulda_files = list(dataset.iter_dataset_files("mafaulda", "*.csv"))
    except FileNotFoundError:
        mafaulda_files = []

    if mafaulda_files:
        print(f"[train] {len(mafaulda_files)} arquivo(s) MAFAULDA encontrado(s) em data/mafaulda/")
        vib_samples = [dataset.load_mafaulda_csv(p) for p in mafaulda_files]
        labeled_by_iso = True
    else:
        print(
            "[train] AVISO: nenhum dado real do MAFAULDA/CWRU encontrado em data/. "
            "Usando dados SINTÉTICOS só para validar o pipeline ponta-a-ponta — "
            "NÃO é um modelo treinado para uso real.",
            file=sys.stderr,
        )
        vib_samples = dataset.generate_synthetic_dataset()
        labeled_by_iso = False

    return vib_samples, labeled_by_iso


def build_feature_matrix(vib_samples, labeled_by_iso, machine_class="I"):
    X = []
    y = []
    for s in vib_samples:
        feats = extract_features(s.accel, s.sample_rate_hz)
        X.append(features_to_vector(feats))
        if labeled_by_iso:
            y.append(label_from_acceleration(s.accel, s.sample_rate_hz, machine_class))
        else:
            y.append(s.label)  # já rotulado (dados sintéticos)
    return np.array(X), np.array(y)


def train(output_path: Path = DEFAULT_OUTPUT, machine_class: str = "I") -> dict:
    vib_samples, labeled_by_iso = load_real_or_synthetic()
    X, y = build_feature_matrix(vib_samples, labeled_by_iso, machine_class)

    X_normal = X[y == "normal"]
    if len(X_normal) < 10:
        raise ValueError(f"poucas amostras 'normal' para treinar ({len(X_normal)}) — verifique os dados/rotulagem")

    subsample_size = min(256, len(X_normal))
    clf = IsolationForest(n_estimators=100, max_samples=subsample_size, contamination="auto", random_state=42)
    clf.fit(X_normal)

    y_pred = clf.predict(X)  # -1 = anômalo, 1 = normal
    y_pred_label = np.where(y_pred == -1, "anomalous", "normal")

    print("[train] features:", FEATURE_ORDER)
    print("[train] amostras normal/anômalo (rótulo de referência):", (y == "normal").sum(), (y == "anomalous").sum())
    print(classification_report(y, y_pred_label, zero_division=0))
    print("matriz de confusão (linhas=referência, colunas=predito) [anomalous, normal]:")
    print(confusion_matrix(y, y_pred_label, labels=["anomalous", "normal"]))

    anomaly_threshold = 0.5  # limiar padrão do artigo original do Isolation Forest
    export_cpp.export_isolation_forest(
        clf,
        output_path,
        anomaly_threshold=anomaly_threshold,
        subsample_size=subsample_size,
        n_features=len(FEATURE_ORDER),
    )
    print(f"[train] header C++ exportado para {output_path}")

    return {"clf": clf, "X": X, "y": y, "labeled_by_iso": labeled_by_iso}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--machine-class", default="I", choices=["I", "II", "III", "IV"])
    args = parser.parse_args()
    train(output_path=args.out, machine_class=args.machine_class)
