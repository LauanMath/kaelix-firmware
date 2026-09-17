# Invólucro — v1 e v2

Duas versões geradas por `hardware/gen_involucro.py` a partir de um único
conjunto de parâmetros (`VERSOES`). Ambas reprodutíveis; nenhum arquivo desta
pasta é editado à mão.

| | v1 | v2 |
|---|---|---|
| estado | congelada | ativa |
| origem das cotas | `docs/device/IMG_5298.jpeg`, versão 4 | dimensionada pela célula real e pela placa |
| planta | quadrada | retangular |
| cavidade | 43 × 43 × 54 | 62 × 52 × 30 |
| corpo | 50 × 50 × 62 | 69 × 59 × 38 |
| montagem | 54 × 54 × **74,5** | 69 × 59 × **50,5** |
| postes M3 | Ø11, recuo 3,5 | Ø8, recuo 2,5 |
| volume externo do corpo | 155 cm³ | 155 cm³ |
| massa se maciço | 112 g | 115 g |
| célula que entra | nenhuma de catálogo | Adafruit 2011, 2000 mAh |
| autonomia a 314 µA | 66 dias (célula de 500 mAh, **que também não entra**) | **265 dias** |
| REQ-PWR-06 (243 dias) | não atendido | atendido |

Eletrônica idêntica nas duas. Cada versão tem a sua placa, desenhada para o
próprio vão (`hardware/pcb/README.md`): 42 × 42 mm na v1, 61 × 51 mm na v2.
Cada uma entra na cavidade correspondente com interferência **0,0 mm³**.

## Arquivos

```
v1/  v2/
  corpo.step  tampa.step  base.step     peças, cada uma na própria origem
  montagem.step                          posicionadas, com placa e bateria
  montagem-corte.step                    meia seção
```

A base (54 × 54, spigot Ø28, quatro ímãs Ø10 em R20, pino de orientação) é a
interface com o motor e é **igual nas duas versões**.

## Defeitos de projeto identificados

Cada linha traz como o defeito foi medido e o que decorre dele.

### Fechados

| # | Defeito | Medição | Correção |
|---|---|---|---|
| 1 | Contorno da placa circular (Ø40) sem fundamento. A justificativa era "com 43 mm de vão, um disco de 40 mm deixa 1,5 mm de folga radial" — trata vão **quadrado** como circular | vistas 1 e 2 do desenho: 50 × 50 externo, 43,0 interno, R7 | placa passou a quadrado 42 × 42 com recortes de canto; +18% de área útil (1257 → 1477 mm²) |
| 2 | Verificador de encaixe da placa comparava escalares (vão 43,0 contra placa 42,0), sem ver corredor de cabo, poste no canto nem altura | — | encaixe passou a ser interseção de sólidos no modelo montado |
| 3 | Modelo do conector JST deslocado 2,65 mm da origem do footprint (substituto da variante passante) | interseção de sólidos: J1 × C12 e J1 × RT1 | modelo próprio da variante SMD, e depois modelo real de terceiro |
| 4 | `.step` exportado sem os quatro componentes mais altos (WROOM-1U, Ra-02, MPU6050, JST), por ausência de modelo 3D na biblioteca | conferência de existência de arquivo por footprint | modelos de terceiros com licença permissiva; ver `3dmodels/origem/ORIGEM.md` |

### Abertos

| # | Defeito | Medição | Decorrência |
|---|---|---|---|
| 5 | **Nenhuma célula de catálogo entra na v1.** Adafruit 2011 (2000 mAh) mede 60,0 × 37,0 × 7,5 — 60 mm não entram em 43. Adafruit 1578 (500 mAh, 36 × 29 × 4,75) colide com os postes | interferência 86,1 mm³ com os postes Ø11 | REQ-PWR-06 não atendido na v1. Resolvido na v2 |
| 6 | Postes Ø11 de altura cheia consomem os cantos da cavidade. Maior retângulo livre: **25 × 40 mm** | varredura geométrica com folga de 1,0 mm | 2000 mAh nesse formato exigiria célula de ~18 mm de espessura, sob encomenda |
| 7 | **Altura dos postes não é cotada** no desenho | vistas 1 e 2 não a apresentam | Se forem postes curtos (só no topo), a v1 aceita célula 40 × 40 × 10 (~1880 mAh, 249 dias). Cota que separa "custom exótico" de "custom viável" |
| 8 | Empilhamento não fecha: 74,5 mm contra os **78,0** da vista 6 | base 9,0 + corpo 62,0 (rebaixo 3,3 absorvido) + tampa 3,5 | −3,5 mm. Candidatos: espessura da tampa, altura da base, gaxeta |
| 9 | **Espessura da tampa não é cotada.** Adotado 3,5, herdado de `experiments/figures/scripts/export_enclosure_data.py` | vista 3 não a apresenta | Se for 7,0, o item 8 fecha exato |
| 10 | Massa anotada (118 g) é cálculo **maciço**, não impresso | modelo maciço: 112 g a 1070 kg/m³ → fração implícita 1,06 | Peça impressa a 35% de infill pesa menos. Diferença de 5% valida a leitura das cotas |
| 11 | Furo USB-C Ø13,0 sem conector correspondente na placa | netlist: J2 é header UART de 6 vias | O desenho anota o furo como provisório |
| 12 | Antena SMA Ø6,5 sem rabicho u.FL→SMA na BOM | `hardware/pcb/v1/kaelix-bom.csv` | O Ra-02 tem conector IPEX; a ligação ao painel não está especificada |
| 13 | Altura dos furos de USB-C e SMA na parede não legível na foto do desenho | — | Modelados a 45% e 80% da cavidade. Bitolas são as do desenho; posições verticais são arbitradas |
| 14 | Assento mínimo da placa não estava especificado em lugar nenhum | interferência 220,3 mm³ com assento de 2,0 mm | **A placa exige ≥3,3 mm acima do fundo**: o Ra-02 está na face de baixo e desce 3,29 mm. Adotado 5,0 mm |
| 16 | **Não existe assento.** Seccionando o corpo no plano dos 5,0 mm adotados, a seção tem só a parede externa e os quatro bosses — nenhum ressalto, nervura ou batente | seção do sólido em z = FUNDO + 5,0 | Os 0,0 mm³ de interferência que `check_3d.py` reporta como aprovação significam que **nada toca a placa**. Onde a carga se apoia vale **fator 2,5** na frequência do conjunto (679 Hz contra 1670 Hz na v2); ver `hardware/fem/README.md` |
| 17 | A v2 **não resolve** o caminho de montagem confirmado em `analise-involucro.ipynb`, e na hipótese pessimista piora | modal FEM: v1 936 Hz, v2 **679 Hz**, com carga na borda de cima | A célula de 2000 mAh que entrega os 265 dias põe 25 g a mais sobre a mola de ASA; a massa vence a redução de 24 mm na altura. A recomendação de base metálica permanece |
| 15 | Base 54 × 54 menor que o corpo da v2 (69 × 59) | — | Corpo avança 7,5 mm sobre a base em X. Decisão pendente: aumentar a base ou manter a interface com o motor intocada |

## Decisões da v2

| Decisão | Razão medida |
|---|---|
| Planta retangular | Célula real manda em X (60 + folgas); placa manda em Y |
| Poste Ø8 em vez de Ø11 | Com Ø11, a menor cavidade que livra célula **e** placa exige corpo de 87 × 51. O inserto térmico M3 do próprio desenho tem Ø4,0; Ø8 de ASA em volta é folgado |
| Cavidade 62 × 52 | Menor solução da varredura sob a restrição dos quatro postes |
| Altura 50,5 mm | 24 mm abaixo da v1. Perde a comparação de altura com o TRACTIAN Smart Trac (40 × 40 × 78,5, vista 6) |
| Base inalterada | É a interface com a máquina; nada na v2 a exige diferente |

## Limitação declarada da v1

A não-adequação da bateria está registrada em `VERSOES["v1"]["limitacao"]` e
sai no relatório de geração como **limitação conhecida**, não como falha:
a v1 gera com código de saída 0. Falha de geração fica reservada a defeito
não previsto.

```
LIMITAÇÕES CONHECIDAS (declaradas, não são falha):
   v1: a bateria não cabe (86 mm3 de interferência com os postes Ø11)
```

## O que a geração verifica

Cada execução mede e reporta, por versão:

- sólido não vazio em cada peça
- interseção placa × corpo
- interseção bateria × corpo, com o lado longo da célula alinhado ao lado
  longo da cavidade
- envelope da montagem e volume externo do corpo
- massa se maciço, contra a anotada no desenho
- empilhamento, contra a altura anotada na vista 6

## Não verificado

- Se a peça impressa mede o desenho. O desenho está marcado **"⚠ COTAS NÃO
  TRAVADAS"** e "medir com paquímetro no componente físico antes da impressão
  final"
- Vedação, IP67, compressão de gaxeta
- Comportamento térmico e modal (o sólido habilita ambos; nenhum foi rodado)
- Disponibilidade comercial das células citadas

## Regenerar

```
/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd hardware/gen_involucro.py
```

Depende de `hardware/pcb/<versão>/kaelix.step` (gerado por `tools/build-hardware.sh`) e dos
modelos em `hardware/3dmodels/origem/`.
