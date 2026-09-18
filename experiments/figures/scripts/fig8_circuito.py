"""Figura 8 — esquemático do circuito do Kaelix.

O CONTEÚDO vem de hardware/gen_schematic.py; só a geometria está aqui.

Por que assim: a versão anterior era um desenho paralelo, com pinos e
valores digitados à mão. Ela mostrava dois BC337 cortando o retorno a GND
do MPU6050 — um circuito que não existe mais no esquemático, e que não
funcionava (os pull-ups do I2C alimentavam o sensor pelos diodos de ESD).
Uma figura que repete a netlist de memória diverge em silêncio, e numa
figura a divergência é pior que num arquivo: ela é o que o leitor acredita.

Não há autoposicionamento aqui, e não deveria haver: um esquemático
legível é um desenho, não uma saída de algoritmo. O que existe é uma
VERIFICAÇÃO — ao final, o script confere pino a pino que tudo o que a
netlist declara aparece no desenho, e falha se faltar. Acrescentar um
componente ao esquemático sem desenhá-lo aqui quebra a geração.

Convenção: cruzamento de fios SEM ponto não é conexão.

Rodar:
    uv run --no-project --with cairosvg python \
        experiments/figures/scripts/fig8_circuito.py
"""

import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ / "hardware"))
import gen_schematic as SCH  # noqa: E402

OUT = pathlib.Path(__file__).resolve().parents[1] / "output"
OUT.mkdir(parents=True, exist_ok=True)

# Alinhado a scripts/theme_kaelix.R: mesma tinta, mesmo azul de sinal, mesmo
# vermelho de acento e mesmo cinza neutro das figuras em R. Antes este
# esquemático usava paleta e família próprias, e destoava das demais no PDF.
TINTA = "#272727"   # pal neutral_dark
ALIM = "#8C2D1E"    # pal accent_red
CORTE = "#3182BD"   # pal signal_blue
CINZA = "#767676"   # pal neutral_mid
FUNDO = "#ffffff"
CAIXA = "#fcfcfc"
# Serif, para casar com o corpo do TCC (pacote `times`), como no tema em R.
FONTE = "Times New Roman, Times, Nimbus Roman, serif"

S = []
DESENHADO = set()          # (ref, pino) já representados no desenho


# =====================================================================
# Netlist: a fonte da verdade
# =====================================================================
def netlist():
    r = {}
    for ref, _lb, _sn, _fp, val, _x, _y, mapa in SCH.COMPONENTES:
        r[ref] = (val, dict(mapa))
    for ref, _sn, _fp, val, _x, _y, n1, n2 in SCH.PASSIVOS:
        r[ref] = (val, {"1": n1, "2": n2})
    for ref, _lb, _sn, _fp, val, _x, _y, mapa in SCH.EXTRAS:
        r[ref] = (val, dict(mapa))
    return r


NET = netlist()


def valor(ref):
    return NET[ref][0]


def rede(ref, pino):
    return NET[ref][1][pino]


# =====================================================================
# Primitivas
# =====================================================================
def fio(x1, y1, x2, y2, cor=TINTA, w=1.7):
    S.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
             f'stroke="{cor}" stroke-width="{w}" stroke-linecap="round"/>')


def poli(pts, cor=TINTA, w=1.7, fill="none"):
    d = " ".join(f"{x},{y}" for x, y in pts)
    S.append(f'<polyline points="{d}" fill="{fill}" stroke="{cor}" '
             f'stroke-width="{w}" stroke-linejoin="round" stroke-linecap="round"/>')


def ponto(x, y, cor=TINTA, r=4.2):
    S.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{cor}"/>')


def txt(x, y, s, size=13, cor=TINTA, anc="middle", peso="normal"):
    for i, linha in enumerate(s.split("\n")):
        e = linha.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        S.append(f'<text x="{x}" y="{y + i * (size + 3)}" font-family="{FONTE}" '
                 f'font-size="{size}" fill="{cor}" text-anchor="{anc}" '
                 f'font-weight="{peso}">{e}</text>')


def caixa(x1, y1, x2, y2, cor=TINTA, w=2.0):
    S.append(f'<rect x="{x1}" y="{y1}" width="{x2-x1}" height="{y2-y1}" rx="3" '
             f'fill="{CAIXA}" stroke="{cor}" stroke-width="{w}"/>')


def bloco(x1, y1, x2, y2, ref, sub=None, cor=TINTA):
    caixa(x1, y1, x2, y2, cor)
    cx = (x1 + x2) / 2
    txt(cx, y1 + 21, valor(ref), size=14, cor=cor, peso="bold")
    txt(x1 + 8, y1 + 21, ref, size=11, cor=CINZA, anc="start")
    if sub:
        txt(cx, y1 + 37, sub, size=10.5, cor=CINZA)


def resistor(x, y, comp, vert=True, cor=TINTA, w=1.7):
    n, amp = 6, 8
    if vert:
        y0 = y - comp / 2
        passo = comp / n
        pts = [(x, y0)] + [(x + (amp if i % 2 == 0 else -amp), y0 + passo * (i + 0.5))
                           for i in range(n)] + [(x, y0 + comp)]
    else:
        x0 = x - comp / 2
        passo = comp / n
        pts = [(x0, y)] + [(x0 + passo * (i + 0.5), y + (amp if i % 2 == 0 else -amp))
                           for i in range(n)] + [(x0 + comp, y)]
    poli(pts, cor, w)


def capacitor(x, y, cor=TINTA):
    """Placas horizontais centradas em (x, y); terminais a +/- 14."""
    fio(x, y - 14, x, y - 4, cor)
    fio(x - 12, y - 4, x + 12, y - 4, cor, w=2.4)
    fio(x - 12, y + 4, x + 12, y + 4, cor, w=2.4)
    fio(x, y + 4, x, y + 14, cor)


def terra(x, y, cor=TINTA):
    fio(x, y, x, y + 12, cor)
    for i, meia in enumerate((14, 9, 4)):
        fio(x - meia, y + 12 + i * 5, x + meia, y + 12 + i * 5, cor, w=1.9)


def antena(x, y, cor=CINZA):
    fio(x, y, x, y - 24, cor)
    poli([(x - 16, y - 44), (x, y - 24), (x + 16, y - 44)], cor)


# --- marcação de pinos: é isto que a verificação final consome ---
def usa(ref, *pinos):
    for p in pinos:
        DESENHADO.add((ref, p))


def gnd(x, y, ref, pino, cor=TINTA):
    assert rede(ref, pino) == "GND", f"{ref}.{pino} não é GND"
    terra(x, y, cor)
    usa(ref, pino)


def tap(x, y, y_trilho, ref, pino, cor=ALIM):
    """Sobe (ou desce) até o trilho de alimentação e marca a junção."""
    fio(x, y, x, y_trilho, cor)
    ponto(x, y_trilho, cor)
    usa(ref, pino)


# =====================================================================
# Geometria
# =====================================================================
Y3V3 = 96          # trilho +3V3
YSW = 470          # trilho +3V3_SW

# ---------------------------------------------------------------------
# Entrada de energia: J1 -> U4 -> +3V3
# ---------------------------------------------------------------------
bloco(30, 66, 140, 126, "J1", "bateria", ALIM)
gnd(110, 126, "J1", "2", ALIM)

# Q3: proteção de polaridade invertida, em série com a entrada.
# DRENO na bateria, FONTE na carga — é a orientação que põe o diodo de corpo
# CONTRA a corrente reversa. Bateria invertida: diodo bloqueado e Vgs = 0.
fio(140, Y3V3, 196, Y3V3, ALIM); usa("Q3", "3"); usa("J1", "1")
fio(196, Y3V3, 196, 146, ALIM)
fio(196, 146, 196, 196, TINTA, w=2.6)                 # canal
fio(178, 154, 178, 188, TINTA, w=2.2)                 # gate
fio(178, 171, 196, 171)
S.append(f'<polygon points="196,171 182,165 182,177" fill="{TINTA}"/>')
fio(150, 171, 178, 171); fio(150, 171, 150, 186)
gnd(150, 186, "Q3", "1")
fio(196, 196, 232, 196, ALIM); fio(232, 196, 232, Y3V3, ALIM)
fio(232, Y3V3, 250, Y3V3, ALIM); usa("Q3", "2")
txt(212, 166, "Q3", size=11, cor=CINZA, anc="start")
txt(212, 182, valor("Q3"), size=10.5, cor=CINZA, anc="start")

bloco(250, 66, 370, 126, "U4", "LDO · Iq ~8 µA", ALIM)
usa("U4", "1")
gnd(310, 126, "U4", "2", ALIM)
fio(370, Y3V3, 1570, Y3V3, ALIM, w=2.2); usa("U4", "3")
txt(760, Y3V3 - 12, "+3V3", size=13, cor=ALIM, peso="bold")

capacitor(246, 246); fio(246, 232, 246, 196); ponto(232, 196, ALIM)
fio(232, 196, 246, 196, ALIM); usa("C9", "1")
gnd(246, 260, "C9", "2")
txt(264, 250, f"C9 {valor('C9')}", size=10.5, cor=CINZA, anc="start")

capacitor(400, 176); tap(400, 162, Y3V3, "C10", "1")
gnd(400, 190, "C10", "2")
txt(418, 180, f"C10 {valor('C10')}", size=10.5, cor=CINZA, anc="start")

# --- divisor de medição da bateria -----------------------------------
# Fica em VBAT (depois da proteção) e não em VBAT_RAW: medir antes de Q3
# leria a bateria mesmo com ela invertida, e a queda no canal é de 8 mV.
ponto(232, 150, ALIM)
fio(232, 150, 90, 150, ALIM); fio(90, 150, 90, 196, ALIM)
resistor(90, 224, 56, cor=ALIM); usa("R9", "1")
fio(90, 252, 90, 268); ponto(90, 268); usa("R9", "2")
txt(76, 228, f"R9 {valor('R9')}", size=10.5, cor=ALIM, anc="end")
fio(90, 268, 90, 296)
resistor(90, 324, 56); usa("R10", "1")
fio(90, 352, 90, 368); gnd(90, 368, "R10", "2")
txt(76, 328, f"R10 {valor('R10')}", size=10.5, anc="end")

# ---------------------------------------------------------------------
# Load switch: Q1 (P-MOSFET) comuta +3V3 -> +3V3_SW; Q2 (NPN) inverte
# ---------------------------------------------------------------------
GX, QX, BX = 500, 630, 380          # gate, Q1, base de Q2

fio(GX, 200, GX, 340, ALIM)
resistor(GX, 250, 56, cor=ALIM)
tap(GX, 200, Y3V3, "R4", "1"); usa("R4", "2")
txt(GX - 14, 254, f"R4 {valor('R4')}", size=10.5, cor=ALIM, anc="end")

# Q1: fonte em +3V3, dreno em +3V3_SW
fio(QX, Y3V3, QX, 300, ALIM); ponto(QX, Y3V3, ALIM); usa("Q1", "2")
fio(QX - 26, 300, QX - 26, 380, TINTA, w=2.6)
fio(QX - 26, 300, QX, 300, ALIM)
fio(QX - 44, 322, QX - 44, 358, TINTA, w=2.2)
fio(QX - 44, 340, QX - 26, 340)
S.append(f'<polygon points="{QX-26},{340} {QX-11},{334} {QX-11},{346}" fill="{TINTA}"/>')
fio(GX, 340, QX - 44, 340); usa("Q1", "1")
fio(QX - 26, 380, QX, 380); fio(QX, 380, QX, YSW, CORTE)
ponto(QX, YSW, CORTE); usa("Q1", "3")
txt(QX - 78, 262, "Q1", size=11, cor=CINZA, anc="start")
txt(QX - 78, 278, valor("Q1"), size=10.5, cor=CINZA, anc="start")

# Q2: coletor no gate, emissor em GND
ponto(GX, 340)
fio(GX, 340, GX, 376); fio(GX, 376, BX + 26, 376)
fio(BX, 384, BX, 444, TINTA, w=2.6)
fio(BX, 392, BX + 26, 376); usa("Q2", "3")
fio(BX, 436, BX + 26, 452)
S.append(f'<polygon points="{BX+14},{446} {BX+3},{441} {BX+8},{454}" fill="{TINTA}"/>')
fio(BX + 26, 452, BX + 26, 476); gnd(BX + 26, 476, "Q2", "2")
txt(BX + 42, 400, "Q2", size=11, cor=CINZA, anc="start")
txt(BX + 42, 416, valor("Q2"), size=10.5, cor=CINZA, anc="start")

YEN = 548

# R5 na entrada e R8 no NÓ DA BASE, não o contrário: o pull-down tem de
# segurar a junção base-R5, que é o ponto que fica solto quando o GPIO vai a
# alta impedância. Do lado do GPIO ele não seguraria nada.
BAX = 340                                   # nó PERIPH_BASE
fio(BAX, 290, BAX, 370)
resistor(BAX, 330, 56)
txt(BAX - 14, 334, f"R5 {valor('R5')}", size=10.5, anc="end")
usa("R5", "1"); usa("R5", "2")
fio(BAX, 370, BAX, 414); fio(BAX, 414, BX, 414); usa("Q2", "1")
ponto(BAX, 414)
fio(BAX, 414, 170, 414); fio(170, 414, 170, 430)
resistor(170, 458, 56); usa("R8", "1")
fio(170, 486, 170, 502); gnd(170, 502, "R8", "2")
txt(156, 462, f"R8 {valor('R8')}", size=10.5, anc="end")

# PERIPH_EN sobe do IO5 e entra por cima do load switch: dois cruzamentos
# limpos, contra cinco se passasse por baixo do trilho comutado.
# y=195 e não 250: em 250 a linha passaria POR DENTRO do zigue-zague do R4.
# Cruzar fio sem ponto é convenção; cruzar símbolo é erro de desenho.
fio(674, 548, 660, 548); fio(660, 548, 660, 210); fio(660, 210, BAX, 210)
fio(BAX, 210, BAX, 290)
txt(560, 200, "PERIPH_EN  (IO5)", size=11)

# trilho comutado
fio(120, YSW, QX, YSW, CORTE, w=2.2)
txt(330, YSW - 14, "+3V3_SW", size=13, cor=CORTE, peso="bold", anc="start")

# ---------------------------------------------------------------------
# MPU6050
# ---------------------------------------------------------------------
MX1, MY1, MX2, MY2 = 130, 640, 340, 800
bloco(MX1, MY1, MX2, MY2, "U2", "I2C 0x68 · 3,9 mA", CORTE)
tap(200, MY1, YSW, "U2", "8", CORTE); tap(250, MY1, YSW, "U2", "13", CORTE)
txt(225, MY1 + 54, "VDD / VLOGIC", size=10.5, cor=CINZA)
for x, p in ((160, "1"), (190, "9"), (220, "11"), (250, "18")):
    fio(x, MY2, x, MY2 + 8, CORTE); gnd(x, MY2 + 8, "U2", p, CORTE)
txt(205, MY2 + 76, "GND · CLKIN, AD0 e FSYNC aterrados;", size=10.5, cor=CINZA)
txt(205, MY2 + 90, "AD0 = 0 fixa o endereço 0x68 do firmware", size=10.5, cor=CINZA)

YSDA, YSCL = 690, 726
for y, p, nome in ((YSDA, "24", "SDA"), (YSCL, "23", "SCL")):
    fio(MX2, y, MX2 + 24, y, CORTE); usa("U2", p)
    txt(MX2 - 10, y + 5, nome, size=12, cor=CORTE, anc="end")

capacitor(305, 850); fio(305, 836, 305, MY2, CORTE)
usa("C4", "1"); gnd(305, 864, "C4", "2")
txt(323, 854, f"C4 {valor('C4')}", size=10.5, cor=CINZA, anc="start")

fio(MX1, YSDA, 60, YSDA, CORTE) if False else None
fio(MX1, 676, 62, 676, CORTE); usa("U2", "10")
txt(MX1 + 10, 681, "REGOUT", size=11, cor=CINZA, anc="start")
capacitor(62, 712); fio(62, 676, 62, 698, CORTE)
usa("C5", "1"); gnd(62, 726, "C5", "2")
txt(80, 704, f"C5 {valor('C5')}", size=10.5, cor=CINZA, anc="start")

fio(MX1, 764, 62, 764, CORTE); usa("U2", "20")
txt(MX1 + 10, 769, "CPOUT", size=11, cor=CINZA, anc="start")
capacitor(62, 816); fio(62, 764, 62, 802, CORTE)
usa("C6", "1"); gnd(62, 830, "C6", "2")
txt(80, 808, f"C6 {valor('C6')}", size=10.5, cor=CINZA, anc="start")

# pull-ups do I2C: no rail COMUTADO, e é isso que faz o corte valer.
# Em +3V3 fixo eles alimentariam o MPU6050 pelos diodos de ESD de SDA/SCL.
for x, rref, ynet in ((410, "R2", YSDA), (460, "R3", YSCL)):
    fio(x, YSW, x, 600, CORTE); ponto(x, YSW, CORTE); usa(rref, "1")
    resistor(x, 628, 56, cor=CORTE)
    fio(x, 656, x, ynet, CORTE); usa(rref, "2"); ponto(x, ynet, CORTE)
    txt(x + 12, 632, f"{rref} {valor(rref)}", size=10.5, cor=CORTE, anc="start")
fio(MX2 + 24, YSDA, 674, YSDA, CORTE)
fio(MX2 + 24, YSCL, 674, YSCL, CORTE)

# ---------------------------------------------------------------------
# Divisor do NTC
# ---------------------------------------------------------------------
NX, YADC = 570, 790
fio(NX, YSW, NX, YADC - 62, CORTE); ponto(NX, YSW, CORTE); usa("R1", "1")
resistor(NX, YADC - 34, 56, cor=CORTE)
txt(NX - 12, YADC - 30, f"R1 {valor('R1')}", size=10.5, cor=CORTE, anc="end")
fio(NX, YADC - 6, NX, YADC + 6, CORTE); ponto(NX, YADC); usa("R1", "2")
fio(NX, YADC, 674, YADC)
fio(NX, YADC, 520, YADC); ponto(NX, YADC)
fio(520, YADC, 520, 812)
capacitor(520, 826); usa("C12", "1"); gnd(520, 840, "C12", "2")
txt(502, 818, f"C12 {valor('C12')}", size=10.5, cor=CINZA, anc="end")
resistor(NX, YADC + 40, 56, cor=CORTE); usa("RT1", "1")
fio(NX, YADC + 68, NX, YADC + 84, CORTE); gnd(NX, YADC + 84, "RT1", "2", CORTE)
txt(NX + 14, YADC + 44, f"RT1 {valor('RT1')}", size=10.5, cor=CORTE, anc="start")

# ---------------------------------------------------------------------
# ESP32-S3
# ---------------------------------------------------------------------
EX1, EY1, EX2, EY2 = 700, 300, 1000, 900
bloco(EX1, EY1, EX2, EY2, "U1", "16 MB flash · 8 MB PSRAM")
YEN_PIN = 860
YVB = 610
for p, nome, y in (("5", "IO5   PERIPH_EN", YEN), ("6", "IO6   VBAT_SENSE", YVB),
                   ("12", "IO8   SDA", YSDA),
                   ("17", "IO9   SCL", YSCL), ("4", "IO4   ADC1_CH3", YADC),
                   ("3", "EN", YEN_PIN)):
    fio(EX1 - 26, y, EX1, y); usa("U1", p)
    txt(EX1 + 10, y + 5, nome, size=11.5, anc="start")

# VBAT_SENSE: divisor junto da fonte, capacitor de reservatório junto do ADC.
# É no pino do ADC que o sample-and-hold puxa carga, e é a pista de 500 k de
# impedância que precisa terminar em baixa impedância.
fio(90, 268, 90, YVB); fio(90, YVB, EX1 - 26, YVB)
ponto(520, YVB)
fio(520, YVB, 520, 636)
capacitor(520, 650); usa("C11", "1"); gnd(520, 664, "C11", "2")
txt(538, 642, f"C11 {valor('C11')}", size=10.5, cor=CINZA, anc="start")

PINOS_DIR = [("18", "IO10  NSS", 360), ("19", "IO11  MOSI", 400),
             ("20", "IO12  SCK", 440), ("21", "IO13  MISO", 480),
             ("22", "IO14  DIO0", 520), ("23", "IO21  RST", 560)]
for p, nome, y in PINOS_DIR:
    fio(EX2, y, EX2 + 26, y); usa("U1", p)
    txt(EX2 - 10, y + 5, nome, size=11.5, anc="end")
for p, nome, y in (("37", "TXD0", 660), ("36", "RXD0", 700), ("27", "IO0", 740)):
    fio(EX2, y, EX2 + 26, y); usa("U1", p)
    txt(EX2 - 10, y + 5, nome, size=11.5, anc="end")

tap(850, EY1, Y3V3, "U1", "2")
txt(850, EY1 + 54, "3V3", size=10.5, cor=CINZA)
for x, p in ((790, "1"), (850, "40"), (910, "41")):
    fio(x, EY2, x, EY2 + 8); gnd(x, EY2 + 8, "U1", p)
txt(850, EY2 + 74, "GND — o pad térmico (41) leva 12 vias ao plano de baixo",
    size=10.5, cor=CINZA)

capacitor(1050, 184); tap(1050, 170, Y3V3, "C2", "1"); gnd(1050, 198, "C2", "2")
capacitor(1110, 184); tap(1110, 170, Y3V3, "C3", "1"); gnd(1110, 198, "C3", "2")
txt(1080, 240, f"C2 {valor('C2')} · C3 {valor('C3')} — desacoplamento do U1,",
    size=10.5, cor=CINZA)
txt(1080, 254, "na mesma face do módulo", size=10.5, cor=CINZA)

# rede de reset (EN): pull-up e capacitor
REN = 626
fio(EX1 - 26, YEN_PIN, REN, YEN_PIN); ponto(REN, YEN_PIN)
fio(REN, YEN_PIN, REN, 900)
capacitor(REN, 936); usa("C1", "1"); gnd(REN, 950, "C1", "2")
txt(REN + 18, 928, f"C1 {valor('C1')}", size=10.5, cor=CINZA, anc="start")
# O corpo do R6 fica acima das horizontais de SDA (690), SCL (726) e do nó do
# ADC (790): a linha do EN as cruza, mas nenhum símbolo se sobrepõe a fio.
fio(REN, YEN_PIN, REN, 678, ALIM)
resistor(REN, 650, 56, cor=ALIM)
fio(REN, 622, REN, Y3V3, ALIM); ponto(REN, Y3V3, ALIM)
usa("R6", "1"); usa("R6", "2")
txt(REN - 14, 654, f"R6 {valor('R6')}", size=10.5, cor=ALIM, anc="end")

# pull-up do IO0
RIO = 1100
fio(EX2 + 26, 740, RIO, 740); ponto(RIO, 740)
fio(RIO, 740, RIO, 706)
resistor(RIO, 678, 56, cor=ALIM)
fio(RIO, 650, RIO, 300)
fio(RIO, 300, RIO, Y3V3, ALIM); ponto(RIO, Y3V3, ALIM); usa("R7", "1")
usa("R7", "2")
txt(RIO + 14, 682, f"R7 {valor('R7')}", size=10.5, cor=ALIM, anc="start")

# ---------------------------------------------------------------------
# RA-02
# ---------------------------------------------------------------------
RX1, RY1, RX2, RY2 = 1220, 300, 1440, 620
bloco(RX1, RY1, RX2, RY2, "U3", "433 MHz · 17 dBm")
for (p, nome, y), (_up, _un, _uy) in zip(
        [("15", "NSS", 360), ("14", "MOSI", 400), ("12", "SCK", 440),
         ("13", "MISO", 480), ("5", "DIO0", 520), ("4", "RESET", 560)], PINOS_DIR):
    fio(RX1 - 26, y, RX1, y); usa("U3", p)
    txt(RX1 + 10, y + 5, nome, size=11.5, anc="start")
    fio(EX2 + 26, y, RX1 - 26, y)
tap(1330, RY1, Y3V3, "U3", "3")
txt(1330, RY1 + 54, "VDD", size=10.5, cor=CINZA)
for x, p in ((1260, "1"), (1300, "2"), (1360, "9"), (1400, "16")):
    fio(x, RY2, x, RY2 + 8); gnd(x, RY2 + 8, "U3", p)
txt(1330, RY2 + 62, "GND", size=10.5, cor=CINZA)
antena(1520, 400); fio(RX2, 400, 1520, 400, CINZA)
txt(1520, 428, "u.FL", size=10.5, cor=CINZA)

capacitor(1490, 184); tap(1490, 170, Y3V3, "C7", "1"); gnd(1490, 198, "C7", "2")
capacitor(1550, 184); tap(1550, 170, Y3V3, "C8", "1"); gnd(1550, 198, "C8", "2")
txt(1520, 240, f"C7 {valor('C7')} · C8 {valor('C8')}", size=10.5, cor=CINZA)

# ---------------------------------------------------------------------
# Header UART/BOOT
# ---------------------------------------------------------------------
JX1, JY1, JX2, JY2 = 1220, 880, 1440, 990
bloco(JX1, JY1, JX2, JY2, "J2", "gravação e console")
gnd(1250, JY2, "J2", "1")
fio(1290, JY1, 1290, 840, ALIM); fio(1290, 840, 1610, 840, ALIM)
fio(1610, 840, 1610, Y3V3, ALIM); ponto(1610, Y3V3, ALIM); usa("J2", "2")
txt(1290, JY1 - 8, "+3V3", size=10, cor=ALIM)
for x, p, nome, orig in ((1340, "3", "TX", 660), (1390, "4", "RX", 700)):
    fio(x, JY1, x, orig); usa("J2", p)
    fio(EX2 + 26, orig, x, orig)
    txt(x, JY1 - 8, nome, size=10)
# EN e IO0 do header
fio(JX1 - 60, 920, JX1, 920); fio(JX1 - 60, 920, JX1 - 60, YEN_PIN)
fio(REN, YEN_PIN, JX1 - 60, YEN_PIN); usa("J2", "5")
txt(JX1 - 68, 925, "EN", size=11, anc="end")
fio(JX1 - 100, 960, JX1, 960); fio(JX1 - 100, 960, JX1 - 100, 740)
fio(RIO, 740, JX1 - 100, 740); usa("J2", "6")
txt(JX1 - 108, 965, "IO0", size=11, anc="end")

# =====================================================================
# Legendas
# =====================================================================
txt(840, 1080,
    "GPIO5 em nível alto liga o rail +3V3_SW pelo load switch Q2/Q1. Em nível baixo — ou com o pino solto, "
    "graças ao R8 — o rail cai a zero e",
    size=12, cor=TINTA)
txt(840, 1098,
    "leva junto o MPU6050, os pull-ups do I2C e o topo do divisor do NTC. Cortar só o retorno a GND não "
    "desligaria o sensor: os pull-ups",
    size=12, cor=TINTA)
txt(840, 1116,
    "continuariam em +3V3 e o alimentariam pelos diodos de ESD de SDA/SCL.",
    size=12, cor=TINTA)
txt(840, 1142,
    "O rádio NÃO está no rail comutado: lora_sleep() por software é obrigatório (1,5 mA x 720 s = 1093 mA·s por ciclo).",
    size=12, cor=ALIM)
txt(840, 1166,
    "Pinos, valores e conexões extraídos de hardware/gen_schematic.py e conferidos pino a pino na geração. "
    "Cruzamento sem ponto não é conexão.",
    size=11.5, cor=CINZA)

# =====================================================================
# Verificação: o desenho contra a netlist
# =====================================================================
esperado = {(ref, p) for ref, (_v, mapa) in NET.items()
            for p, n in mapa.items() if n != SCH.NC}
faltando = sorted(esperado - DESENHADO)
sobrando = sorted(DESENHADO - esperado)
if faltando or sobrando:
    if faltando:
        print(f"FALTA no desenho ({len(faltando)}): "
              + ", ".join(f"{r}.{p}[{rede(r, p)}]" for r, p in faltando))
    if sobrando:
        print(f"DESENHADO e não na netlist ({len(sobrando)}): "
              + ", ".join(f"{r}.{p}" for r, p in sobrando))
    raise SystemExit("figura divergente da netlist — corrija o desenho ou o esquemático")

# =====================================================================
# Escrita
# =====================================================================
W, H = 1700, 1200
svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
       f'viewBox="0 0 {W} {H}">'
       f'<rect width="{W}" height="{H}" fill="{FUNDO}"/>' + "".join(S) + "</svg>")
(OUT / "fig8_circuito.svg").write_text(svg, encoding="utf-8")

try:
    import cairosvg
    cairosvg.svg2png(bytestring=svg.encode(), write_to=str(OUT / "fig8_circuito.png"),
                     scale=2.0, background_color="white")
    cairosvg.svg2pdf(bytestring=svg.encode(), write_to=str(OUT / "fig8_circuito.pdf"))
    print(f"gerado: {OUT}/fig8_circuito.{{svg,png,pdf}}  "
          f"({len(esperado)} pinos conferidos contra a netlist)")
except ImportError:
    print(f"gerado: {OUT}/fig8_circuito.svg  (instale cairosvg para PNG/PDF)")
