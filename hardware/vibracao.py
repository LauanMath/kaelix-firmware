"""Vibração aleatória (Miles) e fadiga de junta de solda (Steinberg).

O modal em `hardware/fem/README.md` responde "em que frequência". Esta é a
pergunta seguinte, e é a que a indústria faz para equipamento que vive
parafusado numa máquina: com o espectro que a máquina produz, quanto a placa
se desloca, e a junta de solda aguenta quanto tempo.

Três verificações, todas de Steinberg:

  1. Deslocamento 3-sigma pela equação de Miles, a partir de uma PSD de
     aceleração e do modo próprio da placa.
  2. Deslocamento admissível por componente,
         Z_adm = 0,00022 * B / (c * h * sqrt(L))            [polegadas]
     onde B é o lado da placa paralelo ao componente, h a espessura, L o
     comprimento entre as juntas extremas e c a classe de encapsulamento.
     O critério vale para 20 milhões de ciclos.
  3. Regra da oitava: placa e chassi têm de estar separados por um fator 2,
     senão respondem acoplados e a amplificação se multiplica.

    uv run --no-project --with numpy python hardware/vibracao.py
"""
import math
import os
import pathlib
import sys

import numpy as np

AQUI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(AQUI.parent / "training"))
from kaelix_ml.labeling import (ISO_10816_3_ZONE_BOUNDARIES_MM_S,  # noqa: E402
                                ISO_BAND_HZ, GRAVITY_MS2)

POL = 25.4                      # mm por polegada
ESPESSURA = 1.6                 # mm
B_FADIGA = 6.4                  # expoente S-N da solda (Steinberg)
N_REF = 20e6                    # ciclos de referência do critério

# Classe de máquina adotada. III = máquinas grandes sobre fundação rígida, que
# é o caso do motor de bancada instrumentado. O limiar usado é o C/D: a faixa
# em que a máquina ainda opera esperando manutenção, e portanto a que o
# sensor precisa sobreviver.
CLASSE = "III"
_ab, _bc, V_CD = ISO_10816_3_ZONE_BOUNDARIES_MM_S[CLASSE]

# Q do amplificador de ressonância. Steinberg estima Q = sqrt(fn) para placa
# de circuito impresso; é o valor coerente com usar o critério dele. Os outros
# dois entram como sensibilidade, não como alternativa igualmente boa.
def q_steinberg(fn):
    return math.sqrt(fn)


# Classe de encapsulamento de Steinberg. Sem terminal, a junta absorve toda a
# flexão e a constante é a pior; com terminal conformável, o terminal cede.
CLASSE_C = {
    "modulo": 2.25,     # WROOM-1U e Ra-02: castelação, sem terminal
    "qfn": 2.25,        # MPU6050
    "chip": 1.00,       # 0805
    "sot": 0.75,        # SOT-23 / SOT-89, terminal conformável
    "tht": 1.26,        # header passante
}
PACOTE = {"U1": "modulo", "U3": "modulo", "U2": "qfn", "U4": "sot",
          "Q1": "sot", "Q2": "sot", "Q3": "sot", "J1": "chip", "J2": "tht"}


def psd_aceleracao(f, v_rms_mm_s, modo="velocidade"):
    """PSD de aceleração, em (m/s²)²/Hz.

    Vibração de máquina rotativa é aproximadamente de VELOCIDADE constante em
    banda larga — é por isso que a ISO 10816 mede velocidade, e não
    aceleração. Com densidade espectral de velocidade W_v constante,
    W_a(f) = (2 pi f)² W_v, e a aceleração cresce com f².

    A norma define a banda até 1000 Hz. O primeiro modo da placa está ACIMA
    disso, então qualquer valor lá é extrapolação, e ela é a única escolha
    livre desta análise. Por isso são dois modos:

      "velocidade"  W_v constante também acima de 1 kHz. Conservador: a
                    aceleração continua subindo com f².
      "aceleracao"  W_a congelada no valor de 1 kHz acima da banda, isto é,
                    a velocidade rola com 1/f. Mais próximo do que espectro
                    real de máquina faz, e o limite otimista.
    """
    f1, f2 = ISO_BAND_HZ
    w_v = (v_rms_mm_s * 1e-3) ** 2 / (f2 - f1)          # (m/s)²/Hz
    f = np.asarray(f, dtype=float)
    if modo == "velocidade":
        return (2 * np.pi * f) ** 2 * w_v
    return (2 * np.pi * np.minimum(f, f2)) ** 2 * w_v


def miles_3sigma(fn, q, w_a):
    """Deslocamento relativo 3-sigma de um sistema de 1 grau de liberdade."""
    a_rms = math.sqrt(math.pi / 2 * fn * q * w_a)        # m/s²
    return 3.0 * a_rms / (2 * math.pi * fn) ** 2 * 1e3   # mm


def z_admissivel(b_mm, c, l_mm, h_mm=ESPESSURA):
    """Steinberg, em mm. A fórmula original é em polegadas."""
    b, l, h = b_mm / POL, l_mm / POL, h_mm / POL
    return 0.00022 * b / (c * h * math.sqrt(l)) * POL


def vida_horas(z_adm, z_real, fn):
    if z_real <= 0:
        return math.inf
    n = N_REF * (z_adm / z_real) ** B_FADIGA
    return n / fn / 3600.0


# ---------------------------------------------------------------------
# Entrada: modo da placa (FEM) e geometria dos componentes (gerador)
# ---------------------------------------------------------------------
def _modulo(caminho, corte):
    """Executa o topo de um arquivo do projeto, sem disparar o resto dele."""
    import types
    src = pathlib.Path(caminho).read_text()
    src = src[:src.index(corte)]
    m = types.ModuleType(pathlib.Path(caminho).stem + "_vib")
    m.__file__ = str(caminho)
    exec(compile(src, str(caminho), "exec"), m.__dict__)
    return m


# le_frd e frequencias vêm de fem_figuras.py: reimplementar o leitor de .frd
# aqui seria manter duas cópias do mesmo parser de formato de coluna fixa.
_FIG = _modulo(AQUI / "fem_figuras.py", "CASOS = [")


def geometria(versao):
    os.environ["KAELIX_PCB"] = versao
    g = _modulo(AQUI / "gen_pcb.py",
                "# =====================================================================\n"
                "# Roteamento")
    comps = {}
    for ref in g.POSICOES:
        _fp, _val, mapa = g.NET[ref]
        if not mapa or ref not in PACOTE:
            continue
        pads = g.pads_abs(ref)
        if len(pads) < 2:
            continue
        # L de Steinberg é o COMPRIMENTO do componente entre as juntas
        # extremas, num eixo — não a diagonal. Pegar a maior distância entre
        # dois pads quaisquer devolvia a diagonal e inflava L (24,1 mm num
        # módulo de 19,5 x 20,15), o que por sua vez encolhia o admissível.
        vx = max(p["x"] for p in pads) - min(p["x"] for p in pads)
        vy = max(p["y"] for p in pads) - min(p["y"] for p in pads)
        melhor = max(vx, vy)
        eixo_x = vx >= vy
        comps[ref] = dict(
            L=melhor,
            cx=sum(p["x"] for p in pads) / len(pads),
            cy=sum(p["y"] for p in pads) / len(pads),
            B=g.LADO_X if eixo_x else g.LADO_Y,
            c=CLASSE_C[PACOTE[ref]], pacote=PACOTE[ref])
    return comps, (g.LADO_X, g.LADO_Y)


def modo_da_placa(versao):
    base = AQUI / "fem" / versao / "modal_furos_povoada"
    frd, dat = base.with_suffix(".frd"), base.with_suffix(".dat")
    if not frd.exists():
        raise SystemExit(f"falta {frd} — rode KAELIX_PCB={versao} "
                         f"uv run --with gmsh python hardware/fem_modal.py")
    nos, _el, modos = _FIG.le_frd(frd)
    fn = _FIG.frequencias(dat)[0]
    uz = {n: abs(u[2]) for n, u in modos[0].items()}
    umax = max(uz.values())
    return fn, nos, {n: v / umax for n, v in uz.items()}


def forma_local(nos, uzn, x, y, raio=3.0):
    """Maior amplitude modal normalizada sob a área do componente.

    Amostrar um raio fixo de 3 mm subestima o que um módulo de 20 mm sente:
    as juntas que falham são as das pontas, não a do centro. O raio passa a
    ser metade do comprimento do componente.
    """
    v = [uzn[n] for n, p in nos.items()
         if math.hypot(p[0] - x, p[1] - y) <= raio and n in uzn]
    return max(v) if v else 0.0


# frequência do caminho de montagem, de hardware/fem_montagem.py
F_CHASSI = {"v1": {"carga no topo": 936.0, "carga no piso": 1181.0},
            "v2": {"carga no topo": 679.0, "carga no piso": 1670.0}}

# Amortecimento do ASA. 0,03 é o valor que analise-involucro.ipynb adotou para
# a transmissibilidade; mantido aqui para as duas análises falarem a mesma
# língua. Não é medido.
ZETA_ASA = 0.03


def transmissibilidade(r, zeta=ZETA_ASA):
    """Razão de amplitude de um 1 GDL excitado pela base, em r = f/fn."""
    return math.sqrt((1 + (2 * zeta * r) ** 2)
                     / ((1 - r ** 2) ** 2 + (2 * zeta * r) ** 2))


# ---------------------------------------------------------------------
# Relatório
# ---------------------------------------------------------------------
print(f"excitação: ISO 10816-3 classe {CLASSE}, limiar C/D = {V_CD:.1f} mm/s RMS")
print(f"           densidade espectral de velocidade constante em "
      f"{ISO_BAND_HZ[0]:.0f}–{ISO_BAND_HZ[1]:.0f} Hz")
print(f"critério:  Steinberg, {N_REF/1e6:.0f} milhões de ciclos, "
      f"expoente S-N da solda b = {B_FADIGA}\n")

LINHAS, PIOR_CORR = [], {}
for ver in ("v1", "v2"):
    fn, nos, uzn = modo_da_placa(ver)
    comps, (lx, ly) = geometria(ver)
    q = q_steinberg(fn)

    print(f"=== {ver} — placa {lx:.0f} x {ly:.0f} mm, "
          f"1º modo {fn:.0f} Hz, Q = sqrt(fn) = {q:.1f} ===")
    for modo_psd, rot in (("velocidade", "veloc. const. extrapolada"),
                          ("aceleracao", "acel. const. acima de 1 kHz")):
        w = float(psd_aceleracao(fn, V_CD, modo_psd))
        z3 = miles_3sigma(fn, q, w)
        print(f"  PSD em {fn:.0f} Hz ({rot}): {w:.3g} (m/s²)²/Hz = "
              f"{w / GRAVITY_MS2**2:.4f} g²/Hz  ->  Z 3σ máx = {z3*1000:.1f} µm")
    print()

    # o caso conservador é o que decide
    w = float(psd_aceleracao(fn, V_CD, "velocidade"))
    z3_max = miles_3sigma(fn, q, w)

    print(f"  {'comp':<5} {'pacote':<7} {'L':>6} {'B':>5} {'c':>5} "
          f"{'forma':>6} {'Z 3σ':>8} {'Z adm':>8} {'margem':>7}  vida")
    print("  " + "-" * 76)
    piores = []
    for ref in sorted(comps):
        d = comps[ref]
        forma = forma_local(nos, uzn, d["cx"], d["cy"],
                            raio=max(3.0, d["L"] / 2))
        z3 = z3_max * forma
        zadm = z_admissivel(d["B"], d["c"], d["L"])
        marg = zadm / z3 if z3 > 0 else math.inf
        h = vida_horas(zadm, z3, fn)
        piores.append((marg, ref))
        vida = "> 100 anos" if h > 876000 else (
            f"{h/8760:.1f} anos" if h > 8760 else f"{h:.0f} h")
        print(f"  {ref:<5} {d['pacote']:<7} {d['L']:5.1f} {d['B']:5.1f} "
              f"{d['c']:5.2f} {forma:6.2f} {z3*1000:7.1f} µm {zadm*1000:7.0f} µm "
              f"{marg:6.1f}x  {vida}")
        LINHAS.append(dict(versao=ver, ref=ref, pacote=d["pacote"], L=d["L"],
                           B=d["B"], c=d["c"], forma=forma, z3_um=z3 * 1000,
                           zadm_um=zadm * 1000, margem=marg, vida_h=h, fn=fn))
    pior = min(piores)
    print(f"  pior caso: {pior[1]} com margem {pior[0]:.1f}x "
          f"({'PASSA' if pior[0] >= 1.0 else 'NAO PASSA'})")
    # Steinberg formula o critério para o componente no CENTRO da placa, onde
    # o deslocamento é máximo. Escalonar pela forma modal local é refinamento;
    # sem ele o número é o do livro, e é o que se leva a uma revisão.
    sem_forma = min(z_admissivel(d["B"], d["c"], d["L"]) / z3_max
                    for d in comps.values())
    print(f"  sem escalonar pela forma modal (critério do livro): "
          f"margem {sem_forma:.1f}x")

    # A margem acima supõe que a placa é excitada por uma BASE RÍGIDA. Se o
    # chassi tem modo próprio perto do da placa, o que chega na placa já vem
    # amplificado pelo chassi, e a hipótese cai. É o que a regra da oitava
    # protege — e é por isso que ela não é estética.
    print(f"\n  regra da oitava e correção de transmissibilidade "
          f"(placa {fn:.0f} Hz, zeta = {ZETA_ASA}):")
    print(f"    {'chassi':<16} {'f':>7} {'razao':>6} {'T':>6} "
          f"{'margem':>10} {'vida (C/D)':>12}")
    for onde, fc in F_CHASSI[ver].items():
        r = fn / fc
        tr = transmissibilidade(r)
        ok = r >= 2.0 or r <= 0.5
        mc = pior[0] / tr
        h = N_REF * mc ** B_FADIGA / fn / 3600.0
        vida = ("> 100 anos" if h > 876000 else
                f"{h/8760:.1f} anos" if h > 8760 else f"{h:.0f} h")
        print(f"    {onde:<16} {fc:6.0f} Hz {r:5.2f} {tr:6.2f} "
              f"{mc:9.1f}x {vida:>12}   "
              f"{'oitava ok' if ok else 'ACOPLADO'}")
        PIOR_CORR.setdefault(ver, []).append((mc, onde, tr, vida))
    print()

print("pior combinacao de cada versao, ja com a amplificacao do chassi:")
for ver, casos in PIOR_CORR.items():
    m, onde, tr, vida = min(casos)
    print(f"  {ver}: {onde}, T = {tr:.2f}  ->  margem {m:.1f}x, vida {vida} "
          f"em zona C/D continua")
print()
print("sensibilidade do pior caso ao Q e ao nivel da ISO (SEM a correcao "
      "do chassi):")
print(f"  {'Q':>6}  {'zona':<12} " + "  ".join(f"{v:>10}" for v in ("v1", "v2")))
for q_fixo, rot_q in ((None, "sqrt(fn)"), (20.0, "20"), (10.0, "10")):
    for zona, vel in (("C/D", V_CD), ("B/C", _bc)):
        cel = []
        for ver in ("v1", "v2"):
            fn = [l["fn"] for l in LINHAS if l["versao"] == ver][0]
            q = q_fixo or q_steinberg(fn)
            w = float(psd_aceleracao(fn, vel, "velocidade"))
            z3max = miles_3sigma(fn, q, w)
            m = min((l["zadm_um"] / (z3max * 1000 * l["forma"])
                     if l["forma"] > 0 else math.inf)
                    for l in LINHAS if l["versao"] == ver)
            cel.append(f"{m:9.1f}x")
        print(f"  {rot_q:>6}  {zona + ' ' + f'{vel:.1f} mm/s':<12} "
              + "  ".join(cel))
sys.stdout.flush()


# ---------------------------------------------------------------------
# Dados para a figura (o desenho é em R, como as demais do projeto)
# ---------------------------------------------------------------------
import csv                                                  # noqa: E402

DADOS = AQUI.parent / "experiments" / "figures" / "data"
DADOS.mkdir(parents=True, exist_ok=True)
FN = {l["versao"]: l["fn"] for l in LINHAS}

with (DADOS / "fig10_transmissibilidade.csv").open("w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["versao", "carga", "f_chassi_hz", "freq_hz", "t"])
    ff = np.logspace(math.log10(100), math.log10(6000), 700)
    for ver, casos in F_CHASSI.items():
        for onde, fc in casos.items():
            for f_ in ff:
                w.writerow([ver, onde, f"{fc:.0f}", f"{f_:.5g}",
                            f"{transmissibilidade(f_ / fc):.5g}"])

with (DADOS / "fig10_margens.csv").open("w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["versao", "ref", "pacote", "L_mm", "forma", "z3_um", "zadm_um",
                "margem", "margem_corrigida", "vida_h", "vida_corrigida_h"])
    for ver, casos in PIOR_CORR.items():
        _m, _onde, tr, _v = min(casos)
        for l in LINHAS:
            if l["versao"] != ver:
                continue
            mc = l["margem"] / tr
            w.writerow([ver, l["ref"], l["pacote"], f"{l['L']:.2f}",
                        f"{l['forma']:.3f}", f"{l['z3_um']:.2f}",
                        f"{l['zadm_um']:.1f}", f"{l['margem']:.3f}",
                        f"{mc:.3f}", f"{l['vida_h']:.4g}",
                        f"{N_REF * mc ** B_FADIGA / l['fn'] / 3600.0:.4g}"])

with (DADOS / "fig10_sensibilidade.csv").open("w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["versao", "q_rotulo", "q", "zona", "v_mm_s", "margem"])
    for q_fixo, rot_q in ((None, "sqrt(fn)"), (20.0, "Q = 20"), (10.0, "Q = 10")):
        for zona, vel in (("C/D", V_CD), ("B/C", _bc), ("A/B", _ab)):
            for ver in ("v1", "v2"):
                fnv = FN[ver]
                q = q_fixo or q_steinberg(fnv)
                z3max = miles_3sigma(fnv, q,
                                     float(psd_aceleracao(fnv, vel, "velocidade")))
                m = min((l["zadm_um"] / (z3max * 1000 * l["forma"])
                         if l["forma"] > 0 else math.inf)
                        for l in LINHAS if l["versao"] == ver)
                w.writerow([ver, rot_q, f"{q:.1f}", zona, vel, f"{m:.3f}"])

with (DADOS / "fig10_referencias.csv").open("w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["classe_iso", "v_ab", "v_bc", "v_cd", "zeta_asa", "b_sn",
                "n_ref", "fn_v1", "fn_v2"])
    w.writerow([CLASSE, _ab, _bc, V_CD, ZETA_ASA, B_FADIGA, N_REF,
                f"{FN['v1']:.0f}", f"{FN['v2']:.0f}"])

print(f"\ndados escritos em {DADOS}/fig10_*.csv")
print("figura: Rscript experiments/figures/scripts/fig10_vibracao.R")
sys.stdout.flush()
