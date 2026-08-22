#include <unity.h>

#include <cstring>

#include "crc16.h"

using namespace kaelix::comms;

void setUp(void) {}
void tearDown(void) {}

void test_crc16_check_vector(void) {
    // Vetor de conferência padrão do CRC-16/CCITT-FALSE.
    const char* s = "123456789";
    TEST_ASSERT_EQUAL_HEX16(0x29B1, crc16_ccitt(reinterpret_cast<const uint8_t*>(s), 9));
}

void test_crc16_empty_is_initial_value(void) {
    TEST_ASSERT_EQUAL_HEX16(0xFFFF, crc16_ccitt(nullptr, 0));
}

void test_crc16_detects_single_bit_flip(void) {
    uint8_t a[8] = {0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08};
    uint8_t b[8];
    std::memcpy(b, a, sizeof(a));
    b[3] ^= 0x01; // um bit

    TEST_ASSERT_NOT_EQUAL(crc16_ccitt(a, 8), crc16_ccitt(b, 8));
}

void test_crc16_detects_byte_swap(void) {
    // Troca de ordem: um checksum por soma não pegaria isso.
    uint8_t a[4] = {0xDE, 0xAD, 0xBE, 0xEF};
    uint8_t b[4] = {0xAD, 0xDE, 0xBE, 0xEF};

    TEST_ASSERT_NOT_EQUAL(crc16_ccitt(a, 4), crc16_ccitt(b, 4));
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_crc16_check_vector);
    RUN_TEST(test_crc16_empty_is_initial_value);
    RUN_TEST(test_crc16_detects_single_bit_flip);
    RUN_TEST(test_crc16_detects_byte_swap);
    return UNITY_END();
}
