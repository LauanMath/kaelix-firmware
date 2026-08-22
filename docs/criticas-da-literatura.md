# O que a literatura aponta contra o Kaelix

Compilação das objeções que a literatura levanta — tanto contra **nossas análises**
quanto contra **decisões do projeto**. Complementa [referencias.md](referencias.md), que
lista as fontes, e [questionamentos-tecnicos.md](questionamentos-tecnicos.md), que traz
os achados numéricos.

> Ressalva de método: a auditoria independente das citações não chegou a rodar. Confirme
> cada fonte antes de citar. Ver o cabeçalho de `referencias.md`.

---

## Parte A — Críticas às nossas análises

### A1. Nossa métrica de avaliação é a errada para o problema

**Quem diz:** Koizumi et al. (DCASE2020 Workshop); Abburi et al. (PHM Society, 2023).

Usamos **AUC global** na comparação de bandas (Fig. 2e). O benchmark DCASE2020 — cujo
cenário é idêntico ao nosso, treino só com dados normais e anomalias desconhecidas —
adota **AUC + pAUC** (AUC parcial restrita à faixa de baixo falso alarme), justamente
porque a AUC global não caracteriza o ponto de operação.

Isso atinge um argumento que nós mesmos fizemos: dissemos que "o AUC cai pouco (1,000 →
0,963) mas a perda é maior perto do joelho da ROC". A literatura tem a métrica que mede
exatamente isso, e nós não a usamos. **Deveríamos ter reportado pAUC.**

Abburi et al. acrescentam que acurácia pura é inadequada sob desbalanceamento, e
recomendam F-score e comparação contra *dummy classifiers*.

**Correção sugerida:** recalcular a Fig. 2e com pAUC (FPR ≤ 0,1) e reportar F1 além de
acurácia na Fig. 2c.

### A2. A magnitude do nosso vazamento está no extremo alto da faixa publicada

**Quem diz:** Abburi et al. (2023); Vieira et al. (MSSP, 2026).

Medimos **35,8 pontos** de inflação (99,0% → 63,2%). A literatura reporta:

| Fonte | Dataset | Queda observada |
|---|---|---|
| Abburi et al. (2023) | CWRU, SVM+STFT | 0,851 → 0,700 (**~15 p.p.**) |
| Abburi et al. (2023) | XJTU, SVM+STFT | 0,988 → 0,890 (~10 p.p.) |
| Vieira et al. (2026) | CWRU, WDCNN | ~33–37 p.p. |

A faixa real vai de **10 a 37 pontos**, e nosso número está no topo. Apresentar 35,8 como
"o" efeito do vazamento é forte demais — o efeito depende de modelo, descritores e dataset.

**Correção sugerida:** reportar nosso valor dentro da faixa da literatura, não como
medida universal.

### A3. Nosso método de escolha de limiar é ingênuo perto do estado da arte

**Quem diz:** Siffer et al. (KDD 2017); Koizumi et al. (DCASE2020); Antonini et al.
(Sensors, 2023).

Recomendamos derivar o limiar de um quantil do conjunto de validação. Funciona, mas a
literatura tem opções melhores:

- **SPOT/DSPOT** (Siffer et al.): teoria de valores extremos, sem hipótese sobre a
  distribuição. O único parâmetro é o **risco q**, que especifica diretamente a taxa de
  falso alarme desejada — exatamente a substituição que nosso item 7 pede.
- **DCASE2020 baseline**: ajusta uma **distribuição gama** ao histograma dos scores dos
  dados normais e fixa o limiar no percentil 90.
- **Antonini et al.**: no ESP32, fixam limiar normalizado de score em **0,75**, com
  mínimo de 100 instâncias para massa crítica.

Nenhum deles usa `contamination`. Nossa crítica ao default está certa; nossa alternativa
é a mais fraca das disponíveis.

### A4. A escolha do Isolation Forest não é defensável como "melhor"

**Quem diz:** Han et al. (ADBench, NeurIPS 2022) — 30 algoritmos × 57 datasets, 98.436
experimentos.

Dois achados que atingem o projeto:

1. **Nenhum algoritmo não-supervisionado é estatisticamente superior aos outros.** O
   Isolation Forest é adequado ao cenário, não superior. Defendê-lo como escolha técnica
   ótima não se sustenta.
2. **Com apenas 1% de anomalias rotuladas, a maioria dos métodos semi-supervisionados já
   supera o melhor não-supervisionado.**

O ponto 2 é o mais relevante: se o Lauan conseguir rotular **alguns poucos** ensaios de
falha na Skala, a arquitetura semi-supervisionada supera o ganho de otimizar o Isolation
Forest puro. Isso questiona a decisão arquitetural central do projeto.

Barbariol & Susto (TiWS-iForest) reforçam por outro caminho: para TinyML, o ganho vem de
**podar árvores com supervisão fraca**, reduzindo memória, latência e erro ao mesmo
tempo — não de ajustar `contamination`.

### A5. Focamos em vRMS quando a literatura aponta pico e pico-a-pico

**Quem diz:** Fidali et al. (Sensors, 2024); El Bouharrouti et al. (Machines, 2024).

Fidali et al. é o único trabalho que aplica a banda 10–1000 Hz da ISO 20816 com sensores
MEMS de banda limitada. Achado central: *"a sensibilidade diagnóstica dos parâmetros
depende do limite superior de banda dos sensores"* — o que confirma nosso item 1 — **mas
também**: os parâmetros mais sensíveis a falhas de fadiga são **pico e pico-a-pico de
aceleração, não a vRMS**.

El Bouharrouti et al. chegam a conclusão compatível: p2p e RMS foram os descritores mais
discriminantes entre sadio e defeituoso.

Ou seja: gastamos esforço na cadeia de integração para vRMS (item 2, correta e
necessária para a norma), mas para **detecção** a literatura aponta para métricas de
pico em aceleração, que não exigem integração nenhuma.

**Implicação:** conformidade com a ISO e capacidade de detecção são objetivos distintos,
e otimizar um não otimiza o outro.

### A6. Não dimensionamos a viabilidade do modelo embarcado

**Quem diz:** Antonini et al. (Sensors, 2023).

O projeto prevê Isolation Forest "embarcado em C++ nativo", mas nunca verificamos se
cabe. Os números medidos em ESP32 (WROVER-IE, 4 MB SPIRAM):

- inferência: 6,9–20,33 ms (10–50 árvores)
- RAM na inferência: 70,8–84,8 kB
- treino no dispositivo: 1,2–6,4 s, 536–1576 kB

É viável, mas o dado deveria estar no projeto. E Antonini et al. declaram explicitamente
que **avaliar acurácia de detecção está fora do escopo** deles — ou seja, não existe FPR
publicado para Isolation Forest embarcado em MCU.

### A7. O problema metodológico mais sério: nosso item 6 e nosso item 7 são incompatíveis nos datasets escolhidos

**Quem diz:** ausência na literatura + estrutura dos datasets.

Toda a literatura de vazamento trata de **classificação supervisionada**. Não há trabalho
sobre vazamento em detecção one-class / Isolation Forest / autoencoder para rolamentos.

E há uma consequência prática dura:

> Treinar só com dados normais (item 7) **e** particionar por rolamento (item 6) é
> **impossível no CWRU** — há uma única configuração saudável — e problemático no
> MAFAULDA, cujas 49 sequências normais vêm de uma única montagem.

Não é um detalhe: as duas recomendações que fizemos não podem ser satisfeitas
simultaneamente com os datasets previstos no projeto. Isso precisa entrar como limitação
declarada, ou exige dados coletados na Skala com mais de uma montagem saudável.

---

## Parte B — Críticas ao projeto

### B1. A bateria recarregável é contestada por todo o mercado e pela literatura

**Quem diz:** Nabavi et al. (Int. J. Electrochemistry, 2025); e os quatro sistemas de
referência, sem exceção.

| Sistema | Bateria |
|---|---|
| TRACTIAN Smart Trac | lítio **primária**, 3 anos |
| Bently Nevada Ranger Pro | Li-SOCl₂ **primária** substituível, até 5 anos |
| Erbessd Phantom | lítio **primária** CR2477, 65.000 medições |
| Jakobsen (2024), open hardware | Li-SOCl₂ AA **primária** + supercapacitor |
| **Kaelix** | **LiPo 2000 mAh recarregável** |

Nabavi et al. recomendam Li-SOCl₂ para "implantações de longo prazo e baixa potência em
ambientes extremos, pela vida útil e estabilidade superiores", reservando químicas
recarregáveis para "aplicações de alta potência com ciclagem frequente". Com **2,0 mW
médios**, o Kaelix cai exatamente na primeira categoria.

**Isto é mais forte que o nosso item 4.** Nós identificamos que a LiPo é o elo térmico
fraco e que a recarga in loco fica bloqueada acima de ~81 °C de carcaça. A literatura vai
além: a LiPo recarregável é a escolha errada de origem. Trocá-la eliminaria simultaneamente o
conector USB-C IP67 (ainda não comprado), o problema térmico de carga, e boa parte da
complexidade do corte de alimentação por transistor.

O contraponto honesto: bateria primária não é recarregável, então a manutenção passa a
ser troca de célula — o que exige abrir o invólucro e conflita com a vedação IP67. É um
trade-off real, mas o mercado inteiro escolheu o outro lado.

### B2. A fixação puramente magnética é contestada pelo próprio benchmark do projeto

**Quem diz:** datasheet do TRACTIAN Smart Trac; Erbessd; Jakobsen.

O TRACTIAN — referência de mercado declarada no projeto — diz que o ímã **"ajuda no
processo de instalação"**, mas que **"idealmente a base deve ser colada no ativo para
evitar queda e aumentar a qualidade da aquisição de dados"**. O produto acompanha cola
bicomponente e ainda tem porca de travamento.

Os outros seguem a mesma linha: Erbessd fixa com parafuso 1/4-28 UNF; Jakobsen usa pé de
alumínio usinado, escolhido explicitamente "para transmissão mecânica das vibrações".

Isso **confirma nosso item 8** por caminho independente — e aponta uma solução que não
consideramos: **colagem estrutural**, não parafuso. Para o Kaelix, cuja proposta de valor
inclui remoção não-destrutiva para recarga, há tensão direta: se B1 for aceito e a
bateria virar primária, a remoção frequente deixa de ser necessária e a colagem passa a
ser viável.

### B3. Nenhum produto comercial usa corpo totalmente plástico com base plástica

**Quem diz:** datasheets de TRACTIAN, Bently Nevada, Erbessd.

O Erbessd Phantom é o único com carcaça declaradamente plástica — e mesmo assim:
*"Housing material: ABS, stainless steel"*, plástico só no corpo, **aço inox na base**.
TRACTIAN é corpo metálico com ressalto de centragem metálico.

Convergente com nossa recomendação de base metálica com quebra térmica (itens 4 e 8), por
evidência de mercado independente da nossa análise.

### B4. Todos os sistemas de referência cobrem banda muito maior

| Sistema | Banda de aceleração | Envelope |
|---|---|---|
| Bently Nevada Ranger Pro | 5 Hz–10 kHz (Z) | PeakDemod até 5 kHz |
| Erbessd Phantom EPH-V11E | 0,5 Hz–10 kHz (X,Y) | — |
| Jakobsen (2024) | ADXL1002, DC–11 kHz | sim |
| **Kaelix** | **até 500 Hz** | não disponível |

Nenhum produto encontrado usa acelerômetro com teto de 500 Hz para diagnóstico de
rolamento. O Bently Nevada, aliás, mede **velocidade em 5–2000 Hz**, cobrindo
integralmente a banda ISO de 10–1000 Hz — que o Kaelix cobre pela metade.

Nota: Jakobsen usa **dois** acelerômetros com papéis separados — ADXL362 (até 200 Hz)
para desbalanceamento e ADXL1002 (até 11 kHz) para rolamento. É a arquitetura que a
literatura sugere quando se quer as duas coisas.

### B5. O sistema mais parecido publicado entrega ~73%, não 99%

**Quem diz:** Kolok et al. (Sensors, 2025) — ESP32-C6 + MPU6050 + Isolation Forest com
`contamination="auto"`, <30 EUR, <300 mW. Praticamente o Kaelix.

Resultados: acurácia ~73% (precisão 0,755; recall 0,679; F1 0,715; ROC-AUC 0,780),
validação cruzada 5-fold 72,9% ± 2,4%, ~900 amostras, **um único tipo de falha**
(desbalanceamento por obstrução parcial de roda). Não discutem ISO 10816 nem banda útil.

Duas leituras:

1. **Validação:** a arquitetura do Kaelix é publicável e o escopo que recomendamos
   declarar (desbalanceamento) é o que a literatura efetivamente valida.
2. **Referência de comparação:** se o Kaelix reportar acurácia muito acima de ~73% com
   hardware equivalente e falha equivalente, é forte indício de vazamento.

Detalhe técnico útil: eles configuraram o **DLPF interno do MPU6050 em 5 Hz** — corte
agressivo que elimina o aliasing que nosso item 1 identificou, ao custo de descartar
quase toda a banda.

---

## Parte C — O que ninguém contesta

Para equilíbrio, os pontos em que a literatura nos dá razão sem ressalva:

- **Item 2 (ISO é velocidade, banda 10–1000 Hz):** confirmado no texto normativo da
  ISO 10816-3:2009, ISO 20816-3:2022 e ISO 2954:2012.
- **Item 2 (integração no domínio da frequência):** Brandt & Brincker (Measurement, 2014)
  concluem que DFT → divisão por jω → IDFT é o melhor método.
- **Item 1 (a informação de rolamento está na ressonância de alta frequência):** Randall
  & Antoni (MSSP, 2011), referência canônica do envelope.
- **Item 7 (mecânica do `contamination`):** verificável na documentação do scikit-learn —
  `offset_ = -0.5` no modo `auto`, e o parâmetro altera apenas o offset.
- **Item 6 (vazamento no CWRU é real e grave):** consenso amplo, com Smith & Randall
  (2015, 2443 citações) como crítica fundacional.

---

## Prioridade das correções

Por impacto sobre a monografia:

1. **A7** — a incompatibilidade entre os itens 6 e 7 nos datasets escolhidos. É um
   problema metodológico que a banca pode apontar, e precisa de resposta escrita.
2. **B1** — a bateria. Decisão de projeto contestada por 4 de 4 sistemas de referência
   e pela literatura específica.
3. **A1** — trocar AUC global por pAUC. Correção barata que melhora a análise.
4. **A4** — declarar que Isolation Forest é adequado, não ótimo, e registrar que rotular
   poucos ensaios renderia mais.
5. **A2** — reportar nosso 35,8 p.p. dentro da faixa de 10–37 da literatura.
6. **A5** — reconhecer que conformidade ISO (vRMS) e detecção (pico) são objetivos
   distintos.
