#pragma once

#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstring>

#include "crc16.h"

// Protocolo de rádio entre transmissor e gateway. Especificação:
// kaelix-Ai-center/docs/comando-e-coleta.md. Só lógica pura, sem Arduino, para
// que os dois lados e os testes no host usem exatamente o mesmo código.
namespace kaelix::protocol {

inline constexpr uint8_t VERSION = 3U;

enum class FrameType : uint8_t { Telemetry = 1U, Reply = 2U, Fragment = 3U, BurstMap = 4U };

// Bits de Telemetry::flags.
inline constexpr uint8_t FLAG_TIME_SYNCED = 1U << 0U;
inline constexpr uint8_t FLAG_WAVE_FOLLOWS = 1U << 1U;
inline constexpr uint8_t FLAG_FALLBACK = 1U << 2U;
inline constexpr uint8_t FLAG_CONFIG_REJECTED = 1U << 3U;
inline constexpr uint8_t FLAG_NO_MEASUREMENT = 1U << 4U;
inline constexpr uint8_t FLAG_SATURATED = 1U << 5U;

// Bits de Reply::flags.
inline constexpr uint8_t REPLY_BURST_GO = 1U << 0U;
inline constexpr uint8_t REPLY_HAS_CONFIG = 1U << 1U;
inline constexpr uint8_t REPLY_HAS_COMMAND = 1U << 2U;

enum class Command : uint8_t { None = 0U, Reboot = 1U, FactoryReset = 2U, CaptureNow = 3U };

inline constexpr size_t MAX_FRAME = 255U;
inline constexpr size_t FRAGMENT_PAYLOAD = 240U; // divisível por 2, 4, 6, 8, 10 e 12
inline constexpr size_t MAX_ROUTINE = 6U;
inline constexpr size_t BURST_MAP_BYTES = 32U;   // 256 fragmentos
inline constexpr uint32_t MAX_WINDOW_SAMPLES = 4096U;
inline constexpr uint32_t MAX_CHANNELS = 6U;
inline constexpr uint32_t MAX_WAVE_BYTES = MAX_WINDOW_SAMPLES * MAX_CHANNELS * 2U;

// O canal de controle é fixo no firmware, de propósito: nenhuma configuração
// remota pode deixar o transmissor numa frequência em que ninguém o escuta.
inline constexpr float CONTROL_FREQUENCY_MHZ = 433.0f;
inline constexpr uint8_t CONTROL_SF = 9U;
inline constexpr float CONTROL_BW_KHZ = 125.0f;
inline constexpr uint8_t CODING_RATE = 5U;
inline constexpr uint8_t SYNC_WORD = 0x12U;
inline constexpr uint16_t PREAMBLE_SYMBOLS = 8U;

struct BurstProfile {
    uint8_t sf;
    float bw_khz;
};
inline constexpr BurstProfile BURST_PROFILES[] = {{9U, 125.0f}, {7U, 125.0f}, {7U, 250.0f}, {7U, 500.0f}};
inline constexpr uint8_t BURST_PROFILE_COUNT = 4U;
inline constexpr uint8_t DEFAULT_BURST_PROFILE = 2U;

struct __attribute__((packed)) Telemetry {
    uint8_t version;
    uint8_t type;
    uint32_t device_id;
    uint32_t sequence;
    uint32_t boot_count;
    uint8_t state;
    uint8_t diag;
    uint8_t flags;
    uint8_t reset_reason;
    uint16_t config_version;
    uint16_t command_seq;
    uint32_t device_time; // UNIX, 0 se sem hora
    uint32_t uptime_s;
    float rms_z;
    float rms_x;
    float rms_y;
    float kurtosis;
    float crest_factor;
    float dominant_freq_hz;
    float sample_rate_hz;
    float temperature_c;
    uint8_t wave_fragments;
    uint8_t burst_profile;
    uint16_t wave_samples;
    uint8_t channels;
    uint8_t sensor_config; // bits 0-1 accel_range, 2-3 gyro_range, 4-6 dlpf
    int8_t tx_power_dbm;
    uint16_t crc;
};
static_assert(sizeof(Telemetry) == 71U, "layout da telemetria mudou: atualize VERSION e a especificação");

struct __attribute__((packed)) ReplyHeader {
    uint8_t version;
    uint8_t type;
    uint32_t device_id;
    uint32_t sequence; // eco da telemetria
    uint32_t utc;      // UNIX, 0 se o gateway está sem hora
    uint8_t flags;
    uint8_t command;
    uint16_t command_seq;
    uint8_t config_len;
    uint8_t reserved;
};
static_assert(sizeof(ReplyHeader) == 20U, "layout da resposta mudou");
inline constexpr size_t REPLY_MIN_FRAME = sizeof(ReplyHeader) + 2U;

struct __attribute__((packed)) FragmentHeader {
    uint8_t version;
    uint8_t type;
    uint32_t device_id;
    uint32_t sequence;
    uint8_t index;
    uint8_t total;
};
static_assert(sizeof(FragmentHeader) == 12U, "layout do fragmento mudou");

struct __attribute__((packed)) BurstMap {
    uint8_t version;
    uint8_t type;
    uint32_t device_id;
    uint32_t sequence;
    uint8_t received[BURST_MAP_BYTES];
    uint16_t crc;
};
static_assert(sizeof(BurstMap) == 44U, "layout do mapa da rajada mudou");

struct RoutineWindow {
    uint8_t days = 0U;      // bit 0 = domingo
    uint16_t start_min = 0U;
    uint16_t end_min = 0U;
};

struct DeviceConfig {
    uint16_t version = 0U; // 0 = configuração de fábrica
    uint16_t cycle_interval_s = 11U;
    uint16_t window_samples = 512U;
    uint8_t channels = 63U;
    uint8_t accel_range = 1U;
    uint8_t gyro_range = 0U;
    uint8_t dlpf = 1U;
    int8_t tx_power_dbm = 10;
    uint8_t burst_profile = DEFAULT_BURST_PROFILE;
    uint8_t wave_every = 1U;
    uint32_t link_loss_s = 900U;
    uint16_t checkin_interval_s = 300U;
    int16_t tz_offset_min = -180;
    uint8_t routine_count = 0U;
    RoutineWindow routine[MAX_ROUTINE]{};
};

inline constexpr size_t CONFIG_BASE_BYTES = 23U;
inline constexpr size_t CONFIG_ROUTINE_BYTES = 5U;
inline constexpr size_t CONFIG_MAX_BYTES = CONFIG_BASE_BYTES + MAX_ROUTINE * CONFIG_ROUTINE_BYTES;
inline constexpr size_t REPLY_MAX_FRAME = REPLY_MIN_FRAME + CONFIG_MAX_BYTES;

inline uint8_t pack_sensor_config(uint8_t accel_range, uint8_t gyro_range, uint8_t dlpf) {
    return static_cast<uint8_t>((accel_range & 3U) | ((gyro_range & 3U) << 2U) | ((dlpf & 7U) << 4U));
}

inline bool config_valid(const DeviceConfig& c) {
    if (c.cycle_interval_s < 1U || c.cycle_interval_s > 3600U) return false;
    if (c.window_samples != 256U && c.window_samples != 512U && c.window_samples != 1024U &&
        c.window_samples != 2048U && c.window_samples != 4096U) return false;
    if (c.channels < 1U || c.channels > 63U || (c.channels & 0x04U) == 0U) return false; // az é obrigatório
    if (c.accel_range > 3U || c.gyro_range > 3U || c.dlpf > 6U) return false;
    if (c.tx_power_dbm < 2 || c.tx_power_dbm > 17) return false;
    if (c.burst_profile >= BURST_PROFILE_COUNT) return false;
    if (c.link_loss_s < 60U || c.link_loss_s > 86400U) return false;
    if (c.checkin_interval_s < 60U || c.checkin_interval_s > 3600U) return false;
    if (c.tz_offset_min < -720 || c.tz_offset_min > 840) return false;
    if (c.routine_count > MAX_ROUTINE) return false;
    for (uint8_t i = 0U; i < c.routine_count; ++i) {
        const RoutineWindow& w = c.routine[i];
        if (w.days == 0U || w.days > 0x7FU || w.start_min > 1440U || w.end_min > 1440U || w.start_min == w.end_min) return false;
    }
    return true;
}

namespace detail {
inline void put16(uint8_t* p, uint16_t v) { p[0] = static_cast<uint8_t>(v); p[1] = static_cast<uint8_t>(v >> 8U); }
inline void put32(uint8_t* p, uint32_t v) { put16(p, static_cast<uint16_t>(v)); put16(p + 2, static_cast<uint16_t>(v >> 16U)); }
inline uint16_t get16(const uint8_t* p) { return static_cast<uint16_t>(p[0] | (static_cast<uint16_t>(p[1]) << 8U)); }
inline uint32_t get32(const uint8_t* p) { return get16(p) | (static_cast<uint32_t>(get16(p + 2)) << 16U); }
} // namespace detail

// Devolve o número de bytes escritos, ou 0 se a configuração for inválida.
inline size_t encode_config(const DeviceConfig& c, uint8_t* out, size_t capacity) {
    const size_t size = CONFIG_BASE_BYTES + c.routine_count * CONFIG_ROUTINE_BYTES;
    if (out == nullptr || !config_valid(c) || capacity < size) return 0U;
    detail::put16(out, c.version);
    detail::put16(out + 2, c.cycle_interval_s);
    detail::put16(out + 4, c.window_samples);
    out[6] = c.channels;
    out[7] = c.accel_range;
    out[8] = c.gyro_range;
    out[9] = c.dlpf;
    out[10] = static_cast<uint8_t>(c.tx_power_dbm);
    out[11] = c.burst_profile;
    out[12] = c.wave_every;
    out[13] = 0U;
    detail::put32(out + 14, c.link_loss_s);
    detail::put16(out + 18, c.checkin_interval_s);
    detail::put16(out + 20, static_cast<uint16_t>(c.tz_offset_min));
    out[22] = c.routine_count;
    for (uint8_t i = 0U; i < c.routine_count; ++i) {
        uint8_t* item = out + CONFIG_BASE_BYTES + i * CONFIG_ROUTINE_BYTES;
        item[0] = c.routine[i].days;
        detail::put16(item + 1, c.routine[i].start_min);
        detail::put16(item + 3, c.routine[i].end_min);
    }
    return size;
}

// Em erro, *out não é escrito.
inline bool decode_config(const uint8_t* bytes, size_t length, DeviceConfig* out) {
    if (bytes == nullptr || out == nullptr || length < CONFIG_BASE_BYTES) return false;
    DeviceConfig c{};
    c.version = detail::get16(bytes);
    c.cycle_interval_s = detail::get16(bytes + 2);
    c.window_samples = detail::get16(bytes + 4);
    c.channels = bytes[6];
    c.accel_range = bytes[7];
    c.gyro_range = bytes[8];
    c.dlpf = bytes[9];
    c.tx_power_dbm = static_cast<int8_t>(bytes[10]);
    c.burst_profile = bytes[11];
    c.wave_every = bytes[12];
    c.link_loss_s = detail::get32(bytes + 14);
    c.checkin_interval_s = detail::get16(bytes + 18);
    c.tz_offset_min = static_cast<int16_t>(detail::get16(bytes + 20));
    c.routine_count = bytes[22];
    if (c.routine_count > MAX_ROUTINE || length != CONFIG_BASE_BYTES + c.routine_count * CONFIG_ROUTINE_BYTES) return false;
    for (uint8_t i = 0U; i < c.routine_count; ++i) {
        const uint8_t* item = bytes + CONFIG_BASE_BYTES + i * CONFIG_ROUTINE_BYTES;
        c.routine[i].days = item[0];
        c.routine[i].start_min = detail::get16(item + 1);
        c.routine[i].end_min = detail::get16(item + 3);
    }
    if (!config_valid(c)) return false;
    *out = c;
    return true;
}

// ---------------------------------------------------------------------
// Quadros
// ---------------------------------------------------------------------

inline void seal(uint8_t* frame, size_t size) {
    detail::put16(frame + size - 2U, comms::crc16_ccitt(frame, size - 2U));
}

inline bool frame_ok(const uint8_t* bytes, size_t length, FrameType type, size_t minimum) {
    if (bytes == nullptr || length < minimum || length > MAX_FRAME) return false;
    if (bytes[0] != VERSION || bytes[1] != static_cast<uint8_t>(type)) return false;
    return comms::crc16_ccitt(bytes, length - 2U) == detail::get16(bytes + length - 2U);
}

inline void seal_telemetry(Telemetry* t) {
    t->version = VERSION;
    t->type = static_cast<uint8_t>(FrameType::Telemetry);
    seal(reinterpret_cast<uint8_t*>(t), sizeof(*t));
}

// Sem medição válida, RMS é NaN; inf nunca é aceito.
inline bool decode_telemetry(const uint8_t* bytes, size_t length, Telemetry* out) {
    if (out == nullptr || length != sizeof(Telemetry) || !frame_ok(bytes, length, FrameType::Telemetry, sizeof(Telemetry))) return false;
    Telemetry t{};
    std::memcpy(&t, bytes, sizeof(t));
    const float values[] = {t.rms_z, t.rms_x, t.rms_y, t.kurtosis, t.crest_factor, t.dominant_freq_hz, t.sample_rate_hz, t.temperature_c};
    for (float value : values) if (std::isinf(value)) return false;
    if (std::isfinite(t.rms_z) && t.rms_z < 0.0f) return false;
    if (t.state > 2U) return false;
    if (t.burst_profile >= BURST_PROFILE_COUNT) return false;
    *out = t;
    return true;
}

// Devolve o tamanho do quadro. `config` pode ser nulo.
inline size_t encode_reply(uint32_t device_id, uint32_t sequence, uint32_t utc, bool burst_go,
                           const DeviceConfig* config, Command command, uint16_t command_seq,
                           uint8_t* out, size_t capacity) {
    if (out == nullptr || capacity < REPLY_MAX_FRAME) return 0U;
    ReplyHeader header{};
    header.version = VERSION;
    header.type = static_cast<uint8_t>(FrameType::Reply);
    header.device_id = device_id;
    header.sequence = sequence;
    header.utc = utc;
    if (burst_go) header.flags |= REPLY_BURST_GO;
    size_t config_len = 0U;
    if (config != nullptr) {
        config_len = encode_config(*config, out + sizeof(header), CONFIG_MAX_BYTES);
        if (config_len == 0U) return 0U;
        header.flags |= REPLY_HAS_CONFIG;
    }
    if (command != Command::None) {
        header.flags |= REPLY_HAS_COMMAND;
        header.command = static_cast<uint8_t>(command);
        header.command_seq = command_seq;
    }
    header.config_len = static_cast<uint8_t>(config_len);
    std::memcpy(out, &header, sizeof(header));
    const size_t size = sizeof(header) + config_len + 2U;
    seal(out, size);
    return size;
}

struct Reply {
    ReplyHeader header{};
    bool has_config = false;
    bool config_rejected = false;
    DeviceConfig config{};
};

// Uma configuração recusada não invalida a resposta: a confirmação e a hora
// continuam valendo, e a recusa volta ao software pela telemetria.
inline bool decode_reply(const uint8_t* bytes, size_t length, uint32_t device_id, Reply* out) {
    if (out == nullptr || !frame_ok(bytes, length, FrameType::Reply, REPLY_MIN_FRAME)) return false;
    Reply r{};
    std::memcpy(&r.header, bytes, sizeof(r.header));
    if (r.header.device_id != device_id) return false;
    if (length != REPLY_MIN_FRAME + r.header.config_len) return false;
    if ((r.header.flags & REPLY_HAS_CONFIG) != 0U) {
        r.has_config = decode_config(bytes + sizeof(r.header), r.header.config_len, &r.config);
        r.config_rejected = !r.has_config;
    }
    *out = r;
    return true;
}

inline uint8_t channel_count(uint8_t mask) {
    uint8_t n = 0U;
    for (uint8_t bit = 0U; bit < MAX_CHANNELS; ++bit) n = static_cast<uint8_t>(n + ((mask >> bit) & 1U));
    return n;
}

inline uint32_t wave_bytes(uint16_t window_samples, uint8_t channels) {
    return static_cast<uint32_t>(window_samples) * channel_count(channels) * 2U;
}

inline uint16_t fragment_payload(uint8_t channels) {
    const uint16_t frame = static_cast<uint16_t>(channel_count(channels) * 2U);
    return frame == 0U ? 0U : static_cast<uint16_t>(FRAGMENT_PAYLOAD - FRAGMENT_PAYLOAD % frame);
}

inline uint16_t fragment_count(uint16_t window_samples, uint8_t channels) {
    const uint16_t payload = fragment_payload(channels);
    if (payload == 0U) return 0U;
    const uint32_t bytes = wave_bytes(window_samples, channels);
    return static_cast<uint16_t>((bytes + payload - 1U) / payload);
}

inline size_t encode_fragment(uint32_t device_id, uint32_t sequence, uint8_t index, uint8_t total,
                              const uint8_t* payload, size_t payload_len, uint8_t* out, size_t capacity) {
    const size_t size = sizeof(FragmentHeader) + payload_len + 2U;
    if (out == nullptr || payload == nullptr || payload_len == 0U || size > capacity || size > MAX_FRAME) return 0U;
    FragmentHeader header{VERSION, static_cast<uint8_t>(FrameType::Fragment), device_id, sequence, index, total};
    std::memcpy(out, &header, sizeof(header));
    std::memcpy(out + sizeof(header), payload, payload_len);
    seal(out, size);
    return size;
}

inline bool decode_fragment(const uint8_t* bytes, size_t length, FragmentHeader* header, const uint8_t** payload, size_t* payload_len) {
    if (header == nullptr || payload == nullptr || payload_len == nullptr) return false;
    if (!frame_ok(bytes, length, FrameType::Fragment, sizeof(FragmentHeader) + 3U)) return false;
    std::memcpy(header, bytes, sizeof(*header));
    if (header->total == 0U || header->index >= header->total) return false;
    *payload = bytes + sizeof(FragmentHeader);
    *payload_len = length - sizeof(FragmentHeader) - 2U;
    return true;
}

inline void seal_burst_map(BurstMap* m) {
    m->version = VERSION;
    m->type = static_cast<uint8_t>(FrameType::BurstMap);
    seal(reinterpret_cast<uint8_t*>(m), sizeof(*m));
}

inline bool decode_burst_map(const uint8_t* bytes, size_t length, BurstMap* out) {
    if (out == nullptr || length != sizeof(BurstMap) || !frame_ok(bytes, length, FrameType::BurstMap, sizeof(BurstMap))) return false;
    std::memcpy(out, bytes, sizeof(*out));
    return true;
}

inline bool bit_get(const uint8_t* map, uint16_t index) { return (map[index / 8U] >> (index % 8U)) & 1U; }
inline void bit_set(uint8_t* map, uint16_t index) { map[index / 8U] = static_cast<uint8_t>(map[index / 8U] | (1U << (index % 8U))); }

// ---------------------------------------------------------------------
// Tempo no ar e esperas da rajada
// ---------------------------------------------------------------------

inline uint32_t airtime_ms(size_t payload, uint8_t sf, float bw_khz) {
    const float symbol = static_cast<float>(1U << sf) / bw_khz;
    const int32_t numerator = 8 * static_cast<int32_t>(payload) - 4 * sf + 44;
    const int32_t blocks = numerator <= 0 ? 0 : (numerator + 4 * sf - 1) / (4 * sf);
    const float symbols = static_cast<float>(PREAMBLE_SYMBOLS) + 4.25f + 8.0f + static_cast<float>(blocks * 5);
    return static_cast<uint32_t>(std::ceil(symbols * symbol));
}

inline constexpr uint32_t FRAGMENT_GAP_MS = 50U;
inline constexpr uint8_t BURST_ROUNDS = 3U;       // envio inicial e duas retransmissões
inline constexpr uint32_t REPLY_WINDOW_MS = 300U; // da telemetria ao início da resposta
inline constexpr uint32_t REPLY_TURNAROUND_MS = 20U;
inline constexpr uint32_t BURST_START_DELAY_MS = 120U; // o gateway troca de perfil e grava a leitura

// Sem fragmento por este tempo, o gateway encerra a rodada e envia o mapa.
inline uint32_t burst_idle_ms(uint8_t profile) {
    const BurstProfile p = BURST_PROFILES[profile < BURST_PROFILE_COUNT ? profile : 0U];
    return 2U * (airtime_ms(sizeof(FragmentHeader) + FRAGMENT_PAYLOAD + 2U, p.sf, p.bw_khz) + FRAGMENT_GAP_MS);
}

// O transmissor espera o mapa pelo pior caso da espera do gateway.
inline uint32_t burst_map_wait_ms(uint8_t profile) {
    const BurstProfile p = BURST_PROFILES[profile < BURST_PROFILE_COUNT ? profile : 0U];
    return burst_idle_ms(profile) + airtime_ms(sizeof(BurstMap), p.sf, p.bw_khz) + 200U;
}

// ---------------------------------------------------------------------
// Rotina
// ---------------------------------------------------------------------

namespace detail {
inline int64_t local_seconds(int64_t utc, int16_t tz_offset_min) { return utc + static_cast<int64_t>(tz_offset_min) * 60; }
inline int day_of_week(int64_t days) { return static_cast<int>(((days + 4) % 7 + 7) % 7); } // 1970-01-01 foi quinta
inline int64_t floor_div(int64_t a, int64_t b) { return a >= 0 ? a / b : -((-a + b - 1) / b); }
}

// Sem janelas, o transmissor fica sempre ativo.
inline bool routine_active(const DeviceConfig& c, int64_t utc) {
    if (c.routine_count == 0U) return true;
    const int64_t local = detail::local_seconds(utc, c.tz_offset_min);
    const int64_t days = detail::floor_div(local, 86400);
    const int minute = static_cast<int>((local - days * 86400) / 60);
    const int today = detail::day_of_week(days), yesterday = (today + 6) % 7;
    for (uint8_t i = 0U; i < c.routine_count; ++i) {
        const RoutineWindow& w = c.routine[i];
        if (w.start_min < w.end_min) {
            if (((w.days >> today) & 1U) != 0U && minute >= w.start_min && minute < w.end_min) return true;
        } else {
            if (((w.days >> today) & 1U) != 0U && minute >= w.start_min) return true;
            if (((w.days >> yesterday) & 1U) != 0U && minute < w.end_min) return true;
        }
    }
    return false;
}

// Segundos até a próxima abertura de janela; 0 se já estiver ativa.
inline uint32_t seconds_until_active(const DeviceConfig& c, int64_t utc) {
    if (routine_active(c, utc)) return 0U;
    const int64_t local = detail::local_seconds(utc, c.tz_offset_min);
    const int64_t days = detail::floor_div(local, 86400);
    int64_t best = INT64_MAX;
    for (int offset = 0; offset <= 7; ++offset) {
        const int dow = detail::day_of_week(days + offset);
        for (uint8_t i = 0U; i < c.routine_count; ++i) {
            if (((c.routine[i].days >> dow) & 1U) == 0U) continue;
            const int64_t start = (days + offset) * 86400 + static_cast<int64_t>(c.routine[i].start_min) * 60;
            if (start > local && start - local < best) best = start - local;
        }
    }
    return best == INT64_MAX ? 0U : static_cast<uint32_t>(best);
}

// ---------------------------------------------------------------------
// Perda de comando
// ---------------------------------------------------------------------

// Como o Command Loss das sondas: sem ouvir o gateway por link_loss_s, o
// transmissor desfaz a configuração não confirmada e, se o silêncio continuar,
// sobe a potência e ignora a rotina. Em nenhum caso para de medir.
struct LinkState {
    uint32_t silent_s = 0U;
    bool tentative = false; // configuração nova, ainda sem resposta do gateway
    bool fallback = false;
};

enum class LinkAction : uint8_t { None, CommitConfig, RevertConfig, EnterFallback, LeaveFallback };

inline LinkAction link_update(LinkState& s, bool heard, uint32_t elapsed_s, uint32_t link_loss_s) {
    if (heard) {
        s.silent_s = 0U;
        if (s.tentative) {
            s.tentative = false;
            return LinkAction::CommitConfig;
        }
        if (s.fallback) {
            s.fallback = false;
            return LinkAction::LeaveFallback;
        }
        return LinkAction::None;
    }
    s.silent_s = (UINT32_MAX - s.silent_s < elapsed_s) ? UINT32_MAX : s.silent_s + elapsed_s;
    if (s.silent_s < link_loss_s) return LinkAction::None;
    if (s.tentative) {
        s.tentative = false;
        s.silent_s = 0U; // a configuração anterior ganha o mesmo prazo
        return LinkAction::RevertConfig;
    }
    if (!s.fallback) {
        s.fallback = true;
        return LinkAction::EnterFallback;
    }
    return LinkAction::None;
}

} // namespace kaelix::protocol
