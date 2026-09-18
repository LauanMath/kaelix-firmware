"""Gera o .kicad_pcb do Kaelix a partir da mesma netlist do esquemático.

A netlist é importada de `gen_schematic.py` — uma fonte da verdade só. Se um
pino mudar lá, muda aqui.

Contorno: QUADRADO de 42 x 42 mm com os quatro cantos recortados. Ele vem do
desenho do invólucro (docs/device/IMG_5298.jpeg, versão 4), que diz:

    corpo 50,0 x 50,0 externo    vão interno 43,0, canto R7
    4 bosses M3 Ø11 a 36,0 entre eixos

Houve aqui, por várias versões, um DISCO de Ø40, justificado assim: "com 43
mm de vão, um disco de 40 mm deixa 1,5 mm de folga radial". A conta está
certa e a premissa está errada — ela trata um vão quadrado como circular.
O que é redondo no desenho é a interface magnética do lado de fora (spigot
Ø28,4, base Ø54 com quatro ímãs em R20), não a cavidade da placa.

O disco custava 18% da área útil, e custava nos CANTOS: era lá que não cabia
furo de fixação, era para lá que o desacoplamento tinha de fugir, e era o
canto que espremia o corredor do cabo da bateria.

    quadrado 42 x 42                       1764 mm²
    menos os quatro recortes de r = 6,0     287 mm²   (bosses Ø11 + 0,5)
    área útil                              1477 mm²   contra 1257 do disco

Por que os módulos voltaram a ficar EMPILHADOS (um por face)
------------------------------------------------------------
A versão anterior punha o WROOM-1U e o Ra-02 lado a lado na face de cima.
Isso exige ~45 mm de largura, e a placa foi crescendo até Ø74 mm para
acomodá-los — 74 mm não entra num vão de 43 mm. Pior: o `verifica_encaixe`
continuava passando, porque o raio usado no teste era o raio inflado. Um
verificador que acompanha o valor que deveria restringir não verifica nada.

Empilhados, cada módulo cabe com folga (o U1 mede 18,0 x 19,2 mm num
contorno de 42 x 42). O argumento contra o empilhamento era que ele
"tirava da face de baixo a área que o desacoplamento precisa" — e isso é
verdade só se o desacoplamento tiver de ficar na face OPOSTA ao CI que
serve, que é o pior lugar possível: acrescenta duas vias ao laço de
desacoplamento, justamente o laço em que indutância importa. Aqui cada
capacitor fica na MESMA face do seu CI, no anel livre em volta dele:

    face de cima   U1 (18,0 x 19,2 mm) + J1 + J2 + desacoplamento de U1
    face de baixo  U3 (16,0 x 17,0 mm) + U2 + U4 + load switch + o resto

    livre em cima  ~900 mm²      livre embaixo  ~660 mm²
    ocupado        ~35 mm²                      ~170 mm²

Rodar:  python3 hardware/gen_pcb.py
"""

import math
import os
import pathlib
import sys
import uuid as _uuid

AQUI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
VERSAO = os.environ.get("KAELIX_PCB", "v1")
PROJ = AQUI / "pcb" / VERSAO          # projeto KiCad desta versão
from sexpr import parse, dump, head, find, find1, sym, st  # noqa: E402
import gen_schematic as SCH  # noqa: E402

FPLIB = pathlib.Path("/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints")

CX, CY = 150.0, 100.0

# Contorno: QUADRADO, não disco.
#
# O disco de Ø40 vinha da versão anterior deste arquivo, que justificava assim:
# "com 43 mm de vão, um disco de 40 mm deixa 1,5 mm de folga radial". A conta
# está certa e a premissa está errada — ela trata um vão QUADRADO como se
# fosse circular. O desenho do invólucro (docs/device/IMG_5298.jpeg, versão 4)
# diz, em três vistas: corpo 50,0 x 50,0 externo, VÃO INTERNO 43,0 com canto
# R7, e quatro bosses M3 de Ø11 a 36,0 entre eixos.
#
# O que é redondo no desenho é a interface magnética do lado de fora — spigot
# Ø28,4 e base Ø54 com quatro ímãs Ø10 em R20. Não é a cavidade da placa.
#
# Os cantos são recortados para liberar os bosses. A placa NÃO pode parafusar
# neles: um furo M3 em (18, 18) precisaria de material até 28,2 mm na
# diagonal, e o canto R7 da cavidade termina em 27,5 mm. Os furos de fixação
# da placa continuam sendo os três M2 próprios, agora com muito mais espaço.
#
#   quadrado 42 x 42                       1764 mm²
#   menos os quatro recortes de r = 6,0     287 mm²
#   área útil                              1477 mm²   (+18% sobre o disco)
#
# A v2 repete o raciocínio sobre o vão da v2 do invólucro (62 x 52, boss Ø8
# a 2,5 da parede): placa 61 x 51, recortes de r = 4,5 a 57,0 x 47,0 entre
# eixos. Mesma netlist, mesmo esquemático — o que muda é o contorno e, por
# consequência, quanto espaço o legalizador tem para honrar as preferências.
#
#   v1  quadrado 42 x 42 menos 4 recortes r=6,0    1477 mm²
#   v2  retângulo 61 x 51 menos 4 recortes r=4,5   2962 mm²   (+101%)
VERSOES = {
    "v1": dict(lado=(42.0, 42.0), boss=(18.0, 18.0), boss_r=6.0, corredor=4.0,
               furo_raios=[18.4 - 0.1 * k for k in range(45)]),
    "v2": dict(lado=(61.0, 51.0), boss=(28.5, 23.5), boss_r=4.5, corredor=6.0,
               furo_raios=[24.0 - 0.1 * k for k in range(81)]),
}
if VERSAO not in VERSOES:
    raise SystemExit(f"versão desconhecida: {VERSAO} (há {', '.join(VERSOES)})")
CFG = VERSOES[VERSAO]
LADO_X, LADO_Y = CFG["lado"]     # lados do retângulo
BOSS_X, BOSS_Y = CFG["boss"]     # meio-passo dos bosses em x e em y
BOSS_R = CFG["boss_r"]           # raio do boss mais 0,5 de folga
BORDA = 0.6                          # folga mínima corpo/pad -> borda da placa
FOLGA = 0.3                          # folga mínima corpo a corpo na mesma face
FOLGA_COBRE = 0.15                   # folga mínima cobre a cobre (netclass)
FOLGA_FURO = 0.25                    # folga mínima furo a cobre

_n = [0]
def uid():
    _n[0] += 1
    return str(_uuid.UUID(int=0xBEEF0000 + _n[0]))


# ---------------------------------------------------------------------
# Netlist: reaproveitada do gerador de esquemático
# ---------------------------------------------------------------------
def netlist():
    r = {}
    for ref, _lb, _sn, fp, val, _x, _y, mapa in SCH.COMPONENTES:
        r[ref] = (fp, val, dict(mapa))
    for ref, _sn, fp, val, _x, _y, n1, n2 in SCH.PASSIVOS:
        r[ref] = (fp, val, {"1": n1, "2": n2})
    for ref, _lb, _sn, fp, val, _x, _y, mapa in SCH.EXTRAS:
        r[ref] = (fp, val, dict(mapa))
    return r


NET = netlist()


# =====================================================================
# Geometria de footprint
# =====================================================================
_fps = {}
def carrega_fp(libfp):
    if libfp not in _fps:
        d, n = libfp.split(":")
        _fps[libfp] = parse((FPLIB / f"{d}.pretty" / f"{n}.kicad_mod").read_text())[0]
    return _fps[libfp]


def gira(px, py, rot):
    """Rotação com o sinal do KiCad.

    Conferido contra o próprio DRC: o pad 4 do header J2 (local (0, 7,62))
    colocado em (157,5, 111,0) com rot 90 aparece no relatório em
    (165,12, 111,0) — ou seja, +7,62 em x. O gerador anterior mandava para
    -7,62. Como só o J2 usava rotação e nada dependia dele, o erro ficou
    latente; passou a importar quando o legalizador começou a girar
    passivos para caberem no anel, e produziu 42 curtos no DRC.
    """
    r = int(rot) % 360
    if r == 0:
        return px, py
    if r == 90:
        return py, -px
    if r == 180:
        return -px, -py
    if r == 270:
        return -py, px
    raise ValueError(f"rotação não ortogonal: {rot}")


_geoms = {}
def geom(libfp):
    """Pads e retângulo do corpo em coordenadas locais do footprint.

    O corpo sai de F.Fab e F.CrtYd. O courtyard do WROOM-1 (não -1U) carrega
    a zona de exclusão da antena impressa, 48 x 41 mm, que é recomendação de
    RF e não obstáculo mecânico — por isso o projeto usa o -1U, cujo
    courtyard é o corpo real.
    """
    if libfp in _geoms:
        return _geoms[libfp]
    pads, xs, ys, passante = [], [], [], False
    for e in carrega_fp(libfp)[1:]:
        if not isinstance(e, list):
            continue
        h = head(e)
        if h == "pad":
            at, sz = find1(e, "at"), find1(e, "size")
            px, py = float(at[1][1]), float(at[2][1])
            w, hh = float(sz[1][1]), float(sz[2][1])
            # O pad tem rotação PRÓPRIA, independente da do footprint. Ignorá-la
            # descrevia o QFN-24 do MPU6050 com pads de 0,85 mm de largura num
            # passo de 0,5 mm — ou seja, pads vizinhos sobrepostos. O roteador
            # concluía, corretamente para esse modelo errado, que nenhum escape
            # cabia, e devolvia o barramento I2C inteiro como não roteado.
            prot = float(at[3][1]) if len(at) > 3 else 0.0
            if int(round(prot)) % 180 == 90:
                w, hh = hh, w

            # Pad `custom`: o (size) é só a ÂNCORA; o cobre de verdade está em
            # (primitives). No SOT-89-3 do HT7333 a âncora tem 1,475 mm e a aba
            # térmica chega a 3,86 mm do centro do pad — o modelo enxergava
            # menos de um terço do cobre, e o roteador passava quatro pistas
            # por cima dela. Aqui a primitiva entra na extensão do pad.
            prim = find1(e, "primitives")
            if prim is not None:
                qx, qy = [], []
                def _prim(no):
                    if isinstance(no, list):
                        if head(no) in ("xy", "start", "end", "center", "mid") and len(no) >= 3:
                            try:
                                a, b = float(no[1][1]), float(no[2][1])
                            except ValueError:
                                return
                            ra, rb = gira(a, b, prot)
                            qx.append(ra); qy.append(rb)
                        for z in no:
                            _prim(z)
                _prim(prim)
                if qx:
                    lo_x = min(px - w / 2, px + min(qx)); hi_x = max(px + w / 2, px + max(qx))
                    lo_y = min(py - hh / 2, py + min(qy)); hi_y = max(py + hh / 2, py + max(qy))
                    px, py = (lo_x + hi_x) / 2, (lo_y + hi_y) / 2
                    w, hh = hi_x - lo_x, hi_y - lo_y
            tht = e[2][1] in ("thru_hole", "np_thru_hole")
            passante = passante or tht
            pads.append({"num": e[1][1], "x": px, "y": py, "w": w, "h": hh, "tht": tht})
            xs += [px - w / 2, px + w / 2]
            ys += [py - hh / 2, py + hh / 2]
        elif h in ("fp_line", "fp_rect", "fp_poly", "fp_circle", "fp_arc"):
            lay = find1(e, "layer")
            if not (lay and len(lay) > 1 and lay[1][1] in ("F.Fab", "F.CrtYd")):
                continue
            if h == "fp_circle":
                # Centro e um ponto da circunferência não são a extensão do
                # círculo. O courtyard do furo M2 é um fp_circle de raio
                # 2,45 mm, e tomar só os dois pontos descrevia um retângulo
                # de 3,55 x 2,20 mm — foi assim que o U1 encostou no H3 sem
                # o verificador reclamar, e o DRC pegou como courtyards_overlap.
                ce, en = find1(e, "center"), find1(e, "end")
                cxx, cyy = float(ce[1][1]), float(ce[2][1])
                rr = math.hypot(float(en[1][1]) - cxx, float(en[2][1]) - cyy)
                xs += [cxx - rr, cxx + rr]
                ys += [cyy - rr, cyy + rr]
                continue
            def anda(no):
                if isinstance(no, list):
                    if head(no) in ("start", "end", "center", "mid", "at") and len(no) >= 3:
                        try:
                            xs.append(float(no[1][1])); ys.append(float(no[2][1]))
                        except ValueError:
                            pass
                    for z in no:
                        anda(z)
            anda(e)
    _geoms[libfp] = {"pads": pads, "corpo": (min(xs), min(ys), max(xs), max(ys)),
                     "passante": passante}
    return _geoms[libfp]


def extensao(libfp, x, y, rot):
    """Retângulo ocupado, em coordenadas da placa, já girado."""
    g = geom(libfp)
    xs, ys = [], []
    bx0, by0, bx1, by1 = g["corpo"]
    cantos = [(bx0, by0), (bx1, by0), (bx1, by1), (bx0, by1)]
    for p in g["pads"]:
        cantos += [(p["x"] - p["w"] / 2, p["y"] - p["h"] / 2),
                   (p["x"] + p["w"] / 2, p["y"] - p["h"] / 2),
                   (p["x"] + p["w"] / 2, p["y"] + p["h"] / 2),
                   (p["x"] - p["w"] / 2, p["y"] + p["h"] / 2)]
    for px, py in cantos:
        rx, ry = gira(px, py, rot)
        xs.append(rx); ys.append(ry)
    return (x + min(xs), y + min(ys), x + max(xs), y + max(ys))


def rect_mecanico(ref):
    """(face, retângulo) que a peça ocupa fisicamente. Só a face em que está.

    Corpo e courtyard valem para a face de montagem: é onde a peça encosta na
    placa. Um via passante da peça NÃO torna a face oposta inutilizável — ele
    é um furo de 0,2 mm coberto por máscara, e módulos assentam por cima disso
    o tempo todo. Confundir as duas coisas fazia o U1 e o U3 aparecerem como
    colisão só porque o pad térmico do WROOM-1U tem vias passantes.
    """
    x, y, rot, lado = POSICOES[ref]
    return lado, extensao(NET[ref][0], x, y, rot)


def eh_furo(ref):
    """Furo de fixação: entra na netlist sem nenhuma net."""
    return not NET[ref][2]


def rects_cobre(ref):
    """[(face, retângulo, net)] de cada pad. Pad passante conta nas duas faces.

    Este é o invariante que a versão anterior não tinha: ela comparava só
    corpo com corpo, filtrando por lado, e por isso não via o furo M2 (face
    de cima, NPTH) atravessando o pad do R6 (face de baixo). Furo NPTH não
    tem net — conflita com qualquer cobre.
    """
    mapa = NET[ref][2]
    out = []
    for p in pads_abs(ref):
        rede = mapa.get(p["num"])
        r = (p["x"] - p["w"] / 2, p["y"] - p["h"] / 2,
             p["x"] + p["w"] / 2, p["y"] + p["h"] / 2)
        for f in p["faces"]:
            out.append((f, r, rede if rede and rede != SCH.NC else None))
    return out


def _cruza(a, b, folga):
    return (a[0] - folga < b[2] and b[0] < a[2] + folga
            and a[1] - folga < b[3] and b[1] < a[3] + folga)


def conflito(refA, refB):
    """None, ou ('mecânica'|'cobre'|'corredor', invasão_x, invasão_y)."""
    # O corredor vem ANTES do descarte rápido por bbox: ele se estende muito
    # além do corpo do conector, e o descarte — que só compara os dois corpos
    # — dava por disjunto o par J1/H2 que o corredor cruza em cheio.
    # Corredor de cabo contra peça da MESMA face, e contra furo, que vale nas
    # duas: a cabeça do parafuso ocupa espaço acima do laminado.
    for dono, outro in ((refA, refB), (refB, refA)):
        cor = corredor(dono)
        if cor is None or dono not in POSICOES or outro not in POSICOES:
            continue
        fo, ro = rect_mecanico(outro)
        if (fo == POSICOES[dono][3] or eh_furo(outro)) and _cruza(cor, ro, 0.0):
            return ("corredor", min(cor[2], ro[2]) - max(cor[0], ro[0]),
                    min(cor[3], ro[3]) - max(cor[1], ro[1]))


    fa, ra = rect_mecanico(refA)
    fb, rb = rect_mecanico(refB)
    if not _cruza(ra, rb, 0.0) and not _cruza(ra, rb, FOLGA):
        # bbox disjunto com folga: nenhum pad pode se cruzar tampouco
        if not _cruza(ra, rb, FOLGA):
            return None
    if fa == fb and _cruza(ra, rb, FOLGA):
        return ("mecânica", min(ra[2], rb[2]) - max(ra[0], rb[0]),
                min(ra[3], rb[3]) - max(ra[1], rb[1]))
    # Furo de fixação: o parafuso precisa de espaço nas DUAS faces, então o
    # furo tem de estar livre do courtyard alheio — não só do cobre alheio.
    # É o que o KiCad chama de npth_inside_courtyard.
    for h, o in ((refA, refB), (refB, refA)):
        if not eh_furo(h) or eh_furo(o):
            continue
        _fo, ro = rect_mecanico(o)
        for _f, rh, _n in rects_cobre(h):
            if _cruza(rh, ro, FOLGA):
                return ("furo/corpo", min(rh[2], ro[2]) - max(rh[0], ro[0]),
                        min(rh[3], ro[3]) - max(rh[1], ro[1]))

    # Pino PASSANTE de peça, o mesmo raciocínio aplicado ao furo: ele atravessa
    # o laminado e sai na face oposta com pad e filete de solda, e ali nenhum
    # corpo pode assentar. É o pth_inside_courtyard do KiCad. Até a v2 só o J2
    # tinha pino passante e nada ficava sob ele; na v3 os quatro pinos de
    # carcaça do USB-C caem na face de baixo, onde fica o carregador.
    for h, o in ((refA, refB), (refB, refA)):
        if eh_furo(h) or eh_furo(o) or h not in POSICOES or o not in POSICOES:
            continue
        fo, ro = rect_mecanico(o)
        if fo == POSICOES[h][3]:
            continue          # mesma face: já coberto pela colisão mecânica
        x, y, rot, _l = POSICOES[h]
        for pd in geom(NET[h][0])["pads"]:
            # Via térmica não é pino: as 12 do pad térmico do WROOM-1U têm pad
            # de 0,6 mm, furo de 0,2 e máscara por cima, e na v1 o Ra-02 assenta
            # sob elas por projeto (ver rect_mecanico). Pino de verdade começa em
            # 1,1 mm (carcaça do USB-C) e 1,7 mm (header).
            if not pd["tht"] or min(pd["w"], pd["h"]) < 0.8:
                continue
            xs, ys = [], []
            for sx in (-1, 1):
                for sy in (-1, 1):
                    rx, ry = gira(pd["x"] + sx * pd["w"] / 2, pd["y"] + sy * pd["h"] / 2, rot)
                    xs.append(x + rx); ys.append(y + ry)
            rp = (min(xs), min(ys), max(xs), max(ys))
            if _cruza(rp, ro, FOLGA):
                return ("pino/corpo", min(rp[2], ro[2]) - max(rp[0], ro[0]),
                        min(rp[3], ro[3]) - max(rp[1], ro[1]))

    furo = eh_furo(refA) or eh_furo(refB)
    folga = FOLGA_FURO if furo else FOLGA_COBRE
    for f1, r1, n1 in rects_cobre(refA):
        for f2, r2, n2 in rects_cobre(refB):
            if f1 != f2 or (n1 is not None and n1 == n2):
                continue
            if _cruza(r1, r2, folga):
                return ("cobre", min(r1[2], r2[2]) - max(r1[0], r2[0]),
                        min(r1[3], r2[3]) - max(r1[1], r2[1]))
    return None


def pads_abs(ref, num=None):
    """Pads de um componente já colocado, em coordenadas da placa."""
    libfp = NET[ref][0]
    x, y, rot, lado = POSICOES[ref]
    fora = []
    for p in geom(libfp)["pads"]:
        if num is not None and p["num"] != num:
            continue
        px, py = gira(p["x"], p["y"], rot)
        w, h = (p["h"], p["w"]) if int(rot) % 180 == 90 else (p["w"], p["h"])
        fora.append({"num": p["num"], "x": x + px, "y": y + py, "w": w, "h": h,
                     "faces": frozenset(("F", "B")) if p["tht"] else frozenset((lado,))})
    return fora


def pad_xy(ref, num):
    p = pads_abs(ref, num)
    if not p:
        raise KeyError(f"pad {num} de {ref}")
    return p[0]["x"], p[0]["y"]


# =====================================================================
# Placement
# =====================================================================
# Peças grandes: posição fixada à mão. Tudo o mais é ancorado ao pino que
# serve e legalizado automaticamente (ver `legaliza`).
#
# A v1 empilha o Ra-02 exatamente sob o WROOM-1U porque não há onde mais
# pôr os dois: 42 x 42 menos dois módulos de ~19 mm não deixa segundo lugar.
# O custo aparece na medição de desacoplamento — C7 e C8 servem o Ra-02 de
# 4,2 e 11,1 mm, porque o anel do Ra-02 é o mesmo anel do WROOM-1U, já
# tomado por C2/C3/R1/RT1. Na v2 os dois módulos ficam em cantos opostos e
# cada um tem anel próprio.
FIXAS_POR_VERSAO = {
    "v1": {
        # Afinadas para o contorno QUADRADO. As posições anteriores vinham do
        # disco e deixavam duas nets sem rota aqui: a área nova está nos
        # cantos, e é para lá que as peças de borda têm de ir.
        "U1": (151.0,  94.0,  0, "F"),   # WROOM-1U, u.FL apontando para a borda
        "U3": (150.0,  94.0,  0, "B"),   # Ra-02, empilhado sob o U1
        "J1": (136.0, 106.0,  0, "F"),   # bateria, borda esquerda
        "J2": (141.0, 116.0, 90, "F"),   # UART/BOOT — THT, pads nas duas faces
        "U2": (160.0, 110.0,  0, "B"),   # acelerômetro
        "U4": (134.0,  96.0,  0, "B"),   # regulador, junto do conector de bateria
    },
    "v2": {
        # 61 x 51: cada módulo em um canto, com anel livre em volta.
        "U1": (137.0, 112.0,  0, "F"),   # WROOM-1U, canto superior esquerdo
        "U3": (164.0, 111.0,  0, "B"),   # Ra-02, canto superior direito
        "J1": (127.5,  92.0,  0, "F"),   # bateria, borda esquerda
        "J2": (152.0,  79.5, 90, "F"),   # UART/BOOT, borda inferior
        "U2": (150.0,  88.0,  0, "B"),   # acelerômetro, junto do centro
        "U4": (137.0,  81.0,  0, "B"),   # regulador, fora do corredor do J1
    },
}
FIXAS = FIXAS_POR_VERSAO[VERSAO]

# Furos M2: três, o mais perto possível de 120° entre si.
#
# O invólucro não prende a placa por parafuso — a cadeia de rigidez do
# projeto é spigot Ø28x3,3 em compressão (export_enclosure_data.py:134-144),
# e a placa assenta pelo aro. Os furos existem por outro motivo: dar apoio
# ao acelerômetro. Um acelerômetro no ponto mais flexível de um disco
# apoiado só no aro mede a flexão da própria placa, não a vibração da
# máquina.
#
# O ângulo NÃO é escolhido à mão. Com o courtyard do WROOM-1U medindo
# 19,5 x 20,15 mm num disco de Ø40, sobra pouca margem, e um triedro fixo
# em 90/210/330° esbarra no módulo. O código varre ângulo e raio, monta o
# conjunto dos pares legais e escolhe o trio que MAXIMIZA a menor separação
# angular — a simetria vira resultado medido, e o relatório diz quanto se
# conseguiu, em vez de o número 120° ficar escrito sem ser verdade.
FURO_FP = "MountingHole:MountingHole_2.2mm_M2"
FURO_RAIOS = CFG["furo_raios"]
FUROS = None

# ref -> (âncora, pad, dx, dy, rot, lado). O ponto é uma PREFERÊNCIA: se
# estiver ocupado ou fora do disco, `legaliza` procura o livre mais próximo.
#
# Regra de face: cada capacitor de desacoplamento fica na MESMA face do CI
# que serve, no anel livre em volta dele. Na face oposta ele custaria duas
# vias dentro do laço de desacoplamento, que é onde indutância importa.
PREFERENCIAS_POR_VERSAO = {
    "v1": {
        # --- face de cima, anel em volta do U1 ---
        "C2":  ("U1", "2",  -3.2, -1.4, 90, "F"),   # desacoplamento +3V3 do U1
        "C3":  ("U1", "2",  -3.2,  1.4, 90, "F"),
        "R6":  ("U1", "3",  -0.5, -6.0,  0, "F"),   # pull-up do EN
        "C1":  ("U1", "3",   3.0, -6.0,  0, "F"),   # capacitor do EN (rede de reset)
        "R1":  ("U1", "5",  -3.2,  1.4, 90, "F"),   # topo do divisor do NTC
        "RT1": ("U1", "4",  -3.2,  4.2, 90, "F"),   # NTC no nó do ADC
        "R7":  ("U1", "27",  3.0,  0.0, 90, "F"),   # pull-up do IO0
        "R3":  ("U1", "17",  0.0,  3.0,  0, "F"),   # pull-up SCL
        # --- face de baixo: load switch, entre o regulador e o MPU6050 ---
        # Q1 fica junto do VOUT do U4 (a fonte) e o dreno cai direto no U2.
        "Q1":  ("U4", "3",   4.5, -1.5,  0, "B"),
        "Q2":  ("U4", "3",   4.5,  2.5,  0, "B"),
        "R4":  ("U4", "3",   8.5, -1.5,  0, "B"),
        "R5":  ("U4", "3",   8.5,  1.5,  0, "B"),
        "R8":  ("U4", "3",   8.5,  4.0,  0, "B"),
        # --- face de baixo: desacoplamento de cada CI, no anel do próprio CI ---
        "R2":  ("U2", "24",  4.5,  0.0,  0, "B"),   # pull-up SDA, no barramento
        "C4":  ("U2", "13",  4.5, -2.5,  0, "B"),   # +3V3_SW do MPU6050
        "C5":  ("U2", "10",  4.5,  2.5,  0, "B"),   # REGOUT
        "C6":  ("U2", "20",  4.5,  5.0,  0, "B"),   # CPOUT
        "C7":  ("U3", "3",  -4.0, -1.4, 90, "B"),   # desacoplamento do Ra-02
        "C8":  ("U3", "3",  -4.0,  1.4, 90, "B"),
        "C9":  ("U4", "1",  -3.5,  0.0, 90, "B"),   # entrada do regulador
        "C10": ("U4", "3",  -3.5,  2.5, 90, "B"),   # saída do regulador
        # --- entrada de energia protegida e medição da bateria ---
        # Q3 em série com o conector: é o primeiro elemento do caminho, e tem de
        # ficar antes do C9 para que uma bateria invertida não chegue nem ao
        # capacitor de entrada do regulador.
        "Q3":  ("J1", "1",   0.0,  5.0,  0, "B"),
        # Divisor junto da FONTE (rail VBAT), capacitor de reservatório junto do
        # ADC: é no pino do ADC que o sample-and-hold puxa a carga, e é a pista de
        # 500 k de impedância que precisa terminar em baixa impedância. Inverter
        # os dois deixaria o nó exposto ao longo de todo o trajeto.
        "R9":  ("U4", "1",  -6.5, -1.5, 90, "B"),
        "R10": ("U4", "1",  -6.5,  1.5, 90, "B"),
        "C11": ("U1", "6",  -3.2,  0.0, 90, "F"),
        # Filtro do nó do ADC do NTC, no próprio pino do ADC.
        "C12": ("U1", "4",  -3.2,  2.8, 90, "F"),
    },
    # v2: mesmas âncoras, deslocamentos recalculados.
    #
    # Na v1 os deslocamentos foram escolhidos à mão, e vários já nascem fora
    # da faixa de 3 mm — C6 pede (+4,5; +5,0) a partir de um pad do QFN, que
    # são 6,7 mm antes de o legalizador tocar em nada. Aqui cada peça de anel
    # sai do CONTORNO do CI mais a folga de corpo mais a meia-largura dela:
    # é a posição mais próxima que não colide, e não um palpite.
    #
    #   0805 em pé (rot 90): meia-largura 0,85 -> anel = contorno + 1,15
    #   passo vertical mínimo entre dois 0805 em pé: 3,2 + 0,3 = 3,5
    "v2": {
        # --- U1, contorno x -9,75..9,75, y -9,85..10,30; pads 2..6 em x=-8,75
        # Coluna da esquerda em x_rel = -10,90 (dx = -2,15 a partir do pad).
        # Cinco pads de sinal a 1,27 de passo não comportam seis discretos a
        # 3 mm: 0805 em pé pede 3,5 de passo. Prioridade: desacoplamento e
        # filtro do ADC na coluna 1, rede do NTC na coluna 2.
        "C2":  ("U1", "2",  -2.15, -1.80, 90, "F"),
        "C3":  ("U1", "2",  -2.15,  1.80, 90, "F"),
        "C11": ("U1", "6",  -2.15,  1.60, 90, "F"),
        "C12": ("U1", "4",  -5.65,  0.00, 90, "F"),
        "R1":  ("U1", "5",  -5.65,  3.50, 90, "F"),
        "RT1": ("U1", "4",  -5.65, -3.50, 90, "F"),
        # rede de reset do EN: fila sob a borda de baixo do U1
        "R6":  ("U1", "3",   3.20, -5.20,  0, "F"),
        "C1":  ("U1", "3",   0.00, -5.20,  0, "F"),
        "R7":  ("U1", "27",  2.15,  0.00, 90, "F"),   # borda direita
        "R3":  ("U1", "17",  0.00,  2.10,  0, "F"),   # borda de cima
        # --- U2 (QFN 4x4, contorno +/-2,65): anel a 3,80 do centro
        "C4":  ("U2", "13",  1.85,  0.00, 90, "B"),
        "C5":  ("U2", "10",  0.00,  1.85,  0, "B"),
        "C6":  ("U2", "20",  0.00, -1.85,  0, "B"),
        "R2":  ("U2", "24", -1.60, -1.85,  0, "B"),
        # --- U3 (contorno x -9,25..9,25): um único pad de +3V3 (pad 3).
        # Dois capacitores num pino só: um encosta, o outro fica no slot
        # seguinte da coluna. Não há terceira opção em 0805.
        "C7":  ("U3", "3",  -2.40,  0.00, 90, "B"),
        "C8":  ("U3", "3",  -2.40, -3.60, 90, "B"),
        # --- U4 (contorno x -2,85..2,25): entrada e saída na coluna esquerda
        "C9":  ("U4", "1",  -2.05, -0.25, 90, "B"),
        "C10": ("U4", "3",  -2.05,  0.25, 90, "B"),
        "R9":  ("U4", "1",  -6.50, -1.75, 90, "B"),
        "R10": ("U4", "1",  -6.50,  1.75, 90, "B"),
        # --- load switch: fila à direita do regulador, fora do contorno dele
        "Q1":  ("U4", "3",   6.00, -1.50,  0, "B"),
        "Q2":  ("U4", "3",   6.00,  2.50,  0, "B"),
        "R4":  ("U4", "3",  10.00, -1.50,  0, "B"),
        "R5":  ("U4", "3",  10.00,  1.50,  0, "B"),
        "R8":  ("U4", "3",  10.00,  4.00,  0, "B"),
        # --- proteção de polaridade, primeiro elemento depois do conector
        "Q3":  ("J1", "1",   0.00,  5.00,  0, "B"),
    },
}
PREFERENCIAS = PREFERENCIAS_POR_VERSAO[VERSAO]

# Corredor de cabo: o espaço que o conector precisa ADIANTE da boca, para o
# alojamento que encaixa nele e para o chicote. Nada disso está no courtyard
# do footprint — courtyard cobre a peça, não o que se conecta nela — e por
# isso o verificador dava a placa por boa com um furo M2 a 2,6 mm da boca do
# conector da bateria, onde a cabeça do parafuso encosta no alojamento.
#
# A boca do J1 é o recorte em -Y do contorno em F.Fab (x +/-3,15, de
# y = -3,2 a -1,6), com os terminais de solda dentro dele.
#
# 4,0 mm é o que a v1 comporta, não o que o conector gostaria.
#
# A varredura antiga registrada aqui ("3,0/4,0 mm furos a 120°; 5,0 mm furos a
# 73°, C11 sem lugar") foi medida antes das correções de ângulo de pad e de
# pad `custom`, e não descreve mais este código. Remedido: o placement fecha
# de 2,0 a 9,0 mm sem tirar peça nenhuma do lugar e sem mexer no triedro de
# furos (97° em toda a faixa). Quem trava é o PLANO DE TERRA — e isso só
# aparece regerando a placa inteira e rodando o DRC:
#
#     v1, 4,0 mm   0 violação de regra, 0 item solto            <- adotado
#     v1, 6,0 mm   0 violação de regra, 3 itens soltos: RT1.2 e R8.2 ficam
#                  sem saída de GND, o corredor corta o caminho do plano
#     v2, 6,0 mm   0 violação de regra, 0 item solto
#
# Um alojamento PHR-2 com chicote costuma pedir ~6 mm. A v1 não dá; a v2 dá,
# porque tem área para o plano contornar o corredor.
CORREDORES = {
    "J1": ((-3.95, -3.2 - CFG["corredor"]), (3.95, -3.2)),
}


def corredor(ref):
    """Retângulo do corredor em coordenadas da placa, ou None."""
    if ref not in CORREDORES or ref not in POSICOES:
        return None
    (ax, ay), (bx, by) = CORREDORES[ref]
    x, y, rot, _l = POSICOES[ref]
    pts = [gira(px, py, rot) for px, py in
           ((ax, ay), (bx, ay), (bx, by), (ax, by))]
    return (x + min(p[0] for p in pts), y + min(p[1] for p in pts),
            x + max(p[0] for p in pts), y + max(p[1] for p in pts))


POSICOES = {}

for _ref, _pos in FIXAS.items():
    POSICOES[_ref] = _pos

def bosses():
    return [(CX + sx * BOSS_X, CY + sy * BOSS_Y)
            for sx in (-1, 1) for sy in (-1, 1)]


def _cabe(x0, y0, x1, y1):
    """Retângulo inteiramente dentro do contorno, com folga de borda.

    Teste exato, não por bounding box: dentro do retângulo E fora de cada
    recorte de boss. A distância do retângulo ao centro do boss é a do ponto
    mais próximo, que para retângulo alinhado aos eixos é fechada.
    """
    if x0 < CX - LADO_X / 2 + BORDA or x1 > CX + LADO_X / 2 - BORDA:
        return False
    if y0 < CY - LADO_Y / 2 + BORDA or y1 > CY + LADO_Y / 2 - BORDA:
        return False
    for bx, by in bosses():
        dx = max(bx - x1, 0.0, x0 - bx)
        dy = max(by - y1, 0.0, y0 - by)
        if math.hypot(dx, dy) < BOSS_R + BORDA:
            return False
    return True


def contorno_pts(margem=0.0, por_arco=14):
    """Polígono do contorno, recuado de `margem`. Arcos amostrados."""
    hx, hy = LADO_X / 2 - margem, LADO_Y / 2 - margem
    br = BOSS_R + margem
    # onde o recorte corta cada lado: em x na aresta horizontal, em y na vertical
    ex = BOSS_X - math.sqrt(max(br * br - (hy - BOSS_Y) ** 2, 0.0))
    ey = BOSS_Y - math.sqrt(max(br * br - (hx - BOSS_X) ** 2, 0.0))
    trechos = [((-ex, hy), (ex, hy), (1, 1)),
               ((hx, ey), (hx, -ey), (1, -1)),
               ((ex, -hy), (-ex, -hy), (-1, -1)),
               ((-hx, -ey), (-hx, ey), (-1, 1))]
    pts = []
    for (ax, ay), (bx_, by_), (sx, sy) in trechos:
        pts += [(ax, ay), (bx_, by_)]
        cx_, cy_ = sx * BOSS_X, sy * BOSS_Y
        a1 = math.atan2(by_ - cy_, bx_ - cx_)
        # o arco passa pelo lado que aponta para o centro da placa
        amid = math.atan2(-sy, -sx)
        prox = trechos[(trechos.index(((ax, ay), (bx_, by_), (sx, sy))) + 1) % 4][0]
        a2 = math.atan2(prox[1] - cy_, prox[0] - cx_)
        varre = (a2 - a1) % (2 * math.pi)
        if not (0 < (amid - a1) % (2 * math.pi) < varre):
            varre -= 2 * math.pi
        for k in range(1, por_arco):
            a = a1 + varre * k / por_arco
            pts.append((cx_ + br * math.cos(a), cy_ + br * math.sin(a)))
    return [(CX + px, CY + py) for px, py in pts]


def _furo_legal(ang, raio, ja):
    a = math.radians(ang)
    x = round(CX + raio * math.cos(a), 2)
    y = round(CY + raio * math.sin(a), 2)
    NET["_H"] = (FURO_FP, "M2", {})
    POSICOES["_H"] = (x, y, 0, "F")
    try:
        if not _cabe(*extensao(FURO_FP, x, y, 0)):
            return None
        if any(conflito("_H", o) is not None for o in ja):
            return None
        return (x, y)
    finally:
        del POSICOES["_H"]; del NET["_H"]


_fixas = list(POSICOES)
_legais = {}
for _ang in range(0, 360):
    for _raio in FURO_RAIOS:
        _pt = _furo_legal(_ang, _raio, _fixas)
        if _pt:
            _legais[_ang] = (_raio, _pt)
            break


def _sep(a, b):
    d = abs(a - b) % 360
    return min(d, 360 - d)


_melhor, _trio = -1.0, None
_angs = sorted(_legais)
for _i, _a in enumerate(_angs):
    for _b in _angs[_i + 1:]:
        for _c in _angs:
            if _c <= _b:
                continue
            m = min(_sep(_a, _b), _sep(_b, _c), _sep(_a, _c))
            if m > _melhor:
                _melhor, _trio = m, (_a, _b, _c)

if _trio:
    for _k, _ang in enumerate(_trio, 1):
        _raio, (_fx, _fy) = _legais[_ang]
        NET[f"H{_k}"] = (FURO_FP, "M2", {})
        POSICOES[f"H{_k}"] = (_fx, _fy, 0, "F")
    FUROS = [(POSICOES[f"H{k}"][0], POSICOES[f"H{k}"][1]) for k in (1, 2, 3)]


def _livre(ref, x, y, rot, lado, ja):
    libfp = NET[ref][0]
    if not _cabe(*extensao(libfp, x, y, rot)):
        return False
    POSICOES[ref] = (x, y, rot, lado)
    try:
        return all(conflito(ref, outro) is None for outro in ja)
    finally:
        del POSICOES[ref]


def legaliza(ref, alvo, rot, lado, ja):
    """Espiral a partir do ponto preferido até achar posição legal.

    Devolve (x, y, rot) ou None. A busca também tenta a peça girada de 90°:
    num anel estreito a orientação costuma ser o que decide se cabe.
    """
    ax, ay = alvo
    for giro in (rot, (rot + 90) % 360):
        for raio in [r / 4 for r in range(0, 61)]:      # até 15 mm, passo 0,25
            passos = 1 if raio == 0 else max(8, int(raio * 8))
            for k in range(passos):
                a = 2 * math.pi * k / passos
                x = round(ax + raio * math.cos(a), 2)
                y = round(ay + raio * math.sin(a), 2)
                if _livre(ref, x, y, giro, lado, ja):
                    return x, y, giro
    return None


_nao_couberam = []
_movidos = []
for _ref, (_anc, _pad, _dx, _dy, _rot, _lado) in PREFERENCIAS.items():
    _px, _py = pad_xy(_anc, _pad)
    _alvo = (round(_px + _dx, 2), round(_py + _dy, 2))
    _r = legaliza(_ref, _alvo, _rot, _lado, list(POSICOES))
    if _r is None:
        _nao_couberam.append(_ref)
        continue
    _x, _y, _g = _r
    if (abs(_x - _alvo[0]) > 0.01 or abs(_y - _alvo[1]) > 0.01 or _g != _rot):
        _movidos.append((_ref, math.hypot(_x - _alvo[0], _y - _alvo[1]), _g != _rot))
    POSICOES[_ref] = (_x, _y, _g, _lado)


# =====================================================================
# Verificação
# =====================================================================
def verifica_encaixe():
    """Peças cujo cobre ou corpo sai do contorno (ou entra na folga de borda)."""
    fora = []
    for ref in POSICOES:
        x, y, rot, _lado = POSICOES[ref]
        ext = extensao(NET[ref][0], x, y, rot)
        if not _cabe(*ext):
            # o quanto invade: pior violação entre quadrado e recortes
            fol = [max(CX - LADO_X / 2 + BORDA - ext[0], ext[2] - (CX + LADO_X / 2 - BORDA),
                       CY - LADO_Y / 2 + BORDA - ext[1], ext[3] - (CY + LADO_Y / 2 - BORDA))]
            for bx, by in bosses():
                dx = max(bx - ext[2], 0.0, ext[0] - bx)
                dy = max(by - ext[3], 0.0, ext[1] - by)
                fol.append(BOSS_R + BORDA - math.hypot(dx, dy))
            fora.append((ref, max(fol)))
    return sorted(fora, key=lambda t: -t[1])


def verifica_colisao():
    """Pares em conflito, separados por invariante.

    Existe porque `verifica_encaixe` responde a pergunta errada: um monte de
    peças empilhadas no mesmo ponto passa perfeitamente no teste de "cabe no
    disco". Contenção e colisão são invariantes distintos — e colisão são
    dois: mecânica (corpo, na face de montagem) e cobre (pads, com o
    passante valendo nas duas faces).
    """
    refs = sorted(POSICOES)
    out = []
    for i, a in enumerate(refs):
        for b in refs[i + 1:]:
            c = conflito(a, b)
            if c:
                out.append((a, b) + c)
    return out


# =====================================================================
# Nets
# =====================================================================
nomes = sorted({n for _, _, m in NET.values() for n in m.values() if n != SCH.NC})
NETNUM = {"": 0}
for i, n in enumerate(nomes, 1):
    NETNUM[n] = i

# =====================================================================
# Roteamento
# =====================================================================
import router  # noqa: E402

PISTAS, VIAS, PENDENTES = router.rotear(
    net=NET, posicoes=POSICOES, netnum=NETNUM, pads_abs=pads_abs,
    centro=(CX, CY), contorno=(LADO_X, LADO_Y, BOSS_X, BOSS_Y, BOSS_R),
    borda=BORDA, nc=SCH.NC)

# =====================================================================
# Emissão
# =====================================================================
corpo = [[sym("net"), sym(str(i)), st(n)] for n, i in sorted(NETNUM.items(), key=lambda kv: kv[1])]

# ---------------------------------------------------------------------
# Modelos 3D
# ---------------------------------------------------------------------
# Quatro footprints apontam para modelos que a instalação do KiCad não tem —
# e são os quatro componentes mais altos. O .step saía com a placa e os
# passivos, sem nada que definisse altura, que é a única coisa que interessa
# quando alguém abre esse arquivo para conferir encaixe no invólucro.
#
# Dois ganham substituto honesto (mesmo envelope, diferença fora do que
# importa); dois são modelados em hardware/gen_3dmodels.py a partir do
# contorno do próprio footprint. A verificação no fim deste arquivo garante
# que nenhum footprint volte a ficar sem corpo em silêncio.
MODELOS_3D = {
    # ref: ([(caminho, rotacao_xyz, deslocamento_xyz)], por que)
    #
    # Os giros e deslocamentos foram MEDIDOS na placa montada, não deduzidos:
    # a convenção de sinal do (rotate) do KiCad não é óbvia, e o sinal errado
    # enfia o módulo para dentro do laminado sem aviso nenhum — foi o que
    # aconteceu com o WROOM na primeira tentativa (+90 em vez de -90 deixava
    # o substrato em Z 0,79..1,60, ou seja, dentro da placa de 1,6 mm).
    "U1": ([("${KIPRJMOD}/../../3dmodels/origem/wroom1u.step",
             (-90, 0, 0), (0, 0, 0))],
           "modelo real, MIT (Lambosaurus/KicadLib); vinha deitado"),
    "U3": ([("${KIPRJMOD}/../../3dmodels/origem/ra02.step",
             (0, 0, 90), (8.25, 8.5, 0))],
           "modelo real, Apache-2.0 (mithro); vinha girado e com origem no canto"),
    "J1": ([("${KIPRJMOD}/../../3dmodels/origem/jst.step",
             (0, 0, 0), (0, 0, 0))],
           "modelo real, MIT (arturo182); ja alinhado ao footprint"),
    "U2": ([("${KICAD10_3DMODEL_DIR}/Package_DFN_QFN.3dshapes/"
             "QFN-24-1EP_4x4mm_P0.5mm_EP2.6x2.6mm.step", (0, 0, 0), (0, 0, 0))],
           "substituto do KiCad: mesmo contorno, difere so no pad termico"),
}

TROCA = {"F.Cu": "B.Cu", "F.Paste": "B.Paste", "F.Mask": "B.Mask",
         "F.SilkS": "B.SilkS", "F.CrtYd": "B.CrtYd", "F.Fab": "B.Fab",
         "F.Adhes": "B.Adhes"}


def vira_camadas(no):
    """Troca camadas de frente por fundo, recursivamente.

    Só as CAMADAS: o KiCad guarda o footprint da face de baixo com as
    coordenadas locais da biblioteca e espelha na renderização (confirmado
    contra as placas de exemplo que acompanham o KiCad, onde as instâncias
    em B.Cu de um footprint assimétrico batem pad a pad com a biblioteca).
    """
    if isinstance(no, tuple):
        return (no[0], TROCA.get(no[1], no[1])) if no[0] == 'str' else no
    return [vira_camadas(x) for x in no]


faltando = []
for ref, (libfp, val, mapa) in NET.items():
    if ref not in POSICOES:
        faltando.append(ref); continue
    x, y, rot, lado = POSICOES[ref]
    fp = carrega_fp(libfp)
    fp = [e for e in fp if not (isinstance(e, list) and head(e) in
                                ("at", "uuid", "path", "property", "layer"))]
    fp[0] = sym("footprint")
    molde_3d = [None]
    novo = [sym("footprint"), st(libfp),
            [sym("layer"), st("B.Cu" if lado == "B" else "F.Cu")],
            [sym("uuid"), st(uid())],
            [sym("at"), sym(f"{x:g}"), sym(f"{y:g}")] + ([sym(str(rot))] if rot else []),
            [sym("property"), st("Reference"), st(ref),
             [sym("at"), sym("0"), sym("-4"), sym("0")],
             [sym("layer"), st("B.SilkS" if lado == "B" else "F.SilkS")],
             [sym("uuid"), st(uid())],
             [sym("effects"), [sym("font"), [sym("size"), sym("1"), sym("1")],
                               [sym("thickness"), sym("0.15")]]]
             + ([[sym("justify"), sym("mirror")]] if lado == "B" else [])],
            [sym("property"), st("Value"), st(val),
             [sym("at"), sym("0"), sym("4"), sym("0")],
             [sym("layer"), st("B.Fab" if lado == "B" else "F.Fab")],
             [sym("uuid"), st(uid())],
             [sym("effects"), [sym("font"), [sym("size"), sym("1"), sym("1")],
                               [sym("thickness"), sym("0.15")]]]
             + ([[sym("justify"), sym("mirror")]] if lado == "B" else [])]]

    for e in fp[1:]:
        if not isinstance(e, list):
            continue
        h = head(e)
        if h in ("descr", "tags", "attr", "model", "pad", "fp_line", "fp_circle",
                 "fp_arc", "fp_poly", "fp_rect", "fp_text", "zone", "embedded_fonts"):
            e = [z for z in e]
            if h == "model" and ref in MODELOS_3D:
                # Guarda o (model ...) original como molde e não o emite: as
                # peças entram depois, uma por arquivo. É preciso um arquivo
                # por peça porque o KiCad guarda UMA cor por modelo — com as
                # duas peças num arquivo só, a cor do substrato era descartada
                # e o módulo saía inteiramente metálico.
                molde_3d[0] = e
                continue
            if h == "pad":
                num = e[1][1]
                # O ângulo do pad no arquivo é ABSOLUTO: o KiCad grava
                # (ângulo da biblioteca + rotação do footprint), conferido
                # contra as placas de exemplo que acompanham o programa. Copiar
                # o ângulo da biblioteca e só girar o footprint produzia pads
                # com a forma NÃO girada — um 0805 em pé continuava com o pad
                # deitado. O DRC pegava como curto contra a pista vizinha.
                if rot:
                    e = [z for z in e]
                    for _k, _z in enumerate(e):
                        if isinstance(_z, list) and head(_z) == "at":
                            _a = float(_z[3][1]) if len(_z) > 3 else 0.0
                            e[_k] = [sym("at"), _z[1], _z[2],
                                     sym(f"{(_a + rot) % 360:g}")]
                            break
                net = mapa.get(num)
                if net and net != SCH.NC:
                    e = e + [[sym("net"), sym(str(NETNUM[net])), st(net)]]
                e = e + [[sym("uuid"), st(uid())]]
            if lado == "B":
                e = vira_camadas(e)
            novo.append(e)

    if ref in MODELOS_3D and molde_3d[0] is not None:
        for _cam, _rot, _off in MODELOS_3D[ref][0]:
            novo.append([sym("model"), st(_cam),
                         [sym("offset"), [sym("xyz")] + [sym(f"{v:g}") for v in _off]],
                         [sym("scale"), [sym("xyz"), sym("1"), sym("1"), sym("1")]],
                         [sym("rotate"), [sym("xyz")] + [sym(f"{v:g}") for v in _rot]]])
    corpo.append(novo)


# ---------------------------------------------------------------------
# Pistas e vias do roteador
# ---------------------------------------------------------------------
for (x1, y1, x2, y2, camada, largura, netid) in PISTAS:
    corpo.append([sym("segment"),
                  [sym("start"), sym(f"{x1:.4f}"), sym(f"{y1:.4f}")],
                  [sym("end"), sym(f"{x2:.4f}"), sym(f"{y2:.4f}")],
                  [sym("width"), sym(f"{largura:g}")],
                  [sym("layer"), st(camada)],
                  [sym("net"), sym(str(netid))],
                  [sym("uuid"), st(uid())]])

for (x, y, netid) in VIAS:
    corpo.append([sym("via"),
                  [sym("at"), sym(f"{x:.4f}"), sym(f"{y:.4f}")],
                  [sym("size"), sym("0.6")], [sym("drill"), sym("0.3")],
                  [sym("layers"), st("F.Cu"), st("B.Cu")],
                  [sym("net"), sym(str(netid))],
                  [sym("uuid"), st(uid())]])


# ---------------------------------------------------------------------
# Planos de terra e costura
# ---------------------------------------------------------------------
# Para módulo LoRa a orientação é plano sólido sob o módulo, com o retorno
# contínuo e as terras ligadas por VÁRIAS vias — não por um traço. Sem plano,
# o percurso de retorno de RF fica indefinido e o alcance despenca.
_pts = [[sym("xy"), sym(f"{_px:.3f}"), sym(f"{_py:.3f}")]
        for _px, _py in contorno_pts(BORDA)]

for _lay in ("F.Cu", "B.Cu"):
    corpo.append([sym("zone"),
                  [sym("net"), sym(str(NETNUM["GND"]))], [sym("net_name"), st("GND")],
                  [sym("layer"), st(_lay)], [sym("uuid"), st(uid())],
                  [sym("name"), st(f"GND_{_lay}")],
                  [sym("hatch"), sym("edge"), sym("0.5")],
                  # Ligação SÓLIDA, não alívio térmico. Alívio térmico existe
                  # para facilitar solda manual; esta placa é de montagem por
                  # refusão, e sob um módulo de RF o que importa é o retorno
                  # ter a menor indutância possível. Alívio também produzia
                  # starved_thermal nos pads que só cabiam com um braço.
                  [sym("connect_pads"), sym("yes"), [sym("clearance"), sym("0.3")]],
                  [sym("min_thickness"), sym("0.2")],
                  [sym("filled_areas_thickness"), sym("no")],
                  # island_removal_mode 0 = descartar ilhas (1 seria MANTER —
                  # o enum do KiCad é Always/Never/Área). Uma ilha do plano
                  # é cobre que não liga a nada: não conduz retorno, não
                  # blinda, e sob um módulo de RF ainda vira um ressonador
                  # parasita de dimensão arbitrária. Mantê-la só existiria
                  # para o preenchimento parecer contínuo no desenho.
                  [sym("fill"), sym("yes"),
                   [sym("thermal_gap"), sym("0.3")],
                   [sym("thermal_bridge_width"), sym("0.4")],
                   [sym("island_removal_mode"), sym("0")]],
                  [sym("polygon"), [sym("pts")] + _pts]])

# Vias de costura ligando os dois planos, onde o plano existe dos dois lados.
_vias_costura, _terra_ok, _terra_falha = router._G["terra"]
_costura = 0
for (_vx, _vy) in _vias_costura:
    corpo.append([sym("via"),
                  [sym("at"), sym(f"{_vx:.3f}"), sym(f"{_vy:.3f}")],
                  [sym("size"), sym("0.6")], [sym("drill"), sym("0.3")],
                  [sym("layers"), st("F.Cu"), st("B.Cu")],
                  [sym("net"), sym(str(NETNUM["GND"]))],
                  [sym("uuid"), st(uid())]])
    _costura += 1

# ---------------------------------------------------------------------
# Contorno: retângulo com quatro recortes de canto
# ---------------------------------------------------------------------
_hx, _hy = LADO_X / 2, LADO_Y / 2
_ex = BOSS_X - math.sqrt(BOSS_R ** 2 - (_hy - BOSS_Y) ** 2)
_ey = BOSS_Y - math.sqrt(BOSS_R ** 2 - (_hx - BOSS_X) ** 2)
_TRACO = [[sym("stroke"), [sym("width"), sym("0.1")], [sym("type"), sym("default")]],
          [sym("layer"), st("Edge.Cuts")]]
for (_ax, _ay), (_bx, _by) in (((-_ex,  _hy), ( _ex,  _hy)),
                               (( _hx,  _ey), ( _hx, -_ey)),
                               (( _ex, -_hy), (-_ex, -_hy)),
                               ((-_hx, -_ey), (-_hx,  _ey))):
    corpo.append([sym("gr_line"),
                  [sym("start"), sym(f"{CX + _ax:.4f}"), sym(f"{CY + _ay:.4f}")],
                  [sym("end"), sym(f"{CX + _bx:.4f}"), sym(f"{CY + _by:.4f}")]]
                 + _TRACO + [[sym("uuid"), st(uid())]])
# Os quatro recortes de boss. O ponto médio do arco fica do lado do CENTRO da
# placa — é um recorte, não um arredondamento: ele tira material do canto.
for _sx, _sy in ((1, 1), (1, -1), (-1, -1), (-1, 1)):
    _cx, _cy = _sx * BOSS_X, _sy * BOSS_Y
    _p1 = (_sx * _ex, _sy * _hy)
    _p2 = (_sx * _hx, _sy * _ey)
    _pm = (_cx - _sx * BOSS_R / math.sqrt(2), _cy - _sy * BOSS_R / math.sqrt(2))
    corpo.append([sym("gr_arc"),
                  [sym("start"), sym(f"{CX + _p1[0]:.4f}"), sym(f"{CY + _p1[1]:.4f}")],
                  [sym("mid"), sym(f"{CX + _pm[0]:.4f}"), sym(f"{CY + _pm[1]:.4f}")],
                  [sym("end"), sym(f"{CX + _p2[0]:.4f}"), sym(f"{CY + _p2[1]:.4f}")]]
                 + _TRACO + [[sym("uuid"), st(uid())]])

# ---------------------------------------------------------------------
# Documento
# ---------------------------------------------------------------------
doc = [sym("kicad_pcb"), [sym("version"), sym("20240108")],
       [sym("generator"), st("kaelix_gen")], [sym("generator_version"), st("9.0")],
       [sym("general"), [sym("thickness"), sym("1.6")], [sym("legacy_teardrops"), sym("no")]],
       [sym("paper"), st("A4")],
       [sym("layers"),
        [sym("0"), st("F.Cu"), sym("signal")],
        [sym("31"), st("B.Cu"), sym("signal")],
        [sym("32"), st("B.Adhes"), sym("user"), st("B.Adhesive")],
        [sym("33"), st("F.Adhes"), sym("user"), st("F.Adhesive")],
        [sym("34"), st("B.Paste"), sym("user")],
        [sym("35"), st("F.Paste"), sym("user")],
        [sym("36"), st("B.SilkS"), sym("user"), st("B.Silkscreen")],
        [sym("37"), st("F.SilkS"), sym("user"), st("F.Silkscreen")],
        [sym("38"), st("B.Mask"), sym("user")],
        [sym("39"), st("F.Mask"), sym("user")],
        [sym("40"), st("Dwgs.User"), sym("user"), st("User.Drawings")],
        [sym("41"), st("Cmts.User"), sym("user"), st("User.Comments")],
        [sym("42"), st("Eco1.User"), sym("user"), st("User.Eco1")],
        [sym("43"), st("Eco2.User"), sym("user"), st("User.Eco2")],
        [sym("44"), st("Edge.Cuts"), sym("user")],
        [sym("45"), st("Margin"), sym("user")],
        [sym("46"), st("B.CrtYd"), sym("user"), st("B.Courtyard")],
        [sym("47"), st("F.CrtYd"), sym("user"), st("F.Courtyard")],
        [sym("48"), st("B.Fab"), sym("user")],
        [sym("49"), st("F.Fab"), sym("user")]],
       [sym("setup"), [sym("pad_to_mask_clearance"), sym("0")]]] + corpo

(PROJ / "kaelix.kicad_pcb").write_text(dump(doc) + "\n", encoding="utf-8")

# ---------------------------------------------------------------------
# Relatório
# ---------------------------------------------------------------------
col = verifica_colisao()
if col:
    print(f"COLISÃO — {len(col)} pares:")
    for a, b, tipo, ox, oy in sorted(col, key=lambda c: -c[3] * c[4])[:12]:
        print(f"   {a:4s} x {b:4s}  {tipo:9s} invasão {ox:.2f} x {oy:.2f} mm")
else:
    print(f"colisão:  nenhum par se sobrepõe ({len(POSICOES)} componentes)")

fora = verifica_encaixe()
if fora:
    print("FORA DO CONTORNO:", ", ".join(f"{r} ({v:.2f} mm)" for r, v in fora))
else:
    print(f"encaixe:  tudo dentro do contorno ({LADO_X:g} x {LADO_Y:g} mm, "
          f"4 recortes r={BOSS_R:g} mm a {2 * BOSS_X:g} x {2 * BOSS_Y:g} mm "
          f"entre eixos)")
if _trio is None:
    print(f"FUROS: nenhuma posição legal para o triedro M2 "
          f"({len(_legais)} ângulos livres de 360)")
else:
    print(f"furos:    3 x M2 em {', '.join(str(a) + chr(176) for a in _trio)}, "
          f"raios {', '.join(f'{_legais[a][0]:.1f}' for a in _trio)} mm — "
          f"menor separação {_melhor:.0f}{chr(176)} (ideal 120{chr(176)}), "
          f"{len(_legais)} ângulos legais de 360")

# A regra de desacoplamento é 1 a 3 mm do pino. Aqui ela é MEDIDA e impressa:
# regra que não é verificada não é regra, e um capacitor a 7 mm do pino não
# desacopla nada. As peças que aparecem nesta lista são dívida declarada, não
# esquecimento — o anel livre em volta de cada CI é o que há, e a alternativa
# testada (mover o U2 para a região aberta da face de baixo) melhorava as
# distâncias e piorava a conectividade do plano de GND de 1 para 4 pads.
# Só entra aqui o que de fato DESACOPLA um rail de alimentação, pela netlist:
# C2/C3 no +3V3 do U1, C7/C8 no +3V3 do U3, C10 na saída do LDO e C4 no
# +3V3_SW do U2. Os outros quatro estavam na lista e mediam a coisa errada:
# C1 é o RC do EN, C5 e C6 são o regulador interno e a bomba de carga do
# MPU6050 (exigência de folha de dados, não de PDN), C9 é a entrada do LDO.
#
# E a distância medida aqui é EUCLIDIANA. O que entra na indutância do laço é
# o comprimento da PISTA, que numa placa de duas camadas diverge — no C8 da
# v1, por 3,25x. Ver hardware/pdn.py e a figura 9.
_DESACOPLA = ("C2", "C3", "C4", "C7", "C8", "C10")
_longe = []
for _r, (_a, _pd, _dx, _dy, _rt, _ld) in PREFERENCIAS.items():
    if _r not in _DESACOPLA or _r not in POSICOES:
        continue
    _px, _py = pad_xy(_a, _pd)
    _d = math.hypot(POSICOES[_r][0] - _px, POSICOES[_r][1] - _py)
    if _d > 3.0:
        _longe.append((_r, _a, _pd, _d))
if _longe:
    print(f"desacopl: {len(_longe)} capacitor(es) acima de 3 mm do pino que servem:")
    for _r, _a, _pd, _d in sorted(_longe, key=lambda t: -t[3]):
        print(f"   {_r:4s} -> {_a}.{_pd}  {_d:.2f} mm")
else:
    print("desacopl: todos a menos de 3 mm do pino que servem")

if _nao_couberam:
    print("SEM LUGAR:", ", ".join(_nao_couberam))
if _movidos:
    print(f"movidos:  {len(_movidos)} peças reposicionadas a partir da preferência "
          f"(máx {max(d for _r, d, _g in _movidos):.2f} mm)")
if PENDENTES:
    print(f"NÃO ROTEADO — {len(PENDENTES)} ligações:")
    for a, b, net in PENDENTES[:12]:
        print(f"   {net:12s} {a} -> {b}")
else:
    print(f"roteamento: {len(PISTAS)} segmentos, {len(VIAS)} vias, "
          f"{_costura} de costura — 0 ligações pendentes")
    _esc_ok, _esc_falha = router._G.get("escapes", ([], []))
    if _esc_ok:
        print(f"terra:    {len(_esc_ok)} pad(s) ilhado(s) pelo encapsulamento, "
              f"com escape roteado antes dos sinais: {', '.join(_esc_ok)}")
    if _esc_falha:
        print(f"TERRA SEM ESCAPE: {', '.join(_esc_falha)}")
    if _terra_ok:
        print(f"terra:    {len(_terra_ok)} pad(s) resolvido(s) na verificação final: "
              f"{', '.join(_terra_ok)}")
    if _terra_falha:
        print(f"TERRA SEM SAÍDA: {', '.join(_terra_falha)}")
# ---------------------------------------------------------------------
# Todo footprint tem corpo 3D que existe em disco?
# ---------------------------------------------------------------------
# Sem isto, a ausência só aparece quando alguém abre o .step num CAD — e o
# arquivo parece completo, porque a placa e os passivos estão lá.
_3D = pathlib.Path("/Applications/KiCad/KiCad.app/Contents/SharedSupport/3dmodels")
_sem_corpo, _substituidos = [], []
for _ref, (_libfp, _v, _m) in NET.items():
    if _ref.startswith("H"):
        continue                      # furo mecânico não tem corpo
    _mods = [_mm[1][1] for _mm in find(carrega_fp(_libfp), "model")]
    if not _mods:
        _sem_corpo.append(f"{_ref} (footprint sem (model))")
        continue
    _lista = ([c for c, _r, _o in MODELOS_3D[_ref][0]]
              if _ref in MODELOS_3D else [_mods[0]])
    for _cam in _lista:
        _res = (_cam.replace("${KICAD10_3DMODEL_DIR}", str(_3D))
                    .replace("${KICAD9_3DMODEL_DIR}", str(_3D))
                    .replace("${KIPRJMOD}", str(PROJ)))
        if not pathlib.Path(_res).exists():
            _sem_corpo.append(f"{_ref} -> {pathlib.Path(_res).name}")
    if _ref in MODELOS_3D:
        _substituidos.append(f"{_ref} ({MODELOS_3D[_ref][1]})")
if _sem_corpo:
    print(f"SEM CORPO 3D — {len(_sem_corpo)}: " + ", ".join(_sem_corpo))
else:
    print(f"modelo 3D: todos os {len(NET) - 3} componentes com corpo em disco")
for _t in _substituidos:
    print(f"   {_t}")

print(f"gerado: kaelix.kicad_pcb — {len(NET)} componentes, {len(NETNUM) - 1} nets")
if faltando:
    print("SEM POSIÇÃO (não colocados):", ", ".join(faltando))
