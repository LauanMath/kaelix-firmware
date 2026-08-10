"""Extração de features — replica EXATAMENTE a lógica de
lib/signal_processing/signal_processing.cpp (RMS, curtose, fator de
crista, frequência dominante). Qualquer mudança de fórmula precisa ser
espelhada dos dois lados, senão o modelo treinado diverge da inferência
embarcada. Os testes em training/tests/test_features.py replicam os
mesmos casos de test/test_signal_processing/test_signal_processing.cpp
para garantir a paridade.
"""

import numpy as np


def compute_rms(samples: np.ndarray) -> float:
    x = np.asarray(samples, dtype=np.float64)
    if x.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(x ** 2)))


def compute_kurtosis(samples: np.ndarray) -> float:
    """Curtose de excesso (Fisher: normal = 0), com momentos populacionais
    (divide por n, não n-1) — mesma convenção do C++."""
    x = np.asarray(samples, dtype=np.float64)
    if x.size == 0:
        return 0.0
    mean = x.mean()
    d = x - mean
    m2 = np.mean(d ** 2)
    m4 = np.mean(d ** 4)
    if m2 == 0.0:
        return 0.0
    return float(m4 / (m2 ** 2) - 3.0)


def compute_crest_factor(samples: np.ndarray) -> float:
    x = np.asarray(samples, dtype=np.float64)
    rms = compute_rms(x)
    if rms == 0.0:
        return 0.0
    return float(np.max(np.abs(x)) / rms)


def dominant_frequency(samples: np.ndarray, sample_rate_hz: float) -> float:
    """FFT (equivalente à fft_radix2 do C++ para n potência de 2) — ignora
    o bin DC (k=0) e retorna a frequência do bin de maior magnitude na
    primeira metade do espectro."""
    x = np.asarray(samples, dtype=np.float64)
    n = x.size
    if n < 4:
        return 0.0
    spectrum = np.fft.fft(x)
    magnitude = np.abs(spectrum)
    half = n // 2
    if half <= 1:
        return 0.0
    best_bin = 1 + int(np.argmax(magnitude[1:half]))
    return float(best_bin * sample_rate_hz / n)


def extract_features(samples: np.ndarray, sample_rate_hz: float) -> dict:
    """Vetor de features na mesma ordem usada por src/ml/model.cpp:
    [rms, kurtosis, crest_factor, dominant_freq_hz]."""
    return {
        "rms": compute_rms(samples),
        "kurtosis": compute_kurtosis(samples),
        "crest_factor": compute_crest_factor(samples),
        "dominant_freq_hz": dominant_frequency(samples, sample_rate_hz),
    }


FEATURE_ORDER = ["rms", "kurtosis", "crest_factor", "dominant_freq_hz"]


def features_to_vector(features: dict) -> np.ndarray:
    return np.array([features[k] for k in FEATURE_ORDER], dtype=np.float64)
