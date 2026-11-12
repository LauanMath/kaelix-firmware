"""Avalia H4 exatamente como em docs/monografia/registro/registro_v2.md, na base de desbalanceamento da Fraunhofer,
com a fonte de dados de registro_v3.md.

Base: Mey, Neudeck, Schneider e Enge-Rosenblatt, Vibration Measurements on a Rotating Shaft at Different Unbalance
Strengths, Fraunhofer Fordatis, versão 151.3, DOI 10.24406/fordatis/65.3, CC BY 4.0. Os seis CSV usados (0D, 0E a
4E) são baixados por baixar_membros_v2.py para experiments/fraunhofer/dados/v2/.

Treino: janelas de 0D. Teste: 0E (falso alarme) e 1E a 4E (fração marcada). Janelas de 2.048 amostras (0,5 s), com
V_in constante, rotação média de 1750 a 1850 r/min e fora das duas primeiras janelas de cada degrau. Descritores e
detector de analise_registrada.py; d2, d3 e d4 com os coeficientes acima de 184 Hz anulados.

Grava experiments/fraunhofer/analise_registrada/ (janelas.csv, h4.csv, ambiente.json) e
docs/monografia/latex/values/h4_values.tex.

Uso, a partir de kaelix-firmware/:
  taskpolicy -b uv run --no-project --python 3.12 --with numpy==2.5.2 --with scipy==1.18.0 \
      --with scikit-learn==1.9.0 --with pandas python experiments/fraunhofer/analise_h4.py
"""
import csv
import hashlib
import json
import pathlib
import platform
import sys

import numpy as np
import pandas as pd
import scipy
import scipy.stats
import sklearn

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "experiments" / "campo"))
import analise_registrada as ar  # noqa: E402

DADOS = RAIZ / "experiments" / "fraunhofer" / "dados"
DADOS_V2 = DADOS / "v2"
REGISTRO = RAIZ / "docs" / "monografia" / "registro"
SAIDA = RAIZ / "experiments" / "fraunhofer" / "analise_registrada"
VALORES = RAIZ / "docs" / "monografia" / "latex" / "values" / "h4_values.tex"
SHA_V2 = "3246d219c3e799d4639cea0f4f04eec12763113009e49879563753ad60482004"
SHA_V3 = "9197884e633b87439c03ea3d56f5f129ee150db04a90db4b399e9638a8d054f8"
ARQUIVOS = ["0D.csv"] + [f"{L}E.csv" for L in range(5)]
LINHAS_CADERNO = {"0E.csv": 6_843_567, "4E.csv": 6_864_047}  # depois do descarte, cadernos dos autores
COLUNAS = ["V_in", "Measured_RPM", "Vibration_1", "Vibration_2", "Vibration_3"]
FS = 4096.0
N = 2048
DESCARTE = 50_000
FAIXA_RPM = (1750.0, 1850.0)
CORTE_HZ = 184.0
BANDA_COMPLETA = (10.0, 1000.0)
FATOR = {0: 0.0, 1: 45.9, 2: 60.7, 3: 75.5, 4: 152.1}  # mm·g
NOME_NIVEL = {0: "Zero", 1: "Um", 2: "Dois", 3: "Tres", 4: "Quatro"}


def sha_arquivo(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def conferir():
    """Registros v2 e v3, SHA-256 dos CSV gravado no download e linhas de 0E e 4E (registro_v3.md)."""
    if sha_arquivo(REGISTRO / "registro_v2.md") != SHA_V2:
        raise SystemExit("SHA-256 diferente do registrado em registro_v2.md")
    if sha_arquivo(REGISTRO / "registro_v3.md") != SHA_V3:
        raise SystemExit("SHA-256 diferente do registrado em registro_v3.md")
    linhas = (REGISTRO / "registro_v3_dados.sha256").read_text(encoding="utf-8").split("\n")
    esperado = {l.split("  ")[1]: l.split("  ")[0] for l in linhas if l.strip()}
    sha = {}
    for nome in ARQUIVOS:
        sha[nome] = sha_arquivo(DADOS_V2 / nome)
        if sha[nome] != esperado[nome]:
            raise SystemExit(f"SHA-256 de {nome} diferente do gravado no download")
    membros = json.loads((DADOS_V2 / "membros.json").read_text(encoding="utf-8"))["membros"]
    for nome, n in LINHAS_CADERNO.items():
        if membros[nome]["linhas_de_dados"] - DESCARTE != n:
            raise SystemExit(f"{nome}: número de linhas diferente do caderno dos autores; registrar e consultar o autor")
    return sha


def vel_rms(x, fs, banda):
    """Velocidade eficaz por eixo (mm/s), com a fórmula de analise_registrada.descritores."""
    n = x.shape[0]
    X = np.fft.rfft(x * ar.G, axis=0)
    f = np.fft.rfftfreq(n, 1 / fs)
    sel = (f >= banda[0]) & (f <= banda[1])
    V = X[sel] / (2j * np.pi * f[sel, None])
    return np.sqrt(2.0 * (np.abs(V) ** 2).sum(axis=0)) / n * 1000.0


def estatisticas(x):
    rms = np.sqrt((x ** 2).mean(axis=0))
    curt = (x ** 4).mean(axis=0) / (x ** 2).mean(axis=0) ** 2 - 3.0
    crista = np.abs(x).max(axis=0) / rms
    return float(np.sqrt((rms ** 2).sum())), float(curt.max()), float(crista.max())


def descritores_h4(x, f_r):
    """Principal (banda do Kaelix) e banda completa, para uma janela (n, canais) na unidade da coluna."""
    x = x - x.mean(axis=0)
    base = ar.descritores(x, FS, f_r)  # d1 de 10 a 184 Hz, d5 e d6 como no registro v1
    if abs(vel_rms(x, FS, ar.BANDA).max() - base["d1"]) > 1e-9 * max(base["d1"], 1e-30):
        raise SystemExit("vel_rms não reproduz d1 do registro v1")
    X = np.fft.rfft(x, axis=0)
    f = np.fft.rfftfreq(x.shape[0], 1 / FS)
    X[f > CORTE_HZ] = 0
    xb = np.fft.irfft(X, n=x.shape[0], axis=0)
    d2, d3, d4 = estatisticas(xb)
    principal = {"d1": base["d1"], "d2": d2, "d3": d3, "d4": d4, "d5": base["d5"], "d6": base["d6"]}
    completa = {"d1": float(vel_rms(x, FS, BANDA_COMPLETA).max()), "d2": base["d2"], "d3": base["d3"],
                "d4": base["d4"], "d5": base["d5"], "d6": base["d6"]}
    return principal, completa


def janelas_do_arquivo(nome):
    df = pd.read_csv(DADOS_V2 / nome)
    if list(df.columns) != COLUNAS:
        raise SystemExit(f"colunas inesperadas em {nome}: {list(df.columns)}")
    a = df.to_numpy(dtype=np.float64)[DESCARTE:]
    del df
    nj = len(a) // N
    W = a[: nj * N].reshape(nj, N, 5)
    v = W[:, :, 0]
    constante = v.max(axis=1) == v.min(axis=1)
    rpm = W[:, :, 1].mean(axis=1)
    pos = np.zeros(nj, dtype=int)
    for i in range(1, nj):
        if constante[i] and constante[i - 1] and v[i, 0] == v[i - 1, 0]:
            pos[i] = pos[i - 1] + 1
    entra = constante & (pos >= 2) & (rpm >= FAIXA_RPM[0]) & (rpm <= FAIXA_RPM[1])
    saida = []
    for i in np.nonzero(entra)[0]:
        x = W[i, :, 2:5].copy()
        f_r = ar.rotacao(x, FS, rpm[i] / 60.0)
        f_r1 = ar.rotacao(x[:, [0]], FS, rpm[i] / 60.0)
        p, c = descritores_h4(x, f_r)
        p1, _ = descritores_h4(x[:, [0]], f_r1)
        saida.append({"arquivo": nome, "janela": int(i), "v_in": float(v[i, 0]), "rpm": float(rpm[i]), "f_r": f_r,
                      "principal": p, "completa": c, "vib1": p1})
    return saida, {"linhas_depois_do_descarte": len(a), "janelas": nj, "janelas_aceitas": len(saida)}


def avaliar(Xtr, testes, fabrica):
    thr, mod = ar.limiar(fabrica, Xtr)
    res = {}
    for nivel, X in testes.items():
        marc = (mod.escore(X) > thr).astype(float)
        lo, hi = ar.bootstrap_fracao(list(marc))
        res[nivel] = {"n": len(X), "fracao": float(marc.mean()), "ic_inf": lo, "ic_sup": hi, "limiar": thr}
    return res


def main():
    sha_csv = conferir()
    SAIDA.mkdir(parents=True, exist_ok=True)
    jan, contagem = {}, {}
    for nome in ARQUIVOS:
        jan[nome], contagem[nome] = janelas_do_arquivo(nome)
        print(nome, contagem[nome], flush=True)

    with open(SAIDA / "janelas.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["arquivo", "janela", "v_in", "rpm", "f_r_hz"] + [f"{k}_{v}" for v in ("principal", "completa")
                                                                    for k in ("d1", "d2", "d3", "d4", "d5", "d6")])
        for nome, js in jan.items():
            for j in js:
                w.writerow([nome, j["janela"], j["v_in"], round(j["rpm"], 3), round(j["f_r"], 4)]
                           + [j[v][k] for v in ("principal", "completa") for k in ("d1", "d2", "d3", "d4", "d5", "d6")])

    def X(nome, variante):
        return ar.matriz([j[variante] for j in jan[nome]])

    linhas, v = [], {}
    variantes = [("principal", "Isolation Forest", s, (lambda s=s: ar.Floresta(s))) for s in range(10)]
    variantes += [("principal", "MAD", 0, ar.Mad), ("completa", "Isolation Forest", 0, lambda: ar.Floresta(0)),
                  ("vib1", "Isolation Forest", 0, lambda: ar.Floresta(0))]
    resultado_principal = None
    for variante, detector, semente, fab in variantes:
        res = avaliar(X("0D.csv", variante), {L: X(f"{L}E.csv", variante) for L in range(5)}, fab)
        fr = [res[L]["fracao"] for L in range(5)]
        rho = scipy.stats.spearmanr([FATOR[L] for L in range(5)], fr).correlation if np.std(fr) > 0 else float("nan")
        for L in range(5):
            linhas.append({"variante": variante, "detector": detector, "semente": semente, "nivel": L,
                           "fator_mm_g": FATOR[L], "n_treino": len(jan["0D.csv"]), **res[L], "spearman": rho})
        if variante == "principal" and detector == "Isolation Forest" and semente == 0:
            resultado_principal = (res, rho)
    with open(SAIDA / "h4.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0]))
        w.writeheader()
        w.writerows(linhas)

    res, rho = resultado_principal
    fa = res[0]
    niveis = [res[L]["fracao"] for L in range(1, 5)]
    if fa["fracao"] <= 0.10 and fa["ic_sup"] <= 0.20 and all(x >= 0.5 for x in niveis):
        veredito = "corroborada"
    elif fa["fracao"] > 0.20 or any(x < 0.5 for x in niveis):
        veredito = "refutada"
    else:
        veredito = "indeterminada"
    menor = next((L for L in range(1, 5) if res[L]["fracao"] >= 0.5), None)

    v["hQuatroVeredito"] = veredito
    v["hQuatroNTreino"] = str(len(jan["0D.csv"]))
    v["hQuatroMenorNivel"] = "nenhum" if menor is None else str(menor)
    v["hQuatroRho"] = ar.br(rho, 2) if not np.isnan(rho) else "indefinido"
    for L in range(5):
        k = NOME_NIVEL[L]
        v[f"hQuatroN{k}"] = str(res[L]["n"])
        v[f"hQuatroFracao{k}"] = ar.br(100 * res[L]["fracao"], 1)
        v[f"hQuatroIcInf{k}"] = ar.br(100 * res[L]["ic_inf"], 1)
        v[f"hQuatroIcSup{k}"] = ar.br(100 * res[L]["ic_sup"], 1)
        d5 = np.median([j["principal"]["d5"] for j in jan[f"{L}E.csv"]])
        v[f"hQuatroDcincoMediana{k}"] = f"{d5:.3g}".replace(".", ",")
    # Descritivo além do registrado: medianas de d1, d3, d4 e d5 por arquivo (treino = 0D) e faixa do falso
    # alarme entre as sementes 0 a 9, para a leitura do resultado.
    # casas fixas por descritor, coerentes dentro de cada tabela: d1 e d5 com três, d3 e d4 com duas
    for nome, k in [("0D.csv", "Treino")] + [(f"{L}E.csv", NOME_NIVEL[L]) for L in range(5)]:
        for d, nd, casas in (("d1", "Dum", 3), ("d3", "Dtres", 2), ("d4", "Dquatro", 2), ("d5", "Dcinco", 3)):
            v[f"hQuatro{nd}Mediana{k}"] = ar.br(float(np.median([j["principal"][d] for j in jan[nome]])), casas)
    fa_sementes = [r["fracao"] for r in linhas if r["variante"] == "principal" and r["detector"] == "Isolation Forest"
                   and r["nivel"] == 0]
    v["hQuatroFaSementeMin"] = ar.br(100 * min(fa_sementes), 1)
    v["hQuatroFaSementeMax"] = ar.br(100 * max(fa_sementes), 1)
    for variante, detector, nomev in (("completa", "Isolation Forest", "BandaCompleta"), ("vib1", "Isolation Forest", "VibUm"),
                                      ("principal", "MAD", "Mad")):
        for r in linhas:
            if r["variante"] == variante and r["detector"] == detector and r["semente"] == 0:
                v[f"hQuatroFracao{nomev}{NOME_NIVEL[r['nivel']]}"] = ar.br(100 * r["fracao"], 1)

    ambiente = {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__,
                "sklearn": sklearn.__version__, "pandas": pd.__version__, "registro": "registro_v2.md e registro_v3.md",
                "registro_v2_sha256": SHA_V2, "registro_v3_sha256": SHA_V3, "csv_sha256": sha_csv,
                "contagem": contagem,
                "veredito_H4": veredito, "menor_nivel_50": menor}
    (SAIDA / "ambiente.json").write_text(json.dumps(ambiente, indent=2, ensure_ascii=False), encoding="utf-8")
    VALORES.write_text("% Gerado por experiments/fraunhofer/analise_h4.py; não editar à mão.\n"
                       + "\n".join(f"\\newcommand{{\\{k}}}{{{v[k]}}}" for k in sorted(v)) + "\n", encoding="utf-8")
    print(json.dumps({"H4": veredito, "menor_nivel_50": menor}, ensure_ascii=False))


if __name__ == "__main__":
    main()
