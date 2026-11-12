"""Resultados descritivos da coleta em campo, fora das hipóteses registradas.

Calcula o ruído do sensor em repouso, a relação entre o sinal das máquinas e esse ruído, as rajadas completas por
nível de sinal, a rotação, as linhas do espectro (ordens diretas e rebatidas), a velocidade por eixo e a resposta do
detector a mudanças de condição. Usa os mesmos descritores e o mesmo detector de analise_registrada.py.

Grava experiments/campo/analise_descritiva/*.csv e docs/monografia/latex/values/descritivos_values.tex.

Uso, a partir de kaelix-firmware/:
  uv run --no-project --with numpy --with scipy --with scikit-learn python experiments/campo/analise_descritiva.py
"""
import csv
import pathlib
import statistics
import sys

import numpy as np
from scipy.signal import welch

AQUI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import analise_registrada as ar  # noqa: E402

DADOS = AQUI / "dados"
SAIDA = AQUI / "analise_descritiva"
VALORES = ar.RAIZ / "docs" / "monografia" / "latex" / "values" / "descritivos_values.tex"
NOME = {("Dobradeira", "1"): "DobradeiraUm", ("Guilhotina", "1"): "GuilhotinaUm", ("Guilhotina", "2"): "GuilhotinaDois",
        ("Calandra", "1"): "CalandraUm", ("Calandra", "2"): "CalandraDois", ("Compressor", "1"): "CompressorUm",
        ("Motor parado", "1"): "MotorParado"}
SINCRONA = {"Dobradeira": 30.0, "Guilhotina": 30.0, "Calandra": 30.0, "Compressor": 60.0}
# Início dos reinícios por queda de tensão da bateria, logo depois do período em repouso. O fim é
# calculado dos dados: a última rajada do primeiro ciclo depois de uma inicialização (número de sequência 1).
INICIO_REINICIOS = "15:00:00"
TOLERANCIA_HZ = 1.0  # distância máxima entre uma linha do espectro e a ordem a que ela é associada


def br(x, casas):
    return f"{x:.{casas}f}".replace(".", ",").replace("-", "\\textminus ")


def escrever(nome, linhas):
    with open(SAIDA / nome, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0]))
        w.writeheader()
        w.writerows(linhas)


def velocidade_por_eixo(a_g, fs):
    n = a_g.shape[0]
    X = np.fft.rfft((a_g - a_g.mean(axis=0)) * ar.G, axis=0)
    f = np.fft.rfftfreq(n, 1 / fs)
    banda = (f >= ar.BANDA[0]) & (f <= ar.BANDA[1])
    V = X[banda] / (2j * np.pi * f[banda, None])
    return np.sqrt(2.0 * (np.abs(V) ** 2).sum(axis=0)) / n * 1000.0


def main():
    SAIDA.mkdir(parents=True, exist_ok=True)
    ensaios, meta, brutas = ar.carregar()
    v = {}

    # Ruído em repouso.
    rep_meta = list(csv.DictReader(open(DADOS / "repouso.csv", encoding="utf-8")))
    rep = np.load(DADOS / "repouso.npz")["amostras"]
    A = np.stack([ar.para_g(rep[i], int(m["accel_range"])) for i, m in enumerate(rep_meta)])
    A = A - A.mean(axis=1, keepdims=True)
    f, P = welch(A, fs=1000.0, window="hann", nperseg=512, axis=1)
    Pm = P.mean(axis=0)
    with open(SAIDA / "psd_repouso.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["f_hz", "psd_x_g2_hz", "psd_y_g2_hz", "psd_z_g2_hz"])
        w.writerows([[f[i]] + list(Pm[i]) for i in range(len(f))])
    banda = (f >= 20) & (f <= 150)
    dens = np.sqrt(Pm[banda].mean(axis=0)) * 1e6
    rms_mg = np.median(np.sqrt((A ** 2).mean(axis=1)), axis=0) * 1e3
    vel_rep = np.array([velocidade_por_eixo(A[i] + 0.0, 1000.0) for i in range(len(A))])
    d1_rep = np.median(vel_rep.max(axis=1))
    d2_rep = np.median(np.sqrt((A ** 2).mean(axis=1).sum(axis=1)))
    escrever("ruido.csv", [{"eixo": e, "rms_mediano_mg": rms_mg[k], "densidade_20_150_ug_rhz": dens[k],
                            "velocidade_mediana_mm_s": float(np.median(vel_rep[:, k]))} for k, e in enumerate("XYZ")])
    for k, e in enumerate("XYZ"):
        v[f"ruidoDensidade{e}"] = br(dens[k], 0)
        v[f"ruidoRms{e}"] = br(rms_mg[k], 1)
    v["ruidoVelocidade"] = br(d1_rep, 2)
    v["ruidoRmsTotal"] = br(d2_rep * 1e3, 1)
    v["ruidoDatasheet"] = "400"
    # Menor mudança detectável de H2 (ensaios do critério) em múltiplos do ruído em repouso no descritor d1.
    h2 = list(csv.DictReader(open(ar.SAIDA / "h2.csv", encoding="utf-8")))
    razoes_mmd = [float(r["mmd_mm_s"]) / d1_rep for r in h2 if r["no_criterio"] == "True"]
    v["hDoisRazaoRuidoMin"], v["hDoisRazaoRuidoMax"] = br(min(razoes_mmd), 1), br(max(razoes_mmd), 1)

    # Descritores por janela, com velocidade por eixo.
    por_ensaio = {}
    for i, m in enumerate(meta):
        e = ensaios[m["ensaio"]]
        a_g = ar.para_g(brutas[i], int(m["accel_range"]))
        fs = float(m["sample_rate_hz"])
        busca = float(e["rotacao_busca_hz"]) if e["rotacao_busca_hz"] else None
        f_r = ar.rotacao(a_g, fs, busca) if busca else float("nan")
        d = ar.descritores(a_g, fs, f_r) if busca else None
        d2 = float(np.sqrt(((a_g - a_g.mean(axis=0)) ** 2).mean(axis=0).sum()))
        por_ensaio.setdefault(m["ensaio"], []).append({"a_g": a_g, "fs": fs, "f_r": f_r, "d": d, "d2": d2,
                                                       "v": velocidade_por_eixo(a_g, fs)})

    # Sinal e ruído, rotação e velocidade por eixo.
    linhas_sr, linhas_rot, linhas_eixo = [], [], []
    desvios = []  # desvio-padrão da rotação entre as janelas de cada ensaio: em Hz e em % da velocidade síncrona
    for e, js in por_ensaio.items():
        maq, rod = ensaios[e]["maquina"], ensaios[e]["rodada"]
        chave = NOME[(maq, rod)]
        d2m = statistics.median(j["d2"] for j in js)
        linhas_sr.append({"ensaio": e, "maquina": maq, "rodada": rod, "d2_mediano_mg": d2m * 1e3,
                          "razao_ruido": d2m / d2_rep})
        v[f"sinalRms{chave}"] = br(d2m * 1e3, 0)
        v[f"sinalRazao{chave}"] = br(d2m / d2_rep, 0)
        if maq == "Motor parado":
            # Com as mesmas casas decimais do valor em repouso, para a comparação no texto.
            v["sinalRmsMotorParadoDecimal"] = br(d2m * 1e3, 1)
            v["sinalRazaoMotorParadoDecimal"] = br(d2m / d2_rep, 2)
            continue
        fr = np.array([j["f_r"] for j in js])
        fr_med = float(np.median(fr))
        s = 100 * (SINCRONA[maq] - fr_med) / SINCRONA[maq]
        linhas_rot.append({"ensaio": e, "maquina": maq, "rodada": rod, "f_r_mediana_hz": fr_med,
                           "f_r_min_hz": float(fr.min()), "f_r_max_hz": float(fr.max()), "rpm": fr_med * 60,
                           "escorregamento_pct": s})
        v[f"rotacaoHz{chave}"] = br(fr_med, 2)
        v[f"rotacaoRpm{chave}"] = br(fr_med * 60, 0)
        v[f"escorregamento{chave}"] = br(s, 2)
        desvios.append((float(fr.std(ddof=1)), 100 * float(fr.std(ddof=1)) / SINCRONA[maq]))
        V = np.array([j["v"] for j in js])
        ax = ar.AXIAL[maq]
        ordem = [ax] + list(ar.RADIAIS[maq])
        for rotulo, k in zip(("axial", "radial 1", "radial 2"), ordem):
            q1, q2, q3 = np.percentile(V[:, k], [25, 50, 75])
            linhas_eixo.append({"ensaio": e, "maquina": maq, "rodada": rod, "direcao": rotulo, "eixo": "XYZ"[k],
                                "q1_mm_s": q1, "mediana_mm_s": q2, "q3_mm_s": q3})
        v[f"velAxial{chave}"] = br(float(np.median(V[:, ax])), 1)
        v[f"velMax{chave}"] = br(float(np.median(V.max(axis=1))), 1)
    escrever("sinal_ruido.csv", linhas_sr)
    escrever("rotacao.csv", linhas_rot)
    escrever("velocidade_por_eixo.csv", linhas_eixo)
    razoes = [r["razao_ruido"] for r in linhas_sr if r["maquina"] != "Motor parado"]
    v["sinalRazaoMin"], v["sinalRazaoMax"] = br(min(razoes), 0), br(max(razoes), 0)
    rpms = [r["rpm"] for r in linhas_rot if r["maquina"] != "Compressor"]
    v["rotacaoRpmMin"], v["rotacaoRpmMax"] = br(min(rpms), 0), br(max(rpms), 0)
    v["rotacaoDesvioMin"], v["rotacaoDesvioMax"] = br(min(d for d, _ in desvios), 2), br(max(d for d, _ in desvios), 2)
    v["rotacaoDesvioPctMin"] = br(min(p for _, p in desvios), 2)
    v["rotacaoDesvioPctMax"] = br(max(p for _, p in desvios), 2)
    for maq in ("Calandra", "Guilhotina"):
        um = statistics.median(j["d"]["d1"] for j in por_ensaio["3" if maq == "Calandra" else "1"])
        dois = statistics.median(j["d"]["d1"] for j in por_ensaio["5" if maq == "Calandra" else "6"])
        v[f"repet{maq}Um"], v[f"repet{maq}Dois"] = br(um, 2), br(dois, 2)
        v[f"repet{maq}Dif"] = br(100 * (dois - um) / um, 1)

    # Espectros médios e linhas: ordens diretas e rebatidas em torno de 1 kHz.
    linhas_esp, linhas_pico = [], []
    for e, js in por_ensaio.items():
        maq = ensaios[e]["maquina"]
        n = 512
        w = np.hanning(n)
        esp = np.mean([np.abs(np.fft.rfft((j["a_g"] - j["a_g"].mean(axis=0)) * w[:, None], n=4 * n, axis=0)).sum(axis=1)
                       * 2 / w.sum() for j in js], axis=0)
        fz = np.fft.rfftfreq(4 * n, 1 / 1000.0)
        for fi, ai in zip(fz, esp):
            linhas_esp.append({"ensaio": e, "maquina": maq, "rodada": ensaios[e]["rodada"], "f_hz": fi, "amp_g": ai})
        if maq == "Motor parado":
            continue
        fr = float(np.median([j["f_r"] for j in js]))
        piso = np.median(esp[(fz > 5)])
        for i in range(1, len(fz) - 1):
            if fz[i] < 5 or not (esp[i] > esp[i - 1] and esp[i] >= esp[i + 1] and esp[i] > 10 * piso):
                continue
            tipo, k = "não identificada", ""
            kd = round(fz[i] / fr)
            if kd >= 1 and abs(fz[i] - kd * fr) <= TOLERANCIA_HZ:
                tipo, k = "ordem direta", kd
            else:
                for kk in range(1, 40):
                    fa = abs(kk * fr - 1000.0 * round(kk * fr / 1000.0))
                    if kk * fr > 500 and abs(fz[i] - fa) <= TOLERANCIA_HZ:
                        tipo, k = "ordem rebatida", kk
                        break
            linhas_pico.append({"ensaio": e, "maquina": maq, "rodada": ensaios[e]["rodada"], "f_hz": round(fz[i], 2),
                                "amp_mg": esp[i] * 1e3, "razao_piso": esp[i] / piso, "tipo": tipo, "ordem": k})
    escrever("espectros.csv", linhas_esp)
    escrever("picos.csv", linhas_pico)
    reb = [p for p in linhas_pico if p["tipo"] == "ordem rebatida"]
    v["picosTotal"] = str(len(linhas_pico))
    v["picosDiretos"] = str(sum(p["tipo"] == "ordem direta" for p in linhas_pico))
    v["picosRebatidos"] = str(len(reb))
    v["picosNaoIdentificados"] = str(sum(p["tipo"] == "não identificada" for p in linhas_pico))
    v["picosTolerancia"] = br(TOLERANCIA_HZ, 0)
    primeira = {e for e, x in ensaios.items() if x["rodada"] == "1" and x["maquina"] != "Motor parado"}
    v["picosPrimeiraRodada"] = str(sum(p["ensaio"] in primeira for p in linhas_pico))
    for rod, chave in (("1", "Um"), ("2", "Dois")):
        v[f"picosRebatidosGuilhotina{chave}"] = str(sum(p["maquina"] == "Guilhotina" and p["rodada"] == rod for p in reb))

    # Rajadas por nível de sinal, fora do período de reinícios por bateria.
    raj = list(csv.DictReader(open(DADOS / "rajadas.csv", encoding="utf-8")))
    seq_um_periodo = [r for r in raj if r["device_sequence"] == "1" and r["hora_local"] >= INICIO_REINICIOS]
    PERIODO_REINICIOS = (INICIO_REINICIOS, max(r["hora_local"] for r in seq_um_periodo))
    v["rajadasSequenciaUmPeriodo"] = str(len(seq_um_periodo))
    fora = [r for r in raj if not (PERIODO_REINICIOS[0] <= r["hora_local"] <= PERIODO_REINICIOS[1])]
    comp = [r for r in fora if r["fragmentos_recebidos"] == r["fragmentos_total"]]
    falhas_reinicio = sum(1 for r in raj if PERIODO_REINICIOS[0] <= r["hora_local"] <= PERIODO_REINICIOS[1]
                          and r["fragmentos_recebidos"] != r["fragmentos_total"])
    falhas_total = sum(1 for r in raj if r["fragmentos_recebidos"] != r["fragmentos_total"])
    v["rajadasFora"], v["rajadasForaCompletas"] = str(len(fora)), str(len(comp))
    v["rajadasForaPct"] = br(100 * len(comp) / len(fora), 0)
    v["rajadasFalhasTotal"], v["rajadasFalhasReinicio"] = str(falhas_total), str(falhas_reinicio)
    v["rajadasDuracaoMediana"] = br(statistics.median(int(r["duracao_ms"]) for r in comp) / 1000, 1)
    linhas_rssi = []
    for lo in range(-130, -50, 10):
        g = [r for r in fora if lo <= float(r["rssi_dbm"]) < lo + 10]
        if g:
            c = sum(r["fragmentos_recebidos"] == r["fragmentos_total"] for r in g)
            linhas_rssi.append({"rssi_min_dbm": lo, "rssi_max_dbm": lo + 10, "n": len(g), "completas": c,
                                "fracao": c / len(g)})
    escrever("rajadas_rssi.csv", linhas_rssi)
    acima80 = [r for r in fora if float(r["rssi_dbm"]) >= -80]
    v["rajadasAcimaOitentaPct"] = br(100 * sum(r["fragmentos_recebidos"] == r["fragmentos_total"] for r in acima80)
                                     / len(acima80), 0)
    abaixo110 = [r for r in fora if float(r["rssi_dbm"]) < -110]
    v["rajadasAbaixoCentoDez"] = str(len(abaixo110))
    v["rajadasAbaixoCentoDezCompletas"] = str(sum(r["fragmentos_recebidos"] == r["fragmentos_total"] for r in abaixo110))
    v["reiniciosInicio"], v["reiniciosFim"] = (h[:5].replace(":", "h") for h in PERIODO_REINICIOS)

    def faixa(lo, hi):
        g = [r for r in fora if lo <= float(r["rssi_dbm"]) < hi]
        return len(g), sum(r["fragmentos_recebidos"] == r["fragmentos_total"] for r in g)
    n, c = faixa(-110, -100)
    v["rajadasCentoDezCem"], v["rajadasCentoDezCemCompletas"] = str(n), str(c)
    n, c = faixa(-100, -80)
    v["rajadasCemOitenta"], v["rajadasCemOitentaCompletas"] = str(n), str(c)
    v["rajadasCemOitentaPct"] = br(100 * c / n, 0)
    # Onde ficaram as rajadas incompletas fora do período de reinícios: dentro ou fora dos trechos analisados, sem
    # nenhum fragmento recebido, e no primeiro ciclo depois de o transmissor iniciar (sequência 1).
    incompletas = [r for r in fora if r["fragmentos_recebidos"] != r["fragmentos_total"]]
    trechos = [(x["inicio_local"], x["fim_local"]) for x in ensaios.values()]
    v["rajadasForaIncompletas"] = str(len(incompletas))
    v["rajadasForaIncompletasTrechos"] = str(sum(any(a <= r["hora_local"] <= b for a, b in trechos) for r in incompletas))
    v["rajadasForaSemFragmento"] = str(sum(r["fragmentos_recebidos"] == "0" for r in incompletas))
    # Com o fim do período na última rajada de sequência 1, nenhuma rajada desse tipo fica fora dele.
    assert not any(r["device_sequence"] == "1" for r in incompletas)
    faixa_media = [r for r in fora if -110 <= float(r["rssi_dbm"]) < -80]
    v["rajadasCentoDezOitenta"] = str(len(faixa_media))
    v["rajadasCentoDezOitentaCompletas"] = str(sum(r["fragmentos_recebidos"] == r["fragmentos_total"]
                                                   for r in faixa_media))

    # Resposta do detector principal a mudanças de condição: treino como em H3, teste no motor desligado e nas
    # janelas de teste das outras máquinas.
    planos = (("Dobradeira", "0", None), ("Guilhotina", "1", "6"), ("Calandra", "3", "5"), ("Compressor", "4", None))
    testes = {}
    treinos = {}
    for maq, tr, te in planos:
        if te is None:
            p1, p2 = np.array_split(np.arange(len(por_ensaio[tr])), 2)
            treinos[maq] = [por_ensaio[tr][i] for i in p1]
            testes[maq] = [por_ensaio[tr][i] for i in p2]
        else:
            treinos[maq], testes[maq] = por_ensaio[tr], por_ensaio[te]
    parado = por_ensaio["2"]
    linhas_cond = []
    for maq in treinos:
        thr, mod = ar.limiar(lambda: ar.Floresta(0), ar.matriz([j["d"] for j in treinos[maq]]))
        for alvo, js in list(testes.items()) + [("Motor desligado", None)]:
            if alvo == "Motor desligado":
                # O motor desligado não tem rotação; os descritores usam a rotação de busca da máquina de treino.
                busca = 59.8 if maq == "Compressor" else 29.8
                ds = [ar.descritores(j["a_g"], j["fs"], busca) for j in parado]
            else:
                ds = [j["d"] for j in js]
            frac = float((mod.escore(ar.matriz(ds)) > thr).mean())
            linhas_cond.append({"treino": maq, "alvo": alvo, "fracao_marcada": frac})
    escrever("condicao.csv", linhas_cond)
    outras = [r["fracao_marcada"] for r in linhas_cond if r["alvo"] not in (r["treino"], "Motor desligado")]
    parad = [r["fracao_marcada"] for r in linhas_cond if r["alvo"] == "Motor desligado"]
    v["condOutrasMin"], v["condOutrasMax"] = br(100 * min(outras), 0), br(100 * max(outras), 0)
    v["condParadoMin"], v["condParadoMax"] = br(100 * min(parad), 0), br(100 * max(parad), 0)

    # Linha de base de H3, como descrição: componente na rotação (d5) nas janelas de teste e, na guilhotina e no
    # compressor, o limiar e a faixa dos escores das janelas de teste sem assinatura e com 2,8 mm/s, com o mesmo
    # treino, o mesmo detector e as mesmas fases sorteadas da análise registrada.
    for maq in treinos:
        v[f"hTresBaseUmX{maq}"] = br(statistics.median(j["d"]["d5"] for j in testes[maq]), 1)
    for maq in ("Guilhotina", "Compressor"):
        thr, mod = ar.limiar(lambda: ar.Floresta(0), ar.matriz([j["d"] for j in treinos[maq]]))
        fases = np.random.default_rng(0).uniform(0, 2 * np.pi, len(testes[maq]))
        esc0 = mod.escore(ar.matriz([j["d"] for j in testes[maq]]))
        ds = [ar.descritores(ar.injetar(j["a_g"], j["fs"], j["f_r"], float(ar.GRADE[-1]), fases[i], ar.RADIAIS[maq]),
                             j["fs"], j["f_r"]) for i, j in enumerate(testes[maq])]
        esc = mod.escore(ar.matriz(ds))
        v[f"hTresLimiar{maq}"] = br(thr, 3)
        v[f"hTresEscoreZeroMin{maq}"], v[f"hTresEscoreZeroMax{maq}"] = br(esc0.min(), 3), br(esc0.max(), 3)
        v[f"hTresEscoreAltoMin{maq}"], v[f"hTresEscoreAltoMax{maq}"] = br(esc.min(), 3), br(esc.max(), 3)

    VALORES.write_text("% Gerado por experiments/campo/analise_descritiva.py; não editar à mão.\n"
                       + "\n".join(f"\\newcommand{{\\{k}}}{{{v[k]}}}" for k in sorted(v)) + "\n", encoding="utf-8")
    print(f"{len(v)} valores")


if __name__ == "__main__":
    main()
