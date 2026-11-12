#include "network.h"

#include <ESPmDNS.h>
#include <HTTPClient.h>
#include <LittleFS.h>
#include <Preferences.h>
#include <Update.h>
#include <WebServer.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <WiFiMulti.h>
#include <esp_ota_ops.h>
#include <esp_system.h>
#include <esp_task_wdt.h>
#include <mbedtls/base64.h>
#include <mbedtls/sha256.h>
#include <sys/time.h>

#include <algorithm>
#include <atomic>

#include "../receiver/log_buffer.h"
#include "../serial_log.h"
#include "spool.h"

extern "C" bool verifyRollbackLater() { return true; } // quem confirma é a primeira sincronização

namespace kaelix::gateway::net {
namespace {
using kaelix::logging::log;
using kaelix::receiver::LogBuffer;
using kaelix::receiver::RemoteLog;

#ifndef KAELIX_GATEWAY_VERSION
#define KAELIX_GATEWAY_VERSION "gateway-2.1.1"
#endif
constexpr const char* FIRMWARE_VERSION = KAELIX_GATEWAY_VERSION;
constexpr const char* SPOOL_DIR = "/lfs/spool";
#ifndef KAELIX_SPOOL_SEGMENT_BYTES
#define KAELIX_SPOOL_SEGMENT_BYTES (256U * 1024U)
#endif
constexpr uint32_t SPOOL_SEGMENT_BYTES = KAELIX_SPOOL_SEGMENT_BYTES;
constexpr uint8_t STORE_ATTEMPTS = 3U;
constexpr uint32_t WAVE_RECORD_MAX = sizeof(WaveRecord) + proto::MAX_WAVE_BYTES;
constexpr size_t WAVE_BODY_MAX = 2048U + (proto::MAX_WAVE_BYTES / 3U + 1U) * 4U + 8U;
constexpr size_t STORE_QUEUE_LENGTH = 32U;
constexpr uint8_t WIFI_MAX = 5U;
constexpr int32_t TLS_CONNECT_TIMEOUT_MS = 8000;
constexpr uint32_t AP_AFTER_MS = 30000U;
constexpr uint32_t AP_LINGER_MS = 60000U;
constexpr uint32_t FACTORY_PRESS_MS = 10000U;
constexpr uint8_t BOOT_PIN = 0U;

struct WifiNetwork {
    char ssid[33];
    char password[65];
};

struct Settings {
    char gateway_id[37] = "";
    char token[64] = "";
    char admin_key[65] = "";
    char tls_sha256[65] = "";
    uint8_t wifi_count = 0U;
    WifiNetwork wifi[WIFI_MAX]{};
    uint32_t config_version = 0U;
    uint16_t heartbeat_s = 30U;
    uint16_t sync_s = 5U;
    bool ap_when_offline = true;
    int8_t tx_power = 17;
    bool paired() const { return gateway_id[0] != 0 && token[0] != 0 && tls_sha256[0] != 0; }
};

struct StoreItem {
    RecordKind kind;
    uint32_t size;
    uint8_t* data;
};

Settings settings;
Preferences prefs;
Spool spool;
WiFiMulti* wifi_multi = nullptr;
WebServer server(80);
LogBuffer<64> diagnostic_logs;
DeviceTable devices;
portMUX_TYPE logs_mux = portMUX_INITIALIZER_UNLOCKED;
SemaphoreHandle_t spool_mutex = nullptr, table_mutex = nullptr;
QueueHandle_t store_queue = nullptr;
char session_id[37];
char ap_ssid[16], ap_password[16], mac_text[18];
uint8_t* wave_record = nullptr; // leitura do gravador, em PSRAM
char* wave_body = nullptr;      // corpo HTTP da janela, em PSRAM
std::atomic<int8_t> tx_power{17};
std::atomic<uint32_t> event_seq{0U};
std::atomic<uint64_t> lora_valid{0U}, lora_rejected{0U}, spi_errors{0U}, queue_dropped{0U};
std::atomic<bool> radio_ok{false}, table_dirty{false}, clock_ready{false};
uint64_t http_failures = 0U, readings_acked = 0U, waves_acked = 0U;
uint32_t heartbeat_seq = 0U;
bool ap_running = false;
bool wifi_attempt_due = false; // tentar mesmo com alguém na rede própria
String ota_result_version, ota_result_reason;
bool ota_result_pending = false, ota_result_ok = false, ota_verify_pending = false;

uint64_t now_ms() { return static_cast<uint64_t>(esp_timer_get_time()) / 1000ULL; }

void capture_log(uint64_t ms, const char* level, const char* event, const char* message, bool truncated) {
    if (strcmp(event, "LOGS") == 0) return; // o envio de logs não gera logs
    portENTER_CRITICAL(&logs_mux);
    diagnostic_logs.push(ms, level, event, message, truncated);
    portEXIT_CRITICAL(&logs_mux);
}

void create_session() {
    uint8_t b[16];
    esp_fill_random(b, sizeof(b));
    b[6] = (b[6] & 15U) | 0x40U;
    b[8] = (b[8] & 63U) | 0x80U;
    snprintf(session_id, sizeof(session_id), "%02x%02x%02x%02x-%02x%02x-%02x%02x-%02x%02x-%02x%02x%02x%02x%02x%02x",
             b[0], b[1], b[2], b[3], b[4], b[5], b[6], b[7], b[8], b[9], b[10], b[11], b[12], b[13], b[14], b[15]);
}

const char* reset_reason_text() {
    switch (esp_reset_reason()) {
        case ESP_RST_POWERON: return "power_on";
        case ESP_RST_SW: return "software";
        case ESP_RST_PANIC: return "panic";
        case ESP_RST_INT_WDT: return "interrupt_watchdog";
        case ESP_RST_TASK_WDT: return "task_watchdog";
        case ESP_RST_WDT: return "watchdog";
        case ESP_RST_BROWNOUT: return "brownout";
        case ESP_RST_DEEPSLEEP: return "deep_sleep";
        case ESP_RST_EXT: return "external";
        default: return "unknown";
    }
}

// ---------------------------------------------------------------------
// Configuração gravada
// ---------------------------------------------------------------------

void load_settings() {
    prefs.begin("kaelix", true);
    prefs.getString("id", settings.gateway_id, sizeof(settings.gateway_id));
    prefs.getString("token", settings.token, sizeof(settings.token));
    prefs.getString("admin", settings.admin_key, sizeof(settings.admin_key));
    prefs.getString("tls", settings.tls_sha256, sizeof(settings.tls_sha256));
    settings.config_version = prefs.getUInt("cfg", 0U);
    settings.heartbeat_s = prefs.getUShort("hb", 30U);
    settings.sync_s = prefs.getUShort("sync", 5U);
    settings.ap_when_offline = prefs.getBool("ap", true);
    settings.tx_power = prefs.getChar("txp", 17);
    if (prefs.getBytesLength("wifi") == sizeof(settings.wifi)) {
        prefs.getBytes("wifi", settings.wifi, sizeof(settings.wifi));
        settings.wifi_count = prefs.getUChar("wifin", 0U);
    }
    static DeviceTable::Entry stored[DeviceTable::CAPACITY];
    const uint8_t count = prefs.getUChar("devn", 0U);
    if (count <= DeviceTable::CAPACITY && prefs.getBytesLength("dev") == sizeof(stored)) {
        prefs.getBytes("dev", stored, sizeof(stored));
        devices.restore(stored, count);
    }
    prefs.end();
    tx_power.store(settings.tx_power);
}

void save_settings() {
    prefs.begin("kaelix", false);
    prefs.putString("id", settings.gateway_id);
    prefs.putString("token", settings.token);
    prefs.putString("admin", settings.admin_key);
    prefs.putString("tls", settings.tls_sha256);
    prefs.putUInt("cfg", settings.config_version);
    prefs.putUShort("hb", settings.heartbeat_s);
    prefs.putUShort("sync", settings.sync_s);
    prefs.putBool("ap", settings.ap_when_offline);
    prefs.putChar("txp", settings.tx_power);
    prefs.putBytes("wifi", settings.wifi, sizeof(settings.wifi));
    prefs.putUChar("wifin", settings.wifi_count);
    prefs.end();
    tx_power.store(settings.tx_power);
}

void save_devices() {
    static DeviceTable::Entry snapshot[DeviceTable::CAPACITY];
    xSemaphoreTake(table_mutex, portMAX_DELAY);
    const uint8_t count = devices.count();
    memset(snapshot, 0, sizeof(snapshot));
    for (uint8_t i = 0U; i < count; ++i) snapshot[i] = devices.entries()[i];
    xSemaphoreGive(table_mutex);
    prefs.begin("kaelix", false);
    prefs.putBytes("dev", snapshot, sizeof(snapshot));
    prefs.putUChar("devn", count);
    prefs.end();
}

void reload_wifi() {
    delete wifi_multi;
    wifi_multi = new WiFiMulti();
    for (uint8_t i = 0U; i < settings.wifi_count; ++i) wifi_multi->addAP(settings.wifi[i].ssid, settings.wifi[i].password);
}

bool apply_wifi_list(JsonArrayConst list, bool keep_missing_passwords) {
    WifiNetwork next[WIFI_MAX]{};
    uint8_t count = 0U;
    for (JsonObjectConst item : list) {
        const char* ssid = item["ssid"] | "";
        const char* password = item["password"] | "";
        if (count == WIFI_MAX || ssid[0] == 0 || strlen(ssid) >= sizeof(next[0].ssid) || strlen(password) >= sizeof(next[0].password)) return false;
        snprintf(next[count].ssid, sizeof(next[count].ssid), "%s", ssid);
        snprintf(next[count].password, sizeof(next[count].password), "%s", password);
        if (keep_missing_passwords && !item["password"].is<const char*>()) {
            for (uint8_t i = 0U; i < settings.wifi_count; ++i)
                if (strcmp(settings.wifi[i].ssid, ssid) == 0) snprintf(next[count].password, sizeof(next[count].password), "%s", settings.wifi[i].password);
        }
        ++count;
    }
    // Sem nenhuma rede o gateway ficaria mudo: a lista vazia é recusada.
    if (count == 0U) return false;
    memcpy(settings.wifi, next, sizeof(next));
    settings.wifi_count = count;
    return true;
}

// ---------------------------------------------------------------------
// Configuração inicial: rede própria e rotas locais
// ---------------------------------------------------------------------

// Devolve o código HTTP. Serve à rota local e ao comando serial de recuperação.
int provision(const char* body, const char* admin_header, String* message) {
    if (settings.admin_key[0] != 0 && strcmp(admin_header, settings.admin_key) != 0) {
        *message = "unauthorized";
        return 401;
    }
    JsonDocument d;
    if (deserializeJson(d, body)) {
        *message = "invalid json";
        return 400;
    }
    const char* id = d["gateway_id"] | "";
    const char* token = d["gateway_token"] | "";
    const char* admin = d["admin_key"] | "";
    const char* tls = d["tls_sha256"] | "";
    if (strlen(id) != 36U || strlen(token) == 0U || strlen(token) >= sizeof(settings.token) || strlen(admin) != 64U || strlen(tls) != 64U) {
        *message = "invalid identity";
        return 422;
    }
    if (!apply_wifi_list(d["wifi"].as<JsonArrayConst>(), false)) {
        *message = "invalid wifi list";
        return 422;
    }
    snprintf(settings.gateway_id, sizeof(settings.gateway_id), "%s", id);
    snprintf(settings.token, sizeof(settings.token), "%s", token);
    snprintf(settings.admin_key, sizeof(settings.admin_key), "%s", admin);
    snprintf(settings.tls_sha256, sizeof(settings.tls_sha256), "%s", tls);
    settings.config_version = 0U;
    save_settings();
    reload_wifi();
    wifi_attempt_due = true;
    log("gateway", "INFO", "PROVISION", "paired gateway=%s networks=%u", settings.gateway_id, settings.wifi_count);
    *message = "ok";
    return 200;
}

void route_info() {
    JsonDocument d;
    d["mac"] = mac_text;
    d["firmware_version"] = FIRMWARE_VERSION;
    d["gateway_id"] = settings.gateway_id;
    d["paired"] = settings.paired();
    const bool connected = WiFi.status() == WL_CONNECTED;
    d["connected"] = connected;
    d["ssid"] = connected ? WiFi.SSID() : String("");
    d["ip"] = connected ? WiFi.localIP().toString() : String("");
    d["config_version"] = settings.config_version;
    String out;
    serializeJson(d, out);
    server.send(200, "application/json", out);
}

void route_scan() {
    const int n = WiFi.scanNetworks();
    JsonDocument d;
    JsonArray list = d["networks"].to<JsonArray>();
    for (int i = 0; i < n && i < 24; ++i) {
        JsonObject item = list.add<JsonObject>();
        item["ssid"] = WiFi.SSID(i);
        item["rssi"] = WiFi.RSSI(i);
        item["secure"] = WiFi.encryptionType(i) != WIFI_AUTH_OPEN;
    }
    WiFi.scanDelete();
    String out;
    serializeJson(d, out);
    server.send(200, "application/json", out);
}

void route_provision() {
    String message;
    const int code = provision(server.arg("plain").c_str(), server.header("X-Kaelix-Admin").c_str(), &message);
    server.send(code, "application/json", String("{\"status\":\"") + message + "\"}");
}

void route_reboot() {
    if (settings.admin_key[0] != 0 && server.header("X-Kaelix-Admin") != settings.admin_key) {
        server.send(401, "application/json", "{\"status\":\"unauthorized\"}");
        return;
    }
    server.send(200, "application/json", "{\"status\":\"ok\"}");
    delay(200);
    ESP.restart();
}

void begin_server() {
    const char* headers[] = {"X-Kaelix-Admin"};
    server.collectHeaders(headers, 1);
    server.on("/info", HTTP_GET, route_info);
    server.on("/scan", HTTP_GET, route_scan);
    server.on("/provision", HTTP_POST, route_provision);
    server.on("/reboot", HTTP_POST, route_reboot);
    server.begin();
}

void start_ap() {
    if (ap_running) return;
    WiFi.mode(WIFI_AP_STA);
    ap_running = WiFi.softAP(ap_ssid, ap_password);
    log("gateway", ap_running ? "INFO" : "ERROR", "AP", "own network %s at %s", ap_ssid, WiFi.softAPIP().toString().c_str());
}

void stop_ap() {
    if (!ap_running) return;
    WiFi.softAPdisconnect(true);
    WiFi.mode(WIFI_STA);
    ap_running = false;
    log("gateway", "INFO", "AP", "own network closed");
}

// Comando de recuperação por cabo: P <json>, com a chave de administração em
// A <chave> antes dele, se o gateway já estiver pareado.
void poll_serial() {
    static char* line = nullptr;
    static size_t used = 0U;
    static char admin[65] = "";
    if (line == nullptr) line = static_cast<char*>(ps_malloc(4096U));
    if (line == nullptr) return;
    while (Serial.available() > 0) {
        const int c = Serial.read();
        if (c == '\r') continue;
        if (c != '\n') {
            if (used < 4095U) line[used++] = static_cast<char>(c);
            continue;
        }
        line[used] = 0;
        used = 0U;
        if (strncmp(line, "A ", 2U) == 0) {
            snprintf(admin, sizeof(admin), "%s", line + 2);
        } else if (strncmp(line, "P ", 2U) == 0) {
            String message;
            const int code = provision(line + 2, admin, &message);
            log("gateway", code == 200 ? "INFO" : "WARN", "PROVISION", "serial status=%d %s", code, message.c_str());
        }
    }
}

// Segurar BOOT por 10 s apaga o pareamento. As leituras em flash continuam lá.
void poll_factory_button() {
    static uint64_t pressed_at = 0U;
    if (digitalRead(BOOT_PIN) != LOW) {
        pressed_at = 0U;
        return;
    }
    if (pressed_at == 0U) pressed_at = now_ms();
    if (now_ms() - pressed_at < FACTORY_PRESS_MS) return;
    log("gateway", "WARN", "PROVISION", "pairing erased by BOOT button");
    prefs.begin("kaelix", false);
    prefs.clear();
    prefs.end();
    delay(200);
    ESP.restart();
}

// ---------------------------------------------------------------------
// HTTPS com certificado fixado
// ---------------------------------------------------------------------

// WiFiClientSecure::stop() zera o contexto e deixa socket em 0, e o stop() seguinte
// fecha o descritor 0. Esse descritor passa a ser do arquivo aberto em seguida, e a
// escrita no gravador falha com EBADF. Deixar -1 impede o segundo fechamento.
class TlsClient : public WiFiClientSecure {
public:
    void stop() override {
        WiFiClientSecure::stop();
        sslclient->socket = -1;
    }
};

TlsClient tls;
std::atomic<uint8_t> wifi_reason{0U};
IPAddress api_ip;
uint16_t api_port = 0U;
uint32_t api_failures = 0U;

bool discover_api() {
    const int found = MDNS.queryService("kaelix", "tcp");
    // A resposta pode chegar sem o endereço, e 0.0.0.0 não é um servidor.
    for (int i = 0; i < found; ++i) {
        const IPAddress ip = MDNS.IP(i);
        if (ip == IPAddress(0U)) continue;
        api_ip = ip;
        api_port = MDNS.port(i);
        api_failures = 0U;
        log("gateway", "INFO", "NET", "API at %s:%u", api_ip.toString().c_str(), api_port);
        return true;
    }
    log("gateway", "WARN", "NET", "API not found on this network");
    return false;
}

bool ensure_connected() {
    if (tls.connected()) return true;
    tls.stop();
    // O servidor está na mesma rede: esperar mais só deixa o gateway sem atender.
    if (!tls.connect(api_ip, api_port, TLS_CONNECT_TIMEOUT_MS)) return false;
    // O token só sai depois de conferir que do outro lado está o nosso servidor.
    if (!tls.verify(settings.tls_sha256, nullptr)) {
        tls.stop();
        log("gateway", "ERROR", "TLS", "server certificate does not match the pairing");
        return false;
    }
    return true;
}

struct Result {
    int code = -1;
    String body;
};

Result post(const char* path, const uint8_t* body, size_t size) {
    Result result;
    if (!ensure_connected()) return result;
    // O destrutor do HTTPClient fecha a conexão, então um objeto local refaria o
    // handshake a cada envio. Só esta tarefa chama post().
    static HTTPClient http;
    http.setReuse(true);
    http.setConnectTimeout(10000);
    http.setTimeout(15000);
    http.setFollowRedirects(HTTPC_DISABLE_FOLLOW_REDIRECTS);
    if (!http.begin(tls, api_ip.toString(), api_port, path, true)) return result;
    http.addHeader("Content-Type", "application/json");
    http.addHeader("Authorization", String("Bearer ") + settings.token);
    result.code = http.POST(const_cast<uint8_t*>(body), size);
    if (result.code == 200 && http.getSize() <= 16384) result.body = http.getString();
    http.end();
    if (result.code < 0) tls.stop();
    return result;
}

Result post_json(const char* path, JsonDocument& request) {
    String payload;
    serializeJson(request, payload);
    return post(path, reinterpret_cast<const uint8_t*>(payload.c_str()), payload.length());
}

void note_transport(const Result& r) {
    if (r.code > 0) {
        api_failures = 0U;
        return;
    }
    ++http_failures;
    if (++api_failures >= 3U) api_port = 0U; // procurar o Mac de novo
}

// ---------------------------------------------------------------------
// Envio do gravador
// ---------------------------------------------------------------------

bool session_equal(const char* a) { return strncmp(a, session_id, 36U) == 0; }

// Confirmação só vale se citar exatamente os eventos enviados.
bool acknowledged(const String& body, const char* session, const uint32_t* events, size_t count) {
    JsonDocument d;
    if (deserializeJson(d, body)) return false;
    if (strcmp(d["gateway_id"] | "", settings.gateway_id) != 0 || strcmp(d["gateway_session_id"] | "", session) != 0) return false;
    JsonArrayConst ack = d["acknowledged"].as<JsonArrayConst>();
    if (ack.size() != count) return false;
    for (JsonObjectConst item : ack) {
        const char* status = item["status"] | "";
        if (strcmp(status, "stored") != 0 && strcmp(status, "duplicate") != 0) return false;
        const uint32_t seq = item["event_seq"] | 0U;
        bool matched = false;
        for (size_t i = 0U; i < count; ++i) matched = matched || events[i] == seq;
        if (!matched) return false;
    }
    return true;
}

// Registro que a API recusa em definitivo não pode travar os seguintes.
bool poison(int code) { return code == 400 || code == 409 || code == 413 || code == 422; }

enum class Upload { Progress, Empty, Failed };

Upload upload_next() {
    static ReadingRecord batch[8];
    Spool::Cursor cursor{};
    RecordKind kind{};
    uint32_t size = 0U;
    xSemaphoreTake(spool_mutex, portMAX_DELAY);
    cursor = spool.head();
    Spool::Cursor after = cursor;
    Spool::ReadResult read = spool.read(after, &kind, wave_record, WAVE_RECORD_MAX, &size);
    size_t count = 0U;
    if (read == Spool::ReadResult::Ok && kind == RecordKind::Reading && size == sizeof(ReadingRecord)) {
        memcpy(&batch[0], wave_record, sizeof(ReadingRecord));
        count = 1U;
        while (count < 8U) {
            Spool::Cursor probe = after;
            RecordKind next_kind{};
            uint32_t next_size = 0U;
            if (spool.read(probe, &next_kind, wave_record, WAVE_RECORD_MAX, &next_size) != Spool::ReadResult::Ok) break;
            if (next_kind != RecordKind::Reading || next_size != sizeof(ReadingRecord)) break;
            memcpy(&batch[count], wave_record, sizeof(ReadingRecord));
            if (strncmp(batch[count].session, batch[0].session, 36U) != 0) break;
            after = probe;
            ++count;
        }
    } else if (read == Spool::ReadResult::Ok && kind == RecordKind::Wave && size >= sizeof(WaveRecord)) {
        // O registro ficou em wave_record; só esta tarefa o usa.
    } else if (read == Spool::ReadResult::Ok || read == Spool::ReadResult::TooLarge) {
        log("gateway", "ERROR", "SPOOL", "skipping unknown record kind=%u size=%lu", static_cast<unsigned>(kind), static_cast<unsigned long>(size));
        if (read == Spool::ReadResult::Ok) spool.ack(after);
        xSemaphoreGive(spool_mutex);
        return read == Spool::ReadResult::Ok ? Upload::Progress : Upload::Failed;
    }
    xSemaphoreGive(spool_mutex);
    if (read == Spool::ReadResult::Empty) return Upload::Empty;

    char session[37];
    Result r;
    uint32_t events[8];
    if (count > 0U) {
        memcpy(session, batch[0].session, 36U);
        session[36] = 0;
        const bool previous = !session_equal(session);
        uint64_t newest = 0U;
        JsonDocument request;
        request["schema_version"] = 1;
        request["gateway_id"] = settings.gateway_id;
        request["gateway_session_id"] = session;
        if (previous) request["previous_session"] = true;
        JsonArray readings = request["readings"].to<JsonArray>();
        for (size_t i = 0U; i < count; ++i) {
            add_reading(readings.add<JsonObject>(), batch[i]);
            events[i] = batch[i].event_seq;
            newest = std::max<uint64_t>(newest, batch[i].rx_uptime_ms);
        }
        request["upload_uptime_ms"] = previous ? newest : now_ms();
        r = post_json("/api/v1/ingest/readings", request);
    } else {
        const auto* wave = reinterpret_cast<const WaveRecord*>(wave_record);
        memcpy(session, wave->session, 36U);
        session[36] = 0;
        const bool previous = !session_equal(session);
        const int prefix = wave_json_prefix(*wave, settings.gateway_id, session, previous, previous ? wave->rx_uptime_ms : now_ms(), wave_body, 2048U);
        size_t encoded = 0U;
        if (prefix <= 0 || prefix >= 2048 || wave->sample_bytes > proto::MAX_WAVE_BYTES ||
            mbedtls_base64_encode(reinterpret_cast<unsigned char*>(wave_body + prefix), WAVE_BODY_MAX - prefix - 3U, &encoded,
                                  wave_record + sizeof(WaveRecord), wave->sample_bytes) != 0) {
            log("gateway", "ERROR", "SPOOL", "wave encode failed; skipping");
            xSemaphoreTake(spool_mutex, portMAX_DELAY);
            spool.ack(after);
            xSemaphoreGive(spool_mutex);
            return Upload::Progress;
        }
        memcpy(wave_body + prefix + encoded, "\"}", 2U);
        events[0] = wave->event_seq;
        r = post("/api/v1/ingest/waveforms", reinterpret_cast<const uint8_t*>(wave_body), static_cast<size_t>(prefix) + encoded + 2U);
    }
    note_transport(r);
    const size_t confirmed = count > 0U ? count : 1U;
    const bool ok = r.code == 200 && acknowledged(r.body, session, events, confirmed);
    if (ok) {
        if (count > 0U) readings_acked += count;
        else ++waves_acked;
        log("gateway", "INFO", count > 0U ? "UPLOAD" : "UPLOAD_WAVE", "confirmed=%u", static_cast<unsigned>(confirmed));
    } else {
        ++http_failures;
        log("gateway", "WARN", "HTTP", "status=%d kind=%s; events retained", r.code, count > 0U ? "readings" : "wave");
    }
    if (ok || poison(r.code)) {
        if (!ok) {
            queue_dropped += confirmed;
            log("gateway", "ERROR", "QUARANTINE", "refused by API status=%d first_seq=%lu; discarded", r.code, static_cast<unsigned long>(events[0]));
        }
        xSemaphoreTake(spool_mutex, portMAX_DELAY);
        spool.ack(after);
        xSemaphoreGive(spool_mutex);
    }
    return ok ? Upload::Progress : Upload::Failed;
}

void send_heartbeat() {
    JsonDocument d;
    d["schema_version"] = 1;
    d["gateway_id"] = settings.gateway_id;
    d["gateway_session_id"] = session_id;
    d["heartbeat_seq"] = ++heartbeat_seq;
    d["uptime_ms"] = now_ms();
    const uint32_t utc = utc_now();
    if (utc != 0U) {
        char at[25];
        format_utc(utc, at, sizeof(at));
        d["sent_at"] = at;
    } else {
        d["sent_at"] = nullptr;
    }
    d["firmware_version"] = FIRMWARE_VERSION;
    JsonObject h = d["health"].to<JsonObject>();
    h["radio_initialized"] = radio_ok.load();
    h["wifi_connected"] = true;
    h["ntp_synchronized"] = clock_ready.load();
    h["queue_size"] = uxQueueMessagesWaiting(store_queue);
    h["queue_capacity"] = STORE_QUEUE_LENGTH;
    h["free_heap_bytes"] = ESP.getFreeHeap();
    h["wifi_rssi_dbm"] = WiFi.RSSI();
    h["ssid"] = WiFi.SSID();
    h["ip"] = WiFi.localIP().toString();
    h["reset_reason"] = reset_reason_text();
    xSemaphoreTake(spool_mutex, portMAX_DELAY);
    h["spool_used_bytes"] = spool.used_bytes();
    h["spool_capacity_bytes"] = spool.capacity_bytes();
    const uint64_t spool_lost = spool.dropped_records();
    xSemaphoreGive(spool_mutex);
    JsonObject c = d["counters"].to<JsonObject>();
    c["lora_valid"] = lora_valid.load();
    c["lora_rejected"] = lora_rejected.load();
    c["spi_errors"] = spi_errors.load();
    c["http_failed_attempts"] = http_failures;
    c["readings_acknowledged"] = readings_acked;
    c["queue_dropped"] = queue_dropped.load();
    c["spool_dropped"] = spool_lost;
    c["waveforms_acknowledged"] = waves_acked;
    const Result r = post_json("/api/v1/ingest/heartbeat", d);
    note_transport(r);
    log("gateway", r.code == 200 ? "INFO" : "WARN", "HEARTBEAT", "status=%d", r.code);
}

bool send_logs() {
    static RemoteLog batch[8];
    portENTER_CRITICAL(&logs_mux);
    const size_t count = diagnostic_logs.snapshot(batch, 8U);
    portEXIT_CRITICAL(&logs_mux);
    if (count == 0U) return true;
    JsonDocument request;
    request["schema_version"] = 1;
    request["gateway_id"] = settings.gateway_id;
    request["gateway_session_id"] = session_id;
    JsonArray logs = request["logs"].to<JsonArray>();
    for (size_t i = 0U; i < count; ++i) {
        JsonObject o = logs.add<JsonObject>();
        o["log_seq"] = batch[i].sequence;
        o["uptime_ms"] = batch[i].uptime_ms;
        o["level"] = batch[i].level;
        o["event"] = batch[i].event;
        o["message"] = batch[i].message;
        o["truncated"] = batch[i].truncated;
    }
    const Result r = post_json("/api/v1/ingest/logs", request);
    note_transport(r);
    if (r.code == 200 || poison(r.code)) {
        portENTER_CRITICAL(&logs_mux);
        diagnostic_logs.pop(count);
        portEXIT_CRITICAL(&logs_mux);
    }
    return r.code == 200;
}

// ---------------------------------------------------------------------
// Atualização remota
// ---------------------------------------------------------------------

void remember_ota(const char* version) {
    prefs.begin("kaelix", false);
    prefs.putString("ota", version);
    prefs.end();
}

void check_ota_state() {
    const esp_partition_t* running = esp_ota_get_running_partition();
    esp_ota_img_states_t state = ESP_OTA_IMG_UNDEFINED;
    ota_verify_pending = esp_ota_get_state_partition(running, &state) == ESP_OK && state == ESP_OTA_IMG_PENDING_VERIFY;
    prefs.begin("kaelix", true);
    const String wanted = prefs.getString("ota", "");
    prefs.end();
    // Tinha atualização pedida e esta não é ela: a nova não confirmou e voltou.
    if (!wanted.isEmpty() && wanted != FIRMWARE_VERSION) {
        ota_result_pending = true;
        ota_result_ok = false;
        ota_result_version = wanted;
        ota_result_reason = "rolled back";
        log("gateway", "ERROR", "OTA", "update to %s rolled back", wanted.c_str());
        remember_ota("");
    }
}

void confirm_ota_after_sync() {
    if (!ota_verify_pending) return;
    ota_verify_pending = false;
    esp_ota_mark_app_valid_cancel_rollback();
    ota_result_pending = true;
    ota_result_ok = true;
    ota_result_version = FIRMWARE_VERSION;
    ota_result_reason = "";
    remember_ota("");
    log("gateway", "INFO", "OTA", "running %s confirmed", FIRMWARE_VERSION);
}

void run_ota(const char* version, const char* expected_sha, uint32_t size, const char* path) {
    if (strcmp(version, FIRMWARE_VERSION) == 0) return;
    log("gateway", "INFO", "OTA", "downloading %s size=%lu", version, static_cast<unsigned long>(size));
    const auto fail = [&](const char* reason) {
        log("gateway", "ERROR", "OTA", "failed: %s", reason);
        Update.abort();
        tls.stop();
        ota_result_pending = true;
        ota_result_ok = false;
        ota_result_version = version;
        ota_result_reason = reason;
    };
    if (!ensure_connected()) return fail("connection");
    HTTPClient http;
    http.setReuse(false);
    http.setTimeout(15000);
    if (!http.begin(tls, api_ip.toString(), api_port, path, true)) return fail("request");
    http.addHeader("Authorization", String("Bearer ") + settings.token);
    const int code = http.GET();
    if (code != 200 || static_cast<uint32_t>(http.getSize()) != size) {
        http.end();
        return fail("download refused");
    }
    if (!Update.begin(size, U_FLASH)) {
        http.end();
        return fail("no room");
    }
    mbedtls_sha256_context sha;
    mbedtls_sha256_init(&sha);
    mbedtls_sha256_starts(&sha, 0);
    static uint8_t chunk[4096];
    WiFiClient* stream = http.getStreamPtr();
    uint32_t written = 0U;
    uint64_t last_data = now_ms();
    while (written < size && now_ms() - last_data < 20000U) {
        esp_task_wdt_reset();
        const size_t available = stream->available();
        if (available == 0U) { delay(5); continue; }
        const int got = stream->read(chunk, std::min<size_t>(available, sizeof(chunk)));
        if (got <= 0) continue;
        if (Update.write(chunk, got) != static_cast<size_t>(got)) break;
        mbedtls_sha256_update(&sha, chunk, got);
        written += got;
        last_data = now_ms();
    }
    uint8_t digest[32];
    mbedtls_sha256_finish(&sha, digest);
    mbedtls_sha256_free(&sha);
    http.end();
    char hex[65];
    for (size_t i = 0U; i < 32U; ++i) snprintf(hex + i * 2U, 3U, "%02x", digest[i]);
    if (written != size) return fail("download incomplete");
    if (strcasecmp(hex, expected_sha) != 0) return fail("sha256 mismatch");
    if (!Update.end(true)) return fail("image refused");
    remember_ota(version);
    log("gateway", "INFO", "OTA", "installed %s; restarting", version);
    delay(500);
    ESP.restart();
}

// ---------------------------------------------------------------------
// Sincronização com a API
// ---------------------------------------------------------------------

void set_clock(const char* iso) {
    int year = 0, month = 0, day = 0, hour = 0, minute = 0, second = 0;
    if (sscanf(iso, "%d-%d-%dT%d:%d:%d", &year, &month, &day, &hour, &minute, &second) != 6) return;
    tm t{};
    t.tm_year = year - 1900;
    t.tm_mon = month - 1;
    t.tm_mday = day;
    t.tm_hour = hour;
    t.tm_min = minute;
    t.tm_sec = second;
    setenv("TZ", "UTC0", 1);
    tzset();
    const time_t seconds = mktime(&t);
    if (seconds <= 0) return;
    timeval value{seconds, 0};
    settimeofday(&value, nullptr);
    if (!clock_ready.exchange(true)) log("gateway", "INFO", "CLOCK", "set from API: %s", iso);
}

void apply_gateway_config(JsonObjectConst c) {
    if (c.isNull() || !c["version"].is<uint32_t>()) return;
    // Lista vazia significa que a API nunca soube das redes: mantém as gravadas.
    if (c["wifi"].as<JsonArrayConst>().size() > 0U && !apply_wifi_list(c["wifi"].as<JsonArrayConst>(), true)) {
        log("gateway", "ERROR", "CONFIG", "gateway config %lu refused: invalid wifi list", static_cast<unsigned long>(c["version"].as<uint32_t>()));
        return;
    }
    const uint16_t heartbeat = c["heartbeat_interval_s"] | settings.heartbeat_s;
    const uint16_t sync = c["sync_interval_s"] | settings.sync_s;
    const int8_t power = c["tx_power_dbm"] | settings.tx_power;
    settings.heartbeat_s = std::max<uint16_t>(10U, std::min<uint16_t>(300U, heartbeat));
    settings.sync_s = std::max<uint16_t>(2U, std::min<uint16_t>(60U, sync));
    settings.tx_power = std::max<int8_t>(2, std::min<int8_t>(17, power));
    settings.ap_when_offline = c["ap_when_offline"] | settings.ap_when_offline;
    settings.config_version = c["version"].as<uint32_t>();
    save_settings();
    reload_wifi();
    log("gateway", "INFO", "CONFIG", "gateway config %lu applied networks=%u", static_cast<unsigned long>(settings.config_version), settings.wifi_count);
}

void send_sync() {
    JsonDocument request;
    request["schema_version"] = 1;
    request["gateway_id"] = settings.gateway_id;
    request["gateway_session_id"] = session_id;
    request["config_version"] = settings.config_version;
    request["firmware_version"] = FIRMWARE_VERSION;
    if (ota_result_pending) {
        JsonObject o = request["ota_result"].to<JsonObject>();
        o["version"] = ota_result_version;
        o["ok"] = ota_result_ok;
        o["reason"] = ota_result_reason;
    } else {
        request["ota_result"] = nullptr;
    }
    JsonArray list = request["devices"].to<JsonArray>();
    xSemaphoreTake(table_mutex, portMAX_DELAY);
    for (uint8_t i = 0U; i < devices.count(); ++i) {
        const DeviceTable::Entry& e = devices.entries()[i];
        JsonObject o = list.add<JsonObject>();
        char id[9];
        snprintf(id, sizeof(id), "%08lX", static_cast<unsigned long>(e.device_id));
        o["device_id"] = id;
        o["radiated_config_version"] = e.radiated_config;
        o["radiated_command_seq"] = e.radiated_command;
    }
    xSemaphoreGive(table_mutex);
    const Result r = post_json("/api/v1/gateway/sync", request);
    note_transport(r);
    if (r.code != 200) {
        log("gateway", "WARN", "SYNC", "status=%d", r.code);
        return;
    }
    JsonDocument d;
    if (deserializeJson(d, r.body) || strcmp(d["gateway_id"] | "", settings.gateway_id) != 0) {
        log("gateway", "WARN", "SYNC", "invalid response");
        return;
    }
    set_clock(d["server_time"] | "");
    confirm_ota_after_sync();
    ota_result_pending = ota_result_pending && !request["ota_result"].is<JsonObject>();
    apply_gateway_config(d["gateway_config"].as<JsonObjectConst>());

    uint32_t listed[DeviceTable::CAPACITY];
    uint8_t listed_count = 0U;
    bool changed = false;
    for (JsonObjectConst item : d["devices"].as<JsonArrayConst>()) {
        const uint32_t id = strtoul(item["device_id"] | "0", nullptr, 16);
        proto::DeviceConfig config{};
        const bool has_config = parse_device_config(item["config"], &config);
        if (!item["config"].isNull() && !has_config) {
            log("gateway", "ERROR", "RELAY", "config for %08lX refused", static_cast<unsigned long>(id));
        }
        const proto::Command command = parse_command(item["command"]["kind"] | static_cast<const char*>(nullptr));
        const uint16_t command_seq = item["command"]["seq"] | 0U;
        xSemaphoreTake(table_mutex, portMAX_DELAY);
        changed = devices.set(id, has_config ? &config : nullptr, command, command_seq) || changed;
        xSemaphoreGive(table_mutex);
        if (listed_count < DeviceTable::CAPACITY) listed[listed_count++] = id;
    }
    xSemaphoreTake(table_mutex, portMAX_DELAY);
    devices.clear_except(listed, listed_count);
    xSemaphoreGive(table_mutex);
    if (changed) table_dirty.store(true);

    JsonObjectConst firmware = d["firmware"].as<JsonObjectConst>();
    if (!firmware.isNull()) {
        run_ota(firmware["version"] | "", firmware["sha256"] | "", firmware["size"] | 0U, firmware["path"] | "");
    }
}

// ---------------------------------------------------------------------
// Tarefas
// ---------------------------------------------------------------------

void store_task(void*) {
    esp_task_wdt_add(nullptr);
    for (;;) {
        esp_task_wdt_reset();
        StoreItem item{};
        if (xQueueReceive(store_queue, &item, pdMS_TO_TICKS(1000)) != pdTRUE) continue;
        // A falha troca de segmento, então tentar de novo costuma bastar. Repetir um
        // registro é inofensivo, porque a API é idempotente; perdê-lo não tem volta.
        bool ok = false;
        for (uint8_t attempt = 1U; attempt <= STORE_ATTEMPTS && !ok; ++attempt) {
            xSemaphoreTake(spool_mutex, portMAX_DELAY);
            ok = spool.append(item.kind, item.data, item.size);
            const char* step = spool.failed_step();
            const int code = spool.failed_errno();
            xSemaphoreGive(spool_mutex);
            if (ok) break;
            log("gateway", attempt < STORE_ATTEMPTS ? "WARN" : "ERROR", "SPOOL", "append failed kind=%u size=%lu attempt=%u step=%s errno=%d", static_cast<unsigned>(item.kind),
                static_cast<unsigned long>(item.size), attempt, step, code);
            vTaskDelay(pdMS_TO_TICKS(50));
        }
        if (!ok) ++queue_dropped;
        free(item.data);
    }
}

void net_task(void*) {
    esp_task_wdt_add(nullptr);
    WiFi.persistent(false);
    WiFi.mode(WIFI_STA);
    WiFi.setHostname(ap_ssid);
    WiFi.setAutoReconnect(true);
    WiFi.setSleep(false); // o gateway não vive de bateria pequena, e a economia chegava a 1,4 s de latência
    WiFi.onEvent([](WiFiEvent_t, WiFiEventInfo_t info) { wifi_reason.store(info.wifi_sta_disconnected.reason); }, ARDUINO_EVENT_WIFI_STA_DISCONNECTED);
    reload_wifi();
    tls.setInsecure(); // a conferência é a impressão digital fixada, em ensure_connected()
    tls.setHandshakeTimeout(10);
    begin_server();
    MDNS.begin(ap_ssid);
    const uint64_t booted = now_ms();
    uint64_t offline_since = booted, connected_at = 0U, next_wifi = 0U, next_discovery = 0U;
    uint64_t next_upload = 0U, next_heartbeat = 0U, next_sync = 0U, next_logs = 0U;
    uint32_t upload_backoff = 1000U;
    uint8_t last_reason = 0U;
    bool connected = false;
    for (;;) {
        esp_task_wdt_reset();
        server.handleClient();
        poll_serial();
        poll_factory_button();
        const bool online = WiFi.status() == WL_CONNECTED;
        const uint8_t reason = wifi_reason.exchange(0U);
        if (reason != 0U && reason != last_reason) {
            last_reason = reason;
            log("gateway", "WARN", "WIFI", "lost or refused: reason=%u", reason);
        }
        if (online != connected) {
            connected = online;
            if (online) {
                connected_at = now_ms();
                last_reason = 0U;
                api_port = 0U;
                next_discovery = 0U;
                log("gateway", "INFO", "WIFI", "connected ssid=%s ip=%s rssi=%d", WiFi.SSID().c_str(), WiFi.localIP().toString().c_str(), WiFi.RSSI());
            } else {
                offline_since = now_ms();
                tls.stop();
                log("gateway", "WARN", "WIFI", "disconnected");
            }
        }
        if (!online) {
            // Não varrer com alguém usando a rede própria: a troca de canal o derruba.
            const bool ap_in_use = ap_running && WiFi.softAPgetStationNum() > 0U;
            if (settings.wifi_count > 0U && (wifi_attempt_due || (!ap_in_use && now_ms() >= next_wifi))) {
                wifi_attempt_due = false;
                wifi_multi->run(8000);
                next_wifi = now_ms() + 15000U;
            }
            if (settings.ap_when_offline && !ap_running && now_ms() - offline_since >= AP_AFTER_MS) start_ap();
            if (settings.wifi_count == 0U && !ap_running) start_ap();
            vTaskDelay(pdMS_TO_TICKS(50));
            continue;
        }
        if (ap_running && WiFi.softAPgetStationNum() == 0U && now_ms() - connected_at >= AP_LINGER_MS) stop_ap();
        if (!settings.paired()) {
            vTaskDelay(pdMS_TO_TICKS(50));
            continue;
        }
        if (api_port == 0U) {
            if (now_ms() >= next_discovery) {
                if (!discover_api()) next_discovery = now_ms() + 5000U;
            }
            vTaskDelay(pdMS_TO_TICKS(50));
            continue;
        }
        if (now_ms() >= next_sync) {
            send_sync();
            next_sync = now_ms() + settings.sync_s * 1000ULL;
        } else if (now_ms() >= next_heartbeat) {
            send_heartbeat();
            next_heartbeat = now_ms() + settings.heartbeat_s * 1000ULL;
        } else if (now_ms() >= next_logs) {
            send_logs();
            next_logs = now_ms() + 5000U;
        } else if (now_ms() >= next_upload) {
            switch (upload_next()) {
                case Upload::Progress:
                    upload_backoff = 1000U;
                    next_upload = now_ms();
                    break;
                case Upload::Empty:
                    upload_backoff = 1000U;
                    next_upload = now_ms() + 250U;
                    break;
                case Upload::Failed:
                    next_upload = now_ms() + upload_backoff;
                    upload_backoff = std::min<uint32_t>(30000U, upload_backoff * 2U);
                    break;
            }
        }
        if (table_dirty.exchange(false)) save_devices();
        vTaskDelay(pdMS_TO_TICKS(20));
    }
}
} // namespace

const char* session() { return session_id; }
uint32_t next_event_seq() { return event_seq.fetch_add(1U) + 1U; }
uint32_t utc_now() { return clock_ready.load() ? static_cast<uint32_t>(time(nullptr)) : 0U; }
int8_t tx_power_dbm() { return tx_power.load(); }
void radio_health(bool initialized) { radio_ok.store(initialized); }
void reading_valid() { ++lora_valid; }
void rejected() { ++lora_rejected; }
void spi_error() { ++spi_errors; }

bool store_reading(const ReadingRecord& record) {
    auto* copy = static_cast<uint8_t*>(malloc(sizeof(record)));
    if (copy == nullptr) {
        ++queue_dropped;
        return false;
    }
    memcpy(copy, &record, sizeof(record));
    StoreItem item{RecordKind::Reading, sizeof(record), copy};
    if (store_queue == nullptr || xQueueSend(store_queue, &item, 0) != pdTRUE) {
        ++queue_dropped;
        free(copy);
        return false;
    }
    return true;
}

bool store_wave(uint8_t* record, uint32_t size) {
    StoreItem item{RecordKind::Wave, size, record};
    if (store_queue == nullptr || xQueueSend(store_queue, &item, 0) != pdTRUE) {
        ++queue_dropped;
        free(record);
        return false;
    }
    return true;
}

Pending pending_for(uint32_t device_id, uint16_t reported_config, uint16_t reported_command) {
    xSemaphoreTake(table_mutex, portMAX_DELAY);
    const Pending p = devices.pending_for(device_id, reported_config, reported_command);
    xSemaphoreGive(table_mutex);
    return p;
}

void mark_radiated(uint32_t device_id, uint16_t config_version, uint16_t command_seq) {
    xSemaphoreTake(table_mutex, portMAX_DELAY);
    devices.mark_radiated(device_id, config_version, command_seq);
    xSemaphoreGive(table_mutex);
}

void begin() {
    logging::set_sink(capture_log);
    create_session();
    pinMode(BOOT_PIN, INPUT_PULLUP);
    esp_task_wdt_init(60, true);
    spool_mutex = xSemaphoreCreateMutex();
    table_mutex = xSemaphoreCreateMutex();
    store_queue = xQueueCreate(STORE_QUEUE_LENGTH, sizeof(StoreItem));
    wave_record = static_cast<uint8_t*>(ps_malloc(WAVE_RECORD_MAX));
    wave_body = static_cast<char*>(ps_malloc(WAVE_BODY_MAX));
    uint8_t mac[6];
    WiFi.macAddress(mac);
    snprintf(mac_text, sizeof(mac_text), "%02x:%02x:%02x:%02x:%02x:%02x", mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
    snprintf(ap_ssid, sizeof(ap_ssid), "Kaelix-%02X%02X", mac[4], mac[5]);
    snprintf(ap_password, sizeof(ap_password), "kaelix-%02X%02X", mac[4], mac[5]);
    load_settings();
    check_ota_state();
    log("gateway", "INFO", "BOOT", "firmware=%s session=%s reset=%s paired=%d networks=%u psram=%lu", FIRMWARE_VERSION, session_id,
        reset_reason_text(), settings.paired(), settings.wifi_count, static_cast<unsigned long>(ESP.getFreePsram()));
    if (wave_record == nullptr || wave_body == nullptr) log("gateway", "ERROR", "BOOT", "PSRAM allocation failed");
    bool mounted = LittleFS.begin(true, "/lfs", 8, "spool");
    if (!mounted) {
        log("gateway", "ERROR", "SPOOL", "mount failed; formatting");
        mounted = LittleFS.format() && LittleFS.begin(true, "/lfs", 8, "spool");
    }
    if (mounted) {
        const uint64_t capacity = static_cast<uint64_t>(LittleFS.totalBytes()) * 9ULL / 10ULL;
        if (!spool.begin(SPOOL_DIR, capacity, SPOOL_SEGMENT_BYTES)) log("gateway", "ERROR", "SPOOL", "begin failed");
        log("gateway", "INFO", "SPOOL", "capacity=%llu used=%llu", static_cast<unsigned long long>(capacity), static_cast<unsigned long long>(spool.used_bytes()));
    } else {
        log("gateway", "ERROR", "SPOOL", "no flash storage; readings will be lost");
    }
    if (xTaskCreatePinnedToCore(store_task, "gateway-store", 8192, nullptr, 2, nullptr, 0) != pdPASS ||
        xTaskCreatePinnedToCore(net_task, "gateway-net", 16384, nullptr, 1, nullptr, 0) != pdPASS) {
        log("gateway", "ERROR", "BOOT", "task allocation failed; radio only");
    }
}

} // namespace kaelix::gateway::net
