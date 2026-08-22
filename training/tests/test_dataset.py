"""Cobre o alinhamento entre o domínio dos datasets e o do firmware:
recursão da busca, decimação, janelamento, unidade e rótulo por caminho.
Cada teste aqui corresponde a um defeito real encontrado na auditoria de
proveniência (ver CHANGELOG.md)."""

import numpy as np
import pytest

from kaelix_ml import dataset
from kaelix_ml.dataset import (
    DEVICE_SAMPLE_RATE_HZ,
    DEVICE_WINDOW_SAMPLES,
    VibrationSample,
    convert_unit,
    generate_synthetic_dataset,
    iter_dataset_files,
    mafaulda_label_from_path,
    resample_to,
    to_device_windows,
)


def _sample(accel, rate=50_000.0, unit="g", label="normal", group="ensaio-1"):
    return VibrationSample(accel=np.asarray(accel, dtype=np.float64), sample_rate_hz=rate,
                           unit=unit, label=label, source="test", group=group)


# --- busca de arquivos ------------------------------------------------------

def test_iter_dataset_files_desce_em_subdiretorios(tmp_path, monkeypatch):
    """O MAFAULDA é organizado em pastas por tipo e severidade de falha.
    Com o glob não recursivo de antes, a busca devolvia zero arquivos e o
    treino caía no fallback sintético em silêncio."""
    raiz = tmp_path / "mafaulda"
    (raiz / "imbalance" / "6g").mkdir(parents=True)
    (raiz / "normal").mkdir(parents=True)
    (raiz / "imbalance" / "6g" / "12.288.csv").write_text("1,2\n")
    (raiz / "normal" / "12.288.csv").write_text("1,2\n")
    monkeypatch.setattr(dataset, "DATA_DIR", tmp_path)

    encontrados = list(iter_dataset_files("mafaulda", "*.csv"))
    assert len(encontrados) == 2


def test_iter_dataset_files_falha_se_pasta_nao_existe(tmp_path, monkeypatch):
    monkeypatch.setattr(dataset, "DATA_DIR", tmp_path)
    with pytest.raises(FileNotFoundError):
        list(iter_dataset_files("mafaulda", "*.csv"))


# --- reamostragem -----------------------------------------------------------

def test_estagios_de_decimacao_respeitam_o_limite():
    for q in (12, 48, 50, 100):
        estagios = dataset._decimation_stages(q)
        assert int(np.prod(estagios)) == q
        assert all(e <= 13 for e in estagios), f"q={q} produziu estágio > 13: {estagios}"


def test_resample_to_atinge_a_taxa_do_dispositivo():
    x = np.random.default_rng(0).standard_normal(250_000)  # 5s @ 50kHz, como o MAFAULDA
    y = resample_to(x, 50_000.0, DEVICE_SAMPLE_RATE_HZ)
    assert len(y) == pytest.approx(5_000, rel=0.01)


def test_resample_preserva_frequencia_dentro_da_banda():
    """Uma senoide de 120 Hz sobrevive à decimação de 50 kHz para 1 kHz —
    está bem abaixo do novo Nyquist de 500 Hz."""
    fs, f0, dur = 50_000.0, 120.0, 2.0
    t = np.arange(int(fs * dur)) / fs
    x = np.sin(2 * np.pi * f0 * t)

    y = resample_to(x, fs, DEVICE_SAMPLE_RATE_HZ)
    espectro = np.abs(np.fft.rfft(y))
    freqs = np.fft.rfftfreq(len(y), 1.0 / DEVICE_SAMPLE_RATE_HZ)
    assert freqs[np.argmax(espectro)] == pytest.approx(f0, abs=2.0)


def test_resample_rejeita_upsampling():
    with pytest.raises(ValueError, match="upsampling"):
        resample_to(np.zeros(100), 500.0, DEVICE_SAMPLE_RATE_HZ)


# --- janelamento ------------------------------------------------------------

def test_to_device_windows_entrega_o_formato_do_firmware():
    """512 amostras a 1 kHz — VIBRATION_SAMPLES em src/main.cpp e
    SAMPLE_RATE_HZ em src/sensors/vibration.cpp."""
    janelas = to_device_windows(_sample(np.random.default_rng(1).standard_normal(250_000)))
    assert janelas, "nenhuma janela gerada"
    for j in janelas:
        assert j.accel.shape == (DEVICE_WINDOW_SAMPLES,)
        assert j.sample_rate_hz == DEVICE_SAMPLE_RATE_HZ
        assert j.unit == dataset.CANONICAL_UNIT


def test_janelas_preservam_o_grupo_de_origem():
    """Todas as janelas de um arquivo precisam cair do mesmo lado do
    GroupKFold — é essa a defesa contra o vazamento do item 6."""
    janelas = to_device_windows(_sample(np.zeros(250_000), group="ensaio-42"))
    assert {j.group for j in janelas} == {"ensaio-42"}


def test_janelas_nao_se_sobrepoem_por_padrao():
    x = np.arange(5_000, dtype=np.float64)
    janelas = to_device_windows(_sample(x, rate=DEVICE_SAMPLE_RATE_HZ))
    assert len(janelas) == 5_000 // DEVICE_WINDOW_SAMPLES
    assert np.array_equal(janelas[0].accel, x[:DEVICE_WINDOW_SAMPLES])
    assert np.array_equal(janelas[1].accel, x[DEVICE_WINDOW_SAMPLES:2 * DEVICE_WINDOW_SAMPLES])


def test_sinal_curto_demais_nao_gera_janela():
    assert to_device_windows(_sample(np.zeros(100), rate=DEVICE_SAMPLE_RATE_HZ)) == []


# --- unidades ---------------------------------------------------------------

def test_convert_unit_g_para_ms2():
    convertido = convert_unit(_sample([1.0], unit="g"), "m/s2")
    assert convertido.accel[0] == pytest.approx(9.80665)
    assert convertido.unit == "m/s2"


def test_convert_unit_ida_e_volta():
    original = _sample([3.0, -1.5], unit="g")
    volta = convert_unit(convert_unit(original, "m/s2"), "g")
    assert volta.accel == pytest.approx(original.accel)


def test_convert_unit_falha_alto_em_unidade_desconhecida():
    """Antes o campo `unit` era escrito e nunca lido: um dataset em m/s²
    era tratado como g em silêncio, com erro de 9,8×."""
    with pytest.raises(ValueError, match="unidade"):
        convert_unit(_sample([1.0], unit="polegadas/s2"), "g")


def test_to_device_windows_normaliza_a_unidade():
    janelas = to_device_windows(_sample(np.ones(250_000) * 9.80665, unit="m/s2"))
    assert janelas[0].unit == "g"
    assert np.mean(janelas[0].accel) == pytest.approx(1.0, rel=1e-3)


# --- rótulo lido do caminho -------------------------------------------------

def test_rotulo_mafaulda_normal_e_falha():
    from pathlib import Path

    classe, rotulo = mafaulda_label_from_path(Path("data/mafaulda/normal/12.288.csv"))
    assert (classe, rotulo) == ("normal", "normal")

    classe, rotulo = mafaulda_label_from_path(Path("data/mafaulda/imbalance/6g/12.288.csv"))
    assert (classe, rotulo) == ("imbalance", "anomalous")

    classe, rotulo = mafaulda_label_from_path(
        Path("data/mafaulda/underhang/ball_fault/0g/12.288.csv"))
    assert (classe, rotulo) == ("underhang-bearing", "anomalous")


def test_rotulo_falha_alto_em_caminho_desconhecido():
    """Rotular errado em silêncio contamina o treino inteiro sem deixar
    rastro — melhor parar e pedir ajuste do mapa de diretórios."""
    from pathlib import Path

    with pytest.raises(ValueError, match="classe de falha"):
        mafaulda_label_from_path(Path("data/mafaulda/pasta-inesperada/x.csv"))


# --- gerador sintético ------------------------------------------------------

def test_sinteticos_tem_grupos_distintos():
    """Cada amostra sintética é um ensaio independente; sem grupos
    distintos o GroupKFold não teria como dividir."""
    amostras = generate_synthetic_dataset(n_normal=5, n_anomalous=3)
    grupos = [s.group for s in amostras]
    assert len(set(grupos)) == len(grupos) == 8


def test_sinteticos_saem_na_taxa_do_dispositivo():
    amostras = generate_synthetic_dataset(n_normal=2, n_anomalous=1)
    assert all(s.sample_rate_hz == DEVICE_SAMPLE_RATE_HZ for s in amostras)
