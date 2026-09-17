"""Desenha as formas modais dos .frd do CalculiX.

Nao ha visualizador headless confiavel para .frd nesta maquina, e o resultado
que interessa e simples: a superficie do solido, deslocada pela forma modal e
colorida pelo modulo do deslocamento. Isso o matplotlib faz.

A escala do deslocamento e ARBITRARIA — autovetor nao tem amplitude fisica.
Cada figura declara a sua.

    uv run --no-project --with numpy --with matplotlib python hardware/fem_figuras.py
"""
import collections
import pathlib
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                       # noqa: E402
from mpl_toolkits.mplot3d.art3d import Poly3DCollection  # noqa: E402

AQUI = pathlib.Path(__file__).resolve().parent
SAIDA = AQUI / "fem" / "figuras"

# Faces de um C3D10 pelos vertices de canto (a casca so precisa dos cantos;
# os nos de meio-lado nao mudam a topologia da superficie).
FACES_TET = ((0, 1, 2), (0, 1, 3), (1, 2, 3), (0, 2, 3))


def le_frd(caminho):
    """Nós, elementos e um campo de deslocamento por modo."""
    nos, elems, modos = {}, [], []
    bloco = None
    atual = None
    pendente = None
    for ln in caminho.read_text().splitlines():
        m = ln[:5].strip()
        if ln.lstrip().startswith("2C"):
            bloco = "nos"; continue
        if ln.lstrip().startswith("3C"):
            bloco = "elem"; continue
        if "100CL" in ln:
            bloco = "disp"; atual = {}; modos.append(atual); continue
        if m == "-3":
            bloco = None; continue
        if bloco == "nos" and m == "-1":
            nos[int(ln[3:13])] = (float(ln[13:25]), float(ln[25:37]),
                                  float(ln[37:49]))
        elif bloco == "elem":
            if m == "-1":
                pendente = int(ln[3:13])
            elif m == "-2" and pendente is not None:
                vs = [int(ln[i:i + 10]) for i in range(3, len(ln.rstrip()), 10)]
                elems.append((pendente, vs)); pendente = None
        elif bloco == "disp" and m == "-1":
            atual[int(ln[3:13])] = (float(ln[13:25]), float(ln[25:37]),
                                    float(ln[37:49]))
    return nos, elems, [m for m in modos if m]


def casca(elems):
    """Triângulos da superfície: faces de tetraedro que aparecem uma só vez."""
    conta = collections.Counter()
    dono = {}
    for _eid, vs in elems:
        c = vs[:4]
        for f in FACES_TET:
            tri = tuple(c[i] for i in f)
            k = tuple(sorted(tri))
            conta[k] += 1
            dono[k] = tri
    return [dono[k] for k, n in conta.items() if n == 1]


def desenha(ax, nos, tris, desl, escala, titulo):
    ids = sorted(nos)
    idx = {n: i for i, n in enumerate(ids)}
    P = np.array([nos[n] for n in ids])
    U = np.array([desl.get(n, (0.0, 0.0, 0.0)) for n in ids])
    mag = np.linalg.norm(U, axis=1)
    if mag.max() > 0:
        U = U / mag.max()
        mag = mag / mag.max()
    span = float(np.ptp(P, axis=0).max())
    Q = P + U * escala * span
    T = np.array([[idx[a], idx[b], idx[c]] for a, b, c in tris])
    cor = mag[T].mean(axis=1)
    col = Poly3DCollection(Q[T], linewidths=0.0)
    col.set_array(cor)
    col.set_cmap("viridis")
    col.set_clim(0.0, 1.0)
    ax.add_collection3d(col)
    c = Q.mean(axis=0)
    r = float(np.abs(Q - c).max())
    ax.set_xlim(c[0] - r, c[0] + r)
    ax.set_ylim(c[1] - r, c[1] + r)
    ax.set_zlim(c[2] - r, c[2] + r)
    ax.set_box_aspect((1, 1, 1))
    ax.set_axis_off()
    ax.set_title(titulo, fontsize=9, pad=-2)
    return col


def modo_lateral(dat):
    """Modo de maior massa modal efetiva lateral — o que move o sensor.

    Escolher o modo a mao aqui daria figura bonita e errada: em varios casos o
    primeiro autovalor e modo local de parede. O criterio e o mesmo de
    fem_montagem.py, lido do mesmo .dat.
    """
    ef, lendo = {}, False
    for ln in pathlib.Path(dat).read_text().splitlines():
        if "E F F E C T I V E   M O D A L" in ln:
            lendo = True; continue
        if "T O T A L   E F F E C T I V E" in ln:
            break
        if lendo:
            c = ln.split()
            if len(c) >= 4 and c[0].isdigit():
                ef[int(c[0])] = float(c[1]) + float(c[2])
    return max(ef, key=ef.get) if ef else 1


def frequencias(dat):
    f, lendo = [], False
    for ln in pathlib.Path(dat).read_text().splitlines():
        if "E I G E N V A L U E" in ln:
            lendo = True; continue
        if "P A R T I C I P A T I O N" in ln:
            break
        if lendo:
            c = ln.split()
            if len(c) >= 4 and c[0].isdigit():
                f.append(float(c[3]))
    return f


CASOS = [
    ("placa v1 — 3 furos M2", "v1/modal_furos_povoada", 1,     18, (34, -58)),
    ("placa v2 — 3 furos M2", "v2/modal_furos_povoada", 1,     18, (34, -58)),
    ("caminho v1 — carga no topo",  "v1/montagem_topo", "auto", 10, (16, -62)),
    ("caminho v2 — carga no topo",  "v2/montagem_topo", "auto", 10, (16, -62)),
    ("caminho v1 — carga no piso",  "v1/montagem_piso", "auto", 10, (16, -62)),
    ("caminho v2 — carga no piso",  "v2/montagem_piso", "auto", 10, (16, -62)),
]

SAIDA.mkdir(parents=True, exist_ok=True)
# Eixos 3D reservam margem enorme por conta propria; posicionar a mao e o
# unico jeito de a peca ocupar o painel.
LARG, ALT = 0.435, 0.275
COL_X = (0.035, 0.475)
LIN_Y = (0.635, 0.335, 0.035)

fig = plt.figure(figsize=(10.5, 11.5))
fig.patch.set_facecolor("white")
col = None
for k, (rot, base, modo, escala, vista) in enumerate(CASOS, 1):
    frd = AQUI / "fem" / f"{base}.frd"
    dat = AQUI / "fem" / f"{base}.dat"
    if not frd.exists():
        raise SystemExit(f"falta {frd} — rode fem_modal.py / fem_montagem.py")
    if modo == "auto":
        modo = modo_lateral(dat)
    nos, elems, modos = le_frd(frd)
    if len(modos) < modo:
        raise SystemExit(f"{base}: {len(modos)} modo(s) no .frd, pedido o {modo}")
    f = frequencias(dat)
    tris = casca(elems)
    lin, colu = (k - 1) // 2, (k - 1) % 2
    ax = fig.add_axes([COL_X[colu], LIN_Y[lin], LARG, ALT], projection="3d")
    ax.view_init(elev=vista[0], azim=vista[1])
    col = desenha(ax, nos, tris, modos[modo - 1], escala / 100.0,
                  f"{rot}\nmodo {modo} = {f[modo - 1]:.0f} Hz"
                  f"   (deslocamento ampliado {escala}%)")
    print(f"{rot}: {len(nos)} nos, {len(tris)} triangulos, "
          f"modo {modo} = {f[modo - 1]:.0f} Hz")

cax = fig.add_axes([0.935, 0.32, 0.018, 0.36])
cb = fig.colorbar(col, cax=cax)
cb.set_label("deslocamento normalizado  |u| / |u|max", fontsize=8)
cb.ax.tick_params(labelsize=7)
fig.text(0.5, 0.975, "Formas modais — CalculiX 2.23 sobre malha gmsh C3D10",
         ha="center", fontsize=12)
fig.text(0.5, 0.950,
         "a amplitude do autovetor é arbitrária: o que informa é a distribuição. "
         "Nos casos do caminho, o modo mostrado é o de maior massa modal efetiva "
         "lateral.",
         ha="center", fontsize=8, color="#444444")
alvo = SAIDA / "modos.png"
fig.savefig(alvo, dpi=150, bbox_inches="tight", facecolor="white")
print(f"\ngerado: {alvo}")
sys.stdout.flush()


# =====================================================================
# Campo de temperatura, em corte
# =====================================================================
# Nota de método: as figuras de publicação do projeto (fig9 a fig11) são
# feitas em R, backend exclusivo. Este arquivo é outra coisa — renderização
# de resultado de FEM para inspeção de engenharia, irmã de `modos.png`, e
# fica no mesmo ferramental que ela.
def le_campo(caminho, nome="NDTEMP"):
    """Nós, elementos e um campo NODAL escalar do .frd."""
    nos, elems, campo = {}, [], {}
    bloco, pendente, lendo = None, None, False
    for ln in caminho.read_text().splitlines():
        m = ln[:5].strip()
        if ln.lstrip().startswith("2C"):
            bloco = "nos"; continue
        if ln.lstrip().startswith("3C"):
            bloco = "elem"; continue
        if "100CL" in ln:
            bloco, lendo = "res", False; continue
        if m == "-3":
            bloco = None; continue
        if bloco == "nos" and m == "-1":
            nos[int(ln[3:13])] = (float(ln[13:25]), float(ln[25:37]),
                                  float(ln[37:49]))
        elif bloco == "elem":
            if m == "-1":
                pendente = int(ln[3:13])
            elif m == "-2" and pendente is not None:
                elems.append((pendente,
                              [int(ln[i:i + 10]) for i in
                               range(3, len(ln.rstrip()), 10)]))
                pendente = None
        elif bloco == "res":
            if m == "-4":
                lendo = nome in ln
            elif m == "-1" and lendo:
                campo[int(ln[3:13])] = float(ln[13:25])
    return nos, elems, campo


def meia(nos, elems, eixo=1, lado=-1):
    """Só os elementos de um lado do plano central: dá o corte."""
    vals = [p[eixo] for p in nos.values()]
    meio = (min(vals) + max(vals)) / 2.0
    return [(e, vs) for e, vs in elems
            if (np.mean([nos[v][eixo] for v in vs[:4]]) - meio) * lado > 0]


def desenha_campo(ax, nos, tris, campo, titulo, vmin, vmax,
                  extra=None, cor_extra="#33B5A5"):
    """Campo em `tris`, mais um corpo opcional `extra` em cor chapada.

    O corpo extra entra na MESMA coleção, e não numa segunda. O mplot3d
    ordena coleções inteiras pela profundidade média: com duas coleções, o
    invólucro inteiro era desenhado na frente da placa inteira e ela sumia,
    mesmo estando dentro da cavidade e à vista. Numa coleção só a ordenação
    é por polígono, e a oclusão sai certa.

    `extra` é (nós, triângulos) e fica FORA do mapa de cor de propósito: a
    placa não foi resolvida neste FEM — a temperatura dela vem de um balanço
    radiativo à parte, e pintá-la com a mesma escala sugeriria o contrário.
    """
    ids = sorted({v for t in tris for v in t})
    idx = {n: i for i, n in enumerate(ids)}
    P = np.array([nos[n] for n in ids])
    C = np.array([campo.get(n, vmin) for n in ids])
    T = np.array([[idx[a], idx[b], idx[c]] for a, b, c in tris])
    norma = matplotlib.colors.Normalize(vmin, vmax)
    mapa = matplotlib.colormaps["inferno"]
    verts = list(P[T])
    cores = list(mapa(norma(C[T].mean(axis=1))))
    bordas = [(0, 0, 0, 0)] * len(verts)
    if extra:
        enos, etris = extra
        eids = sorted({v for tt in etris for v in tt})
        eidx = {n: i for i, n in enumerate(eids)}
        EP = np.array([enos[n] for n in eids])
        ET = np.array([[eidx[a], eidx[b], eidx[c]] for a, b, c in etris])
        verts += list(EP[ET])
        cores += [matplotlib.colors.to_rgba(cor_extra)] * len(ET)
        bordas += [(1, 1, 1, 0.85)] * len(ET)
    ax.add_collection3d(Poly3DCollection(verts, facecolors=cores,
                                         edgecolors=bordas, linewidths=0.2))
    c = P.mean(axis=0)
    r = float(np.abs(P - c).max())
    ax.set_xlim(c[0] - r, c[0] + r); ax.set_ylim(c[1] - r, c[1] + r)
    ax.set_zlim(c[2] - r, c[2] + r)
    ax.set_box_aspect((1, 1, 1)); ax.set_axis_off()
    ax.set_title(titulo, fontsize=9, pad=-2)
    sm = plt.cm.ScalarMappable(norm=norma, cmap=mapa)
    sm.set_array([])
    return sm


TERM = [("v1", "corpo 50 x 50, cavidade 43 x 43", 38.6),
        ("v2", "corpo 69 x 59, cavidade 62 x 52", 38.3)]

# A placa entra no corte na altura em que a montagem a põe. Ela não toca em
# nada, então é desenhada na sua temperatura de equilíbrio — que NÃO é a
# média da cavidade: com fator de forma de 0,8 para um piso a 49 °C, ela
# fica ~4 K acima dessa média.
Z_PLACA = 9.0 + 8.0 + 5.0        # base + fundo + assento
CENTRO_PCB = (150.0, 100.0)      # origem do projeto KiCad

# Duas escalas, e as duas são necessárias. Com 30-90 °C o corpo inteiro sai
# preto — o que É o resultado, mas não deixa ver nada dentro dele. Com
# 30-40 °C aparece o gradiente que sobra depois da base. Mostrar só a segunda
# seria escolher a escala que faz o efeito parecer maior do que é.
ESCALAS = [((30.0, 90.0), "escala cheia: 30 a 90 °C"),
           ((30.0, 40.0), "escala expandida: 30 a 40 °C")]

if all((AQUI / "fem" / v / "termica_regime.frd").exists() for v, _d, _c in TERM):
    dados = []
    for ver, desc, tcav in TERM:
        nos, elems, campo = le_campo(AQUI / "fem" / ver / "termica_regime.frd")
        # Corte no plano central em Y. A face cortada aponta para +y,
        # entao a metade a GUARDAR e a de y menor, com a camera em +y
        # (azim = 62). Guardar a outra mostra o lado de fora da peca.
        el = meia(nos, elems, eixo=1, lado=-1)
        # placa: malha do modal, transladada do referencial do KiCad para o
        # do invólucro e cortada no mesmo plano
        pl = AQUI / "fem" / ver / "malha.inp"
        pnos, pel = ({}, [])
        if pl.exists():
            bloco = None
            for ln in pl.read_text().splitlines():
                u = ln.upper()
                if ln.startswith("*"):
                    bloco = ("no" if u.startswith("*NODE") else
                             "el" if u.startswith("*ELEMENT") and "C3D10" in u
                             else None)
                    continue
                if bloco is None or not ln.strip():
                    continue
                c = [x.strip() for x in ln.split(",") if x.strip()]
                if bloco == "no" and len(c) >= 4:
                    pnos[int(c[0])] = (float(c[1]) - CENTRO_PCB[0],
                                       float(c[2]) - CENTRO_PCB[1],
                                       float(c[3]) + Z_PLACA)
                elif bloco == "el" and len(c) >= 11:
                    pel.append((int(c[0]), [int(x) for x in c[1:11]]))
        ptris = casca(meia(pnos, pel, eixo=1, lado=-1)) if pnos else []
        if pnos:
            import numpy as _np
            _P = _np.array(list(pnos.values()))
            print(f"   placa: {len(pnos)} nos, {len(pel)} elems, "
                  f"{len(ptris)} triangulos no corte; "
                  f"z {_P[:,2].min():.1f}..{_P[:,2].max():.1f} mm")
        else:
            print("   placa: malha nao encontrada")
        dados.append((ver, desc, tcav, nos, casca(el), campo, pnos, ptris))
        print(f"{ver}: corte com {len(casca(el))} triangulos, "
              f"campo {min(campo.values()):.1f} a {max(campo.values()):.1f} °C")

    figt = plt.figure(figsize=(9.6, 7.6))
    figt.patch.set_facecolor("white")
    for li, ((vmin, vmax), rot_esc) in enumerate(ESCALAS):
        colt = None
        for k, (ver, desc, tcav, nos, tris, campo, pnos, ptris) in enumerate(dados):
            ax = figt.add_axes([0.015 + 0.415 * k, 0.46 - 0.43 * li,
                                0.40, 0.40], projection="3d")
            ax.view_init(elev=16, azim=62)
            rot = (f"{ver} — {desc}\nplaca em equilíbrio a {tcav:.1f} °C"
                   if li == 0 else "")
            colt = desenha_campo(ax, nos, tris, campo, rot, vmin, vmax,
                                 extra=(pnos, ptris) if ptris else None)
        cax = figt.add_axes([0.855, 0.545 - 0.44 * li, 0.018, 0.28])
        cb = figt.colorbar(colt, cax=cax,
                           extend="max" if vmax < 90 else "neither")
        cb.set_label(f"°C — {rot_esc}", fontsize=7.5)
        cb.ax.tick_params(labelsize=7)
    figt.text(0.44, 0.965, "Campo de temperatura em corte — carcaça do motor "
              "a 90 °C, ambiente a 30 °C", ha="center", fontsize=11.5)
    figt.text(0.44, 0.935, "os 60 K morrem na base. Em verde, a placa: ela "
              "assenta 5 mm acima do piso e enxerga quase só ele",
              ha="center", fontsize=8, color="#444444")
    alvo = SAIDA / "termica.png"
    figt.savefig(alvo, dpi=150, bbox_inches="tight", facecolor="white")
    print(f"gerado: {alvo}")
sys.stdout.flush()
