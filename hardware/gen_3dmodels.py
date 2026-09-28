"""Confere os modelos 3D importados contra as cotas do footprint.

A biblioteca do KiCad não traz corpo 3D para três footprints deste projeto —
nem a instalação local nem o repositório oficial `kicad-packages3D` têm
ESP32-S3-WROOM-1U, Ai-Thinker Ra-02 ou JST S2B-PH-SM4-TB. O `.step` exportado
saía sem os três componentes mais altos, e um modelo mecânico que omite as
peças altas é pior que nenhum: ele parece completo.

Os três vieram de repositórios públicos com licença permissiva e estão em
`3dmodels/origem/`, sem edição — a procedência, a licença e o SHA256 de cada
um ficam em `3dmodels/origem/ORIGEM.md`.

Por que conferir, e não confiar
-------------------------------
Modelo de terceiro chega em qualquer orientação. Dos três baixados, DOIS
vinham errados para este footprint:

    WROOM-1U   deitado (Y é a espessura, Z é o comprimento)
    Ra-02      girado 90 graus e com a origem no canto, não no centro

Um modelo com eixo trocado é pior que um ausente: ele aparece, parece certo
de longe e mente sobre a altura — que é justamente a cota que se vai buscar
num modelo mecânico. A correção é feita pelo (rotate)/(offset) do próprio
KiCad, declarada em MODELOS_3D no gen_pcb.py, e os valores foram MEDIDOS na
placa montada, não deduzidos: a convenção de sinal do KiCad não é óbvia e
errar o sinal enfia o módulo para dentro do laminado sem aviso nenhum.

Este script confere o que está em disco. Se um modelo sumir ou trocar de
tamanho, a compilação para aqui, e não no dia em que alguém abrir o STEP.

Rodar:  /Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd \\
            hardware/gen_3dmodels.py
"""

import pathlib
import sys

import Part

# O console do freecadcmd sai em ASCII; sem isto o primeiro acento aborta o
# script no meio.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

AQUI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
from sexpr import parse, find, find1, head  # noqa: E402

FPLIB = pathlib.Path("/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints")
ORIGEM = AQUI / "3dmodels" / "origem"

# arquivo -> (footprint que ele veste, giro aplicado pelo KiCad, procedência)
#
# `troca_xy` diz que o modelo está girado 90 graus em relação ao footprint, e
# portanto as cotas conferidas trocam de eixo.
IMPORTADOS = {
    "wroom1u.step": ("RF_Module:ESP32-S3-WROOM-1U", "eixo Z<->Y", False,
                     "Lambosaurus/KicadLib, MIT"),
    "ra02.step": ("RF_Module:Ai-Thinker-Ra-01-LoRa", "90 graus em Z", True,
                  "mithro/esp32-to-433mhz, Apache-2.0"),
    "jst.step": ("Connector_JST:JST_PH_S2B-PH-SM4-TB_1x02-1MP_P2.00mm_Horizontal",
                 "nenhum", False, "arturo182/kicad-modules, MIT"),
}

TOLERANCIA = 1.5    # mm; o modelo traz detalhe que o contorno em F.Fab simplifica


def contorno(libfp):
    """Retângulo do corpo em F.Fab, no próprio footprint do projeto."""
    d, n = libfp.split(":")
    doc = parse((FPLIB / f"{d}.pretty" / f"{n}.kicad_mod").read_text())[0]
    xs, ys = [], []
    for e in doc[1:]:
        if not (isinstance(e, list) and head(e) in
                ("fp_line", "fp_rect", "fp_poly", "fp_circle")):
            continue
        lay = find1(e, "layer")
        if not (lay and len(lay) > 1 and lay[1][1] == "F.Fab"):
            continue
        for nome in ("start", "end", "center", "mid"):
            for v in find(e, nome):
                xs.append(float(v[1][1])); ys.append(float(v[2][1]))
        pts = find1(e, "pts")
        if pts:
            for v in find(pts, "xy"):
                xs.append(float(v[1][1])); ys.append(float(v[2][1]))
    if not xs:
        raise SystemExit(f"{libfp}: sem contorno em F.Fab")
    return max(xs) - min(xs), max(ys) - min(ys)


falhas = []
for arquivo, (libfp, giro, troca_xy, fonte) in IMPORTADOS.items():
    caminho = ORIGEM / arquivo
    if not caminho.exists():
        falhas.append(f"{arquivo}: AUSENTE em 3dmodels/origem/")
        continue
    forma = Part.Shape()
    try:
        forma.read(str(caminho))
    except Exception as exc:
        falhas.append(f"{arquivo}: nao abre ({exc})")
        continue
    if forma.isNull() or not forma.Solids:
        falhas.append(f"{arquivo}: STEP sem solido")
        continue

    b = forma.BoundBox
    fx, fy = contorno(libfp)
    # As duas maiores dimensões do modelo são as do plano da peça; a menor é a
    # altura. Comparar assim funciona para qualquer orientação de origem.
    med = sorted([b.XLength, b.YLength, b.ZLength], reverse=True)[:2]
    esp = sorted([fx, fy], reverse=True)
    ok = all(abs(m - e) <= TOLERANCIA for m, e in zip(med, esp))
    if not ok:
        falhas.append(f"{arquivo}: {med[0]:.2f} x {med[1]:.2f} mm contra "
                      f"{esp[0]:.2f} x {esp[1]:.2f} do footprint")
    print(f"{arquivo:14s} {b.XLength:6.2f} x {b.YLength:6.2f} x {b.ZLength:5.2f} mm  "
          f"{len(forma.Solids):3d} solidos  {'ok' if ok else 'DIVERGE'}")
    print(f"{'':14s} veste {libfp}")
    print(f"{'':14s} giro aplicado pelo KiCad: {giro}   fonte: {fonte}")

if falhas:
    print("MODELOS COM PROBLEMA:")
    for f in falhas:
        print(f"   {f}")
    sys.stdout.flush()
    raise SystemExit(1)
