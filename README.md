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
| Treino com dados reais (MAFAULDA/CWRU) | ⬜ Bloqueado — datasets ainda não anexados em `data/` |
| Calibração física, consumo real, alcance LoRa | ⬜ Bloqueado — precisa do hardware físico |

Ver detalhes de cada decisão técnica em [docs/ARQUITETURA.md](docs/ARQUITETURA.md).

## Estrutura do projeto

```
kaelix-firmware/
├── platformio.ini          # ambientes esp32-s3 (firmware real) e native (testes)
├── src/
│   ├── main.cpp             # ciclo principal
│   ├── sensors/              # vibração (I2C, TODO) e temperatura (ADC)
│   ├── ml/                   # integração do modelo de detecção de anomalias
│   ├── comms/                 # empacotamento e envio LoRa
│   └── power/                  # deep sleep e corte de energia
├── lib/                        # lógica pura, sem dependência de Arduino — testável em `native`
│   ├── signal_processing/       # RMS, curtose, fator de crista, FFT
│   ├── thermistor/                # conversão ADC → resistência → °C
│   └── isolation_forest/           # inferência do modelo de anomalia
├── test/                            # testes unitários (PlatformIO + Unity, ambiente native)
├── training/                         # pipeline Python de treino do modelo (fora do firmware)
│   └── kaelix_ml/
├── data/                               # datasets (MAFAULDA/CWRU) — ainda vazio
├── wokwi/                               # simulação (ESP32-S3 + MPU6050)
└── docs/                                 # documentação técnica detalhada
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
python -m pytest tests/          # 10 testes, incluindo compilação/comparação real com o C++
python -m kaelix_ml.train         # treina e exporta src/ml/isolation_forest_data.h
```

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
- **Datasets MAFAULDA/CWRU**: o layout de colunas/variáveis em
  `training/kaelix_ml/dataset.py` é o documentado publicamente para cada
  dataset, mas não foi conferido contra os arquivos reais.
- **Limiares da ISO 10816-3** (`training/kaelix_ml/labeling.py`): valores
  comumente citados na literatura de engenharia, não conferidos contra o
  texto oficial da norma nem contra a classe real do motor de bancada.
- **Consumo de energia e alcance LoRa**: estimativas teóricas
  (`src/power/sleep.cpp`), a validar com multímetro/INA219 e teste de campo
  quando o hardware físico estiver disponível.
