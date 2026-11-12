#include <unity.h>
#include <cstring>
#include <limits>
#include <string>
#include "../../src/gateway/records.h"

using namespace kaelix::gateway;
using namespace kaelix::protocol;

void setUp() {}
void tearDown() {}

namespace {
const char* GATEWAY = "5ef49647-9449-4f47-8d1d-c06611c3ba81";
const char* SESSION = "17162ec5-4fe1-4dac-a871-879120324a57";
ReadingRecord reading() {
    ReadingRecord r{};
    memcpy(r.session, SESSION, sizeof(r.session));
    r.event_seq = 21U;
    r.rx_uptime_ms = 12000U;
    r.rx_utc = 1793620800U;
    r.rssi = -86.0f;
    r.snr = 13.25f;
    r.telemetry.version = VERSION;
    r.telemetry.device_id = 0x311D0470U;
    r.telemetry.sequence = 48U;
    r.telemetry.boot_count = 2U;
    r.telemetry.state = 2U;
    r.telemetry.rms_z = 0.5f;
    r.telemetry.rms_x = 0.25f;
    r.telemetry.kurtosis = std::numeric_limits<float>::quiet_NaN();
    r.telemetry.temperature_c = std::numeric_limits<float>::quiet_NaN();
    r.telemetry.config_version = 7U;
    r.telemetry.command_seq = 3U;
    r.telemetry.channels = 63U;
    r.telemetry.wave_samples = 512U;
    return r;
}
}

void test_reading_json_matches_contract_fields() {
    JsonDocument d;
    add_reading(d.to<JsonObject>(), reading());
    TEST_ASSERT_EQUAL_STRING("311D0470", d["device_id"]);
    TEST_ASSERT_EQUAL_UINT32(48U, d["device_sequence"].as<uint32_t>());
    TEST_ASSERT_EQUAL_STRING("UNKNOWN", d["state"]);
    TEST_ASSERT_EQUAL_FLOAT(0.5f, d["rms_g"].as<float>());
    TEST_ASSERT_EQUAL_FLOAT(0.25f, d["rms_x_g"].as<float>());
    TEST_ASSERT_TRUE(d["kurtosis"].isNull());
    TEST_ASSERT_TRUE(d["temperature_c"].isNull());
    TEST_ASSERT_EQUAL_STRING("2026-11-02T12:00:00Z", d["gateway_received_at"]);
    TEST_ASSERT_TRUE(d["device_time"].isNull());
    TEST_ASSERT_EQUAL_UINT16(7U, d["config_version"].as<uint16_t>());
    TEST_ASSERT_EQUAL_UINT16(3U, d["command_seq"].as<uint16_t>());
    TEST_ASSERT_EQUAL_INT(VERSION, d["packet_version"].as<int>());
}

void test_reading_without_gateway_clock_has_null_reception_time() {
    ReadingRecord r = reading();
    r.rx_utc = 0U;
    JsonDocument d;
    add_reading(d.to<JsonObject>(), r);
    TEST_ASSERT_TRUE(d["gateway_received_at"].isNull());
}

void test_wave_prefix_lists_missing_fragments_and_is_valid_json() {
    WaveRecord w{};
    w.event_seq = 21U;
    w.rx_uptime_ms = 12000U;
    w.telemetry = reading().telemetry;
    w.telemetry.sensor_config = pack_sensor_config(1U, 2U, 3U);
    w.telemetry.sample_rate_hz = 999.8f;
    w.telemetry.burst_profile = 2U;
    w.fragment_total = 5U;
    bit_set(w.received, 0U);
    bit_set(w.received, 1U);
    bit_set(w.received, 3U);
    char prefix[2048];
    const int n = wave_json_prefix(w, GATEWAY, SESSION, true, 13000U, prefix, sizeof(prefix));
    TEST_ASSERT_TRUE(n > 0 && n < static_cast<int>(sizeof(prefix)));
    const std::string json = std::string(prefix) + "AAAA\"}";
    JsonDocument d;
    TEST_ASSERT_FALSE(deserializeJson(d, json));
    TEST_ASSERT_EQUAL_STRING(GATEWAY, d["gateway_id"]);
    TEST_ASSERT_TRUE(d["previous_session"].as<bool>());
    TEST_ASSERT_TRUE(d["gateway_received_at"].isNull());
    TEST_ASSERT_EQUAL_STRING("311D0470", d["device_id"]);
    TEST_ASSERT_EQUAL_INT(1, d["accel_range"].as<int>());
    TEST_ASSERT_EQUAL_INT(2, d["gyro_range"].as<int>());
    TEST_ASSERT_EQUAL_INT(3, d["dlpf"].as<int>());
    TEST_ASSERT_EQUAL_FLOAT(999.8f, d["sample_rate_hz"].as<float>());
    TEST_ASSERT_EQUAL_UINT(2U, d["fragments_missing"].size());
    TEST_ASSERT_EQUAL_INT(2, d["fragments_missing"][0].as<int>());
    TEST_ASSERT_EQUAL_INT(4, d["fragments_missing"][1].as<int>());
}

void test_wave_prefix_fits_worst_case_buffer() {
    WaveRecord w{};
    w.fragment_total = 205U; // nenhum recebido
    w.telemetry = reading().telemetry;
    char prefix[2048];
    const int n = wave_json_prefix(w, GATEWAY, SESSION, false, UINT64_MAX / 2U, prefix, sizeof(prefix));
    TEST_ASSERT_TRUE(n > 0 && n < static_cast<int>(sizeof(prefix)));
}

void test_device_config_from_api_json() {
    JsonDocument d;
    TEST_ASSERT_FALSE(deserializeJson(d, R"({"version":7,"cycle_interval_s":60,"window_samples":1024,"channels":7,"accel_range":2,"gyro_range":1,"dlpf":3,"tx_power_dbm":14,"burst_profile":1,"wave_every":2,"link_loss_s":600,"checkin_interval_s":120,"tz_offset_min":-180,"routine":[{"days":62,"start_min":480,"end_min":1080}]})"));
    DeviceConfig c{};
    TEST_ASSERT_TRUE(parse_device_config(d.as<JsonVariantConst>(), &c));
    TEST_ASSERT_EQUAL_UINT16(7U, c.version);
    TEST_ASSERT_EQUAL_UINT16(1024U, c.window_samples);
    TEST_ASSERT_EQUAL_INT8(14, c.tx_power_dbm);
    TEST_ASSERT_EQUAL_UINT8(1U, c.routine_count);
    TEST_ASSERT_EQUAL_UINT16(1080U, c.routine[0].end_min);
}

void test_device_config_invalid_or_too_many_windows_is_refused() {
    JsonDocument d;
    DeviceConfig c{};
    c.version = 99U;
    TEST_ASSERT_FALSE(deserializeJson(d, R"({"version":7,"window_samples":500})"));
    TEST_ASSERT_FALSE(parse_device_config(d.as<JsonVariantConst>(), &c));
    TEST_ASSERT_EQUAL_UINT16(99U, c.version);
    TEST_ASSERT_FALSE(deserializeJson(d, R"({"version":7,"routine":[{"days":1,"start_min":1,"end_min":2},{"days":1,"start_min":1,"end_min":2},{"days":1,"start_min":1,"end_min":2},{"days":1,"start_min":1,"end_min":2},{"days":1,"start_min":1,"end_min":2},{"days":1,"start_min":1,"end_min":2},{"days":1,"start_min":1,"end_min":2}]})"));
    TEST_ASSERT_FALSE(parse_device_config(d.as<JsonVariantConst>(), &c));
    TEST_ASSERT_FALSE(deserializeJson(d, R"({"cycle_interval_s":60})"));
    TEST_ASSERT_FALSE(parse_device_config(d.as<JsonVariantConst>(), &c));
}

void test_unknown_command_is_ignored() {
    TEST_ASSERT_EQUAL(static_cast<int>(Command::CaptureNow), static_cast<int>(parse_command("capture_now")));
    TEST_ASSERT_EQUAL(static_cast<int>(Command::None), static_cast<int>(parse_command("self_destruct")));
    TEST_ASSERT_EQUAL(static_cast<int>(Command::None), static_cast<int>(parse_command(nullptr)));
}

void test_device_table_relays_until_telemetry_confirms() {
    DeviceTable table;
    DeviceConfig c{};
    c.version = 7U;
    TEST_ASSERT_TRUE(table.set(0xAAU, &c, Command::CaptureNow, 3U));
    Pending p = table.pending_for(0xAAU, 6U, 2U);
    TEST_ASSERT_TRUE(p.has_config);
    TEST_ASSERT_EQUAL_UINT16(7U, p.config.version);
    TEST_ASSERT_EQUAL(static_cast<int>(Command::CaptureNow), static_cast<int>(p.command));
    p = table.pending_for(0xAAU, 7U, 3U); // telemetria confirmou
    TEST_ASSERT_FALSE(p.has_config);
    TEST_ASSERT_EQUAL(static_cast<int>(Command::None), static_cast<int>(p.command));
    TEST_ASSERT_FALSE(table.pending_for(0xBBU, 0U, 0U).has_config);
}

void test_device_table_records_what_was_radiated_and_ignores_repeated_set() {
    DeviceTable table;
    DeviceConfig c{};
    c.version = 7U;
    TEST_ASSERT_TRUE(table.set(0xAAU, &c, Command::None, 0U));
    TEST_ASSERT_FALSE(table.set(0xAAU, &c, Command::None, 0U)); // nada mudou, nada a gravar
    table.mark_radiated(0xAAU, 7U, 0U);
    TEST_ASSERT_EQUAL_UINT16(7U, table.entries()[0].radiated_config);
    table.clear_except(nullptr, 0U);
    TEST_ASSERT_FALSE(table.pending_for(0xAAU, 0U, 0U).has_config);
}

void test_device_table_is_bounded() {
    DeviceTable table;
    DeviceConfig c{};
    for (uint32_t id = 1U; id <= DeviceTable::CAPACITY; ++id) TEST_ASSERT_TRUE(table.set(id, &c, Command::None, 0U));
    TEST_ASSERT_FALSE(table.set(100U, &c, Command::None, 0U));
    TEST_ASSERT_EQUAL_UINT8(DeviceTable::CAPACITY, table.count());
}

void test_assembler_rebuilds_window_with_retransmission() {
    uint8_t buffer[500]{};
    WaveAssembler a;
    a.begin(buffer, sizeof(buffer), 240U, 3U);
    uint8_t first[240], second[240], third[20];
    memset(first, 1, sizeof(first));
    memset(second, 2, sizeof(second));
    memset(third, 3, sizeof(third));
    TEST_ASSERT_TRUE(a.add(0U, first, sizeof(first)));
    TEST_ASSERT_FALSE(a.round_finished(0U));
    TEST_ASSERT_TRUE(a.add(2U, third, sizeof(third)));
    TEST_ASSERT_TRUE(a.round_finished(2U));
    TEST_ASSERT_FALSE(a.complete());
    TEST_ASSERT_FALSE(bit_get(a.received(), 1U));
    a.begin_round(); // falta só o 1
    TEST_ASSERT_TRUE(a.add(1U, second, sizeof(second)));
    TEST_ASSERT_TRUE(a.round_finished(1U));
    TEST_ASSERT_TRUE(a.complete());
    TEST_ASSERT_EQUAL_UINT8(2U, buffer[240]);
    TEST_ASSERT_EQUAL_UINT8(3U, buffer[480]);
}

void test_assembler_rejects_wrong_size_and_counts_duplicate_once() {
    uint8_t buffer[480]{};
    WaveAssembler a;
    a.begin(buffer, sizeof(buffer), 240U, 2U);
    uint8_t data[240]{};
    TEST_ASSERT_FALSE(a.add(0U, data, 239U));
    TEST_ASSERT_FALSE(a.add(2U, data, 240U));
    TEST_ASSERT_TRUE(a.add(0U, data, 240U));
    TEST_ASSERT_TRUE(a.add(0U, data, 240U));
    TEST_ASSERT_EQUAL_UINT16(1U, a.received_count());
}

int main(int, char**) {
    UNITY_BEGIN();
    RUN_TEST(test_reading_json_matches_contract_fields);
    RUN_TEST(test_reading_without_gateway_clock_has_null_reception_time);
    RUN_TEST(test_wave_prefix_lists_missing_fragments_and_is_valid_json);
    RUN_TEST(test_wave_prefix_fits_worst_case_buffer);
    RUN_TEST(test_device_config_from_api_json);
    RUN_TEST(test_device_config_invalid_or_too_many_windows_is_refused);
    RUN_TEST(test_unknown_command_is_ignored);
    RUN_TEST(test_device_table_relays_until_telemetry_confirms);
    RUN_TEST(test_device_table_records_what_was_radiated_and_ignores_repeated_set);
    RUN_TEST(test_device_table_is_bounded);
    RUN_TEST(test_assembler_rebuilds_window_with_retransmission);
    RUN_TEST(test_assembler_rejects_wrong_size_and_counts_duplicate_once);
    return UNITY_END();
}
