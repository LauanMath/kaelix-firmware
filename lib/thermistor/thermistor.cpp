#include "thermistor.h"

#include <cmath>

namespace kaelix::sensors {
namespace {

// O `out_status` é opcional; centralizar a escrita evita repetir o teste
// de nulo em cada guarda e garante que nenhum caminho de saída esqueça de
// preenchê-lo.
inline void set_status(kaelix::Status* out_status, kaelix::Status s) {
    if (out_status != nullptr) {
        *out_status = s;
    }
}

} // namespace

// NTC_REQUIRE(cond, st) — violação de contrato COM diagnóstico.
//
// KAELIX_REQUIRE_VALUE retorna de dentro da própria macro, então um
// `set_status()` escrito depois dela nunca executaria: o diagnóstico
// precisa ser gravado antes. `cond` é avaliada duas vezes, e é por isso
// que toda condição usada aqui é pura e barata (comparação de escalar).
// A alternativa — guardar `cond` numa variável — faria o build de
// desenvolvimento imprimir o nome da variável em vez do texto da
// condição, perdendo justamente a informação pela qual a asserção existe.
//
// Desvio consciente de MISRA C++ 2008 16-0-4 (macro função-símile), da
// mesma família do desvio já assumido por kaelix_status.h: capturar
// __FILE__/__LINE__ e retornar cedo é inexprimível como função.
#define NTC_REQUIRE(cond, st)                                          \
    do {                                                               \
        if (!(cond)) {                                                 \
            set_status(out_status, (st));                              \
        }                                                              \
        KAELIX_REQUIRE_VALUE((cond), (st), NTC_READING_INVALID);       \
    } while (0)

float ntc_resistance_from_adc(uint16_t adc_raw, uint16_t adc_max, float r_fixed_ohm,
                              kaelix::Status* out_status) {
    // Contrato primeiro, e ANTES da divisão: `adc_max == 0` produzia
    // 0/0 = NaN, e as guardas por clamp que vinham em seguida usavam `<`
    // e `>`, ambas falsas para NaN — o NaN atravessava intacto até o
    // pacote LoRa, empacotado com CRC válido.
    NTC_REQUIRE(adc_max > 0, kaelix::Status::InvalidArgument);
    NTC_REQUIRE(std::isfinite(r_fixed_ohm) && r_fixed_ohm > 0.0f,
                kaelix::Status::InvalidArgument);

    const float ratio = static_cast<float>(adc_raw) / static_cast<float>(adc_max);

    // Defeitos de campo: relatados, nunca abortados. Ver a derivação dos
    // limiares em thermistor.h. `adc_raw > adc_max` cai naturalmente aqui,
    // porque ratio > 1 > NTC_RATIO_OPEN_MIN.
    if (ratio <= NTC_RATIO_SHORTED_MAX) {
        set_status(out_status, kaelix::Status::ThermistorShorted);
        return NTC_READING_INVALID;
    }
    if (ratio >= NTC_RATIO_OPEN_MIN) {
        set_status(out_status, kaelix::Status::ThermistorOpen);
        return NTC_READING_INVALID;
    }

    // Com ratio em (0,02; 0,99) o denominador vale no mínimo 0,01: a
    // divisão não pode estourar. A verificação final existe mesmo assim
    // porque é ela que fecha a promessa da assinatura — nenhum caminho
    // devolve não-finito sem dizer.
    const float resistance_ohm = r_fixed_ohm * ratio / (1.0f - ratio);
    if (!(std::isfinite(resistance_ohm) && resistance_ohm > 0.0f)) {
        set_status(out_status, kaelix::Status::NotFinite);
        return NTC_READING_INVALID;
    }

    set_status(out_status, kaelix::Status::Ok);
    return resistance_ohm;
}

float ntc_resistance_from_millivolts(uint16_t mv, uint16_t vcc_mv, float r_fixed_ohm,
                                     kaelix::Status* out_status) {
    // Mesma razão de divisão de tensão; só muda a unidade da escala.
    return ntc_resistance_from_adc(mv, vcc_mv, r_fixed_ohm, out_status);
}

float ntc_resistance_to_celsius(float resistance_ohm, float r_nominal_ohm, float beta,
                                float t_nominal_c, kaelix::Status* out_status) {
    constexpr float KELVIN_OFFSET = 273.15f;

    // Entrada não-finita é o sentinela que `ntc_resistance_from_adc`
    // devolveu por curto ou circuito aberto — propagação de uma falha já
    // diagnosticada, não bug do chamador. Por isso vem ANTES do bloco de
    // contrato e não aborta em build nenhum.
    if (!std::isfinite(resistance_ohm)) {
        set_status(out_status, kaelix::Status::NotFinite);
        return NTC_READING_INVALID;
    }

    // Contrato. Os três primeiros protegem o domínio de log() e a divisão
    // por beta; o quarto protege a conversão para kelvin, que divergiria
    // exatamente no zero absoluto. Com resistance_ohm = 0 esta função
    // devolvia -273,15 °C: o resultado de log(0) = -inf com cara de física.
    NTC_REQUIRE(resistance_ohm > 0.0f, kaelix::Status::InvalidArgument);
    NTC_REQUIRE(std::isfinite(r_nominal_ohm) && r_nominal_ohm > 0.0f,
                kaelix::Status::InvalidArgument);
    NTC_REQUIRE(std::isfinite(beta) && beta > 0.0f, kaelix::Status::InvalidArgument);
    NTC_REQUIRE(std::isfinite(t_nominal_c) && t_nominal_c > -KELVIN_OFFSET,
                kaelix::Status::InvalidArgument);

    const float t_nominal_k = t_nominal_c + KELVIN_OFFSET;
    const float inv_t =
        1.0f / t_nominal_k + (1.0f / beta) * std::log(resistance_ohm / r_nominal_ohm);
    const float celsius = (1.0f / inv_t) - KELVIN_OFFSET;

    // inv_t == 0 exige um cancelamento exato entre os dois termos —
    // improvável, não impossível em float32 — e daria 1/0 = inf, que sai
    // daqui como -273,15 °C. Um número tão redondo passaria por medição.
    if (!(std::isfinite(celsius) && celsius > -KELVIN_OFFSET)) {
        set_status(out_status, kaelix::Status::NotFinite);
        return NTC_READING_INVALID;
    }

    set_status(out_status, kaelix::Status::Ok);
    return celsius;
}

#undef NTC_REQUIRE

} // namespace kaelix::sensors
