Testes unitários (PlatformIO + Unity, ambiente `native`) da lógica pura em
`lib/`, que não depende de hardware: `signal_processing` (RMS, curtose,
fator de crista, FFT), `thermistor` (ADC → resistência → °C) e
`isolation_forest` (c(n), caminho de árvore, score).

Rodar com: `pio test -e native` — 17 testes.

Os testes do pipeline Python de treino ficam em `training/tests/`
(`python -m pytest tests/`).
