#!/usr/bin/env python3
"""Gera as linhas das tabelas do apêndice de dados por ensaio a partir dos CSV das análises; não recalcula nada.

Lê experiments/campo/analise_registrada/descritores.csv (d1 a d6 de cada janela), experiments/campo/
analise_descritiva/rotacao.csv e velocidade_por_eixo.csv, e grava docs/monografia/latex/values/
tabelas_ensaio_values.tex com duas macros de linhas de tabela: \\linhasDescritoresEnsaio e \\linhasVelocidadeEnsaio.
Só entram os seis ensaios com o motor em operação, na ordem de ensaios.csv.

Uso, a partir de kaelix-firmware/:
  /usr/bin/python3 -I docs/monografia/latex/scripts/build_tabelas_ensaio.py
"""
import csv
import pathlib
import statistics

RAIZ = pathlib.Path(__file__).resolve().parents[4]
REG = RAIZ / "experiments" / "campo" / "analise_registrada"
DESC = RAIZ / "experiments" / "campo" / "analise_descritiva"
SAIDA = RAIZ / "docs" / "monografia" / "latex" / "values" / "tabelas_ensaio_values.tex"
ORDEM = ["0", "1", "3", "4", "5", "6"]  # ensaios com o motor em operação; o 2 é o motor desligado


def br(x, casas):
    return f"{x:.{casas}f}".replace(".", ",").replace("-", "\\textminus ")


def ler(p):
    with open(p, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main():
    janelas = ler(REG / "descritores.csv")
    rot = {r["ensaio"]: r for r in ler(DESC / "rotacao.csv")}
    vel = ler(DESC / "velocidade_por_eixo.csv")

    linhas_d = []
    for e in ORDEM:
        js = [j for j in janelas if j["ensaio"] == e]
        if not js:
            raise SystemExit(f"ensaio {e} sem janelas em descritores.csv")
        med = {k: statistics.median(float(j[k]) for j in js)
               for k in ("d1_mm_s", "d2_g", "d3", "d4", "d5_mm_s", "d6_mm_s")}
        r = rot[e]
        linhas_d.append(" & ".join([
            js[0]["maquina"], js[0]["rodada"], str(len(js)), f"{float(r['rpm']):.0f}",
            br(med["d1_mm_s"], 2), br(1000 * med["d2_g"], 0), br(med["d3"], 2), br(med["d4"], 2),
            br(med["d5_mm_s"], 2), br(med["d6_mm_s"], 2)]) + " \\\\")

    linhas_v = []
    for e in ORDEM:
        vs = {v["direcao"]: v for v in vel if v["ensaio"] == e}
        cel = []
        for d in ("axial", "radial 1", "radial 2"):
            v = vs[d]
            cel.append(f"{v['eixo']}: {br(float(v['mediana_mm_s']), 2)} ({br(float(v['q1_mm_s']), 2)} a "
                       f"{br(float(v['q3_mm_s']), 2)})")
        linhas_v.append(" & ".join([vs["axial"]["maquina"], vs["axial"]["rodada"]] + cel) + " \\\\")

    SAIDA.write_text("% Gerado por scripts/build_tabelas_ensaio.py; não editar à mão.\n"
                     "\\newcommand{\\linhasDescritoresEnsaio}{%\n" + "\n".join(linhas_d) + "\n}\n"
                     "\\newcommand{\\linhasVelocidadeEnsaio}{%\n" + "\n".join(linhas_v) + "\n}\n", encoding="utf-8")
    print(f"{len(linhas_d)} ensaios")


if __name__ == "__main__":
    main()
