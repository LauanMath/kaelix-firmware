# Kaelix — Matriz de rastreabilidade

Documento de verificação. Liga cada requisito ao código que o implementa e ao
teste que o verifica, e — a parte que dá valor à matriz — declara o que **não**
está verificado e por quê.

O alvo não é certificação DO-178C. O alvo é poder afirmar numa defesa, com
evidência, o que o sistema faz e o que ainda não foi demonstrado. Uma matriz que
só lista o que passou é propaganda; a coluna útil é a das lacunas.

## Como estes requisitos foram derivados

Nenhum documento do projeto declarava requisitos numerados de forma completa. Os
59 abaixo foram extraídos de quatro fontes, nesta ordem de precedência:

1. **O comportamento implementado** em `src/` e `lib/` — cada guarda, cada
   `Status` retornado, cada `static_assert` e cada cota de laço é um requisito
   que alguém decidiu impor. Requisito derivado do código tem a vantagem de já
   nascer verificável.
2. **As decisões registradas** em `README.md` (orçamento de energia, formato do
   pacote, banda de análise, escolha do Isolation Forest nativo).
3. **`docs/ARQUITETURA-SOFTWARE.md`** — regra de dependência entre camadas,
   política de memória, política de erro, estado seguro, paridade numérica, e a
   semente de matriz do §9, que este documento substitui e amplia.
4. **`docs/ANALISE-DE-FALHAS.md`** — os `REQ-SEG-01..62` de mitigação de FMEA e
   os invariantes `INV-1..5`. Eles não são renumerados aqui: aparecem na coluna
   de origem, para que a FMEA e esta matriz continuem sendo o mesmo grafo.

Convenção de identificador: `REQ-<ÁREA>-<NN>`. As áreas são `VIB` (vibração),
`TMP` (temperatura), `ML` (modelo), `COM` (comunicação), `PWR` (energia e sono),
`WDT` (watchdog e prazos), `SAF` (estado seguro e integridade do veredito) e
`SYS` (arquitetura, memória e build).

## Legenda de estado

| Estado | Significado |
|---|---|
| **V** | Verificado por teste automatizado que **foi executado nesta revisão** e passou |
| **VC** | Verificado pelo compilador ou por regra estrutural executada nesta revisão (compilação de `lib/` no host, `grep` de regra de camada) |
| **P** | Parcial — parte do enunciado é verificada, parte não; a ressalva está na célula |
| **NV — sem teste** | Implementado e **verificável hoje no host**, mas ninguém escreveu o teste. É a lacuna barata |
| **NV — hardware** | Só demonstrável com o dispositivo físico (MPU6050, SX1278, INA219, bancada). Fase 3 |
| **NV — não testável** | Não verificável por teste automatizado; a evidência é inspeção, análise ou ensaio de bancada |
| **NI** | Não implementado — o caminho ainda não existe, e falha alto (`NotImplemented`) |
| **X** | **Em falha comprovada** — a verificação existe e reprova, ou o código está demonstradamente quebrado |

> **Ressalva sobre a execução.** O PlatformIO não está instalado neste ambiente.
> A suíte `native` foi compilada e executada com `g++` diretamente sobre
> `lib/` + `test/`, com um substituto mínimo de Unity; resultado: **76 casos,
> 0 falhas** (70 no perfil de desenvolvimento, 76 com `-D KAELIX_PRODUCTION`).
> Ver §6. O `pytest` de `training/` **não** pôde ser executado (sem `numpy`/
> `scikit-learn` no ambiente); onde ele é a verificação, o estado foi
> determinado por compilação direta do código que o teste embarca — ver
> REQ-ML-01.

---

## 1. Vibração — `REQ-VIB`

| ID | Requisito | Implementação | Verificação | Estado |
|---|---|---|---|---|
| **REQ-VIB-01** | Dado um bloco de `n` amostras (`n` potência de 2, `4 ≤ n ≤ 512`), o firmware calcula RMS, curtose de excesso (Fisher, normal = 0) e fator de crista, com erro ≤ 1e-3 contra o valor analítico de sinais de referência | `lib/signal_processing/signal_processing.cpp`: `compute_rms`, `compute_kurtosis`, `compute_crest_factor` | `test_signal_processing`: `test_rms_of_sine_wave`, `test_rms_of_constant_signal`, `test_crest_factor_of_sine_wave`, `test_kurtosis_of_two_point_distribution`, `test_kurtosis_of_uniform_like_signal` | **V** |
| **REQ-VIB-02** | A frequência dominante é extraída do espectro de **velocidade** (`\|V(f)\| = \|A(f)\|/2πf`), restrita a 10–1000 Hz; um pico de aceleração fora da banda ou acima dela não pode vencer | `signal_processing.cpp:195` `dominant_frequency_scratch`; `DOMINANT_BAND_LO_HZ/HI_HZ` | `test_dominant_frequency_of_sine_wave`, `test_dominant_frequency_uses_velocity_not_acceleration`, `test_dominant_frequency_ignores_below_band`, `test_dominant_frequency_ignores_above_band`; espelhado em `training/tests/test_features.py` | **V** |
| **REQ-VIB-03** | `n` não potência de 2, `n > FFT_MAX_N`, ponteiro nulo ou `sample_rate_hz` não finita são **recusados com `Status`**, nunca produzem espectro | `fft_radix2` (4 `KAELIX_REQUIRE`), `dominant_frequency_scratch` (9 guardas), `dominant_frequency` (`n <= FFT_MAX_N`) | — | **NV — sem teste** |
| **REQ-VIB-04** | `n` amostras bit a bit idênticas ⇒ `SensorStuck`; nunca features. Um buffer de zeros não pode virar `RMS = 0, curtose = 0` e sair como leitura | `src/sensors/vibration.cpp:119` `vibration_features_from_samples` (`memcmp` contra `samples[0]`) | — | **NV — sem teste** |
| **REQ-VIB-05** | Amostra não finita ⇒ `NotFinite` antes de qualquer matemática; feature calculada não finita ⇒ `NotFinite` antes de publicar. Em erro, `*out` não é escrito | `vibration.cpp:116` e `:140` | — | **NV — sem teste** |
| **REQ-VIB-06** | A rajada de 512 amostras é adquirida a 1 kHz, a taxa **efetiva** é medida e devolvida, e desvio > 2% (`VIBRATION_SAMPLE_RATE_TOLERANCE`) ⇒ `SampleRateMissed` | `vibration.cpp:65` `vibration_acquire` — devolve `NotImplemented`; nada é escrito em `dst` | — | **NI** (bloqueado por hardware) |
| **REQ-VIB-07** | `vibration_init` confirma o sensor lendo `WHO_AM_I` (0x75) e configura o DLPF **abaixo** de fs/2, sem o qual todo conteúdo acima de 500 Hz dobra para dentro da banda | `vibration.cpp:48` `vibration_init` — devolve `NotImplemented` | — | **NI** (bloqueado por hardware) |
| **REQ-VIB-08** | Falha em qualquer etapa da leitura ⇒ `*out` não escrito e nenhuma feature produzida a partir de dado fabricado | `vibration.cpp:154` `vibration_read_features` (`KAELIX_CHECK` sobre `vibration_acquire`) | — | **NV — sem teste** |

Origem: `REQ-SEG-01/02/04/05/09/10/43/44/60/61`, `INV-3`, `INV-4`, seção §9 da
arquitetura (`REQ-VIB-001/002/003`).

---

## 2. Temperatura — `REQ-TMP`

| ID | Requisito | Implementação | Verificação | Estado |
|---|---|---|---|---|
| **REQ-TMP-01** | Converter a leitura do divisor (bruta ou em mV) em resistência do NTC e em °C pela equação B (NTC 10k, beta 3950, nominal a 25 °C), com monotonicidade decrescente R↑ ⇒ T↓ | `lib/thermistor/thermistor.cpp`: `ntc_resistance_from_adc`, `ntc_resistance_from_millivolts`, `ntc_resistance_to_celsius` | `test_thermistor`: `test_celsius_at_nominal_resistance`, `test_celsius_decreases_as_resistance_increases`, `test_celsius_sanity_bounds`, `test_resistance_from_adc_midscale`, `test_resistance_from_adc_quarter_scale`, `test_resistance_from_millivolts_matches_divider`, `test_from_adc_extremos_da_faixa_util_convertem_e_reportam_ok` | **V** |
| **REQ-TMP-02** | Razão do divisor ≤ 0,02 ⇒ `ThermistorShorted`; ≥ 0,99 ⇒ `ThermistorOpen`. Nos dois casos o retorno é **NaN**, nunca uma temperatura de aparência plausível (o clamp anterior produzia +349,7 °C e −77,2 °C com CRC válido) | `thermistor.cpp`, limiares `NTC_RATIO_SHORTED_MAX`/`NTC_RATIO_OPEN_MIN` | `test_from_adc_curto_reporta_thermistor_shorted`, `test_from_adc_aberto_reporta_thermistor_open`, `test_from_adc_acima_do_fundo_de_escala_reporta_thermistor_open`, `test_from_adc_falha_de_campo_nao_produz_temperatura_plausivel`, `test_from_millivolts_extremos_sao_defeito_de_campo`, `test_to_celsius_entrada_nao_finita_propaga_sem_abortar` | **V** |
| **REQ-TMP-03** | Temperatura convertida fora de [−40, +125] °C ⇒ `TemperatureImplausible` e `*out_c` **não** escrito. A forma negada da comparação recusa NaN | `src/sensors/temperature.cpp:89` `temperature_read_celsius` | — | **NV — sem teste** |
| **REQ-TMP-04** | O ADC é configurado com atenuação 11 dB e uma leitura de conferência acima de `ADC_MAX_PLAUSIBLE_MV` (3630 mV) ⇒ `AdcNotConfigured` / `AdcOutOfRange` | `temperature.cpp:37` `temperature_init`, `:68` | — | **NV — hardware** |
| **REQ-TMP-05** | Parâmetros de datasheet inválidos (`adc_max == 0`, `r_fixed ≤ 0`, `beta == 0`, `t_nominal ≤ −273,15`, não finitos) são **violação de contrato**: abortam no build de desenvolvimento e devolvem `Status` em produção | `KAELIX_REQUIRE_VALUE` em `thermistor.cpp` | 8 casos: `test_from_adc_adc_max_zero_viola_contrato`, `test_from_adc_r_fixed_nao_positivo_viola_contrato`, `test_from_millivolts_vcc_zero_viola_contrato`, `test_to_celsius_resistencia_nao_positiva_viola_contrato`, `test_to_celsius_r_nominal_nao_positivo_viola_contrato`, `test_to_celsius_beta_zero_viola_contrato`, `test_to_celsius_t_nominal_no_zero_absoluto_viola_contrato`, `test_parametros_nao_finitos_violam_contrato` | **V** |
| **REQ-TMP-06** | A topologia assumida (`Vcc → R_FIXED → nó → NTC → GND`), `R_FIXED = 10 k`, o pino e o tempo de estabilização de 100 ms correspondem ao hardware real | `temperature.cpp:10-22` (constantes), `src/main.cpp:74` `PERIPHERAL_SETTLE_MS` | — | **NV — hardware** |

Origem: `REQ-SEG-12/13/14/15`, `INV-3`.

**Premissa aberta (REQ-TMP-06).** Os 100 ms de estabilização são estimativa, não
medição. Se a constante de tempo do nó do divisor for maior, toda leitura pega o
transitório e a temperatura fica enviesada **de forma sistemática e consistente**
— o tipo de erro que nenhuma faixa de plausibilidade pega, porque o valor
continua plausível (FM-08).

---

## 3. Modelo de anomalia — `REQ-ML`

| ID | Requisito | Implementação | Verificação | Estado |
|---|---|---|---|---|
| **REQ-ML-01** | O score do Isolation Forest embarcado equivale ao de `-clf.score_samples(X)` do scikit-learn com tolerância 1e-4, sobre o mesmo modelo exportado | `lib/isolation_forest/isolation_forest.cpp`: `isolation_path_length_correction`, `isolation_tree_path_length`, `isolation_forest_score` | `training/tests/test_export_cpp.py::test_cpp_score_matches_sklearn_score` — passa. O `main.cpp` embutido no teste foi atualizado para a assinatura de 6 argumentos que devolve `Status`; a suíte compila com `g++` e compara contra o scikit-learn | **V** |
| **REQ-ML-02** | A travessia de árvore tem cota de profundidade constante conhecida antes do laço (`ISOLATION_TREE_MAX_DEPTH = 32`, ou a `max_depth` declarada quando plausível); ao estourá-la devolve `ModelDepthExceeded` em vez de girar para sempre | `isolation_forest.cpp:55` `traversal_depth_limit`, `:81` laço `for` com cota | `test_tree_path_length_self_referencing_child_returns_depth_exceeded`, `test_tree_path_length_corrupt_max_depth_still_terminates`, `test_forest_score_cyclic_tree_propagates_depth_exceeded` | **V** |
| **REQ-ML-03** | Nenhum índice vindo do dado indexa fora dos arrays: nó fora de `[0, n_nodes)` ⇒ `ModelMalformed`; índice de feature fora de `[0, n_features)` ⇒ `IndexOutOfRange`; marcador de folha corrompido ⇒ `ModelMalformed` (nunca caminho curto, que seria score ALTO) | `isolation_tree_path_length:88-110` | `test_tree_path_length_child_beyond_n_nodes_returns_malformed`, `_negative_child_`, `_root_out_of_range_`, `_feature_index_beyond_vector_returns_index_out_of_range`, `_corrupt_leaf_marker_`, `_null_array_`, `_zero_nodes_` | **V** |
| **REQ-ML-04** | O modelo é validado estruturalmente **uma vez por boot** (não a cada inferência): ponteiros presentes, raiz e filhos em faixa, aciclicidade por ordem crescente, limiares e correções finitos | `isolation_forest_validate` (L1) chamado por `src/ml/model.cpp:29` `model_init` | L1: 11 casos `test_validate_*`. `model_init` em si: — | **P** — a função validadora é verificada; a chamada por `model_init` não |
| **REQ-ML-05** | `n_trees ≤ 0` ⇒ `ModelAbsent`; ponteiros nulos e `subsample_size ≤ 1` ⇒ erro tipado. Nenhum caminho divide por zero nem devolve NaN silencioso | `isolation_forest_score:129-140`, `model.cpp:35` e `:59` | `test_forest_score_zero_trees_returns_model_absent`, `_negative_trees_`, `test_validate_rejects_zero_trees_as_model_absent`, `test_forest_score_null_trees_returns_null_pointer`, `test_forest_score_subsample_one_returns_invalid_argument` | **V** |
| **REQ-ML-06** | Score não finito ⇒ `ScoreNotFinite`, e `*out_score` **não** é escrito. Comparação `score > limiar` com NaN é falsa e devolveria `Normal` | `isolation_forest.cpp:165` | — (nenhum teste da suíte exercita o ramo `ScoreNotFinite`) | **NV — sem teste** |
| **REQ-ML-07** | `model_infer` escreve `MachineState::Unknown` **antes** de qualquer coisa poder falhar, e recusa feature não finita antes de inferir. Nenhum caminho de erro produz `Normal` | `src/ml/model.cpp:53`, `:69-73`, `KAELIX_ENSURE` em `:82` | — | **NV — sem teste** |
| **REQ-ML-08** | A quantidade **e a ordem** das features do firmware coincidem com as do treino (`[rms, kurtosis, crest_factor, dominant_freq_hz]`) | `model.cpp:26` `static_assert(N_FEATURES == 4)`; `training/kaelix_ml/features.py::FEATURE_ORDER` | Quantidade: pelo `static_assert`. Ordem: nada verifica — o `FEATURE_ORDER_HASH` previsto em §7.3 da arquitetura não existe | **P** — quantidade sim, ordem não |
| **REQ-ML-09** | O header gerado por `export_cpp.py` é consumível pelo firmware: cada `IsolationTree` sai com `n_nodes` e `max_depth` preenchidos, sem os quais `isolation_forest_validate` reprova o modelo | `training/kaelix_ml/export_cpp.py:86` emite **6** inicializadores (`feature, threshold, left, right, leaf_correction, 0`); a struct tem **8** membros | Compilado e executado nesta revisão sobre um header no formato do exportador: `n_nodes=0 max_depth=0` ⇒ `isolation_forest_validate` devolve `MODEL_BAD (0x31)` e `isolation_forest_score` também | **X** |
| **REQ-ML-10** | O firmware embarca um modelo treinado com dados reais e emite veredito | `src/ml/isolation_forest_data.h` — `N_TREES = 100`, `N_FEATURES = 4`, `ANOMALY_THRESHOLD = 0,55719777`, treinado no MAFAULDA | O header compila no alvo e `model_init` percorre `isolation_forest_validate`. A guarda `N_TREES <= 0` continua correta para um build sem modelo, mas deixou de ser o caminho exercitado. Veredito em hardware real não observado | **P** |

Origem: `REQ-SEG-34/35/36/37/38/41/42`, `INV-3`, §7 da arquitetura (paridade
numérica), §9 (`REQ-ML-001/002`).

**Consequência combinada de REQ-ML-01 e REQ-ML-09.** O caminho de ML é o mais
testado do repositório em número de casos (38 de 76) e, ao mesmo tempo, o único
com duas falhas comprovadas. As duas apontam para o mesmo lugar: o **contrato
entre `training/` e `lib/`** mudou de um lado só. Hoje, treinar e exportar um
modelo produziria um firmware que responde `ModelMalformed` em todo ciclo — a
degradação correta, mas sem nenhum veredito, para sempre.

---

## 4. Comunicação — `REQ-COM`

| ID | Requisito | Implementação | Verificação | Estado |
|---|---|---|---|---|
| **REQ-COM-01** | O pacote é protegido por CRC-16/CCITT-FALSE (poly 0x1021, init 0xFFFF, sem reflexão), com o vetor de conferência `"123456789" → 0x29B1`, detectando bit invertido e troca de bytes; `n` acima de 255 ou ponteiro nulo com `n > 0` são violação de contrato | `lib/crc16/crc16.cpp` `crc16_ccitt`; `src/comms/lora.cpp:132` e `:139` | `test_crc16_check_vector`, `_empty_is_initial_value`, `_detects_single_bit_flip`, `_detects_byte_swap`, `_valores_de_referencia_do_pacote_de_20_bytes`, `_no_comprimento_maximo_ainda_calcula`, `_ponteiro_nulo_com_n_maior_que_zero_viola_contrato`, `_acima_da_cota_de_comprimento_viola_contrato` | **V** |
| **REQ-COM-02** | O layout do pacote é versionado (`PACKET_VERSION = 2`), tem 21 bytes e o CRC é o **último** membro; mudar o layout sem bump de versão é erro de build | `src/comms/lora.h:22,45,56,64` (dois `static_assert`) | Os `static_assert` foram avaliados por `pio run -e esp32-s3` e passam: o build do alvo roda limpo. Resta a **v1 congelada em dois pontos**: o caso `test_crc16_valores_de_referencia_do_pacote_de_20_bytes` e o `PACKET_SIZE = 20` do gateway em `experiments/gateway/kaelix_gateway/packet.py`, que recusaria todo pacote do firmware atual | **P** |
| **REQ-COM-03** | `make_packet` preenche versão, `device_id` (eFuse MAC), `boot_count` e CRC; em erro `*out` não é escrito | `lora.cpp:117` `make_packet`, `:111` `device_id` | — | **NV — sem teste** |
| **REQ-COM-04** | Campo não medido vai como **NaN**, nunca 0 — 0 é leitura plausível de RMS e de temperatura | `src/main.cpp:94` `MEASUREMENT_INVALID`, `:301-302`; `lora.cpp:128-131` | — | **NV — sem teste** |
| **REQ-COM-05** | Os códigos do RadioLib são traduzidos em `Status` distintos: `CHIP_NOT_FOUND → RadioAbsent`, `SPI_*_FAILED → RadioBusSilent`, `INVALID_FREQUENCY/POWER/BW/SF/CR → RadioConfigRejected`, `TX_TIMEOUT → RadioTxTimeout`, `PACKET_TOO_LONG → PayloadTooLong` | `lora.cpp:68` `from_radiolib` | — | **NV — hardware** (exigiria duplê de RadioLib) |
| **REQ-COM-06** | A transmissão tem cota fixa de 2 tentativas; não há laço "até funcionar" — cada tentativa custa o pico de ~90 mA | `main.cpp:88` `TX_MAX_ATTEMPTS`, `:375` | — | **NV — sem teste** |
| **REQ-COM-07** | Sync word, spreading factor, largura de banda, coding rate, preâmbulo e potência são fixados explicitamente no código, nunca herdados do padrão da biblioteca | `lora_init` fixa apenas frequência (433 MHz) e potência (17 dBm) | — | **NI** (`REQ-SEG-23`) |
| **REQ-COM-08** | Alcance útil e taxa de perda de pacote em planta | — | — | **NV — hardware** |

Origem: `REQ-SEG-16/17/22/23/24/25`, §9 da arquitetura (`REQ-COM-001/002`).

---

## 5. Energia e sono — `REQ-PWR`

| ID | Requisito | Implementação | Verificação | Estado |
|---|---|---|---|---|
| **REQ-PWR-01** | O SX1278 entra em `SLEEP` antes de todo deep sleep, com o retorno **verificado**, até 3 tentativas e pulso de reset por GPIO entre elas (`INV-1`). Sem isso são 910 mA·s por ciclo, 5,5× o orçamento inteiro | `lora.cpp:175` `lora_sleep` (`LORA_SLEEP_MAX_ATTEMPTS = 3`, `lora_hardware_reset`); `main.cpp:207` — primeiro passo do estado seguro, retorno acumulado | — | **NV — hardware** |
| **REQ-PWR-02** | A corrente média do circuito fica abaixo de **1 mA** (projeto: ~309 µA, incluindo ~68,5 µA de autodescarga da LiPo) | O ciclo inteiro; orçamento derivado em `src/power/sleep.cpp:20-61` | Cálculo documentado a partir de valores de datasheet. Medição com INA219 é `REQ-SEG-52` e não foi feita | **NV — hardware** |
| **REQ-PWR-03** | Os periféricos ficam cortados durante todo o sono: `gpio_hold_en()` + `gpio_deep_sleep_hold_en()` antes de dormir, `gpio_hold_dis()` no boot seguinte, com o retorno do hold conferido (`PeripheralPowerFault`) | `src/power/sleep.cpp:65` `peripherals_power`, `:98` em `sleep_prepare` | — | **NV — hardware** (critério de aceitação: < 30 µA em sono, `REQ-SEG-52`) |
| **REQ-PWR-04** | `minutes` fora de [1, 120] é **saturado** e relatado como `InvalidArgument` — nunca recusado, porque recusar deixaria o dispositivo sem despertador armado; o retorno de `esp_sleep_enable_timer_wakeup` é conferido | `sleep.cpp:82` `sleep_prepare` | — | **NV — sem teste** |
| **REQ-PWR-05** | `deep_sleep_now()` não retorna por caminho nenhum: `esp_deep_sleep_start()`, depois `esp_restart()`, depois laço infinito | `sleep.cpp:116` | Inspeção | **NV — não testável** |
| **REQ-PWR-06** | Autonomia ≥ 8 meses com LiPo de 2000 mAh (projeto: ~269 dias = 8,8 meses, com o período de 12 min) | Consequência de REQ-PWR-01..03 e do período de sono (`main.cpp:83`) | Atendido **por cálculo**, com ~26 dias de margem. A 10 min o projeto dava 236 dias e o requisito não era atendido; o período foi elevado para 12 min por essa razão | **NV — hardware** |

Origem: `REQ-SEG-19/20/21/50/51/52/54/55`, `INV-1`, `INV-2`, §9 da arquitetura
(`REQ-PWR-001`).

**Por que REQ-PWR-01 é o requisito mais caro da tabela.** É o único cuja
violação não tem sintoma observável: o dispositivo continua medindo,
transmitindo e reportando `Ok`. A única evidência seria a bateria durar 45 dias
em vez de 241 — descoberta seis meses depois, em campo. O código já está do lado
certo (retorno `[[nodiscard]]`, acumulado, retransmitido no ciclo seguinte via
`last_status`); o que falta é a medição.

---

## 6. Watchdog e prazos — `REQ-WDT`

| ID | Requisito | Implementação | Verificação | Estado |
|---|---|---|---|---|
| **REQ-WDT-01** | Os dois watchdogs são armados na **primeira** instrução do ciclo, antes de energizar qualquer periférico: RTC WDT a 20 s e Task WDT a 6 s com pânico | `src/power/watchdog.cpp:124` `watchdog_arm_active_phase`; `main.cpp:263` | — | **NV — hardware** |
| **REQ-WDT-02** | O dispositivo nunca fica acordado por mais de 20 s consecutivos. O WDT-1 **não é alimentado** durante a fase ativa, e nenhuma função de `src/`/`lib/` alimenta watchdog | `watchdog_feed` só toca o Task WDT; alimentação só em `main.cpp`, entre fases | — | **NV — hardware** |
| **REQ-WDT-03** | A cota de software da fase ativa (5 s) dispara **antes** da janela do Task WDT (6 s), para que o estado seguro seja alcançado de forma ordenada, com o rádio adormecido | `main.cpp:82-83` `CYCLE_DEADLINE_MS` + `static_assert` contra `WATCHDOG_TASK_TIMEOUT_S` | `static_assert` escrito; avaliado só por um build do alvo, que não roda desde as últimas mudanças | **P** |
| **REQ-WDT-04** | Prazo estourado ⇒ `CycleDeadlineExceeded`, **sem transmitir**, mas com `lora_init()` ainda executado, porque `lora_sleep()` precisa do SPI configurado pelo `begin()` | `main.cpp:347-366` | — | **NV — sem teste** |
| **REQ-WDT-05** | Antes do sono, o RTC WDT é **reprogramado** para 1,2× o período (e não desligado): com a janela de 20 s armada, ele reiniciaria o chip 20 s depois de dormir e o período de 12 min nunca aconteceria | `watchdog.cpp:139` `watchdog_arm_for_sleep`; `sleep.cpp:104` | — | **NV — hardware** |
| **REQ-WDT-06** | Nenhum watchdog é alimentado dentro de laço de espera de hardware; cada espera tem timeout e status próprios | Convenção sustentada por inspeção; `watchdog.h:26-30` a declara | Verificável por `grep`, sem script versionado (`tools/check_layers.sh` não existe) | **NV — não testável** |

Origem: `REQ-SEG-32/48/49`, `INV-4`, §6 da análise de falhas, §9 da arquitetura
(`REQ-PWR-002`).

**REQ-WDT-05 é o requisito em que um watchdog mal desenhado quebra o produto.**
Se ele estiver errado, o dispositivo não trava — ele reinicia a cada 20 s, para
sempre, a ~40 mA, e esvazia a bateria em ~50 h. É uma verificação de bancada de
minutos e hoje não existe nenhuma.

**O WDT-1 mudou de via de acesso, não de política.** A implementação anterior
incluía `<soc/rtc_wdt.h>` sob uma guarda `__has_include`. Essa guarda testava a
existência do cabeçalho, não sua usabilidade: no ESP32-S3 o arquivo está presente
e referencia `RTC_WDT_STG_SEL_*`, símbolos definidos apenas na árvore do ESP32
original — de modo que o build do alvo **falhava**, em vez de degradar para
`NotImplemented` como a guarda pretendia. A implementação atual usa
`hal/wdt_hal.h` (RWDT), portátil entre ESP32/S2/S3/C3 e a mesma via que o ESP-IDF
usa no bootloader, com a janela convertida em ticks a partir de
`rtc_clk_slow_freq_get_hz()` — ler a frequência importa porque o `RTC_SLOW_CLK`
é RC de ~136 kHz ou cristal de 32768 Hz conforme a placa, e uma constante fixa
faria a janela de 20 s virar 4,8 s ou 83 s sem sintoma algum.

O que o build do alvo passou a provar: que a API existe, é usada com a assinatura
certa e **resolve em link**. O que ele continua sem provar: que o contador do
RWDT sobrevive ao deep sleep — premissa de que dependem o REQ-WDT-05 e o
despertador de último recurso do `REQ-SEG-49`. Isso é medição de bancada, e
continua não feita.

---

## 7. Estado seguro e integridade do veredito — `REQ-SAF`

| ID | Requisito | Implementação | Verificação | Estado |
|---|---|---|---|---|
| **REQ-SAF-01** | **O dispositivo nunca transmite um `Normal` fabricado.** A inferência só roda com features válidas; qualquer falha de sensor, de modelo ou de aquisição deixa `state = Unknown` e o pacote sai com a causa | `main.cpp:332` (`is_ok(vibration) && is_ok(model)`), `:300` (`Unknown` como inicial), `model.cpp:53`; `lora.h:35` (contrato de validade) | — | **NV — sem teste** |
| **REQ-SAF-02** | O byte `diag` do pacote carrega o **primeiro** erro do ciclo (`status_first_error`: erro derivado não sobrescreve causa raiz), ou o do ciclo anterior se este correu limpo | `lib/kaelix_status/kaelix_status.h:154` `status_first_error`; `main.cpp:369` | — | **NV — sem teste** (`status_first_error` é `constexpr` puro — testável por `static_assert`) |
| **REQ-SAF-03** | Boot vindo de reset anormal (watchdog, pânico, brownout) **pula a fase de medição** — repetir o ciclo que acabou de travar é o laço de reset — mas transmite mesmo assim (`INV-5`, sempre audível) | `main.cpp:298` `recovery`, `:304` | — | **NV — sem teste** |
| **REQ-SAF-04** | Quatro resets anormais consecutivos ⇒ período estendido de 60 min (quarentena), para que o dispositivo sobreviva semanas anunciando o próprio defeito em vez de horas tentando | `main.cpp:70-71`, `:285` | — | **NV — sem teste** |
| **REQ-SAF-05** | O estado que atravessa o sono vive em `RTC_NOINIT_ATTR` (sobrevive a reset anormal, ao contrário de `RTC_DATA_ATTR`), protegido por palavra mágica + CRC-16; bloco que não confere ⇒ `RtcStateCorrupt`, **exceto** no power-on, onde o conteúdo arbitrário é esperado | `main.cpp:110-151` `RetainedState`, `retained_load`, `retained_seal`; `static_assert` no offset do CRC | — | **NV — sem teste** (a lógica é pura o bastante para rodar no host) |
| **REQ-SAF-06** | A causa do reset é lida no início de todo boot e traduzida (`WatchdogResetDetected`, `BrownoutResetDetected`, `Internal` para pânico) | `watchdog.cpp:124` `reset_cause_status`, `:146` `reset_was_power_on`; `main.cpp:258` | — | **NV — hardware** |
| **REQ-SAF-07** | O estado seguro é alcançado sempre na mesma ordem: rádio dorme → periféricos cortados → hold + WDT de sono + timer armado → deep sleep; e o status final é gravado no estado retido **antes** de dormir, para chegar ao gateway no ciclo seguinte | `main.cpp:199` `enter_safe_state` | — | **NV — sem teste** |

Origem: `REQ-SEG-03/26/27/28/33/57/58/59`, `INV-3`, `INV-4`, `INV-5`, §5 e §6 da
análise de falhas.

**Esta é a área mais crítica e a menos verificada da matriz: 7 requisitos, 0
testes.** `REQ-SAF-01` é o requisito que dá razão ao projeto inteiro — a
diferença entre um dispositivo que mede e um que mente — e sua verificação hoje
é a leitura de um `if` em `main.cpp`. Nenhum dos sete depende de hardware para
ser testado: todos são decisões de estado que uma máquina de estados extraída de
`setup()` exercitaria no host.

---

## 8. Arquitetura, memória e build — `REQ-SYS`

| ID | Requisito | Implementação | Verificação | Estado |
|---|---|---|---|---|
| **REQ-SYS-01** | Nenhuma alocação dinâmica em `lib/` nem em `src/` — nem `new`, `malloc`, `std::vector`, `std::string` ou `std::function`, nem em inicialização estática | Buffers de escopo de arquivo (`s_samples`, `s_fft_re/im`); `lora.cpp:58` `Module` estático em vez de `new Module` | `grep -rn '\bnew \|malloc(\|std::vector\|std::string\|std::function' lib/ src/` executado nesta revisão: só ocorrências em comentário | **VC** |
| **REQ-SYS-02** | L0 e L1 (`lib/`) não incluem `<Arduino.h>`, `esp_*.h`, `driver/*.h` nem `<RadioLib>`, e compilam num toolchain de host | `lib/kaelix_status`, `lib/signal_processing`, `lib/thermistor`, `lib/isolation_forest`, `lib/crc16` | `grep` de barreira sem ocorrência (só um comentário), e as quatro suítes compiladas com `g++` sobre `lib/` nesta revisão | **VC** |
| **REQ-SYS-03** | Módulos irmãos de L2 não se incluem: `#include "../outra_area/algo.h"` é proibido | — | `grep -rn '#include "\.\./' src/*/` acusa **`src/ml/model.h:4` incluindo `../sensors/vibration.h`** (o destino de `VibrationFeatures` é L1). Os demais `../machine_state.h` apontam para a raiz de `src/`, não para área irmã, e são o padrão adotado de propósito | **X** (violação registrada no próprio header) |
| **REQ-SYS-04** | Nenhuma recursão; todo laço tem cota superior provável, e laço cujo limite venha de barramento, modelo ou pacote tem cota **constante** e status para o estouro | `fft_radix2` (cotas derivadas de `n`), `isolation_tree_path_length` (cota 32), `crc16_ccitt` (cota 255), `lora_sleep` (3), TX (2) | Inspeção; nenhuma análise estática configurada (`.clang-tidy` não existe no repositório) | **NV — não testável** |
| **REQ-SYS-05** | O build de produção define `-D KAELIX_PRODUCTION`, para que uma violação de contrato em campo **degrade** em vez de abortar um dispositivo parafusado numa máquina | `kaelix_status.h:265` implementa a assimetria | `platformio.ini` **não** define a macro em nenhum ambiente. O firmware do alvo é hoje compilado no perfil que **aborta** | **NI** |
| **REQ-SYS-06** | O firmware compila para `esp32-s3` sem aviso, e é isso que avalia os `static_assert` de `src/` e as chamadas de API do ESP-IDF/RadioLib | `platformio.ini [env:esp32-s3]` | `pio run -e esp32-s3` não roda desde as últimas mudanças (e PlatformIO não está instalado neste ambiente) | **NV — sem teste** |
| **REQ-SYS-07** | A suíte de host passa integralmente | `test/test_*`, `platformio.ini [env:native]` | 76 casos definidos, **0 falhas** na execução desta revisão. Ressalvas: (a) rodada com substituto de Unity, fora do PlatformIO; (b) **6 casos** de `test_isolation_forest` estão sob `#if !KAELIX_ASSERT_ABORT` e só executam com `-D KAELIX_PRODUCTION`, que nenhum ambiente do `platformio.ini` define — são testes que hoje **nunca rodam**; (c) `test/README.md` e o `README.md` ainda anunciam 26 testes | **P** |
| **REQ-SYS-08** | O consumo de RAM estática fica dentro do orçamento declarado (~6,2 KB de 512 KB) e é conferido no mapa de link | `s_samples` 2 KB + `s_fft_re/im` 4 KB em `vibration.cpp`; mais 4 KB em `signal_processing.cpp` hoje sem chamador | Nenhum mapa de link inspecionado | **NV — hardware** |

Origem: §1, §3, §4 e §8 da arquitetura; `REQ-SEG-45/46/47`; `DEV-001` (resolvido:
o `new Module` foi eliminado, o desvio deixou de existir), `DEV-002`, `DEV-003`.

---

## 9. O que não está verificado, e por quê

Esta é a seção que a matriz existe para produzir. 33 dos 59 requisitos não têm
verificação, em três classes com custos muito diferentes.

### 9.1 Sem teste escrito — 19 requisitos

Implementados, **verificáveis hoje no host, sem nenhum hardware**, e sem teste.
É a lacuna barata, e é onde está a maior parte do risco evitável.

`REQ-VIB-03`, `REQ-VIB-04`, `REQ-VIB-05`, `REQ-VIB-08`, `REQ-TMP-03`,
`REQ-ML-06`, `REQ-ML-07`, `REQ-COM-03`, `REQ-COM-04`, `REQ-COM-06`,
`REQ-PWR-04`, `REQ-WDT-04`, `REQ-SAF-01`, `REQ-SAF-02`, `REQ-SAF-03`,
`REQ-SAF-04`, `REQ-SAF-05`, `REQ-SAF-07`, `REQ-SYS-06`.

A causa é estrutural e está registrada em §2 da arquitetura: **`pio test -e
native` compila `lib/` e `test/`, não `src/`.** Enquanto a suíte não alcançar
`src/`, nenhum desses requisitos pode ter teste, por mais barato que fosse.
Quatro deles (`REQ-VIB-04`, `REQ-VIB-05`, `REQ-TMP-03`, `REQ-SAF-05`) já estão
em funções que não tocam hardware — `vibration_features_from_samples`,
`temperature_read_celsius` na parte de plausibilidade, `retained_load` — e
precisariam apenas ser alcançáveis pelo ambiente `native`.

`REQ-SAF-02` é o caso extremo: `status_first_error` é `constexpr` puro em `lib/`,
já compila no host, e mesmo assim não tem um `static_assert` de teste.

### 9.2 Bloqueado por hardware — 13 requisitos

Não é possível verificar sem o dispositivo físico, e nenhum duplê honesto
substitui a medição.

| Requisito | O que a Fase 3 precisa medir | Instrumento |
|---|---|---|
| `REQ-TMP-04`, `REQ-TMP-06` | Topologia do divisor, `R_FIXED`, pino de ADC e tempo real de estabilização do nó | Osciloscópio, esquemático final |
| `REQ-COM-05` | Mapeamento dos códigos do RadioLib com chip ausente, SPI mudo e frequência recusada | Placa com e sem o RA-02 |
| `REQ-COM-08` | Alcance útil e taxa de perda | Gateway em planta |
| `REQ-PWR-01`, `REQ-PWR-02`, `REQ-PWR-03`, `REQ-PWR-06` | Corrente em sono (critério: < 30 µA), corrente média do ciclo, autonomia | INA219 / multímetro |
| `REQ-WDT-01`, `REQ-WDT-02`, `REQ-WDT-05` | O watchdog dispara na janela declarada, e o RTC WDT reprogramado não interrompe o sono de 12 min | Bancada, log de boots |
| `REQ-SAF-06` | `esp_reset_reason()` classifica corretamente watchdog, pânico e brownout | Fonte programável |
| `REQ-SYS-08` | RAM estática efetiva | Mapa de link do build |

Dois desses valores de datasheet dominam o orçamento de energia e nunca foram
medidos: standby do SX1278 (~1,5 mA) e sleep (~0,2 µA). O orçamento inteiro de
309 µA repousa sobre eles.

### 9.3 Não verificável por teste automatizado — 3 requisitos

`REQ-PWR-05` (uma função `[[noreturn]]` que de fato não retorna), `REQ-WDT-06`
(regra negativa sobre onde o watchdog é alimentado) e `REQ-SYS-04` (ausência de
recursão, cota de laço). A evidência apropriada é inspeção e análise estática —
e vale registrar que **nenhuma análise estática está configurada**: o
`.clang-tidy` e o `tools/check_layers.sh` previstos em §1 da arquitetura não
existem. As regras de camada são hoje verificadas por `grep` ad hoc, como nesta
revisão, e não por nada versionado.

### 9.4 Não implementado — 4 requisitos

`REQ-VIB-06` e `REQ-VIB-07` (leitura I2C real do MPU6050 — `vibration_acquire` e
`vibration_init` devolvem `NotImplemented`, e nada é escrito no buffer),
`REQ-COM-07` (parâmetros de rádio explícitos) e `REQ-SYS-05`
(`-D KAELIX_PRODUCTION` ausente do `platformio.ini`). `REQ-ML-10` saiu desta
lista: o modelo treinado está embarcado (`N_TREES = 100`).

Os dois primeiros são a consequência mais visível da matriz: **o dispositivo
hoje não mede vibração.** O que o firmware faz de correto é falhar alto — nenhum
caminho produz features a partir de dado fabricado, e o pacote sai com
`state = Unknown` e `diag = NotImplemented (0xFE)`. Isso é o comportamento
desejado para a ausência, e é o oposto da versão anterior, que devolvia features
de um buffer de zeros. Mas é ausência, não medição, e a matriz precisa dizê-lo.

### 9.5 Em falha comprovada — 1 requisito

| Requisito | Falha | Evidência |
|---|---|---|
| `REQ-SYS-03` | Includes relativos atravessam diretórios: `src/ml/model.h:3-4`, `src/comms/lora.h:6`, `src/comms/lora.cpp:3` | `grep -rn '#include "\.\./' src/*/`; a violação está declarada no próprio header como pendência. São quatro ocorrências, não uma |

**As duas falhas anteriores desta seção foram corrigidas.** `REQ-ML-01`: o
`MAIN_CPP_TEMPLATE` de `test_export_cpp.py` usa a assinatura de 6 argumentos que
devolve `Status`, e a suíte compila e passa. `REQ-ML-09`: `export_cpp.py:103`
emite os 8 inicializadores por árvore, com guarda de estouro de `int16_t`, e o
header versionado traz `n_nodes` e `max_depth` reais (por exemplo `175, 8` na
árvore 0). O invariante de paridade numérica de §7 da arquitetura voltou a ter
verificação ativa — é o teste que compila `lib/isolation_forest` com `g++` e
compara contra `-clf.score_samples(X)` com tolerância de 1e-4.

---

## 10. Resumo quantitativo

| Estado | Quantos | % |
|---|---|---|
| **V** — verificado por teste automatizado executado | 11 | 18,6% |
| **VC** — verificado por compilador / regra estrutural | 2 | 3,4% |
| **P** — parcial | 6 | 10,2% |
| **NV — sem teste escrito** | 19 | 32,2% |
| **NV — bloqueado por hardware** | 13 | 22,0% |
| **NV — não verificável por teste** | 3 | 5,1% |
| **NI** — não implementado | 4 | 6,8% |
| **X** — em falha comprovada | 1 | 1,7% |
| **Total** | **59** | 100% |

### Cobertura real

- **Plenamente verificados: 13 de 59 — 22,0%.** Somando os parciais como meio
  requisito, 16 de 59 — **27,1%**.
- **Descontando o que depende de hardware**, restam 46 requisitos verificáveis
  hoje; 13 estão verificados — **28,3%**. Os 33 restantes são lacuna de teste,
  não limitação física.
- **Por camada:** `lib/` (L0+L1) concentra **76 casos de teste** e responde,
  sozinha ou com o pipeline de treino, por **todos os 13 requisitos plenamente
  verificados**. `src/` (L2+L3) tem **0 casos de teste**;
  **cerca de 40 dos 59 requisitos** têm implementação total ou parcial em
  `src/`, e nenhum deles é verificado por teste automatizado.
- **Área mais frágil:** `REQ-SAF` — 7 requisitos, 0 verificados, e inclui
  `REQ-SAF-01`, o invariante que define o projeto ("nunca transmitir um `Normal`
  fabricado").
- **`REQ-ML` recuperado:** as duas falhas comprovadas foram corrigidas e o
  modelo treinado está embarcado. Resta que nada disso foi observado rodando em
  hardware.

### O que a matriz recomenda, em ordem de custo/benefício

1. **Consertar `export_cpp.py` e `test_export_cpp.py`** (`REQ-ML-09`,
   `REQ-ML-01`). Duas correções pequenas devolvem a verificação do invariante de
   paridade e tornam o modelo treinado consumível. É a única entrada `X` que
   bloqueia funcionalidade.
2. **Fazer o ambiente `native` alcançar as funções puras de `src/`**
   (`test_build_src` ou extração das partes sem hardware). Isso destrava, de uma
   vez, `REQ-VIB-04/05/08`, `REQ-TMP-03`, `REQ-ML-07`, `REQ-SAF-01/05` — sete
   requisitos, entre eles o mais importante do projeto.
3. **Definir `-D KAELIX_PRODUCTION` no ambiente `esp32-s3`** (`REQ-SYS-05`) e no
   perfil de teste que exercita os 6 casos hoje inertes (`REQ-SYS-07`).
4. **Rodar `pio run -e esp32-s3`** (`REQ-SYS-06`): é o que avalia os
   `static_assert` de `REQ-COM-02` e `REQ-WDT-03`, hoje escritos e nunca
   verificados.
5. **Ensaio de bancada com INA219** (`REQ-PWR-01/02/03/06`, `REQ-WDT-01/02/05`)
   — sete requisitos de uma vez, e é o único caminho para eles.

---

## 11. Como reproduzir a verificação

```bash
# Suíte de host, caminho oficial (exige PlatformIO)
pio test -e native                     # 76 casos definidos; 70 rodam no perfil de dev

# Caminho usado nesta revisão, sem PlatformIO: compilação direta de lib/ + test/
# com um substituto mínimo de Unity. Resultado: 76 casos, 0 falhas
#   perfil de desenvolvimento: 8 + 9 + 21 + 32 = 70 casos
#   com -D KAELIX_PRODUCTION:  8 + 9 + 21 + 38 = 76 casos

# Pipeline de treino
cd training && python -m pytest tests/  # não executado nesta revisão (sem numpy/sklearn)

# Regras de arquitetura (§1 da arquitetura), executadas nesta revisão
grep -rn 'Arduino\.h\|esp_\|driver/\|<RadioLib' lib/     # REQ-SYS-02 — só comentário
grep -rn '#include "\.\./' src/*/                        # REQ-SYS-03 — acusa model.h:4
grep -rn '\bnew \|malloc(\|std::vector' lib/ src/        # REQ-SYS-01 — só comentários

# Build do alvo — não executado
pio run -e esp32-s3                                      # REQ-SYS-06
```

## 12. Manutenção desta matriz

- Cada requisito deve aparecer como comentário `// REQ-VIB-04` na função que o
  implementa e no caso de teste que o verifica. Hoje há exatamente **oito** dessas âncoras no repositório: `REQ-ML-002` (numeração
  antiga) em `isolation_forest.h:71`, `isolation_forest.cpp:65` e
  `test_isolation_forest.cpp:241`, e `REQ-SEG-16/32/33/49` em `main.cpp`,
  `watchdog.h` e `lora.h`. Todo o restante da ligação vive apenas nesta tabela,
  o que a torna frágil a refactor — a primeira renomeação de função quebra a
  rastreabilidade sem que nada acuse.
- Requisito novo entra com estado **NV** e motivo explícito. Estado `V` só com
  teste que roda em comando versionado.
- Um requisito só sai de `X` quando a verificação que reprovava passa a passar —
  nunca por ajuste do enunciado.
- Esta tabela **substitui** a semente do §9 de `docs/ARQUITETURA-SOFTWARE.md` e
  o esqueleto do §9 de `docs/ANALISE-DE-FALHAS.md`, que passam a apontar para
  cá. Os `REQ-SEG-nn` da FMEA continuam válidos como requisitos de mitigação e
  aparecem na linha "Origem" de cada área.
