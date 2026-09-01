"""Simulador do enlace LoRa: gera o tráfego que o gateway veria em campo.

Existe porque o rádio nunca transmitiu. Sem hardware, a única forma de
exercitar a cadeia pacote -> ar -> gateway é injetar os mesmos efeitos
que o meio impõe: colisão, perda e corrupção de bit. O que este módulo
NÃO simula é propagação — alcance e margem de enlace dependem do
ambiente e só saem de medição em campo.
"""

import math
import random
from dataclasses import dataclass

from .packet import Leitura, codificar

CICLO_S = 600.0
AIRTIME_S = 0.185      # SF9, BW 125 kHz, CR 4/5, 20 bytes
JITTER_MAX_S = 60      # espelha kpower::JITTER_MAX_SECONDS


@dataclass
class Dispositivo:
    device_id: int
    p_anomalia: float = 0.0     # fração de ciclos em que decide "anômalo"
    rms_base: float = 0.19


def _instante(dev: Dispositivo, ciclo: int, com_jitter: bool) -> float:
    """Quando este dispositivo transmite neste ciclo.

    Sem jitter, todos transmitem no mesmo instante — que é o que acontece
    quando são energizados juntos numa instalação. É esse o caso que o
    deslocamento por device_id resolve.
    """
    base = ciclo * CICLO_S
    if not com_jitter:
        return base
    return base + (dev.device_id + ciclo) % JITTER_MAX_S


def simular(dispositivos: list[Dispositivo], ciclos: int, *, com_jitter: bool = True,
            p_perda: float = 0.0, p_corrupcao: float = 0.0, seed: int = 42):
    """Gera (instante, quadro) ordenado por tempo, aplicando colisão,
    perda e corrupção. Devolve também a contabilidade do que foi
    descartado no ar, para separar perda de meio de erro de gateway."""
    rng = random.Random(seed)
    eventos = []
    for ciclo in range(ciclos):
        for dev in dispositivos:
            anom = rng.random() < dev.p_anomalia
            leitura = Leitura(
                device_id=dev.device_id, boot_count=ciclo + 1,
                status=1 if anom else 0,
                rms=dev.rms_base * (3.5 if anom else 1.0) + rng.gauss(0, 0.01),
                temperature_c=42.0 + rng.gauss(0, 1.5),
            )
            eventos.append([_instante(dev, ciclo, com_jitter), codificar(leitura), dev.device_id])

    eventos.sort(key=lambda e: e[0])

    # Colisão: dois quadros que se sobrepõem no ar destroem um ao outro.
    # A janela vulnerável é o tempo no ar, não um instante.
    colididos = set()
    for i in range(len(eventos)):
        for j in range(i + 1, len(eventos)):
            if eventos[j][0] - eventos[i][0] >= AIRTIME_S:
                break
            colididos.add(i)
            colididos.add(j)

    saida, cont = [], {"colisao": 0, "perda": 0, "corrupcao": 0, "entregues": 0}
    for i, (t, quadro, _) in enumerate(eventos):
        if i in colididos:
            cont["colisao"] += 1
            continue
        if rng.random() < p_perda:
            cont["perda"] += 1
            continue
        if rng.random() < p_corrupcao:
            b = bytearray(quadro)
            b[rng.randrange(len(b))] ^= 1 << rng.randrange(8)
            quadro = bytes(b)
            cont["corrupcao"] += 1
        cont["entregues"] += 1
        saida.append((t, quadro))
    return saida, cont
