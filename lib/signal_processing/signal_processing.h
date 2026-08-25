#pragma once

#include <cstddef>

#include "kaelix_status.h"

// Funções puras de processamento de sinal — sem dependência de Arduino
// ou hardware, para poderem ser testadas no ambiente `native` (host) e
// depois reutilizadas em `src/sensors/vibration.cpp` sobre os dados
// reais do MPU6050. A mesma lógica é replicada em Python em
// `training/kaelix_ml/features.py`, para não haver divergência entre
// treino e inferência embarcada (§7 do documento de arquitetura).
//
// Duas propriedades deste módulo são contrato, não estilo:
//
//   1. Nenhuma alocação dinâmica. O Kaelix acorda ~144 vezes por dia
//      durante ~8 meses; um `std::vector` por ciclo é da ordem de 35 mil
//      alocações no mesmo heap ao longo da vida útil, sem nenhum recurso
//      para diagnosticar fragmentação em campo, e com `-fno-exceptions`
//      uma falha de alocação vira `abort()` → pânico → boot loop a
//      ~40 mA. O rascunho da FFT vive em `.bss`, dimensionado em tempo de
//      compilação (§4).
//
//   2. A assinatura das funções numéricas não muda. Elas continuam
//      devolvendo `float`, porque `training/kaelix_ml/features.py` é o
//      par verificado delas e a paridade está aferida em 15 casos. A
//      validação de parâmetro entra por `KAELIX_REQUIRE_VALUE`, cujo
//      `fallback` é exatamente o valor que a função já devolvia naquele
//      caso — nenhum resultado válido muda de bit (§7.1).

namespace kaelix::sensors {

// ---------------------------------------------------------------------
// Dimensionamento da cadeia de vibração
// ---------------------------------------------------------------------
// §4 do documento de arquitetura exige uma única constante de configuração
// governando toda a cadeia, com todo buffer derivado dela — nada
// dimensionado por número solto. O documento a chama de
// `KAELIX_FFT_MAX_N`; aqui ela é `constexpr` e não macro porque §3 reserva
// o prefixo `KAELIX_` para macros e determina que constante é `constexpr`.
// Mesmo valor e mesma origem, com a vantagem de ter tipo e de poder ser
// verificada por `static_assert`.
constexpr size_t VIBRATION_SAMPLES = 512;   // amostras por ciclo, a 1 kHz
constexpr size_t FFT_MAX_N = VIBRATION_SAMPLES;

// Piso da FFT usado pela extração de frequência dominante. Espelha o
// `if n < 4` de features.py: abaixo disso não há meia-banda utilizável
// (k_hi = n/2 - 1 seria 0, ou seja, só o bin DC).
constexpr size_t FFT_MIN_N = 4;

static_assert((FFT_MAX_N & (FFT_MAX_N - 1)) == 0,
              "FFT radix-2 exige que o buffer estático seja potência de 2");
static_assert(FFT_MAX_N >= FFT_MIN_N,
              "o buffer estático precisa comportar o menor bloco aceito");

// Rascunho da FFT fornecido pelo chamador. Existe como struct — e não
// como três parâmetros soltos — porque `re` e `im` compartilham um único
// invariante ("ambos têm pelo menos `capacity` elementos") que só faz
// sentido verificar junto.
struct FftScratch {
    float* re;
    float* im;
    size_t capacity;
};

// RMS (root mean square) das amostras.
float compute_rms(const float* samples, size_t n);

// Curtose de excesso (Fisher: normal = 0) das amostras.
float compute_kurtosis(const float* samples, size_t n);

// Fator de crista: pico absoluto / RMS.
float compute_crest_factor(const float* samples, size_t n);

// FFT radix-2 Cooley-Tukey (decimação no tempo), in-place.
//
// Devolve `Status` em vez de `void`: com `n` não potência de 2 o laço de
// borboletas indexa `real[i + k + len/2]` além do buffer — estouro
// comprovado com AddressSanitizer em `n = 6`. Uma função `void` não tem
// como recusar, e no ESP32-S3 (sem MPU) o resultado seria corrupção de
// pilha silenciosa. Deliberadamente NÃO usa `KAELIX_REQUIRE_VOID`: em
// produção aquela macro faria a FFT não executar e o chamador seguir
// interpretando amostras do domínio do TEMPO como bins espectrais.
[[nodiscard]] kaelix::Status fft_radix2(float* real, float* imag, size_t n);

// Banda de análise, em Hz — a mesma da ISO 10816-3. O limite inferior
// não é cosmético: a integração para velocidade pesa 1/f, então sem ele
// o bin mais baixo venceria sempre.
constexpr float DOMINANT_BAND_LO_HZ = 10.0f;
constexpr float DOMINANT_BAND_HI_HZ = 1000.0f;

// Frequência dominante do espectro de VELOCIDADE, band-limitado.
//
// Por que velocidade e não aceleração: aceleração escala com ω², então o
// espectro de aceleração é dominado pelo conteúdo de alta frequência —
// tipicamente um modo estrutural da montagem, que é o mesmo com a máquina
// sadia ou defeituosa. Medido no MAFAULDA: o pico de aceleração fica em
// 117 Hz independente da rotação (correlação com a rotação real: -0,018),
// enquanto no espectro de velocidade o pico cai sobre 1x rotação, que é a
// assinatura de desbalanceamento e desalinhamento.
//
// A conversão é feita na magnitude: |V(f)| = |A(f)| / (2*pi*f). A fase não
// importa para escolher o bin de pico, então não é preciso integrar o
// sinal completo — só reponderar o espectro que a FFT já produziu.
//
// ESTA SOBRECARGA NÃO É REENTRANTE. Ela usa o rascunho estático de escopo
// de arquivo (2 × FFT_MAX_N floats = 4 KB em `.bss`), então duas execuções
// simultâneas corrompem uma à outra. Isso é aceitável e verificável no
// Kaelix por uma razão estrutural, não por otimismo: todo o trabalho
// acontece em `setup()`, num superloop de um disparo, sem escalonador, sem
// tarefa concorrente e sem chamada a partir de ISR. Se algum dia houver um
// segundo contexto de execução, use `dominant_frequency_scratch`.
//
// Devolve 0.0f — o mesmo valor de todas as guardas anteriores — quando o
// contrato é violado. Quem precisa saber POR QUE deu 0.0f (e o §5 diz que
// L2 precisa, para nunca transmitir um veredito fabricado) chama
// `dominant_frequency_scratch`, que devolve a causa.
float dominant_frequency(const float* samples, size_t n, float sample_rate_hz,
                         float band_lo_hz = DOMINANT_BAND_LO_HZ,
                         float band_hi_hz = DOMINANT_BAND_HI_HZ);

// Mesma matemática, com o rascunho vindo do chamador — reentrante e com a
// causa da falha preservada. É aqui que a implementação mora de fato: a
// sobrecarga acima é um invólucro fino sobre esta, para que exista uma
// única fonte da verdade numérica e a paridade não possa divergir entre
// os dois caminhos.
//
// `*out_hz` recebe 0.0f antes de qualquer validação, de modo que nenhum
// caminho de erro deixe o destino indefinido.
[[nodiscard]] kaelix::Status dominant_frequency_scratch(
    const float* samples, size_t n, float sample_rate_hz,
    float band_lo_hz, float band_hi_hz,
    FftScratch scratch, float* out_hz);

} // namespace kaelix::sensors
