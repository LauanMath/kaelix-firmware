"""Decodificação do pacote LoRa do Kaelix.

Espelha `struct LoraPacket` de src/comms/lora.h. O acoplamento é
deliberado e é o ponto do módulo: se o layout mudar de um lado e não do
outro, o gateway passa a ler lixo com CRC válido.

Duas defesas contra essa divergência:

1. `PACKET_VERSION` — o emissor carimba a versão no primeiro byte, e o
   decodificador recusa o que não conhece, em vez de interpretar campos
   deslocados.
2. `tests/test_paridade_crc.py` compila o CRC de lib/crc16 com g++ e
   compara contra esta implementação, do mesmo modo que o pipeline de
   treino faz com o Isolation Forest. Um CRC que diverge é pior que um
   ausente: valida pacote corrompido e rejeita pacote íntegro.
"""

import struct
from dataclasses import dataclass

PACKET_VERSION = 1
PACKET_SIZE = 20
# little-endian, sem alinhamento: espelha __attribute__((packed)) no ESP32-S3.
_LAYOUT = "<BIIBffH"

assert struct.calcsize(_LAYOUT) == PACKET_SIZE, "layout divergiu de src/comms/lora.h"


class PacketError(Exception):
    """Motivo pelo qual um quadro não virou leitura. Nunca silencioso."""


def crc16_ccitt(data: bytes) -> int:
    """CRC-16/CCITT-FALSE. Espelha lib/crc16/crc16.cpp."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


@dataclass(frozen=True)
class Leitura:
    device_id: int
    boot_count: int
    status: int          # 0 = normal, 1 = anômalo
    rms: float
    temperature_c: float

    @property
    def anomalo(self) -> bool:
        return self.status == 1


def decodificar(quadro: bytes) -> Leitura:
    """Bytes do rádio -> leitura. Levanta PacketError com o motivo.

    A ordem das verificações importa: tamanho antes de desempacotar,
    versão antes de confiar nos offsets, CRC antes de confiar no valor.
    """
    if len(quadro) != PACKET_SIZE:
        raise PacketError(f"tamanho {len(quadro)} != {PACKET_SIZE}")

    version, device_id, boot_count, status, rms, temp, crc = struct.unpack(_LAYOUT, quadro)

    if version != PACKET_VERSION:
        raise PacketError(
            f"versão {version} desconhecida (esperada {PACKET_VERSION}) — "
            "não interprete os campos seguintes"
        )

    esperado = crc16_ccitt(quadro[:PACKET_SIZE - 2])
    if crc != esperado:
        raise PacketError(f"CRC 0x{crc:04X} != 0x{esperado:04X}")

    if status not in (0, 1):
        raise PacketError(f"status {status} fora do domínio")

    return Leitura(device_id, boot_count, status, rms, temp)


def codificar(leitura: Leitura) -> bytes:
    """Monta o quadro como o dispositivo monta. Existe para o simulador e
    para os testes: sem ele, o decodificador só seria testado contra si
    mesmo."""
    corpo = struct.pack(
        _LAYOUT[:-1], PACKET_VERSION, leitura.device_id, leitura.boot_count,
        leitura.status, leitura.rms, leitura.temperature_c,
    )
    return corpo + struct.pack("<H", crc16_ccitt(corpo))
