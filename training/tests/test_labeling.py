import numpy as np
import pytest

from kaelix_ml.labeling import (
    ISO_10816_3_ZONE_BOUNDARIES_MM_S,
    ISO_BAND_HZ,
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


def test_integracao_bate_com_o_valor_de_referencia_do_item_2():
    """Caso de referência do item 2 dos questionamentos técnicos, o mesmo
    de figures/data/fig2_referencia.csv: 3,0 m/s² @ 50 Hz -> 6,7524 mm/s
    RMS exatos. O notebook mede 0,0% de erro por este método; integração
    no tempo erra +73% (sem passa-alta) ou +156% (com)."""
    fs, dur, amplitude, freq = 5000.0, 4.0, 3.0, 50.0
    t = np.arange(int(fs * dur)) / fs
    accel = amplitude * np.sin(2 * np.pi * freq * t)

    exato = (amplitude / np.sqrt(2)) / (2 * np.pi * freq) * 1000.0
    obtido = acceleration_to_velocity_rms_mm_s(accel, fs)

    assert obtido == pytest.approx(exato, rel=1e-4)


def test_integracao_e_imune_a_bias_do_acelerometro():
    """Um bias de 0,02 m/s², dentro da especificação de qualquer MPU6050,
    leva a integração no tempo a +716%. Na frequência com recorte de
    banda o DC cai fora da máscara e não tem efeito."""
    fs, dur, amplitude, freq = 5000.0, 4.0, 3.0, 50.0
    t = np.arange(int(fs * dur)) / fs
    accel = amplitude * np.sin(2 * np.pi * freq * t)

    sem_bias = acceleration_to_velocity_rms_mm_s(accel, fs)
    com_bias = acceleration_to_velocity_rms_mm_s(accel + 0.02, fs)

    assert com_bias == pytest.approx(sem_bias, rel=1e-6)


def test_mascara_de_banda_rejeita_energia_fora_de_10_1000_hz():
    """A ISO 10816-3 mede entre 10 Hz e 1000 Hz. Antes só o bin DC era
    zerado, então energia fora da banda normativa entrava na conta."""
    fs, dur, amplitude = 8000.0, 4.0, 3.0
    t = np.arange(int(fs * dur)) / fs

    na_banda = acceleration_to_velocity_rms_mm_s(amplitude * np.sin(2 * np.pi * 50.0 * t), fs)
    fora_acima = acceleration_to_velocity_rms_mm_s(amplitude * np.sin(2 * np.pi * 2000.0 * t), fs)
    fora_abaixo = acceleration_to_velocity_rms_mm_s(amplitude * np.sin(2 * np.pi * 3.0 * t), fs)

    # O resíduo não é exatamente zero: a janela de Hann espalha um pouco
    # de energia para os bins vizinhos. Mas fica ordens de grandeza abaixo
    # do menor limiar de zona da norma (0,71 mm/s), então não muda rótulo.
    menor_limiar_iso = min(min(v) for v in ISO_10816_3_ZONE_BOUNDARIES_MM_S.values())
    assert na_banda > 1.0
    assert fora_acima < menor_limiar_iso / 1000
    assert fora_abaixo < menor_limiar_iso / 1000


def test_banda_efetiva_do_dispositivo_e_metade_da_norma():
    """Consequência registrada no item 2: com Nyquist em 500 Hz, o Kaelix
    cobre metade da banda de 10-1000 Hz que a norma exige. Este teste
    existe para que a limitação fique explícita no código, não só na
    documentacao."""
    assert ISO_BAND_HZ == (10.0, 1000.0)

    from kaelix_ml.dataset import DEVICE_SAMPLE_RATE_HZ

    nyquist_dispositivo = DEVICE_SAMPLE_RATE_HZ / 2
    assert nyquist_dispositivo < ISO_BAND_HZ[1]
