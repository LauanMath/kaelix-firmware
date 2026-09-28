"""Aquecimento interno durante a carga da bateria (placa v3, invólucro v2).

termica.py trata a cavidade como ADIABÁTICA, e para a operação isso vale: são
2,0 mW médios, que elevam o interior em centésimos de kelvin. Na carga não
vale. O BQ21040 é linear e dissipa

    P = I_carga · (V_USB − V_bat)

dentro do invólucro fechado — centenas de mW, duas ordens de grandeza acima
da operação. A pergunta é se a célula, somada essa fonte ao calor que vem da
carcaça, ainda fica abaixo dos 45 °C em que o próprio BQ21040 suspende a carga
pelo pino TS.

Modelo: a mesma malha, o mesmo material e a mesma troca externa de
termica.py (termica_base.py). A potência entra como fluxo uniforme pelas faces
da cavidade — é por elas que o calor tem de sair, qualquer que seja o caminho
interno. A placa fica acima da parede pela resistência interna de
termica.py, R_int = 1 / (h · área), e a temperatura da placa é o que o NTC do
TS lê. A célula fica entre a parede e a placa, então a leitura da placa é o
limite SUPERIOR da temperatura da célula: o TS corta cedo, nunca tarde. Com
o motor quente a placa ainda fica acima da média da parede, por enxergar o
piso quente; esse acréscimo vem de hardware/fem/README.md e é somado como
segundo limite (EXTRA_RADIATIVO).

Três cenários:
  bancada       fora do motor; os bolsos de ímã trocam calor com o ar
  motor frio    preso ao motor parado, carcaça na temperatura ambiente
  motor quente  preso ao motor em operação, carcaça a 90 °C

    uv run --no-project --with gmsh --with numpy python hardware/termica_carga.py
"""
import csv
import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from termica_base import (AQUI, T_AMB, T_MOTOR, FACES_TET, DENTRO,  # noqa: E402
                          h_externo, malha, le_inp, contorno, classifica,
                          escreve, roda, le_temperaturas)

VER = "v2"                    # a placa v3 vai no invólucro v2
V_USB = 5.0                   # V; porta USB nominal (5,25 V no teto da norma)
R_CELULA = 0.15               # ohm; resistência interna típica de LiPo de 2 Ah
T_TS_QUENTE = 45.0            # °C; V_TS-45C da folha de dados do BQ21040

CENARIOS = [("bancada", False), ("motor frio", T_AMB), ("motor quente", T_MOTOR)]

# Com o motor quente a cavidade NÃO é isotérmica, e a placa não fica na média
# dela: a 5 mm do piso, com fator de forma 0,84 para ele, o equilíbrio
# radiativo sai 3,2 K acima da média (38,3 contra 35,1 °C na v2 —
# hardware/fem/README.md, "A placa não fica na média da cavidade"; valor
# daquela análise, não recalculado aqui). O real fica entre os dois: a mistura
# do ar puxa para a média. Os dois extremos são reportados. Sem motor quente
# não há gradiente, e o acréscimo é zero.
EXTRA_RADIATIVO = {"motor quente": 38.3 - 35.1}
POTENCIAS_W = [0.0, 0.25, 0.5, 1.0]


def area_tri(a, b, c):
    return 0.5 * float(np.linalg.norm(np.cross(np.subtract(b, a), np.subtract(c, a))))


saida = AQUI / "fem" / VER
inp = saida / "termica_malha.inp"
if not inp.exists():
    malha(saida / "involucro.step", inp)
nos, elems = le_inp(inp)
mapa = dict(elems)
ima, cav, ext = classifica(contorno(nos, elems), VER)
nos_ima = set()
for eid, k in ima:
    nos_ima.update(mapa[eid][i] for i in FACES_TET[k - 1])
vs_cav = set()
areas = []
for eid, k in cav:
    vv = [mapa[eid][i] for i in FACES_TET[k - 1]]
    vs_cav.update(vv)
    areas.append((eid, k, area_tri(*(nos[v] for v in vv))))
a_cav = sum(a for _e, _k, a in areas)                     # mm²
print(f"invólucro {VER}: {len(cav)} faces de cavidade, {a_cav:.0f} mm²")


def resolve(nome, t_motor, p_w):
    """Temperatura média da parede da cavidade e o h convergido."""
    q = p_w * 1e3 / a_cav                                  # mW/mm², uniforme
    fonte = [(e, k, q) for e, k, _a in areas] if p_w > 0 else ()
    extra = ima if t_motor is False else ()
    h = h_externo(5.0)
    for _passada in range(2):
        d = saida / "termica_carga.inp"
        escreve(inp, d, nos_ima, ext, h * 1e-3, max(nos), None,
                t_motor=t_motor, fonte=fonte, film_extra=extra)
        T = le_temperaturas(roda(d))[-1][1]
        t_par = float(np.mean([T[n] for n in vs_cav if n in T]))
        h = h_externo(max(t_par - T_AMB, 0.5))
    return t_par, h


linhas = []
for nome, t_motor in CENARIOS:
    for p in POTENCIAS_W:
        t_par, h = resolve(nome, t_motor, p)
        r_int = 1.0 / (h * DENTRO[VER]["area"])            # K/W
        t_placa = t_par + p * r_int
        linhas.append((nome, p, t_par, r_int, t_placa))
        print(f"  {nome:<13} P = {p:4.2f} W   parede {t_par:5.1f} °C   "
              f"R_int {r_int:4.1f} K/W   placa {t_placa:5.1f} °C")
    sys.stdout.flush()

# Linearização por cenário: t_placa = t0 + g·P. Conferida contra os pontos.
AJUSTE = {}
for nome, _t in CENARIOS:
    pts = [(p, tp) for n, p, _tp, _r, tp in linhas if n == nome]
    g, t0 = np.polyfit([p for p, _ in pts], [t for _, t in pts], 1)
    res = max(abs(t0 + g * p - t) for p, t in pts)
    AJUSTE[nome] = (t0, g)
    print(f"\n{nome}: placa = {t0:.1f} °C + {g:.1f} K/W · P   (resíduo {res:.2f} K)")

# Corrente de carga: P no pior ponto da fase de corrente constante (V_bat =
# 3,0 V) e no ponto médio (3,7 V), mais o I²R da célula.
print(f"\nV_USB = {V_USB} V; corte do TS em {T_TS_QUENTE:.0f} °C; "
      f"motor quente em 'média .. radiativo'\n")
print(f"{'I carga':>8} {'R_ISET':>7} {'P@3,0V':>7} {'P@3,7V':>7} "
      f"{'bancada':>14} {'motor frio':>14} {'motor quente':>22}   tempo")
tabela = []
for i_ma in (100, 150, 200, 250, 300, 500):
    i = i_ma / 1000
    p30 = i * (V_USB - 3.0) + i * i * R_CELULA
    p37 = i * (V_USB - 3.7) + i * i * R_CELULA
    riset = 540.0 / i                                        # K_ISET típico
    temps = {n: AJUSTE[n][0] + AJUSTE[n][1] * p30 for n, _ in CENARIOS}
    t_rad = temps["motor quente"] + EXTRA_RADIATIVO["motor quente"]
    horas = 2.0 / i * 1.15                                   # CC + cauda de CV
    m = lambda t: "ok" if t < T_TS_QUENTE else "CORTA"
    print(f"{i_ma:>6} mA {riset:>6.0f}Ω {p30:>6.2f}W {p37:>6.2f}W "
          f"{temps['bancada']:6.1f} °C {m(temps['bancada']):<5} "
          f"{temps['motor frio']:6.1f} °C {m(temps['motor frio']):<5} "
          f"{temps['motor quente']:5.1f}..{t_rad:4.1f} °C {m(t_rad):<5}"
          f"   ~{horas:.0f} h")
    tabela.append((i_ma, riset, p30, p37, temps["bancada"], temps["motor frio"],
                   temps["motor quente"], t_rad, horas))

dados = AQUI.parent / "experiments" / "figures" / "data" / "termica_carga.csv"
with dados.open("w", newline="") as fh:
    w = csv.writer(fh, lineterminator="\n")
    w.writerow(["cenario", "p_w", "t_parede", "r_int_kw", "t_placa",
                "t_placa_radiativo"])
    for nome, p, tpar, r, tp in linhas:
        w.writerow([nome, f"{p:.2f}", f"{tpar:.3f}", f"{r:.2f}", f"{tp:.3f}",
                    f"{tp + EXTRA_RADIATIVO.get(nome, 0.0):.3f}"])
print(f"\ndados escritos em {dados}")
