"""Modal do caminho de montagem: imas -> base ASA -> spigot -> corpo -> carga.

O notebook `experiments/notebooks/analise-involucro.ipynb` estimou esse
caminho como mola em serie e achou f_n ~= 560 Hz, dentro dos 10-1000 Hz da
ISO 10816-3 — hipotese CONFIRMADA, e o motivo da recomendacao de base
metalica. Aquela conta e de mola equivalente; aqui a geometria e a de verdade,
e ha duas versoes de involucro para comparar, o que antes nao existia.

A pergunta: a v2, 24 mm mais baixa, tira a frequencia da banda sozinha, ou a
base metalica continua necessaria?

    uv run --no-project --with gmsh python hardware/fem_montagem.py
"""
import math
import os
import pathlib
import subprocess
import sys

AQUI = pathlib.Path(__file__).resolve().parent
CCX = pathlib.Path("/Applications/FreeCAD.app/Contents/Resources/bin/ccx")

# ASA impresso. E de 2,0 GPa e o valor de folha para ASA macico; peca impressa
# a 35% de preenchimento e ANISOTROPICA e mais mole, sobretudo entre camadas.
# Isotropico e macico aqui e o limite OTIMISTA: a peca real ressoa mais baixo.
E_ASA = 2000.0           # MPa
NU_ASA = 0.35
RHO_ASA = 1.07e-9        # t/mm3

BASE_ALT, FUNDO = 9.0, 8.0
MAG_R, MAG_D, MAG_P = 20.0, 10.0, 3.2

# Cargas, em gramas. A placa vem medida de fem_modal.py; a celula, do catalogo.
CARGA = {
    "v1": dict(vao=(43.0, 43.0), placa=9.4, bateria=10.0, tampa=13.8,
               nota="celula de 500 mAh (que nem entra; ver involucro/README)"),
    "v2": dict(vao=(62.0, 52.0), placa=13.8, bateria=35.0, tampa=23.8,
               nota="celula real de 2000 mAh"),
}

# Onde a carga se apoia decide o resultado, e o projeto nao decide.
#
#   PISO   piso da cavidade, que e o unico lugar onde ha material na altura
#          em que a montagem poe a placa. Fica em cima do spigot: rigido.
#   TOPO   borda superior do corpo — e onde `analise-involucro.ipynb` poe a
#          massa, ao tratar o corpo como viga engastada com carga na ponta.
#          Pior caso para o modo de flexao lateral.
#
# A tampa entra SEMPRE no topo: ela esta la nas duas hipoteses.
MODOS = 6
# Malha grosseira SUPERESTIMA rigidez, e portanto frequencia. 3,5 mm numa
# parede de 3,5 mm da um elemento na espessura. A variavel existe para medir
# a convergencia, nao para ajustar resultado.
TAM_MALHA = float(os.environ.get("KAELIX_MALHA", "3.5"))
BANDA = (10.0, 1000.0)


def malha(step, inp):
    import gmsh
    gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", 0)
    gmsh.model.add("caminho")
    gmsh.model.occ.importShapes(str(step))
    # O solido vem de um fuse com removeSplitter; sobram faces coincidentes que
    # o gerador de malha recusa ("overlapping facets"). healShapes costura as
    # arestas curtas e remove os slivers antes de sincronizar.
    gmsh.option.setNumber("Geometry.OCCFixDegenerated", 1)
    gmsh.option.setNumber("Geometry.OCCFixSmallEdges", 1)
    gmsh.option.setNumber("Geometry.OCCFixSmallFaces", 1)
    gmsh.option.setNumber("Geometry.OCCSewFaces", 1)
    gmsh.model.occ.healShapes(makeSolids=True, sewFaces=True,
                              fixDegenerated=True, fixSmallEdges=True,
                              fixSmallFaces=True)
    gmsh.model.occ.removeAllDuplicates()
    gmsh.model.occ.synchronize()
    vol = [t for d, t in gmsh.model.getEntities(3)]
    gmsh.model.addPhysicalGroup(3, vol, name="ASA")
    gmsh.option.setNumber("Mesh.MeshSizeFromCurvature", 8)
    gmsh.option.setNumber("Mesh.MeshSizeMax", TAM_MALHA)
    gmsh.option.setNumber("Mesh.MeshSizeMin", 1.0)
    # Nos de meio-lado projetados sobre as faces curvas (canto R7, bosses,
    # spigot) inverteram elementos: o CalculiX parava com "nonpositive
    # jacobian". Com SecondOrderLinear os nos de meio-lado ficam na reta entre
    # os vertices — perde-se fidelidade geometrica na curva, ganha-se malha
    # valida. Para a primeira frequencia a troca compensa.
    gmsh.option.setNumber("Mesh.SecondOrderLinear", 1)
    gmsh.option.setNumber("Mesh.Optimize", 1)
    gmsh.option.setNumber("Mesh.OptimizeNetgen", 1)
    gmsh.option.setNumber("Mesh.OptimizeThreshold", 0.35)
    gmsh.option.setNumber("Mesh.ElementOrder", 2)
    gmsh.option.setNumber("Mesh.SecondOrderIncomplete", 0)
    gmsh.model.mesh.generate(3)
    gmsh.write(str(inp))
    nn = len(gmsh.model.mesh.getNodes()[0])
    _, tags, _ = gmsh.model.mesh.getElements(3)
    gmsh.finalize()
    return nn, sum(len(t) for t in tags)


def le_nos(caminho):
    nos, dentro = {}, False
    for ln in caminho.read_text().splitlines():
        if ln.startswith("*"):
            dentro = ln.upper().startswith("*NODE")
            continue
        if not dentro or not ln.strip():
            continue
        c = ln.split(",")
        if len(c) >= 4:
            nos[int(c[0])] = (float(c[1]), float(c[2]), float(c[3]))
    return nos


def escreve(base_inp, destino, fixos, cargas, modos=MODOS):
    """`cargas` e uma lista de (nome, nós, massa total em toneladas)."""
    linhas = [base_inp.read_text().rstrip()]
    linhas.append("*NSET, NSET=IMAS")
    for k in range(0, len(fixos), 8):
        linhas.append(", ".join(str(v) for v in fixos[k:k + 8]) + ",")
    eid = 10_000_000
    for nome, ns, _m in cargas:
        linhas.append(f"*ELEMENT, TYPE=MASS, ELSET={nome}")
        for n in ns:
            eid += 1
            linhas.append(f"{eid}, {n}")
    for nome, ns, m in cargas:
        linhas.append(f"*MASS, ELSET={nome}")
        linhas.append(f"{m / len(ns):.8e}")
    linhas += [
        "*MATERIAL, NAME=ASA",
        "*ELASTIC", f"{E_ASA:g}, {NU_ASA:g}",
        "*DENSITY", f"{RHO_ASA:.6e}",
        "*SOLID SECTION, ELSET=ASA, MATERIAL=ASA",
        "*BOUNDARY", "IMAS, 1, 3",
        "*STEP", "*FREQUENCY, STORAGE=NO", f"{modos}",
        # sem pedir o campo, o .frd sai so com a malha e nao ha o que
        # desenhar: as frequencias vao para o .dat, as FORMAS nao.
        "*NODE FILE", "U",
        "*END STEP", "",
    ]
    destino.write_text("\n".join(linhas))


def roda(destino):
    subprocess.run([str(CCX), "-i", str(destino.with_suffix(""))],
                   capture_output=True, text=True, cwd=destino.parent)
    dat = destino.with_suffix(".dat")
    if not dat.exists():
        raise SystemExit(f"ccx nao produziu {dat}")
    txt = dat.read_text().splitlines()
    f, lendo = [], False
    for ln in txt:
        if "E I G E N V A L U E" in ln:
            lendo = True; continue
        if "P A R T I C I P A T I O N" in ln:
            break
        if lendo:
            c = ln.split()
            if len(c) >= 4 and c[0].isdigit():
                f.append(float(c[3]))
    # Massa modal efetiva: e ela que diz QUAL modo e o do caminho. O primeiro
    # autovalor costuma ser um modo local de parede, que nao move o sensor.
    ef, lendo = {}, False
    for ln in txt:
        if "E F F E C T I V E   M O D A L" in ln:
            lendo = True; continue
        if "T O T A L   E F F E C T I V E" in ln:
            break
        if lendo:
            c = ln.split()
            if len(c) >= 4 and c[0].isdigit():
                ef[int(c[0])] = float(c[1]) + float(c[2])       # X + Y
    lateral = max(ef, key=ef.get) if ef else None
    return f, lateral, (ef.get(lateral, 0.0) * 1e6 if lateral else 0.0)


print("modal do caminho de montagem — ASA macico, junta do spigot colada")
print(f"E = {E_ASA:.0f} MPa, nu = {NU_ASA}, rho = {RHO_ASA * 1e12:.0f} kg/m3")
print("o modo relatado e o de MAIOR massa modal efetiva lateral (X+Y): e o que")
print("move o sensor. O primeiro autovalor costuma ser modo local de parede.\n")

for v, cfg in CARGA.items():
    saida = AQUI / "fem" / v
    step = saida / "caminho.step"
    if not step.exists():
        raise SystemExit(f"falta {step} — rode hardware/fem_caminho.py no freecadcmd")
    inp = saida / "caminho.inp"
    nn, ne = malha(step, inp)
    nos = le_nos(inp)
    r = MAG_R / math.sqrt(2)
    centros = [(sx * r, sy * r) for sx in (-1, 1) for sy in (-1, 1)]
    fixos = sorted(n for n, (x, y, z) in nos.items()
                   if z <= MAG_P + 0.05
                   and any(math.hypot(x - cx, y - cy) <= MAG_D / 2 + 0.05
                           for cx, cy in centros))
    zf = BASE_ALT + FUNDO
    vx, vy = cfg["vao"]
    piso = sorted(n for n, (x, y, z) in nos.items()
                  if abs(z - zf) < 0.05 and abs(x) < vx / 2 and abs(y) < vy / 2)
    ztopo = max(z for _x, _y, z in nos.values())
    topo = sorted(n for n, (_x, _y, z) in nos.items() if abs(z - ztopo) < 0.05)
    if not (fixos and piso and topo):
        raise SystemExit(f"{v}: conjunto vazio "
                         f"(imas {len(fixos)}, piso {len(piso)}, topo {len(topo)})")
    print(f"{v}: malha {nn} nos / {ne} C3D10; {len(fixos)} nos nos bolsos de ima, "
          f"{len(piso)} no piso da cavidade (z={zf:.0f}), "
          f"{len(topo)} na borda de cima (z={ztopo:.0f})")
    carga_g = cfg["placa"] + cfg["bateria"]
    for onde, ns in (("piso", piso), ("topo", topo)):
        d = saida / f"montagem_{onde}.inp"
        escreve(inp, d, fixos,
                [("TAMPA", topo, cfg["tampa"] * 1e-6),
                 ("CARGA", ns, carga_g * 1e-6)])
        f, modo, mef = roda(d)
        if modo is None:
            raise SystemExit(f"{v}/{onde}: sem massa modal efetiva no .dat")
        fl = f[modo - 1]
        marca = "DENTRO da banda ISO" if fl <= BANDA[1] else "acima da banda ISO"
        print(f"   carga no {onde:<5} ({carga_g:.1f} g placa+bateria, "
              f"{cfg['tampa']:.1f} g de tampa no topo): "
              f"modo {modo} = {fl:.0f} Hz, {mef:.0f} g efetivos — {marca}")
        print(f"      autovalores: " + ", ".join(f"{x:.0f}" for x in f[:MODOS]))
    print(f"   {cfg['nota']}\n")

print("referencia: analise-involucro.ipynb estimou 560 Hz para a v1 tratando o")
print("corpo como viga engastada de 78 mm com a massa TOTAL (118 g) na ponta.")
sys.stdout.flush()
