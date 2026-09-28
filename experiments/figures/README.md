# Figuras — Kaelix

Figuras em padrão de submissão para os questionamentos técnicos do projeto.
Computação em Python, plotagem em R.

## Pipeline

```
notebooks/*.ipynb          validação numérica (fonte da verdade)
                 │
                 ▼
experiments/figures/scripts/export_*.py            reproduz a computação → CSV
                 │
                 ▼
figures/data/*.csv                     dados-fonte, rastreáveis
                 │
                 ▼
experiments/figures/scripts/fig*.R                 ggplot2 + patchwork
                 │
                 ▼
figures/output/*.{svg,pdf,tiff,png}    SVG/PDF vetoriais, TIFF 600 dpi
```

| Fonte da verdade | Exportador | Figura |
|---|---|---|
| `validacao-questionamentos.ipynb` | `export_source_data.py` | 1, 2 |
| `analise-involucro.ipynb` | `export_enclosure_data.py` | 3 |
| `analise-termica.ipynb` | `export_thermal_data.py` | 4 |
| cálculo no próprio exportador | `export_topologia_data.py` | 5 |
| **módulo `experiments/gateway/`** | `export_gateway_data.py` | 7 |
| esquema, sem dado numérico | — | 6 |
| **firmware** (`src/`, `lib/`) | — (desenho direto) | 8 |

**Figura 8 é a exceção do pipeline.** Um esquemático não tem CSV: os valores
*são* o desenho. `fig8_circuito.py` gera SVG diretamente, com coordenadas
absolutas, e cada constante traz no cabeçalho o arquivo e a linha do firmware de
onde saiu (pinos, R_FIXED, correntes). Não usa R nem biblioteca de esquemático —
`schemdraw` foi tentada e descartada: o posicionamento relativo dela fazia o
rótulo do CI disputar espaço com os nomes dos pinos.

**Nota sobre a fonte da verdade das figuras 5 e 7.** As figuras 1 a 4 têm a
computação no notebook e reproduzida no exportador — duas cópias que podem
divergir em silêncio, e o `simulate()` está de fato duplicado hoje. As figuras 5
e 7 não repetem esse arranjo: a 5 calcula no próprio exportador, e a 7 **importa
`gateway/kaelix_gateway`**, rodando o mesmo código que os 19 testes exercitam. O
exportador é adaptador para CSV, não segunda implementação.

**Divisão de responsabilidade.** A cadeia numérica (FFT, Hilbert, `butter`/`sosfiltfilt`,
`decimate`, Isolation Forest, `GroupKFold`) permanece em SciPy/scikit-learn, onde foi
validada. R cuida da camada gráfica, onde ggplot2 dá controle tipográfico superior.
Reimplementar o processamento de sinal em R exigiria revalidar tudo e arriscaria alterar
resultados já verificados.

## Reproduzir

```bash
uv run python experiments/figures/scripts/export_source_data.py      # CSVs das figuras 1 e 2
uv run python experiments/figures/scripts/export_enclosure_data.py   # CSVs da figura 3
uv run python experiments/figures/scripts/export_thermal_data.py     # CSVs da figura 4

Rscript experiments/figures/scripts/fig1_banda_sensor.R              # figura 1
Rscript experiments/figures/scripts/fig2_metodologia.R               # figura 2
Rscript experiments/figures/scripts/fig3_involucro.R                 # figura 3
Rscript experiments/figures/scripts/fig4_termica.R                   # figura 4

uv run python experiments/figures/scripts/export_topologia_data.py   # CSVs da figura 5
uv run python experiments/figures/scripts/export_gateway_data.py     # CSVs da figura 7

Rscript experiments/figures/scripts/fig5_topologia.R                 # figura 5
Rscript experiments/figures/scripts/fig6_cadeia.R                    # figura 6 (sem CSV)
Rscript experiments/figures/scripts/fig7_gateway.R                   # figura 7
```

Dependências R: `ggplot2`, `patchwork`, `dplyr`, `readr`, `scales`, `tidyr`,
`svglite`, `ragg`, `systemfonts`.

---

## Figura 6 — Cadeia completa do sistema

**Conclusão.** Do motor ao manutentor são dez elos; o diagrama mostra o estado de
implementação de cada um, e as fronteiras do ESP32-S3 não coincidem com a quebra
de linha.

**Arquétipo.** Esquema de fluxo, sem dado numérico. 183 × 96 mm.

**Legenda proposta.**

> **Fig. 6 | Cadeia do sistema proposto e estado de cada elo.** Fluxo do motor ao
> manutentor. Cor indica o estado: implementado e testado no host; existente mas
> exercitado apenas em simulação; inexistente; ou bloqueado pela ausência de
> hardware. Linhas tracejadas verticais marcam onde começa e termina o ESP32-S3.
> "Testado" refere-se a verificação no host: nenhum elo desta cadeia foi
> exercitado com rádio ou sensor reais.

## Figura 7 — Cadeia de comunicação exercitada por simulação

**Conclusão.** O deslocamento anticolisão por `device_id` não é otimização: sem
ele, dispositivos energizados juntos perdem **todos** os quadros, em qualquer
quantidade de nós.

**Arquétipo.** Grade quantitativa com painel-herói (a). 183 × 118 mm.

**Legenda proposta.**

> **Fig. 7 | Cadeia de comunicação sob simulação de meio.** **a**, Fração de
> quadros perdidos por colisão contra número de dispositivos energizados
> simultaneamente, com e sem o deslocamento derivado de `device_id`. Sem
> deslocamento a colisão não é probabilística: os nós transmitem no mesmo
> instante a cada ciclo e a perda é total. **b**, Funil de 24 h para 20
> dispositivos, com 2% de perda e 1% de corrupção injetados no meio; as duas
> primeiras barras coincidem porque o deslocamento eliminou a colisão neste
> cenário. **c**, Alerta por dispositivo: a regra de anomalias consecutivas
> dispara nos dois nós com anomalia sustentada e em nenhum dos dezoito com
> anomalia esporádica de 2%. **d**, Perda e corrupção injetadas contra o que o
> gateway reconstrói; a corrupção é integralmente detectada pelo CRC-16, e a
> perda aparece como lacuna na sequência de `boot_count`. A simulação cobre
> colisão, perda e corrupção de bit; **não** cobre propagação — alcance e margem
> de enlace dependem de medição em campo.

**Dados.** `fig7a_jitter.csv`, `fig7b_funil.csv`, `fig7c_alertas.csv`,
`fig7d_deteccao.csv`, gerados por `export_gateway_data.py`, que importa o módulo
`experiments/gateway/`.

## Figura 5 — Comparação de arquiteturas topológicas

**Conclusão.** O enlace decide autonomia tanto quanto decide alcance, e a
topologia atual não tem receptor: das quatro arquiteturas, três diferem apenas
no que fica do lado do gateway, e a escolha entre elas é de escopo, não de
viabilidade técnica.

**Arquétipo.** Composto liderado por esquema, com painel-herói (a). 183 × 168 mm.

**Legenda proposta.**

> **Fig. 5 | Arquiteturas topológicas de rede para o Kaelix.** **a**, Quatro
> arranjos comparados. A, estado atual: os nós transmitem e não há receptor
> implementado. B–D diferem no elemento que recebe — gateway ESP32 de canal
> único, computador de placa única com armazenamento e publicação, e
> concentrador LoRaWAN multicanal com downlink classe A. Linha tracejada,
> enlace de rádio; linha contínua, backhaul com fio. **b**, Autonomia do nó
> contra ganho de enlace, por fator de espalhamento; alcance e autonomia são o
> mesmo parâmetro, e SF9 é a escolha atual. **c**, Probabilidade de colisão em
> ALOHA puro contra número de dispositivos por gateway; o cálculo pressupõe
> fases de transmissão descorrelacionadas. **d**, Autonomia do nó por
> tecnologia de enlace. Todos os valores derivam do orçamento de energia do
> dispositivo (bateria LiPo de 2000 mA h, ciclo de 10 min, pacote de 20 bytes)
> e do tempo no ar calculado pela formulação do SX127x; nenhum vem de medição
> em hardware.

**Dados.** `fig5b_sf_tradeoff.csv`, `fig5c_colisao.csv`, `fig5d_enlace.csv`,
gerados por `scripts/export_topologia_data.py`.

## Figura 1 — Limite de banda do sensor

**Conclusão.** A banda de 500 Hz do MPU6050 preserva a taxa de repetição do defeito
(BPFO, 105 Hz) mas descarta a ressonância de 3,5 kHz que a carrega, reduzindo o
contraste diagnóstico de 413× para 20× e anulando curtose e fator de crista.

**Arquétipo.** Grade quantitativa com painel-herói (a). 183 × 110 mm.

| Painel | Evidência | Dados |
|---|---|---|
| a | PSD comparada, sadio vs. defeito, com a banda do sensor destacada | `fig1a_espectro.csv` |
| b | Contraste em BPFO: envelope (20 kHz) vs. espectro direto (1 kHz) | `fig1b_contraste.csv` |
| c | Curtose e fator de crista por cadeia de aquisição | `fig1c_features.csv` |
| d | Frequência aparente da ressonância sob aliasing | `fig1d_aliasing.csv` |

**Legenda proposta.**

> **Fig. 1 | O limite de banda do MPU6050 descarta a evidência de defeito de rolamento.**
> **a**, Densidade espectral de potência de vibração simulada para rolamento sadio (azul)
> e com defeito de pista externa (vermelho), amostrada a 20 kHz. A faixa sombreada marca
> a banda acessível ao MPU6050 (≤ 500 Hz, Nyquist para ODR de 1 kHz). Os impactos
> periódicos excitam uma ressonância estrutural em 3,5 kHz, inteiramente fora dessa
> banda. **b**, Razão entre a amplitude em BPFO (104,6 Hz) nas condições com e sem
> defeito. A análise de envelope sobre a banda de ressonância (2–6 kHz), disponível
> apenas a 20 kHz, entrega contraste 21× maior que o espectro direto na banda do
> MPU6050. **c**, Curtose e fator de crista, indicadores clássicos de impacto, para as
> três cadeias de aquisição. Com antialiasing correto (MPU c/ AA) as duas condições
> tornam-se indistinguíveis (curtose 1,76 vs. 1,77). Sem antialiasing (s/ AA) as
> descritores aparentam discriminar, mas o conteúdo espectral é artefato. **d**, Frequência
> aparente da ressonância após subamostragem a 1 kHz sem filtro antialiasing; a energia
> real de 3–5 kHz reaparece em frequências onde nada existe fisicamente.
> Sinais sintéticos, motor de 1750 rpm, rolamento SKF 6205. Fonte: `figures/data/`.

---

## Figura 2 — Escolhas metodológicas

**Conclusão.** Integração no domínio errado, split que vaza assinatura de ensaio e
limiar herdado do default produzem erros de 73–716%, 36 pontos de acurácia aparente e
42% de falso alarme.

**Arquétipo.** Grade quantitativa, três blocos independentes. 183 × 112 mm.

| Painel | Evidência | Dados |
|---|---|---|
| a | Erro de cada método de integração contra o valor analítico | `fig2a_integracao.csv` |
| b | Deriva temporal causada por bias de 0,02 m/s² | `fig2b_deriva.csv` |
| c | Acurácia por estratégia de split | `fig2c_split.csv`, `fig2c_folds.csv` |
| d | Falso alarme por valor de `contamination` | `fig2d_contamination.csv` |
| e | ROC do Isolation Forest por banda de aquisição | `fig2e_roc.csv` |

**Legenda proposta.**

> **Fig. 2 | Três escolhas metodológicas alteram os resultados mais do que o efeito
> medido.** **a**, Velocidade RMS obtida por cinco variantes de integração aplicadas a
> uma senoide de 3,0 m/s² a 50 Hz, cuja integral é conhecida analiticamente
> (6,75 mm/s, linha tracejada). Só a integração no domínio da frequência, com a banda de
> 10–1000 Hz da ISO 10816-3, recupera o valor exato; ela permanece exata sob bias porque
> o termo DC cai fora da máscara. **b**, Velocidade instantânea sob bias de 0,02 m/s²,
> dentro da especificação do MPU6050. A integração no tempo acumula deriva linear e
> atinge 55 mm/s de RMS contra os 6,75 mm/s corretos. A modulação do traço azul é a
> janela de Hann, compensada no cálculo do RMS. **c**, Acurácia de um Random Forest sobre
> as mesmos descritores e os mesmos dados, variando apenas a estratégia de divisão.
> Barras: média; erro: desvio-padrão entre repetições (n = 10 seeds) ou folds (n = 5);
> pontos: folds individuais do split por ensaio. **d**, Fração de janelas de operação
> normal classificadas como anomalia, por valor de `contamination`, treinando apenas com
> dados normais. A detecção foi de 100% em todos os casos: o parâmetro desloca o limiar,
> não a qualidade (AUC = 1,000). **e**, Curvas ROC do Isolation Forest para defeito
> incipiente. A faixa sombreada marca a região de operação realista; ali a perda do
> MPU6050 é maior do que o AUC sugere.
> Sinais sintéticos. Fonte: `figures/data/`.

---

## Figura 3 — Invólucro

**Conclusão.** O caminho elástico motor→base→ressalto de centragem→corpo→sensor coloca a frequência de
montagem em 557 Hz, dentro da banda de medição, com erro de amplitude acima de 10% a
partir de 168 Hz — enquanto fixação magnética e modos de placa não são problema.

**Arquétipo.** Grade quantitativa com painel-herói (a). 183 × 125 mm.

| Painel | Evidência | Dados |
|---|---|---|
| a | Transmissibilidade por material, com as bandas destacadas | `fig3d_transmissibilidade.csv` |
| b | Erro de amplitude dentro da banda do sensor | `fig3e_erro.csv` |
| c | Fração da flexibilidade por elo do caminho | `fig3c_rigidez.csv` |
| d | Força de retenção vs. diâmetro da carcaça (hipótese descartada) | `fig3a_fixacao.csv`, `fig3a_margem.csv` |
| e | Modos fundamentais dos painéis (hipótese descartada) | `fig3b_modos.csv` |

**Legenda proposta.**

> **Fig. 3 | O invólucro em ASA filtra o sinal antes que ele chegue ao sensor.**
> **a**, Transmissibilidade de base do conjunto invólucro–sensor, modelado como sistema
> massa–mola de um grau de liberdade ($m$ = 118 g, $\zeta$ = 0,03), para a mesma
> geometria em três materiais. A rigidez de cada elo vem de fórmulas fechadas aplicadas
> às cotas do desenho. Em ASA a frequência de montagem cai em 557 Hz, dentro da banda de
> medição; em alumínio e aço ela sai da faixa e a resposta permanece plana.
> **b**, Erro de amplitude correspondente dentro da banda do MPU6050. O erro ultrapassa
> 10% a partir de 168 Hz e cresce até a ressonância; por variar com a frequência, não é
> corrigível por ganho fixo. **c**, Decomposição da flexibilidade total ($1/k$) por elo:
> base e corpo respondem por 99,6%, enquanto o ressalto de centragem é irrelevante — consequência da
> associação em série, em que o elo mais flexível domina. **d**, Força de retenção dos
> quatro ímãs Ø10×3 sobre carcaças cilíndricas de diferentes diâmetros, considerando o
> entreferro causado pela curvatura; a linha tracejada marca a força inercial a 18 g,
> equivalente a 28 mm/s RMS a 1 kHz. **e**, Modo fundamental dos painéis do invólucro;
> a barra cobre o intervalo entre as condições de contorno simplesmente apoiada e
> engastada. Todos os modos ficam acima da banda da ISO 10816-3.
> Estimativas analíticas a partir das cotas do desenho. Fonte: `figures/data/`.

**Nota de método.** Fórmulas fechadas com condições de contorno idealizadas: placa
circular engastada para a base, compressão axial para o ressalto de centragem, viga tubular engastada
para o corpo. A rigidez real depende de pré-carga dos parafusos, planicidade das faces
impressas, orientação de camadas e comportamento do inserto térmico. O módulo do ASA
impresso é anisotrópico e cai com a temperatura. Os valores são ordem de grandeza; a
conclusão qualitativa é robusta à variação testada (base de 4 a 12 mm mantém $f_n$
dentro da banda), o número exato não.

---

## Figura 4 — Análise térmica

**Conclusão.** Por ser mau condutor, o ASA mantém o interior a 44,8 °C com carcaça a
80 °C, enquanto o alumínio entregaria 79,0 °C. O limitante não é o invólucro nem o ímã,
mas o limite de carga da LiPo (45 °C) — e a base metálica que o item 8 pede exige quebra
térmica para não violá-lo.

**Arquétipo.** Grade quantitativa com painel-herói (a). 183 × 115 mm.

| Painel | Evidência | Dados |
|---|---|---|
| a | Temperatura interna vs. carcaça, por configuração de base | `fig4a_temperatura.csv` |
| b | Limite térmico por componente, colorido pela margem | `fig4b_limites.csv` |
| c | Trade-off rigidez × temperatura entre os itens 4 e 8 | `fig4c_tradeoff.csv` |
| d | Efeito da espessura da quebra térmica | `fig4d_isolador.csv` |

**Legenda proposta.**

> **Fig. 4 | O ASA protege a eletrônica; a bateria é o elo térmico mais fraco.**
> **a**, Temperatura interna em regime permanente em função da temperatura da carcaça,
> para três configurações de base. O modelo de parâmetros concentrados considera condução
> pelo caminho sólido (base e ressalto de centragem), convecção natural e radiação para um ambiente a
> 30 °C. A resistência do caminho em ASA é de 88,8 K/W contra 0,074 K/W em alumínio, uma
> razão de 1206×: o plástico isola e o metal conduz. **b**, Limite térmico de cada
> componente, comparado à temperatura interna com carcaça a 80 °C (linha vertical). A cor
> indica a margem — crítica (< 5 °C), estreita (< 40 °C) ou confortável. O limite de
> carga da bateria é o único abaixo da temperatura de operação. **c**, As duas análises
> impõem requisitos opostos à base: o item 8 pede rigidez (metal) para tirar a frequência
> de montagem da banda de medição, e a térmica pede isolamento (plástico). Nenhuma das
> três configurações alcança simultaneamente a região desejável. **d**, Temperatura
> interna com base de alumínio em função da espessura do espaçador isolante. Meio
> milímetro recupera a maior parte do isolamento, porque a resistência em série é
> dominada pelo elo de menor condutividade.
> Estimativas analíticas a partir das cotas do desenho. Fonte: `figures/data/`.

**Nota de método.** Regime permanente, parâmetros concentrados, caminho condutivo
idealizado como a seção do ressalto de centragem. Não modela resistência de contato entre base e
carcaça, convecção forçada pelo ventilador do motor (que ajudaria) nem radiação recebida
de superfícies quentes próximas (que prejudicaria). A temperatura de carcaça dos
equipamentos da Skala continua não medida — é o dado que fecha a análise.

---

## Notas de QA

Verificado contra o checklist de pré-submissão:

| Item | Situação |
|---|---|
| Largura | 183 mm (dupla coluna) |
| Tipografia | Arial, base 6,5 pt; eixos 6,0 pt; tags 8 pt em negrito |
| Texto editável | SVG com 99, 91, 83 e 88 elementos `<text>`; nenhum glifo convertido em curva |
| Vetorial | SVG e PDF vetoriais; TIFF LZW a 600 dpi como raster |
| Cor | Sem mapa arco-íris; azul = correto/referência, vermelho = erro/perda, consistente nas quatro figuras |
| Escala de cinza | Verificado por conversão nas quatro figuras. Vermelho escurecido para #8C2D1E; curvas sobrepostas recebem `linetype` distinto (ROC do MPU6050; aço na Fig. 3; mitigação na Fig. 4), garantindo separação por luminância e por padrão |
| Legendas | Diretas ou internas; nenhuma legenda redundante repetida |
| Dados-fonte | Todo painel quantitativo rastreável a um CSV em `figures/data/` |

**Estatística dos painéis de modelo (Fig. 2c–e).**

```
split treino/teste : aleatório por janela (vazamento) vs. GroupKFold por ensaio
seeds / folds      : 10 seeds (split aleatório); 5 folds (GroupKFold)
métrica            : acurácia (c); taxa de falso alarme e detecção (d); ROC/AUC (e)
variabilidade      : desvio-padrão entre seeds ou folds
baseline           : classe majoritária (0,50), marcada em c
treino do IF       : apenas janelas de operação normal
```

**Limitação.** Os sinais são sintéticos, com física conhecida. As figuras validam a
cadeia de processamento e dimensionam ordens de grandeza; não substituem MAFAULDA/CWRU
nem medição em campo. Os valores absolutos dependem dos parâmetros de simulação
(amplitude do defeito, frequência de ressonância, nível de ruído).
