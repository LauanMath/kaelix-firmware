# Placa — versões

Projeto KiCad versionado por diretório. Cada versão é autocontida
(`.kicad_sch`, `.kicad_pcb`, `.kicad_pro`, `.kicad_sym`, `sym-lib-table` e
derivados) e é gerada por `hardware/gen_schematic.py` + `hardware/gen_pcb.py`.
Nenhum arquivo destas pastas é editado à mão.

```
KAELIX_PCB=v1 ./tools/build-hardware.sh        # v1 é o padrão
KAELIX_PCB=v2 ./tools/build-hardware.sh
KAELIX_PCB=v3 ./tools/build-hardware.sh
```

**O esquemático é idêntico na v1 e na v2.** Mesma netlist, mesmos 32
componentes, mesmos 24 nets. O que a v2 muda é o contorno, o placement e o
roteamento — consequência do vão do invólucro correspondente
(`hardware/involucro/README.md`), não decisão de circuito.

**A v3 é a primeira revisão de circuito:** a v2 mais a carga da bateria
(BQ21040 e USB-C). Até a v2 a placa não tinha como carregar a célula. Ver
[O que a v3 muda](#o-que-a-v3-muda).

| | v1 | v2 | v3 |
|---|---|---|---|
| estado | congelada | ativa até a v3 | ativa |
| invólucro | v1, vão 43 × 43 | v2, vão 62 × 52 | v3 = corpo da v2 com o furo do USB-C na altura do conector |
| contorno | 42 × 42, 4 recortes r = 6,0 | 61 × 51, 4 recortes r = 4,5 | igual à v2 |
| recortes entre eixos | 36,0 × 36,0 | 57,0 × 47,0 | igual à v2 |
| área útil de cobre | 1477 mm² | 2962 mm² (+101%) | igual à v2 |
| folga no vão | 0,50 mm/lado em X e Y | 0,50 mm/lado em X e Y | 0,50 mm/lado; em −X o USB-C passa 0,07 mm para dentro do furo da parede, por projeto |
| componentes | 32 + 3 furos M2 | 32 + 3 furos M2 | 41 + 3 furos M2 |
| nets · pads com net | 24 · 118 | 24 · 118 | 30 · 149 |
| segmentos | 485 (327 F.Cu / 159 B.Cu) | 501 (419 F.Cu / 83 B.Cu) | 637 (488 F.Cu / 150 B.Cu) |
| vias de sinal | 68 | 68 | 108 |
| vias de costura de terra | 71 | 234 | 220 |
| triedro M2 | 63°, 206°, 326° — menor separação **97°** | 79°, 199°, 319° — menor separação **120°** | 64°, 184°, 304° — menor separação **120°** |
| ângulos legais para furo | 89 de 360 | 171 de 360 | 181 de 360 |
| deslocamento máx. no placement | 13,50 mm | 4,00 mm | 11,25 mm |
| desacoplamento acima de 3 mm (reta) | **6 de 6** | **2 de 6** | **3 de 6** |
| pior caso | 11,08 mm (C8 → U3.3) | 4,47 mm (C8 → U3.3) | 5,90 mm (C3 → U1.2) |
| corredor do cabo da bateria | 4,0 mm | 6,0 mm | 6,0 mm |
| envelope montado | 42,00 × 42,00 × 13,42 mm | 61,00 × 51,00 × 13,42 mm | 61,58 × 51,00 × 13,42 mm (nariz do USB-C) |
| ERC | 0 violações | 0 violações | 0 violações |
| DRC | 0 regra, 0 desconectado | 0 regra, 0 desconectado | 0 regra, 0 desconectado |
| interferência 3D | nenhuma entre 92 corpos | nenhuma entre 92 corpos | nenhuma entre 116 corpos |

A linha de desacoplamento usava uma métrica antiga ("10 de 10", "3 de 10"),
anterior à correção 16a, que tirou da conta os quatro capacitores que não
desacoplam nada. Segmentos, vias e costura da v1 e da v2 mudaram com as
correções 27 e 28 abaixo, sem tocar em circuito nem em placement.

Regras de fabricação, iguais nas duas: traço 0,20 · folga 0,15 · via Ø0,60 com
furo 0,30 mm; mínimos declarados furo 0,20 · folga 0,15 · traço 0,15 mm.

## O que a v2 resolve

| Item | v1 | v2 | Causa |
|---|---|---|---|
| desacoplamento | 10 capacitores acima de 3 mm, pior 11,08 | 3 acima de 3 mm, pior 5,95 | Na v1 o Ra-02 fica empilhado sob o WROOM-1U e divide o mesmo anel; na v2 cada módulo tem canto próprio. Os deslocamentos da v2 também deixaram de ser palpite: saem do contorno do CI mais a folga de corpo mais a meia-largura da peça |
| corredor do cabo | 4,0 mm | 6,0 mm | Medido: com 6,0 mm a v1 perde a saída de GND de RT1.2 e R8.2 (3 itens soltos no DRC); a v2 tem área para o plano contornar o corredor |
| triedro de furos M2 | 97° | 120° | O acelerômetro apoiado num triedro assimétrico mede a flexão da própria placa. 171 ângulos legais contra 89 |
| retorno de sinal | 151 segmentos em B.Cu | 81 | Menos rasgos no plano de terra da face de baixo |
| bateria | nenhuma célula de catálogo entra no invólucro v1 | célula real de 2000 mAh, 265 dias | Ver `hardware/involucro/README.md`, defeitos #5 e #6 |

## O que a v2 **não** muda

Eletrônica. Nenhum componente, valor, net ou conexão difere. Os dois
`.kicad_sch` têm os mesmos 294 elementos e 12 símbolos. Isso é deliberado: a
v2 é uma revisão mecânica e de layout, e misturá-la com mudança de circuito
tornaria impossível atribuir qualquer diferença de comportamento medido.

## O que a v3 muda

Circuito, pela primeira vez desde a v1: a placa passa a **carregar a
bateria**. Até a v2 não havia CI carregador nem conector de entrada — o
invólucro tinha o furo de USB-C, os relatórios falavam em "recarga por USB-C",
e a netlist não. Fonte: bloco `COM_CARGA` em `hardware/gen_schematic.py`.

| Peça | Função | Por quê |
|---|---|---|
| U5 BQ21040 (SOT-23-6) | carregador linear de uma célula, 4,2 V | único entre BQ21040, TP4056 e MCP73831 com monitor de temperatura da **célula** pronto para NTC de 10 k |
| RT2 NTC 10k β 3380 | TS do U5: suspende a carga acima de 45 °C (V_TS < 275 mV) e abaixo de 0 °C (V_TS > 1250 mV) | limiares do BQ21040 calibrados para β ≈ 3370 (103AT-2); o B3950 do RT1 cortaria perto de 39 °C |
| R13 2k7 | I_carga = K_ISET / R_ISET = 540 / 2,7 k = 200 mA | escolhida pelo modelo térmico, ver abaixo |
| J3 USB-C só energia, R11/R12 5k1 | entrada de 5 V | Rd em CC1 e CC2 é o que faz fonte C-para-C entregar VBUS |
| C13, C14 1 µF; C15 220 nF | entrada, saída e filtro do TS | C15 é opcional na folha de dados; aqui não, porque o RT2 fica a 22 mm do U5, na placa do rádio |
| IO7 ← CHG_N | status da carga para o firmware | GPIO de RTC: pode acordar do deep sleep; sem pull-up externo |

O limite de 45 °C que a análise térmica usa deixa de ser recomendação da
folha de dados da célula e passa a ser **imposto pelo hardware**.

**Corrente de carga, do modelo térmico.** O BQ21040 é linear e dissipa
I·(V_USB − V_bat) dentro do invólucro fechado. `hardware/termica_carga.py`
roda o FEM de `termica.py` com essa fonte interna: a placa sobe
**~15 K por watt**. Pior ponto da corrente constante (V_bat = 3,0 V), V_USB =
5,0 V, ambiente 30 °C. Com o motor a 90 °C a placa fica entre a média da
parede e o equilíbrio radiativo com o piso quente (+3,2 K, seção térmica de
`hardware/fem/README.md`); os dois extremos estão na tabela:

| I | P | bancada | motor frio | motor a 90 °C | carga completa |
|---|---|---|---|---|---|
| 150 mA | 0,30 W | 35,1 °C | 35,0 °C | 39,6 – 42,8 °C | ~15 h |
| **200 mA** | **0,41 W** | **36,7 °C** | **36,6 °C** | **41,1 – 44,3 °C** | **~12 h** |
| 250 mA | 0,51 W | 38,3 °C | 38,2 °C | 42,6 – 45,8 °C — TS pode cortar | ~9 h |
| 500 mA | 1,04 W | 46,6 °C — TS corta | 46,4 °C — TS corta | 50,2 – 53,4 °C — TS corta | — |

A 200 mA sobram 8,3 K até o corte na bancada ou com o motor parado. **No
motor a 90 °C sobram entre 0,7 e 3,9 K**: a carga funciona, mas no limite, e
com ambiente acima de 30 °C a margem cai kelvin por kelvin. Quem decide é o
TS, que suspende a carga e a retoma ao esfriar — é a proteção funcionando,
não falha. O procedimento recomendado é carregar fora do motor ou com ele
parado. Tudo isto é modelo, não medição, e a folga do motor quente é
otimista: a resistência interna herdada usa o h externo, e a convecção dentro
da cavidade é mais fraca. Ali a folga real pode ser nula. Hipóteses em
`hardware/termica_carga.py` e `hardware/fem/README.md`.

**Placement.** J3 na borda −X, alinhado ao furo do invólucro; U5 e os passivos
na face de baixo, sob o J3. RT2 na face de cima, sob a célula e longe do U5. O
J1 desce 3 mm em relação à v2: na posição antiga o corpo dele invadia o do J3
em 3,77 × 2,47 mm.

**Conector de borda.** O corpo do USB-C passa da borda da placa por projeto.
O gerador passou a conhecer isso (`NA_BORDA`): o encaixe é conferido pelos
pads, a linha "PCB Edge" do footprint tem de cair na borda (desvio medido
0,000 mm), e a passagem pela parede é interseção de sólidos em
`gen_involucro.py`.

## Defeitos de projeto identificados

### Fechados

| # | Defeito | Medição | Correção |
|---|---|---|---|
| 1 | Corte de energia dos periféricos por BC337 low-side. Os pull-ups de 4k7 permaneciam em +3V3 e alimentavam o MPU6050 pelos diodos de ESD de SDA/SCL | FM-27 em `docs/ANALISE-DE-FALHAS.md` | load switch high-side (Q1 SI2301 + Q2 BC847B); pull-ups movidos para o rail comutado +3V3_SW |
| 2 | MPU6050 permanentemente alimentado: 3,9 mA contínuos | orçamento em `src/power/sleep.cpp` | passou ao rail comutado; 314 µA efetivos |
| 3 | Placa em Ø74 mm num vão de 43. `verifica_encaixe` passava porque comparava escalares | contorno contra o vão do desenho | módulos empilhados um por face; contorno retangular |
| 4 | Ângulo de pad gravado como relativo. É **absoluto** (biblioteca + rotação do footprint) | 42 curtos no DRC | conferido contra as placas de exemplo do KiCad |
| 5 | Sinal da rotação invertido: pad local (0; 7,62) a 90° ia para −x | pad 4 do J2 aparecia em +7,62 no DRC | corrigido |
| 6 | Rotação própria do pad ignorada | QFN-24 descrito com pads de 0,85 mm num passo de 0,5 — sobrepostos entre si | escape do barramento I2C passou a fechar |
| 7 | Pad `custom` medido pelo `size` (âncora) | aba do SOT-89 tem 4,6 mm; o `size` diz 1,475 | quatro pistas passavam por cima da aba |
| 8 | Colisão mecânica e colisão de cobre tratadas como um invariante só | furo M2 sobre o pad do R6 não era detectado | separadas; passante vale nas duas faces |
| 9 | Nenhuma pista roteada — só footprints, planos e contorno | 70 pads desconectados no DRC | roteador de labirinto de duas camadas |
| 10 | Sem medição de tensão da bateria | REQ-SEG-29, REQ-SEG-53 e o heartbeat da QUARENTENA dependem dela | divisor 1M/1M + C11 em IO6 |
| 11 | Sem proteção de polaridade invertida na entrada | — | Q3 SI2301 em série, dreno na bateria |
| 12 | Sem filtro no nó do ADC do NTC. FM-08 raciocina sobre "capacitância de filtro × 10 k" — capacitor que não existia | `docs/ANALISE-DE-FALHAS.md` | C12 100n |
| 13 | Corredor de cabo do conector de bateria não modelado; furo M2 a 2,6 mm da boca | courtyard cobre a peça, não o que se conecta nela | corredor virou restrição de placement |
| 14 | Varredura do corredor registrada em comentário estava obsoleta: atribuía o limite ao triedro de furos e a peças sem lugar | remedido: placement fecha de 2,0 a 9,0 mm, furos a 97° em toda a faixa | o limite real é o plano de terra; comentário reescrito com o número medido |
| 15 | `gen_involucro.py` conferia as duas cavidades contra uma única versão de placa, escolhida por variável de ambiente | v1 do invólucro acusava 1616 mm³ de interferência com a placa da v2 | a placa passou a acompanhar a versão do invólucro |
| 22 | Nenhum caminho de carga da bateria: sem carregador, sem conector de entrada | netlist; o furo USB-C do invólucro não tinha conector | v3: BQ21040 + USB-C. v1 e v2 ficam como estão |
| 27 | Pino passante de peça não contava como obstáculo na face oposta. Só furo de fixação contava | DRC da v3: 3 `pth_inside_courtyard` — pinos de carcaça do J3 sob U5, R13 e C14 | a regra de furo passou a valer para pino (pad ≥ 0,8 mm). Via térmica de 0,6 mm continua de fora: o Ra-02 da v1 assenta sob as do WROOM-1U por projeto |
| 28 | O roteador contava como plano a faixa entre as fileiras de pads de um QFN de passo fino | DRC da v3: grupo de GND solto — o escape do U2.1 terminava numa ilha sob o MPU6050 | sob o corpo de peça de passo fino, na face dela, o plano não conta como caminho (`router.py`, `sob_fino`). Mudou o roteamento da v1 e da v2 também; as duas continuam com DRC limpo |
| 29 | Os furos de USB-C e SMA nunca foram cortados no modelo do invólucro | o cilindro começava fora do corpo, em −cx em vez de −cx/2 | ver `hardware/involucro/README.md` |

### Abertos

| # | Defeito | v1 | v2 | Decorrência |
|---|---|---|---|---|
| 16 | Desacoplamento acima de 3 mm do pino, em linha reta | 6 de 6, pior 11,08 mm | 2 de 6, pior 4,47 mm | Restam C8 (4,47) e C3 (3,30). C8 é o segundo capacitor de um **único** pino de +3V3 do Ra-02: em 0805 não há terceira posição |
| 16a | A métrica contava quatro capacitores que não desacoplam nada | lista antiga: C1, C5, C6, C9 | idem | C1 é o RC do EN, C5 e C6 são o regulador interno e a bomba de carga do MPU6050 (exigência de folha de dados, não de PDN) e C9 é a entrada do LDO. `_DESACOPLA` corrigido para C2, C3, C4, C7, C8, C10 |
| 16b | **A régua mede a reta; o laço vê a pista.** Numa placa de 2 camadas o retorno está a 1,5 mm, o que dá 781 pH/mm de pista e 1,30 nH por via passante | C8: 11,1 mm em reta contra **36,1 mm de pista e 6 vias** → 35,9 nH (3,25×) | pior caso C3: 6,4 mm de pista e 2 vias → 7,59 nH | A distância euclidiana subestimava a indutância por até 3,25×. Ver `hardware/pdn.py` e a figura 9 |
| 16c | **A v2 aproximou os capacitores e piorou o PDN.** O roteador pôs 2 vias no caminho do capacitor de bulk do ESP32-S3 | Z abaixo do alvo de 733 mΩ em toda a faixa | passa do alvo acima de **6,0 MHz** (ESP32-S3) e de **1,1 MHz** (MPU6050) | Ganho de placement em linha reta não se traduziu em ganho elétrico. Corrigir pede fixar o caminho do bulk na mesma face, sem via |
| 17 | Cinco pads de sinal do WROOM-1U a 1,27 mm de passo não comportam seis discretos a 3 mm | — | — | 0805 em pé pede 3,5 mm de passo. Limite de encapsulamento, não de área |
| 18 | Corredor do cabo | 4,0 mm | 6,0 mm | A v1 não aceita os ~6 mm que um alojamento PHR-2 com chicote pede |
| 19 | Altura dominada pelos **conectores**: J2 tem 11,54 mm e J1 tem 5,60, contra 3,20 dos módulos | igual | igual | Num dispositivo selado, um header de gravação de 11,5 mm é a peça mais alta. Decidir se fica populado no produto |
| 20 | Divisor do NTC satura no frio: nó chega a 3,22 V a −40 °C, acima da faixa útil do ADC (~3,1 V a 12 dB) | igual | igual | Abaixo de ~−35 °C a leitura sai otimista e **não** dispara os limiares de curto/aberto (ratio 0,94 contra 0,99). Inverter o divisor refaz toda a derivação de limiares |
| 21 | Numeração de pino do HT7333 em SOT-89-3 varia por fabricante | igual | igual | Conferir contra a folha de dados antes de fabricar |
| 22a | Furo USB-C Ø13,0 no invólucro sem conector correspondente | igual | igual | Fechado na v3 (J3). Na v1 e na v2 o furo existe no corpo e segue sem conector |
| 30 | v3: o NTC do TS lê a **placa**, não a célula | — | — | A placa fica acima da célula durante a carga, então o corte vem cedo, nunca tarde. Célula com NTC próprio (3 fios) tiraria a folga |
| 31 | v3: célula invertida **e** USB ligado ao mesmo tempo | — | — | O carregador sobe VBAT, liga o Q3 e injeta a pré-carga na célula invertida até VBAT cair abaixo do Vgs(th). Exige falha dupla; o JST-PH é polarizado. Saída em VBAT_RAW seria pior: a célula invertida conduziria pelo ESD do OUT mesmo sem USB |
| 32 | v3: nenhum código lê o CHG_N | — | — | O hardware está no IO7; o firmware ainda não sabe se está carregando |
| 33 | v3: modo próprio, PDN e vibração não foram recalculados | — | — | Contorno, furos e módulos são os da v2; as nove peças novas são estimadas em menos de 2 g. Declarado, não medido |
| 34 | v3: sem TVS no VBUS | — | — | O BQ21040 aguenta 30 V na entrada e desliga acima de 6,65 V (OVP). Descarga eletrostática no conector não está tratada |
| 23 | Rabicho u.FL → SMA fora da BOM | igual | igual | O Ra-02 tem IPEX; a ligação ao painel não está especificada |
| 24 | Não há código lendo a tensão da bateria | igual | igual | O caminho de hardware existe (IO6, divisor, capacitor); os limiares de REQ-SEG-29 não estão implementados |
| 26 | Modo próprio da placa cai 32% na v2 (2001 → 1352 Hz) e, a fs = 1000 Hz, dobra para 352 Hz | modal FEM em `hardware/fem/README.md` | Continua acima dos 1000 Hz da ISO nas duas versões, mas é mais um item que o DLPF do MPU6050 tem de rejeitar — configuração ainda pendente em `vibration_init` |
| 25 | A placa não parafusa nos bosses do invólucro em nenhuma das versões | furo M3 em (18; 18) pediria material até 28,2 mm na diagonal; o canto R7 da cavidade termina em 27,5 | recortes r=4,5 ficam exatamente sobre os eixos dos bosses | A fixação é o assento pelo aro mais os três M2 próprios. Os bosses seguram a tampa, não a placa |

## O que a geração verifica

- ERC com aviso tratado como erro
- DRC com zonas preenchidas; violação de regra é falha dura, item desconectado
  é contado contra linha de base declarada (**zero** nas três versões)
- contenção no contorno e colisão entre peças, separadas em mecânica e cobre
- distância de cada capacitor de desacoplamento ao pino que serve
- existência e validade de cada modelo 3D referenciado
- envelope, o que define a altura, interferência entre corpos e folga contra o
  vão da versão correspondente do invólucro
- derivados regerados a cada execução: netlist, BOM, STEP, renders

## Não verificado

- Se a pinagem confere com a peça física
- Numeração de pino do HT7333 em SOT-89-3
- Desempenho de RF, consumo real e qualquer medida de bancada
- Se o roteamento sobrevive à montagem: o gerador prova regras, não fabricação

## Reprodutibilidade

Apagando todos os derivados e regerando, `.kicad_sch`, `.kicad_pcb` e
`.kicad_sym` voltam **byte a byte idênticos**. O roteador é determinístico.
