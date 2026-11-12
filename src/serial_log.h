#pragma once

#include <Arduino.h>
#include <esp_timer.h>
#include <cstdarg>
#include <cstdio>
#include <atomic>

namespace kaelix::logging {

using Sink = void (*)(uint64_t, const char*, const char*, const char*, bool);
inline std::atomic<Sink> sink{nullptr};
inline void set_sink(Sink callback) { sink.store(callback); }

// Relógio monotônico desde o boot, sem sincronização entre dispositivos.
// Usar apenas nas tarefas; nunca chamar de uma ISR.
inline void line(const char* device, const char* level, const char* event,
                 const char* message, bool truncated = false) {
    const uint64_t ms = static_cast<uint64_t>(esp_timer_get_time()) / 1000ULL;
    if (auto callback = sink.load()) callback(ms, level, event, message, truncated);
    Serial.printf("[+%02llu:%02u:%02u.%03u][%s][%s][%s] %s\n",
        static_cast<unsigned long long>(ms / 3600000ULL),
        static_cast<unsigned>((ms / 60000ULL) % 60ULL),
        static_cast<unsigned>((ms / 1000ULL) % 60ULL),
        static_cast<unsigned>(ms % 1000ULL), device, level, event, message);
}

inline void log(const char* device, const char* level, const char* event,
                const char* format, ...) {
    char message[384];
    va_list args;
    va_start(args, format);
    const int length = vsnprintf(message, sizeof(message), format, args);
    va_end(args);
    line(device, level, event, message, length >= static_cast<int>(sizeof(message)));
}

} // namespace kaelix::logging
