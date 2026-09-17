"""Solido do caminho de rigidez: base + corpo, ja unidos pelo spigot.

Roda sob freecadcmd. Nao faz analise; so prepara a geometria que o
fem_montagem.py maneja.

O caminho que interessa e o do notebook analise-involucro.ipynb:

    motor -> imas -> base ASA -> spigot Ø28 -> corpo ASA -> PCB -> MPU6050

Base e corpo sao pecas separadas com 0,2 mm de folga radial no spigot; no
produto elas sao aparafusadas (inserto M3 Ø4 no topo do spigot). Aqui a junta
e tratada como colada: um cilindro Ø28,4 preenche o rebaixo e as tres pecas
viram um solido so. Junta colada SUPERESTIMA a rigidez -- e o limite otimista.
"""
import pathlib
import sys
import Part
from FreeCAD import Vector

AQUI = pathlib.Path(__file__).resolve().parent
BASE_ALT, FUNDO = 9.0, 8.0
REB_D, REB_H = 28.4, 3.3
BOSS_FURO = 2.6

# Os furos-guia M3 sao TAPADOS aqui. Dois motivos, nesta ordem: o parafuso
# esta neles no produto, entao o vazio nao existe na peca montada; e o
# cilindro de Ø2,6 por 54 mm de comprimento produzia elementos degenerados
# (jacobiano nao positivo no elemento 57876 do CalculiX) que impediam a
# solucao. Efeito sobre a rigidez do caminho: desprezivel — sao 4 x 287 mm3
# num solido de 91 cm3, longe da linha neutra de nada.
VAO = {"v1": ((43.0, 43.0), 3.5, 54.0), "v2": ((62.0, 52.0), 2.5, 30.0)}

for v in ("v1", "v2"):
    d = AQUI / "involucro" / v
    (vx, vy), recuo, boss_alt = VAO[v]
    base = Part.Shape(); base.read(str(d / "base.step"))
    corpo = Part.Shape(); corpo.read(str(d / "corpo.step"))
    corpo.translate(Vector(0, 0, BASE_ALT))
    cola = Part.makeCylinder(REB_D / 2, REB_H, Vector(0, 0, BASE_ALT))
    junto = base.fuse(corpo).fuse(cola)
    bx, by = vx / 2 - recuo, vy / 2 - recuo
    z0 = BASE_ALT + FUNDO
    for sx in (-1, 1):
        for sy in (-1, 1):
            junto = junto.fuse(Part.makeCylinder(
                BOSS_FURO / 2, boss_alt, Vector(sx * bx, sy * by, z0)))
    junto = junto.fuse(Part.makeCylinder(
        BOSS_FURO / 2, FUNDO, Vector(0, 0, BASE_ALT)))
    junto = junto.removeSplitter()

    # Invólucro fechado, para a análise térmica: o caminho de rigidez não
    # precisa da tampa, mas o balanço de calor precisa — ela fecha a cavidade
    # e responde por parte da área externa de troca.
    tampa = Part.Shape(); tampa.read(str(d / "tampa.step"))
    tampa.translate(Vector(0, 0, BASE_ALT + boss_alt + FUNDO))
    fechado = junto.fuse(tampa).removeSplitter()
    solidos = junto.Solids
    saida = AQUI / "fem" / v
    saida.mkdir(parents=True, exist_ok=True)
    alvo = saida / "caminho.step"
    junto.exportStep(str(alvo))
    fechado.exportStep(str(saida / "involucro.step"))
    conf = Part.Shape(); conf.read(str(alvo))
    bb = conf.BoundBox
    bbf = fechado.BoundBox
    print(f"   involucro fechado: {fechado.Volume / 1000:.1f} cm3, "
          f"{bbf.XLength:.0f} x {bbf.YLength:.0f} x {bbf.ZLength:.0f} mm")
    print(f"{v}: {len(solidos)} solido(s), volume {junto.Volume / 1000:.1f} cm3, "
          f"envelope {bb.XLength:.1f} x {bb.YLength:.1f} x {bb.ZLength:.1f} mm "
          f"-> {alvo.name} ({len(conf.Solids)} solido lido de volta)")
    if len(solidos) != 1:
        print("   ATENCAO: base e corpo nao ficaram unidos")
sys.stdout.flush()
