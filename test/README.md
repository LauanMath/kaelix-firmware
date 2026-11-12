Testes unitários (PlatformIO + Unity, ambiente `native`) da lógica pura em
`lib/`, que não depende de hardware: `signal_processing` (RMS, curtose,
fator de crista, frequência dominante), `thermistor` (ADC/mV → resistência
→ °C), `isolation_forest` (c(n), caminho de árvore, score) e `crc16`
(integridade do pacote LoRa).

Rodar com: `pio test -e native`.

`test_vibration` verifica a integração dos indicadores em uma janela de
aceleração em g e garante que janelas congeladas/não finitas não publiquem
features. Esses testes não validam o I2C/FIFO na placa.

Os testes do pipeline Python de treino ficam em `training/tests/`
(`uv run python -m pytest tests/`).
