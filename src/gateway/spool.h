#pragma once

#include <dirent.h>
#include <sys/stat.h>
#include <unistd.h>

#include <cerrno>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>

// Gravador em flash do gateway. Cada registro é escrito e sincronizado antes de
// valer, e só sai daqui depois que a API confirma. Usa stdio sobre o VFS: o
// mesmo código roda em LittleFS na placa e em disco nos testes do host.
//
// O chamador sincroniza o acesso. Um boot sempre abre um segmento novo, então
// um registro cortado por queda de energia só pode estar no fim de um segmento
// antigo, e a leitura segue para o próximo.
namespace kaelix::gateway {

enum class RecordKind : uint8_t { Reading = 1U, Wave = 2U };

class Spool {
public:
    struct Cursor {
        uint32_t segment = 0U;
        uint32_t offset = 0U;
        bool operator==(const Cursor& o) const { return segment == o.segment && offset == o.offset; }
    };
    enum class ReadResult { Ok, Empty, TooLarge };

    ~Spool() { close_writer(); }

    bool begin(const char* dir, uint64_t capacity_bytes, uint32_t segment_bytes) {
        close_writer();
        snprintf(dir_, sizeof(dir_), "%s", dir);
        capacity_ = capacity_bytes;
        segment_bytes_ = segment_bytes;
        used_ = 0U;
        ready_ = false;
        struct stat info {};
        if (stat(dir_, &info) != 0 && mkdir(dir_, 0775) != 0) return false;
        DIR* d = opendir(dir_);
        if (d == nullptr) return false;
        uint32_t lowest = UINT32_MAX, highest = 0U;
        bool any = false;
        while (dirent* entry = readdir(d)) {
            uint32_t number = 0U;
            if (!parse_segment(entry->d_name, &number)) continue;
            any = true;
            if (number < lowest) lowest = number;
            if (number > highest) highest = number;
            char path[96];
            segment_path(number, path, sizeof(path));
            if (stat(path, &info) == 0) used_ += static_cast<uint64_t>(info.st_size);
        }
        closedir(d);
        lowest_ = any ? lowest : 1U;
        write_segment_ = any ? highest + 1U : 1U;
        if (!load_head() || head_.segment < lowest_ || head_.segment > write_segment_) head_ = Cursor{lowest_, 0U};
        ready_ = true;
        return true;
    }

    bool ready() const { return ready_; }
    Cursor head() const { return head_; }
    uint64_t used_bytes() const { return used_; }
    uint64_t capacity_bytes() const { return capacity_; }
    uint64_t dropped_records() const { return dropped_; }
    uint64_t corrupted_segments() const { return corrupted_; }
    // Onde e por que a última gravação falhou, para o diagnóstico.
    const char* failed_step() const { return failed_step_; }
    int failed_errno() const { return failed_errno_; }

    bool append(RecordKind kind, const void* data, uint32_t size) {
        if (!ready_ || data == nullptr || size == 0U) return false;
        const uint64_t total = sizeof(RecordHeader) + static_cast<uint64_t>(size);
        if (total > capacity_) return false;
        if (writer_ != nullptr && write_size_ >= segment_bytes_) {
            close_writer();
            ++write_segment_;
        }
        while (used_ + total > capacity_ && lowest_ < write_segment_) drop_oldest();
        if (used_ + total > capacity_) {
            // O segmento em escrita é o único e encheu: vira segmento antigo.
            close_writer();
            ++write_segment_;
            while (used_ + total > capacity_ && lowest_ < write_segment_) drop_oldest();
        }
        if (writer_ == nullptr) {
            char path[96];
            segment_path(write_segment_, path, sizeof(path));
            writer_ = fopen(path, "ab");
            if (writer_ == nullptr) {
                failed_step_ = "open";
                failed_errno_ = errno;
                return false;
            }
            write_size_ = 0U;
        }
        RecordHeader header{};
        header.magic = MAGIC;
        header.kind = static_cast<uint8_t>(kind);
        header.size = size;
        header.crc = crc32(data, size);
        const char* step = nullptr;
        if (fwrite(&header, sizeof(header), 1U, writer_) != 1U) step = "header";
        else if (fwrite(data, 1U, size, writer_) != size) step = "body";
        else if (fflush(writer_) != 0) step = "flush";
        else if (fsync(fileno(writer_)) != 0) step = "sync";
        if (step != nullptr) {
            failed_step_ = step;
            failed_errno_ = errno;
            // Sem saber o que foi gravado, o resto do segmento não é confiável.
            close_writer();
            ++write_segment_;
            return false;
        }
        write_size_ += static_cast<uint32_t>(total);
        used_ += total;
        return true;
    }

    // Lê em `cursor` e o avança. Não consome: quem consome é ack().
    ReadResult read(Cursor& cursor, RecordKind* kind, void* buffer, uint32_t capacity, uint32_t* size) {
        if (!ready_) return ReadResult::Empty;
        while (cursor.segment <= write_segment_) {
            char path[96];
            segment_path(cursor.segment, path, sizeof(path));
            FILE* file = fopen(path, "rb");
            const bool older = cursor.segment < write_segment_;
            if (file == nullptr) {
                if (!older) return ReadResult::Empty;
                next_segment(cursor);
                continue;
            }
            RecordHeader header{};
            const bool positioned = fseek(file, static_cast<long>(cursor.offset), SEEK_SET) == 0;
            const size_t got = positioned ? fread(&header, 1U, sizeof(header), file) : 0U;
            if (got == 0U) {
                fclose(file);
                if (!older) return ReadResult::Empty;
                next_segment(cursor);
                continue;
            }
            if (got != sizeof(header) || header.magic != MAGIC) {
                fclose(file);
                if (!older) return ReadResult::Empty;
                ++corrupted_;
                next_segment(cursor);
                continue;
            }
            if (size != nullptr) *size = header.size;
            if (header.size > capacity) {
                fclose(file);
                return ReadResult::TooLarge;
            }
            const size_t body = fread(buffer, 1U, header.size, file);
            fclose(file);
            if (body != header.size || crc32(buffer, header.size) != header.crc) {
                if (!older) return ReadResult::Empty;
                ++corrupted_;
                next_segment(cursor);
                continue;
            }
            if (kind != nullptr) *kind = static_cast<RecordKind>(header.kind);
            cursor.offset += static_cast<uint32_t>(sizeof(header) + header.size);
            return ReadResult::Ok;
        }
        return ReadResult::Empty;
    }

    // Confirma tudo antes de `cursor`. Repetir um envio é inofensivo, porque a
    // API é idempotente, então a posição só vai à flash de tempos em tempos.
    void ack(const Cursor& cursor) {
        const bool moved_segment = cursor.segment != head_.segment;
        head_ = cursor;
        while (lowest_ < head_.segment && lowest_ < write_segment_) remove_segment(lowest_);
        if (moved_segment || ++acks_since_save_ >= HEAD_SAVE_EVERY) save_head();
    }

    void flush_head() { save_head(); }

private:
    struct __attribute__((packed)) RecordHeader {
        uint16_t magic;
        uint8_t kind;
        uint8_t reserved;
        uint32_t size;
        uint32_t crc;
    };
    struct __attribute__((packed)) HeadFile {
        uint32_t segment;
        uint32_t offset;
        uint32_t crc;
    };
    static constexpr uint16_t MAGIC = 0x534BU;
    static constexpr uint32_t HEAD_SAVE_EVERY = 16U;

    static uint32_t crc32(const void* data, uint32_t size) {
        uint32_t crc = 0xFFFFFFFFU;
        const uint8_t* bytes = static_cast<const uint8_t*>(data);
        for (uint32_t i = 0U; i < size; ++i) {
            crc ^= bytes[i];
            for (uint8_t bit = 0U; bit < 8U; ++bit) crc = (crc >> 1U) ^ (0xEDB88320U & (0U - (crc & 1U)));
        }
        return ~crc;
    }

    static bool parse_segment(const char* name, uint32_t* number) {
        if (strlen(name) != 12U || strcmp(name + 8, ".seg") != 0) return false;
        char* end = nullptr;
        const unsigned long value = strtoul(name, &end, 10);
        if (end != name + 8) return false;
        *number = static_cast<uint32_t>(value);
        return true;
    }

    void segment_path(uint32_t number, char* out, size_t size) const {
        snprintf(out, size, "%s/%08lu.seg", dir_, static_cast<unsigned long>(number));
    }

    void close_writer() {
        if (writer_ != nullptr) fclose(writer_);
        writer_ = nullptr;
        write_size_ = 0U;
    }

    void next_segment(Cursor& cursor) {
        ++cursor.segment;
        cursor.offset = 0U;
    }

    uint64_t remove_segment(uint32_t number) {
        char path[96];
        segment_path(number, path, sizeof(path));
        struct stat info {};
        uint64_t size = 0U;
        if (stat(path, &info) == 0) {
            size = static_cast<uint64_t>(info.st_size);
            used_ = used_ >= size ? used_ - size : 0U;
            remove(path);
        }
        if (number == lowest_) ++lowest_;
        return size;
    }

    // Só o que ainda não foi confirmado conta como perda.
    void drop_oldest() {
        const uint32_t number = lowest_;
        Cursor scan{number, head_.segment == number ? head_.offset : 0U};
        if (head_.segment <= number) {
            char path[96];
            segment_path(number, path, sizeof(path));
            if (FILE* file = fopen(path, "rb")) {
                RecordHeader header{};
                long position = static_cast<long>(scan.offset);
                while (fseek(file, position, SEEK_SET) == 0 && fread(&header, sizeof(header), 1U, file) == 1U && header.magic == MAGIC) {
                    ++dropped_;
                    position += static_cast<long>(sizeof(header) + header.size);
                }
                fclose(file);
            }
        }
        remove_segment(number);
        if (head_.segment <= number) {
            head_ = Cursor{lowest_, 0U};
            save_head();
        }
    }

    bool load_head() {
        char path[96];
        snprintf(path, sizeof(path), "%s/head", dir_);
        FILE* file = fopen(path, "rb");
        if (file == nullptr) return false;
        HeadFile stored{};
        const bool read_ok = fread(&stored, sizeof(stored), 1U, file) == 1U;
        fclose(file);
        if (!read_ok || stored.crc != crc32(&stored, offsetof(HeadFile, crc))) return false;
        head_ = Cursor{stored.segment, stored.offset};
        return true;
    }

    void save_head() {
        acks_since_save_ = 0U;
        char path[96], temporary[96];
        snprintf(path, sizeof(path), "%s/head", dir_);
        snprintf(temporary, sizeof(temporary), "%s/head.tmp", dir_);
        HeadFile stored{head_.segment, head_.offset, 0U};
        stored.crc = crc32(&stored, offsetof(HeadFile, crc));
        FILE* file = fopen(temporary, "wb");
        if (file == nullptr) return;
        const bool ok = fwrite(&stored, sizeof(stored), 1U, file) == 1U && fflush(file) == 0 && fsync(fileno(file)) == 0;
        fclose(file);
        if (ok) rename(temporary, path);
    }

    char dir_[64]{};
    uint64_t capacity_ = 0U, used_ = 0U, dropped_ = 0U, corrupted_ = 0U;
    uint32_t segment_bytes_ = 0U, write_segment_ = 1U, lowest_ = 1U, write_size_ = 0U, acks_since_save_ = 0U;
    Cursor head_{};
    FILE* writer_ = nullptr;
    const char* failed_step_ = "";
    int failed_errno_ = 0;
    bool ready_ = false;
};

} // namespace kaelix::gateway
