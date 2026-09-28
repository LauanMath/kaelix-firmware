"""Constantes e funções do modelo térmico do invólucro, sem execução.

Extraídas de termica.py para que outro cenário — a carga da bateria, com
fonte de calor interna (termica_carga.py) — rode sobre a MESMA malha, o mesmo
material e a mesma troca externa, em vez de uma cópia que divergiria.
"""
import math
import pathlib
import subprocess
import sys

import numpy as np

AQUI = pathlib.Path(__file__).resolve().parent
CCX = pathlib.Path("/Applications/FreeCAD.app/Contents/Resources/bin/ccx")

T_MOTOR = 90.0            # carcaça do motor, °C — a pergunta em discussão
T_AMB = 30.0              # ambiente industrial, mesma hipótese do notebook
EPS = 0.90                # plástico fosco
SIGMA = 5.67e-8           # W/(m²·K⁴)

K_ASA = 0.17              # W/(m·K) = mW/(mm·K)
CP_ASA = 1.3e9            # mJ/(t·K)  = 1300 J/(kg·K)
RHO_ASA = 1.07e-9         # t/mm³

BASE_ALT, FUNDO = 9.0, 8.0
MAG_R, MAG_D, MAG_P = 20.0, 10.0, 3.2
VAO = {"v1": (43.0, 43.0, 54.0), "v2": (62.0, 52.0, 30.0)}

TAM_MALHA = 3.0
FACES_TET = ((0, 1, 2), (0, 1, 3), (1, 2, 3), (0, 2, 3))   # = S1..S4 do C3D10


def h_externo(dt):
    """Convecção natural mais radiação LINEARIZADA, em W/(m²·K).

    Linearizar a radiação vale porque o salto sobre o ambiente é de poucos
    kelvin: h_rad = 4·eps·sigma·T³ erra menos de 1% nessa faixa, e evita a
    não-linearidade no solver. Declarado, não escondido.
    """
    hc = 2.0 if dt <= 0 else 1.42 * (dt / 0.05) ** 0.25
    tm = T_AMB + dt / 2 + 273.15
    return hc + 4 * EPS * SIGMA * tm ** 3


def malha(step, inp):
    import gmsh
    gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", 0)
    gmsh.model.add("inv")
    gmsh.model.occ.importShapes(str(step))
    gmsh.model.occ.healShapes(makeSolids=True, sewFaces=True,
                              fixDegenerated=True, fixSmallEdges=True,
                              fixSmallFaces=True)
    gmsh.model.occ.removeAllDuplicates()
    gmsh.model.occ.synchronize()
    gmsh.model.addPhysicalGroup(3, [t for _d, t in gmsh.model.getEntities(3)],
                                name="ASA")
    gmsh.option.setNumber("Mesh.MeshSizeFromCurvature", 8)
    gmsh.option.setNumber("Mesh.MeshSizeMax", TAM_MALHA)
    gmsh.option.setNumber("Mesh.MeshSizeMin", 1.0)
    gmsh.option.setNumber("Mesh.SecondOrderLinear", 1)
    gmsh.option.setNumber("Mesh.ElementOrder", 2)
    gmsh.option.setNumber("Mesh.Optimize", 1)
    gmsh.model.mesh.generate(3)
    gmsh.write(str(inp))
    nn = len(gmsh.model.mesh.getNodes()[0])
    gmsh.finalize()
    return nn


def le_inp(caminho):
    nos, elems, bloco = {}, [], None
    for ln in caminho.read_text().splitlines():
        u = ln.upper()
        if ln.startswith("*"):
            bloco = ("no" if u.startswith("*NODE") else
                     "el" if u.startswith("*ELEMENT") and "C3D10" in u else None)
            continue
        if bloco is None or not ln.strip():
            continue
        c = [x.strip() for x in ln.split(",") if x.strip()]
        if bloco == "no" and len(c) >= 4:
            nos[int(c[0])] = (float(c[1]), float(c[2]), float(c[3]))
        elif bloco == "el" and len(c) >= 11:
            elems.append((int(c[0]), [int(x) for x in c[1:11]]))
    return nos, elems


def contorno(nos, elems):
    """Faces de fronteira: (elemento, face S1..S4, centroide)."""
    conta, dono = {}, {}
    for eid, vs in elems:
        for k, f in enumerate(FACES_TET, start=1):
            tri = tuple(sorted(vs[i] for i in f))
            conta[tri] = conta.get(tri, 0) + 1
            dono[tri] = (eid, k, [vs[i] for i in f])
    fora = []
    for tri, n in conta.items():
        if n != 1:
            continue
        eid, k, vv = dono[tri]
        c = np.mean([nos[v] for v in vv], axis=0)
        fora.append((eid, k, c))
    return fora


def classifica(faces, versao):
    """Separa as faces em ímã (entrada), cavidade (interna) e externa."""
    vx, vy, valt = VAO[versao]
    r = MAG_R / math.sqrt(2)
    centros = [(sx * r, sy * r) for sx in (-1, 1) for sy in (-1, 1)]
    z0, z1 = BASE_ALT + FUNDO, BASE_ALT + FUNDO + valt
    ima, cav, ext = [], [], []
    for eid, k, c in faces:
        if c[2] <= MAG_P + 0.2 and any(
                math.hypot(c[0] - a, c[1] - b) <= MAG_D / 2 + 0.2
                for a, b in centros):
            ima.append((eid, k))
        elif (abs(c[0]) <= vx / 2 + 0.2 and abs(c[1]) <= vy / 2 + 0.2
              and z0 - 0.2 <= c[2] <= z1 + 0.2):
            cav.append((eid, k))
        else:
            ext.append((eid, k))
    return ima, cav, ext


def escreve(base_inp, destino, nos_ima, ext, h_ext, n_max, transiente=None,
            t_motor=None, fonte=(), film_extra=()):
    """Um passo de condução. `transiente` = (passo, total) em s, ou None.

    Os três últimos argumentos existem para termica_carga.py e, nos valores
    padrão, não mudam nada do que termica.py escreve:
      t_motor     temperatura imposta nos bolsos de ímã; None = T_MOTOR.
                  False = sem motor: os bolsos trocam calor com o ar.
      fonte       [(elemento, face, q)] fluxo entrando pela face, mW/mm².
      film_extra  [(elemento, face)] faces a mais com troca externa.
    """
    L = [base_inp.read_text().rstrip()]
    L += [f"*NSET, NSET=NALL, GENERATE", f"1, {n_max}, 1",
          "*NSET, NSET=IMA"]
    ns = sorted(nos_ima)
    for k in range(0, len(ns), 8):
        L.append(", ".join(str(v) for v in ns[k:k + 8]) + ",")
    L += ["*MATERIAL, NAME=ASA",
          "*CONDUCTIVITY", f"{K_ASA:g}",
          "*SPECIFIC HEAT", f"{CP_ASA:g}",
          "*DENSITY", f"{RHO_ASA:g}",
          "*SOLID SECTION, ELSET=ASA, MATERIAL=ASA",
          "*INITIAL CONDITIONS, TYPE=TEMPERATURE", f"NALL, {T_AMB:g}"]
    if transiente:
        dt, ttot = transiente
        L += ["*STEP, INC=1000000", "*HEAT TRANSFER", f"{dt:g}, {ttot:g}"]
    else:
        L += ["*STEP", "*HEAT TRANSFER, STEADY STATE", "1.0, 1.0"]
    # Entrada de calor: a face dos bolsos de ímã presa na temperatura da
    # carcaça. É o limite OTIMISTA do acoplamento — o ímã real tem cola e uma
    # resistência de contato que este modelo ignora, e que só reduziria o
    # fluxo.
    if t_motor is not False:
        L += ["*BOUNDARY", f"IMA, 11, 11, {T_MOTOR if t_motor is None else t_motor:g}"]
    # A cavidade fica ADIABÁTICA: sem fonte interna, a condução pelo ar
    # (k = 0,026, caminho de dezenas de mm) passa de 1000 K/W contra os
    # poucos K/W da parede. Hipótese declarada.
    L.append("*FILM")
    for eid, k in list(ext) + list(film_extra):
        L.append(f"{eid}, F{k}, {T_AMB:g}, {h_ext:g}")
    if fonte:
        L.append("*DFLUX")
        for eid, k, q in fonte:
            L.append(f"{eid}, S{k}, {q:.6g}")
    L += ["*NODE FILE, FREQUENCYF=1", "NT", "*END STEP", ""]
    destino.write_text("\n".join(L))


def roda(destino):
    r = subprocess.run([str(CCX), "-i", str(destino.with_suffix(""))],
                       capture_output=True, text=True, cwd=destino.parent)
    frd = destino.with_suffix(".frd")
    if not frd.exists():
        print(r.stdout[-1500:]); print(r.stderr[-800:])
        raise SystemExit(f"ccx nao produziu {frd}")
    return frd


def le_temperaturas(frd):
    """Todos os passos de NDTEMP do .frd: lista de (tempo, {no: T})."""
    passos, atual, bloco, tempo = [], None, None, 0.0
    for ln in frd.read_text().splitlines():
        if "100CL" in ln:
            try:
                tempo = float(ln.split()[2])
            except (IndexError, ValueError):
                tempo = float(len(passos) + 1)
            atual, bloco = {}, "espera"
            continue
        if bloco == "espera" and ln.strip().startswith("-4"):
            bloco = "temp" if "NDTEMP" in ln else None
            if bloco is None:
                atual = None
            continue
        if ln[:5].strip() == "-3":
            if atual:
                passos.append((tempo, atual))
            atual, bloco = None, None
            continue
        if bloco == "temp" and ln[:5].strip() == "-1":
            atual[int(ln[3:13])] = float(ln[13:25])
    if atual:
        passos.append((tempo, atual))
    return passos


# Massa térmica do que está DENTRO e não toca em nada. A placa e a célula se
# acoplam à parede só por radiação e convecção interna, então têm constante de
# tempo própria, em série com a do invólucro. `area` é a área de troca desse
# conjunto com a parede.
DENTRO = {"v1": dict(m_placa=9.4e-3, m_bat=10e-3, area=0.008),
          "v2": dict(m_placa=13.8e-3, m_bat=35e-3, area=0.011)}
CP_FR4, CP_LIPO = 1100.0, 1000.0    # J/(kg·K)
