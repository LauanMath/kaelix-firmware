"""Gera values/resultados_values.tex com os números detalhados das hipóteses e da resposta a mudanças de condição.

Lê os CSV de experiments/campo/analise_registrada/ e experiments/campo/analise_descritiva/; não recalcula nada.

Uso, a partir de docs/monografia/latex/: python3 scripts/build_results_values.py
"""
import csv
import math
import pathlib

AQUI = pathlib.Path(__file__).resolve().parent
RAIZ = AQUI.parents[3]
REG = RAIZ / "experiments" / "campo" / "analise_registrada"
DESC = RAIZ / "experiments" / "campo" / "analise_descritiva"
SAIDA = AQUI.parent / "values" / "resultados_values.tex"
CHAVE = {("Dobradeira", "1"): "DobradeiraUm", ("Guilhotina", "1"): "GuilhotinaUm", ("Guilhotina", "2"): "GuilhotinaDois",
         ("Calandra", "1"): "CalandraUm", ("Calandra", "2"): "CalandraDois", ("Compressor", "1"): "CompressorUm"}
SEM_ACENTO = {"Motor desligado": "Parado"}


def br(x, casas):
    return f"{x:.{casas}f}".replace(".", ",").replace("-", "\\textminus ")


def ler(p):
    return list(csv.DictReader(open(p, encoding="utf-8")))


def main():
    v = {}
    for r in ler(REG / "h1.csv"):
        k = r["maquina"] + ("IF" if r["detector"] == "Isolation Forest" else "MAD") + \
            ("Direto" if r["sentido"] == "1 para 2" else "Inverso")
        v[f"hUm{k}"] = br(100 * float(r["fracao"]), 1)
        v[f"hUm{k}Inf"] = br(100 * float(r["ic_inf"]), 1)
        v[f"hUm{k}Sup"] = br(100 * float(r["ic_sup"]), 1)
    for r in ler(REG / "h2.csv"):
        k = CHAVE[(r["maquina"], r["rodada"])]
        v[f"hDoisMediana{k}"] = br(float(r["mediana_mm_s"]), 2)
        v[f"hDoisQ{k}"] = br(float(r["q95_mm_s"]), 2)
        v[f"hDoisMmd{k}"] = br(float(r["mmd_mm_s"]), 2)
        v[f"hDoisRel{k}"] = br(float(r["mmd_rel_pct"]), 0)
        v[f"hDoisN{k}"] = r["n"]
    # H3, curvas do detector principal (Isolation Forest, semente 0) e da regra por mediana e MAD na assinatura 1x.
    curvas = ler(REG / "h3_curvas.csv")
    for maq in ("Dobradeira", "Guilhotina", "Calandra", "Compressor"):
        iff = [float(r["fracao"]) for r in curvas if r["maquina"] == maq and r["assinatura"] == "1x"
               and r["detector"] == "Isolation Forest" and r["semente"] == "0"]
        mad = [float(r["fracao"]) for r in curvas if r["maquina"] == maq and r["assinatura"] == "1x"
               and r["detector"] == "MAD"]
        v[f"hTresFracaoMax{maq}"] = br(100 * max(iff), 1)
        v[f"hTresFracaoMin{maq}"] = br(100 * min(iff), 1)
        v[f"hTresMadZero{maq}"] = br(100 * mad[0], 0)
        n_teste = int(next(r["n_teste"] for r in ler(REG / "h3_resumo.csv") if r["maquina"] == maq))
        v[f"hTresJanelasMax{maq}"] = str(round(max(iff) * n_teste))
        v[f"hTresJanelasMin{maq}"] = str(round(min(iff) * n_teste))
    resumo = ler(REG / "h3_resumo.csv")
    for maq in ("Dobradeira", "Guilhotina", "Calandra", "Compressor"):
        if_ = [r for r in resumo if r["maquina"] == maq and r["assinatura"] == "1x" and r["detector"] == "Isolation Forest"]
        a50 = [float(r["A50_mm_s"]) for r in if_]
        atingiu = sum(not math.isnan(x) for x in a50)
        v[f"hTresSementesAtingiram{maq}"] = str(atingiu)
        s0 = next(r for r in if_ if r["semente"] == "0")
        v[f"hTresFracaoZero{maq}"] = br(100 * float(s0["fracao_A0"]), 0)
        mad = next(r for r in resumo if r["maquina"] == maq and r["assinatura"] == "1x" and r["detector"] == "MAD")
        x = float(mad["A50_mm_s"])
        v[f"hTresMad{maq}"] = "não atingido" if math.isnan(x) else br(x, 2)
        dois = next(r for r in resumo if r["maquina"] == maq and r["assinatura"] == "2x")
        x = float(dois["A50_mm_s"])
        v[f"hTresDoisX{maq}"] = "não atingido" if math.isnan(x) else br(x, 2)
        v[f"hTresTreino{maq}"], v[f"hTresTeste{maq}"] = s0["n_treino"], s0["n_teste"]
    for r in ler(DESC / "condicao.csv"):
        alvo = SEM_ACENTO.get(r["alvo"], r["alvo"])
        v[f"cond{r['treino']}{alvo}"] = br(100 * float(r["fracao_marcada"]), 0)
    SAIDA.write_text("% Gerado por scripts/build_results_values.py; não editar à mão.\n"
                     + "\n".join(f"\\newcommand{{\\{k}}}{{{v[k]}}}" for k in sorted(v)) + "\n", encoding="utf-8")
    print(f"{len(v)} valores em {SAIDA}")


if __name__ == "__main__":
    main()
