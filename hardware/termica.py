"""Condução 3D do motor até a placa, em regime e no transiente.

`experiments/notebooks/analise-termica.ipynb` respondeu isso por modelo
concentrado: uma resistência de condução em série com a troca externa, e o
invólucro inteiro a uma única temperatura. Duas coisas ficaram de fora, e as
duas passaram a ser calculáveis quando os sólidos apareceram:

  1. O GRADIENTE. Com k = 0,17 W/(m·K), o ASA não é isotérmico. A base
     encostada no motor e a tampa não estão na mesma temperatura, e o modelo
     de um nó não sabe dizer a diferença.
  2. Onde a PLACA está nesse gradiente — e ela não toca em nada
     (hardware/fem/README.md), então só se acopla por radiação e convecção
     interna.

Unidades de CalculiX: mm, t, s, mW, °C. Nelas a condutividade tem o mesmo
valor numérico que em W/(m·K).

    uv run --no-project --with gmsh --with numpy python hardware/termica.py
"""
import math
import pathlib
import subprocess
import sys

import numpy as np

# Constantes, malha e solver moram em termica_base.py, compartilhados com
# termica_carga.py.
from termica_base import *  # noqa: E402,F401,F403

# ---------------------------------------------------------------------
# Execução
# ---------------------------------------------------------------------
print(f"motor {T_MOTOR:.0f} °C, ambiente {T_AMB:.0f} °C, "
      f"ASA k = {K_ASA} W/(m·K), eps = {EPS}")
print("entrada pelos quatro bolsos de ímã; cavidade adiabática; "
      "radiação linearizada\n")

RES = {}
for ver in ("v1", "v2"):
    saida = AQUI / "fem" / ver
    step = saida / "involucro.step"
    if not step.exists():
        raise SystemExit(f"falta {step} — rode hardware/fem_caminho.py "
                         f"no freecadcmd")
    inp = saida / "termica_malha.inp"
    nn = malha(step, inp)
    nos, elems = le_inp(inp)
    faces = contorno(nos, elems)
    ima, cav, ext = classifica(faces, ver)
    nos_ima = {v for eid, k in ima
               for v in []}  # preenchido abaixo
    # nós das faces de ímã
    mapa = {e: vs for e, vs in elems}
    nos_ima = set()
    for eid, k in ima:
        vs = mapa[eid]
        nos_ima.update(vs[i] for i in FACES_TET[k - 1])
    a_ext = 0.0
    print(f"=== {ver} — {nn} nós, {len(elems)} C3D10 ===")
    print(f"  faces: {len(ima)} de ímã, {len(cav)} de cavidade, "
          f"{len(ext)} externas")

    # h externo depende do salto, que é o que se quer descobrir: duas
    # passadas bastam, porque o salto é de poucos kelvin.
    h = h_externo(5.0)
    for passada in range(2):
        h_mm = h * 1e-3                     # W/(m²K) -> mW/(mm²K)
        d = saida / f"termica_regime.inp"
        escreve(inp, d, nos_ima, ext, h_mm, max(nos), None)
        passos = le_temperaturas(roda(d))
        T = passos[-1][1]
        t_cav = [T[n] for n, _p in nos.items() if n in T]
        # temperatura das faces de cavidade (o que a placa enxerga)
        vs_cav = set()
        for eid, k in cav:
            vs_cav.update(mapa[eid][i] for i in FACES_TET[k - 1])
        t_int = np.mean([T[n] for n in vs_cav if n in T])
        h = h_externo(max(t_int - T_AMB, 0.5))
    tmin, tmax = min(T.values()), max(T.values())
    print(f"  h externo convergido: {h:.1f} W/(m²·K)")
    print(f"  campo: {tmin:.1f} a {tmax:.1f} °C")
    print(f"  parede da cavidade (o que a placa enxerga): {t_int:.1f} °C  "
          f"-> salto de {t_int - T_AMB:.1f} K sobre o ambiente")
    # gradiente ao longo da altura
    zs = np.array([nos[n][2] for n in T])
    ts = np.array([T[n] for n in T])
    for frac, rot in ((0.05, "base (junto ao motor)"), (0.5, "meia altura"),
                      (0.95, "topo (tampa)")):
        z = zs.min() + frac * (zs.max() - zs.min())
        m = np.abs(zs - z) < 2.0
        if m.any():
            print(f"    z = {z:5.1f} mm  {rot:<24} {ts[m].mean():5.1f} °C")
    RES[ver] = dict(t_int=float(t_int), tmin=float(tmin), tmax=float(tmax),
                    h=float(h), nos=nos, T=dict(T), cav=vs_cav,
                    inp=inp, nos_ima=nos_ima, ext=ext, n_max=max(nos))
    print()
sys.stdout.flush()


# ---------------------------------------------------------------------
# Transiente: quanto tempo até chegar lá
# ---------------------------------------------------------------------
PASSO, TOTAL = 60.0, 14400.0        # 4 h em passos de 1 min

# DENTRO (massa e área de troca de placa e célula) mora em termica_base.py.

print("transiente: degrau de 30 para 90 °C na carcaça, em t = 0\n")
for ver in ("v1", "v2"):
    r = RES[ver]
    saida = AQUI / "fem" / ver
    d = saida / "termica_transiente.inp"
    escreve(r["inp"], d, r["nos_ima"], r["ext"], r["h"] * 1e-3, r["n_max"],
            transiente=(PASSO, TOTAL))
    passos = le_temperaturas(roda(d))
    curva = [(t, float(np.mean([T[n] for n in r["cav"] if n in T])))
             for t, T in passos if T]
    if len(curva) < 3:
        raise SystemExit(f"{ver}: transiente devolveu {len(curva)} passo(s)")
    t_fim = curva[-1][1]

    def quando(frac):
        """Instante em que a parede atinge `frac` do salto, INTERPOLADO.

        O CalculiX cresce o incremento geometricamente: são 13 pontos em 4 h,
        e o intervalo no meio da subida passa de 10 min. Pegar a primeira
        amostra acima do alvo devolvia 33 min onde a interpolação dá 23 —
        erro de amostragem, não de física.
        """
        alvo = T_AMB + frac * (r["t_int"] - T_AMB)
        ant = None
        for tt, vv in curva:
            if vv >= alvo:
                if ant is None:
                    return tt
                t0, v0 = ant
                return t0 + (tt - t0) * (alvo - v0) / (vv - v0)
            ant = (tt, vv)
        return None

    tau, t90 = quando(0.632), quando(0.90)

    dcfg = DENTRO[ver]
    c_int = dcfg["m_placa"] * CP_FR4 + dcfg["m_bat"] * CP_LIPO       # J/K
    r_int = 1.0 / (r["h"] * dcfg["area"])                            # K/W
    tau_int = c_int * r_int

    print(f"=== {ver} ===")
    print(f"  parede da cavidade: {curva[0][1]:.1f} °C em t=0  ->  "
          f"{t_fim:.1f} °C em {TOTAL/3600:.0f} h "
          f"(regime permanente: {r['t_int']:.1f} °C)")
    print(f"  tau do invólucro (63% do salto):  "
          f"{'%.0f min' % (tau/60) if tau else '> 4 h'}")
    print(f"  90% do salto:                     "
          f"{'%.0f min' % (t90/60) if t90 else '> 4 h'}")
    print(f"  massa térmica interna (placa + célula): {c_int:.0f} J/K, "
          f"acoplada por {r_int:.0f} K/W")
    print(f"  tau da placa e da célula, dentro:  {tau_int/60:.0f} min")
    print(f"  salto total sobre o ambiente:     "
          f"{r['t_int'] - T_AMB:.1f} K  (limite de carga da LiPo: 45 °C, "
          f"margem de {45 - r['t_int']:.1f} K)")
    RES[ver]["curva"] = curva
    RES[ver]["tau_int"] = tau_int
    RES[ver]["tau"], RES[ver]["t90"] = tau, t90
    print()
sys.stdout.flush()


# ---------------------------------------------------------------------
# Dados para a figura
# ---------------------------------------------------------------------
import csv                                                  # noqa: E402

DADOS = AQUI.parent / "experiments" / "figures" / "data"
DADOS.mkdir(parents=True, exist_ok=True)

with (DADOS / "fig11_perfil.csv").open("w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["versao", "z_mm", "t_media", "t_min", "t_max"])
    for ver in ("v1", "v2"):
        r = RES[ver]
        zs = np.array([r["nos"][n][2] for n in r["T"]])
        ts = np.array([r["T"][n] for n in r["T"]])
        bordas = np.linspace(zs.min(), zs.max(), 60)
        for a, b in zip(bordas[:-1], bordas[1:]):
            m = (zs >= a) & (zs < b)
            if m.sum() < 3:
                continue
            w.writerow([ver, f"{(a + b) / 2:.2f}", f"{ts[m].mean():.3f}",
                        f"{ts[m].min():.3f}", f"{ts[m].max():.3f}"])

with (DADOS / "fig11_transiente.csv").open("w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["versao", "t_s", "t_parede"])
    for ver in ("v1", "v2"):
        for t, v in RES[ver]["curva"]:
            w.writerow([ver, f"{t:.1f}", f"{v:.4f}"])

# Comparação do modelo concentrado: como estava e resolvido até a raiz.
def _bal(T, Tc, Rp, a_ext):
    hc = 2.0 if T <= T_AMB else 1.42 * ((T - T_AMB) / 0.05) ** 0.25
    q = hc * a_ext * (T - T_AMB) + EPS * SIGMA * a_ext * (
        (T + 273.15) ** 4 - (T_AMB + 273.15) ** 4)
    return (Tc - T) / Rp - q


A_SPIG = math.pi * 14.0 ** 2
A_EXT_NB = 4 * 0.050 * 0.078 + 0.050 ** 2
R_NB = (6e-3 + 3.3e-3) / (K_ASA * A_SPIG * 1e-6)

with (DADOS / "fig11_correcao.csv").open("w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["t_carcaca", "modelo", "t_interna"])
    for tc in np.arange(40.0, 121.0, 2.5):
        # como o notebook calcula: 500 passos de ganho fixo
        T = (tc + T_AMB) / 2
        for _ in range(500):
            T += 0.005 * _bal(T, tc, R_NB, A_EXT_NB)
        w.writerow([f"{tc:.1f}", "concentrado, 500 iterações", f"{T:.3f}"])
        # o mesmo balanço, resolvido
        lo, hi = T_AMB + 1e-6, tc
        for _ in range(200):
            mid = (lo + hi) / 2
            if _bal(mid, tc, R_NB, A_EXT_NB) > 0:
                lo = mid
            else:
                hi = mid
        w.writerow([f"{tc:.1f}", "concentrado, convergido", f"{(lo+hi)/2:.3f}"])

with (DADOS / "fig11_referencias.csv").open("w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["t_motor", "t_amb", "lipo_carga", "lipo_descarga",
                "t_int_v1", "t_int_v2", "tau_min", "t90_min"])
    w.writerow([T_MOTOR, T_AMB, 45.0, 60.0,
                f"{RES['v1']['t_int']:.2f}", f"{RES['v2']['t_int']:.2f}",
                f"{RES['v1']['tau']/60:.0f}", f"{RES['v1']['t90']/60:.0f}"])

print(f"dados escritos em {DADOS}/fig11_*.csv")
print("figura: Rscript experiments/figures/scripts/fig11_termica3d.R")
sys.stdout.flush()
