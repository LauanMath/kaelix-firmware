Testes unitários (PlatformIO + Unity, ambiente `native`) da lógica pura em
`lib/`, que não depende de hardware: `signal_processing` (RMS, curtose,
fator de crista, frequência dominante), `thermistor` (ADC/mV → resistência
→ °C), `isolation_forest` (c(n), caminho de árvore, score) e `crc16`
(integridade do pacote LoRa).

Rodar com: `pio test -e native` — 26 testes.

Os testes do pipeline Python de treino ficam em `training/tests/`
(`python -m pytest tests/`).
