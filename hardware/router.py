"""Roteador de labirinto de duas camadas para o disco do Kaelix.

Por que existe: o gerador de PCB colocava footprints, planos de terra e o
contorno, e parava aí. Toda net de sinal ficava no ratsnest, e o DRC
acusava 70 pads desconectados. "Placa gerada" e "placa roteada" são coisas
diferentes, e a diferença não pode ficar implícita.

Modelo
------
Grade de 0,1 mm sobre o disco, duas camadas (F.Cu e B.Cu). Cada célula
guarda o dono do cobre que a ocupa:

     0   livre
    >0   número da net que ocupa (passável só para essa net)
    -1   proibido para todos (borda, furo NPTH, pad sem net, conflito)

Um obstáculo é carimbado INFLADO por (folga + largura/2), que é a distância
do centro de uma pista até a borda do obstáculo. Assim "célula passável"
já significa "pista aqui respeita a folga", e o A* não precisa checar
geometria a cada passo.

Folga de 0,15 mm, e não 0,2
---------------------------
O MPU6050 é um QFN-24 de 0,5 mm de passo: pad de 0,25 mm, vão de 0,25 mm
entre pads vizinhos. Com folga de 0,2 mm o obstáculo inflado do pad vizinho
cobre a própria linha de centro do pad que se quer escapar (0,375 - 0,3 =
0,075 mm de sobra, menos que uma célula da grade) e o escape falha. Com
0,15 mm sobram 0,125 mm — mais de uma célula, e o escape radial fecha.
0,15 mm de folga e traço com 0,2 mm estão dentro do processo padrão de duas
camadas da maioria das casas; 0,2/0,2 não é requisito de fabricação aqui,
era só o valor herdado.

GND não passa por aqui: os dois planos e as vias de costura resolvem o
retorno. Rotear terra com traço num plano sólido é desfazer o plano.
"""

import heapq
import math

import numpy as np

PASSO = 0.1        # mm por célula
LARGURA = 0.2      # largura da pista
FOLGA = 0.15       # folga cobre a cobre
INFLA = FOLGA + LARGURA / 2          # obstáculo -> centro de pista
VIA_D, VIA_FURO = 0.6, 0.3
FOLGA_FURO = 0.25                    # furo a cobre
FOLGA_BORDA = 0.5                    # cobre a borda da placa (regra do KiCad)
FOLGA_ZONA = 0.3                     # folga do plano de GND aos pads
ESP_ZONA = 0.2                       # espessura mínima do plano

CUSTO_VIA = 12.0        # em unidades de célula (1,2 mm de pista equivalente)

# Numa placa de duas camadas, uma delas precisa ser plano. Tratar F.Cu e B.Cu
# como equivalentes espalha sinal pelos dois lados e retalha o retorno: o
# plano de baixo chegou a ficar partido em três pedaços eletricamente
# separados, justamente sob o módulo LoRa. Encarecer B.Cu empurra o percurso
# longo para cima e deixa embaixo só o que precisa estar embaixo — os escapes
# das peças montadas nessa face.
CUSTO_CAMADA = (1.0, 2.2)   # F.Cu, B.Cu
CUSTO_VIA_TERRA = 12.0   # no escape de GND a via é a saída desejada, não um custo

_G = {}            # estado do módulo, preenchido por rotear()


# ---------------------------------------------------------------------
# Grade
# ---------------------------------------------------------------------
def _ij(x, y):
    return (int(round((x - _G["x0"]) / PASSO)), int(round((y - _G["y0"]) / PASSO)))


def _xy(i, j):
    return (_G["x0"] + i * PASSO, _G["y0"] + j * PASSO)


def _carimba(mascara, camadas, valor):
    """Aplica `valor` às células de `mascara`. Dono diferente vira -1."""
    for c in camadas:
        dono = _G["dono"][c]
        conflito = mascara & (dono != 0) & (dono != valor)
        dono[mascara & (dono == 0)] = valor
        dono[conflito] = -1


def _mask_ret(cx, cy, w, h, infla):
    """Células cujo centro está a <= `infla` do retângulo."""
    X, Y = _G["X"], _G["Y"]
    dx = np.maximum(np.abs(X - cx) - w / 2.0, 0.0)
    dy = np.maximum(np.abs(Y - cy) - h / 2.0, 0.0)
    return (dx * dx + dy * dy) <= infla * infla


def _mask_seg(x1, y1, x2, y2, infla):
    X, Y = _G["X"], _G["Y"]
    vx, vy = x2 - x1, y2 - y1
    L2 = vx * vx + vy * vy
    if L2 == 0.0:
        d2 = (X - x1) ** 2 + (Y - y1) ** 2
    else:
        t = np.clip(((X - x1) * vx + (Y - y1) * vy) / L2, 0.0, 1.0)
        d2 = (X - (x1 + t * vx)) ** 2 + (Y - (y1 + t * vy)) ** 2
    return d2 <= infla * infla


def _erode(mask, raio_celulas):
    """Erosão binária por disco — onde um objeto de raio r cabe inteiro."""
    r = int(raio_celulas)
    out = mask.copy()
    for di in range(-r, r + 1):
        for dj in range(-r, r + 1):
            if di * di + dj * dj > r * r:
                continue
            if di == 0 and dj == 0:
                continue
            out &= np.roll(np.roll(mask, di, axis=0), dj, axis=1)
    return out


# ---------------------------------------------------------------------
# A*
# ---------------------------------------------------------------------
_VIZ = [(1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
        (1, 1, 1.4142), (1, -1, 1.4142), (-1, 1, 1.4142), (-1, -1, 1.4142)]


def _astar(passavel, via_ok, inicio, alvo):
    """Caminho de (camada, i, j) a (camada, i, j). Devolve lista de estados."""
    N = _G["N"]
    li, ii, ji = inicio
    lg, ig, jg = alvo

    def h(l, i, j):
        di, dj = abs(i - ig), abs(j - jg)
        base = (di + dj) + (1.4142 - 2) * min(di, dj)
        return base + (CUSTO_VIA if l != lg else 0.0)

    g = {inicio: 0.0}
    veio = {}
    fila = [(h(*inicio), inicio)]
    visto = set()
    while fila:
        _f, est = heapq.heappop(fila)
        if est in visto:
            continue
        visto.add(est)
        if est == alvo:
            cam, e = [], est
            while e in veio:
                cam.append(e); e = veio[e]
            cam.append(inicio)
            return cam[::-1]
        l, i, j = est
        base = g[est]
        for di, dj, c in _VIZ:
            ni, nj = i + di, j + dj
            if not (0 <= ni < N and 0 <= nj < N) or not passavel[l, ni, nj]:
                continue
            if di and dj:   # diagonal só se os dois ortogonais também abrem
                if not (passavel[l, i + di, j] and passavel[l, i, j + dj]):
                    continue
            nv = (l, ni, nj)
            ng = base + c * CUSTO_CAMADA[l]
            if ng < g.get(nv, 1e18):
                g[nv] = ng
                veio[nv] = est
                heapq.heappush(fila, (ng + h(*nv), nv))
        if via_ok[i, j] and passavel[1 - l, i, j]:
            nv = (1 - l, i, j)
            ng = base + CUSTO_VIA
            if ng < g.get(nv, 1e18):
                g[nv] = ng
                veio[nv] = est
                heapq.heappush(fila, (ng + h(*nv), nv))
    return None


def _segmentos(caminho):
    """Comprime o caminho em segmentos retos e lista as trocas de camada."""
    segs, vias = [], []
    i = 0
    while i < len(caminho) - 1:
        l0, i0, j0 = caminho[i]
        l1, i1, j1 = caminho[i + 1]
        if l0 != l1:
            vias.append(_xy(i0, j0))
            i += 1
            continue
        di, dj = i1 - i0, j1 - j0
        k = i + 1
        while k < len(caminho) - 1:
            la, ia, ja = caminho[k]
            lb, ib, jb = caminho[k + 1]
            if la != lb or (ib - ia, jb - ja) != (di, dj):
                break
            k += 1
        xa, ya = _xy(i0, j0)
        xb, yb = _xy(*caminho[k][1:])
        segs.append((xa, ya, xb, yb, l0))
        i = k
    return segs, vias


# ---------------------------------------------------------------------
# Entrada
# ---------------------------------------------------------------------
CAMADA = {0: "F.Cu", 1: "B.Cu"}


def _liga(pa, pb, nid, pistas, vias):
    """Roteia um par de pads. Devolve True se fechou, carimbando o cobre."""
    passavel = (_G["dono"] == 0) | (_G["dono"] == nid)
    via_ok = _erode(passavel[0] & passavel[1],
                    int(math.ceil((VIA_D / 2 + FOLGA + LARGURA / 2) / PASSO)))
    _ra, _na, xa, ya, ca = pa
    _rb, _nb, xb, yb, cb = pb
    ia, ja = _ij(xa, ya)
    ib, jb = _ij(xb, yb)
    cam = None
    for la in ([ca] if ca is not None else [0, 1]):
        for lb in ([cb] if cb is not None else [0, 1]):
            if not (passavel[la, ia, ja] and passavel[lb, ib, jb]):
                continue
            cam = _astar(passavel, via_ok, (la, ia, ja), (lb, ib, jb))
            if cam:
                break
        if cam:
            break
    if not cam:
        return False
    segs, vs = _segmentos(cam)
    for (x1, y1, x2, y2, l) in segs:
        pistas.append((x1, y1, x2, y2, CAMADA[l], LARGURA, nid))
        _carimba(_mask_seg(x1, y1, x2, y2, INFLA + LARGURA / 2), (l,), nid)
        m = _mask_seg(x1, y1, x2, y2, LARGURA / 2)
        (_G["gnd"] if nid == _G.get("nid_gnd") else _G["cobre"])[l] |= m
    for (vx, vy) in vs:
        vias.append((vx, vy, nid))
        _carimba(_mask_ret(vx, vy, 0.0, 0.0, VIA_D / 2 + INFLA), (0, 1), nid)
        m = _mask_ret(vx, vy, 0.0, 0.0, VIA_D / 2)
        alvo = _G["gnd"] if nid == _G.get("nid_gnd") else _G["cobre"]
        alvo[0] |= m; alvo[1] |= m
    return True


def _fora_do_contorno(margem):
    """Máscara do que está FORA do contorno da placa, com folga `margem`.

    O contorno é um retângulo com quatro recortes circulares nos cantos, para
    os bosses M3 do invólucro — não um disco. Ver o cabeçalho de gen_pcb.py.
    """
    (CXc, CYc), (lx, ly, bx, by, br) = _G["centro"], _G["contorno"]
    hx, hy = lx / 2.0 - margem, ly / 2.0 - margem
    fora = (np.abs(_G["X"] - CXc) > hx) | (np.abs(_G["Y"] - CYc) > hy)
    for sx in (-1, 1):
        for sy in (-1, 1):
            d2 = ((_G["X"] - (CXc + sx * bx)) ** 2
                  + (_G["Y"] - (CYc + sy * by)) ** 2)
            fora |= d2 < (br + margem) ** 2
    return fora


def _monta_grade(net, posicoes, netnum, pads_abs, centro, contorno, nc):
    """Zera a grade e carimba borda, furos e pads. Chamada a cada passada."""
    CXc, CYc = centro
    meio = max(contorno[0], contorno[1]) / 2.0
    N = int(round(2 * meio / PASSO)) + 1
    _G["N"] = N
    _G["contorno"] = contorno
    _G["x0"], _G["y0"] = CXc - meio, CYc - meio
    xs = _G["x0"] + np.arange(N) * PASSO
    ys = _G["y0"] + np.arange(N) * PASSO
    _G["X"], _G["Y"] = np.meshgrid(xs, ys, indexing="ij")
    _G["dono"] = np.zeros((2, N, N), dtype=np.int32)
    # Cobre REAL de nets que não são GND, sem inflação nenhuma. O mapa de
    # donos não serve para decidir onde o plano cabe: ele marca -1 em toda
    # célula que apenas fica PERTO de uma pista legal, e com isso declarava
    # ilhado o pad térmico do WROOM-1U, que na verdade tem doze furos ligando
    # os dois planos. Uma coisa é "não posso rotear aqui", outra é "não há
    # cobre aqui".
    _G["cobre"] = np.zeros((2, N, N), dtype=bool)
    _G["gnd"] = np.zeros((2, N, N), dtype=bool)     # cobre de GND: pad, pista, via
    _G["gnd_alheio"] = np.zeros((2, N, N), dtype=bool)   # pads de GND de passo fino
    # Sob o corpo de um encapsulamento de passo fino, na face dele, o plano
    # NÃO conta. A grade via ali células de plano entre as fileiras de pads e
    # tratava a região como caminho; o preenchimento do KiCad, com espessura
    # mínima e folga exatas, deixa só retalhos que o escape seguinte ou uma
    # pista de sinal fecham em ilha. Foi assim que o U2.1 da v3 terminou num
    # toco "ligado ao plano" que o DRC acusou como grupo solto. Atravessar
    # com pista continua possível; o que sai é contar com plano ali.
    _G["sob_fino"] = np.zeros((2, N, N), dtype=bool)
    _G["centro"] = (CXc, CYc)
    _G["nid_gnd"] = netnum["GND"]

    fora = _fora_do_contorno(FOLGA_BORDA + LARGURA / 2)
    for c in (0, 1):
        _G["dono"][c][fora] = -1

    LADO = {"F": 0, "B": 1}
    for ref, (_fp, _val, mapa) in net.items():
        if ref not in posicoes:
            continue
        todos = pads_abs(ref)
        if mapa and _passo_fino(todos):
            xs = [q["x"] for q in todos]; ys = [q["y"] for q in todos]
            caixa = _mask_ret((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2,
                              max(xs) - min(xs), max(ys) - min(ys), 0.0)
            for f in {f for q in todos for f in q["faces"]}:
                _G["sob_fino"][LADO[f]] |= caixa
        for p in todos:
            if not mapa:        # furo de fixação: NPTH, folga de furo
                _carimba(_mask_ret(p["x"], p["y"], 0.0, 0.0,
                                   p["w"] / 2 + FOLGA_FURO + LARGURA / 2), (0, 1), -1)
                m = _mask_ret(p["x"], p["y"], 0.0, 0.0, p["w"] / 2 + FOLGA_FURO)
                _G["cobre"][0] |= m; _G["cobre"][1] |= m
                continue
            rede = mapa.get(p["num"])
            valor = netnum[rede] if (rede and rede != nc) else -1
            camadas = [LADO[f] for f in p["faces"]]
            _carimba(_mask_ret(p["x"], p["y"], p["w"], p["h"], INFLA), camadas, valor)
            m = _mask_ret(p["x"], p["y"], p["w"], p["h"], 0.0)
            for c in camadas:
                (_G["gnd"] if rede == "GND" else _G["cobre"])[c] |= m
                if rede == "GND":
                    _G["gnd_alheio"][c] |= m


def _passada(grupos, netnum, ordem, pistas, vias):
    pendentes = []
    for rede in ordem:
        pads = grupos[rede]
        if len(pads) < 2:
            continue
        nid = netnum[rede]
        dentro, restam = [0], list(range(1, len(pads)))
        arestas = []
        while restam:
            melhor = min(((a, b) for a in dentro for b in restam),
                         key=lambda ab: math.hypot(pads[ab[0]][2] - pads[ab[1]][2],
                                                   pads[ab[0]][3] - pads[ab[1]][3]))
            arestas.append(melhor)
            dentro.append(melhor[1]); restam.remove(melhor[1])

        # A árvore geradora mínima diz QUAIS ligações fazer, mas a aresta mais
        # curta nem sempre é a roteável: se ela falhar, a net ainda fecha
        # ligando o pad órfão a qualquer pad já conectado.
        conectados = {0}
        for a, b in arestas:
            alvos = sorted(conectados,
                           key=lambda k: math.hypot(pads[k][2] - pads[b][2],
                                                    pads[k][3] - pads[b][3]))
            if a in alvos:
                alvos.remove(a)
            alvos.insert(0, a)
            if any(_liga(pads[k], pads[b], nid, pistas, vias) for k in alvos):
                conectados.add(b)
            else:
                pendentes.append((f"{pads[a][0]}.{pads[a][1]}",
                                  f"{pads[b][0]}.{pads[b][1]}", rede))
    return pendentes


def rotear(net, posicoes, netnum, pads_abs, centro, contorno, borda, nc, passadas=10):
    """Roteia todas as nets de sinal. GND fica com os planos.

    Passadas com prioridade para quem falhou
    ----------------------------------------
    Uma passada só não fecha: a ordem de roteamento decide quem acha
    corredor e quem chega depois de o anel estar cheio. Nem "curtas
    primeiro" nem "longas primeiro" resolve — as duas ordens deixam
    pendências, só que de nets diferentes.

    O que resolve é lembrar. A cada passada a grade é reconstruída do zero
    e as nets que falharam antes vão para a frente da fila, na ordem de
    quantas vezes falharam. Quem não conseguiu passar da última vez escolhe
    caminho primeiro na próxima. É negociação de congestionamento na sua
    forma mais simples, e converge em poucas passadas para este tamanho de
    placa.
    """
    LADO = {"F": 0, "B": 1}
    grupos = {}
    for ref, (_fp, _val, mapa) in net.items():
        if ref not in posicoes:
            continue
        _x, _y, _r, lado = posicoes[ref]
        for p in pads_abs(ref):
            rede = mapa.get(p["num"])
            if not rede or rede == nc or rede == "GND":
                continue
            c = LADO[lado] if len(p["faces"]) == 1 else None
            grupos.setdefault(rede, []).append((ref, p["num"], p["x"], p["y"], c))

    def envergadura(pads):
        return max(math.hypot(a[2] - b[2], a[3] - b[3]) for a in pads for b in pads)

    falhas = {r: 0 for r in grupos}
    melhor_ordem, melhor_n = None, None
    ordem = None
    for _ in range(passadas):
        ordem = sorted(grupos, key=lambda r: (-falhas[r],
                                              envergadura(grupos[r])
                                              if len(grupos[r]) > 1 else 0.0))
        pistas, vias, esc, pend = _uma_passada(net, posicoes, netnum, pads_abs,
                                               centro, contorno, nc, grupos, ordem)
        if melhor_n is None or len(pend) < melhor_n:
            melhor_ordem, melhor_n = list(ordem), len(pend)
        if not pend:
            _G["escapes"] = esc
            _G["terra"] = costura_e_terra(net, posicoes, netnum, pads_abs,
                                          centro, contorno, netnum["GND"], pistas, vias)
            return pistas, vias, pend
        for _a, _b, rede in pend:
            falhas[rede] += 1

    # Nenhuma passada fechou tudo. Refaz a MELHOR do zero, em vez de remendar
    # o estado da última: a grade, o mapa de cobre e os escapes de terra têm
    # de descrever a mesma placa que as pistas devolvidas, ou as vias de
    # costura vão ser colocadas em cima de pista.
    pistas, vias, esc, pend = _uma_passada(net, posicoes, netnum, pads_abs,
                                           centro, contorno, nc, grupos, melhor_ordem)
    _G["escapes"] = esc
    _G["terra"] = costura_e_terra(net, posicoes, netnum, pads_abs,
                                  centro, contorno, netnum["GND"], pistas, vias)
    return pistas, vias, pend


def _uma_passada(net, posicoes, netnum, pads_abs, centro, contorno, nc, grupos, ordem):
    _monta_grade(net, posicoes, netnum, pads_abs, centro, contorno, nc)
    pistas, vias = [], []
    esc = escapes_terra(net, posicoes, netnum, pads_abs, netnum["GND"], pistas, vias)
    pend = _passada(grupos, netnum, ordem, pistas, vias)
    return pistas, vias, esc, pend


def _gnd_ok(nid=None, margem=0.0):
    """Onde o cobre de GND PODE existir, por camada.

    Não é "célula livre": o plano guarda FOLGA_ZONA do cobre alheio e ainda
    precisa de ESP_ZONA de espessura própria. Num QFN de 0,5 mm de passo o
    canal entre dois pads tem 0,25 mm e o plano precisa de 0,7 mm — ele não
    entra, e é por isso que os pads de GND no meio de uma fileira ficam
    ilhados. A conta sai do cobre real, não do mapa de donos.
    """
    borda = _fora_do_contorno(FOLGA_BORDA)
    alheio = _G["cobre"] | borda[None, :, :]
    r = int(math.ceil((FOLGA_ZONA + ESP_ZONA / 2 + margem) / PASSO))
    return ~_dilata(alheio, r) & ~_G["sob_fino"]


def _dilata(mask, r):
    out = mask.copy()
    for di in range(-r, r + 1):
        for dj in range(-r, r + 1):
            if di * di + dj * dj > r * r or (di == 0 and dj == 0):
                continue
            eixo = (1, 2) if mask.ndim == 3 else (0, 1)
            out |= np.roll(np.roll(mask, di, axis=eixo[0]), dj, axis=eixo[1])
    return out


def _alcance(ok, sementes, ponte):
    """Busca em largura sobre o plano, nas duas camadas ligadas pelas vias.

    Este é o teste que estava faltando. "Há célula de plano perto do pad"
    não quer dizer nada: a célula pode ser uma ilha cercada por escapes.
    O que responde à pergunta é a componente conexa — o cobre que sai das
    vias de costura e chega, ou não chega, ao pad.
    """
    N = _G["N"]
    visto = np.zeros_like(ok)
    pilha = []
    for (l, i, j) in sementes:
        if ok[l, i, j] and not visto[l, i, j]:
            visto[l, i, j] = True
            pilha.append((l, i, j))
    while pilha:
        l, i, j = pilha.pop()
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ni, nj = i + di, j + dj
            if 0 <= ni < N and 0 <= nj < N and ok[l, ni, nj] and not visto[l, ni, nj]:
                visto[l, ni, nj] = True
                pilha.append((l, ni, nj))
        # Troca de camada onde HÁ furo metalizado de GND: via de costura, via
        # de sinal de GND ou pad passante de GND — o pad térmico do WROOM-1U
        # tem doze deles. Restringir a ponte às vias de costura declarava
        # ilhado justamente o cobre que os furos do módulo já ligam.
        if ponte[i, j] and ok[1 - l, i, j] and not visto[1 - l, i, j]:
            visto[1 - l, i, j] = True
            pilha.append((1 - l, i, j))
    return visto


def _pad_celulas(x, y, w, h):
    m = _mask_ret(x, y, w, h, 0.0)
    return np.argwhere(m)


def _astar_conjunto(passavel, via_ok, inicio, alvo_mask):
    """Como _astar, mas o alvo é um CONJUNTO de células — o plano de terra.

    Sem heurística: com alvo difuso não existe estimativa admissível barata,
    e a busca é curta o bastante (o plano costuma estar a poucos milímetros)
    para Dijkstra puro resolver.
    """
    N = _G["N"]
    g = {inicio: 0.0}
    veio = {}
    fila = [(0.0, inicio)]
    visto = set()
    while fila:
        _f, est = heapq.heappop(fila)
        if est in visto:
            continue
        visto.add(est)
        l, i, j = est
        if alvo_mask[l, i, j]:
            cam, e = [], est
            while e in veio:
                cam.append(e); e = veio[e]
            cam.append(inicio)
            return cam[::-1]
        base = g[est]
        for di, dj, c in _VIZ:
            ni, nj = i + di, j + dj
            if not (0 <= ni < N and 0 <= nj < N) or not passavel[l, ni, nj]:
                continue
            if di and dj and not (passavel[l, i + di, j] and passavel[l, i, j + dj]):
                continue
            nv = (l, ni, nj)
            if base + c < g.get(nv, 1e18):
                g[nv] = base + c; veio[nv] = est
                heapq.heappush(fila, (base + c, nv))
        if via_ok[i, j] and passavel[1 - l, i, j]:
            nv = (1 - l, i, j)
            # Via BARATA aqui, ao contrário do roteamento de sinal. O escape
            # de um pad de GND ilhado quer exatamente isto: sair da face
            # congestionada e cair no plano da outra, no ponto mais próximo.
            # Com a via cara o A* prefere serpentear pela mesma face e
            # terminar numa ilha de plano que o preenchimento não alcança.
            if base + CUSTO_VIA_TERRA < g.get(nv, 1e18):
                g[nv] = base + CUSTO_VIA_TERRA; veio[nv] = est
                heapq.heappush(fila, (base + CUSTO_VIA_TERRA, nv))
    return None


def _anel_semente(ok):
    """Células do anel externo: o cobre que com certeza é o plano principal."""
    # Faixa junto à borda do contorno: o cobre que com certeza é o plano
    # principal. Vale para qualquer contorno, não só para disco.
    anel = _fora_do_contorno(FOLGA_BORDA + 2.0) & ~_fora_do_contorno(FOLGA_BORDA + 0.4)
    return [(l, i, j) for l in (0, 1) for i, j in np.argwhere(anel & ok[l])]


def _passo_fino(pads, limite=0.8):
    """Menor distância entre centros de pads vizinhos abaixo do limite.

    O critério não é o nome do encapsulamento: é a geometria. Com passo
    abaixo de 0,8 mm o canal entre dois pads não comporta o plano
    (ESP_ZONA de espessura mais FOLGA_ZONA de cada lado), e todo pad de GND
    que não estiver na ponta da fileira fica ilhado por construção.
    """
    # Só entre pads de NÚMEROS diferentes: o pad térmico do WROOM-1U é uma
    # matriz de doze furos com o mesmo número 41, a 0,7 mm um do outro. São
    # o mesmo condutor, não vizinhos disputando espaço — tratá-los como passo
    # fino gerava doze escapes idênticos para o mesmo nó.
    d = [p for p in pads]
    n = len(d)
    for a in range(n):
        for b in range(a + 1, n):
            if d[a]["num"] == d[b]["num"]:
                continue
            dist = math.hypot(d[a]["x"] - d[b]["x"], d[a]["y"] - d[b]["y"])
            if 0 < dist < limite:
                return True
    return False


def escapes_terra(net, posicoes, netnum, pads_abs, nid, pistas, vias):
    """Dá saída aos pads de GND que a própria geometria do encapsulamento ilha.

    Roda ANTES das nets de sinal, e essa ordem é o ponto todo. O AD0 e o
    FSYNC do MPU6050 (pads 9 e 11) ficam no meio de uma fileira de QFN de
    0,5 mm de passo: o plano não entra no canal de 0,25 mm entre pads, e
    depois que os vizinhos escapam não sobra corredor nenhum. Roteado antes,
    cada pad da fileira sai reto para fora no seu próprio corredor — seis
    escapes paralelos a 0,5 mm de passo cabem, porque o mínimo entre eixos
    de pista é 0,4 mm.

    Deixar esses dois pads no ar não é detalhe de layout: o AD0 define o
    endereço I2C do sensor. Flutuando, o endereço é indefinido e o
    WHO_AM_I do firmware falha de forma intermitente.
    """
    # Margem no alvo do escape: o plano no limite exato da folga é uma faixa
    # de 0,2 mm que o KiCad pode não preencher. O escape tem de terminar em
    # plano de verdade, não na borda do que é teoricamente possível.
    ok = _gnd_ok(margem=0.25)
    ponte = np.zeros((_G["N"], _G["N"]), dtype=bool)
    LADO = {"F": 0, "B": 1}
    for ref, (_fp, _val, mapa) in net.items():
        if ref not in posicoes or not mapa:
            continue
        for p in pads_abs(ref):
            if mapa.get(p["num"]) == "GND" and len(p["faces"]) == 2:
                ponte |= _mask_ret(p["x"], p["y"], p["w"], p["h"], 0.0)
    alcance = _alcance(ok | _G["gnd"], _anel_semente(ok), ponte)
    # Travessia e CHEGADA são critérios diferentes. Para saber se um pad já
    # está ligado basta o plano no limite da folga; para TERMINAR um escape
    # ali, não: uma faixa de plano com 0,2 mm no limite exato pode não ser
    # preenchida, e o escape acaba numa ilha. O alvo pede folga extra.
    alvo = alcance & _gnd_ok(margem=0.35)

    feitos, falhas = [], []
    for ref, (_fp, _val, mapa) in net.items():
        if ref not in posicoes or not mapa:
            continue
        todos = pads_abs(ref)
        fino = _passo_fino(todos)
        vistos = set()
        for p in todos:
            if mapa.get(p["num"]) != "GND" or p["num"] in vistos:
                continue
            cams = [LADO[f] for f in p["faces"]]
            cel = np.argwhere(_mask_ret(p["x"], p["y"], p["w"], p["h"], 0.0))
            # O pad dispensa escape se o plano encosta nele DE FATO: uma
            # célula de plano folgado a menos de 0,4 mm do cobre do pad. O
            # teste anterior perguntava se o próprio pad estava no alcance, e
            # isso é sempre verdade — o pad é cobre de GND, e ele se enxerga.
            # É a diferença entre "o plano chega aqui" e "isto tem o mesmo
            # nome do plano". Um AD0 nessa segunda situação fica no ar, e o
            # endereço I2C do sensor passa a ser indefinido.
            # 0,15 mm, não 0,4: com ligação sólida o plano avança até o pad,
            # então "o plano chega" quer dizer ENCOSTA. Plano folgado a 0,4 mm
            # ainda pode estar do outro lado de um gargalo que o preenchimento
            # não atravessa — foi o que deixou o pad 18 ilhado.
            # Em passo fino o escape é INCONDICIONAL, mesmo que o plano
            # encoste no pad agora: "agora" é a placa vazia, e as pistas de
            # sinal roteadas em seguida cercam o pad sem passar por cima dele.
            # Um pad de GND que perde o plano depois não dá sinal nenhum — e
            # no caso do AD0 o preço é o endereço I2C do sensor ficar
            # indefinido, com o WHO_AM_I falhando de forma intermitente.
            perto = _dilata(_mask_ret(p["x"], p["y"], p["w"], p["h"], 0.0)[None],
                            int(math.ceil(0.15 / PASSO)))[0]
            if not fino and any(bool(np.any(alvo[c] & perto)) for c in cams):
                continue
            passavel = (_G["dono"] == 0) | (_G["dono"] == nid)
            via_ok = _erode(passavel[0] & passavel[1],
                            int(math.ceil((VIA_D / 2 + FOLGA + LARGURA / 2) / PASSO)))
            i, j = _ij(p["x"], p["y"])
            cam = None
            for c in cams:
                if passavel[c, i, j]:
                    cam = _astar_conjunto(passavel, via_ok, (c, i, j), alcance)
                    if cam:
                        break
            if not cam:
                falhas.append(f"{ref}.{p['num']}")
                continue
            segs, vs = _segmentos(cam)
            for (x1, y1, x2, y2, l) in segs:
                pistas.append((x1, y1, x2, y2, CAMADA[l], LARGURA, nid))
                _carimba(_mask_seg(x1, y1, x2, y2, INFLA + LARGURA / 2), (l,), nid)
                _G["gnd"][l] |= _mask_seg(x1, y1, x2, y2, LARGURA / 2)
            for (vx, vy) in vs:
                vias.append((vx, vy, nid))
                _carimba(_mask_ret(vx, vy, 0.0, 0.0, VIA_D / 2 + INFLA), (0, 1), nid)
                _m = _mask_ret(vx, vy, 0.0, 0.0, VIA_D / 2)
                _G["gnd"][0] |= _m; _G["gnd"][1] |= _m
                ponte |= _m

            # Se o escape parou num ponto de plano no limite da folga, fecha
            # com uma via. O A* para na primeira célula "alcançável", e essa
            # célula pode estar numa faixa de 0,2 mm que o preenchimento não
            # cobre — o toco vira ilha. A via leva o retorno para o plano da
            # outra face, que ali é aberto.
            fl, fi, fj = cam[-1]
            if not _gnd_ok(margem=0.35)[fl, fi, fj] and via_ok[fi, fj]:
                fx, fy = _xy(fi, fj)
                vias.append((fx, fy, nid))
                _carimba(_mask_ret(fx, fy, 0.0, 0.0, VIA_D / 2 + INFLA), (0, 1), nid)
                _m = _mask_ret(fx, fy, 0.0, 0.0, VIA_D / 2)
                _G["gnd"][0] |= _m; _G["gnd"][1] |= _m
                ponte |= _m

            feitos.append(f"{ref}.{p['num']}")
            vistos.add(p["num"])
            ok = _gnd_ok(margem=0.25)
            alcance = _alcance(ok | _G["gnd"], _anel_semente(ok), ponte)
            alvo = alcance & _gnd_ok(margem=0.35)
    return feitos, falhas


def costura_e_terra(net, posicoes, netnum, pads_abs, centro, contorno, nid,
                    pistas, vias, passo_mm=2.4):
    """Coloca as vias de costura e dá saída aos pads de GND que o plano não pega.

    Devolve (vias_de_costura, pads_ilhados_resolvidos, pads_ilhados_sem_saida).
    """
    CXc, CYc = centro
    fora_via = _fora_do_contorno(FOLGA_BORDA + VIA_D / 2)
    ok = _gnd_ok(nid)
    # Uma via precisa de mais espaço que o plano: VIA_D/2 + FOLGA a partir do
    # cobre alheio, contra ESP_ZONA/2 + FOLGA_ZONA do plano. Usar a folga do
    # plano punha vias a 0,10 mm de pad, e o DRC acusava.
    # +1 célula de arredondamento: a grade discretiza a distância, e um via
    # a exatamente 5 células de um pad NC do WROOM caía em 0,13 mm no DRC.
    r_via = int(math.ceil((VIA_D / 2 + FOLGA) / PASSO)) + 1
    cabe_via = ~_dilata(_G["cobre"] | _G["gnd_alheio"], r_via)
    bons = ok[0] & ok[1] & cabe_via[0] & cabe_via[1]

    # --- costura onde o plano existe DOS DOIS lados ---
    costura, sementes = [], []
    n = int(math.ceil(passo_mm / PASSO))
    for i in range(0, _G["N"], n):
        for j in range(0, _G["N"], n):
            if not bons[i, j]:
                continue
            x, y = _xy(i, j)
            if fora_via[i, j]:
                continue
            costura.append((x, y))
            sementes += [(0, i, j), (1, i, j)]
            _carimba(_mask_ret(x, y, 0.0, 0.0, VIA_D / 2 + INFLA), (0, 1), nid)
            _m = _mask_ret(x, y, 0.0, 0.0, VIA_D / 2)
            _G["gnd"][0] |= _m; _G["gnd"][1] |= _m

    # --- pontes entre camadas: todo furo metalizado que já é GND ---
    ponte = np.zeros((_G["N"], _G["N"]), dtype=bool)
    for (x, y) in costura:
        ponte |= _mask_ret(x, y, 0.0, 0.0, VIA_D / 2)
    for (vx, vy, vnid) in vias:
        if vnid == nid:
            ponte |= _mask_ret(vx, vy, 0.0, 0.0, VIA_D / 2)
    LADO = {"F": 0, "B": 1}
    for ref, (_fp, _val, mapa) in net.items():
        if ref not in posicoes or not mapa:
            continue
        for p in pads_abs(ref):
            if mapa.get(p["num"]) == "GND" and len(p["faces"]) == 2:
                ponte |= _mask_ret(p["x"], p["y"], p["w"], p["h"], 0.0)

    # --- quem o plano alcança ---
    ok = _gnd_ok(nid)
    alcance = _alcance(ok | _G["gnd"], sementes, ponte)
    orfaos = []
    for ref, (_fp, _val, mapa) in net.items():
        if ref not in posicoes or not mapa:
            continue
        _x, _y, _r, lado = posicoes[ref]
        for p in pads_abs(ref):
            if mapa.get(p["num"]) != "GND":
                continue
            cams = [LADO[f] for f in p["faces"]]
            cel = _pad_celulas(p["x"], p["y"], p["w"], p["h"])
            if any(alcance[c, i, j] for c in cams for i, j in cel):
                continue
            orfaos.append((ref, p["num"], p["x"], p["y"], cams, cel))

    # Uma via de costura que o plano não alcança dos dois lados não costura
    # nada — vira um furo solto que o DRC acusa como item desconectado.
    costura = [(x, y) for (x, y) in costura
               if alcance[0, _ij(x, y)[0], _ij(x, y)[1]]
               and alcance[1, _ij(x, y)[0], _ij(x, y)[1]]]

    # ------------------------------------------------------------------
    # Grupos do plano que ficaram sem ligação
    # ------------------------------------------------------------------
    # Preenchido, o plano vira vários polígonos. Isso é normal: pads e pistas
    # o recortam. O que não é normal é um grupo desses tocar pads de GND e não
    # ter caminho até o resto — aí a net GND está partida, e o DRC acusa como
    # "zona a zona". Via de costura em grade não resolve: o grupo pode ser
    # pequeno demais para a grade cair dentro dele.
    #
    # Aqui cada grupo é encontrado por busca e ligado explicitamente: via para
    # a outra face onde o plano já chega, ou pista curta se não couber via.
    grupos_ligados, grupos_soltos = 0, 0
    for _ in range(16):
        ok = _gnd_ok(nid)
        base = ok | _G["gnd"]
        resto = base & ~alcance & _dilata(_G["gnd"], 1)   # só o que toca cobre de GND
        if not resto.any():
            break
        l0, i0, j0 = [int(v) for v in np.argwhere(resto)[0]]
        comp = _alcance(base, [(l0, i0, j0)], ponte)
        comp &= ~alcance

        feito = False
        # 1) via: célula do grupo cuja OUTRA face já está no plano principal
        cabe = ~_dilata(_G["cobre"], int(math.ceil((VIA_D / 2 + FOLGA) / PASSO)) + 1)
        for (l, i, j) in np.argwhere(comp):
            l, i, j = int(l), int(i), int(j)
            if not (alcance[1 - l, i, j] and cabe[0, i, j] and cabe[1, i, j]):
                continue
            vx, vy = _xy(i, j)
            vias.append((vx, vy, nid))
            _carimba(_mask_ret(vx, vy, 0.0, 0.0, VIA_D / 2 + INFLA), (0, 1), nid)
            m = _mask_ret(vx, vy, 0.0, 0.0, VIA_D / 2)
            _G["gnd"][0] |= m; _G["gnd"][1] |= m
            ponte |= m
            feito = True
            break
        # 2) pista curta até o plano principal
        if not feito:
            passavel = (_G["dono"] == 0) | (_G["dono"] == nid)
            via_ok = _erode(passavel[0] & passavel[1],
                            int(math.ceil((VIA_D / 2 + FOLGA + LARGURA / 2) / PASSO)))
            cam = _astar_conjunto(passavel, via_ok, (l0, i0, j0), alcance)
            if cam:
                segs, vs = _segmentos(cam)
                for (x1, y1, x2, y2, l) in segs:
                    pistas.append((x1, y1, x2, y2, CAMADA[l], LARGURA, nid))
                    _carimba(_mask_seg(x1, y1, x2, y2, INFLA + LARGURA / 2), (l,), nid)
                    _G["gnd"][l] |= _mask_seg(x1, y1, x2, y2, LARGURA / 2)
                for (vx, vy) in vs:
                    vias.append((vx, vy, nid))
                    _carimba(_mask_ret(vx, vy, 0.0, 0.0, VIA_D / 2 + INFLA), (0, 1), nid)
                    m = _mask_ret(vx, vy, 0.0, 0.0, VIA_D / 2)
                    _G["gnd"][0] |= m; _G["gnd"][1] |= m
                    ponte |= m
                feito = True

        if feito:
            grupos_ligados += 1
            alcance = _alcance(_gnd_ok(nid) | _G["gnd"], sementes, ponte)
        else:
            # sem saída: marca como visto para não repetir o mesmo grupo
            grupos_soltos += 1
            alcance |= comp
    _G["grupos"] = (grupos_ligados, grupos_soltos)

    resolvidos, sem_saida = [], []
    for (ref, num, x, y, cams, cel) in orfaos:
        passavel = (_G["dono"] == 0) | (_G["dono"] == nid)
        via_ok = _erode(passavel[0] & passavel[1],
                        int(math.ceil((VIA_D / 2 + FOLGA + LARGURA / 2) / PASSO)))
        i, j = _ij(x, y)
        cam = None
        for c in cams:
            if passavel[c, i, j]:
                cam = _astar_conjunto(passavel, via_ok, (c, i, j), alcance)
                if cam:
                    break
        if not cam:
            sem_saida.append(f"{ref}.{num}")
            continue
        segs, vs = _segmentos(cam)
        for (x1, y1, x2, y2, l) in segs:
            pistas.append((x1, y1, x2, y2, CAMADA[l], LARGURA, nid))
            _carimba(_mask_seg(x1, y1, x2, y2, INFLA + LARGURA / 2), (l,), nid)
        for (vx, vy) in vs:
            vias.append((vx, vy, nid))
            _carimba(_mask_ret(vx, vy, 0.0, 0.0, VIA_D / 2 + INFLA), (0, 1), nid)
        resolvidos.append(f"{ref}.{num}")
        for (vx, vy) in vs:
            ponte |= _mask_ret(vx, vy, 0.0, 0.0, VIA_D / 2)
        alcance = _alcance(_gnd_ok(nid) | _G["gnd"], sementes, ponte)

    return costura, resolvidos, sem_saida


def ponto_livre(x, y, r):
    """Cabe uma via de costura de GND aqui, sem tocar em nada de outra net?"""
    i, j = _ij(x, y)
    n = int(math.ceil(r / PASSO))
    N = _G["N"]
    if not (n <= i < N - n and n <= j < N - n):
        return False
    jan = _G["dono"][:, i - n:i + n + 1, j - n:j + n + 1]
    return bool(np.all(jan == 0))
