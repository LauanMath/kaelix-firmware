"""Figuras do capítulo de resultados, geradas a partir dos CSV das análises da coleta em campo.

Lê experiments/campo/analise_descritiva/ e experiments/campo/analise_registrada/ e grava, em Images/,
fig_ruido, fig_enlace, fig_espectros, fig_eixos e fig_injecao, em PDF, SVG e PNG.

Padrão: guia de figuras da Nature ("Preparing figures: our specifications" e "Building and exporting figure
panels", em research-figure-guide.nature.com, lidos em 08/11/2026) e guia de plotagem do autor.
- Largura: 89 mm, uma coluna da Nature, para figura de um painel; 160 mm, a caixa de texto da monografia, para
  figura de vários painéis (a coluna dupla da Nature, 183 mm, não cabe na página). Altura abaixo de 170 mm.
  O LaTeX inclui as figuras sem escala, para que o texto impresso tenha o corpo definido aqui.
- Arial em todo o texto, inclusive nos símbolos matemáticos; texto de 5 a 7 pt; letras de painel em 8 pt,
  negrito, minúsculas, no canto superior esquerdo; fontes TrueType embutidas e texto editável no SVG.
- Eixos com linha e marcações para fora, unidade entre parênteses; sem grade; sem texto colorido; chave dentro
  da figura, no lugar de descrição de cor na legenda; linhas de referência rotuladas na própria figura.
- Cores de Paul Tol (Colour Schemes, SRON/EPS/TN/09-002, versão 3.2, 18/08/2021), escolhidas pelo tipo de
  dado, como ele recomenda, e com um papel fixo em todo o documento. Máquinas são dados qualitativos: esquema
  bright (azul, vermelho, verde e roxo; o amarelo dele fica de fora, com contraste de 1,95:1 sobre o branco em
  linha fina), as mesmas cores da planta do galpão (mudar aqui obriga a mudar a planta). O que não é máquina
  (eixos e direções do sensor, treino, referências, séries de um conjunto só) fica em preto e nos cinzas do Tol,
  distinguidos por marcador e tipo de linha. O amarelo é do rádio LoRa, nas figuras do capítulo do sistema.
- Vírgula decimal, sinal de menos tipográfico e espaço fino nos milhares.

Uso, a partir de docs/monografia/latex/ (a pasta de saída é opcional; o padrão é Images/):
  uv run --no-project --with numpy --with matplotlib python figuras_src/resultados.py [pasta]
"""
import csv
import math
import re
import pathlib
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib._mathtext as _mathtext  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.legend_handler import HandlerTuple  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402
from matplotlib.ticker import FixedLocator, FuncFormatter, NullFormatter  # noqa: E402

AQUI = pathlib.Path(__file__).resolve().parent
LATEX = AQUI.parent
RAIZ = LATEX.parents[2]
DESC = RAIZ / "experiments" / "campo" / "analise_descritiva"
REG = RAIZ / "experiments" / "campo" / "analise_registrada"
SAIDA = pathlib.Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else LATEX / "Images"
MM = 1 / 25.4
LARGURA = 160 * MM  # caixa de texto da monografia
COLUNA = 89 * MM  # uma coluna da Nature
# Esquema bright de Tol, na ordem que ele indica (azul, vermelho, verde), com o roxo no lugar do amarelo.
AZUL, VERMELHO, VERDE, ROXO = "#4477AA", "#EE6677", "#228833", "#AA3377"
# Neutros: preto e os cinzas de Tol (cinza-escuro do esquema dark, cinza do bright, cinza-claro do pale).
PRETO, CINZA_ESCURO, CINZA, CINZA_CLARO = "#000000", "#555555", "#BBBBBB", "#DDDDDD"
CINZA_REF = CINZA  # linhas de referência, finas e atrás dos dados
MAQUINAS = ("Dobradeira", "Guilhotina", "Calandra", "Compressor")  # a mesma ordem em todas as figuras
COR_MAQ = {"Dobradeira": AZUL, "Guilhotina": VERMELHO, "Calandra": VERDE, "Compressor": ROXO}
MARC_MAQ = {"Dobradeira": "o", "Guilhotina": "s", "Calandra": "^", "Compressor": "D"}
# Eixos do sensor e direções em relação ao motor não são máquinas: tons neutros, com tipo de linha e marcador.
ESTILO_EIXO = {"X": (CINZA, "-"), "Y": (CINZA_ESCURO, "--"), "Z": (PRETO, "-")}
ESTILO_DIRECAO = {"axial": (PRETO, "o", PRETO), "radial 1": (CINZA_ESCURO, "s", CINZA_ESCURO),
                  "radial 2": (PRETO, "^", "white")}  # cor, marcador, preenchimento

# O matplotlib reduz os índices a 0,7 do corpo; com 7 pt, o índice de A_v e de d_1 sairia com 4,9 pt, abaixo do
# mínimo de 5 pt da Nature. Com 0,72, sai com 5,04 pt. A constante é lida a cada desenho.
_mathtext.SHRINK_FACTOR = 0.72

plt.rcParams.update({
    "font.family": "sans-serif", "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
    "mathtext.fontset": "custom", "mathtext.rm": "Arial", "mathtext.it": "Arial:italic",
    "mathtext.bf": "Arial:bold", "mathtext.sf": "Arial",
    "font.size": 7, "axes.titlesize": 7, "axes.labelsize": 7, "xtick.labelsize": 6.5, "ytick.labelsize": 6.5,
    "legend.fontsize": 6.5, "axes.titlelocation": "left", "axes.titlepad": 4, "axes.labelpad": 2.5,
    "axes.linewidth": 0.6, "xtick.major.width": 0.6, "ytick.major.width": 0.6, "xtick.minor.width": 0.5,
    "ytick.minor.width": 0.5, "xtick.major.size": 3, "ytick.major.size": 3, "xtick.minor.size": 1.6,
    "ytick.minor.size": 1.6, "xtick.major.pad": 2, "ytick.major.pad": 2, "xtick.direction": "out",
    "ytick.direction": "out", "lines.linewidth": 1.0, "lines.markersize": 3.5, "axes.spines.top": False,
    "axes.spines.right": False, "legend.frameon": False, "legend.handlelength": 2.2, "legend.handletextpad": 0.5,
    "legend.columnspacing": 1.5, "legend.borderaxespad": 0, "legend.borderpad": 0, "pdf.fonttype": 42,
    "svg.fonttype": "none", "axes.unicode_minus": True, "text.color": PRETO, "axes.labelcolor": PRETO,
    "axes.edgecolor": PRETO, "xtick.color": PRETO, "ytick.color": PRETO, "savefig.dpi": 600,
})


def num(x, _pos=None):
    """Número com vírgula decimal, sinal de menos tipográfico e espaço fino nos milhares."""
    s = f"{abs(x):.6g}"
    if "e" in s:
        s = f"{abs(x):.8f}".rstrip("0").rstrip(".")
    inteiro, _, frac = s.partition(".")
    if len(inteiro) >= 4:
        grupos = []
        while inteiro:
            grupos.insert(0, inteiro[-3:])
            inteiro = inteiro[:-3]
        inteiro = " ".join(grupos)
    s = inteiro + ("," + frac if frac else "")
    return ("−" if x < 0 else "") + s


def formatar(ax, x=True, y=True):
    for usar, eixo in ((x, ax.xaxis), (y, ax.yaxis)):
        if usar:
            eixo.set_major_formatter(FuncFormatter(num))
            eixo.set_minor_formatter(NullFormatter())


def referencia(ax, valor, orientacao="h", estilo="--"):
    """Linha de referência fina e cinza, atrás dos dados."""
    f = ax.axhline if orientacao == "h" else ax.axvline
    f(valor, color=CINZA_REF, lw=0.8, ls=estilo, zorder=0)


def ajustar(fig, topo_mm=0.0, base_mm=0.0):
    """Leiaute justo, com faixa livre no topo para a chave e as letras dos painéis."""
    altura = fig.get_figheight() / MM
    fig.tight_layout(pad=0.3, w_pad=1.6, h_pad=1.2, rect=(0, base_mm / altura, 1, 1 - topo_mm / altura))


def letras(fig, axs, rotulos="abcdefgh"):
    """Letras dos painéis em 8 pt, negrito: na coluna, alinhadas pela borda esquerda do painel mais largo
    (rótulo do eixo incluído); na linha, na altura do título ou logo acima do painel."""
    fig.canvas.draw()
    r = fig.canvas.get_renderer()
    inv = fig.transFigure.inverted()
    caixas = [inv.transform_bbox(ax.get_tightbbox(r)) for ax in axs]
    pos = [ax.get_position() for ax in axs]
    for i, (ax, l) in enumerate(zip(axs, rotulos)):
        coluna = [c.x0 for c, p in zip(caixas, pos) if abs(p.x0 - pos[i].x0) < 1e-3]
        linha = [p.y1 for p in pos if abs(p.y1 - pos[i].y1) < 1e-3]
        x = min(coluna)
        if ax.get_title(loc="left"):
            titulo = inv.transform_bbox(ax._left_title.get_window_extent(r))
            # Sem rótulos no eixo vertical (eixo compartilhado), a letra vai para o vão entre os painéis, com a
            # borda direita a 1,5 mm do título.
            x = min(x, titulo.x0 - 3.4 * MM / fig.get_figwidth())
            fig.text(x, titulo.y0, l, fontsize=8, fontweight="bold", ha="left", va="bottom")
        else:
            fig.text(x, max(linha) + 1.2 * MM / fig.get_figheight(), l, fontsize=8, fontweight="bold",
                     ha="left", va="bottom")


def chave(fig, handles, ncol, y_mm=1.0, **kw):
    """Chave única da figura, numa faixa acima dos painéis."""
    altura = fig.get_figheight() / MM
    return fig.legend(handles=handles, loc="upper center", ncol=ncol, bbox_to_anchor=(0.5, 1 - y_mm / altura),
                      **kw)


def linha_maquinas(rotulo, **kw):
    """Item de chave para uma série desenhada na cor de cada máquina: um traço de cada cor."""
    return tuple(Line2D([], [], color=COR_MAQ[m], **kw) for m in MAQUINAS), rotulo


def legenda_maquinas(fig, itens, ncol, y_mm=1.0):
    handles = [h for h, _ in itens]
    rotulos = [t for _, t in itens]
    altura = fig.get_figheight() / MM
    return fig.legend(handles, rotulos, loc="upper center", ncol=ncol, bbox_to_anchor=(0.5, 1 - y_mm / altura),
                      handler_map={tuple: HandlerTuple(ndivide=None, pad=0.0)}, handlelength=3.2)


def ler(caminho):
    return list(csv.DictReader(open(caminho, encoding="utf-8")))


def macro(nome):
    """Valor numérico de uma macro gerada em values/, o mesmo que o texto imprime."""
    for arq in sorted((LATEX / "values").glob("*.tex")):
        m = re.search(r"\\newcommand\{\\" + nome + r"\}\{([^}]*)\}", arq.read_text(encoding="utf-8"))
        if m:
            return float(m.group(1).replace(",", ".").replace("\\,", ""))
    raise SystemExit(f"macro {nome} não encontrada em values/")


# Constantes do procedimento, escritas no texto com \SI: tamanho de referência (seção de métodos), banda nominal
# do filtro interno do sensor e fração do critério de H3.
REF_MM_S = 0.7
FILTRO_HZ = 184
CRITERIO_PCT = 50


def salvar(fig, nome):
    """PDF e SVG vetoriais, com texto editável, e PNG a 600 dpi (guia de plotagem); o LaTeX usa o PDF."""
    fig.savefig(SAIDA / f"{nome}.pdf")
    fig.savefig(SAIDA / f"{nome}.svg")
    fig.savefig(SAIDA / f"{nome}.png", dpi=600)
    plt.close(fig)


def wilson(k, n, z=1.959964):
    """Intervalo de confiança de 95 % de Wilson para a proporção k/n."""
    p = k / n
    centro = (p + z * z / (2 * n)) / (1 + z * z / n)
    meia = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, centro - meia), min(1.0, centro + meia)


def rotulo_ensaio(maquina, rodada):
    return "Motor desligado" if maquina == "Motor parado" else f"{maquina} {rodada}"


def ordem_ensaios(linhas):
    """Ensaios na ordem das máquinas e das rodadas; o trecho com o motor desligado por último."""
    return sorted(linhas, key=lambda r: (MAQUINAS.index(r["maquina"]) if r["maquina"] in MAQUINAS else 9,
                                         int(r["rodada"])))


def fig_ruido():
    psd = ler(DESC / "psd_repouso.csv")
    f = np.array([float(r["f_hz"]) for r in psd])
    sel = (f >= 5) & (f <= 495)
    fig, (a, b) = plt.subplots(1, 2, figsize=(LARGURA, 62 * MM), gridspec_kw={"width_ratios": [1.25, 1]})
    for eixo, (cor, ls) in ESTILO_EIXO.items():
        dens = np.sqrt(np.array([float(r[f"psd_{eixo.lower()}_g2_hz"]) for r in psd])) * 1e6
        a.plot(f[sel], dens[sel], color=cor, ls=ls, lw=1.0, label=eixo, zorder=3 if eixo == "Z" else 2)
    folha = macro("ruidoDatasheet")  # µg/√Hz, folha de dados do MPU-6050
    referencia(a, folha, estilo="-.")
    a.text(497, folha * 1.12, "Folha de dados", ha="right", va="bottom", fontsize=6)
    a.set_yscale("log")
    a.set_xlim(0, 500)
    a.set_ylim(2, 3000)
    a.set_xlabel("Frequência, $f$ (Hz)")
    a.set_ylabel("Densidade espectral de ruído (µg/√Hz)")
    a.legend(loc="lower left", ncol=3, title="Eixo do sensor", title_fontsize=6.5, alignment="left")
    formatar(a)

    sr = ordem_ensaios(ler(DESC / "sinal_ruido.csv"))
    for i, r in enumerate(sr):
        maq = r["maquina"]
        b.plot(float(r["d2_mediano_mg"]), i, marker=MARC_MAQ.get(maq, "X"), color=COR_MAQ.get(maq, CINZA_ESCURO),
               ls="none", ms=4)
    b.set_yticks(range(len(sr)), [rotulo_ensaio(r["maquina"], r["rodada"]) for r in sr])
    b.set_ylim(len(sr) - 0.4, -0.8)
    rep = ler(DESC / "ruido.csv")
    rep_total = float(np.sqrt(sum(float(r["rms_mediano_mg"]) ** 2 for r in rep)))
    referencia(b, rep_total, "v", estilo="-.")
    b.text(rep_total * 1.12, -0.75, "Repouso", ha="left", va="center", fontsize=6)
    b.set_xscale("log")
    b.set_xlim(2, 1000)
    b.set_xlabel("Valor eficaz total da aceleração, $d_2$ (mg)")
    formatar(b, y=False)
    ajustar(fig, topo_mm=4)
    letras(fig, (a, b))
    salvar(fig, "fig_ruido")


def fig_enlace():
    linhas = ler(DESC / "rajadas_rssi.csv")
    fig, a = plt.subplots(figsize=(COLUNA, 62 * MM))
    x = np.array([(float(r["rssi_min_dbm"]) + float(r["rssi_max_dbm"])) / 2 for r in linhas])
    k = np.array([int(r["completas"]) for r in linhas])
    n = np.array([int(r["n"]) for r in linhas])
    p = 100 * k / n
    ic = np.array([wilson(ki, ni) for ki, ni in zip(k, n)]) * 100
    # max(0, ...) só tira o erro de arredondamento quando a proporção é 0 % ou 100 %.
    a.errorbar(x, p, yerr=[np.maximum(0, p - ic[:, 0]), np.maximum(0, ic[:, 1] - p)], fmt="o", color=PRETO, ms=3.5, elinewidth=0.8, capsize=1.5,
               capthick=0.8)
    for xi, ni in zip(x, n):
        a.text(xi, 1.04, num(ni), transform=a.get_xaxis_transform(), ha="center", va="bottom", fontsize=6)
    a.text(-131.5, 1.04, "$n$", transform=a.get_xaxis_transform(), ha="right", va="bottom", fontsize=6)
    a.set_xlabel("RSSI da telemetria (dBm)")
    a.set_ylabel("Rajadas completas (%)")
    a.set_ylim(-4, 104)
    a.set_yticks([0, 25, 50, 75, 100])
    a.set_xlim(-130, -50)
    a.xaxis.set_major_locator(FixedLocator(range(-130, -49, 20)))
    a.xaxis.set_minor_locator(FixedLocator(range(-120, -59, 20)))
    formatar(a)
    ajustar(fig, topo_mm=4)
    salvar(fig, "fig_enlace")


def rotular_picos(fig, ax, f, amp, picos, folga_pt=1.0):
    """Rótulo de cada linha associada a uma ordem, na primeira posição livre: acima do marcador, à esquerda,
    à direita ou mais acima. Livre quer dizer sem tocar, com a folga dada, os marcadores, os rótulos já postos
    e a curva do espectro. Chamada depois do leiaute, quando a geometria do painel é a final."""
    r = fig.canvas.get_renderer()
    folga = folga_pt * fig.dpi / 72
    curva = ax.transData.transform(np.column_stack([f, amp]))
    ocupado = []
    for p in picos:
        cx, cy = ax.transData.transform((float(p["f_hz"]), float(p["amp_mg"]) * 1.6))
        meia = 3.5 / 2 * fig.dpi / 72
        ocupado.append((cx - meia, cy - meia, cx + meia, cy + meia))

    def livre(t):
        b = t.get_window_extent(r)
        x0, y0, x1, y1 = b.x0 - folga, b.y0 - folga, b.x1 + folga, b.y1 + folga
        if any(x0 < o[2] and o[0] < x1 and y0 < o[3] and o[1] < y1 for o in ocupado):
            return None
        dentro = (curva[:, 0] > x0) & (curva[:, 0] < x1) & (curva[:, 1] > y0) & (curva[:, 1] < y1)
        return None if dentro.any() else (b.x0, b.y0, b.x1, b.y1)

    for p in (p for p in picos if p["ordem"]):
        fp, ap = float(p["f_hz"]), float(p["amp_mg"])
        txt = p["ordem"] + ("r" if p["tipo"] == "ordem rebatida" else "")
        # Deslocamentos em pontos, a partir do centro do marcador (3,5 pt de diâmetro).
        for dx, dy, ha, va in ((0, 3.0, "center", "bottom"), (-4.0, 0, "right", "center"),
                               (4.0, 0, "left", "center"), (0, 10.0, "center", "bottom")):
            t = ax.annotate(txt, (fp, ap * 1.6), xytext=(dx, dy), textcoords="offset points", ha=ha, va=va,
                            fontsize=6)
            caixa = livre(t)
            if caixa:
                ocupado.append(caixa)
                break
            t.remove()
        else:
            raise SystemExit(f"sem posição livre para o rótulo {txt} em {fp} Hz")


def fig_espectros():
    esp = ler(DESC / "espectros.csv")
    picos = ler(DESC / "picos.csv")
    paineis = (("0", "Dobradeira"), ("1", "Guilhotina"), ("3", "Calandra"), ("4", "Compressor"))
    estilo = {"ordem direta": ("v", PRETO, "white"), "ordem rebatida": ("s", PRETO, "white"),
              "não identificada": ("o", CINZA_ESCURO, "white")}
    # Eixo vertical comum aos quatro painéis, para que as amplitudes das máquinas se comparem diretamente.
    fig, axs = plt.subplots(2, 2, figsize=(LARGURA, 100 * MM), sharex=True, sharey=True)
    dados = []
    for ax, (e, maq) in zip(axs.flat, paineis):
        f = np.array([float(r["f_hz"]) for r in esp if r["ensaio"] == e])
        amp = np.array([float(r["amp_g"]) for r in esp if r["ensaio"] == e]) * 1e3
        ax.plot(f, amp, color=COR_MAQ[maq], lw=0.7)
        referencia(ax, FILTRO_HZ, "v")
        lista = sorted((p for p in picos if p["ensaio"] == e), key=lambda p: float(p["f_hz"]))
        for p in lista:
            fp, ap = float(p["f_hz"]), float(p["amp_mg"])
            m, borda, fundo = estilo[p["tipo"]]
            ax.plot(fp, ap * 1.6, marker=m, mec=borda, mfc=fundo, mew=0.7, ls="none", ms=3.5, zorder=3)
        dados.append((ax, f, amp, lista))
        ax.set_title(f"{maq}, rodada 1")
        ax.set_yscale("log")
        ax.set_xlim(0, 500)
        ax.set_ylim(0.02, 8000)
        formatar(ax)
    for ax in axs[1]:
        ax.set_xlabel("Frequência, $f$ (Hz)")
    for ax in axs[:, 0]:
        ax.set_ylabel("Amplitude da aceleração (mg)")
    axs[0, 0].text(FILTRO_HZ + 3, 4500, f"{FILTRO_HZ} Hz", ha="left", va="center", fontsize=6)
    handles = [Line2D([], [], marker="v", mec=PRETO, mfc="white", mew=0.7, ls="none", ms=3.5,
                      label="Ordem da rotação"),
               Line2D([], [], marker="s", mec=PRETO, mfc="white", mew=0.7, ls="none", ms=3.5,
                      label="Ordem rebatida pela amostragem"),
               Line2D([], [], marker="o", mec=CINZA_ESCURO, mfc="white", mew=0.7, ls="none", ms=3.5,
                      label="Linha não associada"),
               Line2D([], [], color=CINZA_REF, lw=0.8, ls="--", label="Filtro interno do sensor")]
    chave(fig, handles, ncol=4)
    ajustar(fig, topo_mm=6)
    for ax, f, amp, lista in dados:
        rotular_picos(fig, ax, f, amp, lista)
    letras(fig, list(axs.flat))
    salvar(fig, "fig_espectros")


def fig_eixos():
    linhas = ler(DESC / "velocidade_por_eixo.csv")
    ensaios = ordem_ensaios({r["ensaio"]: r for r in linhas}.values())
    fig, a = plt.subplots(figsize=(COLUNA, 78 * MM))
    for d, (cor, m, fundo) in ESTILO_DIRECAO.items():
        dy = {"axial": -0.24, "radial 1": 0.0, "radial 2": 0.24}[d]
        for i, ens in enumerate(ensaios):
            r = next(r for r in linhas if r["ensaio"] == ens["ensaio"] and r["direcao"] == d)
            med, q1, q3 = float(r["mediana_mm_s"]), float(r["q1_mm_s"]), float(r["q3_mm_s"])
            a.errorbar(med, i + dy, xerr=[[med - q1], [q3 - med]], fmt=m, color=cor, mfc=fundo, mec=cor, mew=0.8,
                       ms=3.5, elinewidth=0.8, capsize=1.2, capthick=0.8, zorder=3)
    referencia(a, REF_MM_S, "v")
    a.text(REF_MM_S * 1.08, -0.72, f"{num(REF_MM_S)} mm/s", ha="left", va="center", fontsize=6)
    a.set_yticks(range(len(ensaios)), [rotulo_ensaio(e["maquina"], e["rodada"]) for e in ensaios])
    a.set_ylim(len(ensaios) - 0.5, -0.9)
    a.set_xscale("log")
    a.set_xlim(0.1, 40)
    a.set_xlabel("Velocidade eficaz de 10 Hz a 184 Hz (mm/s)")
    formatar(a, y=False)
    handles = [Line2D([], [], color=c, marker=m, mfc=fundo, mec=c, mew=0.8, ls="none", ms=3.5, label=d.capitalize())
               for d, (c, m, fundo) in ESTILO_DIRECAO.items()]
    chave(fig, handles, ncol=3, handletextpad=0.2, columnspacing=1.2)
    ajustar(fig, topo_mm=5)
    salvar(fig, "fig_eixos")


def fig_injecao():
    curvas = ler(REG / "h3_curvas.csv")
    fig, axs = plt.subplots(1, 4, figsize=(LARGURA, 58 * MM), sharey=True)
    grade = sorted({float(r["A_v_mm_s"]) for r in curvas})
    for ax, maq in zip(axs, MAQUINAS):
        sem = np.array([[float(r["fracao"]) for r in curvas if r["maquina"] == maq and r["assinatura"] == "1x"
                         and r["detector"] == "Isolation Forest" and int(r["semente"]) == s] for s in range(10)]) * 100
        ax.fill_between(grade, sem.min(axis=0), sem.max(axis=0), color=CINZA_CLARO, lw=0)
        mad = [100 * float(r["fracao"]) for r in curvas if r["maquina"] == maq and r["assinatura"] == "1x"
               and r["detector"] == "MAD"]
        ax.plot(grade, mad, color=PRETO, ls="--", lw=0.8)
        ax.plot(grade, sem[0], color=COR_MAQ[maq], lw=1.0)
        referencia(ax, CRITERIO_PCT, estilo=":")
        referencia(ax, REF_MM_S, "v", estilo="-.")
        ax.set_title(maq)
        ax.set_xlim(0, 2.8)
        ax.set_ylim(-3, 103)
        ax.set_yticks([0, 25, 50, 75, 100])
        ax.set_xlabel("$A_v$ (mm/s)")
        formatar(ax)
    axs[0].set_ylabel("Janelas marcadas (%)")
    axs[0].text(REF_MM_S + 0.08, 97, f"{num(REF_MM_S)} mm/s", ha="left", va="top", fontsize=6)
    itens = [(Patch(facecolor=CINZA_CLARO, lw=0), "Isolation Forest, sementes 0 a 9"),
             linha_maquinas("Isolation Forest, semente 0", lw=1.0),
             (Line2D([], [], color=PRETO, ls="--", lw=0.8), "Mediana e MAD")]
    legenda_maquinas(fig, itens, ncol=3)
    ajustar(fig, topo_mm=6)
    letras(fig, axs)
    salvar(fig, "fig_injecao")


if __name__ == "__main__":
    SAIDA.mkdir(parents=True, exist_ok=True)
    fig_ruido()
    fig_enlace()
    fig_espectros()
    fig_eixos()
    fig_injecao()
    print("figuras em", SAIDA)
