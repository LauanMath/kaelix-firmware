#include "imu.h"

#include <Arduino.h>
#include <Wire.h>
#include <esp_timer.h>

#include "../device_pins.h"
#include "../serial_log.h"

namespace kaelix::transmitter::imu {
namespace {
namespace proto = kaelix::protocol;
using kaelix::Status;

constexpr uint8_t MPU_ADDRESS = 0x68U;
constexpr uint8_t REG_SMPLRT_DIV = 0x19U, REG_CONFIG = 0x1AU, REG_GYRO_CONFIG = 0x1BU, REG_ACCEL_CONFIG = 0x1CU;
constexpr uint8_t REG_ACCEL_CONFIG2 = 0x1DU, REG_FIFO_EN = 0x23U, REG_INT_STATUS = 0x3AU, REG_TEMP = 0x41U;
constexpr uint8_t REG_USER_CTRL = 0x6AU, REG_PWR_MGMT_1 = 0x6BU, REG_PWR_MGMT_2 = 0x6CU;
constexpr uint8_t REG_FIFO_COUNT = 0x72U, REG_FIFO_RW = 0x74U, REG_WHO_AM_I = 0x75U;
constexpr uint8_t MAX_FRAMES_PER_READ = 10U; // 120 bytes cabem no buffer de 128 do Wire
constexpr int16_t SATURATION = 32760;

bool s_i2c_started = false;
bool s_is_6515 = false;
uint16_t s_fifo_capacity = 1024U;

Status write_register(uint8_t reg, uint8_t value) {
    Wire.beginTransmission(MPU_ADDRESS);
    Wire.write(reg);
    Wire.write(value);
    const uint8_t error = Wire.endTransmission();
    if (error == 5U) return Status::BusTimeout;
    return error == 0U ? Status::Ok : Status::BusSilent;
}

Status read_registers(uint8_t reg, uint8_t* bytes, uint8_t count) {
    Wire.beginTransmission(MPU_ADDRESS);
    Wire.write(reg);
    const uint8_t error = Wire.endTransmission(false);
    if (error == 5U) return Status::BusTimeout;
    if (error != 0U) return Status::BusSilent;
    if (Wire.requestFrom(MPU_ADDRESS, count) != count) return Status::BusTimeout;
    for (uint8_t i = 0U; i < count; ++i) bytes[i] = static_cast<uint8_t>(Wire.read());
    return Status::Ok;
}

int16_t word_at(const uint8_t* bytes) {
    return static_cast<int16_t>((static_cast<uint16_t>(bytes[0]) << 8U) | bytes[1]);
}

Status stop_fifo(Status status) {
    return kaelix::status_first_error(status, write_register(REG_FIFO_EN, 0x00U));
}
} // namespace

Status configure(const proto::DeviceConfig& config) {
    if (!s_i2c_started) {
        if (!Wire.begin(kaelix::device::MPU_SDA, kaelix::device::MPU_SCL, 400000U)) return Status::BusSilent;
        Wire.setTimeOut(20);
        s_i2c_started = true;
    }
    Wire.beginTransmission(MPU_ADDRESS);
    const uint8_t probe = Wire.endTransmission();
    if (probe == 5U) return Status::BusTimeout;
    if (probe != 0U) return Status::SensorAbsent;
    uint8_t identity = 0U;
    KAELIX_CHECK(read_registers(REG_WHO_AM_I, &identity, 1U));
    if (identity != 0x68U && identity != 0x74U) return Status::SensorIdentity;
    s_is_6515 = identity == 0x74U;
    s_fifo_capacity = s_is_6515 ? 512U : 1024U;
    KAELIX_CHECK(write_register(REG_PWR_MGMT_1, 0x80U));
    delay(100);
    KAELIX_CHECK(write_register(REG_PWR_MGMT_1, 0x01U));
    KAELIX_CHECK(write_register(REG_PWR_MGMT_2, 0x00U));
    KAELIX_CHECK(write_register(REG_CONFIG, config.dlpf));
    // Com o filtro em 0, o relógio interno passa a 8 kHz; dividir mantém 1 kHz.
    const uint8_t divider = config.dlpf == 0U ? 7U : 0U;
    KAELIX_CHECK(write_register(REG_SMPLRT_DIV, divider));
    KAELIX_CHECK(write_register(REG_GYRO_CONFIG, static_cast<uint8_t>(config.gyro_range << 3U)));
    KAELIX_CHECK(write_register(REG_ACCEL_CONFIG, static_cast<uint8_t>(config.accel_range << 3U)));
    if (s_is_6515) KAELIX_CHECK(write_register(REG_ACCEL_CONFIG2, config.dlpf));
    KAELIX_CHECK(write_register(REG_FIFO_EN, 0x00U));
    KAELIX_CHECK(write_register(REG_USER_CTRL, 0x00U));
    delay(100); // partida do giroscópio
    uint8_t readback[4]{};
    KAELIX_CHECK(read_registers(REG_SMPLRT_DIV, readback, 4U));
    if (readback[0] != divider || readback[1] != config.dlpf || readback[3] != static_cast<uint8_t>(config.accel_range << 3U))
        return Status::SensorIdentity;
    kaelix::logging::log("kaelix", "DEBUG", "IMU", "profile=%s accel=%u gyro=%u dlpf=%u channels=0x%02X",
                         s_is_6515 ? "MPU6515" : "MPU6050", config.accel_range, config.gyro_range, config.dlpf, config.channels);
    return Status::Ok;
}

Status capture(const proto::DeviceConfig& config, int16_t* out, Capture* result) {
    KAELIX_REQUIRE(out != nullptr && result != nullptr, Status::NullPointer);
    // A FIFO guarda os três eixos de aceleração juntos e cada giroscópio à parte.
    const uint8_t gyro_bits = static_cast<uint8_t>((((config.channels >> 3U) & 1U) << 6U) | (((config.channels >> 4U) & 1U) << 5U) | (((config.channels >> 5U) & 1U) << 4U));
    const uint8_t gyro_count = proto::channel_count(static_cast<uint8_t>(config.channels & 0x38U));
    const uint8_t frame_bytes = static_cast<uint8_t>(6U + gyro_count * 2U);
    const uint16_t samples = config.window_samples;

    KAELIX_CHECK(write_register(REG_FIFO_EN, 0x00U));
    KAELIX_CHECK(write_register(REG_USER_CTRL, 0x00U));
    KAELIX_CHECK(write_register(REG_USER_CTRL, 0x04U)); // limpa a FIFO desligada
    KAELIX_CHECK(write_register(REG_USER_CTRL, 0x40U));
    const int64_t started = esp_timer_get_time();
    KAELIX_CHECK(write_register(REG_FIFO_EN, static_cast<uint8_t>(0x08U | gyro_bits)));

    const int64_t limit_us = static_cast<int64_t>(samples) * 3000LL + 500000LL;
    int64_t first_us = 0, last_us = 0;
    uint16_t acquired = 0U;
    size_t written = 0U;
    bool saturated = false;
    uint8_t batch[MAX_FRAMES_PER_READ * 12U];
    while (acquired < samples) {
        if (esp_timer_get_time() - started > limit_us) return stop_fifo(Status::BusTimeout);
        uint8_t interrupt = 0U;
        Status status = read_registers(REG_INT_STATUS, &interrupt, 1U);
        if (kaelix::is_error(status)) return stop_fifo(status);
        uint8_t count_bytes[2]{};
        status = read_registers(REG_FIFO_COUNT, count_bytes, 2U);
        if (kaelix::is_error(status)) return stop_fifo(status);
        const uint16_t count = static_cast<uint16_t>((static_cast<uint16_t>(count_bytes[0]) << 8U) | count_bytes[1]);
        if ((interrupt & 0x10U) != 0U || count >= s_fifo_capacity) return stop_fifo(Status::SampleRateMissed);
        const uint16_t frames = count / frame_bytes;
        if (frames == 0U) {
            delayMicroseconds(200);
            yield();
            continue;
        }
        // O quadro mais antigo da FIFO precede os demais em 1 ms cada.
        const int64_t observed = esp_timer_get_time() - (static_cast<int64_t>(frames) - 1) * 1000LL;
        uint16_t take = frames < MAX_FRAMES_PER_READ ? frames : MAX_FRAMES_PER_READ;
        if (take > samples - acquired) take = static_cast<uint16_t>(samples - acquired);
        status = read_registers(REG_FIFO_RW, batch, static_cast<uint8_t>(take * frame_bytes));
        if (kaelix::is_error(status)) return stop_fifo(status);
        if (acquired == 0U) first_us = observed;
        last_us = observed + (static_cast<int64_t>(take) - 1) * 1000LL;
        for (uint16_t f = 0U; f < take; ++f) {
            const uint8_t* frame = batch + f * frame_bytes;
            uint8_t gyro_position = 0U;
            for (uint8_t channel = 0U; channel < proto::MAX_CHANNELS; ++channel) {
                const bool selected = ((config.channels >> channel) & 1U) != 0U;
                int16_t value = 0;
                if (channel < 3U) {
                    value = word_at(frame + channel * 2U);
                    if (value >= SATURATION || value <= -SATURATION) saturated = true;
                } else if (selected) {
                    value = word_at(frame + 6U + gyro_position * 2U);
                    ++gyro_position;
                }
                if (selected) out[written++] = value;
            }
        }
        acquired = static_cast<uint16_t>(acquired + take);
    }
    KAELIX_CHECK(stop_fifo(Status::Ok));
    const int64_t elapsed = last_us - first_us;
    if (elapsed <= 0) return Status::SampleRateMissed;
    result->sample_rate_hz = static_cast<float>(samples - 1U) * 1000000.0f / static_cast<float>(elapsed);
    result->saturated = saturated;
    uint8_t temperature[2]{};
    KAELIX_CHECK(read_registers(REG_TEMP, temperature, 2U));
    const float raw = static_cast<float>(word_at(temperature));
    result->temperature_c = s_is_6515 ? raw / 333.87f + 21.0f : raw / 340.0f + 36.53f;
    return Status::Ok;
}

void sleep() {
    if (s_i2c_started) (void)write_register(REG_PWR_MGMT_1, 0x40U);
}

} // namespace kaelix::transmitter::imu
