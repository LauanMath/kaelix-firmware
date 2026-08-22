#include "signal_processing.h"

#include <algorithm>
#include <cmath>
#include <vector>

namespace kaelix::sensors {

float compute_rms(const float* samples, size_t n) {
    if (n == 0) return 0.0f;
    double sum_sq = 0.0;
    for (size_t i = 0; i < n; ++i) sum_sq += double(samples[i]) * double(samples[i]);
    return static_cast<float>(std::sqrt(sum_sq / double(n)));
}

float compute_kurtosis(const float* samples, size_t n) {
    if (n == 0) return 0.0f;

    double mean = 0.0;
    for (size_t i = 0; i < n; ++i) mean += samples[i];
    mean /= double(n);

    double m2 = 0.0, m4 = 0.0;
    for (size_t i = 0; i < n; ++i) {
        double d = double(samples[i]) - mean;
        double d2 = d * d;
        m2 += d2;
        m4 += d2 * d2;
    }
    m2 /= double(n);
    m4 /= double(n);

    if (m2 == 0.0) return 0.0f;
    return static_cast<float>(m4 / (m2 * m2) - 3.0);
}

float compute_crest_factor(const float* samples, size_t n) {
    float rms = compute_rms(samples, n);
    if (rms == 0.0f) return 0.0f;

    float peak = 0.0f;
    for (size_t i = 0; i < n; ++i) {
        float a = std::fabs(samples[i]);
        if (a > peak) peak = a;
    }
    return peak / rms;
}

void fft_radix2(float* real, float* imag, size_t n) {
    // Permutação bit-reversal.
    for (size_t i = 1, j = 0; i < n; ++i) {
        size_t bit = n >> 1;
        for (; j & bit; bit >>= 1) j ^= bit;
        j ^= bit;
        if (i < j) {
            std::swap(real[i], real[j]);
            std::swap(imag[i], imag[j]);
        }
    }

    // Borboletas Cooley-Tukey (decimação no tempo).
    for (size_t len = 2; len <= n; len <<= 1) {
        double ang = -2.0 * M_PI / double(len);
        float wr = static_cast<float>(std::cos(ang));
        float wi = static_cast<float>(std::sin(ang));
        for (size_t i = 0; i < n; i += len) {
            float cur_wr = 1.0f, cur_wi = 0.0f;
            for (size_t k = 0; k < len / 2; ++k) {
                float ur = real[i + k];
                float ui = imag[i + k];
                float vr = real[i + k + len / 2] * cur_wr - imag[i + k + len / 2] * cur_wi;
                float vi = real[i + k + len / 2] * cur_wi + imag[i + k + len / 2] * cur_wr;

                real[i + k] = ur + vr;
                imag[i + k] = ui + vi;
                real[i + k + len / 2] = ur - vr;
                imag[i + k + len / 2] = ui - vi;

                float next_wr = cur_wr * wr - cur_wi * wi;
                float next_wi = cur_wr * wi + cur_wi * wr;
                cur_wr = next_wr;
                cur_wi = next_wi;
            }
        }
    }
}

float dominant_frequency(const float* samples, size_t n, float sample_rate_hz,
                         float band_lo_hz, float band_hi_hz) {
    if (n < 4) return 0.0f;

    std::vector<float> real(samples, samples + n);
    std::vector<float> imag(n, 0.0f);
    fft_radix2(real.data(), imag.data(), n);

    const float bin_hz = sample_rate_hz / static_cast<float>(n);
    if (bin_hz <= 0.0f) return 0.0f;

    // Só a primeira metade do espectro é útil (sinal real é simétrico).
    // A busca fica restrita à banda: o bin DC cai fora por construção, e
    // sem o limite inferior a ponderação 1/f faria o bin mais baixo
    // vencer sempre.
    size_t k_lo = static_cast<size_t>(std::ceil(band_lo_hz / bin_hz));
    if (k_lo < 1) k_lo = 1;
    size_t k_hi = static_cast<size_t>(std::floor(band_hi_hz / bin_hz));
    if (k_hi > n / 2 - 1) k_hi = n / 2 - 1;
    if (k_lo > k_hi) return 0.0f;

    constexpr float TWO_PI = 6.28318530718f;
    size_t best_bin = k_lo;
    float best_mag = -1.0f;
    for (size_t k = k_lo; k <= k_hi; ++k) {
        float freq = static_cast<float>(k) * bin_hz;
        // |V(f)| = |A(f)| / (2*pi*f) — integração no domínio da
        // frequência, aplicada só à magnitude.
        float mag = std::sqrt(real[k] * real[k] + imag[k] * imag[k]) / (TWO_PI * freq);
        if (mag > best_mag) {
            best_mag = mag;
            best_bin = k;
        }
    }
    return static_cast<float>(best_bin) * bin_hz;
}

} // namespace kaelix::sensors
