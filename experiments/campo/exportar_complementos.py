"""Exporta do banco da API, em modo de leitura, os dados de 2 de novembro de 2026 que exportar_campo.py não cobre.

Grava em experiments/campo/dados/, sem tocar nos arquivos já registrados:
  repouso.csv    metadados das janelas com o transmissor sobre a mesa, das 14h00 às 14h59 (hora local, UTC-3),
                 durante o almoço entre as duas rodadas
  repouso.npz    amostras brutas (int16) dessas janelas, na ordem de repouso.csv, forma (n, 512, 6)
  rajadas.csv    uma linha por rajada registrada pelo gateway (13h14 às 16h07): hora, sequência, sinal recebido
                 da telemetria, fragmentos recebidos e duração

Uso: uv run --no-project --with numpy python experiments/campo/exportar_complementos.py [nome_do_banco]
"""
import csv
import hashlib
import json
import pathlib
import re
import subprocess
import sys

import numpy as np

BANCO = sys.argv[1] if len(sys.argv) > 1 else "kaelix_lan"
DISPOSITIVO = "311D0470"
SAIDA = pathlib.Path(__file__).resolve().parent / "dados"
REPOUSO = ("2026-11-02 14:00:00-03", "2026-11-02 14:59:59-03")
CAMPOS_JANELA = ["device_sequence", "boot_count", "sample_rate_hz", "window_samples", "channels", "accel_range",
                 "gyro_range", "dlpf", "burst_profile", "fragment_total", "samples_sha256"]


def consulta(sql):
    saida = subprocess.run(["psql", "-d", BANCO, "-X", "-A", "-t", "-F", "\t", "-c", sql],
                           capture_output=True, text=True, check=True).stdout
    return [linha.split("\t") for linha in saida.splitlines() if linha]


def repouso():
    meta, amostras = [], []
    for t, m, h in consulta(f"select estimated_received_at at time zone 'UTC', metadata::text, encode(samples,'hex') "
                            f"from waveforms where device_id='{DISPOSITIVO}' and estimated_received_at between "
                            f"'{REPOUSO[0]}' and '{REPOUSO[1]}' order by id"):
        m = json.loads(m)
        bruto = bytes.fromhex(h)
        if hashlib.sha256(bruto).hexdigest() != m["samples_sha256"]:
            raise SystemExit(f"SHA-256 diferente na janela {m['device_sequence']}")
        if m.get("fragments_missing"):
            continue
        amostras.append(np.frombuffer(bruto, dtype="<i2").reshape(m["window_samples"], 6))
        meta.append([t] + [m[c] for c in CAMPOS_JANELA])
    with open(SAIDA / "repouso.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["recebida_utc"] + CAMPOS_JANELA)
        w.writerows(meta)
    np.savez_compressed(SAIDA / "repouso.npz", amostras=np.stack(amostras))
    return len(meta)


def rajadas():
    linhas = consulta("select to_char(received_at at time zone 'America/Fortaleza','HH24:MI:SS'), gateway_session_id, "
                      "payload->>'event', payload->>'level', payload->>'message' from gateway_logs "
                      "where received_at::date = '2026-11-02' and payload->>'event' in ('RX','WAVE') "
                      "order by gateway_session_id, (payload->>'log_seq')::int")
    saida, ultima = [], None
    for hora, sessao, evento, nivel, msg in linhas:
        if evento == "RX":
            m = re.search(r"seq=(\d+).*rssi=(-?[\d.]+) snr=(-?[\d.]+)", msg)
            ultima = (sessao, int(m.group(1)), float(m.group(2)), float(m.group(3))) if m else None
            continue
        m = re.search(r"seq=(\d+) fragments=(\d+)/(\d+) took=(\d+)ms", msg)
        if m and ultima and ultima[0] == sessao and ultima[1] == int(m.group(1)):
            saida.append([hora, sessao, ultima[1], ultima[2], ultima[3], int(m.group(2)), int(m.group(3)),
                          int(m.group(4)), nivel])
    with open(SAIDA / "rajadas.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["hora_local", "sessao_gateway", "device_sequence", "rssi_dbm", "snr_db", "fragmentos_recebidos",
                    "fragmentos_total", "duracao_ms", "nivel"])
        w.writerows(saida)
    return len(saida)


def main():
    SAIDA.mkdir(parents=True, exist_ok=True)
    print(f"{repouso()} janelas em repouso, {rajadas()} rajadas")


if __name__ == "__main__":
    main()
