#include <Arduino.h>
#include <Preferences.h>
#include <esp_sleep.h>
#include <esp_system.h>
#include <sys/time.h>

#include <cmath>
#include <limits>

#include "../power/rtc_watchdog.h"
#include "../power/watchdog.h"
#include "../sensors/vibration.h"
#include "../serial_log.h"
#include "imu.h"
#include "kaelix_protocol.h"
#include "link.h"

// Transmissor de campo. Mede com a configuração gravada, com ou sem gateway, e
// escuta logo depois de cada telemetria: é só aí que comandos podem chegar.
namespace {
namespace proto = kaelix::protocol;
namespace imu = kaelix::transmitter::imu;
namespace link_ = kaelix::transmitter::link;
using kaelix::Status;
using kaelix::logging::log;

constexpr uint8_t NO_MEASUREMENT_STATE = 2U; // MachineState::Unknown: sem modelo neste perfil
constexpr int8_t FALLBACK_TX_POWER_DBM = 17;
constexpr uint32_t DEEP_SLEEP_MIN_S = 30U; // abaixo disso, religar tudo custa mais que esperar
constexpr uint32_t REPLY_FRAME_MS = 500U;
constexpr uint32_t RTC_RETAINED_MAGIC = 0x4B4C5833UL; // "KLX3"
constexpr uint16_t FEATURE_SAMPLES = 512U;
constexpr float NOT_MEASURED = std::numeric_limits<float>::quiet_NaN();

// Sobrevive ao deep sleep e aos resets que não cortam a energia.
struct RetainedState {
    uint32_t magic;
    uint32_t boot_count;
    uint32_t sequence;
    uint32_t pending_s;   // tempo desde a última avaliação do enlace
    uint32_t silent_s;
    uint16_t command_seq;
    uint16_t reverted_version; // derrubou o enlace; não aplicar de novo
    uint8_t tentative;
    uint8_t fallback;
    uint8_t time_synced;
    uint8_t force_capture;
    uint8_t config_rejected;
    uint8_t wave_counter;
    uint16_t crc;
};
RTC_NOINIT_ATTR RetainedState s_retained;

proto::DeviceConfig s_active{};
proto::DeviceConfig s_previous{};
Preferences s_prefs;
int16_t s_wave[proto::MAX_WINDOW_SAMPLES * proto::MAX_CHANNELS];
float s_z[FEATURE_SAMPLES], s_axis[FEATURE_SAMPLES];
bool s_imu_ready = false, s_radio_ready = false;
uint32_t s_cycle_started_ms = 0U;
uint32_t s_elapsed_ms = 0U; // ainda não somado a pending_s

uint32_t device_id() { return static_cast<uint32_t>(ESP.getEfuseMac() & 0xFFFFFFFFULL); }

void retained_seal() { s_retained.crc = kaelix::comms::crc16_ccitt(reinterpret_cast<const uint8_t*>(&s_retained), offsetof(RetainedState, crc)); }

bool retained_valid() {
    return s_retained.magic == RTC_RETAINED_MAGIC &&
           s_retained.crc == kaelix::comms::crc16_ccitt(reinterpret_cast<const uint8_t*>(&s_retained), offsetof(RetainedState, crc));
}

void load_blob(const char* key, proto::DeviceConfig* out) {
    uint8_t bytes[proto::CONFIG_MAX_BYTES];
    const size_t size = s_prefs.getBytesLength(key);
    if (size == 0U || size > sizeof(bytes)) return;
    s_prefs.getBytes(key, bytes, size);
    if (!proto::decode_config(bytes, size, out)) log("kaelix", "ERROR", "CONFIG", "stored %s invalid; using defaults", key);
}

void save_blob(const char* key, const proto::DeviceConfig& config) {
    uint8_t bytes[proto::CONFIG_MAX_BYTES];
    const size_t size = proto::encode_config(config, bytes, sizeof(bytes));
    if (size > 0U) s_prefs.putBytes(key, bytes, size);
}

void load_state() {
    s_prefs.begin("kaelix", false);
    load_blob("active", &s_active);
    load_blob("previous", &s_previous);
    if (!retained_valid()) {
        // Energia cortada: só o número de boots vem da flash.
        memset(&s_retained, 0, sizeof(s_retained));
        s_retained.magic = RTC_RETAINED_MAGIC;
        s_retained.boot_count = s_prefs.getUInt("boots", 0U) + 1U;
        s_prefs.putUInt("boots", s_retained.boot_count);
        s_retained.command_seq = s_prefs.getUShort("cmd", 0U);
    }
    retained_seal();
}

void apply_new_config(const proto::DeviceConfig& config) {
    s_previous = s_active;
    s_active = config;
    save_blob("previous", s_previous);
    save_blob("active", s_active);
    s_retained.tentative = 1U;
    s_imu_ready = false;
    log("kaelix", "INFO", "CONFIG", "applied version=%u interval=%u window=%u channels=0x%02X power=%d profile=%u routine=%u",
        s_active.version, s_active.cycle_interval_s, s_active.window_samples, s_active.channels, s_active.tx_power_dbm, s_active.burst_profile, s_active.routine_count);
}

void factory_reset() {
    s_active = proto::DeviceConfig{};
    s_previous = proto::DeviceConfig{};
    s_prefs.remove("active");
    s_prefs.remove("previous");
    s_retained.tentative = 0U;
    s_imu_ready = false;
    log("kaelix", "WARN", "CONFIG", "factory reset");
}

// Avalia o enlace depois de cada tentativa de ouvir o gateway.
void update_link(bool heard) {
    proto::LinkState state;
    state.silent_s = s_retained.silent_s;
    state.tentative = s_retained.tentative != 0U;
    state.fallback = s_retained.fallback != 0U;
    const proto::LinkAction action = proto::link_update(state, heard, s_retained.pending_s, s_active.link_loss_s);
    s_retained.pending_s = 0U;
    s_retained.silent_s = state.silent_s;
    s_retained.tentative = state.tentative ? 1U : 0U;
    s_retained.fallback = state.fallback ? 1U : 0U;
    switch (action) {
        case proto::LinkAction::CommitConfig:
            log("kaelix", "INFO", "LINK", "config version=%u confirmed", s_active.version);
            s_previous = s_active;
            save_blob("previous", s_previous);
            break;
        case proto::LinkAction::RevertConfig:
            log("kaelix", "WARN", "LINK", "gateway silent; reverting version=%u to %u", s_active.version, s_previous.version);
            s_retained.reverted_version = s_active.version;
            s_active = s_previous;
            save_blob("active", s_active);
            s_imu_ready = false;
            break;
        case proto::LinkAction::EnterFallback:
            log("kaelix", "WARN", "LINK", "gateway silent for %lu s; fallback power and no routine", static_cast<unsigned long>(s_retained.silent_s));
            break;
        case proto::LinkAction::LeaveFallback:
            log("kaelix", "INFO", "LINK", "gateway heard again");
            break;
        case proto::LinkAction::None:
            break;
    }
}

float rms_of_channel(uint8_t position, uint8_t stride, uint16_t n, float lsb_per_g) {
    double sum = 0.0;
    for (uint16_t i = 0U; i < n; ++i) sum += s_wave[i * stride + position];
    const double mean = sum / n;
    double squares = 0.0;
    for (uint16_t i = 0U; i < n; ++i) {
        const double value = (s_wave[i * stride + position] - mean) / lsb_per_g;
        squares += value * value;
    }
    return static_cast<float>(std::sqrt(squares / n));
}

void fill_measurement(proto::Telemetry* t, const imu::Capture& capture, Status status) {
    const proto::DeviceConfig& c = s_active;
    t->sample_rate_hz = capture.sample_rate_hz;
    t->temperature_c = capture.temperature_c;
    t->rms_x = t->rms_y = t->rms_z = t->kurtosis = t->crest_factor = t->dominant_freq_hz = NOT_MEASURED;
    if (kaelix::is_ok(status) && capture.saturated) {
        status = Status::SensorSaturated;
        t->flags |= proto::FLAG_SATURATED;
    }
    if (kaelix::is_ok(status) && std::fabs(capture.sample_rate_hz - kaelix::sensors::VIBRATION_SAMPLE_RATE_HZ) >
                                     kaelix::sensors::VIBRATION_SAMPLE_RATE_HZ * kaelix::sensors::VIBRATION_SAMPLE_RATE_TOLERANCE) {
        status = Status::SampleRateMissed;
    }
    if (kaelix::is_ok(status)) {
        const uint8_t stride = proto::channel_count(c.channels);
        const uint16_t n = c.window_samples < FEATURE_SAMPLES ? c.window_samples : FEATURE_SAMPLES;
        const float lsb = 16384.0f / static_cast<float>(1U << c.accel_range);
        const uint8_t position_z = proto::channel_count(static_cast<uint8_t>(c.channels & 0x03U));
        double sum = 0.0;
        for (uint16_t i = 0U; i < n; ++i) {
            s_z[i] = static_cast<float>(s_wave[i * stride + position_z]) / lsb;
            sum += s_z[i];
        }
        const float mean = static_cast<float>(sum / n);
        for (uint16_t i = 0U; i < n; ++i) s_z[i] -= mean;
        kaelix::sensors::VibrationFeatures features{};
        status = kaelix::sensors::vibration_features_from_samples(s_z, n, capture.sample_rate_hz, &features);
        if (kaelix::is_ok(status)) {
            t->rms_z = features.rms;
            t->kurtosis = features.kurtosis;
            t->crest_factor = features.crest_factor;
            t->dominant_freq_hz = features.dominant_freq_hz;
            if ((c.channels & 0x01U) != 0U) t->rms_x = rms_of_channel(0U, stride, n, lsb);
            if ((c.channels & 0x02U) != 0U) t->rms_y = rms_of_channel((c.channels & 0x01U) != 0U ? 1U : 0U, stride, n, lsb);
            log("kaelix", "INFO", "MEASURE", "rms=%.6f x=%.6f y=%.6f kurt=%.3f crest=%.3f freq=%.2f fs=%.2f temp=%.1f",
                t->rms_z, t->rms_x, t->rms_y, t->kurtosis, t->crest_factor, t->dominant_freq_hz, t->sample_rate_hz, t->temperature_c);
        }
    }
    t->diag = kaelix::status_code(status);
    if (kaelix::is_error(status)) log("kaelix", "ERROR", "MEASURE", "%s", kaelix::status_to_string(status));
}

// Rajada: envia o que falta, recebe o mapa, em até BURST_ROUNDS rodadas.
void send_burst(const proto::Telemetry& t) {
    const uint16_t total = t.wave_fragments;
    const uint16_t payload = proto::fragment_payload(t.channels);
    const uint32_t bytes = proto::wave_bytes(t.wave_samples, t.channels);
    const proto::BurstProfile profile = proto::BURST_PROFILES[t.burst_profile];
    const uint32_t per_fragment = proto::airtime_ms(sizeof(proto::FragmentHeader) + proto::FRAGMENT_PAYLOAD + 2U, profile.sf, profile.bw_khz) + proto::FRAGMENT_GAP_MS;
    const uint32_t map_wait = proto::burst_map_wait_ms(t.burst_profile);
    // O teto de 20 s por ciclo não cabe numa rajada longa.
    (void)kaelix_rtc_watchdog_arm(20000U + (total * per_fragment + map_wait) * proto::BURST_ROUNDS);
    uint8_t acknowledged[proto::BURST_MAP_BYTES]{};
    uint8_t frame[proto::MAX_FRAME];
    const uint32_t started = millis();
    uint16_t sent = 0U;
    uint8_t rounds = 0U;
    bool complete = false;
    if (kaelix::is_error(link_::use_burst(t.burst_profile))) {
        log("kaelix", "ERROR", "WAVE", "burst profile refused");
    } else {
        delay(proto::BURST_START_DELAY_MS);
        for (uint8_t round = 0U; round < proto::BURST_ROUNDS && !complete; ++round) {
            ++rounds;
            for (uint16_t index = 0U; index < total; ++index) {
                if (proto::bit_get(acknowledged, index)) continue;
                const uint32_t offset = static_cast<uint32_t>(index) * payload;
                const size_t length = bytes - offset < payload ? bytes - offset : payload;
                const size_t size = proto::encode_fragment(t.device_id, t.sequence, static_cast<uint8_t>(index), static_cast<uint8_t>(total),
                                                           reinterpret_cast<const uint8_t*>(s_wave) + offset, length, frame, sizeof(frame));
                (void)kaelix::power::watchdog_feed();
                if (size == 0U || kaelix::is_error(link_::send(frame, size))) log("kaelix", "ERROR", "WAVE", "fragment %u not sent", index);
                ++sent;
                // O gateway responde logo depois do último fragmento: esperar
                // aqui faria o transmissor perder o início do mapa.
                bool more = false;
                for (uint16_t next = index + 1U; next < total && !more; ++next) more = !proto::bit_get(acknowledged, next);
                if (more) delay(proto::FRAGMENT_GAP_MS);
            }
            (void)kaelix::power::watchdog_feed();
            size_t length = 0U;
            proto::BurstMap map{};
            if (!link_::receive(frame, sizeof(frame), &length, map_wait, 500U) || !proto::decode_burst_map(frame, length, &map) ||
                map.device_id != t.device_id || map.sequence != t.sequence) {
                log("kaelix", "WARN", "WAVE", "seq=%lu no map after round %u", static_cast<unsigned long>(t.sequence), round + 1U);
                break;
            }
            memcpy(acknowledged, map.received, sizeof(acknowledged));
            complete = true;
            for (uint16_t index = 0U; index < total; ++index) complete = complete && proto::bit_get(acknowledged, index);
        }
    }
    (void)link_::use_control();
    log("kaelix", complete ? "INFO" : "WARN", "WAVE", "seq=%lu fragments=%u sent=%u rounds=%u complete=%d took=%lums",
        static_cast<unsigned long>(t.sequence), total, sent, rounds, complete, static_cast<unsigned long>(millis() - started));
}

void execute_command(proto::Command command) {
    switch (command) {
        case proto::Command::Reboot:
            log("kaelix", "WARN", "COMMAND", "reboot");
            retained_seal();
            s_prefs.end();
            delay(100);
            ESP.restart();
            break;
        case proto::Command::FactoryReset:
            factory_reset();
            break;
        case proto::Command::CaptureNow:
            s_retained.force_capture = 1U;
            log("kaelix", "INFO", "COMMAND", "capture now");
            break;
        case proto::Command::None:
            break;
    }
}

// Devolve quantos milissegundos dormir ou esperar depois deste ciclo.
uint32_t run_cycle() {
    const proto::DeviceConfig& c = s_active;
    const bool fallback = s_retained.fallback != 0U;
    const int64_t now = static_cast<int64_t>(time(nullptr));
    // Sem hora ou em resposta automática, a rotina não vale: medir é o seguro.
    const bool routine_applies = c.routine_count > 0U && s_retained.time_synced != 0U && !fallback;
    const bool off_window = routine_applies && s_retained.force_capture == 0U && !proto::routine_active(c, now);

    proto::Telemetry t{};
    t.device_id = device_id();
    t.sequence = ++s_retained.sequence;
    t.boot_count = s_retained.boot_count;
    t.state = NO_MEASUREMENT_STATE;
    t.reset_reason = static_cast<uint8_t>(esp_reset_reason());
    t.config_version = c.version;
    t.command_seq = s_retained.command_seq;
    t.device_time = s_retained.time_synced != 0U ? static_cast<uint32_t>(now) : 0U;
    t.uptime_s = static_cast<uint32_t>(millis() / 1000U);
    t.burst_profile = c.burst_profile;
    t.channels = c.channels;
    t.sensor_config = proto::pack_sensor_config(c.accel_range, c.gyro_range, c.dlpf);
    t.tx_power_dbm = fallback ? FALLBACK_TX_POWER_DBM : c.tx_power_dbm;
    if (s_retained.time_synced != 0U) t.flags |= proto::FLAG_TIME_SYNCED;
    if (fallback) t.flags |= proto::FLAG_FALLBACK;
    if (s_retained.config_rejected != 0U) t.flags |= proto::FLAG_CONFIG_REJECTED;

    bool wave_ready = false;
    if (off_window) {
        t.flags |= proto::FLAG_NO_MEASUREMENT;
        t.rms_x = t.rms_y = t.rms_z = t.kurtosis = t.crest_factor = t.dominant_freq_hz = t.sample_rate_hz = t.temperature_c = NOT_MEASURED;
    } else {
        Status status = Status::Ok;
        if (!s_imu_ready) {
            status = imu::configure(c);
            s_imu_ready = kaelix::is_ok(status);
        }
        imu::Capture capture{};
        capture.sample_rate_hz = NOT_MEASURED;
        capture.temperature_c = NOT_MEASURED;
        if (kaelix::is_ok(status)) status = imu::capture(c, s_wave, &capture);
        const bool captured = kaelix::is_ok(status);
        if (!captured) s_imu_ready = false;
        fill_measurement(&t, capture, status);
        const bool wave_due = s_retained.force_capture != 0U || (c.wave_every > 0U && ++s_retained.wave_counter >= c.wave_every);
        if (wave_due && captured) {
            s_retained.wave_counter = 0U;
            wave_ready = true;
            t.flags |= proto::FLAG_WAVE_FOLLOWS;
            t.wave_fragments = static_cast<uint8_t>(proto::fragment_count(c.window_samples, c.channels));
            t.wave_samples = c.window_samples;
        }
        s_retained.force_capture = 0U;
        (void)kaelix::power::watchdog_feed();
    }
    proto::seal_telemetry(&t);

    Status radio = Status::Ok;
    if (!s_radio_ready) {
        radio = link_::init(t.tx_power_dbm);
        s_radio_ready = kaelix::is_ok(radio);
    } else {
        radio = link_::set_power(t.tx_power_dbm);
    }
    bool heard = false;
    proto::Reply reply{};
    if (s_radio_ready) radio = link_::send(reinterpret_cast<const uint8_t*>(&t), sizeof(t));
    if (kaelix::is_error(radio)) {
        log("kaelix", "ERROR", "RADIO", "%s", kaelix::status_to_string(radio));
        s_radio_ready = false;
    } else {
        uint8_t frame[proto::REPLY_MAX_FRAME];
        size_t length = 0U;
        heard = link_::receive(frame, sizeof(frame), &length, proto::REPLY_WINDOW_MS, REPLY_FRAME_MS) &&
                proto::decode_reply(frame, length, t.device_id, &reply) && reply.header.sequence == t.sequence;
    }
    log("kaelix", "INFO", "CYCLE", "seq=%lu flags=0x%02X heard=%d silent=%lu cfg=%u", static_cast<unsigned long>(t.sequence), t.flags, heard, static_cast<unsigned long>(s_retained.silent_s), c.version);
    update_link(heard);

    proto::Command pending_command = proto::Command::None;
    if (heard) {
        if (reply.header.utc != 0U) {
            timeval value{static_cast<time_t>(reply.header.utc), 0};
            settimeofday(&value, nullptr);
            s_retained.time_synced = 1U;
        }
        // O gateway reenvia enquanto a versão não confere. Sem isto, uma configuração
        // que derruba o enlace seria aplicada e revertida para sempre.
        const bool reverted = reply.has_config && reply.config.version == s_retained.reverted_version;
        s_retained.config_rejected = (reply.config_rejected || reverted) ? 1U : 0U;
        if (reply.has_config && !reverted && reply.config.version != s_active.version) apply_new_config(reply.config);
        if ((reply.header.flags & proto::REPLY_HAS_COMMAND) != 0U && reply.header.command_seq != s_retained.command_seq) {
            pending_command = static_cast<proto::Command>(reply.header.command);
            s_retained.command_seq = reply.header.command_seq;
            s_prefs.putUShort("cmd", s_retained.command_seq);
        }
        if (wave_ready && (reply.header.flags & proto::REPLY_BURST_GO) != 0U) send_burst(t);
    }
    execute_command(pending_command);
    retained_seal();

    const uint32_t active_ms = millis() - s_cycle_started_ms;
    if (s_retained.force_capture != 0U) return 0U;
    // A resposta pode ter trazido outra rotina: vale a que está ativa agora.
    const bool routine_applies_now = s_active.routine_count > 0U && s_retained.time_synced != 0U && s_retained.fallback == 0U;
    if (routine_applies_now && !proto::routine_active(s_active, static_cast<int64_t>(time(nullptr)))) {
        const uint32_t until = proto::seconds_until_active(s_active, static_cast<int64_t>(time(nullptr)));
        return (until != 0U && until < s_active.checkin_interval_s ? until : s_active.checkin_interval_s) * 1000U;
    }
    const uint32_t interval_ms = s_active.cycle_interval_s * 1000U;
    return interval_ms > active_ms ? interval_ms - active_ms : 0U;
}

void deep_sleep(uint32_t seconds) {
    imu::sleep();
    (void)link_::sleep();
    link_::hold_pins_for_deep_sleep();
    (void)kaelix::power::watchdog_arm_for_sleep(seconds / 60U + 2U);
    esp_sleep_enable_timer_wakeup(static_cast<uint64_t>(seconds) * 1000000ULL);
    s_retained.pending_s += seconds;
    retained_seal();
    log("kaelix", "INFO", "SLEEP", "deep sleep %lu s", static_cast<unsigned long>(seconds));
    Serial.flush();
    s_prefs.end();
    esp_deep_sleep_start();
}
} // namespace

void setup() {
    Serial.begin(115200);
#if ARDUINO_USB_CDC_ON_BOOT
    Serial.setTxTimeoutMs(0); // sem computador na USB, escrever não pode atrasar o rádio
#endif
    link_::release_pins_after_wake();
    delay(esp_reset_reason() == ESP_RST_DEEPSLEEP ? 50 : 1000);
    load_state();
    log("kaelix", "INFO", "BOOT", "transmitter id=%08lX boot=%lu seq=%lu reset=%d config=%u", static_cast<unsigned long>(device_id()),
        static_cast<unsigned long>(s_retained.boot_count), static_cast<unsigned long>(s_retained.sequence),
        static_cast<int>(esp_reset_reason()), s_active.version);
}

void loop() {
    s_cycle_started_ms = millis();
    const Status armed = kaelix::power::watchdog_arm_active_phase();
    if (kaelix::is_error(armed)) log("kaelix", "ERROR", "WDT", "%s", kaelix::status_to_string(armed));
    uint32_t wait_ms = run_cycle();
    s_elapsed_ms += millis() - s_cycle_started_ms;
    if (wait_ms >= DEEP_SLEEP_MIN_S * 1000U) {
        s_retained.pending_s += s_elapsed_ms / 1000U;
        s_elapsed_ms = 0U;
        deep_sleep(wait_ms / 1000U);
        return;
    }
    if (s_radio_ready) (void)link_::sleep();
    s_elapsed_ms += wait_ms;
    while (wait_ms > 0U) {
        const uint32_t step = wait_ms < 1000U ? wait_ms : 1000U;
        delay(step);
        wait_ms -= step;
        // Espera ociosa não conta para o teto de 20 s do ciclo ativo.
        (void)kaelix_rtc_watchdog_arm(kaelix::power::WATCHDOG_ACTIVE_RTC_MS);
        (void)kaelix::power::watchdog_feed();
    }
    s_retained.pending_s += s_elapsed_ms / 1000U;
    s_elapsed_ms %= 1000U;
    retained_seal();
}
