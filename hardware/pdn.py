"""Impedância do PDN de +3V3, com o caminho ROTEADO lido do .kicad_pcb.

Por que existe: `hardware/pcb/README.md` carrega o defeito #16 como
"N capacitores acima de 3 mm do pino que servem". Isso é regra de bolso, e
tem dois problemas.

O primeiro é que a distância medida é EUCLIDIANA, e o que entra na indutância
do laço é o comprimento da PISTA. Numa placa de duas camadas os dois números
divergem, e é o segundo que importa.

O segundo é que a lista de "desacoplamento" mistura categorias. Pela netlist
de +3V3 e +3V3_SW, só C2, C3, C7, C8, C10 e C4 desacoplam. C1 é o RC do EN,
C5 e C6 são o regulador interno e a bomba de carga do MPU6050 (que têm
exigência própria, de folha de dados, não de PDN), C9 é a entrada do LDO e
C11/C12 são filtros de nó de ADC. Aplicar a regra de 1-3 mm a todos eles
mede a coisa errada com precisão.

A versão quantitativa é a da indústria: montar Z(f) vista do pino de
alimentação de cada carga e comparar com uma impedância-alvo.

    uv run --no-project --with numpy --with matplotlib python hardware/pdn.py
"""
import heapq
import math
import os
import pathlib
import sys

import numpy as np

AQUI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
from sexpr import parse, find, find1  # noqa: E402

VERSOES = ("v1", "v2")

# --- empilhamento -----------------------------------------------------
# 2 camadas, 1,6 mm. O plano de retorno de uma pista em F.Cu está a ~1,5 mm
# — é MUITO longe, e é o que domina a indutância do laço nesta placa.
H_DIELETRICO = 1.5       # mm entre F.Cu e B.Cu
LARG_PISTA = 0.2         # mm
ESP_COBRE = 0.035        # mm
EPS_R = 4.3
VIA_FURO = 0.3           # mm
ESP_PLACA = 1.6          # mm

# --- capacitores ------------------------------------------------------
# ESL e ESR típicos de 0805 MLCC. O derate de tensão é o que separa uma
# análise de PDN de uma conta ingênua: um X5R de 10 uF em 0805 a 3,3 V perde
# perto de 40% da capacitância nominal. Valores declarados, não medidos.
MLCC = {
    "100n": dict(c=100e-9, esl=0.90e-9, esr=0.030, derate=0.90),
    "2n2":  dict(c=2.2e-9, esl=0.90e-9, esr=0.050, derate=0.95),
    "1u":   dict(c=1.0e-6, esl=0.90e-9, esr=0.020, derate=0.80),
    "10u":  dict(c=10.0e-6, esl=0.90e-9, esr=0.010, derate=0.60),
}

# --- alvo -------------------------------------------------------------
# Z_alvo = dV / dI. O degrau é o radio ligando o PA: 90 mA (SX1278 TX @17dBm,
# de src/power/sleep.cpp). A tolerancia de ondulacao adotada e 2% de 3,3 V.
# 2% e criterio de projeto, nao de folha de dados — declarado.
DEGRAU_A = 0.090
ONDULACAO = 0.02 * 3.3
Z_ALVO = ONDULACAO / DEGRAU_A

# Faixa util. Acima de ~50 MHz quem responde e a capacitancia do
# encapsulamento e do die, que este modelo nao tem: a curva alem disso e
# extrapolacao, e esta marcada como tal no grafico.
F = np.logspace(3, 8, 1100)
F_CONFIAVEL = 5e7

# --- fonte ------------------------------------------------------------
# Sem a fonte, |Z| so sobe quando a frequencia cai, e o "pico" da curva vira
# o primeiro ponto da varredura — que foi o que aconteceu na primeira versao
# deste arquivo. Quem segura a baixa frequencia e o regulador.
#
# HT7333: impedancia de saida da ordem de 0,2 ohm ate a banda da malha de
# controle, subindo como indutancia depois. Numeros de ordem de grandeza,
# nao de folha de dados — o HT7333 nao publica curva de Zout.
R_LDO, F_LDO = 0.2, 5e4
L_LDO = R_LDO / (2 * math.pi * F_LDO)

# O rail +3V3_SW nao tem fonte propria: vem do +3V3 atraves do Q1 (SI2301,
# R_DS(on) tipico 90 mOhm a 4,5 V_GS). Modelar o rail comutado so com o C4
# dava 176 ohm em 1 kHz — absurdo, porque ignorava que atras do C4 esta o
# PDN inteiro do +3V3.
R_DSON = 0.090


def l_via():
    """Indutância de uma via passante. L = (mu0*h/2pi)*[ln(4h/d)+1]."""
    h, d = ESP_PLACA * 1e-3, VIA_FURO * 1e-3
    return 2e-7 * h * (math.log(4 * h / d) + 1.0)


def l_por_mm():
    """Indutância de LAÇO por mm de microstrip: L' = Z0 / v_p.

    Z0 pela fórmula de Hammerstad. Como o retorno já está embutido em Z0,
    não se soma trecho de retorno depois — seria contar duas vezes.
    """
    h, w, t = H_DIELETRICO, LARG_PISTA, ESP_COBRE
    z0 = (87.0 / math.sqrt(EPS_R + 1.41)) * math.log(5.98 * h / (0.8 * w + t))
    eps_ef = (EPS_R + 1) / 2 + (EPS_R - 1) / 2 * (1 + 12 * h / w) ** -0.5
    vp = 3e11 / math.sqrt(eps_ef)          # mm/s
    return z0 / vp                          # H/mm


L_VIA = l_via()
L_MM = l_por_mm()


def v(tok):
    return tok[1] if isinstance(tok, tuple) else str(tok)


def le_placa(caminho):
    doc = parse(caminho.read_text())[0]
    nets = {int(v(n[1])): v(n[2]) for n in find(doc, "net") if len(n) > 2}
    segs, vias, pads = [], [], []
    for s in find(doc, "segment"):
        a, b = find1(s, "start"), find1(s, "end")
        segs.append(((float(v(a[1])), float(v(a[2]))),
                     (float(v(b[1])), float(v(b[2]))),
                     v(find1(s, "layer")[1]),
                     int(v(find1(s, "net")[1]))))
    for x in find(doc, "via"):
        a = find1(x, "at")
        vias.append(((float(v(a[1])), float(v(a[2]))),
                     int(v(find1(x, "net")[1]))))
    return nets, segs, vias, pads


def pads_do_gerador(versao):
    """Posições absolutas dos pads pela função do PRÓPRIO gerador.

    Recalcular isso aqui foi tentado e deu errado: footprint na face de baixo
    guarda a coordenada do pad na moldura da BIBLIOTECA, e o KiCad espelha na
    renderização. Reimplementar o espelhamento é reimplementar um bug. O
    `gen_pcb.py` já tem `pads_abs`, e é o mesmo código que gerou a placa —
    então usa-se ele, cortado antes do roteador para não rodar 50 s de A*.
    """
    import types
    os.environ["KAELIX_PCB"] = versao
    src = (AQUI / "gen_pcb.py").read_text()
    src = src[:src.index("# ================================================"
                         "=====================\n# Roteamento")]
    m = types.ModuleType("gp_pdn")
    m.__file__ = str(AQUI / "gen_pcb.py")
    exec(compile(src, "gen_pcb.py", "exec"), m.__dict__)
    fora = []
    for ref in m.POSICOES:
        _fp, _val, mapa = m.NET[ref]
        if not mapa:
            continue
        lado = m.POSICOES[ref][3]
        for p in m.pads_abs(ref):
            rede = mapa.get(p["num"])
            if rede is None or rede == m.SCH.NC:
                continue
            fora.append(dict(ref=ref, num=p["num"], x=p["x"], y=p["y"],
                             nome=rede,
                             camadas=(["F.Cu", "B.Cu"] if len(p["faces"]) > 1
                                      else [f"{lado}.Cu"])))
    return fora


def grafo(segs, vias, nid):
    """Grafo do cobre roteado de uma net. Nó = (x, y, camada) arredondado."""
    def no(p, cam):
        return (round(p[0], 2), round(p[1], 2), cam)
    g = {}
    def liga(a, b, peso, via):
        g.setdefault(a, []).append((b, peso, via))
        g.setdefault(b, []).append((a, peso, via))
    for a, b, cam, n in segs:
        if n != nid:
            continue
        liga(no(a, cam), no(b, cam), math.dist(a, b), 0)
    for p, n in vias:
        if n != nid:
            continue
        liga(no(p, "F.Cu"), no(p, "B.Cu"), 0.0, 1)
    return g


def encaixa(g, x, y, camadas, tol=0.35):
    """Nós do grafo que representam um pad (a grade do roteador é 0,1 mm)."""
    alvo = []
    for nd in g:
        if nd[2].replace(".Cu", "") + ".Cu" not in camadas and "*.Cu" not in camadas:
            continue
        if math.hypot(nd[0] - x, nd[1] - y) <= tol:
            alvo.append(nd)
    return alvo


def caminho(g, origem, destino):
    """Dijkstra ponderado pelo comprimento; devolve (mm, nº de vias)."""
    dist = {o: (0.0, 0) for o in origem}
    fila = [(0.0, 0, o) for o in origem]
    heapq.heapify(fila)
    alvo = set(destino)
    while fila:
        d, nv, u = heapq.heappop(fila)
        if u in alvo:
            return d, nv
        if d > dist.get(u, (math.inf, 0))[0] + 1e-9:
            continue
        for w, peso, via in g.get(u, ()):
            nd, nnv = d + peso, nv + via
            if nd < dist.get(w, (math.inf, 0))[0] - 1e-9:
                dist[w] = (nd, nnv)
                heapq.heappush(fila, (nd, nnv, w))
    return None, None


def z_cap(cfg, l_extra):
    c = cfg["c"] * cfg["derate"]
    l = cfg["esl"] + l_extra
    return cfg["esr"] + 1j * 2 * np.pi * F * l + 1.0 / (1j * 2 * np.pi * F * c)


# Capacitor -> (CI, pino de alimentação que ele serve)
SERVE = {"C2": ("U1", "2"), "C3": ("U1", "2"),
         "C7": ("U3", "3"), "C8": ("U3", "3"),
         "C10": ("U4", "3"), "C4": ("U2", "13")}
VALOR = {"C2": "100n", "C3": "10u", "C7": "100n", "C8": "10u",
         "C10": "1u", "C4": "100n"}
# Cargas: de onde se olha o PDN
CARGAS = [("U1", "2", "+3V3", "ESP32-S3"), ("U3", "3", "+3V3", "Ra-02")]

print(f"Z_alvo = {ONDULACAO * 1000:.0f} mV / {DEGRAU_A * 1000:.0f} mA "
      f"= {Z_ALVO * 1000:.0f} mOhm")
print(f"indutancia de via passante (1,6 mm / furo 0,3): {L_VIA * 1e9:.2f} nH")
print(f"indutancia de laco da microstrip 0,2 mm sobre {H_DIELETRICO} mm: "
      f"{L_MM * 1e12:.0f} pH/mm\n")

# Capacitores de cada rail, e de onde se olha o PDN
RAIL = {"+3V3": ["C2", "C3", "C7", "C8", "C10"], "+3V3_SW": ["C4"]}
CARGAS = [("+3V3", "U1", "2", "ESP32-S3"), ("+3V3", "U3", "3", "Ra-02"),
          ("+3V3_SW", "U2", "13", "MPU6050")]
Z_LDO = R_LDO + 1j * 2 * np.pi * F * L_LDO


def c_plano(area_mm2):
    """Capacitância entre os dois planos. Pequena, mas é o piso da curva."""
    return 8.854e-12 * EPS_R * (area_mm2 * 1e-6) / (H_DIELETRICO * 1e-3)


AREA = {"v1": 1466.0, "v2": 2950.0}          # de fem_modal.py

RESULTADO, CAPS = {}, {}
for ver in VERSOES:
    pcb = AQUI / "pcb" / ver / "kaelix.kicad_pcb"
    nets, segs, vias, _ = le_placa(pcb)
    num_da_rede = {nome: n for n, nome in nets.items()}
    pads = pads_do_gerador(ver)
    for p in pads:
        p["net"] = num_da_rede.get(p["nome"], -1)
    idx = {(p["ref"], p["num"]): p for p in pads}
    grafos = {}

    def caminho_ate(cap, ci, pino):
        pi = idx.get((ci, pino))
        if pi is None:
            return None
        pc = idx.get((cap, "1"))
        if pc is None or pc["net"] != pi["net"]:
            pc = idx.get((cap, "2"))
        if pc is None or pc["net"] != pi["net"]:
            return None
        g = grafos.setdefault(pi["net"], grafo(segs, vias, pi["net"]))
        o = encaixa(g, pc["x"], pc["y"], pc["camadas"])
        d = encaixa(g, pi["x"], pi["y"], pi["camadas"])
        if not o or not d:
            return None
        mm, nv = caminho(g, o, d)
        if mm is None:
            return None
        return (mm, nv, mm * L_MM + nv * L_VIA,
                math.dist((pc["x"], pc["y"]), (pi["x"], pi["y"])))

    caps_ver = {}
    print(f"=== {ver} — caminho roteado do capacitor ate o pino que ele serve ===")
    print(f"{'cap':<5} {'valor':<6} {'serve':<8} {'euclid':>7} {'pista':>7} "
          f"{'vias':>5} {'L laco':>9}  razao")
    print("-" * 64)
    for rail, caps in RAIL.items():
        for cap in caps:
            ci, pino = SERVE[cap]
            r = caminho_ate(cap, ci, pino)
            if r is None:
                print(f"{cap:<5} sem caminho ate {ci}.{pino}")
                continue
            mm, nv, l, eu = r
            caps_ver[cap] = (mm, nv, l, eu, ci, pino)
            print(f"{cap:<5} {VALOR[cap]:<6} {ci + '.' + pino:<8} {eu:6.2f}  "
                  f"{mm:6.2f}  {nv:4d}  {l * 1e9:6.2f} nH  {mm / eu:4.2f}x")
    print()

    def z_rail_3v3(ci, pino):
        ys = [1.0 / Z_LDO, 1j * 2 * np.pi * F * c_plano(AREA[ver])]
        for cap in RAIL["+3V3"]:
            r = caminho_ate(cap, ci, pino)
            if r is not None:
                ys.append(1.0 / z_cap(MLCC[VALOR[cap]], r[2]))
        return 1.0 / sum(ys)

    curvas = {}
    for rail, ci, pino, nome in CARGAS:
        if rail == "+3V3":
            z = z_rail_3v3(ci, pino)
        else:
            # fonte do rail comutado: o +3V3 visto na saida do LDO, mais o
            # canal do Q1 em serie; o C4 fica em paralelo com esse conjunto
            fonte = z_rail_3v3("U4", "3") + R_DSON
            r4 = caminho_ate("C4", ci, pino)
            ys = [1.0 / fonte]
            if r4 is not None:
                ys.append(1.0 / z_cap(MLCC[VALOR["C4"]], r4[2]))
            z = 1.0 / sum(ys)
        curvas[(rail, ci, pino, nome)] = np.abs(z)
    RESULTADO[ver] = curvas
    CAPS[ver] = caps_ver

    print(f"--- {ver}: |Z| visto de cada carga (alvo {Z_ALVO * 1000:.0f} mOhm) ---")
    for (rail, ci, pino, nome), z in curvas.items():
        util = F <= F_CONFIAVEL
        pico = float(z[util].max())
        f_pico = float(F[util][int(np.argmax(z[util]))])
        acima = F[util][z[util] > Z_ALVO]
        if acima.size:
            faixa = f"passa do alvo a partir de {acima.min() / 1e6:.1f} MHz"
        else:
            faixa = "abaixo do alvo em toda a faixa"
        print(f"  {nome:<10} ({ci}.{pino}, {rail:<8}) pico {pico * 1000:6.0f} mOhm "
              f"em {f_pico / 1e6:6.1f} MHz — {faixa}")
    print()


# ---------------------------------------------------------------------
# Dados para a figura
# ---------------------------------------------------------------------
# Este arquivo NÃO desenha. A figura é feita em R, como as demais do projeto
# (experiments/figures/scripts/*.R), e o que sai daqui é a fonte de dados.
import csv                                             # noqa: E402

DADOS = AQUI.parent / "experiments" / "figures" / "data"
DADOS.mkdir(parents=True, exist_ok=True)

with (DADOS / "fig9_pdn_impedancia.csv").open("w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["versao", "rail", "carga", "pino", "freq_hz", "z_ohm"])
    for ver, curvas in RESULTADO.items():
        for (rail, ci, pino, nome), z in curvas.items():
            for f_, z_ in zip(F, z):
                w.writerow([ver, rail, nome, f"{ci}.{pino}",
                            f"{f_:.6g}", f"{z_:.6g}"])

with (DADOS / "fig9_pdn_capacitores.csv").open("w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["versao", "cap", "valor", "serve", "euclid_mm", "pista_mm",
                "vias", "l_pista_nh", "l_vias_nh", "l_total_nh"])
    for ver, linhas in CAPS.items():
        for cap, (mm, nv, l, eu, ci, pino) in linhas.items():
            w.writerow([ver, cap, VALOR[cap], f"{ci}.{pino}",
                        f"{eu:.3f}", f"{mm:.3f}", nv,
                        f"{mm * L_MM * 1e9:.3f}", f"{nv * L_VIA * 1e9:.3f}",
                        f"{l * 1e9:.3f}"])

with (DADOS / "fig9_pdn_referencias.csv").open("w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["z_alvo_ohm", "degrau_a", "ondulacao_v", "f_confiavel_hz",
                "l_via_nh", "l_por_mm_ph", "r_ldo_ohm", "f_ldo_hz",
                "r_dson_ohm", "h_dieletrico_mm"])
    w.writerow([f"{Z_ALVO:.4f}", DEGRAU_A, f"{ONDULACAO:.4f}",
                f"{F_CONFIAVEL:.6g}", f"{L_VIA * 1e9:.3f}",
                f"{L_MM * 1e12:.1f}", R_LDO, f"{F_LDO:.6g}", R_DSON,
                H_DIELETRICO])

print(f"dados escritos em {DADOS}/fig9_pdn_*.csv")
print("figura: Rscript experiments/figures/scripts/fig9_pdn.R")
sys.stdout.flush()
