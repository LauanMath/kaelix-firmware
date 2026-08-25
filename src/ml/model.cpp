#include "model.h"

#include "isolation_forest.h"
#include "isolation_forest_data.h"
#include "kaelix_status.h"

#include <cmath>
#include <cstdint>

namespace kaelix::ml {

// O vetor de features é montado à mão, por posição, contra um header
// GERADO por training/kaelix_ml/export_cpp.py. Se o treino passar a usar
// cinco features, `N_FEATURES` vira 5, o array ganha um quinto elemento
// zero-inicializado e o modelo passa a ser alimentado com um zero
// constante no lugar da feature — sem erro de compilação, sem aviso e sem
// sintoma observável, com o score simplesmente errado. Este static_assert
// transforma essa divergência silenciosa em falha de build.
//
// PENDÊNCIA (training/, fora desta posse): exportar também um
// FEATURE_ORDER_HASH — hash dos nomes das features na ordem de treino — e
// conferi-lo aqui por static_assert. O assert abaixo pega a QUANTIDADE;
// só o hash pega a ORDEM, e uma reordenação no Python avalia o modelo com
// os eixos trocados de forma igualmente silenciosa
// (Status::ModelFeatureMismatch existe para o caso em runtime).
static_assert(N_FEATURES == 4,
              "model.cpp monta o vetor de features na mão — atualize junto com export_cpp.py");

kaelix::Status model_init() {
    // Firmware sem modelo embarcado não é violação de contrato do
    // chamador: é o estado de hoje, até o treino da Fase 2.1 gerar as
    // árvores. Por isso um `if` e não um KAELIX_REQUIRE — este caminho não
    // pode abortar na bancada, ele precisa virar um código de diagnóstico
    // que chega ao gateway.
    if (N_TREES <= 0) {
        return kaelix::Status::ModelAbsent;
    }
    if (isolation_forest_trees == nullptr) {
        // Header gerado com N_TREES > 0 e o ponteiro ainda nulo seria
        // dereferência direta na primeira inferência.
        return kaelix::Status::ModelMalformed;
    }
    return isolation_forest_validate(isolation_forest_trees, N_TREES, N_FEATURES);
}

kaelix::Status model_infer(const kaelix::sensors::VibrationFeatures& features,
                           [[maybe_unused]] float temperature_c,
                           kaelix::MachineState* out_state) {
    KAELIX_REQUIRE(out_state != nullptr, kaelix::Status::NullPointer);

    // Primeira instrução com efeito: a partir daqui, todo `return` de erro
    // deixa o veredito em Unknown.
    *out_state = kaelix::MachineState::Unknown;

    // TODO (Fase 2.1): a temperatura ainda não é feature do modelo. Quando
    // passar a ser, ela entra no array abaixo E em FEATURE_ORDER no
    // Python, na mesma ordem — o static_assert de N_FEATURES é o que
    // garante que as duas metades da mudança andem juntas.
    if (N_TREES <= 0) {
        return kaelix::Status::ModelAbsent;
    }

    const float x[N_FEATURES] = {
        features.rms,
        features.kurtosis,
        features.crest_factor,
        features.dominant_freq_hz,
    };
    for (int32_t i = 0; i < N_FEATURES; ++i) {
        if (!std::isfinite(x[i])) {
            return kaelix::Status::NotFinite;
        }
    }

    float score = 0.0f;
    KAELIX_CHECK(isolation_forest_score(x, N_FEATURES, isolation_forest_trees,
                                        N_TREES, SUBSAMPLE_SIZE, &score));

    // Cinto e suspensórios sobre a garantia de lib/: `score > limiar` com
    // score NaN avalia false e devolveria Normal — o detector falhando
    // exatamente na direção em que não pode falhar.
    KAELIX_ENSURE(std::isfinite(score), kaelix::Status::ScoreNotFinite);

    *out_state = (score > ANOMALY_THRESHOLD) ? kaelix::MachineState::Anomalous
                                             : kaelix::MachineState::Normal;
    return kaelix::Status::Ok;
}

} // namespace kaelix::ml
