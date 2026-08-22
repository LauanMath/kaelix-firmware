# Arquitetura e decisões técnicas

Este documento registra o *porquê* das decisões não óbvias do projeto —
útil tanto para retomar o desenvolvimento quanto para justificar escolhas
numa defesa de TCC.

## Princípio geral: separar matemática pura de acesso a hardware

Cada capacidade do firmware (processamento de vibração, conversão de
temperatura, inferência do modelo) foi dividida em duas camadas:

- **`lib/<nome>/`** — funções puras (sem `Arduino.h`, sem I2C/ADC/SPI real),
  testáveis no ambiente `native` do PlatformIO, que compila e roda no host
  (Mac/Linux) sem precisar do ESP32-S3 nem de simulador.
- **`src/sensors/`, `src/ml/`, `src/comms/`, `src/power/`** — a camada que
  fala com o hardware de verdade (ou, por enquanto, com placeholders até o
  hardware físico chegar) e chama as funções de `lib/`.

Essa separação foi o que permitiu desenvolver e validar ~90% da lógica do
projeto sem ter o ESP32-S3, o MPU6050 ou o RA-02 em mãos: quando o hardware
chegar, só a camada `src/` precisa mudar (trocar buffers zerados por
leituras I2C/ADC reais), a matemática já está testada.

## Processamento de vibração (`lib/signal_processing/`)

RMS, curtose (excesso, convenção de Fisher — normal = 0), fator de crista
(pico/RMS) e frequência dominante, calculada via uma implementação própria
de FFT radix-2 Cooley-Tukey (decimação no tempo, iterativa, sem alocação
dinâmica).

**Por que uma FFT própria em vez da biblioteca `arduinoFFT`?** A
implementação própria compila tanto no ambiente `esp32-s3` quanto no
`native`, permitindo testar a FFT no host com sinais sintéticos (senoides
de frequência conhecida) antes de qualquer hardware. `arduinoFFT` foi
avaliada mas nunca chegou a ser usada — removida do `platformio.ini`.

`n` (número de amostras) precisa ser potência de 2 — responsabilidade do
chamador (`vibration_read_features`, com `VIBRATION_SAMPLES = 512` em
`main.cpp`).

## Temperatura (`lib/thermistor/`)

Duas funções puras:

1. `ntc_resistance_from_adc` — converte a leitura do ADC para a
   resistência do NTC, assumindo um divisor de tensão
   `Vcc → R_FIXED → nó de leitura → NTC → GND`. **Topologia assumida, não
   confirmada contra o esquemático final.**
2. `ntc_resistance_to_celsius` — equação B (Steinhart-Hart simplificada),
   com os valores nominais do NTC 10K (beta 3950).

## Deep sleep e consumo de energia (`src/power/sleep.cpp`)

Corte de energia via GPIO (assumindo topologia low-side com os transistores
BC337: GPIO em nível alto satura o transistor, completando o retorno a GND
do MPU6050 e do divisor de tensão do NTC).

### Estimativa teórica de consumo médio

Ciclo: acordar → ler MPU6050+NTC / processar (3s) → transmitir LoRa
(~150ms) → deep sleep (10min) → repete.

Correntes assumidas (datasheets / valores típicos — a confirmar com
medição real na Fase 3):

| Fonte | Corrente | Origem |
|---|---|---|
| ESP32-S3 ativo (sem WiFi) | ~40 mA | típico, datasheet Espressif |
| MPU6050 em operação | ~3,9 mA | datasheet InvenSense |
| SX1278 TX @ ~17dBm | ~90 mA | datasheet Semtech |
| ESP32-S3 deep sleep | ~10 µA | fornecido no escopo do projeto |
| HT7333 quiescente | ~8 µA | fornecido no escopo do projeto |

Carga por ciclo (`Q = I × t`):

```
Fase ativa (3,0s):   (40 + 3,9 + 0,008) mA × 3,0s        = 131,72 mA·s
Fase TX (0,15s):     (40 + 3,9 + 90 + 0,008) mA × 0,15s  =  20,09 mA·s
Fase sleep (600s):   (0,010 + 0,008) mA × 600s           =  10,80 mA·s
                                                    Total = 162,61 mA·s
                                              = 0,04517 mAh por ciclo (603,15s)
```

Corrente média: `0,04517 mAh ÷ (603,15s / 3600) ≈ 0,2696 mA ≈ 270 µA` —
dentro da meta de <1mA, com margem de ~3,7×. Autonomia estimada com bateria
18650 3000mAh: ~464 dias (~15,5 meses).

## Comunicação LoRa (`src/comms/lora.cpp`)

RadioLib, módulo RA-02/SX1278, 433MHz, potência de TX 17dBm. API conferida
contra o código-fonte real da versão instalada (`Module`, `begin`,
`setOutputPower`, `transmit`) — não só "compilou por acaso".

Pacote (`LoraPacket`, ~13 bytes): status (normal/anômalo), RMS, temperatura,
timestamp.

### Pinos GPIO (ESP32-S3-DevKitC-1, variante Arduino `esp32s3`)

| Uso | Pino | Observação |
|---|---|---|
| I2C (MPU6050) | SDA=8, SCL=9 | *default* da placa — ainda não usado no código (I2C real é TODO) |
| SPI (LoRa) | MOSI=11, MISO=13, SCK=12, SS=10 | *default* da placa |
| LoRa DIO0 | 14 | escolhido para não colidir com I2C |
| LoRa RESET | 21 | escolhido para não colidir com I2C |
| NTC (ADC) | 4 | placeholder |
| Corte de energia (BC337) | 5 | placeholder |

Todos conferidos sem conflito entre si e contra o `pins_arduino.h` real da
variante `esp32s3` — mas ainda não contra um esquemático físico definitivo.

## Modelo de detecção de anomalias — Isolation Forest nativo, sem TFLite Micro

**Decisão:** o modelo é um Isolation Forest (scikit-learn), mas a
inferência embarcada **não** usa TensorFlow Lite Micro — usa uma
implementação C++ própria (`lib/isolation_forest/`) que percorre
diretamente as árvores exportadas do treino.

**Por quê:** TensorFlow Lite é desenhado para redes neurais (grafos de
operações tensoriais); Isolation Forest é um ensemble de árvores de
decisão, cujo score é o comprimento médio de caminho até isolar um ponto —
um cálculo completamente diferente. Não existe um caminho oficial e
confiável de conversão scikit-learn → TFLite Micro para esse tipo de
modelo; a rota possível (`skl2onnx` → `onnx-tf` → `TFLiteConverter`) depende
de ferramentas de conversão de árvores pouco mantidas, com risco real de
falhar no meio do caminho. A alternativa nativa é mais simples, mais leve
em RAM/Flash no ESP32-S3, e elimina essa dependência frágil.

Como consequência, as dependências `TensorFlowLite_ESP32` e (por não ter
sido usada) `arduinoFFT` foram removidas do `platformio.ini`.

### Como funciona a inferência

1. `isolation_path_length_correction(n)` — calcula `c(n)`, o comprimento
   médio de caminho esperado para isolar um ponto numa árvore de busca
   binária com `n` amostras. Mesma fórmula usada internamente pelo
   scikit-learn (`sklearn/ensemble/_iforest.py`), incluindo os casos
   especiais `c(1)=0` e `c(2)=1`.
2. `isolation_tree_path_length` — percorre uma árvore (arrays `feature`,
   `threshold`, `left`, `right`; folha = `feature == -1`) até a folha,
   soma a profundidade percorrida com a correção da folha (para folhas que
   não foram isoladas até um único ponto durante o treino).
3. `isolation_forest_score` — média do comprimento de caminho entre todas
   as árvores do ensemble, normalizada: `score = 2^(-caminho_médio / c(n))`,
   em (0,1]. Próximo de 1 = anômalo.

### Exportação do modelo treinado (`training/kaelix_ml/export_cpp.py`)

Percorre `clf.estimators_` (árvores internas do `IsolationForest` do
scikit-learn) e gera um header C++ com 5 arrays por árvore (`feature`,
`threshold`, `left`, `right`, `leaf_correction`) mais um array de structs
`IsolationTree` apontando para eles. Convenção de folha traduzida de `-2`
(scikit-learn) para `-1` (C++, ver `isolation_forest.h`).

### Validação cruzada Python ↔ C++

O teste `training/tests/test_export_cpp.py` treina um Isolation Forest de
teste, exporta para header C++, **compila de verdade com g++**, roda o
binário e compara o score calculado em C++ contra
`-clf.score_samples(X)` do scikit-learn (o sinal é invertido porque
`score_samples` do scikit-learn retorna o oposto do score `(0,1]` do artigo
original do Isolation Forest). Tolerância: `1e-4`. Isso fecha, de forma
verificável, a exigência de que treino e inferência não divirjam.

Um bug real foi encontrado por esse teste: `export_cpp.py` gerava literais
como `-2f` (inválido em C++; falta o ponto decimal) para valores inteiros
como `-2.0`. Corrigido garantindo que todo float exportado tenha `.` antes
do sufixo `f`.

### Features do modelo

Vetor de entrada, na mesma ordem nos dois lados (`src/ml/model.cpp` e
`training/kaelix_ml/features.py::FEATURE_ORDER`):

```
[rms, kurtosis, crest_factor, dominant_freq_hz]
```

`temperature_c` é lido e passado para `model_infer`, mas **não** entra no
vetor de features hoje — fica disponível para uso futuro (ex.: um segundo
modelo, ou adicionar como 5ª feature depois de experimentos com dados
reais).

### Rotulagem de referência — ISO 10816-3 (`training/kaelix_ml/labeling.py`)

O Isolation Forest é treinado de forma **não supervisionada**, sobre o
subconjunto de dados rotulado como "normal" — prática padrão para esse
tipo de modelo.

A norma define zonas de severidade (A/B = normal, C/D = anômalo) em termos
de **velocidade** de vibração RMS (mm/s) medida na banda de **10 Hz a
1000 Hz** — não aceleração, que é o que o MPU6050 mede. A conversão tem
dois passos:

1. Integrar aceleração para velocidade **no domínio da frequência**
   (`V(f) = A(f)/(j·2π·f)`). Integrar no tempo acumula deriva de offset:
   um bias de 0,02 m/s², dentro da especificação de qualquer MPU6050, leva
   o resultado a +716% de erro.
2. **Recortar a banda de 10–1000 Hz**, como a norma exige, com janela de
   Hann e compensação da potência que a janela remove.

A implementação é a mesma de `figures/scripts/export_source_data.py`
(`vel_freq`), verificada contra valor analítico com erro de 0,0013%, e
coberta por `tests/test_labeling.py`. Essa integração acontece **só no lado
Python** — o firmware não precisa fazer esse cálculo em tempo real, porque
quem decide normal/anômalo em campo é o modelo treinado, não os limiares
ISO diretamente.

**O rótulo ISO não é a verdade de referência.** Quando o dataset codifica a
classe de falha no caminho do arquivo — como o MAFAULDA faz — é esse o
rótulo usado para avaliar. O rótulo ISO é calculado em paralelo e serve
como **diagnóstico**: `train.py` imprime a matriz de concordância entre os
dois. Divergência grande indica que os limiares de zona, a classe de máquina
assumida ou a banda de medição precisam de revisão.

**Consequência da banda.** Com a taxa de 1 kHz do dispositivo, o Nyquist é
500 Hz: o Kaelix cobre metade da banda de 10–1000 Hz que a norma exige.
Conformidade plena com a ISO 10816-3 não é possível com o MPU6050 — ver
item 2 de `docs/questionamentos-tecnicos.md`.

**Os valores de fronteira de zona usados (`ISO_10816_3_ZONE_BOUNDARIES_MM_S`)
são os comumente citados na literatura de engenharia para a ISO
10816-3:2009 — ainda não conferidos contra o texto oficial da norma nem
contra a classe real do motor de bancada.** Confirmar antes de usar para
calibração final.

### Protocolo de treino e calibração (`training/kaelix_ml/train.py`)

Três decisões de método, todas vindas de `docs/questionamentos-tecnicos.md`:

**Domínio alinhado com o firmware.** Os datasets vêm a 50 kHz (MAFAULDA) ou
12/48 kHz (CWRU), em registros de segundos; o dispositivo lê uma janela de
512 amostras a 1 kHz. Extrair features do arquivo inteiro produziria um
modelo inaplicável — `dominant_freq_hz` chegaria a 25 kHz no treino e nunca
passaria de 500 Hz em campo. `dataset.to_device_windows` decima (FIR em
estágios, `zero_phase`) e fatia todo sinal antes de virar feature.

**Split por grupo (item 6).** `GroupKFold` com o arquivo de origem como
grupo — janelas do mesmo ensaio nunca ficam dos dois lados do split. O
relatório traz média ± desvio entre folds; desvio alto é informação sobre
falta de ensaios, não ruído a esconder atrás de um número único.

**Limiar por taxa de falso alarme alvo (item 7).** O limiar não é 0,5 nem
vem do `contamination`: é o quantil `1 - FALSE_ALARM_TARGET` dos scores de
um conjunto de calibração formado por grupos que o modelo não viu no fit.
O default `contamination="auto"` marcaria 42% da operação normal como
anomalia.

**Mesma regra de decisão dos dois lados.** Calibração, avaliação e
exportação usam `device_score()` = `-clf.score_samples(X)`, a convenção
(0,1] idêntica à de `lib/isolation_forest/`. Antes a avaliação usava
`clf.predict()`, que decide pelo `offset_`, então o relatório impresso no
treino não descrevia o comportamento embarcado.

AUC e pAUC (`max_fpr=0.10`, protocolo DCASE2020 Task 2) entram no relatório
com a mesma chamada de `figures/scripts/export_source_data.py`, para que os
números sejam comparáveis com a Fig. 2e — crítica A1 de
`docs/criticas-da-literatura.md`.

### Placeholder atual (`src/ml/isolation_forest_data.h`)

Com `N_TREES = 0`, `model_infer` sempre retorna `Status::Normal` sem
percorrer árvore nenhuma (guarda explícita em `model.cpp`, evita divisão
por zero em `isolation_forest_score`). Este arquivo é **sobrescrito**
automaticamente quando `python -m kaelix_ml.train` roda com sucesso.

## Testes

| Suíte | Local | O que cobre |
|---|---|---|
| `test_signal_processing` | `test/` (PlatformIO/Unity, `native`) | RMS, curtose, fator de crista, frequência dominante — valores analíticos conhecidos |
| `test_thermistor` | `test/` | conversão ADC→resistência→°C — ponto de ancoragem exato + monotonicidade + limites |
| `test_isolation_forest` | `test/` | `c(n)` contra valores de referência, caminhos de árvore construída à mão, score |
| `test_features` | `training/tests/` (pytest) | espelha `test_signal_processing`, garante paridade Python↔C++ |
| `test_labeling` | `training/tests/` | conversão g→m/s², integração na frequência contra valor analítico, máscara de banda 10–1000 Hz, imunidade a bias, limites de zona ISO |
| `test_dataset` | `training/tests/` | recursão da busca, decimação, janelamento, unidade, rótulo por caminho |
| `test_export_cpp` | `training/tests/` | round-trip real: treina → exporta → compila → compara score C++ vs scikit-learn |

Todas as suítes rodam limpas com `-Wall -Wextra -Wpedantic` (C++) e
`-W error` (Python, todo warning tratado como erro).
