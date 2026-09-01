"""Paridade do CRC entre o gateway (Python) e o firmware (C++).

Mesmo método do pipeline de treino: compila a implementação de referência
com g++, roda, e compara. Um CRC divergente é pior que nenhum — valida
quadro corrompido e rejeita quadro íntegro, e nada no sistema acusa.
"""

import random
import subprocess
from pathlib import Path

import pytest

from kaelix_gateway.packet import crc16_ccitt

# gateway/ está sob experiments/; lib/ fica na raiz do repositório
RAIZ = Path(__file__).resolve().parents[3]
LIB_CRC = RAIZ / "lib" / "crc16"
# crc16.h inclui kaelix_status.h; fora do PlatformIO o caminho vai à mão.
LIB_STATUS = RAIZ / "lib" / "kaelix_status"

MAIN = """
#include <cstdio>
#include <cstdlib>
#include "crc16.h"
int main() {
    unsigned char buf[64]; int n;
    while (scanf("%d", &n) == 1) {
        for (int i = 0; i < n; ++i) { int v; if (scanf("%d", &v) != 1) return 1; buf[i] = (unsigned char)v; }
        printf("%u\\n", (unsigned)kaelix::comms::crc16_ccitt(buf, (size_t)n));
    }
    return 0;
}
"""


@pytest.mark.skipif(not (LIB_CRC / "crc16.cpp").exists(), reason="lib/crc16 ausente")
def test_crc_python_bate_com_cpp(tmp_path):
    src = tmp_path / "main.cpp"
    src.write_text(MAIN)
    exe = tmp_path / "a.out"
    subprocess.run(["g++", "-std=c++17", "-O2", "-I", str(LIB_CRC),
                    "-I", str(LIB_STATUS), str(src),
                    str(LIB_CRC / "crc16.cpp"), "-o", str(exe)], check=True)

    rng = random.Random(7)
    casos = [b"123456789", b"", bytes(20), bytes(range(20))]
    casos += [bytes(rng.randrange(256) for _ in range(rng.randrange(1, 40))) for _ in range(200)]

    entrada = "\n".join(f"{len(c)} " + " ".join(str(b) for b in c) for c in casos)
    saida = subprocess.run([str(exe)], input=entrada, capture_output=True, text=True,
                           check=True).stdout.split()

    assert len(saida) == len(casos)
    for caso, cpp in zip(casos, saida):
        assert crc16_ccitt(caso) == int(cpp), f"divergência em {caso!r}"


def test_vetor_de_conferencia_padrao():
    assert crc16_ccitt(b"123456789") == 0x29B1
