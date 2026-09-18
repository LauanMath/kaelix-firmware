"""Modela o invólucro a partir das cotas do desenho, em três peças.

Fonte: docs/device/IMG_5298.jpeg, versão 4 (Lauan Alves, TCC Eng. de Software,
ICEV). Cada cota abaixo traz a vista de onde saiu. Onde o desenho não cota,
está dito de onde veio o número — e onde ele não fecha, está dito também.

Por que modelar
---------------
O desenho existe em papel e a única forma dele no repositório era uma foto.
Com sólido dá para: conferir encaixe da placa em geometria, e não por
comparação de um escalar (o "vão 43,0 contra 42,0 de placa" que eu vinha
usando não vê o corredor do cabo, nem o boss no canto, nem a altura do
header); e alimentar um FEM térmico, que hoje é uma rede de resistências 1D.

Duas versões
------------
v1  É o desenho, como está: quadrado de 50 x 50 x 62, vão de 43 x 43. Fica
    congelada — é o que a eletrônica atual atende e o que está no relatório.
    Limitação conhecida e medida: a LiPo de 2000 mAh que o orçamento de
    energia assume (Adafruit 2011, 60,0 x 37,0 x 7,5) NÃO entra num vão de
    43. A maior célula de catálogo que entra tem 500 mAh, o que dá 66 dias
    contra os 243 do REQ-PWR-06.

v2  Invólucro moldado À BATERIA, não ao contrário. Retangular, dimensionado
    pela célula real de 2000 mAh e pela placa, que continua a mesma — nada de
    eletrônica muda aqui. Sai menor em volume que a v1 e 24 mm mais baixa.

O QUE ESTE MODELO NÃO É
-----------------------
Não é o desenho de fabricação. O próprio desenho está marcado "COTAS NÃO
TRAVADAS" e "medir com paquímetro no componente físico antes da impressão
final". Isto aqui é a leitura das cotas publicadas, para conferência e
simulação — se a peça impressa medir diferente, o certo é a peça.

Rodar:  /Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd \\
            hardware/gen_involucro.py
"""

import math
import os
import pathlib
import sys

import Part
from FreeCAD import Vector

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

AQUI = pathlib.Path(__file__).resolve().parent
SAIDA = AQUI / "involucro"

# ---------------------------------------------------------------------
# Cotas — vista 1: CORPO, corte frontal
# ---------------------------------------------------------------------
# CORPO_EXT e CORPO_ALT saem do vão e das paredes; ver VERSOES.
PAREDE = 3.5
FUNDO = 8.0

USB_D = 13.0              # "USB-C Ø13,0" — o desenho anota: provisório
SMA_D = 6.5               # "antena SMA Ø6,5"
ARRUELA_D = 8.0           # "rebaixo arruela de vedação Ø8"
PINO_D, PINO_H = 3.3, 3.3         # "furo pino Ø3,3 x 3,3"
REB_SPIGOT_D, REB_SPIGOT_H = 28.4, 3.3   # "rebaixo spigot Ø28,4 x 3,3"

# ---------------------------------------------------------------------
# Cotas — vista 2: CORPO, vista superior
# ---------------------------------------------------------------------

R_CANTO = 7.0             # "R7"
# 36,0 entre eixos num vão de 43 põe o eixo do boss a 3,5 da parede
# interna. A v2 mantém a mesma relação.
BOSS_RECUO = 3.5
BOSS_D = 11.0             # "boss M3 Ø11"
BOSS_FURO = 2.6           # "furo-guia Ø2,6"

# ---------------------------------------------------------------------
# Cotas — vista 3: TAMPA, vista inferior
# ---------------------------------------------------------------------
# spigot da tampa: 0,5 menor que o vão (42,5 num vão de 43)
SPIGOT_FOLGA, SPIGOT_TAMPA_H = 0.5, 3.0
GAXETA_L, GAXETA_P = 3.0, 2.2                # "canal gaxeta 3,0 x 2,2 prof."
TAMPA_FURO, TAMPA_REBAIXO = 3.4, 7.0         # "4x Ø3,4 + rebaixo Ø7 p/ arruela"
# NÃO COTADA no desenho. 3,5 vem de export_enclosure_data.py, que modela a
# tampa como CORPO_EXT x CORPO_EXT x PAREDE.
TAMPA_ESP = 3.5

# ---------------------------------------------------------------------
# Cotas — vistas 4 e 5: BASE DE FIXAÇÃO
# ---------------------------------------------------------------------
BASE_LADO = 54.0
BASE_ALT = 9.0            # vista 5
SPIGOT_D, SPIGOT_H = 28.0, 3.3
MAG_D, MAG_P, MAG_R = 10.0, 3.2, 20.0   # "4x ímã Ø10x3", bolso 3,2, em R20
PINO_ORI_D, PINO_ORI_R = 3.0, 10.0      # "pino orientação Ø3 a 10,0 do centro"
PINO_ORI_SAI = 3.0                      # "pino sai 3,0 acima do spigot"
INSERTO_D = 4.0                         # "inserto térmico M3 Ø4,0"

VERSOES = {
    # v1 CONGELADA: é o desenho como está. A não-adequação da bateria é
    # limitação conhecida e medida, não falha de geração — por isso entra em
    # `limitacao` e não derruba a compilação.
    "v1": dict(
        vao=(43.0, 43.0), vao_alt=54.0, boss_d=11.0, boss_recuo=3.5,
        bateria="lipo-500mah-adafruit1578.step",
        limitacao="bateria",
        nota="o desenho como está; nenhuma célula de catálogo livra os postes Ø11"),
    # A v2 é dimensionada RESOLVENDO a restrição, não chutando: a cavidade é a
    # menor que deixa a célula de 60 x 37 E a placa livrarem os quatro bosses.
    # A placa da v2 (61 x 51, gen_pcb.py) foi depois desenhada PARA esta
    # cavidade, com os mesmos recortes de canto — não é ela que manda aqui. Com o Ø11 do desenho isso exigiria um corpo de 87 x 51 —
    # o poste no canto é que manda, não a bateria. O inserto térmico M3 do
    # próprio desenho tem Ø4,0, e Ø8 de ASA em volta dele é folgado; com Ø8 a
    # cavidade cai para 62 x 52.
    "v2": dict(
        vao=(62.0, 52.0), vao_alt=30.0, boss_d=8.0, boss_recuo=2.5,
        bateria="lipo-2000mah-adafruit2011.step",
        nota="moldado à célula real de 2000 mAh (60,0 x 37,0); boss Ø8"),
}

ALTURA_TOTAL_DESENHO = 78.0             # vista 6: "50,0 x 78,0 TOTAL"
MASSA_DESENHO = 118.0                   # "Massa estimada: ~118 g de ASA"
RHO_ASA = 1070.0                        # kg/m3, de export_enclosure_data.py


# ---------------------------------------------------------------------
# Primitivas
# ---------------------------------------------------------------------
def caixa(lx, ly, alt, raio, z0=0.0):
    """Prisma retangular com os quatro cantos verticais em raio."""
    s = Part.makeBox(lx, ly, alt, Vector(-lx / 2, -ly / 2, z0))
    r = min(raio, lx / 2 - 0.1, ly / 2 - 0.1)
    verticais = [e for e in s.Edges
                 if abs(e.Length - alt) < 1e-6
                 and abs(e.Vertexes[0].Point.x - e.Vertexes[1].Point.x) < 1e-6
                 and abs(e.Vertexes[0].Point.y - e.Vertexes[1].Point.y) < 1e-6]
    return s.makeFillet(r, verticais) if verticais and r > 0.05 else s


def cil(d, h, x=0.0, y=0.0, z=0.0, eixo=(0, 0, 1)):
    return Part.makeCylinder(d / 2.0, h, Vector(x, y, z), Vector(*eixo))


def bosses_xy(vao, recuo):
    """Eixos dos quatro bosses, recuados `recuo` da parede interna."""
    bx, by = vao[0] / 2 - recuo, vao[1] / 2 - recuo
    return [(sx * bx, sy * by) for sx in (-1, 1) for sy in (-1, 1)]


def diagonais(r):
    d = r / math.sqrt(2.0)
    return [(sx * d, sy * d) for sx in (-1, 1) for sy in (-1, 1)]


# ---------------------------------------------------------------------
# Peças
# ---------------------------------------------------------------------
def corpo(vao, vao_alt, boss_d, recuo):
    cx, cy = vao[0] + 2 * PAREDE, vao[1] + 2 * PAREDE
    alt = vao_alt + FUNDO
    p = caixa(cx, cy, alt, R_CANTO)
    p = p.cut(caixa(vao[0], vao[1], vao_alt + 1.0,
                    max(R_CANTO - PAREDE, 0.5), z0=FUNDO))
    for x, y in bosses_xy(vao, recuo):
        p = p.fuse(cil(boss_d, vao_alt, x, y, FUNDO))
        p = p.cut(cil(BOSS_FURO, vao_alt + 1.0, x, y, FUNDO))
    # passagens na parede -X: USB-C e antena SMA
    #
    # O cilindro começa FORA da parede (-cx/2 - PAREDE) e tem 3 paredes de
    # comprimento, então atravessa a parede inteira com sobra dos dois lados.
    # Até aqui ele começava em -cx — a largura externa inteira, não a metade —
    # e ia de -69 a -58,5 mm num corpo que termina em -34,5: os dois furos
    # nunca foram cortados, na v1 nem na v2. O defeito 11 do README ("furo
    # USB-C sem conector") descrevia um furo que existia no desenho e não no
    # modelo; só apareceu quando a v3 pôs um conector para passar por ele.
    x0 = -cx / 2 - PAREDE
    p = p.cut(cil(USB_D, PAREDE * 3, x0, 0, FUNDO + vao_alt * 0.45, eixo=(1, 0, 0)))
    p = p.cut(cil(SMA_D, PAREDE * 3, x0, 0, FUNDO + vao_alt * 0.80, eixo=(1, 0, 0)))
    # face de baixo: rebaixo do spigot, furo do pino, passante corpo-base
    p = p.cut(cil(REB_SPIGOT_D, REB_SPIGOT_H, 0, 0, 0))
    p = p.cut(cil(PINO_D, PINO_H + REB_SPIGOT_H, PINO_ORI_R, 0, 0))
    p = p.cut(cil(ARRUELA_D, 1.5, 0, 0, FUNDO - 1.5))
    p = p.cut(cil(BOSS_FURO, FUNDO + 1.0, 0, 0, 0))
    return p, (cx, cy, alt)


def tampa(vao, recuo):
    cx, cy = vao[0] + 2 * PAREDE, vao[1] + 2 * PAREDE
    p = caixa(cx, cy, TAMPA_ESP, R_CANTO)
    sx, sy = vao[0] - SPIGOT_FOLGA, vao[1] - SPIGOT_FOLGA
    p = p.fuse(caixa(sx, sy, SPIGOT_TAMPA_H, max(R_CANTO - PAREDE, 0.5),
                     z0=-SPIGOT_TAMPA_H))
    # canal da gaxeta, na face inferior, entre o spigot e a borda
    mx, my = (cx + sx) / 4.0 + GAXETA_L / 2.0, (cy + sy) / 4.0 + GAXETA_L / 2.0
    canal = caixa(2 * mx + GAXETA_L, 2 * my + GAXETA_L, GAXETA_P, R_CANTO)
    canal = canal.cut(caixa(2 * mx - GAXETA_L, 2 * my - GAXETA_L, GAXETA_P + 1.0,
                            max(R_CANTO - GAXETA_L, 0.5), z0=-0.5))
    p = p.cut(canal)
    for x, y in bosses_xy(vao, recuo):
        p = p.cut(cil(TAMPA_FURO, TAMPA_ESP + SPIGOT_TAMPA_H + 1.0,
                      x, y, -SPIGOT_TAMPA_H - 0.5))
        p = p.cut(cil(TAMPA_REBAIXO, 1.2, x, y, TAMPA_ESP - 1.2))
    return p


def base():
    """Interface com a máquina — igual nas duas versões, é o que encosta no
    motor: spigot Ø28, quatro ímãs Ø10 em R20 e o pino de orientação."""
    p = caixa(BASE_LADO, BASE_LADO, BASE_ALT, R_CANTO)
    p = p.fuse(cil(SPIGOT_D, SPIGOT_H, 0, 0, BASE_ALT))
    for x, y in diagonais(MAG_R):
        p = p.cut(cil(MAG_D, MAG_P, x, y, 0))
    p = p.fuse(cil(PINO_ORI_D, SPIGOT_H + PINO_ORI_SAI, PINO_ORI_R, 0, BASE_ALT))
    p = p.cut(cil(INSERTO_D, 6.0, 0, 0, BASE_ALT + SPIGOT_H - 6.0))
    return p


# ---------------------------------------------------------------------
# Geração das versões
# ---------------------------------------------------------------------
ASSENTO_PLACA = 5.0       # acima do fundo da cavidade; sob a placa passa o Ra-02
FOLGA_BATERIA = 2.0
ORIGEM3D = AQUI / "3dmodels" / "origem"
# A placa acompanha a versão do invólucro, e não a variável de ambiente: cada
# cavidade tem a sua. Com KAELIX_PCB decidindo por fora, a v1 do invólucro era
# conferida contra a placa de 61 x 51 da v2 e acusava 1616 mm3 de interferência
# — um defeito que não existe, num par que ninguém vai montar.
def placa_da(versao):
    return AQUI / "pcb" / versao / "kaelix.step"

falhas, limitacoes = [], []
for versao, cfg in VERSOES.items():
    vao, vao_alt = cfg["vao"], cfg["vao_alt"]
    saida = SAIDA / versao
    saida.mkdir(parents=True, exist_ok=True)
    print(f"\n=== {versao}: vão {vao[0]:.0f} x {vao[1]:.0f} x {vao_alt:.0f} mm — {cfg['nota']}")

    c, (cx, cy, calt) = corpo(vao, vao_alt, cfg["boss_d"], cfg["boss_recuo"])
    t = tampa(vao, cfg["boss_recuo"])
    b = base()
    vol = 0.0
    for nome, peca in (("corpo", c), ("tampa", t), ("base", b)):
        if peca.isNull() or not peca.Solids:
            falhas.append(f"{versao}/{nome}: sólido vazio"); continue
        peca.exportStep(str(saida / f"{nome}.step"))
        bb = peca.BoundBox
        vol += peca.Volume
        print(f"   {nome:6s} {bb.XLength:6.2f} x {bb.YLength:6.2f} x {bb.ZLength:6.2f} mm"
              f"   {peca.Volume/1000:6.2f} cm3")

    Z_CORPO, Z_TAMPA = BASE_ALT, BASE_ALT + calt
    pecas = [b]
    cp = c.copy(); cp.translate(Vector(0, 0, Z_CORPO)); pecas.append(cp)
    tp = t.copy(); tp.translate(Vector(0, 0, Z_TAMPA)); pecas.append(tp)

    topo_placa = None
    placa_step = placa_da(versao)
    if placa_step.exists():
        pl = Part.Shape(); pl.read(str(placa_step))
        pb = pl.BoundBox
        pl.translate(Vector(-(pb.XMin + pb.XMax) / 2, -(pb.YMin + pb.YMax) / 2,
                            Z_CORPO + FUNDO + ASSENTO_PLACA))
        ch = pl.common(cp)
        v = 0.0 if ch.isNull() else ch.Volume
        print(f"   placa {pb.XLength:.0f} x {pb.YLength:.0f}: "
              f"interferência com o corpo {v:.1f} mm3"
              f"{'' if v < 1e-3 else '  <- NAO CABE'}")
        if v >= 1e-3:
            falhas.append(f"{versao}: a placa não cabe")
        pecas.append(pl)
        topo_placa = pl.BoundBox.ZMax

    cam = ORIGEM3D / cfg["bateria"]
    if cam.exists():
        bat = Part.Shape(); bat.read(str(cam))
        # Alinha o lado longo da célula ao lado longo da cavidade. O modelo da
        # Adafruit 2011 vem com 60 mm em Y; sem girar, ele fura a parede e o
        # relatório acusa "não cabe" por motivo errado — a célula cabe, o
        # modelo é que estava de lado.
        if (bat.BoundBox.YLength > bat.BoundBox.XLength) != (vao[1] > vao[0]):
            bat = bat.copy()
            bat.rotate(Vector(0, 0, 0), Vector(0, 0, 1), 90)
        bb = bat.BoundBox
        d = sorted([bb.XLength, bb.YLength, bb.ZLength])
        z = (topo_placa if topo_placa else Z_CORPO + FUNDO + ASSENTO_PLACA) + FOLGA_BATERIA
        bat.translate(Vector(-(bb.XMin + bb.XMax) / 2, -(bb.YMin + bb.YMax) / 2,
                             -bb.ZMin + z))
        chb = bat.common(cp)
        vb = 0.0 if chb.isNull() else chb.Volume
        mah = {"lipo-2000mah-adafruit2011.step": 2000,
               "lipo-500mah-adafruit1578.step": 500}.get(cfg["bateria"], 0)
        dias = mah / 0.314 / 24
        print(f"   bateria {cfg['bateria']}: {d[2]:.1f} x {d[1]:.1f} x {d[0]:.2f} mm"
              f"   interferência {vb:.1f} mm3"
              f"{'' if vb < 1e-3 else '  <- NAO CABE'}")
        print(f"      {mah} mAh a 314 uA -> {dias:.0f} dias  "
              f"(REQ-PWR-06 pede 243)")
        if vb >= 1e-3:
            (limitacoes if cfg.get("limitacao") == "bateria" else falhas).append(
                f"{versao}: a bateria não cabe ({vb:.0f} mm3 de interferência "
                f"com os postes Ø{cfg['boss_d']:.0f})")
        else:
            pecas.append(bat)

    mont = Part.makeCompound(pecas)
    mont.exportStep(str(saida / "montagem.step"))
    meio = Part.makeBox(300, 200, 300, Vector(-150, 0, -50))
    mont.cut(meio).exportStep(str(saida / "montagem-corte.step"))
    mb = mont.BoundBox
    massa = vol * 1e-9 * RHO_ASA * 1000.0
    print(f"   montagem {mb.XLength:.1f} x {mb.YLength:.1f} x {mb.ZLength:.1f} mm"
          f"   volume externo do corpo {cx*cy*calt/1000:.0f} cm3"
          f"   massa se maciço {massa:.0f} g")

if limitacoes:
    print("\nLIMITAÇÕES CONHECIDAS (declaradas, não são falha):")
    for f in limitacoes:
        print(f"   {f}")
if falhas:
    print("\nPROBLEMAS:")
    for f in falhas:
        print(f"   {f}")
    sys.stdout.flush()
    raise SystemExit(1)
sys.stdout.flush()
