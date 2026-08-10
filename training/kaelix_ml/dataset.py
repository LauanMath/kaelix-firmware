"""Carregamento dos datasets MAFAULDA e CWRU Bearing Dataset — e um
gerador de dados sintéticos para testar o pipeline ponta-a-ponta antes
dos arquivos reais chegarem em data/.

TODO: os layouts abaixo (colunas do MAFAULDA, chaves do .mat do CWRU)
são os documentados publicamente para cada dataset, mas ainda não foram
conferidos contra os arquivos reais — ajustar assim que forem anexados
em data/.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import numpy as np

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

# MAFAULDA: CSV sem cabeçalho, 8 colunas, amostrado a 50kHz.
MAFAULDA_SAMPLE_RATE_HZ = 50_000.0
MAFAULDA_COLUMNS = [
    "tachometer",
    "underhang_axial",
    "underhang_radial",
    "underhang_tangential",
    "overhang_axial",
    "overhang_radial",
    "overhang_tangential",
    "microphone",
]

# CWRU: arquivos .mat (scipy.io.loadmat), variáveis terminando em
# "_DE_time" (drive-end) ou "_FE_time" (fan-end), 12kHz ou 48kHz.


@dataclass
class VibrationSample:
    accel: np.ndarray       # série temporal de aceleração (unidade depende da fonte — ver `unit`)
    sample_rate_hz: float
    unit: str                # "g" ou "m/s2"
    label: str                # "normal" | "anomalous" | "unknown" (rotulagem via ISO fica em labeling.py)
    source: str                # ex.: "mafaulda", "cwru", "synthetic"


def load_mafaulda_csv(path: Path, channel: str = "underhang_radial", label: str = "unknown") -> VibrationSample:
    """Lê um CSV do MAFAULDA e retorna a coluna de vibração escolhida.
    TODO: confirmar ordem/unidade das colunas contra o arquivo real."""
    if channel not in MAFAULDA_COLUMNS:
        raise ValueError(f"canal desconhecido: {channel}")
    col_idx = MAFAULDA_COLUMNS.index(channel)
    data = np.loadtxt(path, delimiter=",")
    accel = data[:, col_idx]
    return VibrationSample(accel=accel, sample_rate_hz=MAFAULDA_SAMPLE_RATE_HZ, unit="g", label=label, source="mafaulda")


def load_cwru_mat(path: Path, sample_rate_hz: float = 12_000.0, label: str = "unknown") -> VibrationSample:
    """Lê um arquivo .mat do CWRU Bearing Dataset (canal drive-end).
    TODO: confirmar nome exato da variável contra o arquivo real."""
    from scipy.io import loadmat

    mat = loadmat(str(path))
    de_keys = [k for k in mat.keys() if k.endswith("_DE_time")]
    if not de_keys:
        raise KeyError(f"nenhuma variável '*_DE_time' encontrada em {path}")
    accel = mat[de_keys[0]].flatten()
    return VibrationSample(accel=accel, sample_rate_hz=sample_rate_hz, unit="g", label=label, source="cwru")


def iter_dataset_files(subdir: str, pattern: str) -> Iterator[Path]:
    folder = DATA_DIR / subdir
    if not folder.exists():
        raise FileNotFoundError(
            f"{folder} não existe — anexe os arquivos do dataset em data/{subdir}/ "
            "(ver training/kaelix_ml/dataset.py para o layout esperado)."
        )
    yield from sorted(folder.glob(pattern))


def generate_synthetic_dataset(
    n_normal: int = 200,
    n_anomalous: int = 60,
    n_samples: int = 1024,
    sample_rate_hz: float = 1000.0,
    seed: int = 42,
) -> list:
    """Sinais sintéticos para validar o pipeline (features -> treino ->
    export) ponta-a-ponta enquanto os dados reais não chegam. NÃO
    substitui o treino real com MAFAULDA/CWRU.

    "Normal": senoide de baixa amplitude + ruído gaussiano leve.
    "Anômalo": harmônicos de maior amplitude + impulsos periódicos
    (simula desbalanceamento/defeito de rolamento) — maior amplitude,
    curtose e fator de crista, como um defeito real produziria.
    """
    rng = np.random.default_rng(seed)
    t = np.arange(n_samples) / sample_rate_hz
    samples = []

    for _ in range(n_normal):
        freq = rng.uniform(45, 55)
        amp = rng.uniform(0.5, 1.0)
        noise = rng.normal(0, 0.05, n_samples)
        x = amp * np.sin(2 * np.pi * freq * t) + noise
        samples.append(VibrationSample(accel=x, sample_rate_hz=sample_rate_hz, unit="g", label="normal", source="synthetic"))

    for _ in range(n_anomalous):
        freq = rng.uniform(45, 55)
        amp = rng.uniform(2.0, 4.0)
        harmonics = amp * np.sin(2 * np.pi * freq * t) + 0.5 * amp * np.sin(2 * np.pi * 2 * freq * t)
        impulse_period = max(2, int(sample_rate_hz / rng.uniform(8, 15)))
        impulses = np.zeros(n_samples)
        impulses[::impulse_period] = amp * rng.uniform(1.5, 3.0)
        noise = rng.normal(0, 0.1, n_samples)
        x = harmonics + impulses + noise
        samples.append(VibrationSample(accel=x, sample_rate_hz=sample_rate_hz, unit="g", label="anomalous", source="synthetic"))

    rng.shuffle(samples)
    return samples
