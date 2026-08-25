"""Exporta os dados-fonte da figura térmica.

Reproduz a computação de experiments/notebooks/analise-termica.ipynb e grava CSVs
em figures/data/. O plot é feito em R (figures/scripts/fig4_termica.R).

Uso:  uv run python figures/scripts/export_thermal_data.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parents[1] / "data"
OUT.mkdir(parents=True, exist_ok=True)

SIGMA = 5.67e-8

# ---------------------------------------------------------------------------
# Geometria (cotas do desenho, mm) e materiais
# ---------------------------------------------------------------------------
BASE_H = 6.0
SPIGOT_D, SPIGOT_H = 28.0, 3.3
CORPO_EXT, PAREDE, ALT = 50.0, 3.5, 78.0

A_SPIGOT = np.pi * (SPIGOT_D / 2)**2                                  # mm²
A_EXT = 4 * (CORPO_EXT * 1e-3) * (ALT * 1e-3) + (CORPO_EXT * 1e-3)**2  # m²

K_ASA, K_AL, K_ACO = 0.17, 205.0, 50.0
E_ASA, E_AL, NU = 2.0e9, 69e9, 0.35
EPS, T_AMB = 0.90, 30.0
MASSA = 118e-3

LIM_CARGA, LIM_DESCARGA = 45.0, 60.0


def write(df, name):
    df.to_csv(OUT / name, index=False)
    print(f"  {name:<32} {len(df):>5} linhas")


# ---------------------------------------------------------------------------
# Modelo térmico
# ---------------------------------------------------------------------------
def r_cond(l_mm, a_mm2, k):
    return (l_mm * 1e-3) / (k * (a_mm2 * 1e-6))


def h_conv(dt, l_car=0.05):
    return 2.0 if dt <= 0 else 1.42 * (dt / l_car)**0.25


def temp_corpo(t_carcaca, r_path, t_amb=T_AMB, tol=1e-7):
    """Balanço em regime permanente: condução entra, convecção + radiação saem."""
    t = (t_carcaca + t_amb) / 2
    for _ in range(500):
        q_in = (t_carcaca - t) / r_path
        q_out = (h_conv(t - t_amb) * A_EXT * (t - t_amb)
                 + EPS * SIGMA * A_EXT * ((t + 273.15)**4 - (t_amb + 273.15)**4))
        t += 0.005 * (q_in - q_out)
        if abs(q_in - q_out) < tol:
            break
    return t


R_ASA = r_cond(BASE_H, A_SPIGOT, K_ASA) + r_cond(SPIGOT_H, A_SPIGOT, K_ASA)
R_AL = r_cond(BASE_H, A_SPIGOT, K_AL) + r_cond(SPIGOT_H, A_SPIGOT, K_AL)
R_AL_ISO = (r_cond(BASE_H, A_SPIGOT, K_AL)
            + r_cond(2.0, A_SPIGOT, K_ASA)      # quebra térmica de 2 mm
            + r_cond(SPIGOT_H, A_SPIGOT, K_AL))

print("gerando dados-fonte térmicos...\n")

# --- 4a: temperatura interna vs. carcaça, por configuração de base
tc = np.linspace(30, 110, 240)
rows = []
for nome, ordem, r in [("Base ASA (atual)", 1, R_ASA),
                       ("Base alumínio", 2, R_AL),
                       ("Alumínio + quebra 2 mm", 3, R_AL_ISO)]:
    rows.append(pd.DataFrame({
        "t_carcaca_c": tc,
        "t_interna_c": [temp_corpo(t, r) for t in tc],
        "config": nome, "ordem": ordem,
    }))
write(pd.concat(rows), "fig4a_temperatura.csv")

# --- 4b: limites térmicos dos componentes
LIMITES = [
    ("LiPo — carga", 45, "bateria"),
    ("LiPo — descarga", 60, "bateria"),
    ("LiPo — risco", 70, "bateria"),
    ("MPU6050", 85, "eletrônica"),
    ("ESP32-S3", 85, "eletrônica"),
    ("ASA — HDT", 98, "invólucro"),
    ("ASA — Tg", 105, "invólucro"),
    ("Ímã N42SH", 150, "fixação"),
    ("Ímã N35UH", 180, "fixação"),
]
ti_80 = temp_corpo(80.0, R_ASA)
df = pd.DataFrame(
    [{"componente": n, "limite_c": t, "grupo": g, "ordem": i}
     for i, (n, t, g) in enumerate(LIMITES)]
)
df["excedido_a_80"] = df.limite_c < ti_80
df["margem_c"] = df.limite_c - ti_80
write(df, "fig4b_limites.csv")

# --- 4c: trade-off rigidez x temperatura
R_BASE_EF = SPIGOT_D / 2 + 13


def f_montagem(e_base, e_corpo=E_ASA):
    """Mesmo modelo da análise do invólucro (item 8)."""
    h, a = BASE_H * 1e-3, R_BASE_EF * 1e-3
    k_base = 16 * np.pi * (e_base * h**3 / (12 * (1 - NU**2))) / a**2
    k_spigot = e_base * (A_SPIGOT * 1e-6) / (SPIGOT_H * 1e-3)
    lado, t, l_ = CORPO_EXT * 1e-3, PAREDE * 1e-3, ALT * 1e-3
    inercia = (lado**4 - (lado - 2 * t)**4) / 12
    k_corpo = 3 * e_corpo * inercia / l_**3
    k = 1 / (1 / k_base + 1 / k_spigot + 1 / k_corpo)
    return (1 / (2 * np.pi)) * np.sqrt(k / MASSA)


write(pd.DataFrame([
    {"config": "Base ASA\n(atual)", "f_n_hz": f_montagem(E_ASA),
     "t_interna_c": temp_corpo(80.0, R_ASA)},
    {"config": "Base\nalumínio", "f_n_hz": f_montagem(E_AL),
     "t_interna_c": temp_corpo(80.0, R_AL)},
    {"config": "Alumínio +\nquebra térmica", "f_n_hz": f_montagem(E_AL),
     "t_interna_c": temp_corpo(80.0, R_AL_ISO)},
]), "fig4c_tradeoff.csv")

# --- 4d: efeito da espessura da quebra térmica
rows = []
for e_iso in [0.0, 0.25, 0.5, 1.0, 1.5, 2.0, 3.0, 5.0]:
    r = (r_cond(BASE_H, A_SPIGOT, K_AL)
         + (r_cond(e_iso, A_SPIGOT, K_ASA) if e_iso > 0 else 0.0)
         + r_cond(SPIGOT_H, A_SPIGOT, K_AL))
    rows.append({"isolador_mm": e_iso, "r_total_k_w": r,
                 "t_interna_c": temp_corpo(80.0, r)})
write(pd.DataFrame(rows), "fig4d_isolador.csv")

# --- referências para anotação
def carcaca_para(alvo, r_path):
    for t in np.arange(T_AMB, 250, 0.5):
        if temp_corpo(t, r_path) >= alvo:
            return t
    return np.nan


m_asa, cp_asa = 0.118, 1300.0
m_bat, cp_bat = 0.040, 1000.0
c_th = m_asa * cp_asa + m_bat * cp_bat
r_amb = 1 / (h_conv(20) * A_EXT + 4 * EPS * SIGMA * A_EXT * (320.0**3))

write(pd.DataFrame([{
    "t_interna_80_asa": ti_80,
    "t_carcaca_lim_carga": carcaca_para(LIM_CARGA, R_ASA),
    "lim_carga_c": LIM_CARGA,
    "lim_descarga_c": LIM_DESCARGA,
    "r_asa_k_w": R_ASA,
    "r_al_k_w": R_AL,
    "razao_r": R_ASA / R_AL,
    "tau_min": c_th * r_amb / 60,
    "banda_iso_hz": 1000.0,
}]), "fig4_referencias.csv")

print(f"\nT interna @80 °C (ASA) = {ti_80:.1f} °C")
print(f"carcaça que bloqueia a carga = {carcaca_para(LIM_CARGA, R_ASA):.0f} °C")
print(f"CSVs em {OUT}")
