# Changelog

Registro das mudanças do projeto Kaelix. Formato baseado em
[Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).

## [Não publicado]

## Placa v3: a bateria passa a ser carregável

Até a v2 a placa **não tinha como carregar a célula**: nenhum CI carregador,
nenhum conector de entrada. O invólucro tinha o furo de USB-C, os relatórios
falavam em "recarga por USB-C", a análise térmica inteira raciocinava sobre o
limite de 45 °C *de carga* — e a netlist não tinha nada disso. O achado veio
da auditoria do TCC (defeito 19 do `verificacao-hardware`, enterrado entre
ângulo de pad e rabicho de antena).

A correção é uma **v3**, e não uma mudança na v2: a v2 é revisão mecânica por
regra (`hardware/pcb/README.md`), e circuito novo em versão velha tornaria
impossível atribuir diferença medida. v1 e v2 mantêm o esquemático byte a byte.

| Peça | Função |
|---|---|
| U5 BQ21040 | carregador linear de uma célula; pino TS suspende a carga fora de 0–45 °C |
| RT2 NTC 10k β 3380 | sensor do TS, na face de cima, sob a célula e longe do U5 |
| R13 2k7 | I_carga = 540 / 2,7 k = **200 mA** |
| J3 USB-C só energia, R11/R12 5k1 | entrada de 5 V; Rd em CC1/CC2 para fonte C-para-C |
| C13, C14, C15 | entrada, saída e filtro do TS |
| IO7 ← CHG_N | estado da carga para o firmware (nenhum código lê ainda) |

**Por que BQ21040.** Único entre BQ21040, TP4056 e MCP73831 com monitor de
temperatura da célula pronto para NTC de 10 k. O limite de 45 °C deixa de ser
recomendação da folha de dados da célula e passa a ser imposto pelo hardware.
O RT1 existente (B3950) não serve: os limiares do CI são calibrados para
β ≈ 3370, e com B3950 o corte cairia perto de 39 °C.

**Por que 200 mA — do modelo térmico, não de regra de bolso.** O carregador
é linear e dissipa I·(V_USB − V_bat) dentro do invólucro fechado. Novo
`hardware/termica_carga.py` roda o FEM de `termica.py` com essa fonte interna
(helpers extraídos para `termica_base.py`, saída de `termica.py` inalterada):
a placa sobe **~15 K/W**.

| 200 mA, 0,41 W | placa | folga até o corte |
|---|---|---|
| fora do motor | 36,7 °C | 8,3 K |
| motor a 90 °C | 41,1 – 44,3 °C | 0,7 – 3,9 K, **otimista** |

A 500 mA o TS cortaria nos três cenários. A folga do motor quente é otimista
porque a troca interna usa o h externo; ali ela pode ser nula. Procedimento
recomendado: carregar fora do motor ou com ele parado.

### A conclusão térmica muda — e já estava errada antes da carga

`relatorio-kaelix` concluía que "a bateria atinge 45 °C com a carcaça em torno
de 81 °C". Esse número vinha do modelo concentrado **que não convergia**
(44,8 °C a 80 °C); a correção (33,0 °C convergido; placa a 38,3 °C a 90 °C no
FEM) estava registrada no `verificacao-hardware` e nunca chegou ao texto nem à
figura 4. Reescrito: em operação nenhum limite é atingido até 90 °C de
carcaça; o limite de 45 °C restringe **só durante a carga**. A figura 4 segue
mostrando o valor não convergido, agora declarado na legenda — refazê-la mexe
no notebook de origem.

### Defeitos de gerador achados no caminho

- **Pino passante não era obstáculo na face oposta** (`gen_pcb.py`). Só furo
  de fixação era. Os pinos de carcaça do USB-C caíam sob U5, R13 e C14: 3
  `pth_inside_courtyard` no DRC. Regra estendida a pad ≥ 0,8 mm; as vias
  térmicas de 0,6 mm do WROOM-1U seguem de fora, como antes.
- **O roteador contava como plano a faixa entre as fileiras de um QFN**
  (`router.py`). O escape de GND do U2.1 terminava numa ilha sob o MPU6050 e
  o DRC acusava grupo solto. Agora o plano não conta como caminho sob o corpo
  de peça de passo fino. **Mudou o roteamento da v1 e da v2** (costura 92 → 71
  e 261 → 234), sem tocar em circuito nem placement; as três passam com DRC
  limpo.
- **Os furos de USB-C e SMA nunca foram cortados** (`gen_involucro.py`). O
  cilindro começava em −cx, a largura externa inteira, e ficava fora do corpo.
  O defeito "furo USB-C sem conector" descrevia um furo que só existia no
  desenho. Corrigido; os corpos v1 e v2 perdem 0,58 cm³. **Os resultados
  modais e térmicos de `hardware/fem/` foram calculados sem os furos** e não
  foram refeitos (~1,7% da parede).
- **Peça de borda.** O corpo do USB-C passa da borda da placa por projeto.
  `gen_pcb.py` confere o encaixe pelos pads e exige a linha "PCB Edge" do
  footprint sobre a borda (desvio 0,000 mm); `check_3d.py` aceita a passagem
  só no lado −X; `gen_involucro.py` mede a altura do conector no `.step` da
  placa e põe o furo ali (15,73 mm, contra 21,50 arbitrados).

### Não verificado

Modal, PDN e vibração não foram recalculados para a v3. O NTC do TS lê a
placa, não a célula. Célula invertida com USB ligado injeta a pré-carga
(falha dupla; conector polarizado). Sem TVS no VBUS. Tudo acima é modelo,
nenhuma medição.

## Correções de documentação: norma, procedência, referências e TCC

Entrada que faltou nos commits de 17/09/2026.

- **ISO 20816-3.** Os relatórios chamavam de "a norma" a ISO 10816-3:2009,
  retirada. Os valores de zona são idênticos; muda a rastreabilidade da
  citação. A banda passou a ser enunciada como requisito de instrumento ("ao
  menos 10–1000 Hz"), que é o que sustenta a conclusão de não conformidade.
- **Procedência.** Três resultados próprios da revisão eram apresentados como
  medidos no MAFAULDA e vêm de sinal sintetizado: o par 413×/20×, a queda de
  pAUC de 16,2% contra 3,7% e o falso alarme de ~42% com
  `contamination='auto'`. Todos no único documento que mistura procedências.
- **`docs/relatorio/referencias.bib`**, fonte canônica: 55 chaves, 53 obras;
  nas 5 divergentes vence a versão auditada.
- **Figuras** em Times, com cores de série de contraste ≥ 3:1.
- **TCC** em `docs/assembly_tcc_mount/`, consumindo o `.bib` e as figuras
  sem cópia.

## Período do ciclo para 12 minutos: REQ-PWR-06 atendido

`SLEEP_MINUTES` passou de 10 para 12 (`src/main.cpp:83`).

**Por quê.** `REQ-PWR-06` pede autonomia ≥ 8 meses. A 10 min o projeto entregava
~236 dias (7,7 meses) e o requisito estava em falha — não por medição, mas desde
que os 150 ms estimados de tempo no ar viraram 185 ms calculados para SF9. Das
três saídas possíveis (baixar o alvo, descer para SF8, alongar o período), o
período é a única que fecha o requisito **sem tocar no enlace**.

| | 10 min | 12 min |
|---|---|---|
| Carga por ciclo | 171,96 mA·s | 174,14 mA·s |
| Consumo médio | ~354 µA | **~309 µA** |
| Autonomia | ~236 d (7,7 m) | **~269 d (8,8 m)** |
| REQ-PWR-06 | ❌ | ✅ com ~26 dias de margem |

**Custo:** latência de detecção — uma falha que comece logo após uma transmissão
demora até um período para ser vista. Irrelevante para vibração em motor
industrial, cuja evolução se mede em dias.

**Efeito colateral que vale mais que a economia:** a folga torna **SF10 viável**
(~243 dias, ainda ≥ 8 meses). A 10 min, SF10 dava ~211 dias e a escolha de
alcance ficava travada pelo orçamento de energia — o levantamento de RSSI em
planta agora pode pedir os 2,5 dB extras sem reabrir o requisito. Pelo mesmo
motivo, as três linhas do §7.4 da análise de falhas (pacote de diagnóstico de
36 bytes) passaram a caber no requisito: o custo virou margem consumida, não
conflito.

### Corrigido junto

- **Probabilidade de colisão.** README e `main.cpp` davam 1,5% para 20
  dispositivos e 3,7% para 50. Esses valores correspondem a **226 ms**, o tempo
  no ar em `CR 4/7` — o firmware fixa `CR 4/5`. É a mesma troca de linha já
  encontrada no §7.4. Com 185 ms reais e período de 720 s: **1,0% e 2,5%**.
- **Tabela de SF do README.** Era de 20 bytes e do ciclo de 10 min. Refeita para
  21 bytes, `CR 4/5` e 12 min, com coluna dizendo quais SF atendem REQ-PWR-06.
  SF12 a 21 bytes são 1483 ms, não os 1319 ms da v1.
- **Bloco de orçamento em `src/power/sleep.cpp`.** Ainda descrevia 150 ms de TX,
  600 s de sono e ~346 µA. Reescrito.

## Primeiro build do alvo: WDT-1 corrigido e documentação sincronizada

O `pio run -e esp32-s3` passou a rodar. Ele reprovou de imediato, e o que ele
encontrou motivou esta rodada.

### Corrigido

- **WDT-1 não compilava no ESP32-S3.** `src/power/watchdog.cpp` incluía
  `<soc/rtc_wdt.h>` sob uma guarda `__has_include`. A guarda testava a
  **existência** do cabeçalho, não sua **usabilidade**: no S3 o arquivo está
  presente e referencia `RTC_WDT_STG_SEL_*`, definidos apenas na árvore do ESP32
  original — símbolo nenhum deles existe no SDK do S3. O build do alvo falhava
  com 5 erros, em vez de degradar para `NotImplemented` como a guarda pretendia.
  A proteção falhou exatamente no cenário para o qual foi escrita.

  A implementação passou a usar `hal/wdt_hal.h` (RWDT), portátil entre ESP32, S2,
  S3 e C3 e a mesma via que o ESP-IDF usa no bootloader — o que eliminou o
  condicional por família em vez de acrescentar mais um. A janela é convertida em
  ticks a partir de `rtc_clk_slow_freq_get_hz()`, e não de constante: o
  `RTC_SLOW_CLK` é RC de ~136 kHz ou cristal de 32768 Hz conforme a placa, e uma
  constante fixa faria a janela de 20 s virar 4,8 s ou 83 s sem nenhum sintoma
  além do watchdog agindo na hora errada. `WDT_STAGE_ACTION_RESET_SYSTEM`
  preserva o domínio RTC, onde vive o estado retido — `RESET_RTC` apagaria a
  evidência de instabilidade que o FM-33 existe para preservar.

- **Cabeçalho da imagem declarava 8 MB de flash.** `board_build.flash_size`
  governa só o lado do build; o `elf2image` lê `upload.flash_size`, que o perfil
  da `devkitc-1` fixa em 8 MB. A tabela de partições vai até 16 MB (`app1`
  termina em 12,6 MB; `spiffs`, em 15,6 MB). O app cabe nos primeiros 8 MB, então
  nada quebra hoje; OTA, SPIFFS e coredump quebrariam. Corrigido com
  `board_upload.flash_size`, deliberadamente sem tocar em `maximum_size` — a
  checagem de tamanho tem de continuar valendo contra a partição app0 de 6,25 MB.

- **Erro de conta no §7.4 da análise de falhas.** Os ~363 µA e ~230 dias
  atribuídos ao pacote de 36 bytes pertenciam ao de **21 bytes em CR 4/7**: as
  linhas do cálculo foram trocadas. E a base de comparação (~346 µA, ~241 dias)
  era anterior ao cálculo de tempo no ar em SF9. Recalculado a partir do que o
  firmware transmite (21 B, CR 4/5, 185 ms): 36 bytes custam **12 dias** de
  autonomia mantendo CR 4/5, não 11 contra uma base inexistente.

### Sincronizado com o código

A documentação descrevia um firmware anterior a várias rodadas. Corrigido em
`README.md`, `docs/RASTREABILIDADE.md`, `docs/ANALISE-DE-FALHAS.md` e
`docs/ARQUITETURA-SOFTWARE.md`:

- **Modelo embarcado.** Vários pontos ainda diziam `N_TREES = 0` e "limiar 0,5 é
  placeholder". O header traz 100 árvores e limiar 0,55719777 por quantil de
  calibração. A FMEA chegava a citar `if (N_TREES == 0) return Status::Normal;`,
  código que não existe: a guarda devolve `ModelAbsent` e deixa o veredito em
  `Unknown` — o firmware estava **melhor** do que a própria análise afirmava.
- **Pacote v2.** 21 bytes com `state` ternário e `diag`, não 20 bytes com
  `status` binário.
- **Orçamento de energia.** ~354 µA e ~236 dias (7,8 meses) em toda parte; 346 µA
  e 241 dias eram resíduo da estimativa de 150 ms de tempo no ar. Com isso,
  `REQ-PWR-06` ("autonomia ≥ 8 meses") passou a **não ser atendido pelo próprio
  cálculo de projeto**, e a matriz diz isso.
- **Matriz de rastreabilidade.** `REQ-ML-01` e `REQ-ML-09` estavam marcados como
  falha comprovada e já haviam sido corrigidos — o teste de paridade compila e
  passa, e `export_cpp.py` emite os 8 inicializadores por árvore. Contagens
  refeitas: 13 de 59 plenamente verificados (22,0%), 1 falha ativa restante
  (`REQ-SYS-03`, includes relativos), 4 não implementados.

### Registrado como pendência

- **Gateway uma versão atrás.** `experiments/gateway/packet.py` fixa
  `PACKET_VERSION = 1` e 20 bytes; o firmware emite v2 com 21. O gateway recusaria
  todo pacote real — falha segura, e a guarda de versão funcionando, mas a cadeia
  simulada não corresponde ao dispositivo. Os 19 testes passam porque exercitam o
  gateway contra o próprio `codificar()`: nenhum cruza a fronteira. O byte `diag`
  não tem leitor.
- **Comportamento do WDT-1 não medido.** O build prova que a API é usada
  corretamente e resolve em link; não prova que o contador do RWDT sobrevive ao
  deep sleep, premissa do `REQ-WDT-05` e do despertador de último recurso.

### Conferido contra a peça real

Um ESP32-S3 foi lido com `esptool`: QFN56 rev. v0.2, 16 MB de flash, 8 MB de
PSRAM. Confirma a variante N16R8 que o `platformio.ini` declara — a sobrescrita
do perfil da `devkitc-1` era necessária e está correta.

### Adicionado

- `docs/relatorio/praticas-sistemas-criticos.tex` — tabela de práticas de
  tolerância a falhas em sistemas embarcados críticos (redundância aviônica,
  DO-178C, IEC 61508, ISO 26262, ARINC 653, MISRA C++, JSF++), com origem,
  falha coberta, custo, limite conhecido e situação no Kaelix. Traz declaração de
  nível de conferência por fonte, no espírito de `docs/referencias.md`.

## Reorganização: análise e simulação sob `experiments/`

`figures/` e `gateway/` passaram a viver sob `experiments/`, ao lado de
`notebooks/`. A raiz do repositório fica com o que é firmware (`src/`, `lib/`,
`test/`), o pipeline de treino (`training/`), o ferramental (`tools/`) e a
documentação.

Caminhos reapontados: `\graphicspath` dos três documentos LaTeX, a profundidade
de `parents[]` em `export_gateway_data.py` e em `test_paridade_crc.py`, o runner
de testes, e as árvores de projeto nos READMEs.

**Entradas anteriores deste changelog citam os caminhos antigos** (`figures/scripts/`,
`figures/data/`). Elas descrevem o estado da época e não foram reescritas: um
changelog que reescreve o próprio passado para casar com o presente deixa de
servir como registro.

### Corrigido durante a arrumação

- **Crédito de fotografia sem fotografia.** As legendas da Figura 5, no
  `comunicacao-topologia.tex` e no README de figuras, creditavam imagens de
  componente do Wikimedia Commons. A figura deixou de usá-las quando o painel
  (a) foi refeito como grafo de estrela, e os arquivos não estão mais no
  repositório. Atribuir imagem ausente é erro factual; os créditos saíram.
- **`sys.path.insert` nos testes do gateway.** O `training/` já resolvia o
  import por `conftest.py`; o gateway não seguia o padrão. Passou a seguir, e
  com isso saíram os `# noqa: E402` que existiam só para silenciar o import
  fora de ordem.

### Adicionado

- `experiments/gateway/README.md` — o componente não tinha explicação: por que
  existe separado do nó, o acoplamento com `src/comms/lora.h`, e o que a
  simulação não cobre.
- `tools/run-all-tests.sh` — ponto de entrada único para as três suítes. Havia
  146 casos C++, 35 de treino e 19 de gateway sem forma de rodar juntos, e é
  assim que quebra de integração passa: um refactor em `lib/` que muda
  assinatura aparece no teste C++, mas o gerador Python que consome a mesma
  struct só quebra na suíte de treino. O script termina listando o que não
  cobre — a camada `src/` e qualquer comportamento em hardware.


## Conformidade com práticas de software industrial/aeroespacial

Rodada de reorganização do firmware segundo MISRA C++, JSF++ e os princípios de
determinismo do DO-178C. 19 arquivos alterados, +2027/−254 linhas, 4 módulos novos.
O objetivo não é certificar, é adotar as práticas de organização, determinismo e
rastreabilidade que projetos críticos usam — e poder justificá-las numa defesa.

### Corrigido

- **Alocação dinâmica eliminada.** `dominant_frequency` alocava dois `std::vector` de
  512 floats por chamada — ~4 KB de heap por ciclo, ~35 mil pares malloc/free por ano de
  campo, com falha de alocação não tratada. Substituídos por buffer estático
  `FFT_MAX_N`, com a não reentrância documentada. Proibição de heap após inicialização é
  JSF++ AV-206 e MISRA C++ 18-4-1.

- **Laço sem cota superior.** `isolation_tree_path_length` percorria a árvore com
  `while (tree.feature[node] != -1)`: um array corrompido travava o dispositivo, e não
  havia watchdog para tirá-lo de lá. Virou `for` com cota derivada da profundidade real
  da árvore. O defeito estrutural, porém, era a `struct`: ela não carregava o
  comprimento dos arrays, então nenhuma função conseguia validar índice. Ganhou
  `n_nodes` e `max_depth`.

- **Modelo de erro.** As sete funções que devolviam `bool` passam a devolver
  `kaelix::Status` — 41 valores organizados por faixa de subsistema, para que o gateway
  faça triagem sem tabela completa. Os quatro `false` idênticos de `lora_init()` viraram
  `RadioAbsent`, `RadioBusSilent`, `RadioConfigRejected` e `RadioTxFailed`.

- **Validação de parâmetro** em 9 módulos, via `KAELIX_REQUIRE`/`CHECK`/`ENSURE`. A
  asserção tem dois comportamentos por build: em desenvolvimento aborta com
  arquivo:linha; em produção devolve o status sem travar. A justificativa está no
  header — abortar num dispositivo com 8 meses de bateria numa máquina remota troca um
  bug por um aparelho morto e mudo.

- **Watchdog de dois estágios** (`src/power/watchdog.*`): task WDT na fase ativa, RTC WDT
  como rede de segurança, com rearme distinto para o deep sleep. A alimentação acontece
  entre etapas do ciclo e nunca dentro de laço, para que o watchdog meça progresso e não
  atividade de CPU.

### Adicionado

- `lib/kaelix_status/` — modelo de erro compartilhado, header-only, sem `Arduino.h`.
- `src/machine_state.h` — máquina de estados que materializa o estado seguro.
- `docs/ARQUITETURA-SOFTWARE.md` — camadas, convenções, políticas de memória e erro,
  estado seguro, registro de desvios. Recomenda **não** construir uma camada HAL, e
  argumenta dos dois lados.
- `docs/ANALISE-DE-FALHAS.md` — FMEA com 36 modos de falha, classes de severidade e
  detectabilidade, matriz de criticidade (em vez de RPN com números inventados),
  política de watchdog e telemetria.
- `docs/NORMA-DE-CODIFICACAO.md` — regras selecionadas de MISRA/JSF++ com exemplo certo
  e errado tirados do próprio código, mais uma seção de desvios assumidos.
- `docs/RASTREABILIDADE.md` — matriz requisito → código → teste, com a coluna de não
  verificados explícita.
- `.clang-tidy`, `.clang-format`, `tools/run-native-tests.sh`, `tools/run-static-analysis.sh`.
  O runner roda cada suíte nos **dois modos de build**, porque a asserção se comporta
  diferente em cada um: 146 casos.

### Achados da análise de falhas que não estavam na lista original

1. **Dado fabricado transmitido como medição.** `main.cpp` registrava a falha de
   `vibration_init()` e chamava `vibration_read_features()` mesmo assim; o buffer de
   zeros produz RMS=0 e curtose=0, que o modelo lê como `Normal`. Sensor morto virava
   "máquina saudável", com CRC válido.
2. **Falha para o lado inseguro na decisão.** `score > threshold ? Anomalous : Normal` —
   toda comparação com NaN é falsa em IEEE 754, então feature corrompida resultava
   sistematicamente em "sadia".
3. **O clamp do termistor convertia falha de hardware em número plausível**: NTC aberto
   lia −26 °C a −77 °C; em curto, +349 °C. Floats finitos, indistinguíveis de leitura real.
4. **`new Module(...)` é evitável** — a API do RadioLib aceita ponteiro para instância
   existente. O desvio que eu havia classificado como inevitável não era.

### Regressões introduzidas pelo refactor e corrigidas

Três quebras de integração, todas em fronteiras entre áreas de posse diferente:

- Três testes chamavam a FFT com `n = 1024` e um com `n = 4096`, acima do novo
  `FFT_MAX_N = 512`. Reparametrizados mantendo bin de 1 Hz.
- `isolation_forest.h` passou a incluir `kaelix_status.h`, e `test_export_cpp.py`
  compila fora do PlatformIO — faltava o `-I`.
- **A raiz:** a `struct IsolationTree` ganhou dois campos, mas
  `training/kaelix_ml/export_cpp.py` continuava emitindo o inicializador de seis. Com
  `n_nodes = 0`, toda inferência era rejeitada como `ModelMalformed`. O gerador Python é
  parte do mesmo contrato da struct; o acoplamento está agora documentado no cabeçalho
  dele, com guarda que falha alto se a árvore não couber em `int16_t`.

### Verificação

70 testes C++ (eram 26) e 35 Python. Paridade numérica C++↔Python reverificada em janelas
reais do MAFAULDA: divergência máxima **4,2e-06**.

**O firmware não foi compilado.** A camada `src/` passou de 269 para ~700 linhas usando
APIs do ESP-IDF (`esp_task_wdt_reconfigure`, `rtc_wdt_set_stage`, `esp_task_wdt_delete`)
que nunca passaram por compilador, e há código condicional a versão de SDK
(`#if __has_include(<soc/rtc_wdt.h>)`). `pio run -e esp32-s3` é o que fecha esta rodada.

Os três achados de severidade máxima acima ainda **não foram confirmados como
corrigidos**: a fase de reauditoria do workflow terminou por limite de sessão.

---

## Revisão de literatura e auditoria de citações

### Adicionado

- `docs/relatorio/revisao-literatura.tex` — 1472 linhas, 38 referências, todas conferidas
  em fonte primária. Escopo e método com nota de procedência, revisão por eixo, síntese
  (o que a literatura sustenta, o que contesta, o que se conclui) e lacunas.
  **Falta a seção do Eixo 2** (vazamento de dados): o agente redator caiu duas vezes,
  por conexão e por limite de sessão. As 12 referências desse eixo já estão verificadas.

### Corrigido — auditoria de citações

Duas rodadas de auditoria em fonte primária, com placares parecidos: **6 defeitos em 13**
referências do relatório, **18 em 38** da revisão. O levantamento automático original era,
na prática, uma lista de pistas — não uma bibliografia.

No relatório (`relatorio-kaelix.tex`):

- `varejao2025` — **primeiro autor errado**: I. M. S. Varejão, não F. M. Varejão (que é o
  sexto autor). Duas pessoas do mesmo grupo.
- `kolok2025` — três de cinco iniciais erradas.
- `fidali2024` — terceiro autor é J. Ochmann, não M.; título truncado.
- `iso10816` — **norma retirada**, substituída pela ISO 20816-3:2022, e o relatório a
  tratava como vigente em sete lugares. Registrado o status; a prática industrial ainda
  a usa, e é isso que justifica mantê-la. Descoberta também a Amd 1:2017.
- Títulos completos e DOIs acrescentados em cinco entradas.

**Erro factual corrigido no corpo do relatório:** o texto afirmava que Fidali identifica
pico e pico a pico como mais sensíveis *"acima da velocidade eficaz"*. Velocidade eficaz
nunca foi avaliada no estudo — a palavra "velocity" aparece duas vezes no artigo inteiro,
ambas fora do experimento. A comparação real é com aceleração eficaz, curtose e fator de
crista. A distorção tinha consequência: o parágrafo seguinte trata da velocidade eficaz
normativa da ISO, e o texto criava a impressão de que Fidali mediu o descritor da norma e
o achou inferior — argumento contra a norma que a própria monografia adota. Corrigido, e
a citação passou de contraste a apoio: os autores preveem exatamente o colapso por
limitação de banda que o projeto mediu.

Achados que atingem material já removido do repositório, registrados porque podem ter
circulado: o protocolo de limiar por distribuição gama no percentil 90 **não é** de
Koizumi et al. 2020 (aparece no baseline do DCASE2022); a redução de 90,25% em falsos
alarmes de Hermansa et al. é do **HDBSCAN**, não do Isolation Forest, que ficou atrás
dele no ranking; e Ma et al. não sustenta que o default do `contamination` equivalha a
sorteio — o artigo diz que o iForest com hiperparâmetros default é baseline difícil de
bater, e `contamination` nem está entre os hiperparâmetros estudados.


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
`docs/questionamentos-tecnicos.md` (removido depois) concluiu
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
  `docs/criticas-da-literatura.md` (removido depois).

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
