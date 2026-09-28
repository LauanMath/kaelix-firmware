#pragma once

#include <cstdint>

// =====================================================================
// Kaelix — modelo de erro compartilhado
// =====================================================================
//
// Este é o ÚNICO vocabulário de falha do firmware. Tudo que pode falhar
// devolve `kaelix::Status`, não `bool`.
//
// Por que não `bool`: hoje `vibration_init()`, `temperature_init()`,
// `model_init()`, `lora_init()`, `lora_send()` e `lora_sleep()` devolvem
// todas o mesmo `false`, e o log em src/main.cpp precisa inventar a
// causa em texto livre. Em campo, "rádio LoRa não inicializou" pode ser
// antena solta, SPI mudo, chip ausente ou frequência rejeitada pelo
// RadioLib — quatro deslocamentos diferentes de manutenção. O bit que
// sobrevive até o gateway precisa carregar essa distinção.
//
// Restrições de projeto respeitadas por este arquivo:
//   - compila sem <Arduino.h> (vive em lib/, roda no ambiente `native`);
//   - nenhuma alocação dinâmica, nenhuma exceção, nenhum RTTI;
//   - `Status` ocupa 1 byte, para caber no pacote LoRa de 20 bytes;
//   - todas as funções são `constexpr`/`inline`: custo zero em release.
//
// Convenção de valores — a faixa alta do byte identifica o subsistema,
// o que permite ao gateway triar sem uma tabela completa:
//
//   0x00        sucesso
//   0x01..0x0F  contrato (bug de software: parâmetro/estado inválido)
//   0x10..0x1F  vibração — MPU6050 / barramento I2C
//   0x20..0x2F  temperatura — NTC 10k / ADC
//   0x30..0x3F  modelo — Isolation Forest embarcado
//   0x40..0x4F  rádio — SX1278 / SPI / pacote
//   0x50..0x5F  plataforma — energia, watchdog, memória RTC, prazo
//   0xF0..0xFF  genéricos
//
// Ao acrescentar um valor: escolha a faixa do subsistema, NUNCA reutilize
// um número já publicado (o gateway decodifica por número) e acrescente a
// string curta em `status_to_string`.
// =====================================================================

namespace kaelix {

enum class Status : uint8_t {
    // ---- sucesso -----------------------------------------------------
    Ok = 0x00,

    // ---- 0x01..0x0F contrato ----------------------------------------
    // Violações de contrato do chamador. São bugs de software, não
    // defeitos de campo: em build de desenvolvimento abortam (ver
    // KAELIX_REQUIRE); em produção viram este status.
    NullPointer          = 0x01, // ponteiro obrigatório veio nulo
    InvalidArgument      = 0x02, // valor fora do domínio da função
    LengthZero           = 0x03, // n == 0 onde n >= 1 é exigido
    LengthNotPowerOfTwo  = 0x04, // FFT radix-2 exige n potência de 2
    LengthOutOfRange     = 0x05, // n excede o buffer estático configurado
    IndexOutOfRange      = 0x06, // índice de feature / nó / bin fora de faixa
    NotInitialized       = 0x07, // uso do módulo antes do seu init()
    BufferTooSmall       = 0x08, // destino menor que o necessário
    NotFinite            = 0x09, // NaN ou infinito onde só finito é válido

    // ---- 0x10..0x1F vibração (MPU6050, I2C) --------------------------
    SensorAbsent         = 0x10, // endereço 0x68 não deu ACK: sensor ausente/sem energia
    SensorIdentity       = 0x11, // respondeu, mas WHO_AM_I != esperado (peça trocada/clone)
    BusSilent            = 0x12, // SDA/SCL presos em nível: pull-up, curto ou cabo rompido
    BusTimeout           = 0x13, // transação I2C não completou na cota
    SensorSelfTest       = 0x14, // autoteste do MPU6050 reprovado
    SampleRateMissed     = 0x15, // não sustentou 1 kHz: espectro deslocado, features inválidas
    SensorSaturated      = 0x16, // clipping no fundo de escala: RMS/curtose sem significado
    SensorStuck          = 0x17, // N amostras idênticas: sensor congelado, não máquina parada

    // ---- 0x20..0x2F temperatura (NTC 10k, ADC) -----------------------
    AdcNotConfigured     = 0x20, // atenuação/pino não configurados
    AdcOutOfRange        = 0x21, // leitura fora da janela útil do divisor
    ThermistorOpen       = 0x22, // leitura no topo da escala: NTC ou fio aberto
    ThermistorShorted    = 0x23, // leitura no fundo da escala: NTC em curto
    TemperatureImplausible = 0x24, // fora de -40..+125 °C: converteu, mas não é física

    // ---- 0x30..0x3F modelo (Isolation Forest) ------------------------
    ModelAbsent          = 0x30, // N_TREES == 0: firmware sem modelo treinado
    ModelMalformed       = 0x31, // arrays da árvore inconsistentes (filho fora de faixa)
    ModelDepthExceeded   = 0x32, // guarda de profundidade disparou: árvore corrompida ou cíclica
    ModelFeatureMismatch = 0x33, // ordem/quantidade de features difere do treino
    ModelVersionMismatch = 0x34, // header exportado de uma versão incompatível
    ScoreNotFinite       = 0x35, // score NaN/inf: nunca classificar como Normal

    // ---- 0x40..0x4F rádio (SX1278, SPI, pacote) ----------------------
    RadioAbsent          = 0x40, // registradores lêem 0x00/0xFF: chip ausente ou sem VCC
    RadioBusSilent       = 0x41, // SPI não responde (CS/SCK/MOSI/MISO)
    RadioConfigRejected  = 0x42, // frequência/potência/BW recusados pelo driver
    RadioTxTimeout       = 0x43, // TX_DONE não veio na cota
    RadioTxFailed        = 0x44, // transmissão retornou erro do rádio
    RadioSleepFailed     = 0x45, // CRÍTICO p/ energia: standby de 1,5 mA por 10 min
    PayloadTooLong       = 0x46, // pacote maior que o limite configurado
    ChecksumInvalid      = 0x47, // CRC-16/CCITT não confere
    PacketVersionUnsupported = 0x48, // versão de layout desconhecida do outro lado

    // ---- 0x50..0x5F plataforma ---------------------------------------
    SupplyVoltageLow     = 0x50, // bateria abaixo do mínimo para TX confiável
    WatchdogResetDetected= 0x51, // o boot anterior travou e o WDT reiniciou
    BrownoutResetDetected= 0x52, // queda de tensão reiniciou o dispositivo
    CycleDeadlineExceeded= 0x53, // fase ativa passou do orçamento de tempo/energia
    RtcStateCorrupt      = 0x54, // estado em RTC memory não confere (boot_count perdido)
    PeripheralPowerFault = 0x55, // rail +3V3_SW (load switch) não estabilizou

    // ---- 0xF0..0xFF genéricos ----------------------------------------
    NotImplemented       = 0xFE, // caminho ainda não escrito (deve falhar alto, não silenciar)
    Internal             = 0xFF, // falha não classificada: sempre um defeito deste modelo
};

static_assert(sizeof(Status) == 1, "Status precisa caber em 1 byte do pacote LoRa");

// Subsistema responsável, derivado da faixa do código. Serve ao triage em
// campo ("é o rádio ou é o sensor?") sem exigir a tabela completa.
enum class Subsystem : uint8_t {
    None        = 0x0, // Status::Ok
    Contract    = 0x1,
    Vibration   = 0x2,
    Temperature = 0x3,
    Model       = 0x4,
    Radio       = 0x5,
    Platform    = 0x6,
    Generic     = 0x7,
};

// ---------------------------------------------------------------------
// Predicados e conversões — todos constexpr, sem custo em release.
// ---------------------------------------------------------------------

constexpr bool is_ok(Status s) { return s == Status::Ok; }
constexpr bool is_error(Status s) { return s != Status::Ok; }

// Código numérico, para o byte de diagnóstico do pacote LoRa e para o log.
constexpr uint8_t status_code(Status s) { return static_cast<uint8_t>(s); }

constexpr Subsystem status_subsystem(Status s) {
    const uint8_t hi = static_cast<uint8_t>(static_cast<uint8_t>(s) >> 4);
    switch (hi) {
        case 0x0: return (s == Status::Ok) ? Subsystem::None : Subsystem::Contract;
        case 0x1: return Subsystem::Vibration;
        case 0x2: return Subsystem::Temperature;
        case 0x3: return Subsystem::Model;
        case 0x4: return Subsystem::Radio;
        case 0x5: return Subsystem::Platform;
        default:  return Subsystem::Generic;
    }
}

// Acumulador "o primeiro erro vence". O ciclo do Kaelix não aborta na
// primeira falha — ele degrada e segue até conseguir transmitir o
// diagnóstico. Este acumulador guarda a causa raiz sem deixar que um
// erro posterior e derivado a sobrescreva.
constexpr Status status_first_error(Status accumulated, Status incoming) {
    return is_error(accumulated) ? accumulated : incoming;
}

// String curta e estável para o log serial. Ponteiro para literal em
// .rodata: não aloca, não formata, seguro para chamar de qualquer ponto.
// Máximo de 12 caracteres, para que a linha de log caiba em 80 colunas.
constexpr const char* status_to_string(Status s) {
    switch (s) {
        case Status::Ok:                       return "OK";

        case Status::NullPointer:              return "NULL_PTR";
        case Status::InvalidArgument:          return "BAD_ARG";
        case Status::LengthZero:               return "LEN_ZERO";
        case Status::LengthNotPowerOfTwo:      return "LEN_NOT_P2";
        case Status::LengthOutOfRange:         return "LEN_RANGE";
        case Status::IndexOutOfRange:          return "IDX_RANGE";
        case Status::NotInitialized:           return "NO_INIT";
        case Status::BufferTooSmall:           return "BUF_SMALL";
        case Status::NotFinite:                return "NOT_FINITE";

        case Status::SensorAbsent:             return "MPU_ABSENT";
        case Status::SensorIdentity:           return "MPU_ID";
        case Status::BusSilent:                return "I2C_SILENT";
        case Status::BusTimeout:               return "I2C_TMO";
        case Status::SensorSelfTest:           return "MPU_STEST";
        case Status::SampleRateMissed:         return "RATE_MISS";
        case Status::SensorSaturated:          return "SATURATED";
        case Status::SensorStuck:              return "MPU_STUCK";

        case Status::AdcNotConfigured:         return "ADC_CFG";
        case Status::AdcOutOfRange:            return "ADC_RANGE";
        case Status::ThermistorOpen:           return "NTC_OPEN";
        case Status::ThermistorShorted:        return "NTC_SHORT";
        case Status::TemperatureImplausible:   return "TEMP_BAD";

        case Status::ModelAbsent:              return "NO_MODEL";
        case Status::ModelMalformed:           return "MODEL_BAD";
        case Status::ModelDepthExceeded:       return "TREE_DEPTH";
        case Status::ModelFeatureMismatch:     return "FEAT_ORDER";
        case Status::ModelVersionMismatch:     return "MODEL_VER";
        case Status::ScoreNotFinite:           return "SCORE_NAN";

        case Status::RadioAbsent:              return "RF_ABSENT";
        case Status::RadioBusSilent:           return "SPI_SILENT";
        case Status::RadioConfigRejected:      return "RF_CFG_REJ";
        case Status::RadioTxTimeout:           return "TX_TMO";
        case Status::RadioTxFailed:            return "TX_FAIL";
        case Status::RadioSleepFailed:         return "RF_NOSLEEP";
        case Status::PayloadTooLong:           return "PAYLOAD_BIG";
        case Status::ChecksumInvalid:          return "CRC_BAD";
        case Status::PacketVersionUnsupported: return "PKT_VER";

        case Status::SupplyVoltageLow:         return "VBAT_LOW";
        case Status::WatchdogResetDetected:    return "WDT_RESET";
        case Status::BrownoutResetDetected:    return "BROWNOUT";
        case Status::CycleDeadlineExceeded:    return "DEADLINE";
        case Status::RtcStateCorrupt:          return "RTC_BAD";
        case Status::PeripheralPowerFault:     return "PWR_FAULT";

        case Status::NotImplemented:           return "NOT_IMPL";
        case Status::Internal:                 return "INTERNAL";
    }
    // Código fora do enum: só acontece com byte recebido pelo ar ou com
    // memória corrompida. Não é um caso a esconder.
    return "UNKNOWN";
}

constexpr const char* subsystem_to_string(Subsystem d) {
    switch (d) {
        case Subsystem::None:        return "-";
        case Subsystem::Contract:    return "CONTRACT";
        case Subsystem::Vibration:   return "VIB";
        case Subsystem::Temperature: return "TEMP";
        case Subsystem::Model:       return "ML";
        case Subsystem::Radio:       return "RF";
        case Subsystem::Platform:    return "PLAT";
        case Subsystem::Generic:     return "GEN";
    }
    return "?";
}

// =====================================================================
// Asserção de parâmetro
// =====================================================================
//
// Dois comportamentos, escolhidos em tempo de compilação:
//
//   DESENVOLVIMENTO (padrão; `pio test -e native`, build de bancada)
//     KAELIX_ASSERT_ABORT == 1. A violação imprime
//     "arquivo:linha condição STATUS" em stderr e chama abort().
//     Motivo: uma violação de contrato é um bug do nosso código, e o pior
//     resultado possível é ela devolver um número plausível. Um teste que
//     passa 0.0f adiante e "passa" esconde exatamente o tipo de falha
//     silenciosa que o invariante de paridade numérica não detecta.
//
//   PRODUÇÃO (compilar com -D KAELIX_PRODUCTION)
//     KAELIX_ASSERT_ABORT == 0. A violação NÃO aborta: devolve o status
//     de erro e o ciclo continua degradado até conseguir transmitir o
//     diagnóstico e entrar em deep sleep.
//     Motivo: o Kaelix fica oito meses numa máquina sem ninguém por
//     perto. Abortar transforma um bug num dispositivo morto que não
//     conta o que aconteceu; devolver o status transforma o mesmo bug num
//     pacote com "MODEL_BAD" chegando ao gateway. Disponibilidade do
//     caminho de diagnóstico vale mais que fail-fast em campo.
//
// Em produção o texto e o abort() são removidos pelo pré-processador:
// nem <cstdio> é incluído, nem os literais de __FILE__ vão para a flash.
// =====================================================================

#ifndef KAELIX_ASSERT_ABORT
#  if defined(KAELIX_PRODUCTION)
#    define KAELIX_ASSERT_ABORT 0
#  else
#    define KAELIX_ASSERT_ABORT 1
#  endif
#endif

} // namespace kaelix

#if KAELIX_ASSERT_ABORT
#include <cstdio>
#include <cstdlib>

namespace kaelix::detail {

// Ponto único de parada em build de desenvolvimento: um breakpoint aqui
// pega qualquer violação de contrato do firmware inteiro.
[[noreturn]] inline void assert_failed(const char* file, int line,
                                       const char* expr, Status status) {
    std::fprintf(stderr, "[kaelix][ASSERT] %s:%d  (%s)  -> %s\n",
                 file, line, expr, status_to_string(status));
    std::fflush(stderr);
    std::abort();
}

} // namespace kaelix::detail

#  define KAELIX_ASSERT_FAIL_(expr_str, status) \
      ::kaelix::detail::assert_failed(__FILE__, __LINE__, expr_str, (status))
#else
#  define KAELIX_ASSERT_FAIL_(expr_str, status) ((void)0)
#endif

// KAELIX_REQUIRE(cond, status)
//   Para funções que devolvem `kaelix::Status`. Em produção, retorna
//   `status` ao chamador; em desenvolvimento, aborta.
#define KAELIX_REQUIRE(cond, status)                     \
    do {                                                 \
        if (!(cond)) {                                   \
            KAELIX_ASSERT_FAIL_(#cond, (status));        \
            return (status);                             \
        }                                                \
    } while (0)

// KAELIX_REQUIRE_VALUE(cond, status, fallback)
//   Para funções que NÃO podem mudar de assinatura — em especial as de
//   lib/signal_processing e lib/thermistor, que devolvem `float`. Trocar
//   o retorno delas por Status quebraria o invariante de paridade
//   numérica com training/kaelix_ml/features.py e invalidaria os 15 casos
//   já conferidos. Então elas ganham validação sem perder a assinatura:
//   o `fallback` deve ser exatamente o valor que a função já devolve hoje
//   nesse caso (0.0f nas guardas existentes), para que nenhum resultado
//   válido mude de bit.
#define KAELIX_REQUIRE_VALUE(cond, status, fallback)     \
    do {                                                 \
        if (!(cond)) {                                   \
            KAELIX_ASSERT_FAIL_(#cond, (status));        \
            return (fallback);                           \
        }                                                \
    } while (0)

// KAELIX_REQUIRE_VOID(cond, status)
//   Para funções sem retorno (fft_radix2). Em produção, a função não
//   executa e o chamador precisa ter validado antes — por isso todo uso
//   desta macro exige um KAELIX_REQUIRE equivalente na fronteira pública.
#define KAELIX_REQUIRE_VOID(cond, status)                \
    do {                                                 \
        if (!(cond)) {                                   \
            KAELIX_ASSERT_FAIL_(#cond, (status));        \
            return;                                      \
        }                                                \
    } while (0)

// KAELIX_ENSURE(cond, status)
//   Invariante interno (culpa nossa, não do chamador): índice de nó dentro
//   da árvore, cota de profundidade, resultado finito. Mesma semântica de
//   KAELIX_REQUIRE; existe separada para que a análise estática e a
//   revisão distingam "o chamador errou" de "nós erramos".
#define KAELIX_ENSURE(cond, status) KAELIX_REQUIRE(cond, status)

// KAELIX_CHECK(expr)
//   Propaga o primeiro erro de uma cadeia de chamadas que devolvem Status.
//   Não aborta em nenhum build: erro propagado não é violação de contrato.
#define KAELIX_CHECK(expr)                               \
    do {                                                 \
        const ::kaelix::Status kaelix_check_s_ = (expr); \
        if (::kaelix::is_error(kaelix_check_s_)) {       \
            return kaelix_check_s_;                      \
        }                                                \
    } while (0)
