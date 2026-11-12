#include <unity.h>
#include <cstddef>
#include <cstdlib>
#include <string>
#include <vector>
#include "../../src/gateway/spool.h"

using kaelix::gateway::RecordKind;
using kaelix::gateway::Spool;

namespace {
char directory[96];

void wipe() {
    std::string command = std::string("rm -rf ") + directory;
    TEST_ASSERT_EQUAL(0, system(command.c_str()));
}
std::vector<uint8_t> pattern(uint32_t size, uint8_t seed) {
    std::vector<uint8_t> v(size);
    for (uint32_t i = 0U; i < size; ++i) v[i] = static_cast<uint8_t>(seed + i);
    return v;
}
void put(Spool& s, uint32_t size, uint8_t seed, RecordKind kind = RecordKind::Reading) {
    const auto v = pattern(size, seed);
    TEST_ASSERT_TRUE(s.append(kind, v.data(), size));
}
uint8_t read_seed(Spool& s, Spool::Cursor& c) {
    uint8_t buffer[8192];
    RecordKind kind{};
    uint32_t size = 0U;
    TEST_ASSERT_EQUAL(static_cast<int>(Spool::ReadResult::Ok), static_cast<int>(s.read(c, &kind, buffer, sizeof(buffer), &size)));
    return buffer[0];
}
bool is_empty(Spool& s, Spool::Cursor c) {
    uint8_t buffer[8192];
    return s.read(c, nullptr, buffer, sizeof(buffer), nullptr) == Spool::ReadResult::Empty;
}
}

void setUp() {
    snprintf(directory, sizeof(directory), "/tmp/kaelix-spool-test-%d", static_cast<int>(getpid()));
    wipe();
}
void tearDown() { wipe(); }

void test_records_read_back_in_order_with_kind() {
    Spool s;
    TEST_ASSERT_TRUE(s.begin(directory, 1U << 20U, 4096U));
    put(s, 100U, 1U);
    put(s, 200U, 2U, RecordKind::Wave);
    Spool::Cursor c = s.head();
    uint8_t buffer[512];
    RecordKind kind{};
    uint32_t size = 0U;
    TEST_ASSERT_EQUAL(static_cast<int>(Spool::ReadResult::Ok), static_cast<int>(s.read(c, &kind, buffer, sizeof(buffer), &size)));
    TEST_ASSERT_EQUAL(static_cast<int>(RecordKind::Reading), static_cast<int>(kind));
    TEST_ASSERT_EQUAL_UINT32(100U, size);
    TEST_ASSERT_EQUAL_UINT8_ARRAY(pattern(100U, 1U).data(), buffer, 100U);
    TEST_ASSERT_EQUAL(static_cast<int>(Spool::ReadResult::Ok), static_cast<int>(s.read(c, &kind, buffer, sizeof(buffer), &size)));
    TEST_ASSERT_EQUAL(static_cast<int>(RecordKind::Wave), static_cast<int>(kind));
    TEST_ASSERT_TRUE(is_empty(s, c));
}

void test_unacknowledged_records_survive_reboot() {
    {
        Spool s;
        TEST_ASSERT_TRUE(s.begin(directory, 1U << 20U, 4096U));
        put(s, 50U, 1U);
        put(s, 50U, 2U);
    }
    Spool s;
    TEST_ASSERT_TRUE(s.begin(directory, 1U << 20U, 4096U));
    Spool::Cursor c = s.head();
    TEST_ASSERT_EQUAL_UINT8(1U, read_seed(s, c));
    TEST_ASSERT_EQUAL_UINT8(2U, read_seed(s, c));
    TEST_ASSERT_TRUE(is_empty(s, c));
}

void test_acknowledged_position_survives_reboot() {
    Spool::Cursor after_first{};
    {
        Spool s;
        TEST_ASSERT_TRUE(s.begin(directory, 1U << 20U, 4096U));
        put(s, 50U, 1U);
        put(s, 50U, 2U);
        after_first = s.head();
        read_seed(s, after_first);
        s.ack(after_first);
        s.flush_head();
    }
    Spool s;
    TEST_ASSERT_TRUE(s.begin(directory, 1U << 20U, 4096U));
    Spool::Cursor c = s.head();
    TEST_ASSERT_TRUE(c == after_first);
    TEST_ASSERT_EQUAL_UINT8(2U, read_seed(s, c));
}

void test_new_records_after_reboot_follow_old_ones() {
    {
        Spool s;
        TEST_ASSERT_TRUE(s.begin(directory, 1U << 20U, 4096U));
        put(s, 50U, 1U);
    }
    Spool s;
    TEST_ASSERT_TRUE(s.begin(directory, 1U << 20U, 4096U));
    put(s, 50U, 2U);
    Spool::Cursor c = s.head();
    TEST_ASSERT_EQUAL_UINT8(1U, read_seed(s, c));
    TEST_ASSERT_EQUAL_UINT8(2U, read_seed(s, c));
}

void test_record_cut_by_power_loss_is_skipped_on_next_boot() {
    {
        Spool s;
        TEST_ASSERT_TRUE(s.begin(directory, 1U << 20U, 4096U));
        put(s, 50U, 1U);
        put(s, 50U, 2U);
    }
    // Corta o segundo registro no meio, como uma queda durante a escrita.
    std::string path = std::string(directory) + "/00000001.seg";
    TEST_ASSERT_EQUAL(0, truncate(path.c_str(), 12 + 50 + 12 + 10));
    Spool s;
    TEST_ASSERT_TRUE(s.begin(directory, 1U << 20U, 4096U));
    put(s, 50U, 3U);
    Spool::Cursor c = s.head();
    TEST_ASSERT_EQUAL_UINT8(1U, read_seed(s, c));
    TEST_ASSERT_EQUAL_UINT8(3U, read_seed(s, c));
    TEST_ASSERT_EQUAL_UINT64(1U, s.corrupted_segments());
}

void test_corrupted_payload_is_not_delivered() {
    {
        Spool s;
        TEST_ASSERT_TRUE(s.begin(directory, 1U << 20U, 4096U));
        put(s, 50U, 1U);
    }
    std::string path = std::string(directory) + "/00000001.seg";
    FILE* f = fopen(path.c_str(), "r+b");
    TEST_ASSERT_NOT_NULL(f);
    fseek(f, 30, SEEK_SET);
    fputc(0xFF, f);
    fclose(f);
    Spool s;
    TEST_ASSERT_TRUE(s.begin(directory, 1U << 20U, 4096U));
    TEST_ASSERT_TRUE(is_empty(s, s.head()));
    TEST_ASSERT_EQUAL_UINT64(1U, s.corrupted_segments());
}

void test_capacity_drops_oldest_and_counts_loss() {
    Spool s;
    TEST_ASSERT_TRUE(s.begin(directory, 4000U, 1000U));
    for (uint8_t i = 0U; i < 12U; ++i) put(s, 488U, i); // 500 bytes por registro
    TEST_ASSERT_TRUE(s.used_bytes() <= 4000U);
    TEST_ASSERT_TRUE(s.dropped_records() > 0U);
    Spool::Cursor c = s.head();
    uint8_t seen = read_seed(s, c);
    TEST_ASSERT_EQUAL_UINT8(s.dropped_records(), seen); // o mais antigo restante
    uint8_t last = seen;
    while (!is_empty(s, c)) last = read_seed(s, c);
    TEST_ASSERT_EQUAL_UINT8(11U, last); // o mais novo nunca se perde
}

void test_ack_frees_space_of_finished_segments() {
    Spool s;
    TEST_ASSERT_TRUE(s.begin(directory, 1U << 20U, 1000U));
    for (uint8_t i = 0U; i < 6U; ++i) put(s, 488U, i);
    const uint64_t before = s.used_bytes();
    Spool::Cursor c = s.head();
    for (uint8_t i = 0U; i < 4U; ++i) read_seed(s, c);
    s.ack(c);
    TEST_ASSERT_TRUE(s.used_bytes() < before);
    TEST_ASSERT_EQUAL_UINT64(0U, s.dropped_records());
    Spool::Cursor rest = s.head();
    TEST_ASSERT_EQUAL_UINT8(4U, read_seed(s, rest));
}

void test_record_larger_than_buffer_is_reported_not_consumed() {
    Spool s;
    TEST_ASSERT_TRUE(s.begin(directory, 1U << 20U, 4096U));
    put(s, 300U, 9U);
    Spool::Cursor c = s.head();
    const Spool::Cursor before = c;
    uint8_t small[16];
    uint32_t size = 0U;
    TEST_ASSERT_EQUAL(static_cast<int>(Spool::ReadResult::TooLarge), static_cast<int>(s.read(c, nullptr, small, sizeof(small), &size)));
    TEST_ASSERT_EQUAL_UINT32(300U, size);
    TEST_ASSERT_TRUE(c == before);
}

void test_record_larger_than_capacity_is_refused() {
    Spool s;
    TEST_ASSERT_TRUE(s.begin(directory, 100U, 50U));
    const auto v = pattern(200U, 1U);
    TEST_ASSERT_FALSE(s.append(RecordKind::Wave, v.data(), 200U));
}

// O descritor do gravador já foi fechado por fora, no WiFiClientSecure::stop(). A gravação
// falha e diz onde; a seguinte vai para um segmento novo, sem perder o que já estava gravado.
void test_append_recovers_when_descriptor_is_closed_behind_it() {
    Spool s;
    TEST_ASSERT_TRUE(s.begin(directory, 100000U, 4096U));
    put(s, 100U, 1U);
    char path[128];
    snprintf(path, sizeof(path), "%s/00000001.seg", directory);
    struct stat segment {};
    TEST_ASSERT_EQUAL(0, stat(path, &segment));
    bool closed = false;
    for (int fd = 3; fd < 256 && !closed; ++fd) {
        struct stat info {};
        if (fstat(fd, &info) == 0 && info.st_ino == segment.st_ino && info.st_dev == segment.st_dev) closed = close(fd) == 0;
    }
    TEST_ASSERT_TRUE(closed);
    const auto v = pattern(100U, 2U);
    TEST_ASSERT_FALSE(s.append(RecordKind::Reading, v.data(), 100U));
    TEST_ASSERT_EQUAL_STRING("flush", s.failed_step());
    TEST_ASSERT_EQUAL(EBADF, s.failed_errno());
    TEST_ASSERT_TRUE(s.append(RecordKind::Reading, v.data(), 100U));
    Spool::Cursor c = s.head();
    TEST_ASSERT_EQUAL_UINT8(1U, read_seed(s, c));
    TEST_ASSERT_EQUAL_UINT8(2U, read_seed(s, c));
    TEST_ASSERT_TRUE(is_empty(s, c));
}

int main(int, char**) {
    UNITY_BEGIN();
    RUN_TEST(test_records_read_back_in_order_with_kind);
    RUN_TEST(test_unacknowledged_records_survive_reboot);
    RUN_TEST(test_acknowledged_position_survives_reboot);
    RUN_TEST(test_new_records_after_reboot_follow_old_ones);
    RUN_TEST(test_record_cut_by_power_loss_is_skipped_on_next_boot);
    RUN_TEST(test_corrupted_payload_is_not_delivered);
    RUN_TEST(test_capacity_drops_oldest_and_counts_loss);
    RUN_TEST(test_ack_frees_space_of_finished_segments);
    RUN_TEST(test_record_larger_than_buffer_is_reported_not_consumed);
    RUN_TEST(test_record_larger_than_capacity_is_refused);
    RUN_TEST(test_append_recovers_when_descriptor_is_closed_behind_it);
    return UNITY_END();
}
