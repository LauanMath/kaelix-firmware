"""Exporta do banco da API as leituras e as janelas da coleta em campo de 2 de novembro de 2026.

Lê o banco PostgreSQL da API (só leitura) e grava em experiments/campo/dados/:
  ensaios.csv   um ensaio por linha: máquina, rodada, trecho analisado (hora local, UTC-3)
  leituras.csv  telemetria de cada ciclo dentro dos trechos
  janelas.csv   metadados de cada janela de sinal bruto
  janelas.npz   amostras brutas (int16) de cada janela, na ordem de janelas.csv, forma (n, 512, 6)

Os trechos são os usados na análise: o intervalo de operação estável de cada coleta, sem a
partida do motor e sem o tempo em que os dados continuaram sendo gravados por esquecimento.

Uso: uv run python experiments/campo/exportar_campo.py [nome_do_banco]
"""
import csv
import hashlib
import json
import pathlib
import subprocess
import sys

import numpy as np

BANCO = sys.argv[1] if len(sys.argv) > 1 else "kaelix_lan"
DISPOSITIVO = "311D0470"
DIA = "2026-11-02"
SAIDA = pathlib.Path(__file__).resolve().parent / "dados"

# máquina, rodada, início, fim (hora local, UTC-3), rotação nominal de busca (Hz)
ENSAIOS = [
    ("Dobradeira", 1, "12:48:00", "13:00:26", 29.8),
    ("Guilhotina", 1, "13:05:55", "13:08:56", 30.0),
    ("Motor parado", 1, "13:11:00", "13:14:50", None),
    ("Calandra", 1, "13:18:45", "13:25:00", 29.8),
    ("Compressor", 1, "13:40:11", "13:48:15", 59.8),
    ("Calandra", 2, "15:47:15", "15:55:50", 29.8),
    ("Guilhotina", 2, "16:00:05", "16:06:27", 30.0),
]

CAMPOS_LEITURA = [
    "device_sequence", "boot_count", "device_time", "rssi_dbm", "snr_db", "tx_power_dbm", "config_version",
    "diag_code", "flags", "rms_g", "rms_x_g", "rms_y_g", "kurtosis", "crest_factor", "dominant_freq_hz",
    "sample_rate_hz", "temperature_c", "wave_fragments",
]
CAMPOS_JANELA = [
    "device_sequence", "boot_count", "sample_rate_hz", "window_samples", "channels", "accel_range",
    "gyro_range", "dlpf", "burst_profile", "fragment_total", "samples_sha256",
]


def consulta(sql):
    saida = subprocess.run(["psql", "-d", BANCO, "-X", "-A", "-t", "-F", "\t", "-c", sql],
                           capture_output=True, text=True, check=True).stdout
    return [linha.split("\t") for linha in saida.splitlines() if linha]


def intervalo(inicio, fim):
    return f"estimated_received_at between '{DIA} {inicio}-03' and '{DIA} {fim}-03'"


def main():
    SAIDA.mkdir(parents=True, exist_ok=True)
    with open(SAIDA / "ensaios.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["ensaio", "maquina", "rodada", "inicio_local", "fim_local", "rotacao_busca_hz"])
        for i, (maq, rod, a, b, f0) in enumerate(ENSAIOS):
            w.writerow([i, maq, rod, a, b, "" if f0 is None else f0])

    with open(SAIDA / "leituras.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["ensaio", "recebida_utc"] + CAMPOS_LEITURA)
        for i, (_, _, a, b, _) in enumerate(ENSAIOS):
            for t, payload in consulta(f"select estimated_received_at at time zone 'UTC', payload::text from readings "
                                       f"where device_id='{DISPOSITIVO}' and {intervalo(a, b)} order by id"):
                p = json.loads(payload)
                w.writerow([i, t] + [p.get(c, "") for c in CAMPOS_LEITURA])

    meta, amostras = [], []
    for i, (_, _, a, b, _) in enumerate(ENSAIOS):
        for t, m, h in consulta(f"select estimated_received_at at time zone 'UTC', metadata::text, encode(samples,'hex') "
                                f"from waveforms where device_id='{DISPOSITIVO}' and {intervalo(a, b)} order by id"):
            m = json.loads(m)
            bruto = bytes.fromhex(h)
            if hashlib.sha256(bruto).hexdigest() != m["samples_sha256"]:
                raise SystemExit(f"SHA-256 diferente na janela {m['device_sequence']}")
            if m.get("fragments_missing"):
                raise SystemExit(f"janela incompleta: {m['device_sequence']}")
            amostras.append(np.frombuffer(bruto, dtype="<i2").reshape(m["window_samples"], 6))
            meta.append([i, t] + [m[c] for c in CAMPOS_JANELA])
    with open(SAIDA / "janelas.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["ensaio", "recebida_utc"] + CAMPOS_JANELA)
        w.writerows(meta)
    np.savez_compressed(SAIDA / "janelas.npz", amostras=np.stack(amostras))
    print(f"{len(meta)} janelas, todas completas e com SHA-256 conferido")


if __name__ == "__main__":
    main()
