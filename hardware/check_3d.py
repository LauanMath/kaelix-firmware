"""Mede o envelope real do .step exportado.

Por que não dá para medir com texto: num STEP a geometria de cada componente
fica em coordenadas LOCAIS e é posicionada por matriz de transformação. Ler
os CARTESIAN_POINT do arquivo e tirar mínimo e máximo mede o corpo da placa e
mais um monte de origens de sistemas locais — dá um número, e o número está
errado. Foi assim que passei a achar que o modelo estava completo quando os
quatro componentes mais altos não estavam nele.

Aqui o arquivo é aberto por um kernel de CAD, que resolve as transformações.

Rodar:  /Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd \\
            hardware/check_3d.py
"""

import os
import pathlib
import sys

import Part

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

AQUI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
from sexpr import parse, find, find1  # noqa: E402

VERSAO = os.environ.get("KAELIX_PCB", "v1")
PROJ = AQUI / "pcb" / VERSAO
CAMINHO = PROJ / "kaelix.step"
DIR3D = pathlib.Path("/Applications/KiCad/KiCad.app/Contents/SharedSupport/3dmodels")

# Vão interno do invólucro, por versão — mesma tabela de gen_involucro.py.
# A v1 sai de CORPO_EXT 50,0 menos 2 x PAREDE 3,5; a v2 é moldada à célula
# de 2000 mAh. Não é quadrado na v2, então a folga é medida em cada eixo.
VAO_INTERNO = {"v1": (43.0, 43.0), "v2": (62.0, 52.0), "v3": (62.0, 52.0)}[VERSAO]
# Lado em que uma peça passa da cavidade POR PROJETO, e até quanto: o USB-C
# da v3 entra no furo da parede -X. Aqui só se confere que o excesso fica
# naquele lado e dentro da espessura da parede (3,5 mm); se ele de fato
# passa pelo furo sem tocar a parede é interseção de sólidos, em
# gen_involucro.py.
PASSA_PAREDE = {"v3": {"-X": 3.5}}.get(VERSAO, {})
ESPESSURA_PLACA = 1.6

# Part.Shape().read() ACHATA o assembly, aplicando as matrizes de cada nível.
# Com Import.insert() cada objeto devolve Shape em coordenadas LOCAIS, sem a
# matriz do pai — os componentes apareciam empilhados na origem e o envelope
# saía com 172 mm de largura numa placa de 40.
# ------------------------------------------------------------------
# 1. Todo modelo referenciado abre e contém sólido?
# ------------------------------------------------------------------
# Existir em disco não basta: um STEP pode ter cabeçalho válido e nenhuma
# geometria. O KiCad ignora esse arquivo em silêncio, e o .step exportado
# sai sem a peça — sem aviso nenhum, porque tudo "funcionou".
pcb = parse((PROJ / "kaelix.kicad_pcb").read_text())[0]
ruins, conferidos = [], 0
for fp in find(pcb, "footprint"):
    ref = [pr[2][1] for pr in find(fp, "property") if pr[1][1] == "Reference"][0]
    for mod in find(fp, "model"):
        cam = (mod[1][1].replace("${KICAD10_3DMODEL_DIR}", str(DIR3D))
                        .replace("${KICAD9_3DMODEL_DIR}", str(DIR3D))
                        .replace("${KIPRJMOD}", str(PROJ)))
        if not pathlib.Path(cam).exists():
            ruins.append(f"{ref}: arquivo ausente ({pathlib.Path(cam).name})")
            continue
        try:
            sh = Part.Shape(); sh.read(cam)
            if sh.isNull() or not sh.Solids:
                ruins.append(f"{ref}: STEP sem solido ({pathlib.Path(cam).name})")
            else:
                conferidos += 1
        except Exception as exc:
            ruins.append(f"{ref}: nao abre ({pathlib.Path(cam).name}: {exc})")
print(f"modelos conferidos: {conferidos} abrem e tem solido")
for r in ruins:
    print(f"  MODELO RUIM  {r}")

# ------------------------------------------------------------------
# 2. Envelope do conjunto
# ------------------------------------------------------------------
forma = Part.Shape()
forma.read(str(CAMINHO))

if forma.isNull():
    raise SystemExit("STEP sem sólido nenhum")
solidos = len(forma.Solids)
caixa = forma.BoundBox

larg, prof, alt = caixa.XLength, caixa.YLength, caixa.ZLength
print(f"solidos no modelo: {solidos}")
print(f"envelope: {larg:.2f} x {prof:.2f} x {alt:.2f} mm")
print(f"          X {caixa.XMin:8.2f}..{caixa.XMax:8.2f}")
print(f"          Y {caixa.YMin:8.2f}..{caixa.YMax:8.2f}")
print(f"          Z {caixa.ZMin:8.2f}..{caixa.ZMax:8.2f}")
# Quem define a altura. Um número de envelope sozinho não diz se o problema
# é a placa inteira ou uma peça só — e aqui é uma peça só.
altos = sorted(((sl.BoundBox.ZMax - sl.BoundBox.ZMin, sl.BoundBox) for sl in forma.Solids),
               reverse=True, key=lambda t: t[0])[:3]
print("o que define a altura:")
for h, b in altos:
    print(f"   {b.XLength:5.1f} x {b.YLength:5.1f} x {h:5.2f} mm   "
          f"Z {b.ZMin:6.2f}..{b.ZMax:6.2f}")

# ------------------------------------------------------------------
# 3. Peças que ocupam o mesmo espaço
# ------------------------------------------------------------------
# O verificador de colisão do gerador é 2D e por face. Ele não vê o que
# acontece em Z, e não vê modelo mal posicionado — foi assim que o corpo do
# conector da bateria apareceu por cima de dois passivos: o modelo estava
# deslocado 2,65 mm da origem do footprint, e nenhum teste 2D podia notar.
#
# Par do MESMO componente é ignorado: modelo de encapsulamento costuma trazer
# corpo e terminais como sólidos que se tocam, por construção.
pcb = parse((PROJ / "kaelix.kicad_pcb").read_text())[0]
origens = {}
for fp in find(pcb, "footprint"):
    ref = [pr[2][1] for pr in find(fp, "property") if pr[1][1] == "Reference"][0]
    at = find1(fp, "at")
    origens[ref] = (float(at[1][1]), -float(at[2][1]),
                    find1(fp, "layer")[1][1])


def dono(bb):
    """Componente a que o sólido pertence: origem mais próxima NA MESMA FACE.

    Sem o filtro de face, um terminal do regulador (face de baixo) era
    atribuído ao capacitor que por acaso está mais perto em XY na face de
    cima — e o corpo do próprio U4 contra o próprio terminal virava uma
    "interferência entre componentes" que a placa não tem, já que existe
    1,6 mm de laminado entre as duas faces.
    """
    cx, cy = (bb.XMin + bb.XMax) / 2.0, (bb.YMin + bb.YMax) / 2.0
    face = "F.Cu" if bb.ZMax > ESPESSURA_PLACA / 2 else "B.Cu"
    cand = [k for k in origens if origens[k][2] == face] or list(origens)
    r = min(cand, key=lambda k: (origens[k][0] - cx) ** 2 + (origens[k][1] - cy) ** 2)
    d = ((origens[r][0] - cx) ** 2 + (origens[r][1] - cy) ** 2) ** 0.5
    return r, d


corpos = sorted(forma.Solids, key=lambda sl: -(sl.BoundBox.XLength * sl.BoundBox.YLength))
corpos = corpos[1:]                       # fora a placa: todo mundo encosta nela
choques = {}
for i, a in enumerate(corpos):
    for b in corpos[i + 1:]:
        if not a.BoundBox.intersect(b.BoundBox):
            continue
        try:
            com = a.common(b)
        except Exception:
            continue
        if com.isNull() or com.Volume < 1e-3:
            continue
        ra, da = dono(a.BoundBox)
        rb, db = dono(b.BoundBox)
        if ra == rb:
            continue
        k = tuple(sorted((ra, rb)))
        choques[k] = choques.get(k, 0.0) + com.Volume
if choques:
    print(f"INTERFERENCIA entre {len(choques)} par(es) de componentes:")
    for (ra, rb), v in sorted(choques.items(), key=lambda t: -t[1]):
        print(f"   {ra} x {rb}: {v:.2f} mm3")
else:
    print(f"interferencia: nenhuma entre os {len(corpos)} corpos")

fx = VAO_INTERNO[0] - larg
fy = VAO_INTERNO[1] - prof
folga = min(fx, fy)
if not PASSA_PAREDE:
    print(f"vao interno do involucro: {VAO_INTERNO[0]:.1f} x {VAO_INTERNO[1]:.1f} mm "
          f"-> folga {fx / 2:.2f} mm por lado em X, {fy / 2:.2f} mm em Y")
else:
    # Folga lado a lado, a partir do centro do substrato: o sólido de maior
    # área em planta. Nenhum componente chega perto dos 61 x 51 do laminado;
    # filtrar pela espessura de 1,6 mm pegava corpo de conector.
    sub = max(forma.Solids, key=lambda sl: sl.BoundBox.XLength * sl.BoundBox.YLength)
    pcx, pcy = sub.BoundBox.Center.x, sub.BoundBox.Center.y
    lados = {"-X": VAO_INTERNO[0] / 2 - (pcx - caixa.XMin),
             "+X": VAO_INTERNO[0] / 2 - (caixa.XMax - pcx),
             "-Y": VAO_INTERNO[1] / 2 - (pcy - caixa.YMin),
             "+Y": VAO_INTERNO[1] / 2 - (caixa.YMax - pcy)}
    print(f"vao interno do involucro: {VAO_INTERNO[0]:.1f} x {VAO_INTERNO[1]:.1f} mm, "
          f"folga por lado: " + ", ".join(f"{k} {v:.2f}" for k, v in lados.items()))
    folga = 0.0
    for lado, v in lados.items():
        if v >= 0:
            continue
        if -v <= PASSA_PAREDE.get(lado, 0.0):
            print(f"   {lado}: {-v:.2f} mm entram na parede pelo furo, por projeto "
                  f"(ate {PASSA_PAREDE[lado]:.1f}) — conferir em gen_involucro.py")
        else:
            folga = min(folga, v)
if folga < 0:
    print("NAO CABE no vao interno")
# flush antes de sair: o freecadcmd não descarrega o buffer no SystemExit, e
# o relatório inteiro some justamente quando há algo a relatar.
sys.stdout.flush()
if ruins or folga < 0 or choques:
    raise SystemExit(1)
