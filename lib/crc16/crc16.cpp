#include "crc16.h"

namespace kaelix::comms {

uint16_t crc16_ccitt(const uint8_t* data, size_t n) {
    // `n == 0` com ponteiro nulo é legítimo e devolve o valor inicial:
    // é o caso de "nada a checar", usado pelos testes e pelo gateway ao
    // receber um pacote sem corpo. O que não pode existir é n > 0 sobre
    // ponteiro nulo — dereferência direta.
    KAELIX_REQUIRE_VALUE(data != nullptr || n == 0U, kaelix::Status::NullPointer,
                         static_cast<uint16_t>(0U));
    KAELIX_REQUIRE_VALUE(n <= CRC16_MAX_LEN_BYTES, kaelix::Status::LengthOutOfRange,
                         static_cast<uint16_t>(0U));

    uint16_t crc = 0xFFFFU;
    for (size_t i = 0U; i < n; ++i) {
        // Conversões explícitas: `crc ^= data[i] << 8` promove a int e
        // reatribui int a uint16_t implicitamente (MISRA C++ 2008 5-0-6).
        // O valor calculado é idêntico; o que muda é que a intenção passa
        // a estar escrita.
        crc = static_cast<uint16_t>(crc ^ static_cast<uint16_t>(
                                              static_cast<uint32_t>(data[i]) << 8U));
        for (int bit = 0; bit < 8; ++bit) {
            // `(crc & 0x8000)` como condição é int, não bool
            // (MISRA C++ 2008 5-0-13): a comparação explícita deixa claro
            // que se testa um bit, não um valor.
            // O deslocamento passa por uint32_t de propósito: `crc << 1`
            // promoveria uint16_t a `int` com sinal, e o resultado seria
            // reconvertido implicitamente (MISRA 5-0-6, e -Wsign-conversion
            // aponta). O número calculado é o mesmo; o que muda é não
            // depender mais de promoção implícita para um tipo com sinal.
            const uint32_t shifted = static_cast<uint32_t>(crc) << 1U;
            crc = ((crc & 0x8000U) != 0U) ? static_cast<uint16_t>(shifted ^ 0x1021U)
                                          : static_cast<uint16_t>(shifted);
        }
    }
    return crc;
}

} // namespace kaelix::comms
