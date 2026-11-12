"""Análises posteriores AP3 a AP6, exatamente como em docs/monografia/registro/registro_v4.md.

AP3: falso alarme de H1 (calandra e guilhotina) e de H4 (base pública) com as sementes 0 a 99 (AP3a) e com o treino
     reamostrado por blocos, refazendo limiar e modelo (AP3b).
AP4: intervalo da menor mudança detectável (MMD) de H2 por reamostragem em blocos.
AP5: MMD de d1 com o sensor em repouso e razão entre a MMD de H2 e essa MMD.
AP6: escore do Isolation Forest em pontos fora da faixa do treino, comparado ao limiar, e descrição da injeção de H3.

Usa as funções de analise_registrada.py e analise_posterior.py, sem alterá-las. Os descritores de H4 são os gravados
por experiments/fraunhofer/analise_h4.py, sem recálculo a partir dos CSV da base. Antes do cálculo, confere o SHA-256
dos dados e dos registros v1 a v4 e reproduz os números registrados que cada análise retoma.

Grava experiments/campo/analise_posterior_v4/ (ap3_sementes.csv, ap3_treino.csv, ap4.csv, ap5.csv, ap6_pontos.csv,
ap6_injecao.csv, ambiente.json) e docs/monografia/latex/values/posterior_v4_values.tex.

Uso, a partir de kaelix-firmware/:
  taskpolicy -b uv run --no-project --python 3.12 --with numpy==2.5.2 --with scipy==1.18.0 \
      --with scikit-learn==1.9.0 python experiments/campo/analise_posterior_v4.py
"""
import csv
import hashlib
import json
import platform
import time

import numpy as np
import scipy
import sklearn

import analise_posterior as ap
import analise_registrada as ar

SAIDA = ar.RAIZ / "experiments" / "campo" / "analise_posterior_v4"
VALORES = ar.RAIZ / "docs" / "monografia" / "latex" / "values" / "posterior_v4_values.tex"
REGISTRO = ar.RAIZ / "docs" / "monografia" / "registro"
H4_DIR = ar.RAIZ / "experiments" / "fraunhofer" / "analise_registrada"
DESCRITIVOS = ar.RAIZ / "docs" / "monografia" / "latex" / "values" / "descritivos_values.tex"
SHA_REGISTROS = {
    "registro_v1.md": "fd0afc8941d16b3a54405489172938302b7687f25b8596e17cbd719b0013e39d",
    "registro_v2.md": "3246d219c3e799d4639cea0f4f04eec12763113009e49879563753ad60482004",
    "registro_v3.md": "9197884e633b87439c03ea3d56f5f129ee150db04a90db4b399e9638a8d054f8",
    "registro_v4.md": "d4310d7b6685cea42f3eecdcf930ba1d29feee0e7a489322d47bd27a4cf72844",
}
SEMENTES = range(100)
REPLICAS_TREINO = 1000
REPLICAS_MMD = 2000
NIVEIS = ("Zero", "Um", "Dois", "Tres", "Quatro")
ENSAIOS_H2 = {"0": "DobradeiraUm", "1": "GuilhotinaUm", "6": "GuilhotinaDois", "3": "CalandraUm", "5": "CalandraDois",
              "4": "CompressorUm"}
CRITERIO_H2 = ("0", "3", "4", "5", "6")
NOMES_D = ("d1", "d2", "d3", "d4", "d5", "d6")
PLANOS = (("Dobradeira", "0", None), ("Guilhotina", "1", "6"), ("Calandra", "3", "5"), ("Compressor", "4", None))


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def conferir_registros():
    ar.conferir_hashes()
    for nome, esperado in SHA_REGISTROS.items():
        if sha(REGISTRO / nome) != esperado:
            raise SystemExit(f"SHA-256 diferente do registrado em {nome}")


def escrever(nome, linhas):
    with open(SAIDA / nome, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0]))
        w.writeheader()
        w.writerows(linhas)


def pct(x, casas=1):
    return ar.br(100 * x, casas)


# ---------- reamostragem por blocos de cinco janelas consecutivas ----------

def blocos(n):
    return [list(range(i, min(i + 5, n))) for i in range(0, n, 5)]


def reamostrar(n, rng):
    """Índices e bloco de origem de uma réplica, com a regra de ar.bootstrap_fracao (sorteio, extensão, corte)."""
    bl = blocos(n)
    idx, ids = [], []
    while len(idx) < n:
        b = int(rng.integers(len(bl)))
        idx.extend(bl[b])
        ids.extend([b] * len(bl[b]))
    return np.array(idx[:n]), np.array(ids[:n])


def limiar_grupos(Xtr, ids, semente):
    """Limiar com grupos de validação formados pelos blocos originais distintos (registro v4, AP3b, passo 2)."""
    distintos = np.unique(ids)
    if len(distintos) < 2:
        return None, None
    grupos = np.array_split(distintos, 5) if len(distintos) >= 5 else [np.array([d]) for d in distintos]
    fora = np.empty(len(Xtr))
    for g in grupos:
        m = np.isin(ids, g)
        fora[m] = ar.Floresta(semente).ajustar(Xtr[~m]).escore(Xtr[m])
    return float(np.quantile(fora, 1 - ar.ALFA)), ar.Floresta(semente).ajustar(Xtr)


def mmd(x):
    return float(np.quantile(x, 0.95) - np.median(x))


def intervalo_mmd(x, replicas=REPLICAS_MMD):
    rng = np.random.default_rng(0)
    est = np.array([mmd(x[reamostrar(len(x), rng)[0]]) for _ in range(replicas)])
    return float(np.percentile(est, 2.5)), float(np.percentile(est, 97.5)), est


# ---------- dados ----------

def dados_h1(janelas):
    de = lambda e: [j for j in janelas if j["ensaio"] == e]
    return {"Calandra": (ar.matriz([j["d"] for j in de("3")]), ar.matriz([j["d"] for j in de("5")])),
            "Guilhotina": (ar.matriz([j["d"] for j in de("1")]), ar.matriz([j["d"] for j in de("6")]))}


def dados_h4():
    por_arquivo = {}
    for r in csv.DictReader(open(H4_DIR / "janelas.csv", encoding="utf-8")):
        por_arquivo.setdefault(r["arquivo"], []).append({k: float(r[f"{k}_principal"]) for k in NOMES_D})
    Xtr = ar.matriz(por_arquivo["0D.csv"])
    testes = {L: ar.matriz(por_arquivo[f"{L}E.csv"]) for L in range(5)}
    return Xtr, testes


def veredito_h1(res):
    if all(r["fracao"] <= 0.10 and r["ic_sup"] <= 0.20 for r in res):
        return "corroborada"
    if any(r["fracao"] > 0.20 for r in res):
        return "refutada"
    return "indeterminada"


def veredito_h4(fa, ic_sup, niveis):
    if fa <= 0.10 and ic_sup <= 0.20 and all(x >= 0.5 for x in niveis):
        return "corroborada"
    if fa > 0.20 or any(x < 0.5 for x in niveis):
        return "refutada"
    return "indeterminada"


# ---------- AP3 ----------

def ap3(janelas, v, amb):
    h1 = dados_h1(janelas)
    Xtr4, testes4 = dados_h4()
    reg_h1 = {r["maquina"]: r for r in csv.DictReader(open(ar.SAIDA / "h1.csv", encoding="utf-8"))
              if r["detector"] == "Isolation Forest" and r["sentido"] == "1 para 2"}
    reg_h4 = {int(r["nivel"]): r for r in csv.DictReader(open(H4_DIR / "h4.csv", encoding="utf-8"))
              if r["variante"] == "principal" and r["detector"] == "Isolation Forest" and r["semente"] == "0"}

    linhas = []
    por_semente_h1 = {m: [] for m in h1}
    por_semente_h4 = []
    for s in SEMENTES:
        res_h1 = []
        for maq, (Xtr, Xte) in h1.items():
            thr, mod = ar.limiar(lambda s=s: ar.Floresta(s), Xtr)
            marc = (mod.escore(Xte) > thr).astype(float)
            lo, hi = ar.bootstrap_fracao(list(marc))
            r = {"caso": f"H1 {maq}", "teste": "rodada 2", "semente": s, "limiar": thr, "fracao": float(marc.mean()),
                 "ic_inf": lo, "ic_sup": hi}
            if s == 0:
                reg = reg_h1[maq]
                if abs(thr - float(reg["limiar"])) > 1e-12 or abs(r["fracao"] - float(reg["fracao"])) > 1e-12 \
                        or abs(hi - float(reg["ic_sup"])) > 1e-12:
                    raise SystemExit(f"semente 0 não reproduz H1 em {maq}")
            linhas.append(r)
            res_h1.append(r)
            por_semente_h1[maq].append(r)
        thr, mod = ar.limiar(lambda s=s: ar.Floresta(s), Xtr4)
        res4 = {}
        for L, X in testes4.items():
            marc = (mod.escore(X) > thr).astype(float)
            lo, hi = ar.bootstrap_fracao(list(marc))
            res4[L] = {"caso": "H4", "teste": f"{L}E", "semente": s, "limiar": thr, "fracao": float(marc.mean()),
                       "ic_inf": lo, "ic_sup": hi}
            if s == 0:
                reg = reg_h4[L]
                if abs(thr - float(reg["limiar"])) > 1e-12 or abs(res4[L]["fracao"] - float(reg["fracao"])) > 1e-12:
                    raise SystemExit(f"semente 0 não reproduz H4 no nível {L}")
            linhas.append(res4[L])
        por_semente_h4.append({"semente": s, "res": res4, "h1": veredito_h1(res_h1),
                               "h4": veredito_h4(res4[0]["fracao"], res4[0]["ic_sup"],
                                                 [res4[L]["fracao"] for L in range(1, 5)])})
        if s % 10 == 9:
            print(f"AP3a: semente {s}", flush=True)
    escrever("ap3_sementes.csv", linhas)

    def resumo(fr, prefixo):
        fr = np.array(fr)
        v[f"{prefixo}Med"] = pct(np.median(fr))
        v[f"{prefixo}Min"] = pct(fr.min())
        v[f"{prefixo}Max"] = pct(fr.max())
        v[f"{prefixo}PInf"] = pct(np.percentile(fr, 2.5))
        v[f"{prefixo}PSup"] = pct(np.percentile(fr, 97.5))
        v[f"{prefixo}AteDez"] = str(int((fr <= 0.10).sum()))
        v[f"{prefixo}AcimaVinte"] = str(int((fr > 0.20).sum()))

    for maq, rs in por_semente_h1.items():
        resumo([r["fracao"] for r in rs], f"apTresSemente{maq}")
    for L in range(5):
        resumo([p["res"][L]["fracao"] for p in por_semente_h4], f"apTresSementeNivel{NIVEIS[L]}")
    v["apTresSementeNiveisCinquenta"] = str(sum(all(p["res"][L]["fracao"] >= 0.5 for L in range(1, 5))
                                                for p in por_semente_h4))
    for hip, chave in (("Um", "h1"), ("Quatro", "h4")):
        for ver, nome in (("corroborada", "Corroborada"), ("refutada", "Refutada"), ("indeterminada", "Indeterminada")):
            v[f"apTresVeredito{hip}{nome}"] = str(sum(p[chave] == ver for p in por_semente_h4))
    v["apTresSementes"] = str(len(SEMENTES))

    # AP3b: treino reamostrado, limiar e modelo refeitos, teste reamostrado.
    rng = np.random.default_rng(0)
    linhas_b, descartes = [], {"Calandra": 0, "H4": 0}
    casos = (("Calandra", h1["Calandra"][0], {"rodada 2": h1["Calandra"][1]}),
             ("H4", Xtr4, {f"{L}E": testes4[L] for L in range(5)}))
    resultado_b = {}
    for nome, Xtr, testes in casos:
        fr = {t: [] for t in testes}
        for r in range(REPLICAS_TREINO):
            idx, ids = reamostrar(len(Xtr), rng)
            thr, mod = limiar_grupos(Xtr[idx], ids, r)
            amostras = {t: reamostrar(len(X), rng)[0] for t, X in testes.items()}
            if thr is None:
                descartes[nome] += 1
                continue
            for t, X in testes.items():
                marc = (mod.escore(X) > thr).astype(float)
                f = float(marc[amostras[t]].mean())
                fr[t].append(f)
                linhas_b.append({"caso": nome, "teste": t, "replica": r, "limiar": thr, "fracao": f})
            if r % 100 == 99:
                print(f"AP3b {nome}: réplica {r}", flush=True)
        resultado_b[nome] = {t: (float(np.percentile(x, 2.5)), float(np.percentile(x, 97.5)), float(np.median(x)))
                             for t, x in fr.items()}
    escrever("ap3_treino.csv", linhas_b)
    lo, hi, med = resultado_b["Calandra"]["rodada 2"]
    v["apTresTreinoInfCalandra"], v["apTresTreinoSupCalandra"], v["apTresTreinoMedCalandra"] = pct(lo), pct(hi), pct(med)
    for L in range(5):
        lo, hi, med = resultado_b["H4"][f"{L}E"]
        v[f"apTresTreinoInfNivel{NIVEIS[L]}"] = pct(lo)
        v[f"apTresTreinoSupNivel{NIVEIS[L]}"] = pct(hi)
        v[f"apTresTreinoMedNivel{NIVEIS[L]}"] = pct(med)
    v["apTresDescartesCalandra"] = str(descartes["Calandra"])
    v["apTresDescartesQuatro"] = str(descartes["H4"])
    v["apTresReplicas"] = f"\\num{{{REPLICAS_TREINO}}}"
    amb["AP3"] = {"descartes_um_bloco_distinto": descartes, "treino": resultado_b}


# ---------- AP4 ----------

def ap4(janelas, v, amb):
    h2 = {r["ensaio"]: r for r in csv.DictReader(open(ar.SAIDA / "h2.csv", encoding="utf-8"))}
    linhas, d1_por_ensaio = [], {}
    for e, nome in ENSAIOS_H2.items():
        js = [j for j in janelas if j["ensaio"] == e]
        if [j["seq"] for j in sorted(js, key=lambda j: (j["hora"], j["seq"]))] != [j["seq"] for j in js]:
            raise SystemExit(f"janelas do ensaio {e} fora da ordem de tempo")
        d1 = np.array([j["d"]["d1"] for j in js])
        d1_por_ensaio[e] = d1
        m = mmd(d1)
        if abs(m - float(h2[e]["mmd_mm_s"])) > 1e-12:
            raise SystemExit(f"MMD não reproduz H2 no ensaio {e}")
        lo, hi, est = intervalo_mmd(d1)
        acima = float((est >= ar.CRITERIO_MM_S).mean())
        linhas.append({"ensaio": e, "nome": nome, "n": len(d1), "mmd_mm_s": m, "ic_inf_mm_s": lo, "ic_sup_mm_s": hi,
                       "fracao_replicas_acima_0_7": acima, "no_criterio": e in CRITERIO_H2})
        v[f"apQuatroInf{nome}"] = ar.br(lo, 2)
        v[f"apQuatroSup{nome}"] = ar.br(hi, 2)
        v[f"apQuatroAcima{nome}"] = pct(acima, 0)
    escrever("ap4.csv", linhas)
    return d1_por_ensaio


# ---------- AP5 ----------

def vel_eixos(a_g, fs):
    """Velocidade eficaz de 10 a 184 Hz em cada eixo (mm/s), com a fórmula de ar.descritores."""
    n = a_g.shape[0]
    x = a_g - a_g.mean(axis=0)
    X = np.fft.rfft(x * ar.G, axis=0)
    f = np.fft.rfftfreq(n, 1 / fs)
    b = (f >= ar.BANDA[0]) & (f <= ar.BANDA[1])
    V = X[b] / (2j * np.pi * f[b, None])
    return np.sqrt(2.0 * (np.abs(V) ** 2).sum(axis=0)) / n * 1000.0


def ap5(v, amb):
    meta = list(csv.DictReader(open(ar.DADOS / "repouso.csv", encoding="utf-8")))
    brutas = np.load(ar.DADOS / "repouso.npz")["amostras"]
    if sorted(range(len(meta)), key=lambda i: (meta[i]["recebida_utc"], int(meta[i]["device_sequence"]))) \
            != list(range(len(meta))):
        raise SystemExit("janelas em repouso fora da ordem de tempo")
    vel, vel_nominal = [], []
    for i, m in enumerate(meta):
        a_g = ar.para_g(brutas[i], int(m["accel_range"]))
        fs = float(m["sample_rate_hz"])
        ve = vel_eixos(a_g, fs)
        if i == 0 and abs(ve.max() - ar.descritores(a_g, fs, 30.0)["d1"]) > 1e-12:
            raise SystemExit("vel_eixos não reproduz d1 do registro v1")
        vel.append(ve)
        vel_nominal.append(vel_eixos(a_g, 1000.0))
    vel, vel_nominal = np.array(vel), np.array(vel_nominal)
    publicado = next(l for l in DESCRITIVOS.read_text(encoding="utf-8").splitlines() if "{\\ruidoVelocidade}" in l)
    if ar.br(float(np.median(vel_nominal.max(axis=1))), 2) not in publicado:
        raise SystemExit("a mediana de d1 em repouso não reproduz o valor publicado")
    series = {"d1": vel.max(axis=1), "d1_horizontal": vel[:, :2].max(axis=1)}
    linhas, mmd_rep = [], {}
    for nome, x in series.items():
        m = mmd(x)
        lo, hi, _ = intervalo_mmd(x)
        mmd_rep[nome] = m
        linhas.append({"serie": nome, "n": len(x), "mediana_mm_s": float(np.median(x)), "q95_mm_s": float(np.quantile(x, 0.95)),
                       "mmd_mm_s": m, "ic_inf_mm_s": lo, "ic_sup_mm_s": hi})
        sufixo = "" if nome == "d1" else "Horizontal"
        v[f"apCincoMediana{sufixo}"] = ar.br(float(np.median(x)), 3)
        v[f"apCincoMmd{sufixo}"] = ar.br(m, 3)
        v[f"apCincoMmdInf{sufixo}"] = ar.br(lo, 3)
        v[f"apCincoMmdSup{sufixo}"] = ar.br(hi, 3)
    v["apCincoJanelas"] = str(len(meta))
    h2 = {r["ensaio"]: float(r["mmd_mm_s"]) for r in csv.DictReader(open(ar.SAIDA / "h2.csv", encoding="utf-8"))}
    razoes = {"d1": [], "d1_horizontal": []}
    for e in CRITERIO_H2:
        for nome in razoes:
            r = h2[e] / mmd_rep[nome]
            razoes[nome].append(r)
            linhas.append({"serie": f"razao {nome}", "n": "", "mediana_mm_s": "", "q95_mm_s": "", "mmd_mm_s": r,
                           "ic_inf_mm_s": e, "ic_sup_mm_s": ENSAIOS_H2[e]})
        v[f"apCincoRazao{ENSAIOS_H2[e]}"] = ar.br(h2[e] / mmd_rep["d1"], 1)
    v["apCincoRazaoMin"], v["apCincoRazaoMax"] = ar.br(min(razoes["d1"]), 1), ar.br(max(razoes["d1"]), 1)
    v["apCincoRazaoHorizontalMin"] = ar.br(min(razoes["d1_horizontal"]), 1)
    v["apCincoRazaoHorizontalMax"] = ar.br(max(razoes["d1_horizontal"]), 1)
    escrever("ap5.csv", linhas)
    amb["AP5"] = {"repouso_csv_sha256": sha(ar.DADOS / "repouso.csv"), "repouso_npz_sha256": sha(ar.DADOS / "repouso.npz")}


# ---------- AP6 ----------

def pontos(Xtr, distancia=1.0):
    ref = np.median(Xtr, axis=0)
    mx, mn = Xtr.max(axis=0), Xtr.min(axis=0)
    rg = mx - mn
    acima = lambda j: mx[j] + distancia * rg[j]
    abaixo = lambda j: mn[j] - distancia * rg[j]
    saida = {"referência": ref.copy()}
    for j in range(6):
        p = ref.copy()
        p[j] = acima(j)
        saida[f"{NOMES_D[j]} acima"] = p
        p = ref.copy()
        p[j] = abaixo(j)
        saida[f"{NOMES_D[j]} abaixo"] = p
    p = ref.copy()
    for j in (0, 1, 4):
        p[j] = acima(j)
    saida["d1, d2 e d5 acima"] = p
    saida["todos acima"] = np.array([acima(j) for j in range(6)])
    return saida


def ap6(janelas, v, amb):
    reg_h3 = {r["maquina"]: r for r in csv.DictReader(open(ar.SAIDA / "h3_resumo.csv", encoding="utf-8"))
              if r["assinatura"] == "1x" and r["detector"] == "Isolation Forest" and r["semente"] == "0"}
    Xtr4, testes4 = dados_h4()
    modelos = []
    for maq, tr, te in PLANOS:
        jtr, jte = ap.divisao(janelas, maq, tr, te)
        modelos.append((maq, ar.matriz([j["d"] for j in jtr]), jtr, jte))
    modelos.append(("Quatro", Xtr4, None, None))
    linhas_p, linhas_i = [], []
    for maq, Xtr, jtr, jte in modelos:
        thr, mod = ar.limiar(lambda: ar.Floresta(0), Xtr)
        if jte is not None:
            f0 = float((mod.escore(ar.matriz([j["d"] for j in jte])) > thr).mean())
            if abs(f0 - float(reg_h3[maq]["fracao_A0"])) > 1e-12:
                raise SystemExit(f"modelo de H3 não reproduzido em {maq}")
        else:
            f0 = float((mod.escore(testes4[0]) > thr).mean())
            reg_h4 = next(r for r in csv.DictReader(open(H4_DIR / "h4.csv", encoding="utf-8"))
                          if r["variante"] == "principal" and r["detector"] == "Isolation Forest"
                          and r["semente"] == "0" and r["nivel"] == "0")
            if abs(f0 - float(reg_h4["fracao"])) > 1e-12:
                raise SystemExit("modelo de H4 não reproduzido")
        pts, pts2 = pontos(Xtr), pontos(Xtr, 2.0)
        acima_limiar = 0
        for nome, p in pts.items():
            s = float(mod.escore(p[None, :])[0])
            s2 = float(mod.escore(pts2[nome][None, :])[0])
            if nome != "referência" and abs(s - s2) > 1e-12:
                raise SystemExit(f"escore muda com a distância além da faixa em {maq}, {nome}")
            if nome.split()[0] in NOMES_D and nome.count(" ") == 1 and s > thr:
                acima_limiar += 1
            linhas_p.append({"modelo": maq, "ponto": nome, "escore": s, "limiar": thr, "acima_do_limiar": s > thr})
        esc = {r["ponto"]: r["escore"] for r in linhas_p if r["modelo"] == maq}
        v[f"apSeisLimiar{maq}"] = ar.br(thr, 3)
        v[f"apSeisReferencia{maq}"] = ar.br(esc["referência"], 3)
        v[f"apSeisDcinco{maq}"] = ar.br(esc["d5 acima"], 3)
        v[f"apSeisTres{maq}"] = ar.br(esc["d1, d2 e d5 acima"], 3)
        v[f"apSeisTodos{maq}"] = ar.br(esc["todos acima"], 3)
        v[f"apSeisUmMax{maq}"] = ar.br(max(esc[f"{d} {s}"] for d in NOMES_D for s in ("acima", "abaixo")), 3)
        v[f"apSeisPontosAcima{maq}"] = str(acima_limiar)
        v[f"apSeisTresAcima{maq}"] = "sim" if esc["d1, d2 e d5 acima"] > thr else "não"
        if jte is None:
            continue
        # Injeção de H3 (assinatura 1x, fase sorteada, semente 0).
        rng = np.random.default_rng(0)
        fases = rng.uniform(0, 2 * np.pi, len(jte))
        maximos = {d: max(j["d"][d] for j in jtr) for d in ("d1", "d2", "d5")}
        a_sat = None
        for A in ar.GRADE:
            ds = [ar.descritores(ar.injetar(j["a_g"], j["fs"], j["f_r"], A, fases[i], ar.RADIAIS[maq], 1, True),
                                 j["fs"], j["f_r"]) for i, j in enumerate(jte)]
            s = mod.escore(ar.matriz(ds))
            d5 = np.array([d["d5"] for d in ds])
            linha = {"maquina": maq, "A_v_mm_s": float(A), "mediana_d5_mm_s": float(np.median(d5)),
                     "max_d5_treino_mm_s": maximos["d5"], "mediana_escore": float(np.median(s)),
                     "max_escore": float(s.max()), "limiar": thr, "fracao": float((s > thr).mean())}
            for d in ("d1", "d2", "d5"):
                linha[f"janelas_{d}_acima_do_treino"] = int(sum(x[d] > maximos[d] for x in ds))
            linhas_i.append(linha)
            if a_sat is None and np.median(d5) > maximos["d5"]:
                a_sat = (float(A), float(np.median(s)))
        alto = linhas_i[-1]
        v[f"apSeisAsat{maq}"] = "não atingido" if a_sat is None else ar.br(a_sat[0], 2)
        v[f"apSeisEscoreSat{maq}"] = "" if a_sat is None else ar.br(a_sat[1], 3)
        v[f"apSeisEscoreAlto{maq}"] = ar.br(alto["mediana_escore"], 3)
        v[f"apSeisEscoreAltoMax{maq}"] = ar.br(alto["max_escore"], 3)
        v[f"apSeisJanelasDcincoAcima{maq}"] = str(alto["janelas_d5_acima_do_treino"])
        v[f"apSeisTeste{maq}"] = str(len(jte))
        v[f"apSeisTreino{maq}"] = str(len(jtr))
        print(f"AP6: {maq}", flush=True)
    escrever("ap6_pontos.csv", linhas_p)
    escrever("ap6_injecao.csv", linhas_i)


def main():
    t0 = time.time()
    conferir_registros()
    SAIDA.mkdir(parents=True, exist_ok=True)
    ensaios, janelas = ap.carregar_janelas()
    v, amb = {}, {}
    ap4(janelas, v, amb)
    ap5(v, amb)
    ap6(janelas, v, amb)
    ap3(janelas, v, amb)
    ambiente = {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__,
                "sklearn": sklearn.__version__, "registro": "registro_v4.md",
                "registro_sha256": SHA_REGISTROS["registro_v4.md"], "h4_janelas_sha256": sha(H4_DIR / "janelas.csv"),
                "segundos": round(time.time() - t0, 1), **amb}
    (SAIDA / "ambiente.json").write_text(json.dumps(ambiente, indent=2, ensure_ascii=False), encoding="utf-8")
    VALORES.write_text("% Gerado por experiments/campo/analise_posterior_v4.py; não editar à mão.\n"
                       + "\n".join(f"\\newcommand{{\\{k}}}{{{v[k]}}}" for k in sorted(v)) + "\n", encoding="utf-8")
    print("fim", round(time.time() - t0, 1), "s", flush=True)


if __name__ == "__main__":
    main()
