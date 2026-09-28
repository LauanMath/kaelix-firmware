# Mapa de integração — dos cinco relatórios para o TCC

Resultado do esboço reverso dos cinco documentos de `kaelix-firmware/docs/relatorio/`.
Método: extrair a primeira frase de cada seção e subseção dos cinco `.tex`, ler a sequência
resultante e confrontá-la com a tese fixada no Capítulo 1.

**Conclusão do esboço reverso:** a sequência das aberturas de seção não forma um argumento.
Forma cinco escopos independentes — "Escopo e método da revisão", "Objetivo e escopo",
"Escopo e critério", "Escopo", "Escopo e critério de leitura". Cada documento reabre o
assunto do zero. A integração não é editorial: é subordinar cinco escopos a uma tese.

Dentro de cada documento, porém, há material já organizado como argumento. As subseções de
Resultados do `relatorio-kaelix` têm títulos declarativos que enunciam o achado, e os eixos
da `revisao-literatura` mapeiam quase um a um na ordem de precedência da cadeia. É isso que
torna a integração viável sem reescrever o conteúdo.

---

## Destino por seção de origem

Legenda: **C2** Fundamentação · **C3** Desenvolvimento · **C4** Resultados e discussão ·
**AP** Apêndice · **✂** sai (absorvido em outro trecho)

### `revisao-literatura.tex` (22 pág, 38 refs)

| Seção de origem | Destino | Nota |
|---|---|---|
| Escopo e método da revisão | **C2** §2.1 | Vira o método da revisão, não um escopo autônomo |
| ↳ Nota de procedência | **C2** §2.1 ou **AP** | Verificação em fonte primária; é método, e sustenta o rigor do capítulo |
| Eixo 1 — Isolation Forest, limiar, TinyML | **C2** §2.3 | Segundo elo da cadeia |
| ↳ Escolha do detector e ausência de consenso | **C2** | |
| ↳ O limiar: o *default* não é calibração | **C2** | Estabelece a lacuna que o C4 preenche |
| ↳ Custo em microcontrolador, métricas e falso alarme | **C2** | |
| Eixo 3 — Banda de MEMS e detectabilidade | **C2** §2.2 | Primeiro elo; **vem antes** do Eixo 1 no TCC |
| ↳ De onde vêm os números próprios deste eixo | **C4** §4.1 | ⚠ Não é revisão: é declaração de proveniência. **Mas é a única do documento e cobre só o Eixo 3** — ver pendência 4 |
| ↳ Quão estreita pode ser a banda de um MEMS | **C2** | |
| ↳ As objeções | **C2** | |
| ↳ As alternativas que não foram tomadas | **C2** | |
| Eixo 4 — Normalização ISO e integração | **C2** §2.4 | |
| ↳ A banda normativa como requisito de instrumentação | **C2** | Premissa do achado de truncamento; **manter íntegra** |
| ↳ Integração: obrigação normativa e problema numérico | **C2** | |
| ↳ O que a literatura de sensores objeta | **C2** | |
| ↳ O orçamento de ruído | **C2** | |
| Eixo 5 — Sistemas IoT, invólucro, térmica | **C2** §2.5 | Terceiro elo |
| ↳ Nós de baixo custo: o que a literatura autoriza | **C2** | Absorve `comunicacao-topologia` §Detector embarcado |
| ↳ Banda, invólucro e caminho mecânico | **C2** | |
| ↳ A frequência de montagem: estimativa, não medição | **C2** | |
| ↳ Bateria e margem térmica | **C2** | |
| Síntese → O que a literatura sustenta | **C2** §2.6 | |
| Síntese → O que a literatura contesta | **C2** §2.6 | |
| Síntese → O que se conclui | **C4** §4.4 e **C5** | Já é a tese; não repetir no C2 |
| Lacunas e oportunidades | **C2** §2.7 | Fecha o capítulo com a lacuna que o C4 preenche |

### `relatorio-kaelix.tex` (12 pág)

| Seção de origem | Destino | Nota |
|---|---|---|
| Objetivo e escopo | ✂ | Absorvido pelo Capítulo 1, já escrito |
| Método | **C3** §3.1 | Núcleo da metodologia unificada |
| ↳ Simulação de vibração | **C3** | Modelo de sinal (Eq. do somatório + BPFO/BPFI) |
| ↳ Cadeias de aquisição comparadas | **C3** | |
| ↳ Conversão para velocidade e limiar do detector | **C3** | |
| ↳ Análise mecânica e térmica | **C3** | |
| Resultados → A banda descarta a evidência de rolamento | **C4** §4.1 | |
| Resultados → O invólucro filtra o sinal | **C4** §4.1 | Mesmo elo: aquisição |
| Resultados → A norma exige velocidade, integração na frequência | **C4** §4.2 | |
| Resultados → O protocolo de validação infla a acurácia | **C4** §4.2 | |
| Resultados → O limiar padrão produz falso alarme incompatível | **C4** §4.2 | |
| Resultados → A bateria define a margem térmica | **C4** §4.3 | |
| Confronto com a literatura (3 subseções) | **C4** §4.4 | Vira a Discussão, junto com a Síntese da revisão |
| Limitações | **C5** | Já absorvido pela seção "Alcance dos resultados" |

**Preservar os títulos declarativos.** "A banda do sensor descarta a evidência de defeito de
rolamento" enuncia o achado. Não trocar por títulos temáticos ("Análise de banda") na
integração — é a única parte do material que já está no padrão esperado.

### `verificacao-hardware.tex` (14 pág)

Documento majoritariamente tabular. Divide-se em projeto (corpo) e registro de verificação
(apêndice).

| Seção de origem | Destino | Nota |
|---|---|---|
| Escopo e critério | ✂ | Colapsa na delimitação única do C3 |
| Cadeia de geração e verificação | **C3** | "Nenhum arquivo derivado é editado à mão" é método, e é forte |
| Placa gerada | **C3** | |
| Rede de alimentação (PDN) | **C3** | |
| Análise modal | **C4** §4.1 | Resultado: frequência de montagem |
| Vibração aleatória e fadiga de junta de solda | **C4** §4.1 ou **AP** | Depende de sustentar alguma conclusão |
| Condução térmica do motor à placa | **C4** §4.3 | |
| Correções no esquemático | **AP A** | Registro de engenharia |
| Defeitos de geração da placa (corrigidos / abertos) | **AP A** | Os **abertos** merecem menção no C4/C5 |
| Versões (v1/v2) | **AP A** | |
| ↳ Ausência de assento para a placa | **AP A** | Defeito aberto |
| Correções a análises anteriores | **AP A** | Material forte para a matriz de rastreabilidade |
| Limitações declaradas | **C5** | Já absorvido |

### `comunicacao-topologia.tex` (5 pág)

| Seção de origem | Destino | Nota |
|---|---|---|
| Escopo | ✂ | |
| Comparação com dispositivos publicados → Banda de aquisição | ✂ → **C2** §2.2 | Redundante com Eixo 3 |
| ↳ Fonte de energia | **C2** §2.5 + **C4** §4.4 | Escolha contestada pela literatura |
| ↳ Detector embarcado | ✂ → **C2** §2.5 | Redundante com Eixo 5 (Kolok) |
| Topologia de rede | **C3** | |
| ↳ Parâmetros do enlace e compromisso alcance–autonomia | **C4** §4.3 | Resultado quantitativo |
| ↳ Comparação com Wi-Fi | **C4** §4.3 | |
| Cadeia de dados e gateway | **C3** | |
| ↳ Funções do receptor | **C3** | |
| ↳ Simulação do enlace | **C4** §4.3 | "Sem hardware, a cadeia foi exercitada…" — declarar proveniência |

### `praticas-sistemas-criticos.tex` (3 pág)

Não toca a tese sobre a cadeia de medição. Justifica escolhas de engenharia de firmware.

| Seção de origem | Destino | Nota |
|---|---|---|
| Documento inteiro | **AP B** | Ou seção curta no C3, se o firmware for parte da contribuição reivindicada |
| Verificação das fontes | **AP B** | |

---

## Redundâncias a resolver

Cada item abaixo aparece em três ou mais documentos. Regra: **uma ocorrência por função.**
A segunda só sobrevive se acrescentar contexto, interpretação ou consequência.

| Conteúdo repetido | Onde aparece hoje | Onde fica |
|---|---|---|
| Limitação de banda do MPU6050 | revisão Eixo 3, relatório Resultados, comunicação §Banda | **C2** como objeção da literatura; **C4** §4.1 como achado medido |
| Kolok et al. como análogo mais próximo | revisão Eixo 5, comunicação §Detector, relatório §Confronto | **C2** §2.5 uma vez; citado no C4 §4.4 |
| Exigência normativa ISO (banda, velocidade) | revisão Eixo 4, relatório Método e Resultados | **C2** §2.4 como requisito; **C4** §4.2 referencia |
| Bateria recarregável contraria a prática | revisão Eixo 5, comunicação §Fonte de energia, relatório §Escolhas contestadas | **C4** §4.4 |
| Frequência de montagem 557 Hz | revisão Eixo 5, relatório Resultados, verificação §Modal | **C4** §4.1 |

---

## Pendências que a integração precisa resolver

1. **Renumerar os eixos.** A revisão tem Eixos 1, 3, 4 e 5. A ausência do Eixo 2 é
   deliberada e declarada (`revisao-literatura.tex:90`), mas a lacuna na numeração não
   sobrevive como seções de capítulo. Renumerar **na ordem da cadeia**: aquisição (hoje
   Eixo 3) → estimação (Eixo 1) → normalização (Eixo 4) → implantação (Eixo 5).

2. **Inverter a ordem dos Eixos 3 e 1.** Hoje a revisão abre pelo detector. A cadeia de
   precedência — e o Capítulo 1 — estabelecem que a aquisição vem primeiro. O capítulo de
   revisão deve seguir a mesma ordem do capítulo de resultados.

3. ~~Corrigir `revisao-literatura.tex:427`~~ — **feito.** A frase atribuía à decimação do
   MAFAULDA todos os resultados de banda, mas o par 413×/20× é sinal sintetizado a 20 kHz.
   Agora separada em duas procedências, com o "nenhum deles vem de medição no dispositivo"
   cobrindo as duas.

4. **Verificação de procedência — em andamento, três defeitos encontrados.**
   A suspeita se confirmou: o defeito do item 3 não era isolado. Todos são da mesma
   forma — resultado sobre **sinal sintetizado** apresentado como se fosse sobre **dado
   real (MAFAULDA)**.

   | # | Número | Apresentado como | Origem real | Situação |
   |---|---|---|---|---|
   | 1 | par 413×/20× de contraste | decimação do MAFAULDA | sinal sintetizado a 20 kHz | corrigido |
   | 2 | pAUC cai 16,2% / AUC cai 3,7% | resultado próprio, sem marca | sinal sintetizado (`tab:pauc`) | corrigido |
   | 3 | ≈42% de falso alarme com `contamination='auto'` | "sobre o MAFAULDA, com GroupKFold por ensaio" (legenda de `tab:fpr`) | sinal sintetizado | **aberto** |

   **Sobre o nº 3.** Verificado até o dado-fonte, não só contra o texto:
   `experiments/figures/data/fig2d_contamination.csv` registra `auto → 0,4214` com
   detecção `1.0` em todos os valores, e o README das figuras declara para a Figura 2
   "Sinais sintéticos". A legenda da `tab:fpr` atribui a procedência MAFAULDA a "os dois
   últimos"; só o último (2% calibrado) a tem.

   É o mais grave dos três pela consequência, não pela frase: a tabela põe o ≈42%
   sintetizado lado a lado com três valores de literatura medidos em máquinas reais
   (22–38%) e conclui compatibilidade de ordem de grandeza. A procedência não licencia
   essa comparação.

   **Falta cobrir:** `verificacao-hardware.tex` e `comunicacao-topologia.tex` ainda não
   foram varridos por esta categoria.

5. **Dispersão suprimida nos resultados de detecção.** Os valores medidos estão corretos,
   mas são citados sem o desvio registrado no `CHANGELOG.md`:

   | citado | registrado |
   |---|---|
   | 75,0% em desbalanceamento | 75,0% ± 3,5% |
   | 5–7% em desalinhamento | vertical 7,2% ± 4,3%; horizontal 5,0% ± 3,1% |
   | 15–21% em rolamento puro | 14,8% e 20,7%, sem desvio registrado |

   A segunda linha é a crítica. A afirmação mais original do trabalho — que o
   desalinhamento falha por escolha de descritor, e não por banda — repousa num número
   cuja incerteza é da ordem do próprio número (±4,3% sobre 7,2%). Com a dispersão
   declarada a afirmação continua defensável, mas como **hipótese**, não como medição.
   Sem ela, uma banca que peça o desvio desmonta o argumento no ponto onde ele é mais
   forte. Obrigatório para o TCC.

6. **Lacuna de rastreabilidade dos resultados de treino.** Não existe artefato versionado
   com esses resultados — nem JSON, nem CSV, nem log de execução. Os números só existem
   em tabelas do `CHANGELOG.md`, e reproduzi-los exige rodar o treino de novo. Aceitável
   no TCC **se declarado** no capítulo de Metodologia, mas é lacuna real num projeto cuja
   rastreabilidade é, no resto, o ponto mais forte.

7. **Os 27 não-verificados.** Ao mover cada um, acrescentar a terceira parte: qual
   afirmação ele restringe. Hoje quase nenhum a tem.

8. **A nota de equivalência de zonas ISO** (valores idênticos entre as edições) entra no
   trecho que introduz as zonas de severidade — provável **C2** §2.4.

---

## Ordem sugerida de execução

1. **C4 primeiro.** É o capítulo com material mais pronto e com títulos já declarativos.
   Escrevê-lo primeiro fixa o que os capítulos 2 e 3 precisam preparar.
2. **C2 depois**, na ordem da cadeia já estabelecida pelo C4.
3. **C3 por último**, porque é o que mais depende de decidir o que é contribuição
   reivindicada (firmware, hardware, gateway) e o que é registro de engenharia.
4. **Apêndices** ao final, absorvendo o que sobrar do `verificacao-hardware` e do
   `praticas-sistemas-criticos`.
5. **Elementos pré-textuais** (resumo, *abstract*, palavras-chave) depois de tudo — o
   resumo só pode ser escrito quando os resultados estiverem no lugar.
