"""Rotulagem normal/anômalo via ISO 10816-3.

Papel no pipeline: quando o dataset traz a verdade de referência (o
MAFAULDA codifica a classe de falha na estrutura de diretórios — ver
`dataset.mafaulda_label_from_path`), o rótulo ISO serve como
**diagnóstico comparativo**, não como verdade. `train.py` imprime a
matriz de concordância entre os dois. O Isolation Forest em si é
treinado de forma não supervisionada sobre o subconjunto "normal".

A ISO 10816-3 define zonas de severidade em termos de VELOCIDADE de
vibração RMS (mm/s) medida na banda de 10 Hz a 1000 Hz — não
aceleração, que é o que o MPU6050 entrega. A conversão precisa então de
dois passos, e o segundo estava faltando:

1. Integrar aceleração -> velocidade **no domínio da frequência**
   (V(f) = A(f)/(j·2πf)). Integrar no tempo acumula deriva de offset: o
   item 2 mediu +716% de erro com um bias de 0,02 m/s², dentro da
   especificação de qualquer MPU6050.
2. **Recortar a banda de 10–1000 Hz**, como a norma exige. Antes só o
   bin DC era zerado, o que deixava passar energia fora da banda
   normativa e divergia do método validado no notebook.

A implementação abaixo é a mesma de `figures/scripts/export_source_data.py`
(`vel_freq`), que o item 2 verificou contra valor analítico com erro de
0,0% — janela de Hann, recorte de banda, compensação da perda de
potência da janela.

IMPORTANTE: os valores de fronteira das zonas continuam sendo os
comumente citados na literatura de engenharia para a ISO 10816-3:2009.
Ainda não foram conferidos contra o texto oficial da norma nem contra a
classe real do motor de bancada da Skala — fazer isso antes de usar
para calibração final (Fase 3).
"""

import numpy as np

GRAVITY_MS2 = 9.80665

# Banda de medição da ISO 10816-3, em Hz.
ISO_BAND_HZ = (10.0, 1000.0)

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


def acceleration_to_velocity_rms_mm_s(
    accel_ms2: np.ndarray,
    sample_rate_hz: float,
    band_hz: tuple = ISO_BAND_HZ,
) -> float:
    """Velocidade RMS (mm/s) na banda da ISO 10816-3, por integração no
    domínio da frequência.

    Só os bins dentro de `band_hz` sobrevivem — o que zera o DC de
    quebra (0 Hz está fora da banda) e é o que torna o método imune ao
    bias do acelerômetro. A janela de Hann reduz o vazamento espectral;
    a divisão por sqrt(mean(w²)) devolve a potência que a janela tirou,
    para que o RMS continue comparável ao do sinal original.
    """
    x = np.asarray(accel_ms2, dtype=np.float64)
    n = x.size
    if n == 0:
        return 0.0

    f_lo, f_hi = band_hz
    w = np.hanning(n)
    spectrum = np.fft.rfft(x * w)
    freqs = np.fft.rfftfreq(n, d=1.0 / sample_rate_hz)

    velocity_spectrum = np.zeros_like(spectrum)
    in_band = (freqs >= f_lo) & (freqs <= f_hi)
    velocity_spectrum[in_band] = spectrum[in_band] / (2j * np.pi * freqs[in_band])

    velocity_time = np.fft.irfft(velocity_spectrum, n) / np.sqrt(np.mean(w ** 2))
    return float(np.sqrt(np.mean(velocity_time ** 2)) * 1000.0)  # m/s -> mm/s


def label_from_velocity_rms(v_rms_mm_s: float, machine_class: str = "I") -> str:
    _ab, bc, _cd = ISO_10816_3_ZONE_BOUNDARIES_MM_S[machine_class]
    return "anomalous" if v_rms_mm_s >= bc else "normal"


def label_from_acceleration(accel_g: np.ndarray, sample_rate_hz: float, machine_class: str = "I") -> str:
    """Rótulo ISO a partir de aceleração em **g** (unidade canônica do
    pipeline — ver `dataset.CANONICAL_UNIT`). Passar m/s² aqui produz um
    resultado 9,8× errado; use `dataset.convert_unit` antes."""
    accel_ms2 = g_to_ms2(accel_g)
    v_rms = acceleration_to_velocity_rms_mm_s(accel_ms2, sample_rate_hz)
    return label_from_velocity_rms(v_rms, machine_class)
