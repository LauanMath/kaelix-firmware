"""Espelha os testes de test/test_signal_processing/test_signal_processing.cpp
— mesmos casos, para garantir que a matemática em Python bate com a do
firmware (evita divergência entre treino e inferência)."""

import numpy as np
import pytest

from kaelix_ml.features import (
    compute_crest_factor,
    compute_kurtosis,
    compute_rms,
    dominant_frequency,
)


def make_sine(n, amplitude, freq_hz, sample_rate_hz):
    t = np.arange(n) / sample_rate_hz
    return amplitude * np.sin(2 * np.pi * freq_hz * t)


def test_rms_of_sine_wave():
    x = make_sine(1024, 2.0, 50.0, 1000.0)
    assert compute_rms(x) == pytest.approx(2.0 / np.sqrt(2.0), abs=0.01)


def test_rms_of_constant_signal():
    x = np.full(100, 3.0)
    assert compute_rms(x) == pytest.approx(3.0, abs=1e-5)


def test_crest_factor_of_sine_wave():
    x = make_sine(1024, 5.0, 60.0, 2000.0)
    assert compute_crest_factor(x) == pytest.approx(np.sqrt(2.0), abs=0.02)


def test_kurtosis_of_two_point_distribution():
    x = np.array([1.0, -1.0] * 500)
    assert compute_kurtosis(x) == pytest.approx(-2.0, abs=1e-4)


def test_kurtosis_of_uniform_like_signal():
    x = np.array([(i % 100) / 100.0 - 0.5 for i in range(1000)])
    assert compute_kurtosis(x) < 0.0


def test_dominant_frequency_of_sine_wave():
    n = 1024
    sample_rate_hz = 1024.0
    freq_hz = 50.0
    x = make_sine(n, 1.0, freq_hz, sample_rate_hz)
    detected = dominant_frequency(x, sample_rate_hz)
    assert detected == pytest.approx(freq_hz, abs=0.5)


def test_dominant_frequency_uses_velocity_not_acceleration():
    """Espelha test_dominant_frequency_uses_velocity_not_acceleration do C++.

    Regressão do achado no MAFAULDA: o pico de aceleração fica na
    componente de alta frequência (modo estrutural da montagem, igual com
    máquina sadia ou defeituosa); o de velocidade cai sobre 1x rotação.
    Amplitudes escolhidas para que as duas leituras discordem:
      aceleração: 5,0 (200 Hz) > 1,0 (20 Hz)       -> pico em 200 Hz
      velocidade: 1,0/20 = 0,050 > 5,0/200 = 0,025 -> pico em 20 Hz
    """
    n, fs = 1024, 1024.0
    x = make_sine(n, 1.0, 20.0, fs) + make_sine(n, 5.0, 200.0, fs)

    # O pico bruto de aceleração é mesmo o de 200 Hz — é disso que a
    # reponderação nos protege.
    bruto = np.abs(np.fft.fft(x))[1:n // 2]
    assert (1 + int(np.argmax(bruto))) * fs / n == pytest.approx(200.0, abs=1.0)

    assert dominant_frequency(x, fs) == pytest.approx(20.0, abs=1.0)


def test_dominant_frequency_ignores_below_band():
    """Sem o corte inferior, a ponderação 1/f faria qualquer componente de
    baixíssima frequência vencer."""
    n, fs = 1024, 1024.0
    x = make_sine(n, 3.0, 3.0, fs) + make_sine(n, 1.0, 50.0, fs)
    assert dominant_frequency(x, fs) == pytest.approx(50.0, abs=1.0)


def test_dominant_frequency_ignores_above_band():
    n, fs = 4096, 8192.0
    x = make_sine(n, 50.0, 2000.0, fs) + make_sine(n, 1.0, 60.0, fs)
    assert dominant_frequency(x, fs) == pytest.approx(60.0, abs=2.0)
