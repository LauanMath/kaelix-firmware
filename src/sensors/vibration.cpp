#include "vibration.h"

#include "kaelix_status.h"
#include "signal_processing.h"

#include <cmath>
#include <cstring>

#if defined(ARDUINO)
#include <Arduino.h>
#include "../device_pins.h"
#include "../serial_log.h"
#include <Wire.h>
#include <esp_timer.h>
#endif

// MPU6050 register map: https://invensense.tdk.com/wp-content/uploads/2015/02/MPU-6000-Register-Map1.pdf
// MPU6515 (ID 0x74) usa ACCEL_CONFIG2 e FIFO de 512 bytes, conforme
// https://github.com/torvalds/linux/blob/master/drivers/iio/imu/inv_mpu6050/inv_mpu_core.c
// FIFO de aceleração XYZ; análise no eixo Z, em g, removendo a média
// da janela para excluir gravidade/bias. Não equivale à calibração de campo.

namespace kaelix::sensors {
namespace {

// Buffer de amostras em escopo de arquivo, dimensionado em tempo de
// compilação: 512 floats = 2048 bytes de `.bss`. Substitui um
// `std::vector<float>` que alocava e liberava o mesmo tamanho a cada
// ciclo — ~35 mil pares malloc/free por ano de campo, sem nenhum recurso
// para diagnosticar fragmentação numa máquina sem ninguém por perto, e
// com `-fno-exceptions` uma falha de alocação vira abort() → pânico →
// boot loop a ~40 mA (JSF++ AV-206; MISRA C++ 18-4-1).
float s_samples[VIBRATION_MAX_SAMPLES];

// Rascunho da FFT. Existe aqui — e não se usa a sobrecarga de
// `dominant_frequency` que traz o próprio rascunho estático — porque L2
// precisa da CAUSA da falha para nunca transmitir um veredito fabricado
// (§5): a sobrecarga simples devolve 0.0f sem dizer por quê, enquanto
// `dominant_frequency_scratch` devolve o Status. Custo: 2 × 2048 bytes de
// `.bss`, os mesmos que a sobrecarga simples usaria; como nada mais neste
// firmware a chama, o rascunho interno de lib/ deixa de ser referenciado.
float s_fft_re[VIBRATION_MAX_SAMPLES];
float s_fft_im[VIBRATION_MAX_SAMPLES];

// A aquisição só é permitida após conferir identidade e configuração.
bool s_initialized = false;

#if defined(ARDUINO)
constexpr uint8_t MPU_ADDRESS = 0x68;
constexpr uint8_t FIFO_EN = 0x23;
constexpr uint8_t USER_CTRL = 0x6A;
float s_acquired[VIBRATION_MAX_SAMPLES];
bool s_i2c_started = false;
uint16_t s_fifo_capacity = 1024U;

kaelix::Status write_register(uint8_t reg, uint8_t value) {
    Wire.beginTransmission(MPU_ADDRESS);
    Wire.write(reg);
    Wire.write(value);
    const uint8_t error = Wire.endTransmission();
    if (error == 5U) return kaelix::Status::BusTimeout;
    return error == 0U ? kaelix::Status::Ok : kaelix::Status::BusSilent;
}

kaelix::Status read_registers(uint8_t reg, uint8_t* bytes, uint8_t count) {
    Wire.beginTransmission(MPU_ADDRESS);
    Wire.write(reg);
    const uint8_t error = Wire.endTransmission(false);
    if (error == 5U) return kaelix::Status::BusTimeout;
    if (error != 0U) return kaelix::Status::BusSilent;
    if (Wire.requestFrom(MPU_ADDRESS, count) != count) return kaelix::Status::BusTimeout;
    for (uint8_t i = 0U; i < count; ++i) bytes[i] = static_cast<uint8_t>(Wire.read());
    return kaelix::Status::Ok;
}

int16_t signed_word(const uint8_t* bytes) {
    const int32_t value = (static_cast<uint16_t>(bytes[0]) << 8U) | bytes[1];
    return static_cast<int16_t>(value >= 32768 ? value - 65536 : value);
}

// Mesmo em falha, tentar parar o FIFO. Não publicar uma janela incompleta.
kaelix::Status stop_fifo(kaelix::Status status) {
    return kaelix::status_first_error(status, write_register(FIFO_EN, 0x00));
}
#endif

constexpr bool is_power_of_two(uint16_t n) {
    return n != 0U && (static_cast<uint32_t>(n) & static_cast<uint32_t>(n - 1U)) == 0U;
}

} // namespace

kaelix::Status vibration_init() {
    s_initialized = false;

#if defined(ARDUINO)
    if (!s_i2c_started) {
        if (!Wire.begin(kaelix::device::MPU_SDA, kaelix::device::MPU_SCL, 400000U))
            return kaelix::Status::BusSilent;
        Wire.setTimeOut(20);
        s_i2c_started = true;
    }
    Wire.beginTransmission(MPU_ADDRESS);
    const uint8_t probe = Wire.endTransmission();
    if (probe == 5U) return kaelix::Status::BusTimeout;
    if (probe != 0U) return kaelix::Status::SensorAbsent;
    uint8_t identity = 0U;
    KAELIX_CHECK(read_registers(0x75, &identity, 1));
#if defined(KAELIX_BENCH) && KAELIX_BENCH
    kaelix::logging::log("kaelix", "DEBUG", "IMU", "mpu addr=0x%02X who_am_i=0x%02X supported=0x68/0x74",
                  MPU_ADDRESS, identity);
#endif
    if (identity != 0x68 && identity != 0x74) return kaelix::Status::SensorIdentity;
    const bool is_mpu6515 = identity == 0x74;
    s_fifo_capacity = is_mpu6515 ? 512U : 1024U;
#if defined(KAELIX_BENCH) && KAELIX_BENCH
    kaelix::logging::log("kaelix", "DEBUG", "IMU", "imu profile=%s fifo=%u bytes",
                  is_mpu6515 ? "MPU6515" : "MPU6050", static_cast<unsigned>(s_fifo_capacity));
#endif
    KAELIX_CHECK(write_register(0x6B, 0x80)); // DEVICE_RESET
    delay(100);
    KAELIX_CHECK(write_register(0x6B, 0x01)); // PLL X gyro, awake
    KAELIX_CHECK(write_register(0x6C, 0x00));
    KAELIX_CHECK(write_register(0x1A, 0x01)); // DLPF accel 184 Hz; clock 1 kHz
    KAELIX_CHECK(write_register(0x19, 0x00)); // divider 0 -> 1 kHz
    KAELIX_CHECK(write_register(0x1C, 0x08)); // +/-4 g, 8192 LSB/g
    if (is_mpu6515) {
        // A_DLPF_CFG=1 (184 Hz), ACCEL_FCHOICE_B=0: filtro ativo, 1 kHz.
        KAELIX_CHECK(write_register(0x1D, 0x01));
    }
    KAELIX_CHECK(write_register(FIFO_EN, 0x00));
    KAELIX_CHECK(write_register(USER_CTRL, 0x00));
    delay(100); // cobre também o tempo de partida do giroscópio MPU6515
    uint8_t identity_after_reset = 0U;
    KAELIX_CHECK(read_registers(0x75, &identity_after_reset, 1));
    if (identity_after_reset != identity) return kaelix::Status::SensorIdentity;
    uint8_t config[4]{};
    KAELIX_CHECK(read_registers(0x19, config, 4));
#if defined(KAELIX_BENCH) && KAELIX_BENCH
    kaelix::logging::log("kaelix", "DEBUG", "IMU", "mpu div=0x%02X dlpf=0x%02X accel=0x%02X expected=00/01/08",
                  config[0], config[1], config[3]);
#endif
    if (config[0] != 0x00 || config[1] != 0x01 || config[3] != 0x08)
        return kaelix::Status::SensorIdentity;
    if (is_mpu6515) {
        uint8_t accel_filter = 0U;
        KAELIX_CHECK(read_registers(0x1D, &accel_filter, 1));
#if defined(KAELIX_BENCH) && KAELIX_BENCH
        kaelix::logging::log("kaelix", "DEBUG", "IMU", "mpu accel_config2=0x%02X expected=0x01", accel_filter);
#endif
        if (accel_filter != 0x01) return kaelix::Status::SensorIdentity;
    }
    s_initialized = true;
    return kaelix::Status::Ok;
#else
    return kaelix::Status::NotImplemented;
#endif
}

kaelix::Status vibration_acquire(float* dst, uint16_t n, float* out_sample_rate_hz) {
    KAELIX_REQUIRE(dst != nullptr, kaelix::Status::NullPointer);
    KAELIX_REQUIRE(out_sample_rate_hz != nullptr, kaelix::Status::NullPointer);
    KAELIX_REQUIRE(n >= VIBRATION_MIN_SAMPLES && n <= VIBRATION_MAX_SAMPLES,
                   kaelix::Status::LengthOutOfRange);
    KAELIX_REQUIRE(is_power_of_two(n), kaelix::Status::LengthNotPowerOfTwo);
    KAELIX_REQUIRE(s_initialized, kaelix::Status::NotInitialized);

#if defined(ARDUINO)
    KAELIX_CHECK(write_register(FIFO_EN, 0x00));
    KAELIX_CHECK(write_register(USER_CTRL, 0x00));
    KAELIX_CHECK(write_register(USER_CTRL, 0x04)); // reset FIFO while disabled
    KAELIX_CHECK(write_register(USER_CTRL, 0x40)); // enable FIFO engine
    const int64_t started = esp_timer_get_time();
    KAELIX_CHECK(write_register(FIFO_EN, 0x08)); // XYZ, 6 bytes/sample
    uint16_t acquired = 0U;
    int64_t first_sample_us = 0;
    int64_t last_sample_us = 0;
    double sum = 0.0;
    while (acquired < n) {
        if (esp_timer_get_time() - started > 1500000LL)
            return stop_fifo(kaelix::Status::BusTimeout);
        uint8_t interrupt = 0U;
        kaelix::Status status = read_registers(0x3A, &interrupt, 1);
        if (kaelix::is_error(status)) return stop_fifo(status);
        uint8_t count_bytes[2]{};
        status = read_registers(0x72, count_bytes, 2);
        if (kaelix::is_error(status)) return stop_fifo(status);
        const uint16_t count = (static_cast<uint16_t>(count_bytes[0]) << 8U) | count_bytes[1];
        if ((interrupt & 0x10U) != 0U || count >= s_fifo_capacity)
            return stop_fifo(kaelix::Status::SampleRateMissed);
        if (count < 6U) {
            delayMicroseconds(100);
            yield();
            continue;
        }
        // Timestamp da observação do FIFO, antes da leitura I2C.
        // Desconta a fila: o registro mais antigo precede os demais por 1 ms.
        const int64_t observed = esp_timer_get_time() - (count / 6U - 1U) * 1000LL;
        uint8_t xyz[6]{};
        status = read_registers(0x74, xyz, 6);
        if (kaelix::is_error(status)) return stop_fifo(status);
        const int16_t z = signed_word(xyz + 4);
        if (z <= -32760 || z >= 32760)
            return stop_fifo(kaelix::Status::SensorSaturated);
        if (acquired == 0U) first_sample_us = observed;
        last_sample_us = observed;
        s_acquired[acquired++] = static_cast<float>(z) / 8192.0f;
        sum += s_acquired[acquired - 1U];
    }
    KAELIX_CHECK(stop_fifo(kaelix::Status::Ok));
    const int64_t elapsed = last_sample_us - first_sample_us;
    if (elapsed <= 0) return kaelix::Status::SampleRateMissed;
    const float rate = static_cast<float>(n - 1U) * 1000000.0f / static_cast<float>(elapsed);
    if (std::fabs(rate - VIBRATION_SAMPLE_RATE_HZ) >
        VIBRATION_SAMPLE_RATE_HZ * VIBRATION_SAMPLE_RATE_TOLERANCE)
        return kaelix::Status::SampleRateMissed;
    const float mean = static_cast<float>(sum / n);
    for (uint16_t i = 0U; i < n; ++i) dst[i] = s_acquired[i] - mean;
    *out_sample_rate_hz = rate;
#if defined(KAELIX_BENCH) && KAELIX_BENCH
    kaelix::logging::log("kaelix", "DEBUG", "IMU", "mpu fs=%.2f Hz z_mean=%.5f g", rate, mean);
#endif
    return kaelix::Status::Ok;
#else
    return kaelix::Status::NotImplemented;
#endif
}

kaelix::Status vibration_features_from_samples(const float* samples, uint16_t n,
                                               float sample_rate_hz,
                                               VibrationFeatures* out) {
    KAELIX_REQUIRE(samples != nullptr, kaelix::Status::NullPointer);
    KAELIX_REQUIRE(out != nullptr, kaelix::Status::NullPointer);
    KAELIX_REQUIRE(n >= VIBRATION_MIN_SAMPLES && n <= VIBRATION_MAX_SAMPLES,
                   kaelix::Status::LengthOutOfRange);
    KAELIX_REQUIRE(is_power_of_two(n), kaelix::Status::LengthNotPowerOfTwo);
    KAELIX_REQUIRE(std::isfinite(sample_rate_hz) && sample_rate_hz > 0.0f,
                   kaelix::Status::InvalidArgument);

    // Uma única varredura, cota superior `n`, responde às duas perguntas
    // que precisam ser feitas ANTES de qualquer matemática.
    bool all_finite = true;
    bool all_identical = true;
    for (uint16_t i = 0U; i < n; ++i) {
        if (!std::isfinite(samples[i])) {
            all_finite = false;
        }
        // Comparação bit a bit, e não `==`: igualdade de ponto flutuante é
        // proibida (MISRA C++ 6-2-2) e aqui seria além disso a pergunta
        // errada — o que se quer saber é se o sensor devolveu literalmente
        // o mesmo padrão de bits, não se dois valores são numericamente
        // próximos.
        if (std::memcmp(&samples[i], &samples[0], sizeof(float)) != 0) {
            all_identical = false;
        }
    }

    // Falhas de campo: não abortam em build nenhum. São o motivo de o
    // dispositivo existir, e acontecem com o firmware correto.
    if (!all_finite) {
        return kaelix::Status::NotFinite;
    }
    if (all_identical) {
        // N amostras bit a bit idênticas é sensor congelado (I2C devolvendo
        // o mesmo registrador, sensor sem clock, buffer nunca escrito), não
        // máquina parada: um acelerômetro vivo tem ruído no bit menos
        // significativo mesmo em repouso. Sem esta verificação, um buffer
        // de zeros vira RMS = 0 / curtose = 0 e sai como "máquina sadia".
        return kaelix::Status::SensorStuck;
    }

    // Calculado em locais e só depois publicado: nenhum caminho de erro
    // deixa `*out` meio escrito.
    const float rms = compute_rms(samples, n);
    const float kurtosis = compute_kurtosis(samples, n);
    const float crest_factor = compute_crest_factor(samples, n);

    float dominant_freq_hz = 0.0f;
    const FftScratch scratch{ s_fft_re, s_fft_im, VIBRATION_MAX_SAMPLES };
    KAELIX_CHECK(dominant_frequency_scratch(samples, n, sample_rate_hz,
                                            DOMINANT_BAND_LO_HZ, DOMINANT_BAND_HI_HZ,
                                            scratch, &dominant_freq_hz));

    if (!std::isfinite(rms) || !std::isfinite(kurtosis) ||
        !std::isfinite(crest_factor) || !std::isfinite(dominant_freq_hz)) {
        // Toda comparação com NaN é falsa, então uma feature não finita
        // atravessaria o limiar de anomalia como "Normal". Ela morre aqui.
        return kaelix::Status::NotFinite;
    }

    out->rms = rms;
    out->kurtosis = kurtosis;
    out->crest_factor = crest_factor;
    out->dominant_freq_hz = dominant_freq_hz;
    return kaelix::Status::Ok;
}

kaelix::Status vibration_read_features(uint16_t n, VibrationFeatures* out) {
    KAELIX_REQUIRE(out != nullptr, kaelix::Status::NullPointer);
    KAELIX_REQUIRE(n >= VIBRATION_MIN_SAMPLES && n <= VIBRATION_MAX_SAMPLES,
                   kaelix::Status::LengthOutOfRange);
    KAELIX_REQUIRE(is_power_of_two(n), kaelix::Status::LengthNotPowerOfTwo);

    // A taxa efetiva vem da aquisição; a constante é apenas o valor
    // inicial, para que nenhum caminho use uma taxa não escrita.
    float sample_rate_hz = VIBRATION_SAMPLE_RATE_HZ;
    KAELIX_CHECK(vibration_acquire(s_samples, n, &sample_rate_hz));
    return vibration_features_from_samples(s_samples, n, sample_rate_hz, out);
}

} // namespace kaelix::sensors
