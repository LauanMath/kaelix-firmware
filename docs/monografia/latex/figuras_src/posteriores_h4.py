"""Figuras da H4 (base pública de desbalanceamento) e da AP1 (assinatura em fase), no capítulo de resultados.

fig_h4: escore do detector principal, d1 e d3 por arquivo da base pública. O escore é recalculado a partir dos
descritores gravados por experiments/fraunhofer/analise_h4.py (analise_registrada/janelas.csv), com o mesmo
detector e o mesmo limiar, e a fração marcada é conferida contra h4.csv antes do desenho.
fig_ap1: fração marcada em função da amplitude da assinatura, com fase sorteada (H3) e com fase fixa (AP1), lida de
experiments/campo/analise_posterior/ap1_curvas.csv.

Estilo, cores e funções de resultados.py (guia de figuras da Nature e guia de plotagem): 160 mm, Arial de 5 a 7 pt,
letras de painel em 8 pt, chave na figura, cores de Paul Tol com redundância por marcador e tipo de linha,
vírgula decimal. Grava fig_h4 e fig_ap1, em PDF, SVG e PNG, em Images/ ou na pasta dada.

Uso, a partir de docs/monografia/latex/:
  taskpolicy -b uv run --no-project --python 3.12 --with numpy==2.5.2 --with scipy==1.18.0 \\
      --with scikit-learn==1.9.0 --with matplotlib python figuras_src/posteriores_h4.py [pasta]
"""
import pathlib
import sys

from matplotlib.lines import Line2D
from matplotlib.patches import Patch

AQUI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import resultados as r  # noqa: E402  (estilo, cores e funções comuns; lê a pasta de saída de sys.argv)

plt = r.plt
MM = r.MM
RAIZ = r.RAIZ
sys.path.insert(0, str(RAIZ / "experiments" / "campo"))
import analise_registrada as ar  # noqa: E402

H4 = RAIZ / "experiments" / "fraunhofer" / "analise_registrada"
AP1 = RAIZ / "experiments" / "campo" / "analise_posterior" / "ap1_curvas.csv"
ARQUIVOS = ["0D.csv", "0E.csv", "1E.csv", "2E.csv", "3E.csv", "4E.csv"]
ROTULOS = ["0D", "0E", "1E", "2E", "3E", "4E"]
CINZA_TREINO = r.CINZA_CLARO


def fig_h4():
    linhas = r.ler(H4 / "janelas.csv")
    desc = {a: [{k: float(l[f"{k}_principal"]) for k in ("d1", "d2", "d3", "d4", "d5", "d6")}
                for l in linhas if l["arquivo"] == a] for a in ARQUIVOS}
    thr, mod = ar.limiar(lambda: ar.Floresta(0), ar.matriz(desc["0D.csv"]))
    escores = {a: mod.escore(ar.matriz(desc[a])) for a in ARQUIVOS}
    # conferência: a fração marcada tem de ser a de h4.csv (detector principal, semente 0)
    gravada = {int(l["nivel"]): float(l["fracao"]) for l in r.ler(H4 / "h4.csv")
               if l["variante"] == "principal" and l["detector"] == "Isolation Forest" and l["semente"] == "0"}
    for nivel, a in enumerate(ARQUIVOS[1:]):
        f = float((escores[a] > thr).mean())
        if abs(f - gravada[nivel]) > 1e-12:
            raise SystemExit(f"{a}: fração {f} diferente da gravada {gravada[nivel]}")

    fig, axs = plt.subplots(1, 3, figsize=(r.LARGURA, 62 * MM))
    series = [
        ([escores[a] for a in ARQUIVOS], "Escore do detector", False),
        ([[d["d1"] for d in desc[a]] for a in ARQUIVOS], "$d_1$ (unidade dos canais)", True),
        ([[d["d3"] for d in desc[a]] for a in ARQUIVOS], "Curtose em excesso, $d_3$", False),
    ]
    for ax, (dados, rotulo, log) in zip(axs, series):
        bp = ax.boxplot(dados, widths=0.55, patch_artist=True, showfliers=True,
                        medianprops={"color": r.PRETO, "lw": 1.0},
                        boxprops={"lw": 0.6}, whiskerprops={"lw": 0.6}, capprops={"lw": 0.6},
                        flierprops={"marker": "o", "markersize": 1.6, "markeredgewidth": 0.4,
                                    "markeredgecolor": r.CINZA_ESCURO, "markerfacecolor": "none"})
        for k, caixa in enumerate(bp["boxes"]):
            caixa.set_facecolor(CINZA_TREINO if k == 0 else "white")
            caixa.set_edgecolor(r.PRETO)
        ax.set_xticks(range(1, len(ROTULOS) + 1), ROTULOS)
        ax.set_xlabel("Arquivo")
        ax.set_ylabel(rotulo)
        if log:
            ax.set_yscale("log")
            ax.set_yticks([0.01, 0.02, 0.05, 0.1, 0.2])
        r.formatar(ax, x=False)
    axs[0].axhline(thr, color=r.PRETO, lw=0.8, ls="--", zorder=0)
    handles = [Patch(facecolor=CINZA_TREINO, edgecolor=r.PRETO, lw=0.6, label="Treino (0D)"),
               Patch(facecolor="white", edgecolor=r.PRETO, lw=0.6, label="Avaliação, níveis 0 a 4 (0E a 4E)"),
               Line2D([], [], color=r.PRETO, lw=0.8, ls="--", label="Limiar do detector")]
    r.chave(fig, handles, ncol=3, handlelength=1.6)
    r.ajustar(fig, topo_mm=7)
    r.letras(fig, axs)
    r.salvar(fig, "fig_h4")
    return thr


def fig_ap1():
    curvas = r.ler(AP1)
    fig, axs = plt.subplots(1, 4, figsize=(r.LARGURA, 60 * MM), sharey=True)
    estilos = {0: dict(ls="-", marker=None), 90: dict(ls="-", marker="o", markevery=8, mfc="white", mew=0.6),
               180: dict(ls="-", marker="^", markevery=8, mfc="white", mew=0.6)}
    for ax, maq in zip(axs, r.MAQUINAS):
        def serie(theta, campo):
            pts = sorted((float(c["A_v_mm_s"]), 100 * float(c[campo])) for c in curvas
                         if c["maquina"] == maq and int(c["theta_graus"]) == theta)
            return [p[0] for p in pts], [p[1] for p in pts]
        x, y = serie(0, "fracao_h3_sorteada")
        ax.plot(x, y, color=r.CINZA, lw=1.6, solid_capstyle="butt")
        x, y = serie(0, "fracao_mad")
        ax.plot(x, y, color=r.PRETO, ls="--", lw=0.8)
        for theta in (0, 90, 180):
            x, y = serie(theta, "fracao_if")
            ax.plot(x, y, color=r.COR_MAQ[maq], lw=1.0, markersize=3, **estilos[theta])
        r.referencia(ax, r.CRITERIO_PCT, estilo=":")
        r.referencia(ax, r.REF_MM_S, "v", estilo="-.")
        ax.set_title(maq)
        ax.set_xlim(0, 2.8)
        ax.set_ylim(-3, 103)
        ax.set_yticks([0, 25, 50, 75, 100])
        ax.set_xlabel("$A_v$ (mm/s)")
        r.formatar(ax)
    axs[0].set_ylabel("Janelas marcadas (%)")
    axs[0].text(r.REF_MM_S + 0.08, 97, f"{r.num(r.REF_MM_S)} mm/s", ha="left", va="top", fontsize=6)
    # Chave: as séries do detector principal com fase fixa são desenhadas na cor de cada máquina, e o item da chave
    # mostra as quatro cores; o marcador distingue a diferença de fase.
    itens = [(Line2D([], [], color=r.CINZA, lw=1.6), "Fase sorteada (H3)")]
    for theta in (0, 90, 180):
        kw = {k: v for k, v in estilos[theta].items() if k != "markevery"}
        itens.append(r.linha_maquinas(f"Fase fixa, $\\theta$ = {theta}°", lw=1.0, markersize=3, **kw))
    itens.append((Line2D([], [], color=r.PRETO, ls="--", lw=0.8), "Mediana e MAD, $\\theta$ = 0°"))
    r.legenda_maquinas(fig, itens, ncol=5)
    r.ajustar(fig, topo_mm=6)
    r.letras(fig, axs)
    r.salvar(fig, "fig_ap1")


if __name__ == "__main__":
    r.SAIDA.mkdir(parents=True, exist_ok=True)
    limiar = fig_h4()
    fig_ap1()
    print(f"fig_h4 (limiar {limiar:.3f}) e fig_ap1 em {r.SAIDA}")
