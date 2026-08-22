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


# Banda de análise, em Hz — a mesma da ISO 10816-3. Espelha
# DOMINANT_BAND_LO_HZ / _HI_HZ em lib/signal_processing/signal_processing.h.
DOMINANT_BAND_LO_HZ = 10.0
DOMINANT_BAND_HI_HZ = 1000.0


def dominant_frequency(
    samples: np.ndarray,
    sample_rate_hz: float,
    band_lo_hz: float = DOMINANT_BAND_LO_HZ,
    band_hi_hz: float = DOMINANT_BAND_HI_HZ,
) -> float:
    """Frequência dominante do espectro de VELOCIDADE, band-limitado.

    Aceleração escala com ω², então o espectro de aceleração é dominado
    pelo conteúdo de alta frequência — tipicamente um modo estrutural da
    montagem, idêntico com a máquina sadia ou defeituosa. Medido no
    MAFAULDA: o pico de aceleração fica em 117 Hz independente da rotação
    (correlação com a rotação real: -0,018), enquanto no espectro de
    velocidade o pico cai sobre 1x rotação — a assinatura de
    desbalanceamento e desalinhamento.

    A conversão é feita na magnitude: |V(f)| = |A(f)| / (2*pi*f). A fase
    não importa para escolher o bin de pico. O limite inferior da banda
    não é cosmético: sem ele a ponderação 1/f faria o bin mais baixo
    vencer sempre.
    """
    x = np.asarray(samples, dtype=np.float64)
    n = x.size
    if n < 4:
        return 0.0

    bin_hz = sample_rate_hz / n
    if bin_hz <= 0.0:
        return 0.0

    magnitude = np.abs(np.fft.fft(x))
    half = n // 2
    if half <= 1:
        return 0.0

    k_lo = max(1, int(np.ceil(band_lo_hz / bin_hz)))
    k_hi = min(half - 1, int(np.floor(band_hi_hz / bin_hz)))
    if k_lo > k_hi:
        return 0.0

    k = np.arange(k_lo, k_hi + 1)
    velocity_magnitude = magnitude[k_lo:k_hi + 1] / (2.0 * np.pi * k * bin_hz)
    return float(k[int(np.argmax(velocity_magnitude))] * bin_hz)


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
