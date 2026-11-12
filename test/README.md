Testes do *firmware* no computador, sem os dispositivos, com o PlatformIO e o
Unity (ambiente `native`). As sete suítes somam 64 casos:

- `test_protocol`: mensagens do protocolo de rádio v3 (`lib/kaelix_protocol/`),
  validação da configuração, fragmentos da rajada, tempo no ar, rotina de
  medição e perda do enlace;
- `test_gateway_v3`: registros que o *gateway* envia à API, configuração
  recebida da API e repasse ao transmissor (`src/gateway/records.h`);
- `test_spool`: gravador em *flash* do *gateway* (`src/gateway/spool.h`):
  ordem dos registros, confirmação, reinício, queda de energia, dado
  corrompido e capacidade;
- `test_remote_logs`: *buffer* de logs do *gateway*
  (`src/receiver/log_buffer.h`);
- `test_crc16`: CRC dos pacotes de rádio (`lib/crc16/`);
- `test_signal_processing`: RMS, curtose, fator de crista e frequência
  dominante (`lib/signal_processing/`);
- `test_vibration`: indicadores de uma janela de aceleração em g e descarte de
  janelas congeladas ou com valores não finitos (`src/sensors/vibration.cpp`).
  A suíte não testa o I2C nem a FIFO do sensor na placa.

Rodar com `pio test -e native`.
