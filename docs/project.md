# O que é o Kaelix

Dispositivo IoT de baixo custo para manutenção preventiva de motores industriais. Mede vibração e temperatura, roda detecção de anomalias por TinyML diretamente no dispositivo (edge computing, sem depender da nuvem para a decisão) e transmite os dados via LoRa para um gateway.

É desenvolvido tendo como referência de mercado o TRACTIAN Smart Trac, e será validado em equipamentos reais da Skala Metalurgia, onde perfiladeiras, compressores, dobradeiras, guilhotinas, ventiladores industriais e calandras estão disponíveis para testes.

## Arquitetura

**Sensoriamento:** vibração (MPU6050, acelerômetro + giroscópio) e temperatura (termistor NTC 10k, equação de Steinhart-Hart).

**Processamento:** ESP32-S3-WROOM-1 N16R8. Extração de descritores (RMS, curtose, fator de crista, FFT) e inferência do Isolation Forest embarcados em C++ nativo.

**Comunicação:** LoRa 433 MHz (módulo RA-02 / SX1278), escolhido em vez de Wi-Fi por robustez a interferência e alcance em ambiente industrial.

**Energia:** bateria LiPo 2000 mAh, deep sleep com corte de alimentação por transistor BC337, recarga por USB-C IP67 sem necessidade de abrir o invólucro. Consumo médio estimado de ~346 µA, autonomia de ~241 dias — ver o orçamento em [ARQUITETURA.md](ARQUITETURA.md).

**Fixação:** base magnética (ímãs N42SH / N35UH, 150 °C), não destrutiva, permite remover o dispositivo para recarga e manutenção.

**Invólucro:** ASA impresso em 3D, geometria comparável ao TRACTIAN Smart Trac, 3 peças — corpo, tampa e base.

## Pendências críticas

**Dados reais de falha:** modelo de ML validado apenas com dados sintéticos. Falta baixar e validar o layout dos datasets MAFAULDA (UFRJ) e CWRU Bearing Dataset contra os loaders implementados.

**Norma ISO 10816-3:** os limiares de severidade (zonas A–D) usados na rotulagem vêm da literatura, ainda não confrontados com o texto oficial da norma nem com a classe real dos motores da Skala.

Ver também: [Questionamentos técnicos](questionamentos-tecnicos.md).
