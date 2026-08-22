#pragma once

#include <cstddef>
#include <cstdint>

// CRC-16/CCITT-FALSE — polinômio 0x1021, inicial 0xFFFF, sem reflexão.
// Função pura, sem dependência de Arduino: um pacote corrompido no ar
// que chegue ao gateway como leitura válida é pior que um pacote
// perdido, então a verificação precisa ser testável no host.
//
// Vetor de conferência padrão: crc16_ccitt("123456789", 9) == 0x29B1.

namespace kaelix::comms {

uint16_t crc16_ccitt(const uint8_t* data, size_t n);

} // namespace kaelix::comms
