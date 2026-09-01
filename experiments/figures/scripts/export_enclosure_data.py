"""Exporta os dados-fonte da figura do invólucro.

Reproduz a computação de experiments/notebooks/analise-involucro.ipynb e grava
CSVs em experiments/figures/data/. O plot é feito em R (experiments/figures/scripts/fig3_involucro.R).

Uso:  uv run python experiments/figures/scripts/export_enclosure_data.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parents[1] / "data"
OUT.mkdir(parents=True, exist_ok=True)

MU0 = 4e-7 * np.pi

# ---------------------------------------------------------------------------
# Cotas do desenho (docs/device/, versão 4) — mm
# ---------------------------------------------------------------------------
CORPO_EXT = 50.0
PAREDE, FUNDO = 3.5, 8.0
ALTURA_TOTAL = 78.0
BASE_LADO = 54.0
SPIGOT_D, SPIGOT_H = 28.0, 3.3
MAG_D, MAG_T, MAG_R = 10.0, 3.0, 20.0
BOLSO_PROF = 3.2
MASSA = 118e-3                      # kg

E_ASA, RHO_ASA, NU = 2.0e9, 1070.0, 0.35
E_AL, E_ACO = 69e9, 200e9
H_BASE_EF = 6.0                     # espessura efetiva da base sob o spigot


def write(df, name):
    df.to_csv(OUT / name, index=False)
    print(f"  {name:<32} {len(df):>5} linhas")


# ---------------------------------------------------------------------------
# Fixação magnética
# ---------------------------------------------------------------------------
def entreferro(x_mm, d_carcaca_mm):
    """Sagitta a uma distância x do contato, base plana sobre cilindro."""
    r = d_carcaca_mm / 2
    return np.inf if abs(x_mm) >= r else r - np.sqrt(r**2 - x_mm**2)


def forca_ima(z_mm, br=1.30, d=MAG_D, t=MAG_T):
    """Força de atração ímã–aço em N (método das imagens). Br=1,30 T ≈ N42."""
    z, r, tt = max(z_mm, 1e-4) * 1e-3, (d / 2) * 1e-3, t * 1e-3
    area = np.pi * r**2
    termo = z / np.sqrt(z**2 + r**2) - (z + tt) / np.sqrt((z + tt)**2 + r**2)
    return (br**2 * area / (2 * MU0)) * termo**2


off = MAG_R / np.sqrt(2)
GAP_CONTATO = BOLSO_PROF - MAG_T          # ímã aflora 0,2 mm
F_pleno = 4 * forca_ima(GAP_CONTATO)

print("gerando dados-fonte do invólucro...\n")

rows = []
for d in [100, 150, 200, 250, 300, 400, 500]:
    g = entreferro(off, d)
    # 2 ímãs de uma diagonal tocam; 2 da outra ficam com entreferro
    f = 2 * forca_ima(GAP_CONTATO) + 2 * forca_ima(GAP_CONTATO + g)
    rows.append({"diametro_carcaca_mm": d, "entreferro_mm": g,
                 "forca_N": f, "forca_kgf": f / 9.81,
                 "perda_frac": 1 - f / F_pleno})
write(pd.DataFrame(rows), "fig3a_fixacao.csv")

# critério dinâmico: força inercial vs. força magnética disponível
def vel_para_acel(v_mm_s, f_hz):
    return 2 * np.pi * f_hz * v_mm_s * 1e-3


a_max_g = vel_para_acel(28.0, 1000) / 9.81
F_curva_pior = 2 * forca_ima(GAP_CONTATO) + 2 * forca_ima(GAP_CONTATO + entreferro(off, 150))
write(pd.DataFrame([{
    "aceleracao_g": a_max_g,
    "forca_inercial_N": MASSA * a_max_g * 9.81,
    "forca_magnetica_N": F_curva_pior,
    "margem": F_curva_pior / (MASSA * a_max_g * 9.81),
}]), "fig3a_margem.csv")

# ---------------------------------------------------------------------------
# Modos das placas
# ---------------------------------------------------------------------------
def f_placa(a_mm, b_mm, h_mm, e=E_ASA, rho=RHO_ASA):
    a, b, h = a_mm * 1e-3, b_mm * 1e-3, h_mm * 1e-3
    d = e * h**3 / (12 * (1 - NU**2))
    return (np.pi / 2) * np.sqrt(d / (rho * h)) * (1 / a**2 + 1 / b**2)


rows = []
for nome, a, b, h in [("Tampa", CORPO_EXT, CORPO_EXT, PAREDE),
                      ("Parede lateral", CORPO_EXT, ALTURA_TOTAL, PAREDE),
                      ("Fundo", CORPO_EXT, CORPO_EXT, FUNDO)]:
    f = f_placa(a, b, h)
    rows.append({"painel": nome, "espessura_mm": h,
                 "f_apoiada_hz": f, "f_engastada_hz": 1.8 * f})
write(pd.DataFrame(rows), "fig3b_modos.csv")

# ---------------------------------------------------------------------------
# Rigidez do caminho de transmissão
# ---------------------------------------------------------------------------
def k_placa_circular(h_mm, a_mm, e=E_ASA):
    """Placa circular engastada, carga central: k = 16*pi*D/a²."""
    h, a = h_mm * 1e-3, a_mm * 1e-3
    d = e * h**3 / (12 * (1 - NU**2))
    return 16 * np.pi * d / a**2


def k_compressao(d_mm, l_mm, e=E_ASA):
    area = np.pi * (d_mm * 1e-3 / 2)**2
    return e * area / (l_mm * 1e-3)


def k_viga_tubo(a_mm, t_mm, l_mm, e=E_ASA):
    """Tubo quadrado em flexão, engastado, carga na ponta: k = 3EI/L³."""
    a, t, l_ = a_mm * 1e-3, t_mm * 1e-3, l_mm * 1e-3
    inercia = (a**4 - (a - 2 * t)**4) / 12
    return 3 * e * inercia / l_**3


def serie(*ks):
    return 1 / sum(1 / k for k in ks)


R_BASE = SPIGOT_D / 2 + 13

k_base = k_placa_circular(H_BASE_EF, R_BASE)
k_spigot = k_compressao(SPIGOT_D, SPIGOT_H)
k_corpo = k_viga_tubo(CORPO_EXT, PAREDE, ALTURA_TOTAL)
k_total = serie(k_base, k_spigot, k_corpo)
F_N = (1 / (2 * np.pi)) * np.sqrt(k_total / MASSA)

flex_tot = 1 / k_base + 1 / k_spigot + 1 / k_corpo
write(pd.DataFrame([
    {"elo": "Base ASA\n(placa, h≈6 mm)", "ordem": 1, "k_N_m": k_base,
     "flex_frac": (1 / k_base) / flex_tot},
    {"elo": "Spigot Ø28×3,3\n(compressão)", "ordem": 2, "k_N_m": k_spigot,
     "flex_frac": (1 / k_spigot) / flex_tot},
    {"elo": "Corpo 50×50×3,5\n(flexão, L=78)", "ordem": 3, "k_N_m": k_corpo,
     "flex_frac": (1 / k_corpo) / flex_tot},
]), "fig3c_rigidez.csv")

# transmissibilidade por material
def transmissibilidade(f, fn, zeta=0.03):
    r = f / fn
    return 1 / np.sqrt((1 - r**2)**2 + (2 * zeta * r)**2)


freqs = np.logspace(np.log10(10), np.log10(3000), 700)
rows = []
fn_por_material = {}
for nome, e in [("ASA (atual)", E_ASA), ("Alumínio", E_AL), ("Aço", E_ACO)]:
    kt = serie(k_placa_circular(H_BASE_EF, R_BASE, e),
               k_compressao(SPIGOT_D, SPIGOT_H, e),
               k_viga_tubo(CORPO_EXT, PAREDE, ALTURA_TOTAL, e))
    fn = (1 / (2 * np.pi)) * np.sqrt(kt / MASSA)
    fn_por_material[nome] = fn
    rows.append(pd.DataFrame({
        "freq_hz": freqs, "T": transmissibilidade(freqs, fn),
        "material": nome, "f_n_hz": fn,
        "rotulo": f"{nome} — f_n = {fn:.0f} Hz",
    }))
    print(f"    {nome:<12} k={kt:.2e} N/m  f_n={fn:.0f} Hz")
write(pd.concat(rows), "fig3d_transmissibilidade.csv")

# erro de amplitude dentro da banda do sensor
fb = np.linspace(10, 500, 400)
err = (transmissibilidade(fb, F_N) - 1) * 100
f10 = fb[np.argmax(err > 10)]
write(pd.DataFrame({"freq_hz": fb, "erro_pct": err}), "fig3e_erro.csv")

# sensibilidade à espessura da base
rows = []
for h in [4.0, 5.0, 6.0, 7.0, 9.0, 12.0]:
    kt = serie(k_placa_circular(h, R_BASE), k_spigot, k_corpo)
    rows.append({"h_base_mm": h, "k_N_m": kt,
                 "f_n_hz": (1 / (2 * np.pi)) * np.sqrt(kt / MASSA)})
write(pd.DataFrame(rows), "fig3f_sensibilidade.csv")

# referências usadas nas anotações
write(pd.DataFrame([{
    "f_n_asa_hz": F_N,
    "f_erro10_hz": f10,
    "banda_sensor_hz": 500.0,
    "banda_iso_hz": 1000.0,
    "regra_3x_iso_hz": 3000.0,
    "modo_placa_min_hz": min(f_placa(a, b, h) for _, a, b, h in
                             [("", CORPO_EXT, CORPO_EXT, PAREDE),
                              ("", CORPO_EXT, ALTURA_TOTAL, PAREDE),
                              ("", CORPO_EXT, CORPO_EXT, FUNDO)]),
}]), "fig3_referencias.csv")

print(f"\nf_n (ASA) = {F_N:.0f} Hz | erro > 10% a partir de {f10:.0f} Hz")
print(f"CSVs em {OUT}")
