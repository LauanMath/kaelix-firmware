#include <unity.h>

#include <cmath>

#include "thermistor.h"

using namespace kaelix::sensors;

void setUp(void) {}
void tearDown(void) {}

void test_celsius_at_nominal_resistance(void) {
    // R = R_nominal -> ln(1) = 0 -> T = T_nominal exatamente.
    float t = ntc_resistance_to_celsius(10000.0f, 10000.0f, 3950.0f, 25.0f);
    TEST_ASSERT_FLOAT_WITHIN(0.001f, 25.0f, t);
}

void test_celsius_decreases_as_resistance_increases(void) {
    // NTC: resistência cai quando a temperatura sobe (coeficiente negativo).
    float t_low_r = ntc_resistance_to_celsius(5000.0f, 10000.0f, 3950.0f, 25.0f);
    float t_nominal = ntc_resistance_to_celsius(10000.0f, 10000.0f, 3950.0f, 25.0f);
    float t_high_r = ntc_resistance_to_celsius(20000.0f, 10000.0f, 3950.0f, 25.0f);
    TEST_ASSERT_TRUE(t_low_r > t_nominal);
    TEST_ASSERT_TRUE(t_nominal > t_high_r);
}

void test_celsius_sanity_bounds(void) {
    // Resistência bem abaixo da nominal -> temperatura bem acima de 25°C.
    float t_hot = ntc_resistance_to_celsius(1000.0f, 10000.0f, 3950.0f, 25.0f);
    TEST_ASSERT_TRUE(t_hot > 70.0f);

    // Resistência bem acima da nominal -> temperatura bem abaixo de 25°C.
    float t_cold = ntc_resistance_to_celsius(50000.0f, 10000.0f, 3950.0f, 25.0f);
    TEST_ASSERT_TRUE(t_cold < 5.0f);
}

void test_resistance_from_adc_midscale(void) {
    // adc_raw/adc_max = 0.5 -> R_ntc = R_fixed * 0.5/0.5 = R_fixed.
    float r = ntc_resistance_from_adc(2000, 4000, 10000.0f);
    TEST_ASSERT_FLOAT_WITHIN(1.0f, 10000.0f, r);
}

void test_resistance_from_adc_quarter_scale(void) {
    // ratio = 0.25 -> R_ntc = R_fixed * 0.25/0.75 = R_fixed/3.
    float r = ntc_resistance_from_adc(1000, 4000, 10000.0f);
    TEST_ASSERT_FLOAT_WITHIN(1.0f, 10000.0f / 3.0f, r);
}

void test_resistance_from_adc_edges_stay_finite(void) {
    float r_low = ntc_resistance_from_adc(0, 4095, 10000.0f);
    float r_high = ntc_resistance_from_adc(4095, 4095, 10000.0f);
    TEST_ASSERT_TRUE(std::isfinite(r_low) && r_low > 0.0f);
    TEST_ASSERT_TRUE(std::isfinite(r_high) && r_high > 0.0f);
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_celsius_at_nominal_resistance);
    RUN_TEST(test_celsius_decreases_as_resistance_increases);
    RUN_TEST(test_celsius_sanity_bounds);
    RUN_TEST(test_resistance_from_adc_midscale);
    RUN_TEST(test_resistance_from_adc_quarter_scale);
    RUN_TEST(test_resistance_from_adc_edges_stay_finite);
    return UNITY_END();
}
