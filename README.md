# Kaelix

Dispositivo IoT de manutenção preditiva para motores industriais — monitora
vibração e temperatura, roda um modelo de detecção de anomalias embarcado
(TinyML) e transmite o resultado via LoRa. TCC de Engenharia de Software
(ICEV), inspirado na arquitetura do TRACTIAN Smart Trac.

O hardware físico ainda não foi montado. Todo o firmware e o pipeline de
treino foram desenvolvidos e testados em simulador/dados offline, para que
a integração com o hardware real seja só calibração quando ele chegar.

## Hardware alvo

| Componente | Modelo | Interface |
|---|---|---|
| Microcontrolador | ESP32-S3-WROOM-1 N16R8 | — |
| Acelerômetro/giroscópio | MPU6050 | I2C (endereço 0x68) |
| Temperatura | Termistor NTC 10K (beta 3950) | ADC analógico |
| Rádio | RA-02 (SX1278) LoRa 433MHz | SPI |
| Regulador | HT7333 (LDO 3,3V ultra baixo consumo) | — |
| Corte de energia | BC337 ×2 (desligam MPU6050/periféricos no sleep) | GPIO |

## Status atual

| Frente | Situação |
|---|---|
| Estrutura do firmware (PlatformIO) | ✅ Completa, buildando |
| Processamento de vibração (RMS, curtose, fator de crista, FFT) | ✅ Implementado e testado |
| Leitura I2C real do MPU6050 | ⬜ Bloqueado — precisa do hardware físico |
| Temperatura (NTC + Steinhart-Hart) | ✅ Implementado e testado |
| Deep sleep + corte de energia | ✅ Implementado, consumo estimado em ~270µA médio |
| Comunicação LoRa (RadioLib) | ✅ Implementado, compila; transmissão real não testada |
| Simulação Wokwi | 🟡 Arquivo pronto; verificação visual pendente |
| Pipeline de treino (Isolation Forest) | ✅ Implementado e validado ponta-a-ponta com dados sintéticos |
| Split por ensaio, limiar por falso alarme alvo | ✅ `GroupKFold` + calibração por quantil (itens 6 e 7) |
| Alinhamento treino ↔ inferência (1 kHz, 512 amostras) | ✅ `dataset.to_device_windows` |
| Treino com dados reais (MAFAULDA/CWRU) | ⬜ Bloqueado — datasets ainda não anexados em `data/` |
| Calibração física, consumo real, alcance LoRa | ⬜ Bloqueado — precisa do hardware físico |

Ver detalhes de cada decisão técnica em [docs/ARQUITETURA.md](docs/ARQUITETURA.md),
os pontos em aberto em [docs/questionamentos-tecnicos.md](docs/questionamentos-tecnicos.md)
e o histórico de mudanças em [CHANGELOG.md](CHANGELOG.md).

## Estrutura do projeto

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
│   ├── thermistor/         # conversão ADC → resistência → °C
│   └── isolation_forest/   # inferência do modelo de anomalia
├── test/               # testes unitários do firmware (PlatformIO + Unity)
├── wokwi/              # simulação (ESP32-S3 + MPU6050)
│
├── training/           # pipeline Python de treino do modelo
│   ├── kaelix_ml/        # ingestão, features, rotulagem, treino, export C++
│   └── tests/            # testes do pipeline (pytest)
├── data/               # datasets — brutos ignorados, cache derivado versionado
│
├── docs/               # documentação técnica e monografia
│   ├── ARQUITETURA.md            # o porquê de cada decisão do firmware
│   ├── project.md                # visão geral do produto
│   ├── questionamentos-tecnicos.md  # os 8 itens e o que foi verificado
│   ├── criticas-da-literatura.md    # o que a literatura aponta contra
│   ├── referencias.md
│   ├── relatorio/                # monografia (LaTeX + PDF)
│   ├── device/                   # desenho técnico do invólucro
│   └── img/
├── experiments/        # notebooks de validação numérica (fonte da verdade)
│   └── notebooks/
└── figures/            # figuras em padrão de submissão
    ├── scripts/          # exportadores Python + plot em R (ggplot2)
    ├── data/             # CSVs rastreáveis, gerados dos notebooks
    └── output/           # SVG/PDF vetoriais, TIFF 600 dpi
```

## Como rodar

### Firmware (build real para ESP32-S3)

```bash
pio run -e esp32-s3
```

### Testes unitários do firmware (sem hardware, roda no host)

```bash
pio test -e native
```

Cobre `lib/signal_processing`, `lib/thermistor` e `lib/isolation_forest` — 17
testes no total.

### Pipeline de treino (Python)

```bash
cd training
pip install -r requirements.txt
python -m pytest tests/          # 32 testes, incluindo compilação/comparação real com o C++
python -m kaelix_ml.train         # treina e exporta src/ml/isolation_forest_data.h
```

O treino imprime a validação cruzada por ensaio (`GroupKFold`), com média ±
desvio entre folds, e a matriz de concordância entre o rótulo verdadeiro e o
rótulo derivado da ISO 10816-3. Use `--out` para exportar o header a outro
caminho sem sobrescrever o placeholder do repositório.

Sem dados reais em `data/`, o treino cai automaticamente para dados
sintéticos (só para exercitar o pipeline — não é um modelo utilizável).

### Simulação Wokwi

Abrir a pasta do projeto em [wokwi.com](https://wokwi.com) ou pela extensão
do VSCode, usando `wokwi/diagram.json`. Ainda não foi verificado
visualmente neste ambiente de desenvolvimento (sem Node.js/wokwi-cli
disponível).

## Pendências conhecidas

- **Pinos GPIO** (`NTC_ADC_PIN`, `PERIPHERALS_POWER_PIN`, pinos do LoRa) são
  placeholders sem conflito entre si, mas ainda não conferidos contra um
  esquemático final — ajustar quando o hardware for definido.
- **Datasets MAFAULDA/CWRU**: o pipeline já entrega os sinais no domínio do
  firmware (1 kHz, janelas de 512 amostras) e lê o rótulo verdadeiro da
  estrutura de diretórios — mas o layout de colunas/variáveis e os **nomes
  dos diretórios de falha** em `training/kaelix_ml/dataset.py` são os
  documentados publicamente, ainda não conferidos contra os arquivos reais.
  As funções de rótulo **falham alto** em caminho não reconhecido, em vez de
  adivinhar; se o download tiver outra estrutura, ajustar
  `MAFAULDA_FAULT_DIRS` / `CWRU_FAULT_DIRS`.
- **Limiares da ISO 10816-3** (`training/kaelix_ml/labeling.py`): valores
  comumente citados na literatura de engenharia, não conferidos contra o
  texto oficial da norma nem contra a classe real do motor de bancada. A
  integração para velocidade já usa o método validado (frequência, banda
  10–1000 Hz); o que falta são os limiares de zona.
- **Banda ISO só coberta pela metade**: com 1 kHz de amostragem o Nyquist é
  500 Hz, contra os 1000 Hz que a norma exige. Ver item 2 dos
  questionamentos técnicos.
- **Consumo de energia e alcance LoRa**: estimativas teóricas
  (`src/power/sleep.cpp`), a validar com multímetro/INA219 e teste de campo
  quando o hardware físico estiver disponível.
