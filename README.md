# Kaelix

Dispositivo IoT de manutenção preditiva para motores industriais — monitora
vibração e temperatura, roda um modelo de detecção de anomalias embarcado
(TinyML) e transmite o resultado via LoRa. TCC de Engenharia de Software
(ICEV), inspirado na arquitetura do TRACTIAN Smart Trac.

## Montagem atual: C3 como device

A inversão de papéis começa pelo **ESP32-C3 Super Mini como transmissor**,
com MPU e RA-02. Use `esp32-c3-device`, conforme
[ligações e operação](docs/engenharia/c3-device.md). O S3 será migrado para gateway
em uma etapa posterior. O NTC e o circuito de alimentação final ainda não
estão montados. As instruções de S3 abaixo descrevem a montagem anterior.

## Montagem anterior: S3 transmissor (USB, sem NTC)

Use o ambiente **`esp32-s3-bench`** para esta montagem:

```bash
pio run -e esp32-s3-bench -t upload
pio device monitor -e esp32-s3-bench -b 115200
```

Abra o monitor e pressione RESET/EN para acompanhar desde o início. O ambiente
`esp32-s3` continua com NTC e deep sleep de 12 minutos; não é a configuração
adequada para a montagem atual.

O ambiente de bancada habilita `ARDUINO_USB_CDC_ON_BOOT=1`: as mensagens
`[kaelix]` de `Serial` saem pelo USB Serial/JTAG nativo do S3. Sem essa
opção, `Serial` usa UART0; ver apenas logs internos como `i2cInit()` no USB
não demonstra que a execução parou no I²C. Se usar um conversor USB–UART,
os logs da aplicação devem ser acompanhados no USB nativo nesta configuração.

Os logs da aplicação no S3 e no C3 incluem tempo desde o boot e marcadores:
`[+00:00:12.345][gateway][INFO][RX] RX ... crc=OK`.
Os níveis são `INFO`, `DEBUG`, `WARN` e `ERROR`; os eventos identificam
`BOOT`, `CONFIG`, `PHASE`, `IMU`, `MEASURE`, `RADIO`, `TX`, `RX`, `IRQ`,
`HEALTH`, `SPI`, `REJECT` e `CYCLE`. O prefixo `+` indica tempo de execução,
não horário civil: cada placa tem sua própria origem, reiniciada no boot.
Para carimbar com o horário do computador e salvar o ensaio, use os filtros
`-f time -f log2file` no monitor. O diagnóstico bruto RadioLib está desativado
por padrão no ambiente de bancada; pode ser reativado pelos flags
`RADIOLIB_DEBUG_BASIC` e `RADIOLIB_DEBUG_SPI` em `platformio.ini`.

O driver aceita MPU6050 (`WHO_AM_I=0x68`) e MPU6515 (`0x74`). A placa
conectada devolveu `0x74`, compatível com MPU6515; confirmar a marcação física
antes de atualizar o hardware do TCC. O perfil MPU6515 usa `ACCEL_CONFIG2`
e FIFO de 512 bytes, conforme o [driver do Linux](https://github.com/torvalds/linux/blob/master/drivers/iio/imu/inv_mpu6050/inv_mpu_core.c).

A bancada lê 512 amostras do eixo Z pelo FIFO, drenado continuamente, com relógio de
1 kHz, escala ±4 g e DLPF de 184 Hz. Aceleração em **g**, com a média da
janela removida (gravidade/bias), e estimativa de taxa por observação do FIFO.
Essa estimativa não substitui uma medição com instrumento externo. A janela
é descartada em erro de I2C, timeout, overflow, clipping ou desvio de taxa >2%.
Posicione o eixo Z na direção de vibração que deseja observar. A filtragem
reduz conteúdo de alta frequência; a banda útil não corresponde a 0–500 Hz
com resposta plana e precisa ser considerada na validação do modelo.

O log mostra `vib_init`, `vib_read`, taxa, média de Z e os quatro indicadores.
O pacote mantém temperatura `NaN`, estado `UNKNOWN` e sequência por ciclo.
O modelo não é executado na bancada: unidade em g é compatível com o pipeline,
mas resposta do sensor, montagem e remoção da média precisam ser validadas
antes de tratar o modelo MAFAULDA como diagnóstico desse motor.

O LoRa usa SCK=12, MISO=13, MOSI=11, CS=10, RESET=21 e DIO0=14, SPI a
100 kHz e potência de bancada de 2 dBm. Cada ciclo transmite uma vez, coloca
o rádio em sono e espera 10 segundos, sem deep sleep nem controle do GPIO5.
Mantenha a antena conectada. `lora raw_spi_100k` mostra a leitura direta de RegVersion a 100 kHz para
comparação com o RadioLib; a versão esperada do SX1278 é `0x12`.
`radiolib begin=` e `radiolib tx=` mostram o
retorno original; **`tx=-16` significa que a leitura de um registrador não
correspondeu ao valor escrito**, não uma prova de ausência total de SPI.
O ambiente de bancada habilita `RADIOLIB_DEBUG_BASIC/SPI` para mostrar
o endereço, valor escrito e valor lido quando uma verificação falha.
Esses logs alteram o tempo de execução e servem somente ao diagnóstico.
`tx=0` indica conclusão local; a recepção exige outro rádio compatível.

## Receptor no ESP32-C3 Super Mini

O segundo RA-02 pode receber os pacotes do S3 usando o ambiente
`esp32-c3-receiver`. Ligações, gravação e saída esperada estão em
[src/receiver/README.md](src/receiver/README.md). Esse receptor valida o
pacote v2 de 21 bytes; o gateway Python antigo usa outro formato.

## Diagnóstico isolado do LoRa

Se a versão continuar `0x00`, use o firmware de leitura isolada:

```bash
pio run -e lora-probe -t upload
pio device monitor -e lora-probe -b 115200
```

Pressione RESET/EN com o monitor aberto. Esse ambiente não executa RadioLib,
I2C, modelo nem transmissão. Lê RegVersion por GPIO (SPI por software,
modo 0) e por uma instância FSPI a 100 kHz e 1 MHz. Também confere se o
periférico SPI foi inicializado. A versão esperada é `0x12`.
Se GPIO funciona e hardware SPI falha, investigar configuração/periférico SPI;
se ambos funcionam, investigar integração com o restante do firmware.
Se ambos falham, os resultados ainda exigem conferir os sinais, alimentação,
reset e identificação física do módulo; não comprovam defeito do rádio.
Volte à bancada enviando `esp32-s3-bench` após o diagnóstico.

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
| I2C (MPU6050) | SDA=8, SCL=9 | explícitos no driver; AD0 em GND (`0x68`) |
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
MPU6050 e SX1278 conectados em bancada; NTC ainda ausente.

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

O *porquê* das escolhas não óbvias (lógica separada do hardware, FFT própria, Isolation
Forest nativo, protocolo de treino, temperatura, LoRa, deep sleep e orçamento de energia)
está em [docs/engenharia/decisoes-arquitetura.md](docs/engenharia/decisoes-arquitetura.md).

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
| Leitura I2C real do MPU6050 + DLPF | 🟡 Implementada com FIFO; validação física pendente |
| Calibração física, consumo real, alcance LoRa | ⬜ Pendente; alcance exige receptor |

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
├── platformio.ini      # ambientes de firmware (S3, C3, receptor, diagnóstico) e native (testes)
├── pyproject.toml      # ambiente Python único: treino, figuras, notebooks e testes
│
├── src/                # camada que fala com o hardware
│   ├── main.cpp          # ciclo principal do transmissor
│   ├── device_pins.h     # pinagem do transmissor, por placa
│   ├── sensors/          # vibração (I2C/FIFO) e temperatura (ADC)
│   ├── ml/               # integração do modelo de detecção de anomalias
│   ├── comms/            # empacotamento e envio LoRa
│   ├── power/            # deep sleep, corte de energia e watchdog
│   ├── receiver/         # receptor LoRa e envio por Wi-Fi (firmware à parte)
│   └── diagnostics/      # sonda isolada do RA-02 (firmware à parte)
├── lib/                # lógica pura, sem Arduino, testável em `native`
│   ├── signal_processing/  # RMS, curtose, fator de crista, FFT
│   ├── thermistor/         # conversão mV → resistência → °C
│   ├── isolation_forest/   # inferência do modelo de anomalia
│   ├── crc16/              # integridade do pacote LoRa
│   └── kaelix_status/      # códigos de status compartilhados
├── include/            # configuração do gateway (o arquivo local fica fora do git)
├── test/               # testes unitários do firmware (PlatformIO + Unity)
├── wokwi/              # simulação (ESP32-S3 + MPU6050)
├── logs/               # registros seriais dos ensaios de bancada
│
├── training/           # pipeline Python de treino do modelo
│   ├── kaelix_ml/        # ingestão, features, rotulagem, treino, export C++
│   └── tests/            # testes do pipeline (pytest)
├── tools/              # verificação reproduzível e análise estática
├── data/               # datasets: brutos ignorados, cache derivado versionado
│
├── docs/
│   ├── TCC/              # monografia (LaTeX; `make` gera build/main.pdf)
│   ├── relatorios/       # relatórios técnicos de origem (LaTeX)
│   ├── engenharia/       # arquitetura, decisões, falhas, norma de codificação, rastreabilidade, referências
│   ├── guias/            # guias de escrita
│   ├── contracts/        # contratos JSON da API do gateway
│   └── img/
├── experiments/
│   ├── figures/          # figuras em padrão de submissão
│   │   ├── scripts/        # exportadores Python + plot em R (ggplot2)
│   │   ├── data/           # CSVs rastreáveis
│   │   └── output/         # SVG/PDF vetoriais, TIFF 600 dpi
│   ├── notebooks/        # validação numérica (fonte da verdade)
│   ├── gateway/          # simulador do gateway e seus testes
│   └── verificacao-lean/ # verificação formal em Lean 4
└── hardware/           # placas, invólucro e análises (trabalho futuro no TCC)
    ├── scripts/          # geradores e análises; o que está nas outras pastas sai deles
    ├── pcb/              # versões v1 a v3
    ├── involucro/        # versões v1 a v3
    ├── fem/              # elementos finitos (malhas fora do git)
    └── 3dmodels/
```

`docs/relatorios/` contém cinco documentos: o relatório de simulação da cadeia de
medição, a revisão de literatura, a análise de comunicação e topologia, a verificação
do hardware e a tabela de práticas de tolerância a falhas em sistemas embarcados
críticos (`praticas-sistemas-criticos.tex`: redundância aviônica, normas de garantia e
o que o Kaelix adota, não adota e por quê).

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
| `tools/run-native-tests.sh` | 176 (85 em dev, 91 em prod) | `lib/` e a lógica de `src/` que compila no host |
| `training/tests/` | 35 | pipeline de treino, paridade C++↔Python |
| `experiments/gateway/tests/` | 19 | pacote, receptor, cadeia simulada |

`test_vibration`, `test_packet_decode`, `test_gateway_delivery` e `test_remote_logs`
incluem arquivos de `src/`. O restante da camada, que fala com o hardware, depende de
`pio run` e do ensaio em bancada.

## Pipeline de treino

```bash
uv sync                                   # ambiente único, definido em pyproject.toml
cd training
uv run python -m pytest tests/            # 35 testes, inclui compilação real com g++
uv run python -m kaelix_ml.ingest --all   # baixa o MAFAULDA e cacheia (~12GB -> 32MB)
uv run python -m kaelix_ml.train          # treina e exporta o header C++
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

- **Gateway uma versão atrás do firmware.** `experiments/gateway/kaelix_gateway/packet.py` fixa
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

## Licença

O código está sob a licença MIT ([LICENSE](LICENSE)). Os dados e os
resultados das análises estão sob a licença Creative Commons Atribuição 4.0
Internacional ([LICENSE-DADOS](LICENSE-DADOS)):

- `experiments/campo/dados/`: dados da coleta em campo de 2 de novembro de 2026;
- `experiments/campo/analise_registrada/`, `analise_descritiva/`,
  `analise_posterior/` e `analise_posterior_v4/`: resultados das análises da
  coleta;
- `experiments/fraunhofer/analise_registrada/`: descritores e resultados
  derivados da base pública da Fraunhofer, também CC BY 4.0; a atribuição e as
  modificações estão em `LICENSE-DADOS`;
- `docs/monografia/registro/`: registro das hipóteses e das emendas.

Mantêm a licença de origem:

- `docs/monografia/latex/abntex2-alf-2025.bst`: cópia modificada de
  `abntex2-alf.bst`, do abnTeX2, sob a LaTeX Project Public License 1.3 ou
  posterior;
- `docs/monografia/latex/imagens/logo-icev.jpg` e
  `docs/monografia/latex/preambulo/estilo-icev.tex`: logo e estilo do modelo de
  monografia do iCEV, que pertencem à instituição.
