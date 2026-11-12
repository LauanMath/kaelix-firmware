#include <unity.h>
#include <cmath>
#include <limits>
#include "../../src/sensors/vibration.cpp"

void setUp() {}
void tearDown() {}

void test_frozen_window_does_not_publish_features() {
    float samples[512]{};
    kaelix::sensors::VibrationFeatures features{1, 2, 3, 4};
    const auto status = kaelix::sensors::vibration_features_from_samples(samples, 512, 1000, &features);
    TEST_ASSERT_EQUAL(kaelix::Status::SensorStuck, status);
    TEST_ASSERT_EQUAL_FLOAT(1, features.rms);
    TEST_ASSERT_EQUAL_FLOAT(4, features.dominant_freq_hz);
}

void test_nonfinite_window_does_not_publish_features() {
    float samples[512]{};
    samples[200] = std::numeric_limits<float>::quiet_NaN();
    kaelix::sensors::VibrationFeatures features{1, 2, 3, 4};
    const auto status = kaelix::sensors::vibration_features_from_samples(samples, 512, 1000, &features);
    TEST_ASSERT_EQUAL(kaelix::Status::NotFinite, status);
    TEST_ASSERT_EQUAL_FLOAT(1, features.rms);
    TEST_ASSERT_EQUAL_FLOAT(4, features.dominant_freq_hz);
}

void test_window_in_g_has_expected_rms_and_frequency() {
    float samples[512]{};
    // 32 ciclos/janela: 62,5 Hz; amplitude 0,1 g.
    for (unsigned i = 0; i < 512; ++i)
        samples[i] = 0.1f * std::sin(2.0 * 3.141592653589793 * 32 * i / 512);
    kaelix::sensors::VibrationFeatures features{};
    const auto status = kaelix::sensors::vibration_features_from_samples(samples, 512, 1000, &features);
    TEST_ASSERT_EQUAL(kaelix::Status::Ok, status);
    TEST_ASSERT_FLOAT_WITHIN(0.0001f, 0.0707107f, features.rms);
    TEST_ASSERT_FLOAT_WITHIN(0.01f, 62.5f, features.dominant_freq_hz);
    TEST_ASSERT_FLOAT_WITHIN(0.01f, 1.41421f, features.crest_factor);
}

int main() {
    UNITY_BEGIN();
    RUN_TEST(test_frozen_window_does_not_publish_features);
    RUN_TEST(test_nonfinite_window_does_not_publish_features);
    RUN_TEST(test_window_in_g_has_expected_rms_and_frequency);
    return UNITY_END();
}
