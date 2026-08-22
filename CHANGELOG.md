# Changelog

Registro das mudanças do projeto Kaelix. Formato baseado em
[Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).

## [Não publicado]

## Firmware — bloco de energia e integridade do pacote

### Corrigido — o SX1278 nunca entrava em sleep

Correção de maior impacto do bloco. O rádio não está no barramento cortado
pelos BC337, e o código nunca chamava `radio.sleep()`: depois do
`transmit()`, o RadioLib devolve o módulo para STANDBY, onde consome
~1,5 mA continuamente — inclusive durante os 10 minutos de deep sleep.

```
sem lora_sleep():  (1,5 + 0,018) mA × 600s = 910,8 mA·s
com lora_sleep():  (0,0002 + 0,018) mA × 600s = 10,9 mA·s
```

Sozinha, a diferença é 5,5× o orçamento inteiro do ciclo. O orçamento
publicado não tinha termo nenhum de LoRa idle.

### Corrigido — orçamento de energia refeito

Além do rádio, dois erros na conta anterior: a autonomia era calculada para
uma 18650 de 3000 mAh enquanto `project.md` especifica LiPo de 2000 mAh, e
a autodescarga da bateria (~2,5%/mês = ~68,5 µA, 25% do orçamento) não
entrava.

| | Antes (publicado) | Real, sem a correção | Depois |
|---|---|---|---|
| Corrente média | 270 µA | ~1,84 mA | **~346 µA** |
| Autonomia | 464 dias (18650 3000mAh) | ~45 dias | **~241 dias** (LiPo 2000mAh) |
| Meta <1 mA | ✅ margem 3,7× | ❌ 84% acima | ✅ margem 2,9× |

Os números anteriores estavam em `sleep.cpp`, `ARQUITETURA.md`, `README.md`
e `project.md`, agora todos alinhados.

### Corrigido — GPIO flutuava durante o deep sleep

GPIOs não-RTC vão para alta impedância ao entrar em deep sleep, deixando a
base dos BC337 flutuando justamente durante os 10 minutos em que o corte de
energia precisa valer. `deep_sleep()` agora chama `gpio_hold_en()` +
`gpio_deep_sleep_hold_en()`, e `peripherals_power()` chama `gpio_hold_dis()`
no boot seguinte — o hold sobrevive ao reset e travaria o pino se não fosse
solto.

### Corrigido — pacote LoRa não identificava o emissor nem detectava erro

O pacote tinha status, RMS, temperatura e um `timestamp` que era `millis()`
— que zera a cada deep sleep, então todo pacote chegava com ~3000 ms. Não
era um relógio. E sem identificação, um gateway com mais de um Kaelix na
planta não teria como saber de quem era a leitura.

Novo formato, 20 bytes: `version`, `device_id` (eFuse MAC), `boot_count`
(RTC memory, sobrevive ao sleep), `status`, `rms`, `temperature_c`, `crc`.

O CRC-16/CCITT vive em `lib/crc16/` como função pura, testada no host
contra o vetor de conferência padrão (`"123456789"` → `0x29B1`) e contra
bit invertido e troca de bytes. Um pacote corrompido no ar que chegue ao
gateway como leitura válida é pior que um pacote perdido.

Layout e round-trip verificados isoladamente: 20 bytes, offsets corretos,
CRC detecta 1 bit invertido.

### Corrigido — retornos de init eram ignorados

`main.cpp` descartava o `bool` dos quatro `*_init()` e de `lora_send()`: o
dispositivo transmitia mesmo com o rádio fora do ar, e uma falha de TX
sumia em silêncio. Agora cada falha é reportada e a transmissão é
condicionada ao rádio ter subido.

Acrescenta também `delay(100ms)` após energizar os periféricos — o MPU6050
precisa estabilizar antes do init.

### Corrigido — ADC do NTC assumia linearidade que o hardware não tem

`analogRead()` no ESP32-S3 é sensivelmente não-linear. A leitura passa a
usar `analogReadMilliVolts()`, que aplica a curva de calibração gravada no
eFuse de fábrica, com `analogSetPinAttenuation(ADC_11db)` para abrir a
faixa aos ~3,3 V do divisor. `lib/thermistor` ganhou
`ntc_resistance_from_millivolts` com testes.

### Corrigido — `platformio.ini` não declarava o hardware alvo

O alvo é o WROOM-1 **N16R8** (16 MB de flash, 8 MB de PSRAM octal), mas o
perfil default da `esp32-s3-devkitc-1` declara 8 MB de flash e nenhuma
PSRAM — metade da flash e toda a PSRAM ficavam invisíveis. Adicionados
`board_build.flash_size`, `partitions`, `memory_type = qio_opi` e
`-D BOARD_HAS_PSRAM`.

### Verificação

26 testes C++ (eram 20) e 35 Python passando. O firmware completo não pôde
ser compilado aqui (sem toolchain ESP32 nesta máquina) — `pio run -e esp32-s3`
continua sendo o passo que fecha esta rodada.

### Ainda aberto no firmware

Leitura I2C real do MPU6050 e configuração do DLPF (item 1) seguem
bloqueadas por hardware. As correntes do SX1278 e a autodescarga da LiPo
são valores de datasheet — são os dois termos que mais pesam no orçamento e
precisam de INA219 na Fase 3.


### Contexto

Rodada de correções no pipeline de treino (`training/`) para
deixá-lo pronto para receber os datasets reais (MAFAULDA/CWRU). O gatilho foi
uma auditoria de proveniência dos dados: **nenhum número do projeto vinha de
medição** — tudo era simulado — e o pipeline tinha defeitos que fariam o
download dos datasets virar retrabalho.

As correções também fecham a lacuna entre o que
[`docs/questionamentos-tecnicos.md`](docs/questionamentos-tecnicos.md) concluiu
e o que o código fazia: os itens 2, 6 e 7 prescreviam correções que a
implementação ainda não tinha incorporado.

### Corrigido

- **`dataset.py`: busca de arquivos não era recursiva.** `iter_dataset_files`
  usava `Path.glob`, que não desce em subdiretórios. Como o MAFAULDA é
  organizado em pastas por tipo e severidade de falha, a busca encontraria zero
  arquivos e `train.py` cairia em silêncio no fallback sintético — como se nada
  tivesse sido baixado. Agora usa `rglob`.

- **`labeling.py`: faltava a máscara de banda da ISO 10816-3.** A norma define
  as zonas A–D sobre velocidade RMS medida entre 10 Hz e 1000 Hz. A integração
  zerava apenas o bin DC, sem recortar a banda — divergindo do método que o
  item 2 validou com erro de 0,0%. A implementação agora é a mesma do notebook
  (janela de Hann, recorte 10–1000 Hz, compensação de potência da janela),
  verificada contra o valor analítico de referência.

- **Regra de decisão do treino divergia da do firmware.** `train.py` avaliava
  com `clf.predict()`, que decide pelo `offset_` derivado de `contamination`,
  enquanto o dispositivo decide `score > ANOMALY_THRESHOLD`
  (`src/ml/model.cpp`). Os relatórios impressos no treino não descreviam o
  comportamento embarcado. Agora tudo — calibração, avaliação e exportação —
  usa `device_score()`, a mesma convenção do firmware.

- **`contamination="auto"` e limiar fixo em 0,5.** Exatamente o default que o
  item 7 mediu em 42% de falso alarme, e um limiar que não vinha de lugar
  nenhum. O limiar agora é derivado por quantil sobre um conjunto de
  calibração separado por grupo, com taxa de falso alarme alvo explícita
  (`FALSE_ALARM_TARGET = 1%`).

- **Campo `unit` era escrito e nunca lido.** `label_from_acceleration` assumia
  `g` incondicionalmente; um dataset em m/s² seria multiplicado por 9,80665
  outra vez, em silêncio. A conversão agora é explícita (`convert_unit`) e
  falha alto em unidade desconhecida.

- **`load_cwru_mat` era código morto.** Nenhum chamador — nem `train.py`, nem
  os testes. Baixar o CWRU não teria efeito. Agora está ligado ao carregamento
  por `load_device_windows("cwru")`.

### Adicionado

- **Alinhamento entre domínio de treino e de inferência** (`to_device_windows`).
  O treino extraía um vetor de features por arquivo inteiro — MAFAULDA a 50 kHz,
  ~250k amostras — enquanto o firmware extrai de uma janela de 512 amostras a
  1 kHz. `dominant_freq_hz` chegaria a 25 kHz no treino e nunca passaria de
  500 Hz no dispositivo. Todo sinal carregado agora é decimado para
  `DEVICE_SAMPLE_RATE_HZ` (com anti-aliasing FIR em estágios) e fatiado em
  janelas de `DEVICE_WINDOW_SAMPLES`, espelhando `src/main.cpp` e
  `src/sensors/vibration.cpp`.

- **Rótulo verdadeiro lido do caminho do arquivo**
  (`mafaulda_label_from_path`, `cwru_label_from_path`). O MAFAULDA codifica a
  classe de falha na estrutura de diretórios; o pipeline descartava isso e
  derivava o rótulo pelos limiares ISO. Agora o rótulo do caminho é a verdade
  de referência e o rótulo ISO vira **diagnóstico comparativo** — `train.py`
  imprime a matriz de concordância entre os dois.

- **Validação com `GroupKFold` por arquivo de origem** (item 6). Antes não
  havia split algum: `clf.fit(X_normal)` seguido de `clf.predict(X)` sobre o
  mesmo conjunto. O relatório agora traz média ± desvio entre folds, como o
  item 6 exige, e o desvio alto é informação, não ruído a esconder.

- **Calibração do limiar aninhada.** Dentro de cada fold de treino, um
  subconjunto de grupos é separado para calibrar o limiar; a avaliação ocorre
  no fold de validação intocado. Evita o otimismo de calibrar e avaliar no
  mesmo dado.

- **AUC e pAUC no relatório de treino**, com `max_fpr=0.10` — mesma chamada
  usada em `figures/scripts/export_source_data.py`, para que os números sejam
  comparáveis com a Fig. 2e. Atende à crítica A1 de
  [`docs/criticas-da-literatura.md`](docs/criticas-da-literatura.md).

- **`training/tests/test_dataset.py`** — cobre recursão do `rglob`, taxa e
  formato da decimação, janelamento, conversão de unidade e leitura de rótulo
  por caminho.

- **Teste de referência da integração ISO** em `test_labeling.py`, contra o
  valor analítico exato de `figures/data/fig2_referencia.csv`.

### Alterado

- `data/README.md` descrevia os datasets como insumo dos testes unitários de
  `sensors/vibration.cpp`; o consumidor real é o pipeline Python. Reescrito
  com a árvore de diretórios esperada.
- `test/README.md` dizia cobrir `sensors/vibration` e `sensors/temperature`;
  os testes cobrem `lib/signal_processing`, `lib/thermistor` e
  `lib/isolation_forest`.
- `VibrationSample` ganhou o campo `group` (identidade do ensaio/arquivo de
  origem), necessário para o `GroupKFold`. O gerador sintético atribui um grupo
  distinto por amostra.

### Achado durante a implementação

O diagnóstico ISO recém-adicionado produziu resultado logo na primeira
execução: **o gerador sintético rotula como "normal" sinais que a ISO
10816-3 classifica como anômalos** — concordância global de 23,1%, com 100%
das janelas "normais" caindo em zona C/D.

A causa é dimensional. As amostras "normais" sintéticas são senoides de
0,5–1,0 g em torno de 50 Hz; integrando, isso dá ~16 mm/s RMS de velocidade,
contra o limite B/C de 1,8 mm/s da classe I. O gerador nunca foi calibrado
em amplitude contra a norma — ele foi escrito para exercitar o pipeline, e
para isso serve.

Não é um defeito do código novo; é o novo diagnóstico funcionando. Mas
reforça que os números de desempenho obtidos sobre dados sintéticos não
transferem, e que o gerador precisaria de amplitudes fisicamente plausíveis
se algum dia for usado para algo além de teste de fumaça.

### Layout do MAFAULDA conferido em fonte primária

Os nomes de diretório e a ordem das 8 colunas em `dataset.py` eram
"documentados publicamente, não conferidos". Conferidos agora contra a
página oficial da UFRJ:

- **Nomes de diretório: batem.** Os 6 tarballs distribuídos são `normal`,
  `horizontal-misalignment`, `vertical-misalignment`, `imbalance`,
  `underhang` e `overhang` — exatamente as chaves de `MAFAULDA_FAULT_DIRS`.
- **Ordem das colunas: bate.** Tacômetro, acelerômetro underhang (axial,
  radial, tangencial), acelerômetro overhang (axial, radial, tangencial),
  microfone.
- **Volume:** 1951 arquivos, 13,0 GB, janelas de 5 s a 50 kHz (250.000
  linhas por arquivo).

O TODO correspondente foi removido. O do CWRU foi **afiado** em vez de
removido: o download oficial entrega .mat soltos e numerados, sem estrutura
de pastas — a condição de cada ensaio está numa tabela do site. É preciso
organizar em `normal/`, `ir/`, `or/`, `b/` antes de carregar, e
`cwru_label_from_path` falha alto até que isso seja feito.

### Composição do MAFAULDA e o que ela implica

| Classe | Arquivos |
|---|---|
| Normal | 49 |
| Imbalance | 333 |
| Horizontal misalignment | 197 |
| Vertical misalignment | 301 |
| Underhang bearing | 558 |
| Overhang bearing | 513 |

Dois pontos que afetam o planejamento:

1. **Só 49 arquivos normais.** Como o Isolation Forest treina apenas sobre
   operação normal, o conjunto de treino inteiro sai desses 49 → ~441
   janelas de 512 amostras. Suficiente, mas modesto, e é o que limita o
   `GroupKFold` (49 grupos).
2. **56% das anomalias (1071 de 1902) são falha de rolamento.** É
   exatamente a classe que o item 1 mostra ficar fora do alcance do
   MPU6050: depois de decimar para 1 kHz, a ressonância de 3–10 kHz que
   carrega a assinatura do defeito já foi descartada. Esperar bom
   desempenho nessas classes contradiz a própria análise do projeto — o
   desempenho útil deve vir de imbalance e misalignment (831 arquivos).

### Primeiro treino em dados reais (parcial — 4 de 6 classes)

880 arquivos do MAFAULDA (normal, imbalance, horizontal- e
vertical-misalignment) → 7920 janelas. Underhang/overhang ainda baixando.

**O pipeline funciona.** Falso alarme medido de 1,8% ± 3,0% contra alvo de
1% — a calibração por quantil faz o que promete. `GroupKFold` por arquivo,
5 folds.

**O modelo não.** Detecção de 11,7% ± 16,1% no ponto de operação:

| Classe | Detecção @ 1% FA |
|---|---|
| horizontal-misalignment | 3,8% ± 3,8% |
| vertical-misalignment | 8,6% ± 8,5% |
| imbalance | 19,3% ± 30,3% |

AUC global 0,795 ± 0,040, pAUC (FPR≤10%) 0,665 ± 0,099. A distância entre
as duas confirma em dado real a crítica A1: a AUC global sugere um detector
razoável, e no ponto de operação que importa ele não é.

### Duas causas identificadas, ambas anteriores ao modelo

**1. O vetor de 4 features não separa desalinhamento de normal.** Medianas:

| Classe | rms | kurtosis | crest | dom. freq |
|---|---|---|---|---|
| normal | 0,177 | −0,155 | 3,11 | 46,9 |
| horizontal-misalignment | 0,174 | −0,115 | 3,11 | 48,8 |
| vertical-misalignment | 0,171 | 0,034 | 3,23 | 50,8 |
| imbalance | 0,607 | −1,310 | 2,00 | 41,0 |

Desalinhamento é indistinguível de normal nas quatro features — o RMS é até
levemente menor. Só imbalance separa, por amplitude. Entre 64% e 92% das
janelas anômalas caem dentro da faixa p1–p99 dos normais em cada feature.

**2. `dominant_freq_hz` mede a ressonância da bancada, não a falha.** A
correlação com a rotação real do ensaio (que o MAFAULDA codifica no nome do
arquivo) é **−0,018**. Investigando o espectro:

```
rot 12,3 Hz | pico ACELERAÇÃO 117,2 Hz | pico VELOCIDADE (10-500 Hz) 11,7 Hz
rot 13,9 Hz | pico ACELERAÇÃO 117,2 Hz | pico VELOCIDADE (10-500 Hz) 27,3 Hz
```

O pico de aceleração fica em 117,2 Hz independente da rotação: é um modo
estrutural do MFS. Como aceleração escala com ω², o espectro de aceleração
é sempre dominado pelo conteúdo de alta frequência, e a linha de 1× rotação
— que é a assinatura de desbalanceamento e desalinhamento — fica soterrada.
No espectro de **velocidade** com a banda 10–500 Hz, o pico cai sobre 1×
rotação, com 86–100% da energia do pico.

**Consequência para o firmware:** `dominant_frequency()` em
`lib/signal_processing/` deveria operar sobre o espectro de velocidade
band-limitado, não sobre a aceleração crua. A FFT já é calculada; falta
dividir por 2πf e aplicar a máscara de banda — o mesmo método que o item 2
já validou para a rotulagem ISO. É barato e provavelmente a mudança de
maior retorno no dispositivo.

### Classe de máquina ISO: o default está errado para esta bancada

Velocidade RMS mediana da operação **normal** real: 4,74 mm/s.

| Classe assumida | Corte B/C | % dos normais reais marcados anômalos |
|---|---|---|
| **I** (default do `train.py`) | 1,80 mm/s | **93,4%** |
| II | 2,80 mm/s | 76,4% |
| III | 4,50 mm/s | 54,6% |
| IV | 7,10 mm/s | 2,0% |

O código antigo derivava o rótulo *da* ISO: teria treinado em ~29 janelas
sobreviventes, em silêncio, e exportado um modelo sem sentido. A mudança
para rótulo-do-caminho como verdade evitou exatamente isso.

Encaminhamento: **não usar o MAFAULDA para calibrar limiar de zona ISO.**
A bancada SpectraQuest opera mais áspera do que a norma admite para classe
I, e nenhuma das quatro classes descreve bem um simulador de laboratório.
Essa calibração depende da medição na Skala — item 3 dos questionamentos.

### Corrigido — `dominant_frequency` passa a medir velocidade band-limitada

Implementado nos dois lados (`lib/signal_processing/signal_processing.cpp` e
`training/kaelix_ml/features.py`), com a paridade preservada.

A frequência dominante era extraída do espectro de **aceleração** cru. Como
aceleração escala com ω², esse espectro é sempre dominado pelo conteúdo de
alta frequência — no MAFAULDA, um modo estrutural da bancada em 117 Hz,
idêntico com máquina sadia ou defeituosa. A feature carregava a assinatura
da montagem, não da falha.

Agora a magnitude é reponderada por `|V(f)| = |A(f)|/(2πf)` e a busca fica
restrita a 10–1000 Hz. A fase é irrelevante para escolher o bin de pico, então
não é preciso integrar o sinal — só reponderar o espectro que a FFT já produz.
Custo no firmware: uma divisão por bin. O limite inferior da banda **não é
cosmético**: sem ele a ponderação 1/f faria o bin mais baixo vencer sempre.

**Resultado, mesmos 880 arquivos e mesmo protocolo:**

| Métrica | Antes | Depois |
|---|---|---|
| Detecção @ 1% FA alvo | 11,7% ± 16,1% | **38,5% ± 8,5%** |
| F1 | 0,178 ± 0,223 | **0,550 ± 0,083** |
| pAUC (FPR≤10%) | 0,665 ± 0,099 | **0,702 ± 0,047** |
| AUC global | 0,795 | 0,805 |
| Falso alarme medido | 1,8% ± 3,0% | 3,6% ± 2,9% |

| Classe | Antes | Depois |
|---|---|---|
| imbalance | 19,3% | **77,5%** |
| vertical-misalignment | 8,6% | 15,1% |
| horizontal-misalignment | 3,8% | 8,3% |

Note que a AUC global quase não se move (0,795 → 0,805) enquanto a detecção
no ponto de operação triplica. É a mesma lição da crítica A1, agora do lado
positivo: a AUC global não teria detectado esta melhoria.

**Verificação de paridade:** comparação numérica direta Python ↔ C++ em 15
casos (10 janelas reais do MAFAULDA + 5 sintéticos adversariais).
`dominant_freq_hz` bate exatamente (divergência 0); as demais features
divergem no máximo 5,1e-06. Testes de regressão espelhados nos dois lados:
9 testes C++ (eram 6), 35 Python (eram 32).

### O que a correção não resolveu

Desalinhamento continua praticamente invisível (8,3% e 15,1%). As quatro
features atuais medem amplitude e forma de onda; a assinatura clássica de
desalinhamento é a **razão entre as linhas de 2× e 1× rotação**, que nenhuma
delas captura. Próximo passo natural: features de energia em banda em torno
de 1× e 2× da rotação — o que exige conhecer a rotação (o MAFAULDA a traz no
tacômetro, coluna 0, hoje não usada; no dispositivo, viria de estimativa
espectral).

O falso alarme subiu de 1,8% para 3,6%, acima do alvo de 1%. Causa provável:
só 49 arquivos normais para dividir entre fit, calibração e validação — a
estimativa de quantil fica ruidosa. É um limite do dataset, não do método.

### Treino completo — 6 classes, 1951 arquivos, 17.559 janelas

Dataset inteiro ingerido: **31 GB de CSV bruto → 32 MB de cache**, bruto
descartado. `GroupKFold` por arquivo, 5 folds, limiar por quantil a 1% de
falso alarme alvo.

| Métrica | Valor |
|---|---|
| Falso alarme medido | 2,0% ± 1,3% |
| Detecção agregada | 42,6% ± 4,4% |
| F1 | 0,596 ± 0,043 |
| AUC global | 0,852 ± 0,022 |
| pAUC (FPR≤10%) | 0,752 ± 0,057 |

### O número agregado é enganoso — e o motivo confirma o item 1

A detecção agregada **subiu** ao acrescentar as classes de rolamento
(38,5% → 42,6%), o que contradiria a previsão do item 1. Investigando: o
MAFAULDA roda os ensaios de falha de rolamento **com massa de
desbalanceamento adicionada**, em quatro níveis (0g, 6g, 20g, 35g), e a
estrutura de diretórios é `overhang/ball_fault/20g/*.csv`.

A detecção acompanha a massa, não o defeito:

| Classe | 0g | 6g | 20g | 35g |
|---|---|---|---|---|
| underhang-bearing | **14,8%** | 46,2% | 82,0% | 87,3% |
| overhang-bearing | **20,7%** | 19,5% | 64,0% | 78,3% |

Na condição 0g — defeito de rolamento puro, sem desbalanceamento
sobreposto — a detecção cai para 14,8% e 20,7%, no mesmo patamar do
desalinhamento. O que o modelo detecta nos arquivos de rolamento é a massa
adicionada, não o defeito.

**Isso confirma o item 1 com dado real**, e acrescenta um alerta
metodológico: reportar "detecção de falha de rolamento: 56%" sem
estratificar pela massa adicionada seria exatamente o tipo de número
inflado que o item 6 e a crítica A2 alertam. O agregado de 42,6% tem o
mesmo problema.

### Quadro honesto do que o dispositivo detecta

| Classe | Detecção @ 2% falso alarme |
|---|---|
| imbalance | **75,0% ± 3,5%** |
| overhang-bearing (0g, puro) | 20,7% |
| underhang-bearing (0g, puro) | 14,8% |
| vertical-misalignment | 7,2% ± 4,3% |
| horizontal-misalignment | 5,0% ± 3,1% |

Só desbalanceamento é detectável de forma útil. Desalinhamento e defeito de
rolamento puro ficam perto do piso.

Para desalinhamento a causa é o vetor de features, não o sensor — a
assinatura é a razão 2×/1× rotação, que RMS, curtose, fator de crista e
frequência dominante não capturam. É corrigível sem trocar hardware.

Para rolamento a causa é a banda, como o item 1 previu por simulação e
estes dados agora confirmam. Não é corrigível por feature nenhuma.

### Consolidado num único repositório

`docs/`, `experiments/` e `figures/` viviam na raiz do workspace, fora do
repositório com remoto (`kaelix-firmware`), num repo git sem nenhum commit.
Todo o trabalho de análise — notebooks, figuras, monografia — estava
efetivamente fora de controle de versão.

Movidos para dentro de `kaelix-firmware/`, junto com `pyproject.toml`,
`uv.lock`, `.python-version` e este CHANGELOG. As três pastas mantiveram a
posição relativa entre si, então as referências cruzadas continuam válidas;
`docs/` foi **fundido** com o `docs/` do firmware (sem colisão de nomes —
`ARQUITETURA.md` convive com os demais).

- `.gitignore` unificado, com `.DS_Store`, caches de Jupyter e R, e os
  datasets brutos. O cache derivado em `data/cache/` (~32 MB) fica
  **versionado de propósito**: torna o treino reproduzível sem rebaixar
  12 GB do MAFAULDA.
- `pyproject.toml` renomeado de `lauan` para `kaelix`.
- Árvore do projeto no README atualizada.
- **Link quebrado corrigido**: `validacao-questionamentos.ipynb` apontava
  para `../docs/questionamentos-tecnicos.md`, que resolvia para
  `experiments/docs/` — quebrado desde antes do move. Agora `../../docs/`.

Verificação: 18 links relativos resolvem, 0 quebrados; `\graphicspath` da
monografia continua achando `figures/output/` e `docs/img/`; 35 testes
Python e 20 C++ passando; `export_thermal_data.py` reproduz os mesmos
44,8 °C documentados.

### Verificação

- `training/tests/`: **32 testes passando** (eram 10), incluindo o
  round-trip real treina → exporta → compila com g++ → compara contra
  `sklearn.score_samples`.
- `pio test -e native`: 17 testes C++ inalterados, revalidados aqui com um
  shim mínimo do Unity (o `pio` não estava instalado na máquina).
- Treino ponta-a-ponta em dados sintéticos: falso alarme 2,0% ± 1,7%
  (alvo 1%), detecção 100% ± 0%, em 5 folds de `GroupKFold`.
- Header exportado com o limiar calibrado (0,665, não mais 0,5 fixo)
  compila limpo com `-Wall -Wextra -Wpedantic` e produz a decisão esperada.
- O placeholder `src/ml/isolation_forest_data.h` (`N_TREES = 0`) foi
  **preservado** — exportar um modelo treinado em dados sintéticos para
  dentro do repositório seria pior que não ter modelo nenhum.

### Pendente (não coberto nesta rodada)

Correções de firmware levantadas na mesma auditoria seguem abertas — ver
`README.md`. As de maior impacto:

- SX1278 nunca entra em sleep; o orçamento de energia não tem termo de LoRa
  idle e o consumo médio real deve ficar ~6,5× acima do estimado.
- `platformio.ini` não declara os 16 MB de flash nem a PSRAM do N16R8.
- `LoraPacket` não tem identificação de dispositivo, e `timestamp = millis()`
  zera a cada deep sleep.
- Retornos de `*_init()` e de `lora_send()` são ignorados em `main.cpp`.
