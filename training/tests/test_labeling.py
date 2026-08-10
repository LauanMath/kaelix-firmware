import numpy as np
import pytest

from kaelix_ml.labeling import (
    ISO_10816_3_ZONE_BOUNDARIES_MM_S,
    acceleration_to_velocity_rms_mm_s,
    g_to_ms2,
    label_from_velocity_rms,
)


def test_g_to_ms2():
    assert g_to_ms2(np.array([1.0])) == pytest.approx([9.80665])


def test_velocity_rms_of_pure_sine_acceleration():
    # a(t) = A*sin(wt) -> v(t) = -(A/w)*cos(wt) -> v_rms = (A/w)/sqrt(2)
    freq_hz = 50.0
    amplitude_ms2 = 10.0
    sample_rate_hz = 5000.0
    n = 8192
    t = np.arange(n) / sample_rate_hz
    accel = amplitude_ms2 * np.sin(2 * np.pi * freq_hz * t)

    w = 2 * np.pi * freq_hz
    expected_v_rms_mm_s = (amplitude_ms2 / w) / np.sqrt(2.0) * 1000.0

    v_rms = acceleration_to_velocity_rms_mm_s(accel, sample_rate_hz)
    assert v_rms == pytest.approx(expected_v_rms_mm_s, rel=0.02)


def test_label_boundaries_class_I():
    ab, bc, cd = ISO_10816_3_ZONE_BOUNDARIES_MM_S["I"]
    assert label_from_velocity_rms(0.0, "I") == "normal"
    assert label_from_velocity_rms(ab, "I") == "normal"
    assert label_from_velocity_rms(bc - 0.01, "I") == "normal"
    assert label_from_velocity_rms(bc, "I") == "anomalous"
    assert label_from_velocity_rms(cd, "I") == "anomalous"
    assert label_from_velocity_rms(cd + 10.0, "I") == "anomalous"
