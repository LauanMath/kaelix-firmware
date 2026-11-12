#pragma once

#include <ArduinoJson.h>

#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <ctime>

#include "kaelix_protocol.h"

// O que o gateway grava em flash e como converte para o contrato HTTP. Sem
// Arduino, para que o JSON seja conferido no host contra o contrato da API.
namespace kaelix::gateway {

namespace proto = kaelix::protocol;

struct __attribute__((packed)) ReadingRecord {
    char session[36];
    uint32_t event_seq;
    uint64_t rx_uptime_ms;
    uint32_t rx_utc; // 0 se o gateway estava sem hora
    float rssi;
    float snr;
    proto::Telemetry telemetry;
};

// Seguido de `sample_bytes` bytes de amostras.
struct __attribute__((packed)) WaveRecord {
    char session[36];
    uint32_t event_seq;
    uint64_t rx_uptime_ms;
    uint32_t rx_utc;
    proto::Telemetry telemetry;
    uint16_t fragment_total;
    uint32_t sample_bytes;
    uint8_t received[proto::BURST_MAP_BYTES];
};

inline void format_utc(uint32_t seconds, char* out, size_t size) {
    const time_t t = static_cast<time_t>(seconds);
    tm utc{};
    gmtime_r(&t, &utc);
    strftime(out, size, "%Y-%m-%dT%H:%M:%SZ", &utc);
}

inline void set_number(JsonObject o, const char* key, float value) {
    if (std::isfinite(value)) o[key] = static_cast<double>(value);
    else o[key] = nullptr;
}

inline void add_reading(JsonObject o, const ReadingRecord& r) {
    const proto::Telemetry& t = r.telemetry;
    o["event_seq"] = r.event_seq;
    o["gateway_rx_uptime_ms"] = r.rx_uptime_ms;
    if (r.rx_utc != 0U) {
        char at[25];
        format_utc(r.rx_utc, at, sizeof(at));
        o["gateway_received_at"] = at;
    } else {
        o["gateway_received_at"] = nullptr;
    }
    o["packet_version"] = t.version;
    char id[9];
    snprintf(id, sizeof(id), "%08lX", static_cast<unsigned long>(t.device_id));
    o["device_id"] = id;
    o["device_sequence"] = t.sequence;
    o["boot_count"] = t.boot_count;
    static constexpr const char* STATES[] = {"NORMAL", "ANOMALOUS", "UNKNOWN"};
    o["state"] = STATES[t.state <= 2U ? t.state : 2U];
    o["diag_code"] = t.diag;
    set_number(o, "rms_g", t.rms_z);
    set_number(o, "rms_x_g", t.rms_x);
    set_number(o, "rms_y_g", t.rms_y);
    set_number(o, "kurtosis", t.kurtosis);
    set_number(o, "crest_factor", t.crest_factor);
    set_number(o, "dominant_freq_hz", t.dominant_freq_hz);
    set_number(o, "sample_rate_hz", t.sample_rate_hz);
    set_number(o, "temperature_c", t.temperature_c);
    o["rssi_dbm"] = r.rssi;
    o["snr_db"] = r.snr;
    o["packet_crc16"] = t.crc;
    o["config_version"] = t.config_version;
    o["command_seq"] = t.command_seq;
    o["reset_reason"] = t.reset_reason;
    o["flags"] = t.flags;
    if (t.device_time != 0U) {
        char at[25];
        format_utc(t.device_time, at, sizeof(at));
        o["device_time"] = at;
    } else {
        o["device_time"] = nullptr;
    }
    o["uptime_s"] = t.uptime_s;
    o["wave_fragments"] = t.wave_fragments;
    o["wave_samples"] = t.wave_samples;
    o["channels"] = t.channels;
    o["tx_power_dbm"] = t.tx_power_dbm;
}

// Cabeçalho do JSON da janela, até o início de samples_b64. Em texto, porque o
// bloco em base64 pode ter 64 KiB e não deve ser copiado para um documento.
inline int wave_json_prefix(const WaveRecord& w, const char* gateway_id, const char* session,
                            bool previous_session, uint64_t upload_uptime_ms, char* out, size_t size) {
    const proto::Telemetry& t = w.telemetry;
    char received[32] = "null";
    if (w.rx_utc != 0U) {
        char at[25];
        format_utc(w.rx_utc, at, sizeof(at));
        snprintf(received, sizeof(received), "\"%s\"", at);
    }
    char missing[proto::BURST_MAP_BYTES * 8U * 4U + 3U];
    size_t used = 0U;
    missing[used++] = '[';
    bool first = true;
    for (uint16_t i = 0U; i < w.fragment_total; ++i) {
        if (proto::bit_get(w.received, i)) continue;
        used += static_cast<size_t>(snprintf(missing + used, sizeof(missing) - used, first ? "%u" : ",%u", static_cast<unsigned>(i)));
        first = false;
    }
    snprintf(missing + used, sizeof(missing) - used, "]");
    char rate[24] = "null";
    if (std::isfinite(t.sample_rate_hz)) snprintf(rate, sizeof(rate), "%.3f", static_cast<double>(t.sample_rate_hz));
    return snprintf(out, size,
        "{\"schema_version\":1,\"gateway_id\":\"%s\",\"gateway_session_id\":\"%s\",\"previous_session\":%s,"
        "\"upload_uptime_ms\":%llu,\"event_seq\":%lu,\"gateway_rx_uptime_ms\":%llu,\"gateway_received_at\":%s,"
        "\"device_id\":\"%08lX\",\"device_sequence\":%lu,\"boot_count\":%lu,\"channels\":%u,\"window_samples\":%u,"
        "\"sample_rate_hz\":%s,\"accel_range\":%u,\"gyro_range\":%u,\"dlpf\":%u,\"burst_profile\":%u,"
        "\"fragment_total\":%u,\"fragments_missing\":%s,\"samples_b64\":\"",
        gateway_id, session, previous_session ? "true" : "false",
        static_cast<unsigned long long>(upload_uptime_ms), static_cast<unsigned long>(w.event_seq),
        static_cast<unsigned long long>(w.rx_uptime_ms), received,
        static_cast<unsigned long>(t.device_id), static_cast<unsigned long>(t.sequence),
        static_cast<unsigned long>(t.boot_count), static_cast<unsigned>(t.channels), static_cast<unsigned>(t.wave_samples),
        rate, static_cast<unsigned>(t.sensor_config & 3U), static_cast<unsigned>((t.sensor_config >> 2U) & 3U),
        static_cast<unsigned>((t.sensor_config >> 4U) & 7U), static_cast<unsigned>(t.burst_profile),
        static_cast<unsigned>(w.fragment_total), missing);
}

// A API já validou, mas o gateway não repassa pelo rádio nada que o transmissor
// recusaria. Campo ausente mantém o padrão de fábrica.
inline bool parse_device_config(JsonVariantConst j, proto::DeviceConfig* out) {
    if (out == nullptr || !j.is<JsonObjectConst>() || !j["version"].is<uint16_t>()) return false;
    proto::DeviceConfig c{};
    c.version = j["version"].as<uint16_t>();
    c.cycle_interval_s = j["cycle_interval_s"] | c.cycle_interval_s;
    c.window_samples = j["window_samples"] | c.window_samples;
    c.channels = j["channels"] | c.channels;
    c.accel_range = j["accel_range"] | c.accel_range;
    c.gyro_range = j["gyro_range"] | c.gyro_range;
    c.dlpf = j["dlpf"] | c.dlpf;
    c.tx_power_dbm = j["tx_power_dbm"] | c.tx_power_dbm;
    c.burst_profile = j["burst_profile"] | c.burst_profile;
    c.wave_every = j["wave_every"] | c.wave_every;
    c.link_loss_s = j["link_loss_s"] | c.link_loss_s;
    c.checkin_interval_s = j["checkin_interval_s"] | c.checkin_interval_s;
    c.tz_offset_min = j["tz_offset_min"] | c.tz_offset_min;
    JsonArrayConst routine = j["routine"].as<JsonArrayConst>();
    if (routine.size() > proto::MAX_ROUTINE) return false;
    for (JsonObjectConst w : routine) {
        proto::RoutineWindow& item = c.routine[c.routine_count++];
        item.days = w["days"] | 0U;
        item.start_min = w["start_min"] | 0U;
        item.end_min = w["end_min"] | 0U;
    }
    if (!proto::config_valid(c)) return false;
    *out = c;
    return true;
}

inline proto::Command parse_command(const char* kind) {
    if (kind == nullptr) return proto::Command::None;
    if (strcmp(kind, "reboot") == 0) return proto::Command::Reboot;
    if (strcmp(kind, "factory_reset") == 0) return proto::Command::FactoryReset;
    if (strcmp(kind, "capture_now") == 0) return proto::Command::CaptureNow;
    return proto::Command::None;
}

struct Pending {
    bool has_config = false;
    proto::DeviceConfig config{};
    proto::Command command = proto::Command::None;
    uint16_t command_seq = 0U;
};

// O que falta repassar a cada transmissor. Fica em flash para que o gateway
// continue repassando mesmo sem falar com a API. Quem chama sincroniza o acesso.
class DeviceTable {
public:
    static constexpr uint8_t CAPACITY = 8U;
    struct Entry {
        uint32_t device_id = 0U;
        bool has_config = false;
        proto::DeviceConfig config{};
        proto::Command command = proto::Command::None;
        uint16_t command_seq = 0U;
        uint16_t radiated_config = 0U;
        uint16_t radiated_command = 0U;
    };

    // Devolve true se algo mudou. `config` nulo mantém o transmissor sem
    // configuração a repassar.
    bool set(uint32_t device_id, const proto::DeviceConfig* config, proto::Command command, uint16_t command_seq) {
        Entry* entry = find(device_id);
        if (entry == nullptr) {
            if (count_ == CAPACITY) return false;
            entry = &entries_[count_++];
            *entry = Entry{};
            entry->device_id = device_id;
        } else if (entry->has_config == (config != nullptr) &&
                   (config == nullptr || entry->config.version == config->version) &&
                   entry->command == command && entry->command_seq == command_seq) {
            return false;
        }
        entry->has_config = config != nullptr;
        if (config != nullptr) entry->config = *config;
        entry->command = command;
        entry->command_seq = command_seq;
        return true;
    }

    Pending pending_for(uint32_t device_id, uint16_t reported_config, uint16_t reported_command) const {
        Pending p;
        for (uint8_t i = 0U; i < count_; ++i) {
            const Entry& e = entries_[i];
            if (e.device_id != device_id) continue;
            if (e.has_config && e.config.version != reported_config) {
                p.has_config = true;
                p.config = e.config;
            }
            if (e.command != proto::Command::None && e.command_seq != reported_command) {
                p.command = e.command;
                p.command_seq = e.command_seq;
            }
        }
        return p;
    }

    void mark_radiated(uint32_t device_id, uint16_t config_version, uint16_t command_seq) {
        Entry* entry = find(device_id);
        if (entry == nullptr) return;
        if (config_version != 0U) entry->radiated_config = config_version;
        if (command_seq != 0U) entry->radiated_command = command_seq;
    }

    // A API só lista o que falta. Quem saiu da lista foi confirmado, mas o
    // registro do que foi transmitido continua sendo informado.
    void clear_except(const uint32_t* ids, uint8_t n) {
        for (uint8_t i = 0U; i < count_; ++i) {
            bool listed = false;
            for (uint8_t k = 0U; k < n; ++k) listed = listed || ids[k] == entries_[i].device_id;
            if (listed) continue;
            entries_[i].has_config = false;
            entries_[i].command = proto::Command::None;
        }
    }

    uint8_t count() const { return count_; }
    const Entry* entries() const { return entries_; }
    void restore(const Entry* entries, uint8_t count) {
        count_ = count <= CAPACITY ? count : CAPACITY;
        for (uint8_t i = 0U; i < count_; ++i) entries_[i] = entries[i];
    }

private:
    Entry* find(uint32_t device_id) {
        for (uint8_t i = 0U; i < count_; ++i) if (entries_[i].device_id == device_id) return &entries_[i];
        return nullptr;
    }
    Entry entries_[CAPACITY]{};
    uint8_t count_ = 0U;
};

// Remontagem de uma janela. O buffer é zerado por quem o entrega: fragmento que
// não chegar fica em zero e é listado em fragments_missing.
class WaveAssembler {
public:
    void begin(uint8_t* buffer, uint32_t bytes, uint16_t payload, uint16_t total) {
        buffer_ = buffer;
        bytes_ = bytes;
        payload_ = payload;
        total_ = total;
        memset(received_, 0, sizeof(received_));
        got_ = 0U;
        begin_round();
    }
    // A rodada termina ao chegar o maior índice que faltava no início dela.
    void begin_round() {
        round_last_ = 0U;
        for (uint16_t i = 0U; i < total_; ++i) if (!proto::bit_get(received_, i)) round_last_ = i;
    }
    bool add(uint16_t index, const uint8_t* data, size_t length) {
        if (buffer_ == nullptr || index >= total_) return false;
        const uint32_t offset = static_cast<uint32_t>(index) * payload_;
        const uint32_t expected = bytes_ - offset < payload_ ? bytes_ - offset : payload_;
        if (length != expected) return false;
        memcpy(buffer_ + offset, data, length);
        if (!proto::bit_get(received_, index)) {
            proto::bit_set(received_, index);
            ++got_;
        }
        return true;
    }
    bool round_finished(uint16_t index) const { return index >= round_last_; }
    bool complete() const { return got_ == total_; }
    uint16_t received_count() const { return got_; }
    uint16_t total() const { return total_; }
    const uint8_t* received() const { return received_; }

private:
    uint8_t* buffer_ = nullptr;
    uint32_t bytes_ = 0U;
    uint16_t payload_ = 0U, total_ = 0U, got_ = 0U, round_last_ = 0U;
    uint8_t received_[proto::BURST_MAP_BYTES]{};
};

} // namespace kaelix::gateway
