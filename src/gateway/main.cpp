#include <Arduino.h>
#include <RadioLib.h>
#include <SPI.h>
#include <esp_task_wdt.h>

#include "../receiver/gateway_pins.h"
#include "../serial_log.h"
#include "network.h"

// Tarefa do rádio. É a única que toca o SPI, e nada aqui espera flash ou rede:
// o transmissor só escuta por 300 ms depois de transmitir.
namespace {
using namespace kaelix::receiver::pins;
namespace proto = kaelix::protocol;
namespace gw = kaelix::gateway;
namespace net = kaelix::gateway::net;
using kaelix::logging::log;

constexpr uint8_t IRQ_RX_DONE = 0x40U;
constexpr uint32_t HEALTH_INTERVAL_MS = 5000U;

Module module(CS_PIN, DIO0_PIN, RESET_PIN, RADIOLIB_NC, SPI, SPISettings(100000, MSBFIRST, SPI_MODE0));
SX1278 radio(&module);
volatile bool dio0_rose = false;
bool receiving = false;
uint32_t last_attempt = 0U, last_poll = 0U, last_health = 0U;
uint32_t received = 0U, refused = 0U, waves = 0U;
int8_t applied_power = 0;

void IRAM_ATTR on_dio0() { dio0_rose = true; }

bool start_listening() {
    dio0_rose = false;
    const int16_t result = radio.startReceive();
    if (result != RADIOLIB_ERR_NONE) {
        net::spi_error();
        log("gateway", "ERROR", "RADIO", "start_rx error=%d", result);
    }
    return result == RADIOLIB_ERR_NONE;
}

bool set_modem(uint8_t sf, float bw) {
    return radio.standby() == RADIOLIB_ERR_NONE && radio.setSpreadingFactor(sf) == RADIOLIB_ERR_NONE &&
           radio.setBandwidth(bw) == RADIOLIB_ERR_NONE;
}

bool initialize_radio() {
    const int16_t result = radio.begin(proto::CONTROL_FREQUENCY_MHZ, proto::CONTROL_BW_KHZ, proto::CONTROL_SF,
                                       proto::CODING_RATE, proto::SYNC_WORD, net::tx_power_dbm(), proto::PREAMBLE_SYMBOLS);
    log("gateway", result == RADIOLIB_ERR_NONE ? "INFO" : "ERROR", "RADIO", "rf_init=%d version=0x%02X", result,
        static_cast<unsigned>(static_cast<uint16_t>(radio.getChipVersion())));
    if (result != RADIOLIB_ERR_NONE) {
        net::spi_error();
        return false;
    }
    applied_power = net::tx_power_dbm();
    radio.setDio0Action(on_dio0, RISING);
    return start_listening();
}

// Nova leitura pronta no FIFO? Consulta o SPI também, para não depender de a
// borda de DIO0 ter sido vista.
bool packet_ready(uint32_t poll_ms) {
    const uint32_t now = millis();
    if (!dio0_rose && now - last_poll < poll_ms) return false;
    last_poll = now;
    return (radio.getIRQFlags() & IRQ_RX_DONE) != 0U;
}

// O transmissor abre a recepção logo depois de transmitir. A espera garante que
// o preâmbulo não comece antes disso.
void transmit_after_turnaround(const uint8_t* bytes, size_t size, uint32_t since_ms) {
    const uint32_t elapsed = millis() - since_ms;
    if (elapsed < proto::REPLY_TURNAROUND_MS) delay(proto::REPLY_TURNAROUND_MS - elapsed);
    const int16_t result = radio.transmit(bytes, size);
    if (result != RADIOLIB_ERR_NONE) log("gateway", "ERROR", "RADIO", "tx error=%d size=%u", result, static_cast<unsigned>(size));
}

// Recebe a rajada: até BURST_ROUNDS rodadas, cada uma encerrada pelo maior
// fragmento que faltava ou por silêncio, com um mapa do que chegou.
void receive_burst(const proto::Telemetry& t, uint32_t event_seq, uint64_t rx_ms, uint32_t rx_utc, uint8_t* record, uint32_t wave_size) {
    const proto::BurstProfile profile = proto::BURST_PROFILES[t.burst_profile];
    const uint32_t idle_ms = proto::burst_idle_ms(t.burst_profile);
    gw::WaveAssembler assembler;
    assembler.begin(record + sizeof(gw::WaveRecord), wave_size, proto::fragment_payload(t.channels), t.wave_fragments);
    uint8_t frame[proto::MAX_FRAME];
    const uint32_t started = millis();
    if (!set_modem(profile.sf, profile.bw_khz)) {
        net::spi_error();
    } else {
        for (uint8_t round = 0U; round < proto::BURST_ROUNDS; ++round) {
            start_listening();
            uint32_t last_seen = millis();
            uint32_t finished_at = 0U;
            // O transmissor pode estar gravando uma configuração nova antes de começar.
            uint32_t wait_ms = round == 0U ? idle_ms + proto::BURST_START_DELAY_MS + 400U : idle_ms;
            while (millis() - last_seen < wait_ms) {
                esp_task_wdt_reset();
                if (!packet_ready(2U)) { delay(1); continue; }
                const uint32_t done_at = millis();
                const size_t length = radio.getPacketLength();
                const int16_t result = (length > 0U && length <= sizeof(frame)) ? radio.readData(frame, length) : RADIOLIB_ERR_PACKET_TOO_LONG;
                proto::FragmentHeader header{};
                const uint8_t* payload = nullptr;
                size_t payload_len = 0U;
                last_seen = done_at;
                wait_ms = idle_ms;
                if (result == RADIOLIB_ERR_NONE && proto::decode_fragment(frame, length, &header, &payload, &payload_len) &&
                    header.device_id == t.device_id && header.sequence == t.sequence && header.total == t.wave_fragments) {
                    assembler.add(header.index, payload, payload_len);
                    if (assembler.round_finished(header.index)) {
                        finished_at = done_at;
                        break;
                    }
                } else {
                    net::rejected();
                }
                start_listening();
            }
            // Sem nenhum fragmento o transmissor não entrou na rajada: ele não
            // ouviu a autorização e não está esperando mapa.
            if (assembler.received_count() == 0U) break;
            proto::BurstMap map{};
            map.device_id = t.device_id;
            map.sequence = t.sequence;
            memcpy(map.received, assembler.received(), sizeof(map.received));
            proto::seal_burst_map(&map);
            transmit_after_turnaround(reinterpret_cast<const uint8_t*>(&map), sizeof(map), finished_at != 0U ? finished_at : millis());
            if (assembler.complete()) break;
            assembler.begin_round();
        }
        if (!set_modem(proto::CONTROL_SF, proto::CONTROL_BW_KHZ)) net::spi_error();
    }
    const uint16_t got = assembler.received_count();
    log("gateway", got == t.wave_fragments ? "INFO" : "WARN", "WAVE", "seq=%lu fragments=%u/%u took=%lums",
        static_cast<unsigned long>(t.sequence), static_cast<unsigned>(got), static_cast<unsigned>(t.wave_fragments),
        static_cast<unsigned long>(millis() - started));
    if (got == 0U) {
        free(record);
        return;
    }
    ++waves;
    auto* header = reinterpret_cast<gw::WaveRecord*>(record);
    memcpy(header->session, net::session(), sizeof(header->session));
    header->event_seq = event_seq;
    header->rx_uptime_ms = rx_ms;
    header->rx_utc = rx_utc;
    header->telemetry = t;
    header->fragment_total = t.wave_fragments;
    header->sample_bytes = wave_size;
    memcpy(header->received, assembler.received(), sizeof(header->received));
    net::store_wave(record, static_cast<uint32_t>(sizeof(gw::WaveRecord) + wave_size));
}

void handle_telemetry(const proto::Telemetry& t, float rssi, float snr, uint32_t done_at) {
    ++received;
    net::reading_valid();
    const uint64_t rx_ms = static_cast<uint64_t>(esp_timer_get_time()) / 1000ULL;
    const uint32_t rx_utc = net::utc_now();
    const uint32_t event_seq = net::next_event_seq();

    // Reservar a memória antes de autorizar: sem ela, a rajada nem começa.
    uint8_t* wave = nullptr;
    const bool wave_follows = (t.flags & proto::FLAG_WAVE_FOLLOWS) != 0U && t.wave_fragments > 0U;
    const uint32_t wave_size = wave_follows ? proto::wave_bytes(t.wave_samples, t.channels) : 0U;
    if (wave_follows && wave_size > 0U && wave_size <= proto::MAX_WAVE_BYTES &&
        proto::fragment_count(t.wave_samples, t.channels) == t.wave_fragments) {
        wave = static_cast<uint8_t*>(ps_calloc(1U, sizeof(gw::WaveRecord) + wave_size));
    }

    const gw::Pending pending = net::pending_for(t.device_id, t.config_version, t.command_seq);
    uint8_t frame[proto::REPLY_MAX_FRAME];
    const size_t size = proto::encode_reply(t.device_id, t.sequence, rx_utc, wave != nullptr,
                                            pending.has_config ? &pending.config : nullptr,
                                            pending.command, pending.command_seq, frame, sizeof(frame));
    if (applied_power != net::tx_power_dbm() && radio.setOutputPower(net::tx_power_dbm()) == RADIOLIB_ERR_NONE) applied_power = net::tx_power_dbm();
    if (size == 0U) {
        log("gateway", "ERROR", "RELAY", "reply encode failed id=%08lX", static_cast<unsigned long>(t.device_id));
    } else {
        transmit_after_turnaround(frame, size, done_at);
        net::mark_radiated(t.device_id, pending.has_config ? pending.config.version : 0U, pending.command_seq);
    }

    // Gravar só depois de responder, para que o log não atrase a resposta.
    gw::ReadingRecord record{};
    memcpy(record.session, net::session(), sizeof(record.session));
    record.event_seq = event_seq;
    record.rx_uptime_ms = rx_ms;
    record.rx_utc = rx_utc;
    record.rssi = rssi;
    record.snr = snr;
    record.telemetry = t;
    net::store_reading(record);
    log("gateway", "INFO", "RX", "id=%08lX seq=%lu diag=0x%02X rms=%.6f kurt=%.3f crest=%.3f freq=%.2f fs=%.2f temp=%.1f flags=0x%02X cfg=%u rssi=%.1f snr=%.1f%s%s",
        static_cast<unsigned long>(t.device_id), static_cast<unsigned long>(t.sequence), t.diag,
        t.rms_z, t.kurtosis, t.crest_factor, t.dominant_freq_hz, t.sample_rate_hz, t.temperature_c, t.flags,
        t.config_version, rssi, snr, pending.has_config ? " relay=config" : "",
        pending.command != proto::Command::None ? " relay=command" : "");

    if (wave != nullptr) receive_burst(t, event_seq, rx_ms, rx_utc, wave, wave_size);
    else if (wave_follows) log("gateway", "WARN", "WAVE", "seq=%lu refused: fragments=%u samples=%u", static_cast<unsigned long>(t.sequence), t.wave_fragments, t.wave_samples);
}
} // namespace

void setup() {
    Serial.begin(115200);
    delay(500); // não depender do computador estar conectado para começar
    net::begin();
    log("gateway", "INFO", "BOOT", "S3 RX SCK=%u MISO=%u MOSI=%u CS=%u RST=%u DIO0=%u protocol=v%u",
        SCK_PIN, MISO_PIN, MOSI_PIN, CS_PIN, RESET_PIN, DIO0_PIN, proto::VERSION);
    esp_task_wdt_add(nullptr);
    SPI.begin(SCK_PIN, MISO_PIN, MOSI_PIN, CS_PIN);
    if (SPI.bus() == nullptr) {
        log("gateway", "ERROR", "SPI", "SPI_INIT_FAILED");
        return;
    }
    receiving = initialize_radio();
    last_attempt = millis();
}

void loop() {
    esp_task_wdt_reset();
    net::radio_health(receiving);
    if (!receiving) {
        if (SPI.bus() != nullptr && millis() - last_attempt >= 5000U) {
            last_attempt = millis();
            receiving = initialize_radio();
        }
        delay(10);
        return;
    }
    const uint32_t now = millis();
    if (now - last_health >= HEALTH_INTERVAL_MS) {
        last_health = now;
        const uint8_t version = module.SPIreadRegister(0x42);
        log("gateway", version == 0x12 ? "DEBUG" : "ERROR", "HEALTH", "version=0x%02X op=0x%02X rx=%lu refused=%lu waves=%lu",
            version, module.SPIreadRegister(0x01), static_cast<unsigned long>(received), static_cast<unsigned long>(refused), static_cast<unsigned long>(waves));
        if (version != 0x12) {
            net::spi_error();
            receiving = false;
            last_attempt = now;
            return;
        }
    }
    if (!packet_ready(10U)) {
        delay(1);
        return;
    }
    // Flags lidos por SPI não provam pacote se o barramento perdeu o chip.
    if (module.SPIreadRegister(0x42) != 0x12 || module.SPIreadRegister(0x42) != 0x12) {
        log("gateway", "ERROR", "SPI", "SPI_UNSTABLE; retry initialization");
        net::spi_error();
        receiving = false;
        last_attempt = now;
        return;
    }
    const uint32_t done_at = millis();
    uint8_t bytes[proto::MAX_FRAME]{};
    const size_t length = radio.getPacketLength();
    const int16_t result = (length > 0U && length <= sizeof(bytes)) ? radio.readData(bytes, length) : RADIOLIB_ERR_PACKET_TOO_LONG;
    proto::Telemetry telemetry{};
    if (result == RADIOLIB_ERR_NONE && proto::decode_telemetry(bytes, length, &telemetry)) {
        const float rssi = radio.getRSSI();
        const float snr = radio.getSNR();
        handle_telemetry(telemetry, rssi, snr, done_at);
    } else {
        ++refused;
        net::rejected();
        log("gateway", "WARN", "REJECT", "read=%d length=%u first=0x%02X", result, static_cast<unsigned>(length), bytes[0]);
    }
    receiving = start_listening();
}
