# Kaelix

Dispositivo IoT de manutenção preditiva para motores industriais — monitora
vibração e temperatura, roda um modelo de detecção de anomalias embarcado
(TinyML) e transmite o resultado via LoRa. TCC de Engenharia de Software
(ICEV), inspirado na arquitetura do TRACTIAN Smart Trac.

O hardware físico ainda não foi montado. Todo o firmware e o pipeline de
treino foram desenvolvidos e testados em simulador e dados offline, para que
a integração com o hardware real seja só calibração quando ele chegar.

## Hardware alvo

| Componente | Modelo | Interface |
|---|---|---|
| Microcontrolador | ESP32-S3-WROOM-1 N16R8 | — |
| Acelerômetro/giroscópio | MPU6050 | I2C (endereço 0x68) |
| Temperatura | Termistor NTC 10K (beta 3950) | ADC analógico |
| Rádio | RA-02 (SX1278) LoRa 433MHz | SPI |
| Regulador | HT7333 (LDO 3,3V ultra baixo consumo) | — |
| Corte de energia | Load switch high-side: SI2301 (P-MOSFET) + BC847B (inversor) | GPIO |
| Proteção de entrada | SI2301 em série (polaridade invertida) | — |
| Medição da bateria | Divisor 1M/1M + 100n | ADC analógico |

### Pinagem

| Uso | Pino | Observação |
|---|---|---|
| I2C (MPU6050) | SDA=8, SCL=9 | *default* da placa — ainda não usado (I2C real é TODO) |
| SPI (LoRa) | MOSI=11, MISO=13, SCK=12, SS=10 | *default* da placa |
| LoRa DIO0 | 14 | escolhido para não colidir com I2C |
| LoRa RESET | 21 | escolhido para não colidir com I2C |
| NTC (ADC) | 4 | placeholder |
| Corte de energia (+3V3_SW) | 5 | ativo-alto; RTC-capable, ver *deep sleep* |
| Tensão da bateria (ADC) | 6 | divisor 1M/1M; 4,2 V → 2,10 V, 3,0 V → 1,50 V |

Conferidos sem conflito entre si e contra o `pins_arduino.h` real da variante
`esp32s3`, mas ainda não contra um esquemático físico definitivo.

**Microcontrolador conferido contra a peça real.** Um ESP32-S3 foi lido com
`esptool`: QFN56 revisão v0.2, 16 MB de flash, 8 MB de PSRAM embarcada. Confirma a
variante N16R8 que o `platformio.ini` declara — e portanto a necessidade de
sobrescrever o perfil da `devkitc-1`, que declara 8 MB de flash e nenhuma PSRAM.
Os demais componentes (MPU6050, NTC, SX1278) continuam não montados.

## O ciclo

```
acordar → energizar periféricos (100ms de estabilização)
        → ler 512 amostras a 1 kHz + NTC
        → extrair RMS, curtose, fator de crista, frequência dominante
        → inferir Isolation Forest embarcado
        → transmitir 21 bytes via LoRa
        → dormir o rádio, cortar periféricos, deep sleep (12 min)
```

Todo o trabalho acontece em `setup()`; `loop()` nunca executa, porque o
dispositivo entra em deep sleep antes de chegar lá.

---

# Decisões de arquitetura

Esta seção registra o *porquê* das escolhas não óbvias — útil tanto para
retomar o desenvolvimento quanto para justificá-las numa defesa.

## Separar matemática pura de acesso a hardware

É a decisão estruturante do projeto. Cada capacidade do firmware foi
dividida em duas camadas:

- **`lib/<nome>/`** — funções puras, sem `Arduino.h`, sem I2C/ADC/SPI.
  Compilam e rodam no host pelo ambiente `native` do PlatformIO.
- **`src/sensors/`, `src/ml/`, `src/comms/`, `src/power/`** — a camada que
  fala com o hardware de verdade e chama as funções de `lib/`.

Foi isso que permitiu desenvolver e validar a maior parte da lógica sem ter
o ESP32-S3, o MPU6050 ou o RA-02 em mãos. Quando o hardware chegar, só a
camada `src/` muda — trocar buffers zerados por leituras reais — porque a
matemática já está testada.

## FFT própria em vez de `arduinoFFT`

A implementação própria (radix-2 Cooley-Tukey, iterativa, sem alocação
dinâmica) compila tanto no ambiente `esp32-s3` quanto no `native`, o que
permite testá-la no host com senoides de frequência conhecida antes de
qualquer hardware. `arduinoFFT` foi avaliada e nunca chegou a ser usada.

`n` precisa ser potência de 2 — responsabilidade do chamador
(`VIBRATION_SAMPLES = 512`).

## Frequência dominante da velocidade, não da aceleração

Aceleração escala com ω², então o espectro de aceleração é sempre dominado
pelo conteúdo de alta frequência — tipicamente um modo estrutural da
montagem, que é o mesmo com a máquina sadia ou defeituosa. Medido em dados
reais do MAFAULDA: o pico de aceleração fica em 117 Hz independente da
rotação, com correlação de **−0,018** contra a rotação real do ensaio.

A magnitude é reponderada por `|V(f)| = |A(f)|/(2πf)` e a busca fica
restrita a 10–1000 Hz. A fase é irrelevante para escolher o bin de pico,
então não é preciso integrar o sinal — só reponderar o espectro que a FFT já
produziu. Custo no firmware: uma divisão por bin.

O limite inferior da banda não é cosmético: sem ele, a ponderação 1/f faria
o bin mais baixo vencer sempre.

**Efeito medido** em 880 arquivos reais, mesmo protocolo: detecção de 11,7%
para 38,5%, F1 de 0,178 para 0,550. A AUC global quase não se move
(0,795 → 0,805), o que ilustra por que ela não serve como métrica de
operação.

## Isolation Forest nativo, sem TensorFlow Lite Micro

O modelo é um Isolation Forest (scikit-learn), mas a inferência embarcada
**não** usa TFLite Micro — usa uma implementação C++ própria
(`lib/isolation_forest/`) que percorre diretamente as árvores exportadas.

TensorFlow Lite é desenhado para redes neurais; Isolation Forest é um
ensemble de árvores cujo score é o comprimento médio de caminho até isolar
um ponto. Não existe caminho oficial e confiável de conversão
scikit-learn → TFLite Micro para esse tipo de modelo, e a rota possível
(`skl2onnx` → `onnx-tf` → `TFLiteConverter`) depende de ferramentas pouco
mantidas. A alternativa nativa é mais simples, mais leve em RAM/Flash, e
elimina a dependência frágil.

### Como funciona

1. `isolation_path_length_correction(n)` — c(n), o comprimento médio de
   caminho esperado numa árvore binária com n amostras. Mesma fórmula do
   scikit-learn, incluindo os casos `c(1)=0` e `c(2)=1`.
2. `isolation_tree_path_length` — percorre a árvore até a folha e soma a
   profundidade com a correção da folha.
3. `isolation_forest_score` — média entre as árvores, normalizada:
   `score = 2^(−caminho_médio / c(n))`, em (0,1]. Próximo de 1 = anômalo.

### Validação cruzada Python ↔ C++

`training/tests/test_export_cpp.py` treina um modelo, exporta o header,
**compila de verdade com g++**, roda o binário e compara o score contra
`-clf.score_samples(X)` do scikit-learn, com tolerância de 1e-4. É o que
garante, de forma verificável, que treino e inferência não divergem.

O vetor de features é o mesmo dos dois lados (`src/ml/model.cpp` e
`training/kaelix_ml/features.py::FEATURE_ORDER`):

```
[rms, kurtosis, crest_factor, dominant_freq_hz]
```

`temperature_c` é lido e passado para `model_infer`, mas ainda não entra no
vetor.

### Estado do modelo embarcado

`src/ml/isolation_forest_data.h` traz o modelo treinado nos dados reais do
MAFAULDA: `N_TREES = 100`, `N_FEATURES = 4`, `ANOMALY_THRESHOLD = 0,55719777`
(quantil de calibração, não 0,5). O arquivo é gerado por
`python -m kaelix_ml.train` — use `--out` para exportar a outro caminho e
preservar o que está versionado.

`model_init` e `model_infer` mantêm a guarda `N_TREES <= 0`, que devolve
`Status::ModelAbsent` e deixa o veredito em `Unknown`. Ela deixou de ser o
caminho normal quando o modelo foi embarcado, mas continua sendo o
comportamento correto para um build sem modelo — e é o que impede que a
ausência de árvores vire "máquina sadia".

## Protocolo de treino e calibração

**Domínio alinhado com o firmware.** Os datasets vêm a 50 kHz (MAFAULDA) ou
12/48 kHz (CWRU), em registros de segundos; o dispositivo lê 512 amostras a
1 kHz. Extrair features do arquivo inteiro produziria um modelo inaplicável
— `dominant_freq_hz` chegaria a 25 kHz no treino e nunca passaria de 500 Hz
em campo. `dataset.to_device_windows` decima e fatia todo sinal antes de
virar feature.

**Split por ensaio.** `GroupKFold` com o arquivo de origem como grupo, para
que janelas do mesmo ensaio nunca fiquem dos dois lados do split. O relatório
traz média ± desvio entre folds: desvio alto é informação sobre falta de
ensaios, não ruído a esconder atrás de um número único.

**Limiar por taxa de falso alarme alvo.** O limiar não é 0,5 nem vem do
`contamination`: é o quantil dos scores de um conjunto de calibração formado
por grupos que o modelo não viu no fit. O default `contamination="auto"`
marcaria ~42% da operação normal como anomalia.

**Mesma regra de decisão dos dois lados.** Calibração, avaliação e exportação
usam `device_score()` = `-clf.score_samples(X)`, a convenção (0,1] idêntica à
de `lib/isolation_forest/`. Usar `clf.predict()` faria o relatório do treino
descrever um comportamento diferente do embarcado.

**Rótulo verdadeiro do caminho, ISO como diagnóstico.** Quando o dataset
codifica a classe de falha na estrutura de diretórios — como o MAFAULDA faz
— é esse o rótulo usado. O rótulo derivado da ISO 10816-3 é calculado em
paralelo e o treino imprime a matriz de concordância. Em dados reais, a ISO
sob classe I marca **93,4% da operação genuinamente normal como anômala**,
o que a desqualifica como fonte de rótulo para este dataset.

## Temperatura

Duas funções puras em `lib/thermistor/`:

1. `ntc_resistance_from_millivolts` — converte a leitura para resistência,
   assumindo o divisor `Vcc → R_FIXED → nó de leitura → NTC → GND`.
   **Topologia assumida, não confirmada contra o esquemático final.**
2. `ntc_resistance_to_celsius` — equação B (Steinhart-Hart simplificada).

O firmware usa a variante em milivolts porque o ADC bruto do ESP32-S3 é
sensivelmente não-linear; `analogReadMilliVolts` aplica a curva de calibração
gravada no eFuse de fábrica. Usar a contagem crua assume uma linearidade que
o hardware não tem e enviesa a temperatura.

## Comunicação LoRa

RadioLib, SX1278, 433 MHz, TX a 17 dBm. API conferida contra o código-fonte
da versão instalada.

### Pacote — 21 bytes, versão 2

| Campo | Bytes | Por quê |
|---|---|---|
| `version` | 1 | o gateway precisa saber interpretar o layout; sem isso, mudar o formato vira leitura silenciosamente errada do outro lado |
| `device_id` | 4 | do eFuse MAC. Com mais de um Kaelix na planta, sem ele o gateway não sabe de quem é a leitura |
| `boot_count` | 4 | contador em RTC memory, sobrevive ao deep sleep. Dá sequência e detecção de pacote perdido |
| `state` | 1 | `kaelix::MachineState` — normal, anômalo ou **desconhecido** |
| `diag` | 1 | `kaelix::status_code()` do primeiro erro do ciclo (0 = Ok). É o canal de diagnóstico de produção: sem ele, `state = Unknown` chega ao gateway sem dizer por quê |
| `rms` | 4 | NaN = não medido |
| `temperature_c` | 4 | NaN = não medido |
| `crc` | 2 | CRC-16/CCITT sobre os 19 bytes anteriores |

A v1 tinha 20 bytes e um campo `status` binário. O `state` ternário e o `diag`
entraram juntos: um veredito que pode ser "não sei" é inútil se o outro lado
não recebe a causa.

O campo `timestamp` que existia antes era `millis()`, que zera a cada deep
sleep — todo pacote chegava com ~3000 ms. Não era um relógio. O tempo de
parede é responsabilidade do gateway, que carimba na recepção.

O CRC vive em `lib/crc16/` como função pura, testada no host contra o vetor
de conferência padrão (`"123456789"` → `0x29B1`): um pacote corrompido no ar
que chegue ao gateway como leitura válida é pior que um pacote perdido.

Um `static_assert` trava o tamanho do struct, para que uma mudança de layout
não passe despercebida sem bump de `PACKET_VERSION`.

### Topologia de rede e o elo que falta

O dispositivo transmite. Do outro lado existe um receptor **em simulação**, em
`experiments/gateway/` — decodificação do quadro, estado por dispositivo, detecção de
lacuna na sequência e regra de alerta, com 19 testes. Não existe receptor em rádio
real: nada nunca recebeu um pacote pelo ar.

**E o gateway está uma versão atrás.** `packet.py` fixa `PACKET_VERSION = 1` e
`PACKET_SIZE = 20`; o firmware emite v2 com 21 bytes. A guarda de versão faria o
gateway recusar **todos** os pacotes do firmware atual — falha segura, e a defesa
funcionando como projetada, mas a cadeia ponta-a-ponta simulada não corresponde ao
dispositivo. Os 19 testes passam porque o gateway é exercitado contra o próprio
`codificar()`, um laço fechado em v1: o teste de paridade cruza a **função** CRC com
`lib/crc16`, não o **layout** da struct. O byte `diag`, que o firmware trata como
canal de diagnóstico de produção, não tem leitor nenhum.

Fechar isso é subir o gateway para v2 e criar um teste que gere o quadro a partir do
layout de `src/comms/lora.h`, em vez do próprio codificador.

**LoRa cru, não LoRaWAN.** `radio.transmit()` direto: sem endereçamento de rede, sem
join, sem criptografia, sem confirmação. Qualquer receptor na mesma frequência, SF e
syncWord recebe o pacote. É escolha, não esquecimento — LoRaWAN exigiria um
concentrador multicanal em vez de um SX1278 e traria complexidade que um protótipo não
paga. Mas o custo aparece nos itens abaixo.

**Sem confirmação, sem retransmissão.** `lora_send()` informa se a transmissão saiu,
não se chegou. Um pacote perdido some em silêncio. O `boot_count` existe para que o
gateway detecte o buraco na sequência — sem gateway, isso é teoria.

**Colisão.** ALOHA puro. Com 185 ms no ar e ciclo de 720 s, a probabilidade de colisão
é 1,0% para 20 dispositivos e 2,5% para 50. Aceitável.
(Uma revisão anterior dava 1,5% e 3,7%: aqueles valores correspondem a 226 ms, o tempo
no ar em `CR 4/7`, que não é o que o firmware usa — ele fixa `CR 4/5`.) Mas essa conta pressupõe fases
aleatórias, e uma instalação em que os aparelhos são ligados juntos não tem fase
aleatória: eles acordariam no mesmo instante e colidiriam de forma sistemática. É o que
o deslocamento anticolisão em `transmission_jitter_seconds()` resolve.

**Sem downlink.** O dispositivo nunca escuta. Intervalo de sono, limiar de anomalia e
modelo são fixos no flash. Atualizar qualquer um exige regravar cada aparelho
fisicamente. A base magnética facilita a remoção, mas continua sendo trabalho manual
por unidade. Downlink exigiria janela de recepção após a transmissão, com custo de
energia a orçar.

**Risco regulatório: 433 MHz não é faixa ISM no Brasil.** A Resolução 680 da Anatel
define 902–907,5 MHz e 915–928 MHz para radiação restrita. Para protótipo acadêmico é
irrelevante; para qualquer intenção de produto, é bloqueante — o dispositivo não
passaria em homologação. A migração para 915 MHz (RA-01H, SX1276) é praticamente
drop-in em firmware, então o custo de errar é baixo. O risco precisa estar registrado,
e é este o registro.

**O que existe depois do gateway.** Nada definido: banco de dados, painel, alerta ao
manutentor. E o `device_id` é um número do eFuse — alguém precisa mapeá-lo para
"compressor 3". Esse cadastro não existe.

Um gateway mínimo — ESP32 ou Raspberry Pi com SX1278, validando o CRC com a mesma
lógica de `packet_is_valid()` e publicando o resultado — é o que transformaria
"transmite" em "sistema funciona de ponta a ponta". Fica como trabalho futuro,
registrado aqui para não ser confundido com esquecimento.

## Deep sleep e orçamento de energia

Ciclo: acordar → ler e processar (3s) → transmitir (~150ms) → deep sleep
(10min).

| Fonte | Corrente | Origem |
|---|---|---|
| ESP32-S3 ativo (sem WiFi) | ~40 mA | típico, datasheet Espressif |
| MPU6050 em operação | ~3,9 mA | datasheet InvenSense |
| SX1278 TX @ ~17dBm | ~90 mA | datasheet Semtech |
| **SX1278 standby (STDBY)** | **~1,5 mA** | datasheet Semtech |
| **SX1278 sleep** | **~0,2 µA** | datasheet Semtech |
| ESP32-S3 deep sleep | ~10 µA | fornecido no escopo do projeto |
| HT7333 quiescente | ~8 µA | fornecido no escopo do projeto |

### A linha que decide o orçamento

O rádio **não** está no rail comutado (+3V3_SW), então o estado em que
ele passa os 12 minutos de sleep é decidido por software:

```
sem lora_sleep():  (1,5 + 0,018) mA × 720s = 1093,0 mA·s
com lora_sleep():  (0,0002 + 0,018) mA × 720s = 13,1 mA·s
```

Sozinha, essa diferença é 5,5× maior que o orçamento inteiro do ciclo.
`comms::lora_sleep()` antes do `deep_sleep()` é obrigatório, não opcional.

### Carga por ciclo, com o rádio dormindo

```
Fase ativa (3,0s):   (40 + 3,9 + 1,5 + 0,008) mA × 3,0s   = 136,22 mA·s
                     (o rádio fica em standby depois do begin())
Fase TX (0,185s):    (40 + 3,9 + 90 + 0,008) mA × 0,185s  =  24,77 mA·s
Fase sleep (720s):   (0,0002 + 0,010 + 0,008) mA × 720s   =  13,10 mA·s
                                                   Total  = 171,91 mA·s
```

Corrente média do circuito: `171,91 ÷ 603,19 ≈ 285 µA`.

O tempo de transmissão não é estimativa: sai do cálculo de tempo no ar para os
parâmetros fixados em `src/comms/lora.cpp` (SF9, BW 125 kHz, CR 4/5, preâmbulo de 8
símbolos, 21 bytes de payload). Antes o orçamento assumia 150 ms, número que não vinha
de cálculo nenhum, e os parâmetros do enlace ficavam nos defaults do RadioLib — de modo
que uma atualização da biblioteca mudaria o consumo do produto em silêncio.

Alcance e autonomia são o mesmo botão:

| SF | Tempo no ar | Autonomia | Ganho de enlace | REQ-PWR-06 (≥ 8 meses) |
|---|---|---|---|---|
| 7 | 57 ms | 292 dias | referência | ✅ |
| 8 | 103 ms | 283 dias | +2,5 dB | ✅ |
| **9 (atual)** | **185 ms** | **269 dias** | **+5,0 dB** | ✅ |
| 10 | 371 ms | 243 dias | +7,5 dB | ✅ (no limite) |
| 11 | 741 ms | 202 dias | +10,0 dB | ❌ |
| 12 | 1483 ms | 152 dias | +12,5 dB | ❌ |

Tempo no ar para 21 bytes em `CR 4/5`; autonomia para o ciclo de 12 min. A tabela
anterior era de 20 bytes e do ciclo de 10 min.

A escolha definitiva depende da distância entre os motores e o gateway, que ainda não
foi medida. O período de 12 min é o que mantém **SF10 dentro do orçamento** — a 10 min
ele dava 211 dias e a decisão de alcance ficava travada pela energia.

Somando a autodescarga da LiPo (~2,5%/mês sobre 2000 mAh ≈ **68,5 µA**, 28%
do orçamento):

```
Consumo efetivo: ~309 µA            → dentro da meta de <1mA, margem ~3,2×
Autonomia (LiPo 2000mAh): ~269 dias (~8,8 meses)
```

REQ-PWR-06 (autonomia ≥ 8 meses) fica atendido com ~26 dias de margem. A 10 min o
projeto entregava 236 dias (7,7 meses) e o requisito não era atendido — não por
medição, mas desde que os 150 ms estimados de tempo no ar viraram 185 ms calculados.

Para comparação, sem `lora_sleep()` o consumo seria ~1,83 mA e a autonomia
cairia para ~48 dias.

### Retenção do GPIO

GPIOs não-RTC vão para alta impedância ao entrar em deep sleep, o que
deixaria a base de Q2 flutuando justamente durante os 12 minutos em que
o corte de energia precisa valer. `deep_sleep()` chama `gpio_hold_en()` +
`gpio_deep_sleep_hold_en()`; `peripherals_power()` chama `gpio_hold_dis()` no
boot seguinte, porque o hold sobrevive ao reset e travaria o pino.

---

# Status

| Frente | Situação |
|---|---|
| Estrutura do firmware (PlatformIO) | ✅ Completa |
| Processamento de vibração (RMS, curtose, fator de crista, FFT) | ✅ Implementado e testado |
| Frequência dominante na velocidade band-limitada | ✅ Paridade C++/Python verificada numericamente |
| Temperatura (NTC + Steinhart-Hart, ADC calibrado) | ✅ Implementado e testado |
| Deep sleep, corte de energia, retenção de GPIO | ✅ ~309 µA médio, autonomia ~269 dias (ciclo de 12 min) |
| LoRa (RadioLib) com device id, sequência e CRC-16 | ✅ Implementado; transmissão real não testada |
| Pipeline de treino (Isolation Forest) | ✅ Validado ponta-a-ponta |
| Split por ensaio + limiar por falso alarme alvo | ✅ `GroupKFold` + calibração por quantil |
| Alinhamento treino ↔ inferência (1 kHz, 512 amostras) | ✅ `dataset.to_device_windows` |
| Treino com dados reais (MAFAULDA) | ✅ 1951 arquivos, 17.559 janelas |
| Modelo embarcado no firmware | ✅ 100 árvores, limiar 0,55719777 |
| Build do firmware para ESP32-S3 | ✅ `pio run -e esp32-s3` limpo — RAM 8,5%, Flash 9,0% de 6,25 MB |
| Watchdog RTC (WDT-1) no ESP32-S3 | ✅ Via `hal/wdt_hal.h`; armado e linkado, comportamento não medido |
| Gateway ↔ firmware na mesma versão de pacote | ❌ Gateway em v1/20 B, firmware em v2/21 B |
| Simulação Wokwi | 🟡 Arquivo pronto; só ESP32+MPU6050, sem NTC nem rádio |
| Leitura I2C real do MPU6050 + DLPF | ⬜ Bloqueado — precisa do hardware físico |
| Calibração física, consumo real, alcance LoRa | ⬜ Bloqueado — precisa do hardware físico |

## O que o modelo detecta

Medido com `GroupKFold` por ensaio, a 2% de falso alarme, em dados reais do
MAFAULDA:

| Classe | Detecção |
|---|---|
| Desbalanceamento | **75,0% ± 3,5%** |
| Defeito de rolamento (0g, puro) | 15–21% |
| Desalinhamento vertical | 7,2% ± 4,3% |
| Desalinhamento horizontal | 5,0% ± 3,1% |

Só desbalanceamento é detectável de forma útil hoje, e as outras duas falham
por motivos diferentes:

- **Desalinhamento** — limitação do vetor de features, não do sensor. A
  assinatura é a razão entre as linhas de 2× e 1× rotação, que nenhuma das
  quatro features captura. Corrigível em software.
- **Rolamento** — limitação de banda. Com Nyquist em 500 Hz, a ressonância de
  3–10 kHz que carrega a assinatura do defeito já foi descartada na
  aquisição. Nenhuma feature recupera informação que o sensor não capturou.

Atenção ao ler números agregados deste dataset: o MAFAULDA roda os ensaios de
rolamento **com massa de desbalanceamento adicionada** (0g, 6g, 20g, 35g), e
a detecção acompanha a massa, não o defeito — de 14,8% em 0g a 87,3% em 35g.
Reportar detecção de rolamento sem estratificar pela massa infla o resultado.

---

# Estrutura do projeto

```
kaelix-firmware/
├── platformio.ini      # ambientes esp32-s3 (firmware real) e native (testes)
├── pyproject.toml      # ambiente Python das análises, figuras e notebooks
│
├── src/                # camada que fala com o hardware
│   ├── main.cpp          # ciclo principal
│   ├── sensors/          # vibração (I2C, TODO) e temperatura (ADC)
│   ├── ml/               # integração do modelo de detecção de anomalias
│   ├── comms/            # empacotamento e envio LoRa
│   └── power/            # deep sleep e corte de energia
├── lib/                # lógica pura, sem Arduino — testável em `native`
│   ├── signal_processing/  # RMS, curtose, fator de crista, FFT
│   ├── thermistor/         # conversão mV → resistência → °C
│   ├── isolation_forest/   # inferência do modelo de anomalia
│   └── crc16/              # integridade do pacote LoRa
├── test/               # testes unitários do firmware (PlatformIO + Unity)
├── wokwi/              # simulação (ESP32-S3 + MPU6050)
│
├── training/           # pipeline Python de treino do modelo
│   ├── kaelix_ml/        # ingestão, features, rotulagem, treino, export C++
│   └── tests/            # testes do pipeline (pytest)
├── tools/              # verificação reproduzível e análise estática
├── data/               # datasets — brutos ignorados, cache derivado versionado
│
├── docs/
│   ├── referencias.md    # revisão de literatura
│   ├── relatorio/        # monografia (LaTeX + PDF)
│   ├── device/           # desenho técnico do invólucro
│   └── img/
├── experiments/        # notebooks de validação numérica (fonte da verdade)
└── experiments/figures/  # figuras em padrão de submissão
    ├── scripts/          # exportadores Python + plot em R (ggplot2)
    ├── data/             # CSVs rastreáveis
    └── output/           # SVG/PDF vetoriais, TIFF 600 dpi
```

`docs/relatorio/` contém quatro documentos: o relatório de simulação da cadeia de
medição, a revisão de literatura, a análise de comunicação e topologia, e a tabela
de práticas de tolerância a falhas em sistemas embarcados críticos
(`praticas-sistemas-criticos.tex` — redundância aviônica, normas de garantia e o que
o Kaelix adota, não adota e por quê).

Histórico de mudanças em [CHANGELOG.md](CHANGELOG.md).

# Como rodar

## Firmware

```bash
pio run -e esp32-s3
```

## Testes do firmware (sem hardware, roda no host)

```bash
./tools/run-all-tests.sh      # as três suítes de uma vez
```

São três, em duas linguagens, e rodá-las separadamente é como quebra de
integração passa: um refactor em `lib/` que muda assinatura aparece no teste C++,
mas o gerador Python que consome a mesma struct só quebra na suíte de treino.

| Suíte | Casos | Cobre |
|---|---|---|
| `tools/run-native-tests.sh` | 146 | `lib/`, nos dois modos de build |
| `training/tests/` | 35 | pipeline de treino, paridade C++↔Python |
| `experiments/gateway/tests/` | 19 | pacote, receptor, cadeia simulada |

Nenhuma cobre a camada `src/`, que depende de `pio run -e esp32-s3`.

## Pipeline de treino

```bash
cd training
pip install -r requirements.txt
python -m pytest tests/            # 35 testes, inclui compilação real com g++
python -m kaelix_ml.ingest --all   # baixa o MAFAULDA e cacheia (~12GB -> 32MB)
python -m kaelix_ml.train          # treina e exporta o header C++
```

`ingest` processa uma classe por vez e apaga os CSVs após cachear, então o
pico de disco é o maior tarball e não os ~31 GB extraídos. É resumível, com
timeout e retomada por HTTP Range.

`train` imprime a validação cruzada por ensaio com média ± desvio entre
folds, AUC, pAUC e a matriz de concordância com a ISO 10816-3. Use `--out`
para exportar o header a outro caminho e preservar o placeholder do
repositório.

Sem dados em `data/`, o treino cai para dados sintéticos com aviso em stderr
— serve para exercitar o pipeline, não como modelo utilizável.

## Simulação Wokwi

Abrir a pasta em [wokwi.com](https://wokwi.com) ou pela extensão do VSCode,
usando `wokwi/diagram.json`. O diagrama tem só ESP32-S3 e MPU6050 — sem NTC e
sem rádio — e, como a leitura I2C ainda é um stub, a simulação hoje exercita
pouco além do boot.

# Pendências conhecidas

- **Gateway uma versão atrás do firmware.** `experiments/gateway/packet.py` fixa
  `PACKET_VERSION = 1` e 20 bytes; o firmware emite v2 com 21 bytes. O gateway
  recusaria todo pacote real. Os 19 testes passam porque exercitam o gateway
  contra o próprio codificador — nenhum teste cruza a fronteira firmware↔gateway.
  O caso `test_crc16_valores_de_referencia_do_pacote_de_20_bytes` também congela o
  tamanho da v1.
- **Comportamento do WDT-1 não medido.** O build prova que a API do RWDT é usada
  corretamente e que resolve em link; não prova que o contador sobrevive ao deep
  sleep, premissa em que se apoiam o `watchdog_arm_for_sleep` e o despertador de
  último recurso. Medir com o timer de despertar desabilitado.
- **Nada foi transmitido pelo ar.** `lora_init()` e `lora_send()` compilam contra a
  RadioLib instalada, mas nenhum pacote saiu de um SX1278 real.
- **Pinos GPIO** são placeholders sem conflito entre si, mas não conferidos
  contra um esquemático final. O pino de corte de energia precisa ser
  RTC-capable para que `gpio_hold_en` funcione.
- **Correntes do SX1278** (standby ~1,5mA, sleep ~0,2µA) e a autodescarga da
  LiPo (~2,5%/mês) são valores de datasheet. São os dois termos que mais
  pesam no orçamento de energia — medir com INA219 na Fase 3.
- **Layout do CWRU.** O download oficial entrega `.mat` soltos e numerados,
  sem estrutura de pastas; é preciso organizar em `normal/`, `ir/`, `or/`,
  `b/` antes de carregar. `cwru_label_from_path` falha alto até lá, de
  propósito — rotular errado em silêncio contamina o treino inteiro.
- **Limiares da ISO 10816-3** (`training/kaelix_ml/labeling.py`): valores
  comumente citados na literatura, não conferidos contra o texto oficial nem
  contra a classe real do motor de bancada. A integração para velocidade já
  usa o método validado; o que falta são os limiares de zona.
- **Banda ISO coberta pela metade.** Com 1 kHz de amostragem o Nyquist é
  500 Hz, contra os 1000 Hz que a norma exige. Conformidade plena não é
  possível com o MPU6050.
- **Alcance LoRa e taxa de perda** nunca testados em campo.
