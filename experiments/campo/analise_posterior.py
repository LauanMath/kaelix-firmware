"""Análises posteriores AP1 e AP2, exatamente como em docs/monografia/registro/registro_v2.md.

AP1: assinatura 1x somada aos eixos radiais com fase relativa fixa (0°, 90° e 180°) em relação à 1x existente
em cada eixo, com máquinas, divisão, detector, limiar e grade de H3.
AP2: mediana móvel de d1 sobre k = 1 a 5 janelas consecutivas e menor mudança detectável MMD_k, nos ensaios com
ao menos 25 janelas.

Usa as funções de analise_registrada.py (descritores, rotação, detectores, limiar, reamostragem), sem alterá-las.
Antes do cálculo: confere o SHA-256 dos dados e dos registros v1 e v2; confere a injeção num cosseno sintético
(erro de até 2 %); reproduz a curva de H3 (fase sorteada) e a compara com h3_curvas.csv.

Grava experiments/campo/analise_posterior/ (ap1_curvas.csv, ap1_resumo.csv, ap1_base_radial.csv, ap2.csv,
ambiente.json) e docs/monografia/latex/values/posterior_values.tex.

Uso, a partir de kaelix-firmware/:
  taskpolicy -b uv run --no-project --python 3.12 --with numpy==2.5.2 --with scipy==1.18.0 \
      --with scikit-learn==1.9.0 python experiments/campo/analise_posterior.py
"""
import csv
import hashlib
import json
import platform

import numpy as np
import scipy
import scipy.stats
import sklearn

import analise_registrada as ar

SAIDA = ar.RAIZ / "experiments" / "campo" / "analise_posterior"
VALORES = ar.RAIZ / "docs" / "monografia" / "latex" / "values" / "posterior_values.tex"
REGISTRO = ar.RAIZ / "docs" / "monografia" / "registro"
SHA_REGISTROS = {
    "registro_v1.md": "fd0afc8941d16b3a54405489172938302b7687f25b8596e17cbd719b0013e39d",
    "registro_v2.md": "3246d219c3e799d4639cea0f4f04eec12763113009e49879563753ad60482004",
}
THETAS = (0, 90, 180)
NOME_THETA = {0: "Zero", 90: "Noventa", 180: "CentoOitenta"}
PREVISAO = ("Dobradeira", "Calandra", "Compressor")
ENSAIOS_AP2 = ("0", "3", "4", "5", "6")
NOME_ENSAIO = {"0": "DobradeiraUm", "3": "CalandraUm", "4": "CompressorUm", "5": "CalandraDois", "6": "GuilhotinaDois"}
NOME_K = {1: "Um", 2: "Dois", 3: "Tres", 4: "Quatro", 5: "Cinco"}
LETRA = "XYZ"


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def conferir_registros():
    ar.conferir_hashes()
    for nome, esperado in SHA_REGISTROS.items():
        if sha(REGISTRO / nome) != esperado:
            raise SystemExit(f"SHA-256 diferente do registrado em {nome}")


def fase_1x(a_g, fs, f_r, eixo):
    """Fase ψ da 1x do eixo, para x ≈ C cos(2π f_r t + ψ), com t = 0 na primeira amostra."""
    n = a_g.shape[0]
    w = np.hanning(n)
    x = a_g[:, eixo] - a_g[:, eixo].mean()
    X = np.fft.rfft(x * w, n=16 * n)
    fz = np.fft.rfftfreq(16 * n, 1 / fs)
    return float(np.angle(X[int(np.argmin(np.abs(fz - f_r)))]))


def injetar_fase(a_g, fs, f_r, A_v, theta, eixos, fases):
    n = a_g.shape[0]
    t = np.arange(n) / fs
    A_a_g = np.sqrt(2) * (A_v / 1000.0) * 2 * np.pi * f_r / ar.G
    y = a_g.copy()
    for e, psi in zip(eixos, fases):
        y[:, e] += A_a_g * np.cos(2 * np.pi * f_r * t + psi + np.radians(theta))
    return y


def ordem1_por_eixo(a_g, fs, f_r):
    """Amplitude eficaz da 1x em velocidade em cada eixo (mm/s), com a mesma leitura de d5."""
    n = a_g.shape[0]
    x = (a_g - a_g.mean(axis=0)) * ar.G
    w = np.hanning(n)
    Xw = np.fft.rfft(x * w[:, None], n=16 * n, axis=0)
    fz = np.fft.rfftfreq(16 * n, 1 / fs)
    i = int(np.argmin(np.abs(fz - f_r)))
    amp_pico = 2.0 * np.abs(Xw[i]) / w.sum()
    return amp_pico / (2 * np.pi * fz[i]) / np.sqrt(2) * 1000.0


def conferencia_sintetica():
    """Cosseno de 5 mm/s em dois eixos, fase sorteada; θ = 0° deve dar 7,8 mm/s, e θ = 180°, 2,2 mm/s."""
    fs, n, C, A = 1000.5, 512, 5.0, 2.8
    fz = np.fft.rfftfreq(16 * n, 1 / fs)
    f_r = float(fz[np.argmin(np.abs(fz - 29.9))])
    t = np.arange(n) / fs
    rng = np.random.default_rng(1)
    psi_real = rng.uniform(0, 2 * np.pi, 2)
    C_a_g = np.sqrt(2) * (C / 1000.0) * 2 * np.pi * f_r / ar.G
    resultado = {}
    for nome, desvio in (("na_grade", 0.0), ("fora_da_grade_0,05_Hz", 0.05)):
        a_g = np.zeros((n, 3))
        for k, e in enumerate((0, 2)):
            a_g[:, e] = C_a_g * np.cos(2 * np.pi * (f_r + desvio) * t + psi_real[k])
        fases = [fase_1x(a_g, fs, f_r, e) for e in (0, 2)]
        for theta, esperado in ((0, C + A), (180, C - A)):
            y = injetar_fase(a_g, fs, f_r, A, theta, (0, 2), fases)
            obtido = ordem1_por_eixo(y, fs, f_r)[[0, 2]]
            base = ordem1_por_eixo(a_g, fs, f_r)[[0, 2]]
            # o erro é medido sobre a variação da amplitude, que é o que a assinatura acrescenta
            erro = float(np.max(np.abs((obtido - base) - (esperado - C)) / A))
            resultado[f"{nome}_theta{theta}"] = {"esperado_mm_s": esperado, "obtido_mm_s": [float(v) for v in obtido],
                                                 "erro_relativo": erro}
    if max(r["erro_relativo"] for k, r in resultado.items() if k.startswith("na_grade")) > 0.02:
        raise SystemExit(f"conferência sintética falhou: {resultado}")
    return resultado


def carregar_janelas():
    ensaios, meta, brutas = ar.carregar()
    janelas = []
    for i, m in enumerate(meta):
        e = ensaios[m["ensaio"]]
        a_g = ar.para_g(brutas[i], int(m["accel_range"]))
        fs = float(m["sample_rate_hz"])
        busca = float(e["rotacao_busca_hz"]) if e["rotacao_busca_hz"] else None
        f_r = ar.rotacao(a_g, fs, busca) if busca else float("nan")
        janelas.append({"ensaio": m["ensaio"], "maquina": e["maquina"], "rodada": e["rodada"], "fs": fs, "f_r": f_r,
                        "a_g": a_g, "d": ar.descritores(a_g, fs, f_r) if busca else None,
                        "hora": m["recebida_utc"], "seq": int(m["device_sequence"])})
    return ensaios, janelas


def divisao(janelas, maq, tr, te):
    de = lambda e: [j for j in janelas if j["ensaio"] == e]
    if te is None:
        todas = de(tr)
        p1, p2 = np.array_split(np.arange(len(todas)), 2)
        return [todas[i] for i in p1], [todas[i] for i in p2]
    return de(tr), de(te)


def h3_gravada():
    linhas = csv.DictReader(open(ar.SAIDA / "h3_curvas.csv", encoding="utf-8"))
    return {(r["maquina"], float(r["A_v_mm_s"])): float(r["fracao"]) for r in linhas
            if r["assinatura"] == "1x" and r["detector"] == "Isolation Forest" and r["semente"] == "0"}


def escrever(nome, linhas):
    with open(SAIDA / nome, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0]))
        w.writeheader()
        w.writerows(linhas)


def main():
    conferir_registros()
    SAIDA.mkdir(parents=True, exist_ok=True)
    sintetica = conferencia_sintetica()
    ensaios, janelas = carregar_janelas()
    v = {}

    # AP1
    gravada = h3_gravada()
    curvas, resumo, base_radial, reproducao = [], [], [], {}
    planos = (("Dobradeira", "0", None), ("Guilhotina", "1", "6"), ("Calandra", "3", "5"), ("Compressor", "4", None))
    a28 = int(np.argmin(np.abs(ar.GRADE - 2.8)))
    for maq, tr, te in planos:
        jtr, jte = divisao(janelas, maq, tr, te)
        Xtr = ar.matriz([j["d"] for j in jtr])
        eixos = ar.RADIAIS[maq]
        thr, mod = ar.limiar(lambda: ar.Floresta(0), Xtr)
        thr_mad, mod_mad = ar.limiar(ar.Mad, Xtr)

        # reprodução de H3 (fase sorteada, como em analise_registrada.py)
        rng = np.random.default_rng(0)
        sorteadas = rng.uniform(0, 2 * np.pi, len(jte))
        f_h3 = []
        for A in ar.GRADE:
            ds = [ar.descritores(ar.injetar(j["a_g"], j["fs"], j["f_r"], A, sorteadas[i], eixos, 1, True),
                                 j["fs"], j["f_r"]) for i, j in enumerate(jte)]
            f_h3.append(float((mod.escore(ar.matriz(ds)) > thr).mean()))
        dif = max(abs(f - gravada[(maq, float(A))]) for A, f in zip(ar.GRADE, f_h3))
        reproducao[maq] = dif
        if dif > 1e-12:
            raise SystemExit(f"H3 não reproduzida em {maq}: diferença {dif}")

        # 1x de base por eixo radial, nas janelas de teste limpas
        uns = np.array([ordem1_por_eixo(j["a_g"], j["fs"], j["f_r"]) for j in jte])
        for e in eixos:
            base_radial.append({"maquina": maq, "eixo": LETRA[e], "n": len(jte),
                                "mediana_1x_mm_s": float(np.median(uns[:, e])),
                                "q1_mm_s": float(np.quantile(uns[:, e], 0.25)),
                                "q3_mm_s": float(np.quantile(uns[:, e], 0.75))})
            v[f"apUmBase{maq}{LETRA[e]}"] = ar.br(float(np.median(uns[:, e])), 2)

        fases = [[fase_1x(j["a_g"], j["fs"], j["f_r"], e) for e in eixos] for j in jte]
        d5_limpo = np.array([j["d"]["d5"] for j in jte])
        for theta in THETAS:
            f_if, f_mad, var_d5 = [], [], []
            for A in ar.GRADE:
                ds = [ar.descritores(injetar_fase(j["a_g"], j["fs"], j["f_r"], A, theta, eixos, fases[i]),
                                     j["fs"], j["f_r"]) for i, j in enumerate(jte)]
                X = ar.matriz(ds)
                fi = float((mod.escore(X) > thr).mean())
                fm = float((mod_mad.escore(X) > thr_mad).mean())
                dd5 = float(np.mean(np.array([d["d5"] for d in ds]) - d5_limpo))
                f_if.append(fi)
                f_mad.append(fm)
                var_d5.append(dd5)
                curvas.append({"maquina": maq, "theta_graus": theta, "A_v_mm_s": float(A), "fracao_if": fi,
                               "fracao_mad": fm, "fracao_h3_sorteada": f_h3[len(f_if) - 1],
                               "variacao_media_d5_mm_s": dd5})
            f_if, f_mad = np.array(f_if), np.array(f_mad)
            rho = scipy.stats.spearmanr(ar.GRADE, f_if).correlation if f_if.std() > 0 else float("nan")
            resumo.append({"maquina": maq, "theta_graus": theta, "n_treino": len(jtr), "n_teste": len(jte),
                           "fracao_A0": float(f_if[0]), "fracao_2_8": float(f_if[a28]),
                           "fracao_2_8_h3": f_h3[a28], "A50_mm_s": ar.a50(ar.GRADE, f_if),
                           "A50_mad_mm_s": ar.a50(ar.GRADE, f_mad), "spearman": float(rho)})
            v[f"apUmFracao{NOME_THETA[theta]}{maq}"] = ar.br(100 * float(f_if[a28]), 1)
            a = ar.a50(ar.GRADE, f_if)
            v[f"apUmAcinquenta{NOME_THETA[theta]}{maq}"] = "não atingido" if np.isnan(a) else ar.br(a, 2)
            # detector secundário e variação média de d5 em 2,8 mm/s, para o texto (descritivos do registro v2)
            v[f"apUmMadFracao{NOME_THETA[theta]}{maq}"] = ar.br(100 * float(f_mad[a28]), 1)
            am = ar.a50(ar.GRADE, f_mad)
            v[f"apUmMadAcinquenta{NOME_THETA[theta]}{maq}"] = "não atingido" if np.isnan(am) else ar.br(am, 2)
            v[f"apUmVariacaoDcinco{NOME_THETA[theta]}{maq}"] = ar.br(var_d5[a28], 2)
        v[f"apUmFracaoSorteada{maq}"] = ar.br(100 * f_h3[a28], 1)
        v[f"apUmFracaoSemAssinatura{maq}"] = ar.br(100 * float(f_if[0]), 1)
        v[f"apUmMadSemAssinatura{maq}"] = ar.br(100 * float(f_mad[0]), 1)
        v[f"apUmTeste{maq}"] = str(len(jte))
        v[f"apUmTreino{maq}"] = str(len(jtr))
    escrever("ap1_curvas.csv", curvas)
    escrever("ap1_resumo.csv", resumo)
    escrever("ap1_base_radial.csv", base_radial)
    zero = {r["maquina"]: r for r in resumo if r["theta_graus"] == 0}
    confirmada = all(zero[m]["fracao_2_8"] > zero[m]["fracao_2_8_h3"] for m in PREVISAO)
    v["apUmVeredito"] = "confirmada" if confirmada else "não confirmada"

    # AP2
    ap2 = []
    for e in ENSAIOS_AP2:
        js = [j for j in janelas if j["ensaio"] == e]
        ordenadas = sorted(js, key=lambda j: (j["hora"], j["seq"]))
        if [j["seq"] for j in ordenadas] != [j["seq"] for j in js]:
            raise SystemExit(f"janelas do ensaio {e} fora da ordem de tempo")
        d1 = np.array([j["d"]["d1"] for j in ordenadas])
        horas = np.array([np.datetime64(j["hora"].replace(" ", "T")) for j in ordenadas])
        intervalo = float(np.median(np.diff(horas).astype("timedelta64[s]").astype(float)))
        auto = float(np.corrcoef(d1[:-1], d1[1:])[0, 1])
        mmd1 = None
        kestrela = None
        for k in range(1, 6):
            med = np.array([np.median(d1[i:i + k]) for i in range(len(d1) - k + 1)])
            q95, m = float(np.quantile(med, 0.95)), float(np.median(med))
            mmd = q95 - m
            mmd1 = mmd if k == 1 else mmd1
            if kestrela is None and mmd < ar.CRITERIO_MM_S:
                kestrela = k
            ap2.append({"ensaio": e, "maquina": ensaios[e]["maquina"], "rodada": ensaios[e]["rodada"],
                        "n_janelas": len(d1), "intervalo_mediano_s": intervalo, "k": k, "n_medianas": len(med),
                        "mediana_mm_s": m, "q95_mm_s": q95, "mmd_mm_s": mmd, "razao_mmd1": mmd / mmd1,
                        "autocorrelacao_1": auto})
            v[f"apDoisMmd{NOME_ENSAIO[e]}{NOME_K[k]}"] = ar.br(mmd, 2)
        v[f"apDoisRazao{NOME_ENSAIO[e]}"] = ar.br(ap2[-1]["razao_mmd1"], 2)
        v[f"apDoisAutocorr{NOME_ENSAIO[e]}"] = ar.br(auto, 2)
        v[f"apDoisKestrela{NOME_ENSAIO[e]}"] = "não atingido" if kestrela is None else str(kestrela)
    # conferência: MMD_1 reproduz H2
    h2 = {r["ensaio"]: float(r["mmd_mm_s"]) for r in csv.DictReader(open(ar.SAIDA / "h2.csv", encoding="utf-8"))}
    dif_h2 = max(abs(r["mmd_mm_s"] - h2[r["ensaio"]]) for r in ap2 if r["k"] == 1)
    if dif_h2 > 1e-9:
        raise SystemExit(f"MMD_1 não reproduz H2: diferença {dif_h2}")
    escrever("ap2.csv", ap2)

    ambiente = {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__,
                "sklearn": sklearn.__version__, "registro": "registro_v2.md",
                "registro_sha256": SHA_REGISTROS["registro_v2.md"],
                "conferencia_sintetica": sintetica, "reproducao_h3_diferenca_maxima": reproducao,
                "reproducao_h2_diferenca_maxima": dif_h2, "AP1": v["apUmVeredito"]}
    (SAIDA / "ambiente.json").write_text(json.dumps(ambiente, indent=2, ensure_ascii=False), encoding="utf-8")
    VALORES.write_text("% Gerado por experiments/campo/analise_posterior.py; não editar à mão.\n"
                       + "\n".join(f"\\newcommand{{\\{k}}}{{{v[k]}}}" for k in sorted(v)) + "\n", encoding="utf-8")
    print(json.dumps({"AP1": v["apUmVeredito"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
