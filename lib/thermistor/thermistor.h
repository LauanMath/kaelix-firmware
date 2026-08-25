#pragma once

#include <cstdint>
#include <limits>

#include "kaelix_status.h"

// Matemática pura de conversão do termistor NTC — sem dependência de
// Arduino, testável no ambiente `native`. A leitura ADC real fica em
// src/sensors/temperature.cpp.
//
// ---------------------------------------------------------------------
// Por que estas funções continuam devolvendo `float`
// ---------------------------------------------------------------------
// A regra de L1 em docs/ARQUITETURA-SOFTWARE.md §5 é explícita: a
// matemática pura mantém o retorno `float` e valida com KAELIX_REQUIRE*.
// Trocar o retorno por `Status` mudaria todos os pontos de chamada e o
// formato dos testes de paridade sem ganhar nada — o diagnóstico cabe num
// parâmetro de saída. Então cada função ganhou um `out_status` OPCIONAL:
// quando não-nulo, ele é SEMPRE escrito (Status::Ok inclusive), e o valor
// de retorno passa a ser redundante com ele.
//
// ---------------------------------------------------------------------
// A sentinela é NaN, e isso é deliberado
// ---------------------------------------------------------------------
// Toda falha devolve `NTC_READING_INVALID` (NaN silencioso), conforme a
// tabela de degradação de §5 ("temperature_c = sentinela (NaN)").
// 0.0f seria a escolha errada: 0 °C é uma temperatura perfeitamente
// plausível para uma máquina, e um sentinela que se disfarça de medição é
// exatamente a falha silenciosa que este trabalho existe para eliminar.
// NaN não é confundível com leitura, sobrevive a qualquer aritmética
// posterior e é detectável com um único `std::isfinite`.
//
// O contrato para o chamador é, portanto: NUNCA transmitir o `float` sem
// olhar o `Status`. NaN no pacote sem o código de diagnóstico junto é um
// defeito do chamador, não desta biblioteca.
//
// ---------------------------------------------------------------------
// Duas classes de falha, dois comportamentos
// ---------------------------------------------------------------------
//   1. VIOLAÇÃO DE CONTRATO (0x01..0x0F) — adc_max == 0, beta == 0,
//      r_nominal_ohm <= 0, t_nominal_c <= -273,15. Nenhuma dessas vem do
//      mundo físico: são constantes de datasheet erradas no código, ou
//      seja, bug nosso. Usam KAELIX_REQUIRE_VALUE e portanto ABORTAM em
//      build de desenvolvimento (§5, "desenvolvimento aborta").
//
//   2. DEFEITO DE CAMPO (0x2_) — NTC em curto, NTC/fio aberto. São o
//      motivo de o dispositivo existir e acontecem com o firmware
//      correto. NÃO abortam em build nenhum: devolvem sentinela + Status
//      e o ciclo segue para transmitir o diagnóstico.
//
// Misturar as duas classes é o erro que torna um modelo de erro inútil:
// se um fio rompido abortasse na bancada, a equipe desligaria a asserção.

namespace kaelix::sensors {

// Sentinela de "não é uma medição". Ver bloco acima.
inline constexpr float NTC_READING_INVALID = std::numeric_limits<float>::quiet_NaN();

// ---------------------------------------------------------------------
// Limiares de detecção de curto/aberto — derivação, não números mágicos
// ---------------------------------------------------------------------
// Divisor: Vcc -> R_FIXED (10 k) -> nó de leitura -> NTC -> GND, logo
//   ratio = V_no/Vcc = R_ntc / (R_fixed + R_ntc)
// e ratio cresce quando o NTC esfria (coeficiente negativo).
//
// Faixa útil do NTC 10k B3950 sobre R_fixed = 10 k, nos extremos de
// operação do equipamento monitorado (-40 °C a +125 °C):
//
//   T = +125 °C  ->  R =    358,8 ohm  ->  ratio = 0,03464
//   T =  +25 °C  ->  R = 10.000   ohm  ->  ratio = 0,50000
//   T =  -40 °C  ->  R =  401.860 ohm  ->  ratio = 0,97572
//
// Os limiares ficam FORA dessa janela, com margem para ruído de ADC:
//
//   ratio <= 0,02  ->  R <=    204 ohm  ->  +149,0 °C  (impossível)
//   ratio >= 0,99  ->  R >= 990.000 ohm ->   -51,8 °C  (impossível)
//
// A folga é intencional e reparte a responsabilidade em duas camadas:
// L1 (aqui) detecta o que é ELETRICAMENTE impossível — o divisor saturou,
// só um curto ou um circuito aberto produz isso. L2
// (src/sensors/temperature.cpp) detecta o que é FISICAMENTE implausível,
// aplicando a janela -40..+125 °C e emitindo TemperatureImplausible.
// Como [-51,8; +149,0] contém estritamente [-40; +125], as duas
// verificações nunca se sobrepõem nem deixam buraco entre elas.
//
// Estes limiares SUBSTITUÍRAM um clamp em [0,001; 0,999], que convertia
// as duas falhas de campo mais prováveis do NTC em temperaturas de
// aparência plausível: +349,7 °C para fio em curto e -77,2 °C para fio
// rompido, ambas transmitidas ao gateway com CRC válido. Um clamp
// silencia a falha exatamente onde ela precisava gritar.
inline constexpr float NTC_RATIO_SHORTED_MAX = 0.02f;
inline constexpr float NTC_RATIO_OPEN_MIN    = 0.99f;

// ---------------------------------------------------------------------
// Precisão esperada
// ---------------------------------------------------------------------
// O erro é dominado pela quantização do ADC, não pela aritmética float32.
// Com 12 bits (1 LSB = 1/4095 de ratio), dT/dratio dá:
//
//   ratio = 0,500 (  +25 °C)  ->  0,022 °C por LSB   (melhor caso)
//   ratio = 0,976 (  -40 °C)  ->  0,142 °C por LSB
//   ratio = 0,035 ( +125 °C)  ->  0,294 °C por LSB   (pior caso)
//
// A aritmética em float32 (eps ~1,2e-7) contribui com menos de 1e-3 °C em
// toda a faixa — duas ordens de grandeza abaixo da quantização. Somem-se
// a isso as tolerâncias de peça, que dominam tudo: R_fixed 1% e beta ±1%
// valem alguns °C e só somem com calibração ponto a ponto, ainda não
// feita. Ou seja: a REPETIBILIDADE é ~0,3 °C, a EXATIDÃO absoluta é da
// ordem de ±3 °C até haver calibração. Para manutenção preditiva o que
// importa é a tendência, e a repetibilidade basta — mas o número absoluto
// não deve ser apresentado como se fosse metrológico.

// Converte uma leitura ADC de um divisor de tensão para a resistência do
// NTC, em ohms. `adc_raw` deve ser proporcional a Vcc (adc_max = fundo de
// escala).
//
// Faixa válida de operação:
//   adc_max     [1 .. 65535]        (0 é violação de contrato)
//   adc_raw     [0 .. adc_max]      (acima de adc_max é lido como aberto)
//   r_fixed_ohm finito e > 0        (10.000 no hardware do Kaelix)
//   retorno     (0 .. ~990.000] ohm, ou NTC_READING_INVALID
//
// Status possíveis: Ok, InvalidArgument, ThermistorShorted,
// ThermistorOpen, NotFinite.
//
// TODO: confirmar topologia do divisor contra o esquemático final (Fase 3).
[[nodiscard]] float ntc_resistance_from_adc(uint16_t adc_raw, uint16_t adc_max,
                                            float r_fixed_ohm,
                                            kaelix::Status* out_status = nullptr);

// Mesma matemática, entrada em milivolts. É esta a forma correta no
// ESP32-S3: o ADC bruto é sensivelmente não-linear, e `analogReadMilliVolts`
// aplica a curva de calibração gravada no eFuse de fábrica. Usar a
// contagem crua assume uma linearidade que o hardware não tem.
//
// Faixa válida: vcc_mv [1 .. 65535] (3300 no Kaelix), mv [0 .. vcc_mv].
[[nodiscard]] float ntc_resistance_from_millivolts(uint16_t mv, uint16_t vcc_mv,
                                                   float r_fixed_ohm,
                                                   kaelix::Status* out_status = nullptr);

// Equação B (Steinhart-Hart simplificada): converte a resistência do NTC
// para temperatura em °C, dados a resistência nominal, o beta e a
// temperatura nominal (datasheet: NTC 10K, beta 3950, nominal a 25 °C).
//
// Faixa válida de operação:
//   resistance_ohm  finito e > 0   (domínio de log; 0 daria log(0) = -inf,
//                                   que hoje devolvia exatamente -273,15 °C
//                                   — física de aparência a partir de um
//                                   infinito)
//   r_nominal_ohm   finito e > 0   (10.000)
//   beta            finito e > 0   (3950; 0 divide por zero)
//   t_nominal_c     > -273,15      (25,0; -273,15 divide por zero em kelvin)
//   retorno         (-273,15 .. +inf) °C, ou NTC_READING_INVALID
//
// `resistance_ohm` NÃO-FINITO é tratado como propagação, não como bug: é o
// sentinela que `ntc_resistance_from_adc` acabou de devolver por curto ou
// circuito aberto. Devolve NotFinite sem abortar — abortar aqui puniria o
// chamador por uma falha de campo que ele já diagnosticou.
//
// Status possíveis: Ok, InvalidArgument, NotFinite.
[[nodiscard]] float ntc_resistance_to_celsius(float resistance_ohm, float r_nominal_ohm,
                                              float beta, float t_nominal_c,
                                              kaelix::Status* out_status = nullptr);

} // namespace kaelix::sensors
