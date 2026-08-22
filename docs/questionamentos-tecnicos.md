# Questionamentos técnicos — Kaelix

Pontos levantados na análise de [project.md](project.md). Cada item registra o problema, por que importa e o que precisa ser decidido ou verificado.

Os itens marcados **[verificado]** foram checados numericamente:

| Itens | Notebook | Figura |
|---|---|---|
| 1, 2, 6, 7 | [`validacao-questionamentos.ipynb`](../experiments/notebooks/validacao-questionamentos.ipynb) | [Fig. 1](../figures/output/fig1_banda_sensor.png), [Fig. 2](../figures/output/fig2_metodologia.png) |
| 8 | [`analise-involucro.ipynb`](../experiments/notebooks/analise-involucro.ipynb) | [Fig. 3](../figures/output/fig3_involucro.png) |
| 4 | [`analise-termica.ipynb`](../experiments/notebooks/analise-termica.ipynb) | — |

Os itens 3 e 5 dependem de dado externo (medição em campo, consulta regulatória) e
seguem abertos. O item 4 foi analisado, mas a temperatura real de carcaça na Skala
continua não medida.

**Dois itens tiveram a hipótese original refutada pela verificação** — item 4 (o ASA
protege, não prejudica) e parte do item 8 (curvatura e modos de placa não são problema).
As correções estão registradas no próprio item.

---

## 1. O MPU6050 limita quais falhas o produto consegue detectar

**Problema.** O MPU6050 tem taxa de amostragem máxima de ~1 kHz no acelerômetro e densidade de ruído da ordem de 400 µg/√Hz. Por Nyquist, a banda útil termina em ~500 Hz.

**Por que importa.** As frequências características de defeito em rolamento (BPFO, BPFI, BSF, FTF) e, principalmente, a ressonância excitada por esses defeitos ficam tipicamente entre 3 kHz e 10 kHz. Com teto em 500 Hz, o dispositivo enxerga bem desbalanceamento (1× RPM), desalinhamento (2× RPM), folga mecânica e problemas de fundação — mas não enxerga defeito incipiente de rolamento, que é justamente o que o TRACTIAN Smart Trac promete.

**[verificado]** A simulação mostrou um quadro mais matizado que "não detecta":

| Métrica (razão defeito/sadio) | Sensor 20 kHz | MPU6050 (1 kHz) |
|---|---|---|
| Contraste em BPFO | 413× (envelope) | 20× (espectro direto) |
| Curtose | 2,57× | 1,01× |
| Fator de crista | 2,11× | 1,00× |
| Pico | 2,93× | 1,01× |
| Pico-a-pico | 3,28× | 1,07× |

Ou seja: como BPFO (105 Hz) cai dentro da banda, **ainda sobra sinal detectável** — mas a margem cai por um fator de ~21, e é essa margem que acomoda variação de carga, temperatura e montagem em campo. Mais grave: **curtose e fator de crista deixam de separar as classes**, e são duas das quatro descritores previstos no projeto.

**Pico e pico-a-pico não resgatam o sensor.** Fidali et al. (*Sensors*, 2024) apontam esses dois parâmetros como os **mais sensíveis** a falha de fadiga em rolamento, acima da velocidade RMS — seria razoável esperar que resistissem melhor. Testamos: também colapsam (2,93× e 3,28× na referência, contra 1,01× e 1,07× na banda do MPU6050). **A escolha de descritor não compensa banda insuficiente**; o problema está na aquisição.

Há ainda um artefato de interpretação. Sem o DLPF configurado, a leitura a 1 kHz sofre aliasing e a curtose *parece* funcionar (1,82 → 4,55), mas a energia de 3,5 kHz reaparece dobrada em 500 Hz — frequência onde não existe nada fisicamente. Qualquer diagnóstico por frequência fica errado, com aparência de acerto.

**O que decidir.**
- Se o escopo é desbalanceamento/desalinhamento, o MPU6050 serve e isso deve estar explícito no documento do projeto e na defesa.
- Se o MPU6050 for mantido, **configurar o DLPF é obrigatório**, não opcional.
- Se o escopo inclui rolamento, é preciso trocar o sensor. Candidatos: ADXL1002 (analógico, ±50 g, 11 kHz), IIM-42652 (digital, baixo ruído, ODR alto), ADXL355.
- Verificar qual é a rotação nominal dos motores da Skala para calcular as frequências de defeito reais e confirmar se caem ou não dentro da banda disponível.

---

## 2. ISO 10816-3 é norma de velocidade, não de aceleração

**Problema.** A ISO 10816-3 define as zonas A–D em **velocidade RMS (mm/s)**, medida na banda de 10 Hz a 1000 Hz. O MPU6050 entrega **aceleração**.

**Por que importa.** Aplicar limiares de mm/s a valores de m/s² produz rotulagem sem sentido físico. Para usar a norma é necessário integrar o sinal de aceleração para velocidade — e integração numérica acumula deriva de offset, que cresce sem limite ao longo da janela.

**[verificado]** Testado contra senoide de valor analítico conhecido (3,0 m/s² @ 50 Hz → 6,7524 mm/s RMS exatos):

| Método | RMS obtido | Erro |
|---|---|---|
| Integração no tempo, sem passa-alta | 11,69 mm/s | +73% |
| Integração no tempo, com passa-alta | 17,31 mm/s | +156% |
| **Integração na frequência (banda ISO)** | **6,7525 mm/s** | **0,0%** |
| Na frequência, com bias de 0,02 m/s² | 6,7525 mm/s | 0,0% |
| No tempo sem HP, com bias de 0,02 m/s² | 55,08 mm/s | +716% |

Dois resultados merecem destaque. Primeiro, **o passa-alta não salva a integração no tempo** — piorou (156% contra 73%), porque o `cumsum` ainda acumula o transiente de borda do filtro. Segundo, um bias de apenas 0,02 m/s², dentro da especificação de qualquer MPU6050, leva o resultado a 55 mm/s quando o correto é 6,75: um sinal na zona A seria classificado muito além da zona D.

A integração na frequência é imune ao bias porque o bin de DC cai fora da máscara de 10–1000 Hz. Validada também em sinal multi-componente (erro de 0,003%).

**O que fazer.**
1. Remover o bias do acelerômetro (média ou passa-alta em 10 Hz).
2. Integrar **no domínio da frequência** (dividir cada bin da FFT por `j·2πf`), reaproveitando a FFT já calculada para os descritores. Não integrar no tempo.
3. Zerar os bins fora de 10–1000 Hz, conforme a norma, e calcular o RMS por Parseval.
4. Validar contra sinal de referência conhecido antes de confiar nos números.

**Consequência para o item 1.** Com Nyquist em 500 Hz, o Kaelix cobre apenas metade da banda de 10–1000 Hz que a norma exige. A conformidade plena com a ISO 10816-3 **não é possível com o MPU6050** — um argumento para revisar o sensor independente do de rolamento.

Este item é **pré-requisito** da pendência crítica sobre a ISO 10816-3 já listada no projeto: não adianta confrontar os limiares com o texto oficial se a grandeza medida não é a grandeza da norma.

---

## 3. Classe do motor define os limiares — e ainda não foi levantada

**Problema.** A ISO 10816-3 divide as máquinas em grupos por potência e tipo de fundação (rígida ou flexível). Os limiares das zonas A–D mudam conforme o grupo.

**O que fazer.** Levantar na Skala, para cada equipamento a instrumentar: potência nominal (kW), rotação nominal (RPM), tipo de fundação e tipo de acoplamento. Sem isso, qualquer limiar adotado é arbitrário.

---

## 4. Margem térmica: o gargalo é a bateria, não o ASA nem o ímã

**Hipótese original (refutada).** Este item afirmava que o ASA (Tg ≈ 105 °C) seria o elo térmico mais fraco, por estar em contato com uma carcaça a 80–100 °C.

**[verificado]** A análise em [`experiments/notebooks/analise-termica.ipynb`](../experiments/notebooks/analise-termica.ipynb) mostra que a hipótese está errada, e por um motivo que inverte o raciocínio: **é justamente por ser mau condutor que o ASA protege a eletrônica**.

| T da carcaça | T interna (base ASA) | T interna (base alumínio) |
|---|---|---|
| 60 °C | 39,3 °C | 59,5 °C |
| 80 °C | 44,8 °C | 79,0 °C |
| 100 °C | 50,1 °C | 98,5 °C |

A resistência do caminho condutivo em ASA é de 88,8 K/W contra 0,074 K/W em alumínio — uma razão de 1206×. O ASA só se aproxima da sua HDT (98 °C) se a própria carcaça já estiver nessa temperatura.

O autoaquecimento é irrelevante: com duty cycle de 30 s/h, a potência média é de 2,0 mW, elevando a temperatura interna em 0,01 °C. **Todo o calor vem de fora.**

**O elo mais fraco é a bateria LiPo**, com folga sobre os demais:

```
LiPo carga (45 °C) < LiPo descarga (60 °C) < MPU6050/ESP32 (85 °C)
                   < ASA HDT (98 °C) < N42SH (150 °C)
```

Os ímãs ficam em contato direto com a carcaça, então operam à temperatura dela — mas o N42SH suporta 150 °C, bem acima do cenário. A perda de força a 80 °C é de ~14%, e é **reversível**.

### A consequência operacional não documentada

O desenho prevê recarga por USB-C sem abrir o invólucro, o que sugere recarregar o dispositivo instalado. Células LiPo não podem ser carregadas acima de 45 °C. Com carcaça acima de ~81 °C o interior ultrapassa esse limite e um carregador correto recusa a carga.

A saída existe — destacar o dispositivo, que a base magnética já permite, e aguardar. A constante de tempo de resfriamento é de ~14 min, e ~31 min dissipam 90% do ΔT. Mas isso é **procedimento operacional que não está no projeto**.

### Conflito com o item 8

Os dois estudos pedem coisas opostas da base: a vibração quer rigidez (metal), a térmica quer isolamento (plástico).

| Configuração | T interna @80 °C | f_n |
|---|---|---|
| Base ASA (atual) | 44,8 °C | 557 Hz |
| Base alumínio | 79,0 °C | 788 Hz |
| **Base alumínio + quebra térmica de 2 mm** | **47,1 °C** | **788 Hz** |

A quebra térmica resolve o conflito de material: um espaçador isolante de 1–2 mm entre a base metálica e o corpo recupera quase todo o isolamento mantendo o ganho de rigidez. Meio milímetro já recupera a maior parte, porque a resistência em série é dominada pelo elo de menor condutividade — mesmo princípio que, no item 8, fazia o elo mais flexível dominar a rigidez.

Duas ressalvas honestas: trocar só a base leva f_n de 557 para 788 Hz, **ainda dentro da banda** — resolver a vibração exige tratar também o corpo. E 47 °C continua acima dos 45 °C de carga, então a restrição de recarga in loco permanece: ela vem da bateria, não do material da base.

**O que fazer.**
- Medir a temperatura real de carcaça na Skala com termopar ou câmera térmica. **Continua pendente** e é o dado que fecha esta análise.
- Especificar a janela de recarga em função da temperatura, ou prever recarga com o dispositivo destacado.
- Se adotar base metálica pelo item 8, incluir a quebra térmica no mesmo projeto.
- Verificar se o circuito de carga tem proteção por temperatura (NTC no pack); sem ela, a restrição de 45 °C não é aplicada automaticamente.

---

## 5. Risco regulatório: 433 MHz não é faixa ISM homologada no Brasil

**Problema.** A faixa ISM para radiação restrita no Brasil, conforme Anatel (Resolução 680), é 902–907,5 MHz e 915–928 MHz. A faixa de 433 MHz tem uso restrito e não é a faixa padrão para LoRa nacional.

**Por que importa.** Para protótipo acadêmico é irrelevante. Para qualquer intenção de produto comercializável, é bloqueante — o dispositivo não passaria em homologação.

**O que fazer.** Registrar como risco conhecido. Se houver intenção de produto, migrar para módulo de 915 MHz (ex.: RA-01H, SX1276 em 915 MHz) — a mudança é praticamente drop-in em nível de firmware.

---

## 6. Vazamento de dados na validação com o CWRU

**Problema.** O CWRU Bearing Dataset é notório por produzir acurácias de ~99% que não se sustentam fora dele. A causa mais comum é vazamento de dados: janelas contíguas do mesmo ensaio acabam divididas entre treino e teste, de modo que o modelo memoriza a assinatura do ensaio em vez de aprender a falha.

**[verificado]** Reproduzido com defeito incipiente e assinatura de montagem por ensaio. Mesmo modelo, mesmos dados, mesmos descritores:

| Estratégia de split | Acurácia |
|---|---|
| Aleatório por janela (vazamento) | 0,990 ± 0,010 |
| Por ensaio, GroupKFold (correto) | 0,632 ± 0,192 |
| Chute na classe majoritária | 0,500 |

A inflação é de ~36 pontos percentuais. O detalhe mais revelador está nos folds individuais do split correto: `[0.50, 0.64, 1.00, 0.52, 0.50]` — três ficam no nível do chute, e um chega a 1,00. O desvio-padrão elevado evidencia que o modelo não generaliza para ensaios novos; a média única do split incorreto suprime essa informação.

**O que fazer.**
- Fazer split por **ensaio/arquivo**, nunca por janela aleatória (`GroupKFold` / `GroupShuffleSplit`).
- Reportar **média e desvio entre folds** — desvio alto significa que faltam ensaios, não necessariamente que o modelo é ruim.
- Reportar a acurácia com a origem do split explicitada. Um número alto sem essa ressalva será questionado na banca.
- Priorizar o MAFAULDA (UFRJ) como referência principal: é mais próximo do caso de uso real, tem condições de falha mais variadas e menos histórico de vazamento na literatura.
- Tratar validação em dados sintéticos como verificação de implementação da pipeline, não como evidência de desempenho.

---

## 7. Isolation Forest: verificar o pressuposto de dados

**Contexto.** A escolha do Isolation Forest é coerente com o cenário realista de manutenção preditiva, em que se coleta muito dado de operação normal e quase nenhum de falha. Vale apenas confirmar dois pontos.

**[verificado]** Efeito do `contamination`, treinando apenas com dados normais:

| `contamination` | Falso alarme | Detecção |
|---|---|---|
| 0,5 | 50,0% | 100% |
| 0,1 | 10,0% | 100% |
| 0,01 | 1,4% | 100% |
| `"auto"` (default) | **42,1%** | 100% |

O default marcaria **42% da operação normal como anomalia**. Num dispositivo que dispara alerta de manutenção, mais de um terço dos alertas seria falso e o operador deixaria de confiar no sistema em poucos dias. O parâmetro não altera a qualidade do detector (AUC = 1,000 nas quatro linhas) — apenas onde o corte é feito. Fixando 1% de falso alarme alvo por quantil no conjunto de validação, a detecção permaneceu em 100%.

Quanto à banda, com defeito **incipiente** o AUC caiu de 1,000 (20 kHz) para 0,963 (MPU6050) — 3,7%, aparentemente modesto. Mas a AUC global não caracteriza o ponto de operação, e o benchmark DCASE2020 Task 2 (cenário idêntico ao nosso: treino só com dados normais, anomalias desconhecidas) adota **pAUC**, a AUC parcial restrita a falso alarme baixo:

| Métrica | 20 kHz | MPU6050 | Queda |
|---|---|---|---|
| AUC global | 1,000 | 0,963 | 3,7% |
| pAUC (FA ≤ 10%) | 0,999 | 0,837 | **16,2%** |
| pAUC (FA ≤ 5%) | 0,998 | 0,795 | **20,3%** |

A perda real é **quatro a cinco vezes maior** do que a AUC global sugere. Correção adotada por recomendação da literatura.

**O que fazer.**
- Definir `contamination` próximo de zero e derivar o limiar de um conjunto de validação com taxa de falso alarme alvo — nunca do default da biblioteca.
- Ter claro que o gargalo é a **aquisição, não o classificador**: nenhum ajuste de modelo recupera informação que o sensor descartou.

---

## 8. O invólucro em ASA filtra o sinal antes que ele chegue ao sensor

**Problema.** O invólucro não é apenas proteção: ele é parte da cadeia de medição. Entre a superfície do motor e o chip existe o caminho `motor → ímãs → base ASA → ressalto Ø28 → corpo ASA → PCB → MPU6050`. Cada elo em ASA é uma mola, e um acelerômetro montado sobre molas em série forma um sistema massa-mola com frequência natural própria.

**Por que importa.** A regra da acelerometria exige que a frequência de montagem fique em pelo menos 3× a maior frequência de interesse. Abaixo disso, a montagem passa a dominar a leitura.

**[verificado]** Análise em [`experiments/notebooks/analise-involucro.ipynb`](../experiments/notebooks/analise-involucro.ipynb), a partir das cotas do desenho (`docs/device/`, versão 4).

Duas hipóteses foram testadas e **descartadas**:

| Hipótese | Resultado | Veredito |
|---|---|---|
| A curvatura da carcaça compromete a fixação magnética | perda de 7–30% (Ø500 a Ø100 mm); margem de ~2× sob vibração severa (18 g) | descartada |
| As paredes ressoam na banda de medição | modo mais baixo ≈ 1307 Hz, acima da banda ISO | descartada |

A terceira foi **confirmada**:

| Elo | Rigidez (N/m) | Fração da flexibilidade |
|---|---|---|
| Base ASA (placa, h ≈ 6 mm) | 2,83 × 10⁶ | 51,1% |
| Ressalto de centragem Ø28 × 3,3 | 3,73 × 10⁸ | 0,4% |
| Corpo 50×50×3,5, L = 78 mm | 2,98 × 10⁶ | 48,5% |
| **Em série** | **1,45 × 10⁶** | — |

Resulta em **f_n ≈ 557 Hz** — dentro da banda que o dispositivo pretende medir. A transmissibilidade a 500 Hz chega a ~5×: o sensor lê cinco vezes a vibração real. O erro de amplitude passa de 10% já em **168 Hz**.

O efeito é robusto à incerteza: dobrando a espessura da base para 12 mm, f_n sobe apenas para 750 Hz, ainda dentro da banda. O corpo tubular de 78 mm limita tanto quanto a base.

**Três consequências.**

1. **Amplificação dependente da frequência.** Como o fator varia com a frequência, nenhuma calibração por ganho fixo corrige.
2. **A rotulagem pela ISO 10816-3 fica comprometida** mesmo com a integração do item 2 implementada corretamente — parte da banda vem amplificada, parte atenuada.
3. **Falsos positivos plausíveis.** Uma máquina saudável cuja excitação caia perto de 560 Hz produz leitura alta, com assinatura estável e repetível: parece defeito, não ruído.

**Este item é independente do item 1.** Mesmo trocando o MPU6050 por um acelerômetro de 20 kHz, o invólucro continuaria filtrando o sinal antes que ele chegasse ao chip.

**O que fazer.** Por ordem de eficácia, segundo a decomposição da flexibilidade:

1. **Base metálica** (alumínio ou aço) mantendo a interface com o corpo. Mesma geometria em alumínio dá f_n ≈ 3273 Hz, que atende a regra de 3×.
2. **Aproximar o sensor da base** — montar o PCB do acelerômetro sobre pilar rígido solidário à base, em vez de suspenso no corpo.
3. **Encurtar ou reforçar o corpo.**

**Como verificar em bancada.** Um *bump test* resolve em uma tarde: com o dispositivo montado no motor parado, dar um toque leve na tampa e registrar a resposta do próprio MPU6050 — a frequência de decaimento livre é f_n. Alternativa: medir o mesmo ponto com o Kaelix e com um acelerômetro de referência aparafusado; a razão entre os espectros é a transmissibilidade medida.

**Nota sobre a base — corrigida pelo item 4.** A sugestão inicial era que a base metálica resolveria simultaneamente este item e a margem térmica. A [análise térmica](../experiments/notebooks/analise-termica.ipynb) mostrou o contrário: o ASA protege a eletrônica por ser isolante, e o alumínio levaria o interior de 44,8 °C para 79,0 °C com carcaça a 80 °C. A base metálica **exige quebra térmica** (espaçador isolante de 1–2 mm), que preserva o ganho de rigidez e recupera o isolamento. Ver item 4.

---

## Ordem sugerida de resolução

1. Definir o escopo de falhas (item 1) — determina se o sensor muda, e isso afeta hardware, firmware e modelo.
2. Executar o *bump test* (item 8) — barato, rápido, e confirma ou refuta o achado mais estrutural.
3. Levantar dados da planta: temperatura de carcaça, potência, RPM, fundação (itens 3 e 4).
4. Corrigir a cadeia de medição para velocidade (item 2) — pré-requisito da validação da norma.
5. Refazer a validação do modelo com split por ensaio (itens 6 e 7).
6. Registrar o risco de 433 MHz (item 5) sem bloquear o protótipo.

**Nota sobre a ordem.** Os itens 1 e 8 são independentes entre si e ambos afetam a qualidade do sinal na origem. Corrigir o modelo (itens 6 e 7) antes de resolver a aquisição otimiza sobre dados que ainda vão mudar.
