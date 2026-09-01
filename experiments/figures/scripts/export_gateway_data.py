"""Dados da Figura 7 — cadeia de comunicação exercitada por simulação.

Diferente das figuras 1 a 4, a computação NÃO é reimplementada aqui: este
script importa `gateway/kaelix_gateway` e roda o mesmo código que os 19
testes exercitam. É de propósito. O `simulate()` das figuras 1 e 2 existe
duplicado entre notebook e exportador, e se as cópias divergirem a figura
deixa de corresponder ao notebook em silêncio. Aqui a fonte da verdade é
o módulo, e o exportador é só o adaptador para CSV.
"""

import sys
from pathlib import Path

import pandas as pd

# figures/ e gateway/ são irmãos sob experiments/
RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ / "experiments" / "gateway"))

from kaelix_gateway.receptor import Receptor  # noqa: E402
from kaelix_gateway.simulador import Dispositivo, simular  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "data"
OUT.mkdir(parents=True, exist_ok=True)

CICLOS = 100

# --- 7a: colisão contra número de dispositivos, com e sem deslocamento ------
# Sem jitter a colisão não é probabilística: dispositivos energizados juntos
# transmitem no mesmo instante SEMPRE.
linhas = []
for n in (2, 5, 10, 20, 35, 50):
    devs = [Dispositivo(device_id=0xA000 + i) for i in range(n)]
    for rot, jit in (("sem deslocamento", False), ("com deslocamento", True)):
        _, m = simular(devs, ciclos=CICLOS, com_jitter=jit)
        total = m["colisao"] + m["entregues"]
        linhas.append({"n_dispositivos": n, "modo": rot,
                       "p_colisao": m["colisao"] / total if total else 0.0,
                       "entregues": m["entregues"]})
pd.DataFrame(linhas).to_csv(OUT / "fig7a_jitter.csv", index=False)

# --- 7b: funil de ponta a ponta, 24 h ---------------------------------------
N_DEV, CICLOS_DIA = 20, 144
ANOMALOS = {4, 11}
devs = [Dispositivo(device_id=0xA000 + i, p_anomalia=0.7 if i in ANOMALOS else 0.02)
        for i in range(N_DEV)]
quadros, meio = simular(devs, ciclos=CICLOS_DIA, p_perda=0.02, p_corrupcao=0.01)
r = Receptor()
for t, q in quadros:
    r.receber(q, t=t)
s = r.resumo()

transmitidos = N_DEV * CICLOS_DIA
pd.DataFrame([
    {"etapa": "transmitidos",        "n": transmitidos,      "ordem": 1},
    {"etapa": "sobrevivem à colisão","n": transmitidos - meio["colisao"], "ordem": 2},
    {"etapa": "chegam ao gateway",   "n": meio["entregues"], "ordem": 3},
    {"etapa": "passam no CRC",       "n": s["recebidos"],    "ordem": 4},
]).to_csv(OUT / "fig7b_funil.csv", index=False)

# --- 7c: alerta por dispositivo ---------------------------------------------
alertados = {e.device_id for e in r.eventos if e.tipo == "alerta"}
pd.DataFrame([
    {"dispositivo": i,
     "taxa_anomalia": 0.7 if i in ANOMALOS else 0.02,
     "alertou": (0xA000 + i) in alertados,
     "sustentada": i in ANOMALOS}
    for i in range(N_DEV)
]).to_csv(OUT / "fig7c_alertas.csv", index=False)

# --- 7d: o que o gateway consegue reconstruir do que se perdeu --------------
pd.DataFrame([
    {"grandeza": "perdidos no ar",        "n": meio["perda"] + meio["corrupcao"]},
    {"grandeza": "lacunas detectadas",    "n": s["perdidos"]},
    {"grandeza": "corrompidos injetados", "n": meio["corrupcao"]},
    {"grandeza": "descartados pelo CRC",  "n": s["descartados"]},
]).to_csv(OUT / "fig7d_deteccao.csv", index=False)

print(f"  jitter: sem={linhas[-2]['p_colisao']:.1%} com={linhas[-1]['p_colisao']:.1%} (n={linhas[-1]['n_dispositivos']})")
print(f"  funil:  {transmitidos} -> {s['recebidos']} leituras ({s['recebidos']/transmitidos:.1%})")
print(f"  CRC:    {meio['corrupcao']} injetados, {s['descartados']} descartados")
print(f"  alerta: {sorted(hex(d) for d in alertados)}")
print(f"  CSVs em {OUT}")
