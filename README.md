# Kaelix

O Kaelix mede a vibração de motores industriais com um transmissor de baixo
custo, fixado na carcaça do motor, que envia o sinal pelo rádio LoRa a um
*gateway* instalado no mesmo local. Este repositório guarda o *firmware* dos
dois dispositivos, os dados da coleta em campo de 2 de novembro de 2026 e as
análises de detecção de falhas feitas com esses dados e com uma base pública de
laboratório. A interface de programação de aplicações (API), o banco de dados e
o aplicativo de mesa que recebem os dados do *gateway* estão no repositório
[kaelix-industrial-intelligence](https://github.com/LauanMath/kaelix-industrial-intelligence).

O sistema foi desenvolvido no trabalho de conclusão de curso de Lauan Matheus
da Rocha Alves, em Engenharia de Software, no Instituto de Ensino Superior
iCEV, em 2026. A monografia está em [`docs/monografia/`](docs/monografia/).

## Sistema

O transmissor usa o microcontrolador ESP32-C3, o módulo MPU-6050, com
acelerômetro e giroscópio de três eixos, e o rádio Ra-02 (circuito SX1278) em
433 MHz. Em cada ciclo de medição, ele adquire uma janela de 512 amostras por
eixo a 1 kHz e envia pelo rádio uma telemetria, com indicadores calculados
sobre a janela e o estado do dispositivo. Quando o *gateway* autoriza, o
transmissor envia também a janela de sinal bruto dos seis canais, dividida em
26 fragmentos, e essa sequência de fragmentos é chamada de rajada. O *gateway*
informa quais fragmentos recebeu, e o transmissor reenvia só os ausentes, em
até três tentativas.

O *gateway* usa o ESP32-S3, com outro rádio Ra-02 e Wi-Fi, e envia os dados à
API por HTTPS, pela rede local. Cada telemetria e cada janela ficam gravadas na
memória *flash* do *gateway* até que a API confirme o recebimento. O
transmissor recebe pelo rádio, por meio do *gateway*, a configuração, a rotina
de medição e os comandos definidos no aplicativo. O *gateway* é configurado
pela rede Wi-Fi própria (`Kaelix-XXXX`) e recebe atualizações de *firmware*
pela rede; o transmissor só recebe *firmware* por cabo.

| Parte | Código | Ambiente do PlatformIO |
|---|---|---|
| Transmissor | `src/transmitter/`, `src/sensors/`, `src/power/` | `kaelix-transmitter` |
| *Gateway* | `src/gateway/`, com a pinagem e o *buffer* de logs de `src/receiver/` | `kaelix-gateway` |
| Protocolo de rádio v3 e CRC | `lib/kaelix_protocol/`, `lib/crc16/` | os dois |
| Processamento de sinal e códigos de estado | `lib/signal_processing/`, `lib/kaelix_status/` | transmissor |

## Compilação e gravação

Os dois ambientes compilam com o PlatformIO, na plataforma `espressif32` com o
*framework* Arduino, e o rádio usa a biblioteca RadioLib 7.7.1:

```bash
pio run -e kaelix-transmitter -t upload --upload-port <porta>
pio run -e kaelix-gateway -t upload --upload-port <porta>
```

O `platformio.ini` é o mesmo que compilou o *firmware* da coleta, em 2 de
novembro de 2026, e não foi editado depois. O resumo SHA-256 dele e dos fontes
do transmissor e do *gateway* identifica essa versão
([`build_sistema_values.py`](docs/monografia/latex/scripts/build_sistema_values.py)).
Por isso, o arquivo ainda declara sete ambientes de versões anteriores
(`esp32-s3`, `esp32-s3-bench`, `lora-probe`, `esp32-s3-gateway`,
`esp32-c3-device`, `esp32-c3-receiver` e `lora-probe-c3`), cujo código foi
removido do repositório. Os ambientes antigos não compilam, e `pio run` sem
`-e` termina com erro ao chegar a eles. O `kaelix-gateway` herda do `esp32-s3`
as configurações da placa.

## Testes

Os testes do *firmware* rodam no computador, sem os dispositivos:

```bash
pio test -e native
```

As sete suítes somam 64 casos e cobrem o protocolo, os registros e o gravador
do *gateway*, o *buffer* de logs, o CRC, o processamento de sinal e a aquisição
de vibração. A saída da execução de 7 de novembro de 2026, sobre o mesmo código
da coleta, está em `experiments/sistema/`.

## Dados e análises

A coleta em campo de 2 de novembro de 2026 mediu quatro máquinas de uma
instalação industrial em operação normal: uma dobradeira, uma guilhotina
hidráulica, uma calandra piramidal e um compressor de parafuso. Os dados foram
exportados do banco da API em modo somente leitura e estão em
`experiments/campo/dados/`. O resumo SHA-256 de `ensaios.csv`, `leituras.csv`,
`janelas.csv` e `janelas.npz` foi gravado no registro das hipóteses antes de
qualquer cálculo
([`registro_v1.md`](docs/monografia/registro/registro_v1.md)). O banco e os
registros dos ensaios ficam fora do repositório, porque trazem nomes de rede e
endereços do local, e por isso os scripts de exportação não rodam a partir
dele.

As hipóteses H1 a H3, avaliadas nos dados de campo, foram registradas em 6 de
novembro de 2026, antes do cálculo. Emendas datadas, também anteriores aos
cálculos que definem, acrescentaram a hipótese H4, avaliada na base pública de
desbalanceamento da Fraunhofer-Gesellschaft, e as análises posteriores AP1 a
AP6 (registros v2 a v4, em [`docs/monografia/registro/`](docs/monografia/registro/)).

| Script | Análise | Saídas |
|---|---|---|
| `experiments/campo/analise_registrada.py` | H1 a H3 | `experiments/campo/analise_registrada/` |
| `experiments/campo/analise_descritiva.py` | ruído do sensor, rotação, espectros, rajadas e resposta a mudanças de condição | `experiments/campo/analise_descritiva/` |
| `experiments/campo/analise_posterior.py` | AP1 e AP2 | `experiments/campo/analise_posterior/` |
| `experiments/fraunhofer/baixar_membros_v2.py` | download dos seis arquivos da base usados em H4, com conferência de CRC-32 e tamanho | `experiments/fraunhofer/dados/v2/`, fora do git |
| `experiments/fraunhofer/analise_h4.py` | H4 | `experiments/fraunhofer/analise_registrada/` |
| `experiments/campo/analise_posterior_v4.py` | AP3 a AP6, com os descritores calculados por `analise_h4.py` | `experiments/campo/analise_posterior_v4/` |

O cabeçalho de cada script traz o comando de execução, com as versões das
bibliotecas, e cada análise grava as versões usadas em `ambiente.json`, junto
com as saídas. Os comandos rodam a partir da raiz do repositório:

```bash
uv run --no-project --with numpy --with scipy --with scikit-learn python experiments/campo/analise_registrada.py
python3 -I experiments/fraunhofer/baixar_membros_v2.py
```

Os seis arquivos da base da Fraunhofer somam cerca de 4 GB. Os números da
monografia não são digitados: scripts gravam macros do LaTeX em
`docs/monografia/latex/values/`, e o
[`README.md` da monografia](docs/monografia/README.md) lista cada script e o
que ele confere. A monografia compila com `make` em `docs/monografia/latex/`,
com saída em `build/main.pdf`.

## Figuras

Os diagramas do sistema são gerados em R, com o tema de
`experiments/figures/scripts/theme_kaelix.R`, por exemplo com
`Rscript experiments/figures/scripts/fig12_implantacao.R`; com `FIG_ANON=1`, o
mesmo script gera a variante `fig12_implantacao_anon`, sem o nome do serviço na
rede local. As figuras com fotos de campo são montadas em Python a partir das
fotos originais, que ficam fora do repositório porque mostram a instalação
industrial. As saídas estão em `experiments/figures/output/`, e as figuras de
resultados da monografia são geradas por `docs/monografia/latex/figuras_src/`.

## Estrutura

```
kaelix-firmware/
├── platformio.ini          ambientes do PlatformIO
├── partitions/             tabela de partições do gateway
├── src/
│   ├── transmitter/        transmissor (ESP32-C3)
│   ├── gateway/            gateway (ESP32-S3)
│   ├── sensors/            aquisição de vibração
│   ├── power/              watchdog
│   └── receiver/           pinagem e buffer de logs usados pelo gateway
├── lib/                    protocolo v3, CRC, processamento de sinal e códigos de estado
├── test/                   testes do firmware no computador (PlatformIO e Unity)
├── tools/                  análise estática e testes sem o PlatformIO
├── experiments/
│   ├── campo/              dados e análises da coleta em campo
│   ├── fraunhofer/         download da base pública e análise de H4
│   ├── sistema/            saída dos testes do firmware de 7 de novembro de 2026
│   └── figures/            diagramas do sistema e fotos de campo
└── docs/monografia/        monografia em LaTeX, registro das hipóteses e auditoria do texto
```

## Estudos anteriores

Até 11 de novembro de 2026, o repositório também guardava o projeto das placas
e do invólucro, a análise térmica, um modelo de detecção embarcado treinado na
base MAFAULDA, versões anteriores do *firmware*, um simulador do enlace, uma
verificação formal em Lean 4 e a versão anterior da monografia. Os estudos
anteriores não entram na monografia atual e foram removidos da árvore de
arquivos, mas continuam no histórico do git: o commit `82548fd` é o último que
contém todos eles. O
[CHANGELOG](CHANGELOG.md) registra as mudanças.

## Limites

- O transmissor só recebe *firmware* por cabo e não grava as medições: uma
  janela medida com o *gateway* desligado se perde.
- Uma telemetria corrompida no ar não é reenviada. Sem ela, o *gateway* não
  autoriza a rajada, e a leitura e a janela daquele ciclo se perdem; a falta
  aparece como lacuna na sequência das telemetrias.
- Os comandos enviados pelo rádio são protegidos por CRC, sem autenticação.
- O sensor do módulo respondeu `0x74` ao registrador de identificação,
  diferente do `0x68` do MPU-6050, e a marcação do circuito integrado não foi
  conferida.
- O filtro passa-baixas digital do sensor foi configurado com banda nominal de
  184 Hz, abaixo dos 1000 Hz da faixa de medição da série ISO 10816. A
  velocidade eficaz calculada até 184 Hz é, por isso, um limite inferior da
  velocidade eficaz de banda larga.
- O transmissor não tem termistor (`KAELIX_HAS_NTC=0`), e a temperatura das
  telemetrias é a do próprio sensor.

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
