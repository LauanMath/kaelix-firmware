#include "signal_processing.h"

#include "kaelix_status.h"

#include <cmath>

namespace kaelix::sensors {
namespace {

// ---------------------------------------------------------------------
// Rascunho da FFT
// ---------------------------------------------------------------------
// Rota escolhida: buffer estático dimensionado em tempo de compilação
// (rota "b" da política de memória, §4). A rota alternativa — exigir que
// todo chamador forneça o rascunho — continua disponível e é a que os
// testes usam, mas não é a rota padrão. O motivo da escolha:
//
//   - o único chamador de produção é `src/sensors/vibration.cpp`, que
//     roda uma vez por ciclo dentro de `setup()`. Empurrar 4 KB de
//     rascunho para ele não elimina o buffer, apenas o move para outro
//     módulo — e o move para uma camada (L2) que não compila no host,
//     onde o `static_assert` de tamanho deixaria de ser verificado pela
//     suíte `native`;
//   - com o buffer aqui, `FFT_MAX_N` fica ao lado da matemática que o
//     consome, e a validação `n <= FFT_MAX_N` é local em vez de ser uma
//     convenção entre módulos;
//   - o custo é a não reentrância, que o cabeçalho declara explicitamente
//     e que o regime do dispositivo torna verificável: superloop de um
//     disparo, sem escalonador, sem ISR chamando esta função.
//
// 2 × 512 × 4 B = 4 KB em `.bss`, de 512 KB de SRAM interna. Nunca
// liberado, nunca fragmentado, custo de alocação zero e limitado
// superiormente — o que devolve ao orçamento de 3,0 s de fase ativa uma
// premissa verificável.
float s_fft_re[FFT_MAX_N];
float s_fft_im[FFT_MAX_N];

// M_PI não faz parte do C++ padrão (é extensão POSIX/GNU): com
// `-std=c++17` estrito — que é o que os analisadores estáticos usam por
// padrão — o arquivo não compilaria. Mesmos dígitos, mesmo valor `double`.
constexpr double K_PI = 3.14159265358979323846;

// Reponderação 1/f. Mantido com os mesmos dígitos do código original: um
// fator constante multiplica todos os bins por igual e não moveria o
// argmax, mas em paridade numérica nada se muda "porque não deveria
// importar".
constexpr float TWO_PI = 6.28318530718f;

constexpr bool is_power_of_two(size_t n) {
    return (n != 0U) && ((n & (n - 1U)) == 0U);
}

} // namespace

float compute_rms(const float* samples, size_t n) {
    // `n == 0` devolve 0.0f em silêncio, e não por asserção, porque
    // features.py:16 faz o mesmo: é comportamento espelhado e acordado
    // entre os dois lados do par, não um contrato deixado sem verificar.
    if (n == 0U) {
        return 0.0f;
    }
    KAELIX_REQUIRE_VALUE(samples != nullptr, Status::NullPointer, 0.0f);

    double sum_sq = 0.0;
    // Cota superior: n, verificado pelo chamador (no dispositivo,
    // VIBRATION_SAMPLES). Nenhum limite vem de dado externo.
    for (size_t i = 0; i < n; ++i) {
        sum_sq += static_cast<double>(samples[i]) * static_cast<double>(samples[i]);
    }
    return static_cast<float>(std::sqrt(sum_sq / static_cast<double>(n)));
}

float compute_kurtosis(const float* samples, size_t n) {
    if (n == 0U) {
        return 0.0f;
    }
    KAELIX_REQUIRE_VALUE(samples != nullptr, Status::NullPointer, 0.0f);

    double mean = 0.0;
    for (size_t i = 0; i < n; ++i) {
        mean += samples[i];
    }
    mean /= static_cast<double>(n);

    double m2 = 0.0;
    double m4 = 0.0;
    for (size_t i = 0; i < n; ++i) {
        const double d = static_cast<double>(samples[i]) - mean;
        const double d2 = d * d;
        m2 += d2;
        m4 += d2 * d2;
    }
    m2 /= static_cast<double>(n);
    m4 /= static_cast<double>(n);

    // Igualdade exata com zero é desvio registrado DEV-003: é a guarda de
    // divisão correta aqui e é IDÊNTICA à de features.py:30. Trocar por
    // tolerância quebraria a paridade — não é para "corrigir".
    if (m2 == 0.0) {
        return 0.0f;
    }
    return static_cast<float>(m4 / (m2 * m2) - 3.0);
}

float compute_crest_factor(const float* samples, size_t n) {
    if (n == 0U) {
        return 0.0f;
    }
    KAELIX_REQUIRE_VALUE(samples != nullptr, Status::NullPointer, 0.0f);

    const float rms = compute_rms(samples, n);
    // DEV-003 novamente; espelha features.py:38.
    if (rms == 0.0f) {
        return 0.0f;
    }

    float peak = 0.0f;
    for (size_t i = 0; i < n; ++i) {
        const float a = std::fabs(samples[i]);
        if (a > peak) {
            peak = a;
        }
    }
    return peak / rms;
}

kaelix::Status fft_radix2(float* real, float* imag, size_t n) {
    KAELIX_REQUIRE(real != nullptr, Status::NullPointer);
    KAELIX_REQUIRE(imag != nullptr, Status::NullPointer);
    KAELIX_REQUIRE(n >= 2U, Status::LengthZero);
    KAELIX_REQUIRE(is_power_of_two(n), Status::LengthNotPowerOfTwo);

    // Permutação bit-reversal.
    //
    // Cota superior dos dois laços: o externo é limitado por `n`. O
    // interno é limitado por log2(n) — `bit` começa em n/2 e é dividido
    // por dois a cada passo, então chega a 0 em no máximo log2(n)
    // iterações, e `j & 0` é falso, o que encerra o laço. A cota é
    // provável a partir da própria variável de controle, sem contador
    // auxiliar.
    for (size_t i = 1U, j = 0U; i < n; ++i) {
        size_t bit = n >> 1U;
        for (; (j & bit) != 0U; bit >>= 1U) {
            j ^= bit;
        }
        j ^= bit;
        if (i < j) {
            const float tmp_re = real[i];
            real[i] = real[j];
            real[j] = tmp_re;
            const float tmp_im = imag[i];
            imag[i] = imag[j];
            imag[j] = tmp_im;
        }
    }

    // Borboletas Cooley-Tukey (decimação no tempo).
    //
    // Cota superior: o laço de estágios roda log2(n) vezes (`len` dobra),
    // e os dois internos somam exatamente n/2 borboletas por estágio.
    // Total limitado por (n/2)·log2(n) — com n <= FFT_MAX_N = 512, no
    // máximo 2304 borboletas, um WCET constante e analisável.
    for (size_t len = 2U; len <= n; len <<= 1U) {
        const size_t half = len / 2U;
        const double ang = -2.0 * K_PI / static_cast<double>(len);
        const float wr = static_cast<float>(std::cos(ang));
        const float wi = static_cast<float>(std::sin(ang));
        for (size_t i = 0; i < n; i += len) {
            float cur_wr = 1.0f;
            float cur_wi = 0.0f;
            for (size_t k = 0; k < half; ++k) {
                const size_t lo = i + k;
                const size_t hi = lo + half;

                const float ur = real[lo];
                const float ui = imag[lo];
                const float vr = real[hi] * cur_wr - imag[hi] * cur_wi;
                const float vi = real[hi] * cur_wi + imag[hi] * cur_wr;

                real[lo] = ur + vr;
                imag[lo] = ui + vi;
                real[hi] = ur - vr;
                imag[hi] = ui - vi;

                const float next_wr = cur_wr * wr - cur_wi * wi;
                const float next_wi = cur_wr * wi + cur_wi * wr;
                cur_wr = next_wr;
                cur_wi = next_wi;
            }
        }
    }
    return Status::Ok;
}

kaelix::Status dominant_frequency_scratch(const float* samples, size_t n, float sample_rate_hz,
                                          float band_lo_hz, float band_hi_hz,
                                          FftScratch scratch, float* out_hz) {
    KAELIX_REQUIRE(out_hz != nullptr, Status::NullPointer);
    // Escrito antes de qualquer outra validação: nenhum caminho de erro
    // pode deixar o destino indefinido para o chamador.
    *out_hz = 0.0f;

    KAELIX_REQUIRE(samples != nullptr, Status::NullPointer);
    KAELIX_REQUIRE(scratch.re != nullptr, Status::NullPointer);
    KAELIX_REQUIRE(scratch.im != nullptr, Status::NullPointer);
    KAELIX_REQUIRE(n != 0U, Status::LengthZero);
    KAELIX_REQUIRE(n >= FFT_MIN_N, Status::LengthOutOfRange);
    // A verificação que não existia e é a mais grave das três: a FFT
    // radix-2 com `n` não potência de 2 não falha alto — ela lê e escreve
    // fora do buffer e devolve um espectro errado. `dominant_freq_hz`
    // divergiria do treino sem que nada acusasse.
    KAELIX_REQUIRE(is_power_of_two(n), Status::LengthNotPowerOfTwo);
    KAELIX_REQUIRE(n <= scratch.capacity, Status::BufferTooSmall);
    KAELIX_REQUIRE(std::isfinite(sample_rate_hz) && sample_rate_hz > 0.0f,
                   Status::InvalidArgument);
    // Guardas de banda validadas ANTES da FFT, e não depois: no código
    // anterior o teste de `bin_hz` vinha depois de já ter alocado 4 KB e
    // rodado a transformada inteira. Validadas também por serem finitas,
    // porque `std::ceil`/`std::floor` de um quociente NaN convertido para
    // `size_t` é comportamento indefinido, e a guarda `< 1` seguinte é
    // cega a isso.
    KAELIX_REQUIRE(std::isfinite(band_lo_hz) && band_lo_hz >= 0.0f, Status::InvalidArgument);
    KAELIX_REQUIRE(std::isfinite(band_hi_hz) && band_hi_hz >= band_lo_hz, Status::InvalidArgument);

    const float bin_hz = sample_rate_hz / static_cast<float>(n);
    // Forma negada porque `!(x > 0)` também captura NaN, o que `x <= 0`
    // não faz. Alcançável só por underflow com `sample_rate_hz`
    // subnormal, mas é justamente o caso que uma guarda cega deixaria
    // passar como número.
    if (!(bin_hz > 0.0f)) {
        return Status::InvalidArgument;
    }

    // Cópia para o rascunho: substitui os dois `std::vector` do código
    // anterior sem tocar em nenhum valor.
    for (size_t i = 0; i < n; ++i) {
        scratch.re[i] = samples[i];
        scratch.im[i] = 0.0f;
    }
    KAELIX_CHECK(fft_radix2(scratch.re, scratch.im, n));

    // Só a primeira metade do espectro é útil (sinal real é simétrico).
    // A busca fica restrita à banda: o bin DC cai fora por construção, e
    // sem o limite inferior a ponderação 1/f faria o bin mais baixo
    // vencer sempre.
    //
    // Os índices são obtidos em `float` — exatamente a mesma expressão de
    // antes, para não mover um bit — mas a conversão para `size_t` só
    // acontece depois de o valor estar comprovadamente dentro de
    // [0, n/2 - 1]. Converter um `float` negativo ou gigante para tipo sem
    // sinal é comportamento indefinido, e a guarda por clamp que existia
    // antes era cega a ele.
    const size_t k_max = n / 2U - 1U;   // n >= 4 garante k_max >= 1
    const float k_lo_real = std::ceil(band_lo_hz / bin_hz);
    const float k_hi_real = std::floor(band_hi_hz / bin_hz);

    if (k_lo_real > static_cast<float>(k_max)) {
        return Status::Ok;   // banda inteira acima da meia-banda: 0.0f
    }
    size_t k_lo = 1U;
    if (k_lo_real > 1.0f) {
        k_lo = static_cast<size_t>(k_lo_real);
    }
    size_t k_hi = k_max;
    if (k_hi_real < static_cast<float>(k_max)) {
        k_hi = static_cast<size_t>(k_hi_real);
    }
    if (k_lo > k_hi) {
        return Status::Ok;
    }

    // Cota superior: k_hi - k_lo + 1 <= n/2 <= FFT_MAX_N/2 = 256.
    size_t best_bin = k_lo;
    float best_mag = -1.0f;
    for (size_t k = k_lo; k <= k_hi; ++k) {
        const float freq = static_cast<float>(k) * bin_hz;
        // |V(f)| = |A(f)| / (2*pi*f) — integração no domínio da
        // frequência, aplicada só à magnitude.
        const float mag =
            std::sqrt(scratch.re[k] * scratch.re[k] + scratch.im[k] * scratch.im[k]) /
            (TWO_PI * freq);
        if (mag > best_mag) {
            best_mag = mag;
            best_bin = k;
        }
    }
    *out_hz = static_cast<float>(best_bin) * bin_hz;
    return Status::Ok;
}

float dominant_frequency(const float* samples, size_t n, float sample_rate_hz,
                         float band_lo_hz, float band_hi_hz) {
    // Com rascunho estático, `n > FFT_MAX_N` deixa de ser "aloca mais" e
    // passa a ser estouro de buffer — é a consequência direta da política
    // de memória e por isso a verificação é obrigatória aqui, na fronteira
    // pública, e não delegada.
    KAELIX_REQUIRE_VALUE(n <= FFT_MAX_N, Status::LengthOutOfRange, 0.0f);

    float out_hz = 0.0f;
    const Status status = dominant_frequency_scratch(
        samples, n, sample_rate_hz, band_lo_hz, band_hi_hz,
        FftScratch{s_fft_re, s_fft_im, FFT_MAX_N}, &out_hz);
    if (is_error(status)) {
        // A causa é descartada aqui, e isso é uma perda consciente: esta
        // assinatura é contrato de paridade com features.py (§7.1) e não
        // pode devolver `Status`. `out_hz` já vale 0.0f, o mesmo valor que
        // todas as guardas do código anterior devolviam. Quem precisa da
        // causa — L2, para nunca transmitir um veredito fabricado — chama
        // `dominant_frequency_scratch`.
        return 0.0f;
    }
    return out_hz;
}

} // namespace kaelix::sensors
