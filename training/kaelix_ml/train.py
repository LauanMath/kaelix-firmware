"""Orquestra o treino do Isolation Forest.

Três decisões de método, todas vindas de docs/questionamentos-tecnicos.md:

**Split por grupo (item 6).** A validação usa `GroupKFold` com o arquivo
de origem como grupo. Janelas do mesmo ensaio nunca ficam dos dois lados
do split — é o vazamento que o item 6 mediu inflando a acurácia em ~36
pontos. Antes não havia split algum: o código dava `fit(X_normal)` e
logo `predict(X)` sobre o mesmo conjunto.

**Limiar por taxa de falso alarme alvo (item 7).** O limiar não é 0,5 nem
vem do `contamination`: é o quantile `1 - FALSE_ALARM_TARGET` dos scores
de um conjunto de calibração formado por grupos que o modelo não viu. O
default `contamination="auto"` marcaria 42% da operação normal como
anomalia.

**Mesma regra de decisão do firmware.** Tudo aqui usa `device_score()`,
que é `-clf.score_samples(X)` — a convenção (0,1] do artigo original,
idêntica à de `lib/isolation_forest/isolation_forest.cpp` e verificada
por `tests/test_export_cpp.py`. Antes a avaliação usava `clf.predict()`,
que decide pelo `offset_`, então o relatório impresso no treino não
descrevia o que o dispositivo faria.

Uso: python -m kaelix_ml.train [--out ARQUIVO_SAIDA.h]
"""

import argparse
import sys
from pathlib import Path

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.metrics import confusion_matrix, f1_score, roc_auc_score
from sklearn.model_selection import GroupKFold, GroupShuffleSplit

from . import dataset, export_cpp
from .features import FEATURE_ORDER, extract_features, features_to_vector
from .labeling import label_from_acceleration

DEFAULT_OUTPUT = Path(__file__).resolve().parents[2] / "src" / "ml" / "isolation_forest_data.h"

# Taxa de falso alarme alvo. Num dispositivo que dispara ordem de
# manutenção, é este número — não a acurácia — que decide se o operador
# continua confiando no sistema.
FALSE_ALARM_TARGET = 0.01

# pAUC restrita a FPR <= 0,10, protocolo do DCASE2020 Task 2. Mesma
# chamada de figures/scripts/export_source_data.py, para que os números
# sejam comparáveis com a Fig. 2e. (Crítica A1 de criticas-da-literatura.md.)
PAUC_MAX_FPR = 0.10

N_ESTIMATORS = 100
RANDOM_STATE = 42
CALIBRATION_GROUP_FRACTION = 0.25
MIN_NORMAL_SAMPLES = 10


def device_score(clf, X):
    """Score de anomalia na convenção do firmware: 2^(-E[h(x)]/c(n)),
    em (0,1], alto = anômalo. `score_samples` do sklearn devolve o
    negativo disso."""
    return -clf.score_samples(X)


def load_real_or_synthetic():
    """Tenta carregar MAFAULDA, depois CWRU, de data/; se não houver,
    gera dados sintéticos. O retorno já vem no domínio do firmware
    (1 kHz, janelas de 512 amostras) — ver dataset.to_device_windows."""
    for name in ("mafaulda", "cwru"):
        try:
            windows = dataset.load_device_windows(name)
        except FileNotFoundError:
            continue
        if windows:
            n_files = len({w.group for w in windows})
            print(f"[train] {name.upper()}: {n_files} arquivo(s) -> {len(windows)} janelas de "
                  f"{dataset.DEVICE_WINDOW_SAMPLES} amostras @ {dataset.DEVICE_SAMPLE_RATE_HZ:.0f} Hz")
            return windows, True

    print(
        "[train] AVISO: nenhum dado real do MAFAULDA/CWRU encontrado em data/. "
        "Usando dados SINTÉTICOS só para validar o pipeline ponta-a-ponta — "
        "NÃO é um modelo treinado para uso real.",
        file=sys.stderr,
    )
    windows = []
    for s in dataset.generate_synthetic_dataset():
        windows.extend(dataset.to_device_windows(s))
    return windows, False


def build_feature_matrix(windows, machine_class="I"):
    """Features + rótulo de referência + grupo + rótulo ISO.

    O rótulo de referência (`y`) vem do caminho do arquivo quando o
    dataset o codifica; o rótulo ISO (`y_iso`) é calculado em paralelo e
    serve só para comparação — não para treinar."""
    X, y, groups, y_iso, fault_classes = [], [], [], [], []
    for w in windows:
        X.append(features_to_vector(extract_features(w.accel, w.sample_rate_hz)))
        y.append(w.label)
        groups.append(w.group)
        y_iso.append(label_from_acceleration(w.accel, w.sample_rate_hz, machine_class))
        fault_classes.append(w.fault_class)
    return (np.array(X), np.array(y), np.array(groups),
            np.array(y_iso), np.array(fault_classes))


def _fit_isolation_forest(X_normal):
    subsample = min(256, len(X_normal))
    clf = IsolationForest(
        n_estimators=N_ESTIMATORS,
        max_samples=subsample,
        # Não usamos clf.predict() — a decisão é score > limiar calibrado.
        # Fixamos contamination no alvo para que offset_ fique coerente,
        # em vez do "auto" que o item 7 mediu em 42% de falso alarme.
        contamination=FALSE_ALARM_TARGET,
        random_state=RANDOM_STATE,
    )
    clf.fit(X_normal)
    return clf


def _calibrate_threshold(clf, X_calib_normal):
    """Limiar no quantil que deixa FALSE_ALARM_TARGET dos normais acima
    dele. Calibrado em grupos que o modelo não viu no fit."""
    scores = device_score(clf, X_calib_normal)
    return float(np.quantile(scores, 1.0 - FALSE_ALARM_TARGET))


def _fit_and_calibrate(X, y, groups, seed=RANDOM_STATE):
    """Separa grupos de fit e de calibração dentro do conjunto de treino,
    devolve (modelo, limiar). Calibrar no mesmo dado do fit produziria
    limiar otimista."""
    normal = y == "normal"
    X_n, g_n = X[normal], groups[normal]
    if len(X_n) < MIN_NORMAL_SAMPLES:
        raise ValueError(f"poucas amostras 'normal' para treinar ({len(X_n)}) — verifique os dados/rotulagem")

    unique_groups = np.unique(g_n)
    if len(unique_groups) < 2:
        # Sem grupos suficientes para separar calibração — calibra no
        # próprio treino e avisa, em vez de falhar.
        clf = _fit_isolation_forest(X_n)
        print("[train] AVISO: só um grupo normal disponível; limiar calibrado no próprio "
              "conjunto de fit (otimista).", file=sys.stderr)
        return clf, _calibrate_threshold(clf, X_n)

    splitter = GroupShuffleSplit(n_splits=1, test_size=CALIBRATION_GROUP_FRACTION, random_state=seed)
    fit_idx, calib_idx = next(splitter.split(X_n, groups=g_n))
    clf = _fit_isolation_forest(X_n[fit_idx])
    return clf, _calibrate_threshold(clf, X_n[calib_idx])


def _fold_metrics(clf, threshold, X_val, y_val):
    scores = device_score(clf, X_val)
    pred = np.where(scores > threshold, "anomalous", "normal")

    is_normal = y_val == "normal"
    is_anom = ~is_normal
    metrics = {
        "falso_alarme": float(np.mean(pred[is_normal] == "anomalous")) if is_normal.any() else np.nan,
        "deteccao": float(np.mean(pred[is_anom] == "anomalous")) if is_anom.any() else np.nan,
        "f1": f1_score(y_val, pred, pos_label="anomalous", zero_division=0),
        "auc": np.nan,
        "pauc": np.nan,
    }
    # AUC exige as duas classes presentes no fold.
    if is_normal.any() and is_anom.any():
        y_bin = (y_val == "anomalous").astype(int)
        metrics["auc"] = roc_auc_score(y_bin, scores)
        metrics["pauc"] = roc_auc_score(y_bin, scores, max_fpr=PAUC_MAX_FPR)
    return metrics


def cross_validate(X, y, groups, n_splits=5):
    """GroupKFold pelo arquivo de origem (item 6). Reporta média e desvio
    entre folds — desvio alto significa que faltam ensaios, e esconder
    isso atrás de um número único é o que o item 6 critica."""
    n_groups = len(np.unique(groups))
    n_splits = min(n_splits, n_groups)
    if n_splits < 2:
        print("[train] AVISO: grupos insuficientes para validação cruzada.", file=sys.stderr)
        return []

    results = []
    for fold, (tr, va) in enumerate(GroupKFold(n_splits=n_splits).split(X, y, groups)):
        if not (y[tr] == "normal").any():
            continue
        try:
            clf, thr = _fit_and_calibrate(X[tr], y[tr], groups[tr], seed=RANDOM_STATE + fold)
        except ValueError as exc:
            print(f"[train] fold {fold} ignorado: {exc}", file=sys.stderr)
            continue
        m = _fold_metrics(clf, thr, X[va], y[va])
        m["fold"] = fold
        m["limiar"] = thr
        results.append(m)
    return results


def _report_cv(results):
    if not results:
        print("[train] sem folds válidos para reportar.")
        return
    print(f"\n[train] validação cruzada — GroupKFold por arquivo de origem, {len(results)} folds")
    print(f"        limiar por fold: quantil {1 - FALSE_ALARM_TARGET:.0%} dos scores normais de calibração")
    print(f"  {'fold':>4}  {'falso alarme':>12}  {'detecção':>9}  {'F1':>6}  {'AUC':>6}  {'pAUC':>6}  {'limiar':>7}")
    for m in results:
        print(f"  {m['fold']:>4}  {m['falso_alarme']:>11.1%}  {m['deteccao']:>8.1%}  "
              f"{m['f1']:>6.3f}  {m['auc']:>6.3f}  {m['pauc']:>6.3f}  {m['limiar']:>7.4f}")

    def agg(key):
        vals = np.array([m[key] for m in results], dtype=float)
        vals = vals[~np.isnan(vals)]
        return (np.mean(vals), np.std(vals)) if len(vals) else (np.nan, np.nan)

    print("\n  média ± desvio entre folds:")
    for key, label in [("falso_alarme", "falso alarme"), ("deteccao", "detecção"),
                       ("f1", "F1"), ("auc", "AUC"), ("pauc", f"pAUC (FPR<={PAUC_MAX_FPR:.0%})")]:
        mean, std = agg(key)
        print(f"    {label:<22} {mean:.3f} ± {std:.3f}")
    print(f"\n  (pAUC McClish-corrigida, sklearn max_fpr={PAUC_MAX_FPR} — mesma convenção da Fig. 2e)")


def _report_iso_agreement(y, y_iso, fault_classes):
    """A ISO como diagnóstico, não como verdade. Divergência grande aqui
    é sinal de que os limiares de zona, a classe de máquina assumida ou
    a banda de medição precisam de revisão — não de que o dataset está
    errado."""
    print("\n[train] concordância entre rótulo de referência (caminho) e rótulo ISO 10816-3")
    labels = ["anomalous", "normal"]
    cm = confusion_matrix(y, y_iso, labels=labels)
    print(f"        {'':>12}  {'ISO:anômalo':>12}  {'ISO:normal':>11}")
    for row, label in zip(cm, labels):
        print(f"        ref:{label:<8}  {row[0]:>12}  {row[1]:>11}")
    agreement = float(np.mean(y == y_iso))
    print(f"        concordância global: {agreement:.1%}")

    known = sorted(set(fault_classes) - {"unknown"})
    if known:
        print("\n        por classe de falha:")
        for fc in known:
            m = fault_classes == fc
            print(f"          {fc:<26} n={m.sum():>6}  ISO marca anômalo em {np.mean(y_iso[m] == 'anomalous'):.1%}")


def train(output_path: Path = DEFAULT_OUTPUT, machine_class: str = "I") -> dict:
    windows, labeled_by_path = load_real_or_synthetic()
    X, y, groups, y_iso, fault_classes = build_feature_matrix(windows, machine_class)

    print("[train] features:", FEATURE_ORDER)
    print(f"[train] {len(X)} janelas em {len(np.unique(groups))} grupos — "
          f"normal: {(y == 'normal').sum()}, anômalo: {(y == 'anomalous').sum()}")
    if not labeled_by_path:
        print("[train] rótulos vêm do gerador sintético (não há caminho de dataset para ler).")

    _report_iso_agreement(y, y_iso, fault_classes)
    results = cross_validate(X, y, groups)
    _report_cv(results)

    # Modelo final: fit e calibração em grupos disjuntos, exportado como
    # par (modelo, limiar) coerente. A validação cruzada acima é a
    # estimativa de desempenho; este é o artefato que vai para o device.
    clf, threshold = _fit_and_calibrate(X, y, groups)
    print(f"\n[train] modelo final: {N_ESTIMATORS} árvores, max_samples={clf.max_samples_}, "
          f"limiar={threshold:.6f} (falso alarme alvo {FALSE_ALARM_TARGET:.0%})")

    export_cpp.export_isolation_forest(
        clf,
        output_path,
        anomaly_threshold=threshold,
        subsample_size=int(clf.max_samples_),
        n_features=len(FEATURE_ORDER),
    )
    print(f"[train] header C++ exportado para {output_path}")

    return {"clf": clf, "threshold": threshold, "X": X, "y": y, "groups": groups,
            "y_iso": y_iso, "cv": results, "labeled_by_path": labeled_by_path}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--machine-class", default="I", choices=["I", "II", "III", "IV"])
    args = parser.parse_args()
    train(output_path=args.out, machine_class=args.machine_class)
