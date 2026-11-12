#include "link.h"

#include <Arduino.h>
#include <RadioLib.h>
#include <SPI.h>
#include <driver/gpio.h>

#include "../device_pins.h"
#include "../serial_log.h"
#include "kaelix_protocol.h"

namespace kaelix::transmitter::link {
namespace {
namespace proto = kaelix::protocol;
using kaelix::Status;

constexpr uint8_t IRQ_RX_DONE = 0x40U, IRQ_VALID_HEADER = 0x10U;

Module module(kaelix::device::LORA_CS, kaelix::device::LORA_DIO0, kaelix::device::LORA_RST, RADIOLIB_NC,
              SPI, SPISettings(100000U, MSBFIRST, SPI_MODE0));
SX1278 radio(&module);
bool s_spi_started = false;

Status from_radiolib(int16_t state, Status fallback) {
    switch (state) {
        case RADIOLIB_ERR_NONE: return Status::Ok;
        case RADIOLIB_ERR_CHIP_NOT_FOUND: return Status::RadioAbsent;
        case RADIOLIB_ERR_INVALID_FREQUENCY:
        case RADIOLIB_ERR_INVALID_OUTPUT_POWER:
        case RADIOLIB_ERR_INVALID_BANDWIDTH:
        case RADIOLIB_ERR_INVALID_SPREADING_FACTOR:
        case RADIOLIB_ERR_INVALID_CODING_RATE: return Status::RadioConfigRejected;
        case RADIOLIB_ERR_TX_TIMEOUT: return Status::RadioTxTimeout;
        case RADIOLIB_ERR_PACKET_TOO_LONG: return Status::PayloadTooLong;
        default: return fallback;
    }
}

Status set_modem(uint8_t sf, float bw) {
    KAELIX_CHECK(from_radiolib(radio.standby(), Status::RadioConfigRejected));
    KAELIX_CHECK(from_radiolib(radio.setSpreadingFactor(sf), Status::RadioConfigRejected));
    return from_radiolib(radio.setBandwidth(bw), Status::RadioConfigRejected);
}
} // namespace

Status init(int8_t tx_power_dbm) {
    if (!s_spi_started) {
        SPI.begin(kaelix::device::LORA_SCK, kaelix::device::LORA_MISO, kaelix::device::LORA_MOSI, kaelix::device::LORA_CS);
        if (SPI.bus() == nullptr) return Status::RadioBusSilent;
        s_spi_started = true;
    }
    const int16_t state = radio.begin(proto::CONTROL_FREQUENCY_MHZ, proto::CONTROL_BW_KHZ, proto::CONTROL_SF, proto::CODING_RATE,
                                      proto::SYNC_WORD, tx_power_dbm, proto::PREAMBLE_SYMBOLS);
    kaelix::logging::log("kaelix", state == RADIOLIB_ERR_NONE ? "INFO" : "ERROR", "RADIO", "begin=%d power=%d", state, tx_power_dbm);
    return from_radiolib(state, Status::RadioConfigRejected);
}

Status set_power(int8_t tx_power_dbm) { return from_radiolib(radio.setOutputPower(tx_power_dbm), Status::RadioConfigRejected); }
Status use_control() { return set_modem(proto::CONTROL_SF, proto::CONTROL_BW_KHZ); }
Status use_burst(uint8_t profile) {
    const proto::BurstProfile p = proto::BURST_PROFILES[profile < proto::BURST_PROFILE_COUNT ? profile : proto::DEFAULT_BURST_PROFILE];
    return set_modem(p.sf, p.bw_khz);
}
Status send(const uint8_t* bytes, size_t size) { return from_radiolib(radio.transmit(bytes, size), Status::RadioTxFailed); }

bool receive(uint8_t* bytes, size_t capacity, size_t* length, uint32_t header_ms, uint32_t frame_ms) {
    if (radio.startReceive() != RADIOLIB_ERR_NONE) return false;
    const uint32_t started = millis();
    for (;;) {
        const uint32_t flags = radio.getIRQFlags();
        if ((flags & IRQ_RX_DONE) != 0U) break;
        const uint32_t limit = (flags & IRQ_VALID_HEADER) != 0U ? header_ms + frame_ms : header_ms;
        if (millis() - started > limit) {
            (void)radio.standby();
            return false;
        }
        delay(1);
    }
    const size_t size = radio.getPacketLength();
    if (size == 0U || size > capacity) {
        (void)radio.standby();
        return false;
    }
    const int16_t state = radio.readData(bytes, size);
    (void)radio.standby();
    if (state != RADIOLIB_ERR_NONE) return false;
    *length = size;
    return true;
}

Status sleep() {
    const Status status = from_radiolib(radio.sleep(), Status::RadioSleepFailed);
    if (kaelix::is_ok(status) && radio.getChipVersion() != 0x12) return Status::RadioSleepFailed;
    return status;
}

void hold_pins_for_deep_sleep() {
    gpio_hold_en(static_cast<gpio_num_t>(kaelix::device::LORA_CS));
    gpio_hold_en(static_cast<gpio_num_t>(kaelix::device::LORA_RST));
    gpio_deep_sleep_hold_en();
}

void release_pins_after_wake() {
    gpio_deep_sleep_hold_dis();
    gpio_hold_dis(static_cast<gpio_num_t>(kaelix::device::LORA_CS));
    gpio_hold_dis(static_cast<gpio_num_t>(kaelix::device::LORA_RST));
}

} // namespace kaelix::transmitter::link
