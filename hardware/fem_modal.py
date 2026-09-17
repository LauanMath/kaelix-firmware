"""Análise modal da placa, direto do .kicad_pcb gerado.

Por que existe: `experiments/notebooks/analise-involucro.ipynb` confirmou uma
hipótese — o caminho motor -> ímãs -> base ASA -> corpo ASA -> PCB tem
frequência de montagem em torno de 560 Hz, dentro dos 10-1000 Hz que a
ISO 10816-3 exige. Aquela análise tratou o caminho como mola em série e a
PLACA como massa rígida.

Este arquivo testa a parte que ficou de fora: a placa também é uma mola. Um
acelerômetro parafusado no ponto mais flexível de uma chapa de 1,6 mm mede a
flexão da própria chapa. E a pergunta ficou urgente porque a v2 tem 61 x 51 mm
contra 42 x 42 da v1 — a frequência de uma placa cai com o quadrado do vão
livre, então a decisão de aumentar a placa precisa de um número, não de um
palpite.

O contorno e os furos NÃO são redigitados aqui: saem do Edge.Cuts e dos
footprints MountingHole do próprio .kicad_pcb. Se a placa mudar, a simulação
muda junto.

    KAELIX_PCB=v2 uv run --no-project --with gmsh python hardware/fem_modal.py
"""
import math
import os
import pathlib
import subprocess
import sys

AQUI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
from sexpr import parse, find, find1  # noqa: E402

VERSAO = os.environ.get("KAELIX_PCB", "v1")
PCB = AQUI / "pcb" / VERSAO / "kaelix.kicad_pcb"
SAIDA = AQUI / "fem" / VERSAO
CCX = pathlib.Path("/Applications/FreeCAD.app/Contents/Resources/bin/ccx")

# --- material -------------------------------------------------------
# Unidades de CalculiX: mm, N, tonelada, s  ->  E em MPa, rho em t/mm³,
# frequência em Hz.
#
# FR-4 é ortotrópico e a rigidez no plano depende da trama; 24 GPa é o valor
# usual para tecido 7628 em flexão no plano. Isotrópico aqui é simplificação
# declarada: erra o modo torcional mais que o de flexão.
E_FR4 = 24000.0          # MPa
NU_FR4 = 0.136
RHO_FR4 = 1.85e-9        # t/mm³ (1850 kg/m³)
ESPESSURA = 1.6          # mm

# Massa dos componentes, somada como densidade equivalente na chapa.
# Espalhar massa que na verdade está concentrada nos dois módulos SUBESTIMA a
# queda de frequência quando a massa fica no meio do vão e SUPERESTIMA quando
# fica perto do apoio. É limitação declarada, não resultado.
MASSA_COMPONENTES = 5.1  # g — WROOM-1U 2,4 + Ra-02 1,5 + J2 0,6 + resto 0,6

MODOS = 8
TAM_MALHA = 2.0          # mm
FURO_D = 2.2             # broca do MountingHole M2


def v(tok):
    """Valor de um token do parser: ('sym'|'str', texto)."""
    return tok[1] if isinstance(tok, tuple) else str(tok)


def xy(form):
    return (float(v(form[1])), float(v(form[2])))


def geometria():
    """Contorno (segmentos e arcos) e centros dos furos, do .kicad_pcb."""
    doc = parse(PCB.read_text())[0]
    linhas, arcos = [], []
    for e in find(doc, "gr_line"):
        if v(find1(e, "layer")[1]) != "Edge.Cuts":
            continue
        linhas.append((xy(find1(e, "start")), xy(find1(e, "end"))))
    for e in find(doc, "gr_arc"):
        if v(find1(e, "layer")[1]) != "Edge.Cuts":
            continue
        arcos.append((xy(find1(e, "start")), xy(find1(e, "mid")),
                      xy(find1(e, "end"))))
    furos = []
    for f in find(doc, "footprint"):
        if "MountingHole" not in v(f[1]):
            continue
        furos.append(xy(find1(f, "at")))
    if not linhas or not arcos or not furos:
        raise SystemExit(f"contorno incompleto em {PCB}")
    return linhas, arcos, furos


def centro_do_arco(p1, pm, p2):
    """Centro do círculo por três pontos."""
    (x1, y1), (x2, y2), (x3, y3) = p1, pm, p2
    d = 2 * (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2))
    if abs(d) < 1e-9:
        raise SystemExit("três pontos colineares num gr_arc")
    ux = ((x1**2 + y1**2) * (y2 - y3) + (x2**2 + y2**2) * (y3 - y1)
          + (x3**2 + y3**2) * (y1 - y2)) / d
    uy = ((x1**2 + y1**2) * (x3 - x2) + (x2**2 + y2**2) * (x1 - x3)
          + (x3**2 + y3**2) * (x2 - x1)) / d
    return (ux, uy)


def primitivas(linhas, arcos, furos):
    """Retângulo + recortes, derivados do contorno lido.

    Reconstruir arco por arco a partir das coordenadas do arquivo falha: o
    KiCad grava 4 casas, e start/mid/end deixam de estar no mesmo círculo por
    alguns micrometros — o OCC recusa. Aqui os arcos servem para MEDIR centro
    e raio dos recortes, e a peça é montada com primitivas exatas. A área
    conferida contra o contorno lido é o que garante que não se inventou nada.
    """
    xs = [p[0] for s in linhas for p in s]
    ys = [p[1] for s in linhas for p in s]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    hx, hy = max(xs) - cx, max(ys) - cy
    recortes = []
    for p1, pm, p2 in arcos:
        c = centro_do_arco(p1, pm, p2)
        r = math.hypot(p1[0] - c[0], p1[1] - c[1])
        recortes.append((c[0], c[1], r))
    return (cx, cy, hx, hy), recortes, furos


def malha(linhas, arcos, furos, caminho_inp):
    import gmsh
    (cx, cy, hx, hy), recortes, furos = primitivas(linhas, arcos, furos)
    gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", 0)
    gmsh.model.add("placa")
    occ = gmsh.model.occ

    corpo = occ.addBox(cx - hx, cy - hy, 0.0, 2 * hx, 2 * hy, ESPESSURA)
    corte = []
    for x, y, r in recortes:
        corte.append((3, occ.addCylinder(x, y, -1.0, 0, 0, ESPESSURA + 2, r)))
    for x, y in furos:
        corte.append((3, occ.addCylinder(x, y, -1.0, 0, 0, ESPESSURA + 2,
                                         FURO_D / 2)))
    placa, _ = occ.cut([(3, corpo)], corte)
    occ.synchronize()
    vol = [t for d, t in placa if d == 3]
    gmsh.model.addPhysicalGroup(3, vol, name="PLACA")

    gmsh.option.setNumber("Mesh.MeshSizeMax", TAM_MALHA)
    gmsh.option.setNumber("Mesh.MeshSizeMin", TAM_MALHA / 4)
    gmsh.option.setNumber("Mesh.ElementOrder", 2)
    gmsh.option.setNumber("Mesh.SecondOrderIncomplete", 0)
    gmsh.model.mesh.generate(3)
    vol_real = sum(occ.getMass(3, t) for d, t in placa if d == 3)
    gmsh.write(str(caminho_inp))
    nt = gmsh.model.mesh.getNodes()[0]
    _, tags, _ = gmsh.model.mesh.getElements(3)
    ne = sum(len(t) for t in tags)
    gmsh.finalize()
    return len(nt), ne, vol_real, (cx, cy, hx, hy)


def _ordena(curvas, linhas, arcos):
    """gmsh exige o laço na ordem; o Edge.Cuts do KiCad já sai em sequência."""
    return curvas


def area(linhas, arcos):
    """Área do contorno pelo teorema de Green, arcos amostrados."""
    pontos = []
    for a, b in linhas:
        pontos += [a, b]
    for p1, pm, p2 in arcos:
        c = centro_do_arco(p1, pm, p2)
        r = math.hypot(p1[0] - c[0], p1[1] - c[1])
        a1 = math.atan2(p1[1] - c[1], p1[0] - c[0])
        a2 = math.atan2(p2[1] - c[1], p2[0] - c[0])
        am = math.atan2(pm[1] - c[1], pm[0] - c[0])
        varre = (a2 - a1) % (2 * math.pi)
        if not (0 < (am - a1) % (2 * math.pi) < varre):
            varre -= 2 * math.pi
        pontos += [(c[0] + r * math.cos(a1 + varre * k / 24),
                    c[1] + r * math.sin(a1 + varre * k / 24)) for k in range(25)]
    cx = sum(p[0] for p in pontos) / len(pontos)
    cy = sum(p[1] for p in pontos) / len(pontos)
    pontos.sort(key=lambda p: math.atan2(p[1] - cy, p[0] - cx))
    s = 0.0
    for i in range(len(pontos)):
        x1, y1 = pontos[i]
        x2, y2 = pontos[(i + 1) % len(pontos)]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2


print(f"placa: {VERSAO}")
SAIDA.mkdir(parents=True, exist_ok=True)
_lin, _arc, _fur = geometria()
_a = area(_lin, _arc)
print(f"contorno lido do .kicad_pcb: {len(_lin)} segmentos, {len(_arc)} arcos, "
      f"{len(_fur)} furos M2 — area {_a:.0f} mm2")

_inp = SAIDA / "malha.inp"
_nn, _ne, _vol, _ret = malha(_lin, _arc, _fur, _inp)
_a_solido = _vol / ESPESSURA
print(f"solido: retangulo {2 * _ret[2]:.1f} x {2 * _ret[3]:.1f} x {ESPESSURA} mm, "
      f"area {_a_solido:.0f} mm2 (contorno lido: {_a:.0f})")
_esperado = _a - len(_fur) * math.pi * (FURO_D / 2) ** 2
if abs(_a_solido - _esperado) > 0.5:
    raise SystemExit(f"solido {_a_solido:.1f} mm2 diverge do contorno lido "
                     f"menos os furos ({_esperado:.1f} mm2)")
print(f"malha: {_nn} nos, {_ne} elementos C3D10")


# =====================================================================
# Condições de contorno
# =====================================================================
# O projeto é ambíguo sobre como a placa se prende, e a ambiguidade muda a
# resposta por um fator grande. `gen_pcb.py` diz, no bloco dos furos M2:
# "O invólucro não prende a placa por parafuso [...] a placa assenta pelo aro.
# Os furos existem por outro motivo: dar apoio ao acelerômetro." As duas
# frases descrevem apoios diferentes, e não há desenho que decida.
#
# Então são simulados os dois, como limites:
#
#   FUROS  engaste nos três cilindros M2 — o que os furos dariam se fossem
#          usados com espaçador e parafuso. Vão livre grande, limite INFERIOR.
#   ARO    face de baixo do perímetro com uz = 0 — "assenta pelo aro". É
#          apoio simples de verdade: bloqueia o afundamento, não o giro da
#          borda, e não restringe o plano. Limite SUPERIOR.
#
# Travar os três graus de liberdade numa faixa de 1 mm da face de baixo, como
# se fez no primeiro corte, não é apoio simples: é engaste, e devolvia 4218 Hz
# onde o apoio simples devolve bem menos. Com uz apenas, sobram três modos de
# corpo rígido em ~0 Hz, descartados na leitura.
#
# A montagem real fica entre os dois. Se o limite superior já cair na banda,
# não há discussão a fazer.
def le_nos(caminho):
    nos, dentro = {}, False
    for ln in caminho.read_text().splitlines():
        if ln.startswith("*"):
            dentro = ln.upper().startswith("*NODE")
            continue
        if not dentro or not ln.strip():
            continue
        c = ln.split(",")
        if len(c) < 4:
            continue
        nos[int(c[0])] = (float(c[1]), float(c[2]), float(c[3]))
    return nos


def conjunto_furos(nos, furos):
    r = FURO_D / 2 + 0.02
    return sorted(n for n, (x, y, _z) in nos.items()
                  if any(math.hypot(x - fx, y - fy) <= r for fx, fy in furos))


def conjunto_aro(nos, ret, recortes, faixa=1.0):
    cx, cy, hx, hy = ret
    fora = []
    for n, (x, y, z) in nos.items():
        if z > 0.01:                       # só a face de baixo assenta
            continue
        d = min(hx - abs(x - cx), hy - abs(y - cy))
        for bx, by, r in recortes:
            d = min(d, math.hypot(x - bx, y - by) - r)
        if d <= faixa:
            fora.append(n)
    return sorted(fora)


def escreve_inp(base, destino, nsets, rho, modos=MODOS):
    """`nsets` é nome -> (nós, (gdl inicial, gdl final))."""
    corpo = base.read_text().rstrip()
    linhas = [corpo]
    for nome, (ns, _gdl) in nsets.items():
        linhas.append(f"*NSET, NSET={nome}")
        for k in range(0, len(ns), 8):
            linhas.append(", ".join(str(v) for v in ns[k:k + 8]) + ",")
    linhas += [
        "*MATERIAL, NAME=FR4",
        "*ELASTIC", f"{E_FR4:g}, {NU_FR4:g}",
        "*DENSITY", f"{rho:.6e}",
        "*SOLID SECTION, ELSET=PLACA, MATERIAL=FR4",
        "*BOUNDARY",
    ]
    for nome, (_ns, gdl) in nsets.items():
        linhas.append(f"{nome}, {gdl[0]}, {gdl[1]}")
    linhas += ["*STEP", "*FREQUENCY, STORAGE=NO", f"{modos}",
        # sem pedir o campo, o .frd sai so com a malha e nao ha o que
        # desenhar: as frequencias vao para o .dat, as FORMAS nao.
        "*NODE FILE", "U",
        "*END STEP", ""]
    destino.write_text("\n".join(linhas))


def roda(destino):
    r = subprocess.run([str(CCX), "-i", str(destino.with_suffix(""))],
                       capture_output=True, text=True, cwd=destino.parent)
    dat = destino.with_suffix(".dat")
    if not dat.exists():
        print(r.stdout[-2000:]); print(r.stderr[-1000:])
        raise SystemExit("ccx nao produziu .dat")
    freq, lendo = [], False
    for ln in dat.read_text().splitlines():
        if "E I G E N V A L U E" in ln:
            lendo = True; continue
        if not lendo:
            continue
        c = ln.split()
        if len(c) >= 4 and c[0].isdigit():
            freq.append(float(c[3]))
    return freq


_nos = le_nos(_inp)
_, _recortes, _ = primitivas(_lin, _arc, _fur)
_set_furos = conjunto_furos(_nos, _fur)
_set_aro = conjunto_aro(_nos, _ret, _recortes)
print(f"apoios: {len(_set_furos)} nos nos tres furos M2, "
      f"{len(_set_aro)} nos na aresta inferior do contorno")
if not _set_furos or not _set_aro:
    raise SystemExit("conjunto de apoio vazio")

# Massa: a chapa nua e a chapa povoada. f ~ 1/sqrt(m), entao a diferenca nao
# e detalhe — e a componente que mais desloca o resultado depois do apoio.
_m_nua = _vol * RHO_FR4 * 1e6            # g  (t/mm3 * mm3 -> t -> g)
_rho_pov = RHO_FR4 * (_m_nua + MASSA_COMPONENTES) / _m_nua
print(f"massa: chapa nua {_m_nua:.2f} g, com componentes "
      f"{_m_nua + MASSA_COMPONENTES:.2f} g "
      f"(rho equivalente {_rho_pov / RHO_FR4:.2f}x)")

BANDA = (10.0, 1000.0)                   # ISO 10816-3
print()
print(f"{'apoio':<8} {'massa':<10} " + " ".join(f"f{k+1:<7}" for k in range(5)))
print("-" * 62)
_res = {}
for _nome, _ns in (("FUROS", {"FUROS": (_set_furos, (1, 3))}),
                   ("ARO", {"ARO": (_set_aro, (3, 3))})):
    for _rot, _rho in (("nua", RHO_FR4), ("povoada", _rho_pov)):
        _d = SAIDA / f"modal_{_nome.lower()}_{_rot}.inp"
        escreve_inp(_inp, _d, _ns, _rho)
        _f = [x for x in roda(_d) if x > 1.0][:5]
        _res[(_nome, _rot)] = _f
        print(f"{_nome:<8} {_rot:<10} " + " ".join(f"{x:<8.0f}" for x in _f))

print()
for (_nome, _rot), _f in _res.items():
    if not _f:
        continue
    _f1 = _f[0]
    _sit = ("DENTRO da banda ISO 10816-3 (10-1000 Hz)" if _f1 <= BANDA[1]
            else "acima da banda")
    print(f"{_nome}/{_rot}: 1o modo {_f1:.0f} Hz — {_sit}")
sys.stdout.flush()
