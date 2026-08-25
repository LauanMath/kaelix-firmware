"""Exporta os dados-fonte das figuras do Kaelix.

Reproduz exatamente a computação de notebooks/validacao-questionamentos.ipynb e
grava CSVs em figures/data/. O plot é feito em R (figures/scripts/fig*.R).

Uso:  uv run python figures/scripts/export_source_data.py
"""
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import signal
from scipy.stats import kurtosis
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.metrics import roc_auc_score, roc_curve
from sklearn.model_selection import GroupKFold, train_test_split
from sklearn.preprocessing import StandardScaler

OUT = Path(__file__).resolve().parents[1] / "data"
OUT.mkdir(parents=True, exist_ok=True)

# ----------------------------------------------------------------------------
# Parâmetros do caso de estudo
# ----------------------------------------------------------------------------
RPM = 1750.0
FR = RPM / 60.0
ND, PD, NB, THETA = 0.3126, 1.537, 9, 0.0        # SKF 6205 (rolamento do CWRU)

FS_REF = 20_000.0      # sensor de banda larga (referência)
FS_MPU = 1_000.0       # MPU6050
DEC = int(FS_REF / FS_MPU)
DUR = 2.0


def bearing_freqs(fr, nb=NB, nd=ND, pd_=PD, theta=THETA):
    r = (nd / pd_) * np.cos(theta)
    return {
        "BPFO": nb / 2 * fr * (1 - r),
        "BPFI": nb / 2 * fr * (1 + r),
        "BSF": pd_ / (2 * nd) * fr * (1 - r**2),
        "FTF": fr / 2 * (1 - r),
    }


BF = bearing_freqs(FR)


def simulate(fs, dur, fr=FR, unbalance=0.5, bearing_defect=0.0,
             f_res=3500.0, decay=800.0, noise=0.05, seed=0):
    """Aceleração simulada em m/s². Ver notebook para a justificativa física."""
    rng = np.random.default_rng(seed)
    n = int(fs * dur)
    t = np.arange(n) / fs
    x = np.zeros(n)

    x += unbalance * np.sin(2 * np.pi * fr * t)
    x += 0.30 * unbalance * np.sin(2 * np.pi * 2 * fr * t + 0.7)
    x += 0.10 * unbalance * np.sin(2 * np.pi * 3 * fr * t + 1.3)

    if bearing_defect > 0:
        tau = 1.0 / BF["BPFO"]
        for t0 in np.arange(0, dur, tau):
            k = int((t0 + rng.normal(0, 0.01 * tau)) * fs)
            if 0 <= k < n:
                tt = t[k:] - t[k]
                x[k:] += bearing_defect * np.exp(-decay * tt) * np.sin(2 * np.pi * f_res * tt)

    return t, x + rng.normal(0, noise, n)


def write(df, name):
    p = OUT / name
    df.to_csv(p, index=False)
    print(f"  {name:<34} {len(df):>6} linhas")


print("gerando dados-fonte...\n")

# ============================================================================
# FIGURA 1 — limite de banda do sensor
# ============================================================================
t_ref, x_def = simulate(FS_REF, DUR, bearing_defect=2.0, seed=0)
_, x_ok = simulate(FS_REF, DUR, bearing_defect=0.0, seed=0)

mpu_def = signal.decimate(x_def, DEC, ftype="fir", zero_phase=True)
mpu_ok = signal.decimate(x_ok, DEC, ftype="fir", zero_phase=True)
alias_def, alias_ok = x_def[::DEC], x_ok[::DEC]

# --- 1a: densidade espectral (referência 20 kHz)
rows = []
for cond, x in [("sadio", x_ok), ("defeito", x_def)]:
    f, P = signal.welch(x, FS_REF, nperseg=4096)
    m = f <= 8000
    rows.append(pd.DataFrame({"freq_hz": f[m], "psd": P[m], "condicao": cond}))
write(pd.concat(rows), "fig1a_espectro.csv")

# --- 1b: contraste defeito/sadio em BPFO, por método
def envelope_spectrum(x, fs, band=(2000, 6000)):
    sos = signal.butter(4, band, "bandpass", fs=fs, output="sos")
    env = np.abs(signal.hilbert(signal.sosfiltfilt(sos, x)))
    env -= env.mean()
    n = len(env)
    E = np.abs(np.fft.rfft(env * signal.windows.hann(n))) / n * 2
    return np.fft.rfftfreq(n, 1 / fs), E


def spec(x, fs):
    n = len(x)
    return np.fft.rfftfreq(n, 1 / fs), np.abs(np.fft.rfft(x * signal.windows.hann(n))) / n * 2


def peak_at(f, S, f0, tol=3.0):
    return S[np.abs(f - f0) <= tol].max()


fe_d, Ee_d = envelope_spectrum(x_def, FS_REF)
fe_o, Ee_o = envelope_spectrum(x_ok, FS_REF)
fm_d, Sm_d = spec(mpu_def, FS_MPU)
fm_o, Sm_o = spec(mpu_ok, FS_MPU)

razao_env = peak_at(fe_d, Ee_d, BF["BPFO"]) / peak_at(fe_o, Ee_o, BF["BPFO"])
razao_mpu = peak_at(fm_d, Sm_d, BF["BPFO"]) / peak_at(fm_o, Sm_o, BF["BPFO"])

write(pd.DataFrame({
    "metodo": ["Envelope na ressonância\n(sensor 20 kHz)", "Espectro direto\n(MPU6050, 1 kHz)"],
    "metodo_curto": ["envelope 20 kHz", "espectro 1 kHz"],
    "contraste": [razao_env, razao_mpu],
}), "fig1b_contraste.csv")

# espectros de envelope e direto, para o painel comparativo
rows = []
for f, S, cond in [(fe_o, Ee_o, "sadio"), (fe_d, Ee_d, "defeito")]:
    m = f <= 600
    rows.append(pd.DataFrame({"freq_hz": f[m], "amp": S[m], "condicao": cond,
                              "painel": "envelope 20 kHz"}))
for f, S, cond in [(fm_o, Sm_o, "sadio"), (fm_d, Sm_d, "defeito")]:
    m = f <= 500
    rows.append(pd.DataFrame({"freq_hz": f[m], "amp": S[m], "condicao": cond,
                              "painel": "espectro direto 1 kHz"}))
write(pd.concat(rows), "fig1b_espectros_bpfo.csv")

# --- 1c: features de impacto por cadeia de aquisição
crest = lambda x: np.max(np.abs(x)) / np.sqrt(np.mean(x**2))
rows = []
for cadeia, ordem, a, b in [
    ("Referência 20 kHz", 1, x_ok, x_def),
    ("MPU6050 c/ antialias", 2, mpu_ok, mpu_def),
    ("MPU6050 s/ antialias", 3, alias_ok, alias_def),
]:
    # pico e pico-a-pico entram porque Fidali et al. (Sensors, 2024) os apontam como
    # mais sensíveis a falha de fadiga que a velocidade RMS
    for feat, fn in [("curtose", lambda z: kurtosis(z, fisher=False)),
                     ("fator de crista", crest),
                     ("pico", lambda z: np.max(np.abs(z))),
                     ("pico-a-pico", np.ptp)]:
        rows.append({"cadeia": cadeia, "ordem": ordem, "feature": feat,
                     "sadio": fn(a), "defeito": fn(b)})
df = pd.DataFrame(rows)
df["separacao"] = df["defeito"] - df["sadio"]
write(df, "fig1c_features.csv")

# --- 1d: dobramento por aliasing
fres = np.array([3000, 3300, 3500, 4200, 5100], dtype=float)
a = fres % FS_MPU
write(pd.DataFrame({
    "f_real_hz": fres,
    "f_aparente_hz": np.where(a <= FS_MPU / 2, a, FS_MPU - a),
}), "fig1d_aliasing.csv")

# ============================================================================
# FIGURA 2 — metodologia
# ============================================================================
FS_V, DUR_V = 5000.0, 4.0
A_AMP, F0 = 3.0, 50.0
tv = np.arange(int(FS_V * DUR_V)) / FS_V
a_test = A_AMP * np.sin(2 * np.pi * F0 * tv)
V_EXATO = (A_AMP / np.sqrt(2)) / (2 * np.pi * F0) * 1000.0


def vel_tempo_sem_hp(a, fs):
    return np.cumsum(a) / fs * 1000.0


def vel_tempo_com_hp(a, fs, hp=10.0):
    sos = signal.butter(4, hp, "hp", fs=fs, output="sos")
    return np.cumsum(signal.sosfiltfilt(sos, a)) / fs * 1000.0


def vel_freq(a, fs, f_lo=10.0, f_hi=1000.0):
    n = len(a)
    w = signal.windows.hann(n)
    A = np.fft.rfft(a * w)
    f = np.fft.rfftfreq(n, 1 / fs)
    V = np.zeros_like(A)
    m = (f >= f_lo) & (f <= f_hi)
    V[m] = A[m] / (2j * np.pi * f[m])
    return np.fft.irfft(V, n) / np.sqrt(np.mean(w**2)) * 1000.0


rms = lambda x: np.sqrt(np.mean(x**2))
a_bias = a_test + 0.02

metodos = [
    ("Integração no tempo\nsem passa-alta", 1, rms(vel_tempo_sem_hp(a_test, FS_V))),
    ("Integração no tempo\ncom passa-alta", 2, rms(vel_tempo_com_hp(a_test, FS_V))),
    ("Integração na frequência\n(banda ISO)", 3, rms(vel_freq(a_test, FS_V))),
    ("Na frequência\ncom bias 0,02 m/s²", 4, rms(vel_freq(a_bias, FS_V))),
    ("No tempo sem HP\ncom bias 0,02 m/s²", 5, rms(vel_tempo_sem_hp(a_bias, FS_V))),
]
df = pd.DataFrame(metodos, columns=["metodo", "ordem", "rms_mm_s"])
df["valor_exato"] = V_EXATO
df["erro_pct"] = (df.rms_mm_s - V_EXATO) / V_EXATO * 100
df["correto"] = df.erro_pct.abs() < 1.0
write(df, "fig2a_integracao.csv")

# deriva temporal (subamostrada para manter o CSV enxuto)
step = 5
write(pd.DataFrame({
    "tempo_s": np.r_[tv[::step], tv[::step]],
    "velocidade_mm_s": np.r_[vel_tempo_sem_hp(a_bias, FS_V)[::step], vel_freq(a_bias, FS_V)[::step]],
    "metodo": ["no tempo, sem passa-alta"] * len(tv[::step]) + ["na frequência"] * len(tv[::step]),
}), "fig2b_deriva.csv")

pd.DataFrame({"valor_exato_mm_s": [V_EXATO]}).to_csv(OUT / "fig2_referencia.csv", index=False)

# --- Split: vazamento vs. por ensaio ---------------------------------------
N_ENSAIOS = 5


def extrair_features(x, fs):
    r = np.sqrt(np.mean(x**2))
    mabs = np.mean(np.abs(x))
    f = np.fft.rfftfreq(len(x), 1 / fs)
    P = np.abs(np.fft.rfft(x * signal.windows.hann(len(x))))**2
    bandas = [(0, 100), (100, 500)] if fs <= 1100 else [(0, 100), (100, 500), (500, 2000), (2000, 6000)]
    e = [P[(f >= lo) & (f < hi)].sum() for lo, hi in bandas]
    tot = sum(e) + 1e-12
    return np.array([r, kurtosis(x, fisher=False), np.max(np.abs(x)) / r,
                     mabs, r / mabs] + [v / tot for v in e])


def janelas(x, fs, win=0.2, hop=0.1):
    n, h = int(win * fs), int(hop * fs)
    return [x[i:i + n] for i in range(0, len(x) - n, h)]


def gerar_ensaios(defeito, seed0):
    out = []
    for i in range(N_ENSAIOS):
        rng = np.random.default_rng(seed0 + i * 7)
        ganho = rng.uniform(0.6, 1.6)
        _, x = simulate(FS_REF, 3.0, unbalance=rng.uniform(0.3, 0.7) * ganho,
                        bearing_defect=defeito * ganho,
                        noise=rng.uniform(0.03, 0.12) * ganho, seed=seed0 * 100 + i)
        out.append(x)
    return out


sadios_i, defeitos_i = gerar_ensaios(0.00, 1), gerar_ensaios(0.25, 60)

X, y, ensaio = [], [], []
for r, x in enumerate(sadios_i + defeitos_i):
    xm = signal.decimate(x, DEC, ftype="fir", zero_phase=True)
    for w in janelas(xm, FS_MPU):
        X.append(extrair_features(w, FS_MPU))
        y.append(0 if r < N_ENSAIOS else 1)
        ensaio.append(r)
X, y, ensaio = np.array(X), np.array(y), np.array(ensaio)

acc_vaz = []
for s in range(10):
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.3, random_state=s, stratify=y)
    clf = RandomForestClassifier(n_estimators=150, random_state=0).fit(Xtr, ytr)
    acc_vaz.append(clf.score(Xte, yte))

acc_grp, folds = [], []
for k, (tr, te) in enumerate(GroupKFold(n_splits=5).split(X, y, groups=ensaio)):
    if len(set(y[te])) < 2:
        continue
    a_ = RandomForestClassifier(n_estimators=150, random_state=0).fit(X[tr], y[tr]).score(X[te], y[te])
    acc_grp.append(a_)
    folds.append({"fold": k, "acuracia": a_})

write(pd.DataFrame([
    {"estrategia": "Split aleatório\npor janela", "ordem": 1, "tipo": "vazamento",
     "media": np.mean(acc_vaz), "desvio": np.std(acc_vaz)},
    {"estrategia": "Split por ensaio\n(GroupKFold)", "ordem": 2, "tipo": "correto",
     "media": np.mean(acc_grp), "desvio": np.std(acc_grp)},
]), "fig2c_split.csv")
write(pd.DataFrame(folds), "fig2c_folds.csv")
pd.DataFrame({"baseline": [max(y.mean(), 1 - y.mean())]}).to_csv(OUT / "fig2c_baseline.csv", index=False)

# --- Isolation Forest -------------------------------------------------------
sadios_c, defeitos_c = gerar_ensaios(0.0, 200), gerar_ensaios(2.0, 300)
Xc, yc = [], []
for r, x in enumerate(sadios_c + defeitos_c):
    for w in janelas(x, FS_REF):
        Xc.append(extrair_features(w, FS_REF))
        yc.append(0 if r < N_ENSAIOS else 1)
Xc, yc = np.array(Xc), np.array(yc)
sc = StandardScaler().fit(Xc[yc == 0])
Xn = sc.transform(Xc)

rows = []
for cont in [0.5, 0.2, 0.1, 0.01, "auto"]:
    iso = IsolationForest(contamination=cont, n_estimators=200, random_state=0).fit(Xn[yc == 0])
    rows.append({
        "contamination": str(cont),
        "falso_alarme": (iso.predict(Xn[yc == 0]) == -1).mean(),
        "deteccao": (iso.predict(Xn[yc == 1]) == -1).mean(),
        "is_default": cont == "auto",
    })
write(pd.DataFrame(rows), "fig2d_contamination.csv")


def auc_e_roc(fs_alvo):
    Xb, yb = [], []
    for r, x in enumerate(sadios_i + defeitos_i):
        xx = x if fs_alvo >= FS_REF else signal.decimate(x, int(FS_REF / fs_alvo),
                                                         ftype="fir", zero_phase=True)
        for w in janelas(xx, fs_alvo):
            Xb.append(extrair_features(w, fs_alvo))
            yb.append(0 if r < N_ENSAIOS else 1)
    Xb, yb = np.array(Xb), np.array(yb)
    s_ = StandardScaler().fit(Xb[yb == 0])
    m = IsolationForest(contamination="auto", n_estimators=200, random_state=0).fit(s_.transform(Xb[yb == 0]))
    sc_ = -m.score_samples(s_.transform(Xb))
    fpr, tpr, _ = roc_curve(yb, sc_)
    # pAUC (FPR <= 0,1) segue o protocolo do DCASE2020 Task 2: a AUC global não
    # caracteriza o ponto de operação, a parcial sim
    return (roc_auc_score(yb, sc_), roc_auc_score(yb, sc_, max_fpr=0.10), fpr, tpr)


rows = []
for fs_alvo, lab in [(FS_REF, "Sensor 20 kHz"), (FS_MPU, "MPU6050 1 kHz")]:
    auc, pauc, fpr, tpr = auc_e_roc(fs_alvo)
    rows.append(pd.DataFrame({"fpr": fpr, "tpr": tpr, "auc": auc, "pauc": pauc,
                              "banda": f"{lab}\nAUC {auc:.3f} · pAUC {pauc:.3f}",
                              "banda_curta": lab}))
    print(f"    {lab}: AUC {auc:.3f}  pAUC {pauc:.3f}")
write(pd.concat(rows), "fig2e_roc.csv")

print(f"\nCSVs em {OUT}")
