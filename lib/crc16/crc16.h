#pragma once

#include <cstddef>
#include <cstdint>

#include "kaelix_status.h"

// CRC-16/CCITT-FALSE — polinômio 0x1021, inicial 0xFFFF, sem reflexão.
// Função pura, sem dependência de Arduino: um pacote corrompido no ar
// que chegue ao gateway como leitura válida é pior que um pacote
// perdido, então a verificação precisa ser testável no host.
//
// Vetor de conferência padrão: crc16_ccitt("123456789", 9) == 0x29B1.

namespace kaelix::comms {

// Cota superior de comprimento. Não é um limite arbitrário: 255 é o
// máximo que cabe no campo de tamanho de um pacote LoRa do SX1278, então
// nenhuma entrada legítima deste projeto passa disso.
//
// A cota existe pelo lado do GATEWAY, não pelo do dispositivo. Aqui o
// chamador é sempre `sizeof(LoraPacket)`, uma constante; do outro lado o
// `n` virá de um campo de tamanho lido do ar, e um valor corrompido faria
// o laço percorrer megabytes de memória alheia antes de "terminar". Com a
// cota, o laço tem limite máximo provável em tempo de compilação:
// 255 * 8 = 2040 iterações, o que dá ao ciclo um WCET fechado.
inline constexpr size_t CRC16_MAX_LEN_BYTES = 255U;

// Faixa válida de operação:
//   data   não-nulo quando n > 0; pode ser nulo quando n == 0
//   n      [0 .. CRC16_MAX_LEN_BYTES]
//   retorno o CRC, ou 0x0000 se um contrato foi violado
//
// Sobre o valor de erro 0x0000: ele é um CRC legítimo para algumas
// entradas, portanto NÃO serve como sentinela confiável. Isso é aceito de
// propósito — as duas condições que o produzem (ponteiro nulo com n > 0,
// n acima da cota) são violações de contrato, e violação de contrato
// aborta em build de desenvolvimento (ver §5 da arquitetura). Em produção
// o efeito prático é um CRC que não confere, que é o desfecho seguro:
// o pacote é descartado em vez de aceito.
//
// Precisão/garantia de detecção: CCITT-FALSE detecta 100% dos erros de
// 1 e 2 bits, 100% das rajadas de até 16 bits e todos os erros de número
// ímpar de bits; a probabilidade residual de uma rajada mais longa passar
// é 2^-16 (~1,5e-5). Trocas de ordem de bytes são detectadas — é a razão
// de não ser uma soma simples.
[[nodiscard]] uint16_t crc16_ccitt(const uint8_t* data, size_t n);

} // namespace kaelix::comms
