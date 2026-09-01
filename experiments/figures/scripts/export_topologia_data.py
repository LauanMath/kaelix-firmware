"""Dados da Figura 5 — comparação de arquiteturas topológicas de rede.

Segue o pipeline do projeto: a computação numérica fica aqui, em Python,
e o R cuida só da camada gráfica. Grava CSVs em experiments/figures/data/.

Nenhum número desta figura é estimativa de catálogo: tempo no ar sai da
fórmula de LoRa, autonomia sai do mesmo orçamento de energia documentado
no README, e probabilidade de colisão sai do modelo ALOHA puro.
"""

import math
from pathlib import Path

import pandas as pd

OUT = Path(__file__).resolve().parents[1] / "data"
OUT.mkdir(parents=True, exist_ok=True)

# --- parâmetros do dispositivo (espelham src/ e o README) -------------------
PAYLOAD_BYTES = 20        # LoraPacket
PREAMBLE_SYM = 8
BW_KHZ = 125
CR = 1                    # 4/5
CICLO_S = 600.0           # deep sleep de 10 min
FASE_ATIVA_S = 3.0

I_ESP32_ATIVO = 40.0      # mA
I_MPU6050 = 3.9
I_LORA_TX = 90.0
I_LORA_STANDBY = 1.5
I_HT7333 = 0.008
I_DEEPSLEEP = 0.010
I_LORA_SLEEP = 0.0002
BATERIA_MAH = 2000.0
AUTODESCARGA_MA = 0.0685  # LiPo ~2,5%/mes


def airtime_s(sf, bw_khz=BW_KHZ, cr=CR, pl=PAYLOAD_BYTES, pre=PREAMBLE_SYM, crc=1):
    """Tempo no ar LoRa, formula do datasheet Semtech SX127x."""
    tsym = (2 ** sf) / (bw_khz * 1000.0)
    de = 1 if (sf >= 11 and bw_khz == 125) else 0
    n = 8 + max(math.ceil((8 * pl - 4 * sf + 28 + 16 * crc) / (4 * (sf - 2 * de))) * (cr + 4), 0)
    return ((pre + 4.25) * tsym + n * tsym)


def autonomia_dias(t_tx_s, i_tx=I_LORA_TX, i_idle_ativo=I_LORA_STANDBY, i_idle_sleep=I_LORA_SLEEP):
    """Autonomia pelo mesmo orcamento do README: carga por ciclo / periodo."""
    q_ativo = (I_ESP32_ATIVO + I_MPU6050 + i_idle_ativo + I_HT7333) * FASE_ATIVA_S
    q_tx = (I_ESP32_ATIVO + I_MPU6050 + i_tx + I_HT7333) * t_tx_s
    q_sleep = (i_idle_sleep + I_DEEPSLEEP + I_HT7333) * CICLO_S
    periodo = FASE_ATIVA_S + t_tx_s + CICLO_S
    media_ma = (q_ativo + q_tx + q_sleep) / periodo
    return BATERIA_MAH / (media_ma + AUTODESCARGA_MA) / 24.0, media_ma


# --- 5b: tempo no ar, autonomia e ganho de enlace por SF ---------------------
linhas = []
for sf in range(7, 13):
    t = airtime_s(sf)
    dias, media = autonomia_dias(t)
    linhas.append({
        "sf": sf,
        "airtime_ms": t * 1000.0,
        "autonomia_dias": dias,
        "corrente_media_ua": media * 1000.0,
        "ganho_db": (sf - 7) * 2.5,   # ~2,5 dB de sensibilidade por passo de SF
        "atual": sf == 9,
    })
pd.DataFrame(linhas).to_csv(OUT / "fig5b_sf_tradeoff.csv", index=False)

# --- 5c: colisao em ALOHA puro, por SF -------------------------------------
# Janela vulneravel = 2x o tempo no ar. Pressupoe fases aleatorias; uma
# instalacao simultanea NAO tem fase aleatoria, e e isso que o jitter resolve.
linhas = []
for sf in (7, 9, 12):
    t = airtime_s(sf)
    for n in range(1, 101):
        linhas.append({
            "sf": sf,
            "n_nos": n,
            "p_colisao": 1 - math.exp(-2 * n * t / CICLO_S),
        })
pd.DataFrame(linhas).to_csv(OUT / "fig5c_colisao.csv", index=False)

# --- 5d: autonomia do no por tecnologia de enlace ---------------------------
# WiFi: associacao + DHCP + TCP + TX medidos tipicamente em 3-6 s a ~120-200 mA
# no ESP32. Usa-se 5 s a 150 mA, valor conservador para o cenario favoravel.
t_lora = airtime_s(9)
dias_lora, ma_lora = autonomia_dias(t_lora)
dias_lora_sf12, ma_lora_sf12 = autonomia_dias(airtime_s(12))
dias_wifi, ma_wifi = autonomia_dias(5.0, i_tx=150.0, i_idle_ativo=0.0, i_idle_sleep=0.0)
# Rádio nunca posto em sleep: o defeito que este projeto corrigiu.
dias_semsleep, ma_semsleep = autonomia_dias(t_lora, i_idle_sleep=I_LORA_STANDBY)

pd.DataFrame([
    {"enlace": "LoRa SF9",            "dias": dias_lora,      "corrente_ua": ma_lora * 1000},
    {"enlace": "LoRa SF12",           "dias": dias_lora_sf12, "corrente_ua": ma_lora_sf12 * 1000},
    {"enlace": "LoRa sem sleep\\ndo rádio", "dias": dias_semsleep,  "corrente_ua": ma_semsleep * 1000},
    {"enlace": "Wi-Fi",               "dias": dias_wifi,      "corrente_ua": ma_wifi * 1000},
]).to_csv(OUT / "fig5d_enlace.csv", index=False)

print(f"SF9: {t_lora*1000:.0f} ms, {dias_lora:.0f} dias, {ma_lora*1000:.0f} uA")
print(f"SF12: {airtime_s(12)*1000:.0f} ms, {dias_lora_sf12:.0f} dias")
print(f"WiFi: {dias_wifi:.0f} dias, {ma_wifi*1000:.0f} uA")
print(f"LoRa sem sleep do radio: {dias_semsleep:.0f} dias")
print(f"CSVs em {OUT}")
