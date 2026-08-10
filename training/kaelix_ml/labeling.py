"""Rotulagem normal/anômalo via ISO 10816-3 — usada só para AVALIAR o
modelo e calibrar o limiar de decisão (o Isolation Forest em si é
treinado de forma não supervisionada sobre o subconjunto "normal").

A ISO 10816-3 define zonas de severidade em termos de VELOCIDADE de
vibração RMS (mm/s), não aceleração — por isso a aceleração lida pelo
MPU6050 precisa ser integrada no domínio da frequência antes de aplicar
os limiares.

IMPORTANTE: os valores de fronteira das zonas abaixo são os comumente
citados na literatura de engenharia para a ISO 10816-3:2009. Ainda não
foram conferidos contra o texto oficial da norma nem contra a classe
real do motor de bancada da Skala — fazer isso antes de usar para
calibração final (Fase 3).
"""

import numpy as np

GRAVITY_MS2 = 9.80665

# (limite A/B, limite B/C, limite C/D) em mm/s RMS de velocidade.
# Zonas A e B = normal; zonas C e D = anômalo (corte no limite B/C).
ISO_10816_3_ZONE_BOUNDARIES_MM_S = {
    "I": (0.71, 1.8, 4.5),      # máquinas pequenas (<15kW)
    "II": (1.12, 2.8, 7.1),     # máquinas médias
    "III": (1.8, 4.5, 11.2),    # máquinas grandes, fundação rígida
    "IV": (2.8, 7.1, 18.0),     # máquinas grandes, fundação flexível
}


def g_to_ms2(accel_g: np.ndarray) -> np.ndarray:
    return np.asarray(accel_g, dtype=np.float64) * GRAVITY_MS2


def acceleration_to_velocity_rms_mm_s(accel_ms2: np.ndarray, sample_rate_hz: float) -> float:
    """Integra aceleração (m/s²) para velocidade via domínio da
    frequência: V(f) = A(f) / (j*2*pi*f). O bin DC é zerado (aceleração
    constante não representa oscilação). Retorna o RMS da velocidade
    resultante, em mm/s."""
    x = np.asarray(accel_ms2, dtype=np.float64)
    n = x.size
    if n == 0:
        return 0.0

    freqs = np.fft.fftfreq(n, d=1.0 / sample_rate_hz)
    spectrum = np.fft.fft(x)

    velocity_spectrum = np.zeros_like(spectrum)
    nonzero = freqs != 0.0
    velocity_spectrum[nonzero] = spectrum[nonzero] / (1j * 2.0 * np.pi * freqs[nonzero])

    velocity_time = np.fft.ifft(velocity_spectrum).real
    v_rms_m_s = float(np.sqrt(np.mean(velocity_time ** 2)))
    return v_rms_m_s * 1000.0  # m/s -> mm/s


def label_from_velocity_rms(v_rms_mm_s: float, machine_class: str = "I") -> str:
    _ab, bc, _cd = ISO_10816_3_ZONE_BOUNDARIES_MM_S[machine_class]
    return "anomalous" if v_rms_mm_s >= bc else "normal"


def label_from_acceleration(accel_g: np.ndarray, sample_rate_hz: float, machine_class: str = "I") -> str:
    accel_ms2 = g_to_ms2(accel_g)
    v_rms = acceleration_to_velocity_rms_mm_s(accel_ms2, sample_rate_hz)
    return label_from_velocity_rms(v_rms, machine_class)
