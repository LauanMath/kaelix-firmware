"""Gravidade média por eixo em cada ensaio da coleta em campo de 2 de novembro de 2026.

Lê experiments/campo/dados/ (gerado por exportar_campo.py) e grava
experiments/campo/dados/gravidade_por_ensaio.csv. A média de cada eixo do
acelerômetro, sem remover a componente contínua, dá a direção da gravidade no
referencial do sensor e indica a face da carcaça em que ele foi colado.

Conversão: valor bruto dividido por 16384 / 2**a, em que a é o código da faixa
configurada (accel_range em janelas.csv), como no texto da seção 3.

Uso: uv run python experiments/campo/gravidade_por_ensaio.py
"""
import csv
import pathlib

import numpy as np

DADOS = pathlib.Path(__file__).resolve().parent / "dados"


def main() -> None:
    amostras = np.load(DADOS / "janelas.npz")["amostras"]
    janelas = list(csv.DictReader(open(DADOS / "janelas.csv", newline="")))
    ensaios = list(csv.DictReader(open(DADOS / "ensaios.csv", newline="")))
    linhas = []
    for e in ensaios:
        idx = [i for i, j in enumerate(janelas) if j["ensaio"] == e["ensaio"]]
        faixas = {int(janelas[i]["accel_range"]) for i in idx}
        if len(faixas) != 1:
            raise SystemExit(f"ensaio {e['ensaio']}: mais de uma faixa do acelerômetro ({faixas})")
        lsb_por_g = 16384 / 2 ** faixas.pop()
        media = amostras[idx, :, :3].astype(float).mean(axis=(0, 1)) / lsb_por_g
        linhas.append({
            "ensaio": e["ensaio"], "maquina": e["maquina"], "rodada": e["rodada"], "janelas": len(idx),
            "gx_g": f"{media[0]:.3f}", "gy_g": f"{media[1]:.3f}", "gz_g": f"{media[2]:.3f}",
            "modulo_g": f"{np.linalg.norm(media):.3f}",
        })
    with open(DADOS / "gravidade_por_ensaio.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0]))
        w.writeheader()
        w.writerows(linhas)
    for l in linhas:
        print(f"{l['maquina']:<13} {l['rodada']}  n={l['janelas']:>3}  X {l['gx_g']:>7}  Y {l['gy_g']:>7}  "
              f"Z {l['gz_g']:>7}  |g| {l['modulo_g']}")


if __name__ == "__main__":
    main()
