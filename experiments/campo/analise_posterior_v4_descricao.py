"""Descrição acrescentada depois do cálculo da AP3, fora do registro v4.

No treino reamostrado da AP3 (analise_posterior_v4.py), o intervalo da fração marcada no nível 4 da base pública foi
de 0 % a 100 %, embora as sementes de 0 a 99 tenham marcado de 95,8 % a 100 % das janelas de 4E. Este script descreve
a causa, sem recalcular a AP3:
  - número de réplicas da AP3b em que nenhuma janela de cada arquivo passou do limiar (lido de ap3_treino.csv);
  - com o modelo registrado de H4 (semente 0), número de descritores fora da faixa do treino por janela e percentis do
    escore das janelas de cada arquivo.

Grava experiments/campo/analise_posterior_v4/descricao_h4.csv e
docs/monografia/latex/values/posterior_v4_descricao_values.tex.

Uso, a partir de kaelix-firmware/:
  taskpolicy -b uv run --no-project --python 3.12 --with numpy==2.5.2 --with scipy==1.18.0 \
      --with scikit-learn==1.9.0 python experiments/campo/analise_posterior_v4_descricao.py
"""
import csv

import numpy as np

import analise_posterior_v4 as v4
import analise_registrada as ar

VALORES = ar.RAIZ / "docs" / "monografia" / "latex" / "values" / "posterior_v4_descricao_values.tex"


def main():
    v4.conferir_registros()
    replicas = {}
    for r in csv.DictReader(open(v4.SAIDA / "ap3_treino.csv", encoding="utf-8")):
        if r["caso"] == "H4":
            replicas.setdefault(r["teste"], []).append(float(r["fracao"]))
    Xtr, testes = v4.dados_h4()
    thr, mod = ar.limiar(lambda: ar.Floresta(0), Xtr)
    mx, mn = Xtr.max(axis=0), Xtr.min(axis=0)
    linhas, v = [], {}
    for L in range(5):
        s = mod.escore(testes[L])
        fora = ((testes[L] > mx) | (testes[L] < mn)).sum(axis=1)
        zero = int(sum(f == 0.0 for f in replicas[f"{L}E"]))
        linhas.append({"arquivo": f"{L}E", "replicas": len(replicas[f"{L}E"]), "replicas_sem_marcacao": zero,
                       "descritores_fora_mediana": float(np.median(fora)), "escore_p5": float(np.percentile(s, 5)),
                       "escore_mediana": float(np.median(s)), "escore_max": float(s.max()), "limiar": thr})
        nome = v4.NIVEIS[L]
        v[f"descReplicasSemMarcacao{nome}"] = str(zero)
        v[f"descForaMediana{nome}"] = ar.br(float(np.median(fora)), 0)
        v[f"descEscoreCincoPct{nome}"] = ar.br(float(np.percentile(s, 5)), 3)
        v[f"descEscoreMax{nome}"] = ar.br(float(s.max()), 3)
    v["descLimiarQuatro"] = ar.br(thr, 3)
    v4.escrever("descricao_h4.csv", linhas)
    VALORES.write_text("% Gerado por experiments/campo/analise_posterior_v4_descricao.py; não editar à mão.\n"
                       + "\n".join(f"\\newcommand{{\\{k}}}{{{v[k]}}}" for k in sorted(v)) + "\n", encoding="utf-8")
    print(linhas)


if __name__ == "__main__":
    main()
