"""Avalia H1, H2 e H3 exatamente como em docs/monografia/registro/registro_v1.md.

Lê experiments/campo/dados/ (conferindo o SHA-256 registrado), calcula os descritores, os detectores e as três
hipóteses, e grava:
  experiments/campo/analise_registrada/   descritores.csv, h1.csv, h2.csv, h3_curvas.csv, h3_resumo.csv, ambiente.json
  docs/monografia/latex/values/hipoteses_values.tex   macros com os números usados no texto

Escolhas que o registro não fixava, decididas aqui antes de rodar e gravadas em ambiente.json:
  - taxa de amostragem de cada janela: a medida pelo transmissor (janelas.csv), e não a nominal de 1000 Hz;
  - reamostragem por blocos: blocos de cinco janelas consecutivas sem sobreposição, sorteados com reposição até
    completar o número de janelas do teste, gerador do numpy com semente 0;
  - divisão em metades (dobradeira e compressor): numpy.array_split em duas partes, a primeira de treino;
  - fase das assinaturas: um gerador com semente 0 por máquina, um sorteio por janela de teste, na ordem do tempo,
    reaproveitado em todas as amplitudes;
  - ordem 2x: valor do espectro na linha mais próxima de 2 f_r.

Uso, a partir de kaelix-firmware/:
  uv run --no-project --with numpy --with scipy --with scikit-learn python experiments/campo/analise_registrada.py
"""
import csv
import hashlib
import json
import pathlib
import platform

import numpy as np
import scipy
import scipy.stats
import sklearn
from sklearn.ensemble import IsolationForest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
DADOS = RAIZ / "experiments" / "campo" / "dados"
SAIDA = RAIZ / "experiments" / "campo" / "analise_registrada"
VALORES = RAIZ / "docs" / "monografia" / "latex" / "values" / "hipoteses_values.tex"

SHA = {
    "ensaios.csv": "eb0730509cd4dfa818c2fa2ff60f1dd9a3ada0da26b3c60a315c65d51aff5cd1",
    "leituras.csv": "929db12213a90f7ed03eecfb15dda2181ce9c5a8a01a5a71bc1d703fcdfe63f0",
    "janelas.csv": "cf8ba6dfdcbe637c426006ba07807e5833fcfbe8d9c5a243ac953ec5d81934f6",
    "janelas.npz": "2ebcf5b91bbdcb652dd2c22a5f83612ec72c6f12ef263a00f8829563921a45d2",
}
G = 9.80665
CONTAGENS_POR_G = {0: 16384, 1: 8192, 2: 4096, 3: 2048}
BANDA = (10.0, 184.0)
ALFA = 0.05
CRITERIO_MM_S = 0.7
GRADE = np.round(np.arange(0.0, 2.8 + 1e-9, 0.05), 2)
# Eixos: 0 = X, 1 = Y, 2 = Z. Variante 1 (Y axial) em guilhotina, calandra e compressor; dobradeira com X axial.
AXIAL = {"Dobradeira": 0, "Guilhotina": 1, "Calandra": 1, "Compressor": 1}
RADIAIS = {"Dobradeira": (1, 2), "Guilhotina": (0, 2), "Calandra": (0, 2), "Compressor": (0, 2)}


def conferir_hashes():
    for nome, esperado in SHA.items():
        obtido = hashlib.sha256((DADOS / nome).read_bytes()).hexdigest()
        if obtido != esperado:
            raise SystemExit(f"SHA-256 diferente do registrado em {nome}")


def carregar():
    ensaios = {r["ensaio"]: r for r in csv.DictReader(open(DADOS / "ensaios.csv", encoding="utf-8"))}
    meta = list(csv.DictReader(open(DADOS / "janelas.csv", encoding="utf-8")))
    brutas = np.load(DADOS / "janelas.npz")["amostras"]
    return ensaios, meta, brutas


def para_g(bruta, faixa):
    return bruta[:, :3].astype(float) / CONTAGENS_POR_G[faixa]


def rotacao(a_g, fs, busca):
    n = a_g.shape[0]
    w = np.hanning(n)
    x = a_g - a_g.mean(axis=0)
    espectro = np.abs(np.fft.rfft(x * w[:, None], n=16 * n, axis=0)).sum(axis=1)
    f = np.fft.rfftfreq(16 * n, 1 / fs)
    faixa = (f >= busca - 2.5) & (f <= busca + 2.5)
    return float(f[faixa][np.argmax(espectro[faixa])])


def descritores(a_g, fs, f_r):
    """d1 a d6 do registro para uma janela em g (n, 3)."""
    n = a_g.shape[0]
    x = a_g - a_g.mean(axis=0)
    a_ms2 = x * G
    X = np.fft.rfft(a_ms2, axis=0)
    f = np.fft.rfftfreq(n, 1 / fs)
    banda = (f >= BANDA[0]) & (f <= BANDA[1])
    V = np.zeros_like(X)
    V[banda] = X[banda] / (2j * np.pi * f[banda, None])
    v_rms = np.sqrt(2.0 * (np.abs(V[banda]) ** 2).sum(axis=0)) / n * 1000.0  # mm/s, por eixo
    rms = np.sqrt((x ** 2).mean(axis=0))
    curt = (x ** 4).mean(axis=0) / (x ** 2).mean(axis=0) ** 2 - 3.0
    crista = np.abs(x).max(axis=0) / rms
    w = np.hanning(n)
    Xw = np.fft.rfft(a_ms2 * w[:, None], n=16 * n, axis=0)
    fz = np.fft.rfftfreq(16 * n, 1 / fs)
    amp_pico = 2.0 * np.abs(Xw) / w.sum()  # m/s^2, corrigida para a janela de Hann

    def ordem(k):
        i = int(np.argmin(np.abs(fz - k * f_r)))
        v_pico = amp_pico[i] / (2 * np.pi * fz[i])  # m/s
        return float(np.sqrt(((v_pico / np.sqrt(2) * 1000.0) ** 2).sum()))

    return {
        "d1": float(v_rms.max()),
        "d2": float(np.sqrt((rms ** 2).sum())),
        "d3": float(curt.max()),
        "d4": float(crista.max()),
        "d5": ordem(1),
        "d6": ordem(2),
    }


def matriz(ds):
    return np.array([[np.log10(d["d1"]), np.log10(d["d2"]), d["d3"], d["d4"], np.log10(d["d5"]), np.log10(d["d6"])]
                     for d in ds])


class Floresta:
    def __init__(self, semente=0):
        self.semente = semente

    def ajustar(self, X):
        self.m = IsolationForest(n_estimators=100, max_samples=min(256, len(X)), random_state=self.semente).fit(X)
        return self

    def escore(self, X):
        return -self.m.score_samples(X)


class Mad:
    def ajustar(self, X):
        self.med = np.median(X, axis=0)
        mad = np.median(np.abs(X - self.med), axis=0)
        self.esc = 1.4826 * np.where(mad > 0, mad, 1e-12)
        return self

    def escore(self, X):
        return (np.abs(X - self.med) / self.esc).max(axis=1)


def limiar(fabrica, X):
    blocos = np.array_split(np.arange(len(X)), 5)
    fora = np.empty(len(X))
    for b in blocos:
        resto = np.setdiff1d(np.arange(len(X)), b)
        fora[b] = fabrica().ajustar(X[resto]).escore(X[b])
    return float(np.quantile(fora, 1 - ALFA)), fabrica().ajustar(X)


def bootstrap_fracao(marcadas, reps=2000, semente=0):
    rng = np.random.default_rng(semente)
    blocos = [marcadas[i:i + 5] for i in range(0, len(marcadas), 5)]
    n = len(marcadas)
    est = []
    for _ in range(reps):
        amostra = []
        while len(amostra) < n:
            amostra.extend(blocos[rng.integers(len(blocos))])
        est.append(np.mean(amostra[:n]))
    return float(np.percentile(est, 2.5)), float(np.percentile(est, 97.5))


def injetar(a_g, fs, f_r, A_v, phi, eixos, k=1, quadratura=True):
    n = a_g.shape[0]
    t = np.arange(n) / fs
    A_a_g = np.sqrt(2) * (A_v / 1000.0) * 2 * np.pi * k * f_r / G
    y = a_g.copy()
    y[:, eixos[0]] += A_a_g * np.sin(2 * np.pi * k * f_r * t + phi)
    if quadratura and len(eixos) > 1:
        y[:, eixos[1]] += A_a_g * np.cos(2 * np.pi * k * f_r * t + phi)
    return y


def a50(grade, fracao):
    acima = np.nonzero(fracao >= 0.5)[0]
    if len(acima) == 0:
        return float("nan")
    i = acima[0]
    if i == 0:
        return 0.0
    x0, x1, y0, y1 = grade[i - 1], grade[i], fracao[i - 1], fracao[i]
    return float(x0 + (0.5 - y0) * (x1 - x0) / (y1 - y0))


def br(x, casas):
    return f"{x:.{casas}f}".replace(".", ",").replace("-", "\\textminus ")


def main():
    conferir_hashes()
    SAIDA.mkdir(parents=True, exist_ok=True)
    ensaios, meta, brutas = carregar()

    janelas = []  # por janela: ensaio, máquina, rodada, fs, f_r, g, descritores
    for i, m in enumerate(meta):
        e = ensaios[m["ensaio"]]
        a_g = para_g(brutas[i], int(m["accel_range"]))
        fs = float(m["sample_rate_hz"])
        busca = float(e["rotacao_busca_hz"]) if e["rotacao_busca_hz"] else None
        f_r = rotacao(a_g, fs, busca) if busca else float("nan")
        d = descritores(a_g, fs, f_r) if busca else None
        janelas.append({"ensaio": m["ensaio"], "maquina": e["maquina"], "rodada": e["rodada"], "fs": fs, "f_r": f_r,
                        "a_g": a_g, "d": d})

    with open(SAIDA / "descritores.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["ensaio", "maquina", "rodada", "fs_hz", "f_r_hz", "d1_mm_s", "d2_g", "d3", "d4", "d5_mm_s", "d6_mm_s"])
        for j in janelas:
            if j["d"]:
                w.writerow([j["ensaio"], j["maquina"], j["rodada"], j["fs"], round(j["f_r"], 4)]
                           + [round(j["d"][k], 6) for k in ("d1", "d2", "d3", "d4", "d5", "d6")])

    def de(ensaio):
        return [j for j in janelas if j["ensaio"] == ensaio]

    v = {}

    # H1
    h1 = []
    for maq, tr, te in (("Calandra", "3", "5"), ("Guilhotina", "1", "6")):
        Xtr, Xte = matriz([j["d"] for j in de(tr)]), matriz([j["d"] for j in de(te)])
        for nome, fab, principal in (("Isolation Forest", lambda: Floresta(0), True), ("MAD", Mad, False)):
            for sentido, A, B in (("1 para 2", Xtr, Xte), ("2 para 1", Xte, Xtr)):
                thr, mod = limiar(fab, A)
                marc = (mod.escore(B) > thr).astype(float)
                lo, hi = bootstrap_fracao(list(marc))
                h1.append({"maquina": maq, "detector": nome, "sentido": sentido, "n_treino": len(A), "n_teste": len(B),
                           "limiar": thr, "fracao": float(marc.mean()), "ic_inf": lo, "ic_sup": hi,
                           "principal": principal and sentido == "1 para 2"})
    with open(SAIDA / "h1.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(h1[0]))
        w.writeheader()
        w.writerows(h1)
    prin = [r for r in h1 if r["principal"]]
    if all(r["fracao"] <= 0.10 and r["ic_sup"] <= 0.20 for r in prin):
        h1_ver = "corroborada"
    elif any(r["fracao"] > 0.20 for r in prin):
        h1_ver = "refutada"
    else:
        h1_ver = "indeterminada"
    for r in prin:
        k = "Calandra" if r["maquina"] == "Calandra" else "Guilhotina"
        v[f"hUmFracao{k}"] = br(100 * r["fracao"], 1)
        v[f"hUmIcInf{k}"] = br(100 * r["ic_inf"], 1)
        v[f"hUmIcSup{k}"] = br(100 * r["ic_sup"], 1)
    v["hUmVeredito"] = h1_ver

    # H2
    h2 = []
    for e in ("0", "1", "3", "4", "5", "6"):
        d1 = np.array([j["d"]["d1"] for j in de(e)])
        q95, med = float(np.quantile(d1, 0.95)), float(np.median(d1))
        h2.append({"ensaio": e, "maquina": ensaios[e]["maquina"], "rodada": ensaios[e]["rodada"], "n": len(d1),
                   "mediana_mm_s": med, "q95_mm_s": q95, "mmd_mm_s": q95 - med, "mmd_rel_pct": 100 * (q95 - med) / med,
                   "no_criterio": len(d1) >= 25})
    with open(SAIDA / "h2.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(h2[0]))
        w.writeheader()
        w.writerows(h2)
    crit = [r for r in h2 if r["no_criterio"]]
    h2_ver = "corroborada" if all(r["mmd_mm_s"] < CRITERIO_MM_S for r in crit) else "refutada"
    v["hDoisVeredito"] = h2_ver
    v["hDoisMmdMin"] = br(min(r["mmd_mm_s"] for r in crit), 2)
    v["hDoisMmdMax"] = br(max(r["mmd_mm_s"] for r in crit), 2)

    # H3
    curvas, resumo = [], []
    planos = (("Dobradeira", "0", None), ("Guilhotina", "1", "6"), ("Calandra", "3", "5"), ("Compressor", "4", None))
    for maq, tr, te in planos:
        if te is None:
            todas = de(tr)
            p1, p2 = np.array_split(np.arange(len(todas)), 2)
            jtr, jte = [todas[i] for i in p1], [todas[i] for i in p2]
        else:
            jtr, jte = de(tr), de(te)
        Xtr = matriz([j["d"] for j in jtr])
        rng = np.random.default_rng(0)
        fases = rng.uniform(0, 2 * np.pi, len(jte))
        for assinatura, eixos, k, quad in (("1x", RADIAIS[maq], 1, True), ("2x", (AXIAL[maq],), 2, False)):
            detectores = [("Isolation Forest", s, (lambda s=s: Floresta(s))) for s in range(10)] if assinatura == "1x" \
                else [("Isolation Forest", 0, lambda: Floresta(0))]
            if assinatura == "1x":
                detectores.append(("MAD", 0, Mad))
            for nome, sem, fab in detectores:
                thr, mod = limiar(fab, Xtr)
                fr = []
                for A in GRADE:
                    ds = [descritores(injetar(j["a_g"], j["fs"], j["f_r"], A, fases[i], eixos, k, quad), j["fs"], j["f_r"])
                          for i, j in enumerate(jte)]
                    fr.append(float((mod.escore(matriz(ds)) > thr).mean()))
                fr = np.array(fr)
                rho = scipy.stats.spearmanr(GRADE, fr).correlation if fr.std() > 0 else float("nan")
                principal = assinatura == "1x" and nome == "Isolation Forest" and sem == 0
                for A, x in zip(GRADE, fr):
                    curvas.append({"maquina": maq, "assinatura": assinatura, "detector": nome, "semente": sem,
                                   "A_v_mm_s": float(A), "fracao": x})
                resumo.append({"maquina": maq, "assinatura": assinatura, "detector": nome, "semente": sem,
                               "n_treino": len(jtr), "n_teste": len(jte), "fracao_A0": float(fr[0]),
                               "A50_mm_s": a50(GRADE, fr), "spearman": float(rho), "principal": principal})
    for nome, linhas in (("h3_curvas.csv", curvas), ("h3_resumo.csv", resumo)):
        with open(SAIDA / nome, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(linhas[0]))
            w.writeheader()
            w.writerows(linhas)
    prin = [r for r in resumo if r["principal"]]
    ok = all(not np.isnan(r["A50_mm_s"]) and r["A50_mm_s"] < CRITERIO_MM_S and r["spearman"] >= 0.9 for r in prin)
    v["hTresVeredito"] = "corroborada" if ok else "refutada"
    for r in prin:
        v[f"hTresAcinquenta{r['maquina']}"] = "não atingido" if np.isnan(r["A50_mm_s"]) else br(r["A50_mm_s"], 2)
        v[f"hTresRho{r['maquina']}"] = br(r["spearman"], 2) if not np.isnan(r["spearman"]) else "indefinido"

    ambiente = {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__,
                "sklearn": sklearn.__version__, "registro": "registro_v1.md",
                "registro_sha256": hashlib.sha256((RAIZ / "docs/monografia/registro/registro_v1.md").read_bytes()).hexdigest(),
                "vereditos": {"H1": h1_ver, "H2": h2_ver, "H3": v["hTresVeredito"]}}
    (SAIDA / "ambiente.json").write_text(json.dumps(ambiente, indent=2, ensure_ascii=False), encoding="utf-8")
    VALORES.write_text("% Gerado por experiments/campo/analise_registrada.py; não editar à mão.\n"
                       + "\n".join(f"\\newcommand{{\\{k}}}{{{v[k]}}}" for k in sorted(v)) + "\n", encoding="utf-8")
    print(json.dumps(ambiente["vereditos"], ensure_ascii=False))


if __name__ == "__main__":
    main()
