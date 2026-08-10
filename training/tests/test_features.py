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
