#include <unity.h>
#include <cmath>
#include <limits>
#include "kaelix_protocol.h"

using namespace kaelix::protocol;

void setUp() {}
void tearDown() {}

namespace {
Telemetry sample_telemetry() {
    Telemetry t{};
    t.device_id = 0x311D0470U;
    t.sequence = 48U;
    t.state = 2U;
    t.rms_z = 0.0031f;
    t.temperature_c = std::numeric_limits<float>::quiet_NaN();
    t.burst_profile = 2U;
    return t;
}
DeviceConfig routine_config() {
    DeviceConfig c{};
    c.version = 7U;
    c.routine_count = 1U;
    c.routine[0].days = 0x3EU; // segunda a sexta
    c.routine[0].start_min = 8U * 60U;
    c.routine[0].end_min = 18U * 60U;
    return c;
}
// 2026-11-02 é segunda-feira; 12:00 em UTC são 09:00 em UTC-3.
constexpr int64_t MONDAY_NOON_UTC = 1793620800;
}

void test_telemetry_roundtrip_and_nan_is_preserved() {
    Telemetry t = sample_telemetry();
    seal_telemetry(&t);
    Telemetry out{};
    TEST_ASSERT_TRUE(decode_telemetry(reinterpret_cast<const uint8_t*>(&t), sizeof(t), &out));
    TEST_ASSERT_EQUAL_UINT32(48U, out.sequence);
    TEST_ASSERT_TRUE(std::isnan(out.temperature_c));
}

void test_telemetry_rejects_bit_flip_length_and_wrong_type() {
    Telemetry t = sample_telemetry();
    seal_telemetry(&t);
    Telemetry out{};
    uint8_t bytes[sizeof(t)];
    std::memcpy(bytes, &t, sizeof(t));
    bytes[20] ^= 1U;
    TEST_ASSERT_FALSE(decode_telemetry(bytes, sizeof(bytes), &out));
    bytes[20] ^= 1U;
    TEST_ASSERT_FALSE(decode_telemetry(bytes, sizeof(bytes) - 1U, &out));
    bytes[1] = 2U;
    seal(bytes, sizeof(bytes));
    TEST_ASSERT_FALSE(decode_telemetry(bytes, sizeof(bytes), &out));
}

void test_telemetry_rejects_infinite_measurement() {
    Telemetry t = sample_telemetry();
    t.kurtosis = std::numeric_limits<float>::infinity();
    seal_telemetry(&t);
    Telemetry out{};
    TEST_ASSERT_FALSE(decode_telemetry(reinterpret_cast<const uint8_t*>(&t), sizeof(t), &out));
}

void test_config_roundtrip_with_full_routine() {
    DeviceConfig c{};
    c.version = 9U;
    c.cycle_interval_s = 60U;
    c.window_samples = 4096U;
    c.channels = 4U;
    c.tx_power_dbm = 17;
    c.burst_profile = 3U;
    c.link_loss_s = 86400U;
    c.tz_offset_min = -720;
    c.routine_count = MAX_ROUTINE;
    for (uint8_t i = 0U; i < MAX_ROUTINE; ++i) { c.routine[i].days = 1U; c.routine[i].start_min = i; c.routine[i].end_min = 1440U; }
    uint8_t bytes[CONFIG_MAX_BYTES];
    const size_t n = encode_config(c, bytes, sizeof(bytes));
    TEST_ASSERT_EQUAL(CONFIG_MAX_BYTES, n);
    DeviceConfig out{};
    TEST_ASSERT_TRUE(decode_config(bytes, n, &out));
    TEST_ASSERT_EQUAL_UINT16(9U, out.version);
    TEST_ASSERT_EQUAL_UINT16(4096U, out.window_samples);
    TEST_ASSERT_EQUAL_INT8(17, out.tx_power_dbm);
    TEST_ASSERT_EQUAL_UINT32(86400U, out.link_loss_s);
    TEST_ASSERT_EQUAL_INT16(-720, out.tz_offset_min);
    TEST_ASSERT_EQUAL_UINT16(5U, out.routine[5].start_min);
}

void test_factory_config_is_valid() {
    TEST_ASSERT_TRUE(config_valid(DeviceConfig{}));
}

void test_config_validation_rejects_each_out_of_range_field() {
    DeviceConfig c{};
    c = DeviceConfig{}; c.cycle_interval_s = 0U; TEST_ASSERT_FALSE(config_valid(c));
    c = DeviceConfig{}; c.cycle_interval_s = 3601U; TEST_ASSERT_FALSE(config_valid(c));
    c = DeviceConfig{}; c.window_samples = 500U; TEST_ASSERT_FALSE(config_valid(c));
    c = DeviceConfig{}; c.channels = 3U; TEST_ASSERT_FALSE(config_valid(c)); // sem az
    c = DeviceConfig{}; c.accel_range = 4U; TEST_ASSERT_FALSE(config_valid(c));
    c = DeviceConfig{}; c.dlpf = 7U; TEST_ASSERT_FALSE(config_valid(c));
    c = DeviceConfig{}; c.tx_power_dbm = 1; TEST_ASSERT_FALSE(config_valid(c));
    c = DeviceConfig{}; c.tx_power_dbm = 18; TEST_ASSERT_FALSE(config_valid(c));
    c = DeviceConfig{}; c.burst_profile = 4U; TEST_ASSERT_FALSE(config_valid(c));
    c = DeviceConfig{}; c.link_loss_s = 59U; TEST_ASSERT_FALSE(config_valid(c));
    c = DeviceConfig{}; c.checkin_interval_s = 59U; TEST_ASSERT_FALSE(config_valid(c));
    c = DeviceConfig{}; c.tz_offset_min = 841; TEST_ASSERT_FALSE(config_valid(c));
    c = DeviceConfig{}; c.routine_count = 7U; TEST_ASSERT_FALSE(config_valid(c));
    c = routine_config(); c.routine[0].end_min = c.routine[0].start_min; TEST_ASSERT_FALSE(config_valid(c));
    c = routine_config(); c.routine[0].days = 0U; TEST_ASSERT_FALSE(config_valid(c));
}

void test_reply_carries_config_and_command() {
    DeviceConfig c = routine_config();
    uint8_t frame[REPLY_MAX_FRAME];
    const size_t n = encode_reply(0x311D0470U, 48U, 1793620800U, true, &c, Command::CaptureNow, 5U, frame, sizeof(frame));
    TEST_ASSERT_GREATER_THAN(REPLY_MIN_FRAME, n);
    Reply r{};
    TEST_ASSERT_TRUE(decode_reply(frame, n, 0x311D0470U, &r));
    TEST_ASSERT_TRUE(r.has_config);
    TEST_ASSERT_EQUAL_UINT16(7U, r.config.version);
    TEST_ASSERT_EQUAL_UINT8(static_cast<uint8_t>(Command::CaptureNow), r.header.command);
    TEST_ASSERT_EQUAL_UINT16(5U, r.header.command_seq);
    TEST_ASSERT_TRUE((r.header.flags & REPLY_BURST_GO) != 0U);
}

void test_reply_without_config_has_documented_size() {
    uint8_t frame[REPLY_MAX_FRAME];
    TEST_ASSERT_EQUAL(22U, encode_reply(1U, 2U, 3U, false, nullptr, Command::None, 0U, frame, sizeof(frame)));
}

void test_reply_for_other_device_is_ignored() {
    uint8_t frame[REPLY_MAX_FRAME];
    const size_t n = encode_reply(1U, 2U, 3U, false, nullptr, Command::None, 0U, frame, sizeof(frame));
    Reply r{};
    TEST_ASSERT_FALSE(decode_reply(frame, n, 99U, &r));
}

void test_invalid_config_in_reply_keeps_ack_and_flags_rejection() {
    DeviceConfig c = routine_config();
    uint8_t frame[REPLY_MAX_FRAME];
    const size_t n = encode_reply(1U, 2U, 3U, false, &c, Command::None, 0U, frame, sizeof(frame));
    frame[sizeof(ReplyHeader) + 2U] = 0U; // cycle_interval_s baixo
    frame[sizeof(ReplyHeader) + 3U] = 0U;
    seal(frame, n);
    Reply r{};
    TEST_ASSERT_TRUE(decode_reply(frame, n, 1U, &r));
    TEST_ASSERT_FALSE(r.has_config);
    TEST_ASSERT_TRUE(r.config_rejected);
    TEST_ASSERT_EQUAL_UINT32(3U, r.header.utc);
}

void test_fragment_roundtrip_and_counts() {
    TEST_ASSERT_EQUAL_UINT16(26U, fragment_count(512U, 63U));
    TEST_ASSERT_EQUAL_UINT16(5U, fragment_count(512U, 4U));
    TEST_ASSERT_EQUAL_UINT16(205U, fragment_count(4096U, 63U));
    TEST_ASSERT_EQUAL_UINT32(6144U, wave_bytes(512U, 63U));
    uint8_t payload[240];
    for (size_t i = 0U; i < sizeof(payload); ++i) payload[i] = static_cast<uint8_t>(i);
    uint8_t frame[MAX_FRAME];
    const size_t n = encode_fragment(7U, 8U, 3U, 26U, payload, sizeof(payload), frame, sizeof(frame));
    TEST_ASSERT_EQUAL(254U, n);
    FragmentHeader header{};
    const uint8_t* body = nullptr;
    size_t len = 0U;
    TEST_ASSERT_TRUE(decode_fragment(frame, n, &header, &body, &len));
    TEST_ASSERT_EQUAL_UINT8(3U, header.index);
    TEST_ASSERT_EQUAL(240U, len);
    TEST_ASSERT_EQUAL_UINT8_ARRAY(payload, body, len);
    frame[100] ^= 0x10U;
    TEST_ASSERT_FALSE(decode_fragment(frame, n, &header, &body, &len));
}

void test_burst_map_covers_largest_window() {
    TEST_ASSERT_TRUE(fragment_count(MAX_WINDOW_SAMPLES, 63U) <= BURST_MAP_BYTES * 8U);
    BurstMap m{};
    m.device_id = 7U;
    m.sequence = 8U;
    bit_set(m.received, 204U);
    seal_burst_map(&m);
    BurstMap out{};
    TEST_ASSERT_TRUE(decode_burst_map(reinterpret_cast<const uint8_t*>(&m), sizeof(m), &out));
    TEST_ASSERT_TRUE(bit_get(out.received, 204U));
    TEST_ASSERT_FALSE(bit_get(out.received, 203U));
}

void test_airtime_matches_lora_formula() {
    TEST_ASSERT_UINT32_WITHIN(1U, 411U, airtime_ms(70U, 9U, 125.0f));
    TEST_ASSERT_UINT32_WITHIN(1U, 185U, airtime_ms(18U, 9U, 125.0f));
    TEST_ASSERT_UINT32_WITHIN(1U, 200U, airtime_ms(254U, 7U, 250.0f));
}

void test_routine_inside_and_outside_window() {
    const DeviceConfig c = routine_config();
    TEST_ASSERT_TRUE(routine_active(c, MONDAY_NOON_UTC)); // 09:00 local
    TEST_ASSERT_FALSE(routine_active(c, MONDAY_NOON_UTC - 2 * 3600)); // 07:00 local
    TEST_ASSERT_EQUAL_UINT32(3600U, seconds_until_active(c, MONDAY_NOON_UTC - 2 * 3600));
    TEST_ASSERT_EQUAL_UINT32(0U, seconds_until_active(c, MONDAY_NOON_UTC));
}

void test_routine_end_is_exclusive_and_skips_weekend() {
    const DeviceConfig c = routine_config();
    const int64_t monday_18h = MONDAY_NOON_UTC + 9 * 3600;
    TEST_ASSERT_FALSE(routine_active(c, monday_18h));
    TEST_ASSERT_TRUE(routine_active(c, monday_18h - 60));
    const int64_t saturday_09h = MONDAY_NOON_UTC + 5 * 86400;
    TEST_ASSERT_FALSE(routine_active(c, saturday_09h));
    TEST_ASSERT_EQUAL_UINT32(2U * 86400U - 3600U, seconds_until_active(c, saturday_09h));
}

void test_routine_crossing_midnight_uses_start_day() {
    DeviceConfig c{};
    c.routine_count = 1U;
    c.routine[0].days = 1U << 1U; // só segunda
    c.routine[0].start_min = 22U * 60U;
    c.routine[0].end_min = 2U * 60U;
    const int64_t monday_09h = MONDAY_NOON_UTC;
    TEST_ASSERT_TRUE(routine_active(c, monday_09h + 13 * 3600));  // segunda 22:00
    TEST_ASSERT_TRUE(routine_active(c, monday_09h + 16 * 3600));  // terça 01:00
    TEST_ASSERT_FALSE(routine_active(c, monday_09h + 17 * 3600)); // terça 02:00
    TEST_ASSERT_FALSE(routine_active(c, monday_09h + 40 * 3600)); // quarta 01:00
}

void test_empty_routine_is_always_active() {
    TEST_ASSERT_TRUE(routine_active(DeviceConfig{}, MONDAY_NOON_UTC));
}

void test_link_loss_reverts_tentative_then_enters_fallback_and_recovers() {
    LinkState s{};
    s.tentative = true;
    TEST_ASSERT_EQUAL(static_cast<int>(LinkAction::None), static_cast<int>(link_update(s, false, 899U, 900U)));
    TEST_ASSERT_EQUAL(static_cast<int>(LinkAction::RevertConfig), static_cast<int>(link_update(s, false, 1U, 900U)));
    TEST_ASSERT_FALSE(s.tentative);
    TEST_ASSERT_EQUAL(static_cast<int>(LinkAction::None), static_cast<int>(link_update(s, false, 899U, 900U)));
    TEST_ASSERT_EQUAL(static_cast<int>(LinkAction::EnterFallback), static_cast<int>(link_update(s, false, 1U, 900U)));
    TEST_ASSERT_TRUE(s.fallback);
    TEST_ASSERT_EQUAL(static_cast<int>(LinkAction::None), static_cast<int>(link_update(s, false, 10000U, 900U)));
    TEST_ASSERT_EQUAL(static_cast<int>(LinkAction::LeaveFallback), static_cast<int>(link_update(s, true, 0U, 900U)));
    TEST_ASSERT_FALSE(s.fallback);
    TEST_ASSERT_EQUAL_UINT32(0U, s.silent_s);
}

void test_link_heard_commits_tentative_config() {
    LinkState s{};
    s.tentative = true;
    TEST_ASSERT_EQUAL(static_cast<int>(LinkAction::CommitConfig), static_cast<int>(link_update(s, true, 0U, 900U)));
    TEST_ASSERT_FALSE(s.tentative);
}

int main(int, char**) {
    UNITY_BEGIN();
    RUN_TEST(test_telemetry_roundtrip_and_nan_is_preserved);
    RUN_TEST(test_telemetry_rejects_bit_flip_length_and_wrong_type);
    RUN_TEST(test_telemetry_rejects_infinite_measurement);
    RUN_TEST(test_config_roundtrip_with_full_routine);
    RUN_TEST(test_factory_config_is_valid);
    RUN_TEST(test_config_validation_rejects_each_out_of_range_field);
    RUN_TEST(test_reply_carries_config_and_command);
    RUN_TEST(test_reply_without_config_has_documented_size);
    RUN_TEST(test_reply_for_other_device_is_ignored);
    RUN_TEST(test_invalid_config_in_reply_keeps_ack_and_flags_rejection);
    RUN_TEST(test_fragment_roundtrip_and_counts);
    RUN_TEST(test_burst_map_covers_largest_window);
    RUN_TEST(test_airtime_matches_lora_formula);
    RUN_TEST(test_routine_inside_and_outside_window);
    RUN_TEST(test_routine_end_is_exclusive_and_skips_weekend);
    RUN_TEST(test_routine_crossing_midnight_uses_start_day);
    RUN_TEST(test_empty_routine_is_always_active);
    RUN_TEST(test_link_loss_reverts_tentative_then_enters_fallback_and_recovers);
    RUN_TEST(test_link_heard_commits_tentative_config);
    return UNITY_END();
}
