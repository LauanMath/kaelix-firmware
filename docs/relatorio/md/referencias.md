# Referências — revisão de literatura do Kaelix

Levantamento gerado por busca sistemática em 5 eixos temáticos, confrontando os
achados numéricos do projeto com a literatura publicada.

> **Estado de verificação.** A etapa de auditoria independente das citações **não
> chegou a rodar** (limite de sessão). A coluna *Meta* traz a confiança auto-declarada
> pelo agente de busca. As entradas marcadas **[CONFERIDO]** foram verificadas por mim
> em fonte primária. Antes de citar qualquer item deste documento na monografia,
> confirme autores, ano e veículo no site do editor ou no DOI.

---

## Verificações em fonte primária

Conferi as citações de maior peso. Duas apresentavam problemas.

### ✅ Vieira, Bauler, Rosa, Silva (2026) — números corrigidos

*Towards a more realistic evaluation of machine learning models for bearing fault
diagnosis.* Mechanical Systems and Signal Processing, v. 258, art. 114640 (no prelo).
Preprint: [arXiv:2509.22267](https://arxiv.org/abs/2509.22267).

**Atenção: há duas versões do artigo com numeração de tabelas diferente.** Verifiquei a
**v1** (set/2025) e o agente de busca leu a **v5** (jul/2026, que é a versão aceita).

Na **v1, Tabela 12** (modelo WDCNN), que eu li diretamente:

| Protocolo no CWRU | Domínio do tempo | Domínio da frequência |
|---|---|---|
| Sem vazamento (*bearing-wise*) | 66,4% ± 16,8% | 62,4% ± 20,6% |
| Vazamento de rolamento (*condition-wise*) | 99,9% ± 0,2% | 100,0% ± 0,0% |
| Vazamento de segmentação | 99,8% ± 0,2% | 99,9% ± 0,1% |

A v1 **não traz p-valores** e **não tem Tabela 13**.

O agente cita a **v5, Tabela 13**: 63,17% ± 10,84% (tempo), 64,34% ± 9,29% (frequência),
63,89% ± 9,26% (envelope) sem vazamento, contra 100,00% ± 0,00% com vazamento
*condition-wise*, e p = 7,11e-8. A v5 reorganizou o artigo (o vazamento virou a Seção 6),
então essa tabela plausivelmente existe — **não consegui confirmá-la** porque o HTML da
v5 veio truncado antes da Seção 6.

**Encaminhamento:** ambas as versões apontam a mesma conclusão — inflação de **33 a 37
pontos percentuais**, contra os 35,8 que medimos (99,0% → 63,2%). Antes de citar na
monografia, **baixe a versão publicada em MSSP** e confirme tabela, valores e p-valor.
Não cite os dois conjuntos de números como se fossem do mesmo lugar.

### ⚠️ El Bouharrouti, Moríñigo-Sotelo, Belahcen (2024) — rótulo invertido

*Multi-Rate Vibration Signal Analysis for Bearing Fault Detection in Induction Machines
Using Supervised Learning Classifiers.* Machines (MDPI), v. 12, n. 1, art. 17.
DOI: 10.3390/machines12010017.

O agente classificou como **"contradiz"** o nosso A1. Li o PDF: **o paper apoia o A1.**
A Figura 7 mostra acurácia baixa a 1 kHz, subindo acentuadamente a partir de 12 kHz, e o
texto afirma que a melhora ocorre "particularmente para sinais cuja taxa é igual ou
superior a 12 kHz". SVM e MNLR "não aprenderam do conjunto de treino" a 1 e 6 kHz. Na
Figura 9, modelos treinados a 1–6 kHz classificam mal os sinais de 48 kHz.

Três ressalvas que **enfraquecem o paper como evidência**, em qualquer direção:

1. **Confundidor de quantidade de dados.** A 1 kHz restam 96 amostras contra 4678 a
   48 kHz (Figura 6). O colapso pode ser escassez de dados, não perda de banda.
2. **Falhas artificiais por eletroerosão**, de 0,178 a 0,533 mm — severas, não
   incipientes. Não testa o caso que nos interessa.
3. **Batches com 50% de sobreposição**, sem split por rolamento — exatamente o
   vazamento que o item A3 identifica. Os valores absolutos são provavelmente inflados.

Usam 20 descritores de domínio do tempo (incluindo curtose e fator de crista) e
**descartaram explicitamente os descritores de frequência**.

### ✅ Demais verificações pontuais

- **ISO 20816-3:2022 e ISO 10816-3:2009** — o agente afirma ter lido o texto normativo e
  cita a exigência de resposta plana em 10–1000 Hz. Plausível e coerente com a ISO 2954,
  mas **não confirmei o texto da norma** (documento pago). Confirme antes de citar.
- **Documentação do scikit-learn** — a afirmação de que `offset_ = -0.5` quando
  `contamination="auto"` é verificável na documentação oficial e sustenta o A4.

---

## Eixo 1 — Isolation Forest, limiar e TinyML embarcado

**Achado confrontado:** A4 · **Veredito da busca:** ALINHADO

| Paper | Ano | Veículo | Relação | Meta |
|---|---|---|---|---|
| Antonini, Pincheira, Vecchio, Antonelli. *An Adaptable and Unsupervised TinyML Anomaly Detection System for Extreme Indust* | 2023 | Sensors (MDPI), 23(4):2344 | confirma | ✓ |
| scikit-learn developers. *sklearn.ensemble.IsolationForest -- documentacao oficial (v1.9 estavel, acessada* | 2026 | Documentacao oficial scikit-learn (fonte prim | confirma | ✓ |
| Liu, Ting, Zhou. *Isolation Forest* | 2008 | IEEE ICDM 2008, pp. 413-422 | matiza | ✓ |
| Ma, Zhao, Zhang, Akoglu. *The Need for Unsupervised Outlier Model Selection: A Review and Evaluation of In* | 2021 | arXiv cs.LG 2104.01422; versao de revista em  | confirma | ✓ |
| Han, Hu, Huang, Jiang, Zhao. *ADBench: Anomaly Detection Benchmark* | 2022 | NeurIPS 2022 (Datasets & Benchmarks Track) | matiza | ✓ |
| Brito, Susto, Brito, Duarte. *An Explainable Artificial Intelligence Approach for Unsupervised Fault Detection* | 2021 | arXiv cs.AI 2102.11848 (versao de revista: Me | confirma | ~ |
| Hermansa, Kozielski, Michalak, Szczyrba, Wrobel, Sikora. *Sensor-Based Predictive Maintenance with Reduction of False Alarms -- A Case Stu* | 2022 | Sensors (MDPI), 22(1):226 | confirma | ✓ |
| Barbariol, Susto. *TiWS-iForest: Isolation forest in weakly supervised and tiny ML scenarios* | 2022 | Information Sciences, 610:126-143 | matiza | ✓ |
| Siffer, Fouque, Termier, Largouet. *Anomaly Detection in Streams with Extreme Value Theory* | 2017 | ACM SIGKDD (KDD) 2017, pp. 1067-1075 | matiza | ✓ |
| Koizumi, Kawaguchi, Imoto, Nakamura, Nikaido, Tanabe, Purohi. *Description and Discussion on DCASE2020 Challenge Task2: Unsupervised Anomalous * | 2020 | DCASE2020 Workshop (arXiv 2006.05822) | matiza | ✓ |
| Bouman, Bukhsh, Heskes. *Unsupervised Anomaly Detection Algorithms on Real-world Data: How Many Do We Nee* | 2024 | Journal of Machine Learning Research, 25(105) | contexto | ✓ |
| Bouman, Heskes. *Autoencoders for Anomaly Detection are Unreliable* | 2025 | arXiv cs.LG 2501.13864 (preprint, sem publica | contexto | ✓ |

<details><summary>Achados detalhados</summary>

**Antonini, Pincheira, Vecchio, Antonelli (2023)** — An Adaptable and Unsupervised TinyML Anomaly Detection System for Extreme Industrial Environments  
`https://doi.org/10.3390/s23042344`  
Trabalho mais proximo do Kaelix: Isolation Forest TREINADO E EXECUTADO no proprio ESP32 (ESP32_WROVER_IE, firmware MicroPython), amostragem de acel+giro a 1125 Hz. Numeros: 84 KB de memoria na inferencia com ensemble de 50 arvores; ~1.570 KB no treino com 30 arvores; carregamento do modelo ate ~1 MB para 50 arvores; latencia de inferencia 20,33 +/- 7,17 ms (instancias normais) e 16,27 +/- 7,04 ms (anomalas); treino on-device 1,2-6,4 s para 10-50 arvores. PONTO CRITICO PARA A4: o limiar de deteccao NAO foi deixado no default -- foi FIXADO MANUALMENTE em 0,75 sobre o score normalizado do Isolation Forest, assumindo que a fase inicial de treino contem apenas comportamento normal. Os autores declaram explicitamente que avaliar a acuracia de deteccao esta fora do escopo do trabalho -- ou seja, nao ha FPR reportado.

**scikit-learn developers (2026)** — sklearn.ensemble.IsolationForest -- documentacao oficial (v1.9 estavel, acessada em ago/2026)  
`https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.IsolationForest.html`  
PROVA MECANICA DIRETA DE A4. Texto literal do atributo offset_: 'decision_function = score_samples - offset_. When the contamination parameter is set to "auto", the offset is equal to -0.5 as the scores of inliers are close to 0 and the scores of outliers are close to -1. When a contamination parameter different than "auto" is provided, the offset is defined in such a way we obtain the expected number of outliers (samples with decision function < 0) in training.' Consequencias: (1) contamination='auto' congela o corte em -0,5, um valor herdado da interpretacao do artigo original, NAO calibrado nos dados -- por isso pode marcar fracao arbitrariamente grande da operacao normal; (2) contamination altera SOMENTE o offset, nunca os scores brutos de score_samples -- logo qualquer metrica baseada em ranking (ROC-AUC) e matematicamente INVARIANTE ao parametro. Isso confirma exatamente o achado 'AUC=1,000 independente do parametro: ele so move o limiar'. Range permitido para float: (0, 0.5].

**Liu, Ting, Zhou (2008)** — Isolation Forest  
`https://doi.org/10.1109/ICDM.2008.17`  
Artigo fundador. Score s(x,n) = 2^(-E(h(x))/c(n)), com c(n) o comprimento medio de caminho em uma BST aleatoria de n nos. s -> 1 indica anomalia; s -> 0 indica normal denso; s ~ 0,5 corresponde a E(h(x)) ~ c(n), ou seja, ponto com profundidade tipica. Os autores usam 0,5 como REFERENCIA INTERPRETATIVA (se toda a amostra devolve s ~ 0,5, o conjunto nao tem anomalia distinta), nao como limiar operacional calibrado -- e exatamente esse 0,5 que o sklearn materializa como offset_=-0,5 no modo 'auto'. Defaults recomendados de ensemble: t=100 arvores, psi=256 (subamostragem), que os autores mostram ser robustos -- a robustez do iForest e nos parametros do ENSEMBLE, nao no limiar.

**Ma, Zhao, Zhang, Akoglu (2021)** — The Need for Unsupervised Outlier Model Selection: A Review and Evaluation of Internal Evaluation Strategies (A Large-scale Study on Unsupervised Outlier Model Selection: Do Internal Strategies Suffice?)  
`https://arxiv.org/abs/2104.01422`  
Responde diretamente a pergunta 'como escolher contamination sem rotulos'. Testbed com 39 tarefas de deteccao, 297 modelos candidatos (8 detectores x varias configuracoes de hiperparametros) e 7 estrategias internas de avaliacao (sem rotulos). Conclusao literal: nenhuma seria 'practically useful, as they select models only comparable to a state-of-the-art detector (with random configuration)'. Ou seja: NAO existe metodo label-free confiavel para escolher detector+hiperparametro; deixar no default e estatisticamente equivalente a sortear -- o que valida a critica de A4 ao contamination='auto' como escolha nao informada.

**Han, Hu, Huang, Jiang, Zhao (2022)** — ADBench: Anomaly Detection Benchmark  
`https://arxiv.org/abs/2206.09426`  
30 algoritmos (14 nao supervisionados, 7 semi-supervisionados, 9 supervisionados) x 57 datasets = 98.436 experimentos. Dois achados diretamente aplicaveis: (1) NENHUM algoritmo nao supervisionado e estatisticamente melhor que os outros -- a escolha do detector importa menos que o protocolo; (2) com apenas 1% de anomalias ROTULADAS, a maioria dos metodos semi-supervisionados ja supera o melhor metodo nao supervisionado. Implicacao pratica para o Kaelix: rotular alguns ensaios de falha (ex.: MAFAULDA) produz mais resultado que otimizar o Isolation Forest puro.

**Brito, Susto, Brito, Duarte (2021)** — An Explainable Artificial Intelligence Approach for Unsupervised Fault Detection and Diagnosis in Rotating Machinery  
`https://arxiv.org/abs/2102.11848`  
11 detectores nao supervisionados comparados (kNN, MCD, LOF, CBLOF, OCSVM, Descritor Bagging, FastABOD, Isolation Forest, HBOS, LODA, Ensemble) em 3 datasets de maquinas rotativas, com descritores de vibracao a 20 kHz (curtose, RMS, BPFI/BPFO/BSF, harmonicos 1x-4x) e explicabilidade via SHAP e Local-DIFFI. Numeros: IF com F1 97,19% e PR-AUC 99,92% (rolamento run-to-failure), F1 99,71% e PR-AUC 99,99% (caixa de engrenagens), F1 97,20% e PR-AUC 99,74% (faltas mecanicas). PONTO CRITICO: o limiar NAO veio de 'auto' -- em condicao estatica a razao de contaminacao era CONHECIDA e usada para definir o limiar; em condicao dinamica o limiar veio da hipotese 'o grupo de treino contem apenas sinais normais'. Alem disso reportam PR-AUC, nao so ROC-AUC.

**Hermansa, Kozielski, Michalak, Szczyrba, Wrobel, S (2022)** — Sensor-Based Predictive Maintenance with Reduction of False Alarms -- A Case Study in Heavy Industry  
`https://doi.org/10.3390/s22010226`  
Melhor evidencia de campo sobre taxa de falso alarme. Comparam HDBSCAN, LOF, Isolation Forest e One-Class SVM em sensores de vibracao (max e RMS) + temperatura de britadores de carvao (NW-10, NW-20) e porticos (S201, S202), mais um dataset sintetico de 30.000 observacoes. Numeros: o detector de outliers ISOLADO produziu metrica de falso positivo N entre 0,457 e 0,939 conforme o conjunto; adicionando adaptacao do modelo base + modelo de correcao, N caiu para 0,026-0,115, uma reducao MEDIA de 90,25% nos falsos alarmes. Ou seja: um detector nao supervisionado 'cru' e inaceitavel em campo, exatamente o cenario de A4.

**Barbariol, Susto (2022)** — TiWS-iForest: Isolation forest in weakly supervised and tiny ML scenarios  
`https://doi.org/10.1016/j.ins.2022.07.129`  
Unico trabalho encontrado que ataca o Isolation Forest especificamente para TinyML/microprocessadores ultra-restritos. Argumento central: 'the standard algorithm might be improved in terms of memory requirements, latency and performances', o que e critico em cenarios de baixo recurso e implementacoes TinyML. A solucao proposta NAO e mexer em contamination, e sim usar supervisao FRACA (poucos rotulos) para ranquear e podar as arvores do ensemble, reduzindo simultaneamente memoria, latencia e erro de deteccao. Codigo publico para reprodutibilidade. Preprint anterior: arXiv 2111.15432 (2021).

**Siffer, Fouque, Termier, Largouet (2017)** — Anomaly Detection in Streams with Extreme Value Theory  
`https://doi.org/10.1145/3097983.3098144`  
Alternativa metodologica principiada ao contamination. Os algoritmos SPOT/DSPOT usam Teoria de Valores Extremos (peaks-over-threshold / distribuicao de Pareto generalizada) para fixar o limiar SEM hipotese sobre a distribuicao dos dados e SEM limiar ajustado a mao. O unico parametro e o RISCO q, que controla diretamente a taxa de falsos positivos -- isto e, o engenheiro especifica o FPR desejado em vez de adivinhar a fracao de anomalias. E exatamente a substituicao que A4 pede para contamination='auto'.

**Koizumi, Kawaguchi, Imoto, Nakamura, Nikaido, Tana (2020)** — Description and Discussion on DCASE2020 Challenge Task2: Unsupervised Anomalous Sound Detection for Machine Condition Monitoring  
`https://arxiv.org/abs/2006.05822`  
Benchmark de referencia para o cenario EXATO do Kaelix: so ha dados normais no treino e as anomalias sao desconhecidas ('detect unknown anomalous sounds under the condition that only normal sound samples have been provided as training data'). 117 submissoes de 40 equipes. PROTOCOLO DE LIMIAR (o que substituir por contamination='auto'): o baseline autoencoder assume que o score de anomalia segue uma distribuicao GAMA, estima os parametros a partir do histograma dos scores dos dados NORMAIS de treino e define o limiar no PERCENTIL 90 dessa gama. Metrica primaria e AUC + pAUC (AUC parcial em faixa de baixa FPR), justamente porque AUC global sozinha nao caracteriza o ponto de operacao.

</details>

**Números citáveis:** MECANISMO (scikit-learn, doc oficial v1.9): contamination='auto' => offset_ = -0.5; decision_function = score_samples - offset_; float permitido apenas em (0, 0.5]; contamination redefine SO o offset, nunca score_samples => ROC-AUC invariante. | LIU/TING/ZHOU 2008 (ICDM, pp. 413-422): s(x,n)=2^(-E(h(x))/c(n)); s~0.5 <=> E(h(x))~c(n); defaults de ensemble t=100 arvores, psi=256 subamostras. | ANTONINI 2023 (Sensors 23(4):2344, ESP32 + IF em MicroPython): amostragem 1125 Hz; 84 KB de RAM na inferencia com 50 arvores; ~1.570 KB no treino com 30 arvores; carregamento de modelo ate ~1 MB (50 arvores); latencia 20,33 +/- 7,17 ms (normal) e 16,27 +/- 7,04 ms (anomalo); treino on-device 1,2-6,4 s (10-50 arvores); LIMIAR FIXADO EM 0,75 do score normalizado. | HERMANSA 2022 (Sensors 22(1):226): detector isolado com metrica de FP N = 0,457-0,939; com adaptacao+correcao N = 0,026-0,115; reducao media de falsos alarmes de 90,25%; dataset sintetico de 30.000 observacoes. | BRITO/SUSTO (MSSP 163:108105 / arXiv 2102.11848): 11 detectores; sinais a 20 kHz; IF F1 97,19% e PR-AUC 99,92% (rolamento), F1 99,71% e PR-AUC 99,99% (engrenagens), F1 97,20% e PR-AUC 99,74% (faltas mecanicas). | MA/AKOGLU: 39 tarefas, 297 modelos, 8 detectores, 7 estrategias internas, ZERO melhores que configuracao aleatoria. | ADBENCH (NeurIPS 2022): 30 algoritmos, 57 datasets, 98.436 experimentos; nenhum nao supervisionado estatisticamente superior; 1% de rotulos ja basta para semi-supervisionado bater o melhor nao supervisionado. | BOUMAN JMLR 2024, 25(105):1-34: 33 algoritmos x 52 datasets, EIF vence significativamente. | DCASE2020 Task 2 (Koizumi et al.): limiar = percentil 90 de uma GAMA ajustada aos scores dos dados normais de treino; metrica primaria AUC + pAUC (AUC parcial em faixa de baixa FPR); 117 submissoes de 40 equipes. | SIFFER KDD 2017 (pp. 1067-1075): SPOT/DSPOT via EVT, unico parametro = risco q que controla diretamente a taxa de falsos positivos. | REFERENCIA DE GESTAO DE ALARME (fonte NAO academica, verificar antes de citar): EEMUA 191 -- media recomendada de ~6 alarmes/hora por operador e pico de no maximo 10 alarmes por 10 minutos (inicio de 'alarm flood'); util para argumentar que 42% de janelas normais marcadas como anomalia e ordens de grandeza acima do tolerável.

**Lacunas neste eixo:** 1) NUMERO ORIGINAL SEM PRECEDENTE NA LITERATURA: nao encontrei nenhum trabalho que quantifique a FRACAO da operacao normal marcada como anomalia por contamination='auto' em vibracao industrial. Os 42% de voces parecem ser contribuicao original -- otimo para o TCC, mas exige que a metodologia (dataset, descritores, split) seja descrita com muito rigor, porque nao ha baseline publicado para comparar. 2) O trabalho mais proximo (Antonini et al., IF em ESP32) declara EXPLICITAMENTE que avaliar acuracia de deteccao esta fora do escopo -- ou seja, nao existe FPR publicado para Isolation Forest embarcado em MCU. Isso e um buraco que o Kaelix pode preencher. 3) Ninguem cruza as duas restricoes de voces ao mesmo tempo: acelerometro MEMS de banda limitada (MPU6050, Nyquist 500 Hz) + detector nao supervisionado embarcado + limiar calibrado para um FPR alvo. A literatura de vibracao usa 20-50 kHz (Brito: 20 kHz; MAFAULDA: 50 kHz), e a literatura TinyML usa banda baixa mas sem discutir o custo diagnostico dessa escolha (conexao direta com o achado A1 de voces). 4) NAO EXISTE NORMA que fixe taxa de falso alarme aceitavel para manutencao preditiva por vibracao: ISO 10816/20816 define severidade de VELOCIDADE, nao estatistica de alarme; EEMUA 191 e ISA-18.2 sao de alarmes de processo, nao de PdM. Qualquer numero de FPR aceitavel que voces adotarem precisa ser justificado por custo (razao custo de falso negativo : falso positivo, tipicamente citada como 20:1 a 100:1 em fontes de industria -- mas so achei isso em fontes NAO academicas, nao citem sem verificar). 5) Falta comparacao controlada IF vs OC-SVM vs autoencoder EM MCU com o MESMO orcamento de memoria E o MESMO protocolo de limiar; os papers comparam ou algoritmos (em PC) ou plataformas (sem controlar o limiar). 6) Nenhuma das bibliotecas de exportacao sklearn->C mais usadas (emlearn, micromlgen) documenta suporte a IsolationForest -- so a arvores/RF/SVM/NB; Antonini et al. contornaram isso implementando o IF diretamente em MicroPython. Se voces pretendem embarcar o IF, isso e um risco de implementacao que a literatura nao cobre e que vale registrar. 7) Nao encontrei nada sobre DERIVA (concept drift) do limiar do IF em motor industrial ao longo de meses -- carga, temperatura e regime mudam o score base, e nenhum dos papers de MCU faz recalibracao periodica.

---

## Eixo 2 — Vazamento de dados e avaliação em datasets de rolamento

**Achado confrontado:** A3 · **Veredito da busca:** ALINHADO

| Paper | Ano | Veículo | Relação | Meta |
|---|---|---|---|---|
| Vieira, Bauler, Rosa, Silva. *Towards a more realistic evaluation of machine learning models for bearing fault* | 2026 | Mechanical Systems and Signal Processing, v.  | confirma | ✓ |
| Hendriks, Dumond, Knox. *Towards better benchmarking using the CWRU bearing fault dataset* | 2022 | Mechanical Systems and Signal Processing, v.  | confirma | ✓ |
| Varejão, Costa, Silva, Rodrigues, Ribeiro, Varejão, Oliveira. *The similarity bias problem: What it is and how it impacts vibration based intel* | 2025 | Mechanical Systems and Signal Processing, v.  | confirma | ✓ |
| Wheat, von Mohrenschildt, Habibi, Al-Ani. *Impact of Data Leakage in Vibration Signals Used for Bearing Fault Diagnosis* | 2024 | IEEE Access, v. 12, p. 169879-169895 | confirma | ✓ |
| Abburi, Chaudhary, Ilyas, Manne, Mittal, Williams, Snaidauf,. *A Closer Look at Bearing Fault Classification Approaches* | 2023 | Annual Conference of the PHM Society, v. 15 ( | matiza | ✓ |
| Rauber, Loca, Boldt, Rodrigues, Varejão. *An experimental methodology to evaluate machine learning methods for fault diagn* | 2021 | Expert Systems with Applications, v. 167, art | confirma | ✓ |
| Matania, Cohen, Bechhoefer, Bortman. *Test-Training Leakage in Evaluation of Machine Learning Algorithms for Condition* | 2024 | PHM Society European Conference, v. 8, n. 1,  | confirma | ✓ |
| Knap, Jachymczyk, Lalik. *Leakage-Safe, Reproducible Benchmarking for Vibration-Based Fault Diagnosis* | 2026 | PHM Society European Conference, v. 9, n. 1 | confirma | ✓ |
| Smith, Randall. *Rolling element bearing diagnostics using the Case Western Reserve University da* | 2015 | Mechanical Systems and Signal Processing, v.  | contexto | ✓ |
| Zhao, Li, Wu, Sun, Wang, Yan, Chen. *Deep learning algorithms for rotating machinery intelligent diagnosis: An open s* | 2020 | ISA Transactions, v. 107, p. 224-255 | matiza | ✓ |
| Fan, Jiang, Zhang, Zheng, Lv, Han, Liang, Li, Zhang, Qian, C. *FISHER: A Foundation Model for Multi-Modal Industrial Signal Comprehensive Repre* | 2026 | IEEE Transactions on Industrial Informatics ( | confirma | ~ |
| Shamim, Nuruzzaman, Ferdus, Ahmed, Anward, Tooneer, Khan, Ho. *Leakage-Robust Evaluation and Data-Scale Sensitivity of Attention-Enhanced Multi* | 2026 | arXiv (submetido a Next Research, Elsevier) | confirma | ✓ |

<details><summary>Achados detalhados</summary>

**Vieira, Bauler, Rosa, Silva (2026)** — Towards a more realistic evaluation of machine learning models for bearing fault diagnosis  
`https://doi.org/10.1016/j.ymssp.2026.114640 (preprint: https://arxiv.org/abs/2509.22267)`  
Paper-espelho do nosso A3, com numeros quase identicos. Experimento controlado (treino FIXO, so o conjunto de teste muda, eliminando o confundidor 'menos dados de treino'). CWRU: protocolo sem vazamento da Macro AUROC 63,17% +/- 10,84% (tempo), 64,34% +/- 9,29% (frequencia), 63,89% +/- 9,26% (envelope); com vazamento de nivel de rolamento (split condition-wise) sobe para 100,00% +/- 0,00%, 99,96% +/- 0,13% e 99,79% +/- 0,54%; com vazamento de segmentacao, 100,00% nos tres casos (p entre 7,1e-8 e 1,7e-8). PU: sem vazamento 54,25% +/- 17,79% (tempo) / 61,25% (freq) / 76,98% (envelope); condition-wise +32,6 p.p. (86,88%/92,27%/87,79%); repetition-wise 98,57%/100,00%/99,99% (+44,3 p.p.); segmentacao 98,56%/100%/100%. UORED-VAFCLS: sem vazamento 87,25%/90,21%/87,34%; vazamento de rolamento +3,0/+3,9/+6,4 p.p.; vazamento de segmentacao +12,6/+9,8/+12,5 p.p. (chega a 99,88%/100,00%/99,88%). Taxonomia formal: 'segmentation-level leakage' vs 'bearing-level leakage' (este ultimo com sub-tipos condition-wise e repetition-wise). Survey: 195 artigos MSSP de 2025 recuperados, 18 analisados em detalhe - 8 (44%) usaram split aleatorio, 9 (50%) condition-wise, 1 (6%) nao especificou; citam trabalhos anteriores que reportam problemas de particao em >90% dos artigos publicados. Toy problem com 48 rolamentos: teto teorico de acuracia 90,30%, e os testes com vazamento EXCEDERAM esse teto (prova de memorizacao). NUANCE CRITICA PARA NOS: sob split correto no CWRU (Tabela 10), o Random Forest com descritores de tempo+envelope chegou a 85,06% +/- 8,92% Macro AUROC, contra 63,22% +/- 10,24% do WDCNN - modelos rasos degradam MENOS que deep learning sob particao honesta. Outra ressalva: no experimento CWRU eles tiveram de EXCLUIR todos os sinais saudaveis, pois o CWRU tem uma unica configuracao de rolamento saudavel e nao ha como fazer split bearing-wise da classe normal.

**Hendriks, Dumond, Knox (2022)** — Towards better benchmarking using the CWRU bearing fault dataset  
`https://doi.org/10.1016/j.ymssp.2021.108732`  
Paper-semente da critica moderna ao CWRU (158 citacoes no Semantic Scholar). Argumenta que o procedimento aceito de montar treino e teste com CONDICOES DE OPERACAO diferentes (0/1/2/3 hp) NAO constitui um problema real de domain shift, porque os MESMOS rolamentos fisicos aparecem nos dois conjuntos. Propoe um framework alternativo de benchmark que constroi treino e teste com conjuntos INDEPENDENTES de rolamentos. E a origem da distincao 'variacao de condicao != variacao de componente' que sustenta o nosso A3. Limitacao apontada por Vieira et al. (2026): a estrategia por tamanho de falha de Hendriks nao elimina o vazamento da classe saudavel, que continua sendo dividida por carga.

**Varejão, Costa, Silva, Rodrigues, Ribeiro, Varejão (2025)** — The similarity bias problem: What it is and how it impacts vibration based intelligent fault diagnosis  
`https://doi.org/10.1016/j.ymssp.2025.112822`  
Cunha o termo 'similarity bias' para o fenomeno que chamamos de vazamento por janela. Levantamento sistematico: de 41 estudos revisados que usam o CWRU (publicados entre 2008 e 2020), 40 empregaram desenho experimental suscetivel a esse vies - ou seja, ~97,6% da literatura CWRU daquele periodo e otimista por construcao. Compara modelos convencionais e de deep learning sob estrategia de validacao cruzada que controla o vies, e mostra quantitativamente que o similarity bias produz resultados otimistas. Grupo brasileiro (UFES), mesmo grupo do Rauber et al. (2021) que usa MAFAULDA - terminologia util e citavel em portugues/ingles.

**Wheat, von Mohrenschildt, Habibi, Al-Ani (2024)** — Impact of Data Leakage in Vibration Signals Used for Bearing Fault Diagnosis  
`https://doi.org/10.1109/ACCESS.2024.3497716`  
Quantifica o vazamento com metodos SEM modelo treinado pesado - exatamente o regime do KAELIX. Aplica 6 metodos classicos de diagnostico (PCA, SPCA e LDA combinados com analise em frequencia e analise de envelope) a 2 datasets (McMaster e Paderborn) sob 3 estrategias de particao: run-to-run, day-to-day e part-to-part. Reporta variacoes de desempenho SUPERIORES A 40 PONTOS PERCENTUAIS de acuracia dependendo apenas da estrategia de particao, expondo domain shifts nao identificados anteriormente (inclusive shift entre DIAS de aquisicao, nao so entre pecas). Recomenda protocolos melhores de desenho experimental e avaliacao. A nomenclatura run-to-run / day-to-day / part-to-part e mais granular que o nosso 'split por ensaio' e vale adotar.

**Abburi, Chaudhary, Ilyas, Manne, Mittal, Williams, (2023)** — A Closer Look at Bearing Fault Classification Approaches  
`https://arxiv.org/abs/2309.17001 | https://papers.phmsociety.org/index.php/phmconf/article/view/3473`  
Fonte de numeros diretos e NUANCE IMPORTANTE contra a magnitude do nosso A3. Classificacao multiclasse no CWRU, comparando split por rolamento vs split aleatorio: SVM+STFT cai de 0,851 (aleatorio) para 0,700 (por rolamento) de acuracia; Naive Bayes+RFFT cai de 0,858 para 0,695. No XJTU: SVM+STFT 0,988 -> 0,890; NB+RFFT 0,910 -> 0,728. Ou seja, a queda observada por eles no CWRU e de ~15 p.p., NAO ~36 p.p. como no nosso A3. Alertam explicitamente que estudos anteriores (citam nominalmente Zhao et al. 2020) usaram split aleatorio atribuindo registros do MESMO rolamento a treino, validacao e teste. Tambem defendem F-score/metricas de desbalanceamento em vez de acuracia pura, e o uso de dummy classifiers como baseline - recomendacao diretamente aplicavel ao nosso relatorio.

**Rauber, Loca, Boldt, Rodrigues, Varejão (2021)** — An experimental methodology to evaluate machine learning methods for fault diagnosis based on vibration signals  
`https://doi.org/10.1016/j.eswa.2020.114022`  
UNICO paper de metodologia de avaliacao encontrado que usa explicitamente MAFAULDA E CWRU juntos - exatamente a nossa combinacao de datasets. Estabelece um procedimento sistematico para comparar de forma justa scores experimentais de metodos de ML sobre sinais de vibracao. Afirma que o desenho experimental da maioria das publicacoes da area e enviesado, baseado em metodos de validacao inaceitavelmente simples e na reciclagem de padroes identicos no conjunto de teste que ja foram usados no treino, o que torna a classificacao uma tarefa facil. E uma das duas fontes (junto com Varejão et al. 2025) das quais Vieira et al. (2026) tiram a estatistica de problemas de particao em >90% dos artigos publicados. 93 citacoes.

**Matania, Cohen, Bechhoefer, Bortman (2024)** — Test-Training Leakage in Evaluation of Machine Learning Algorithms for Condition-Based Maintenance  
`https://doi.org/10.36001/phme.2024.v8i1.4125`  
Artigo curto e didatico, dedicado exclusivamente ao problema: em muitos trabalhos de ML para manutencao baseada em condicao, especialmente classificacao de falhas de rolamento, a separacao de exemplos entre teste e treino esta incorreta, levando a conclusao otimista sobre o desempenho do algoritmo quando o desempenho real e menor. Propoe divisao guiada por TAMANHO DE FALHA (fault-size guided splitting) aplicada a CWRU e PU. Ressalva registrada por Vieira et al. (2026): essa estrategia nao e aplicavel a datasets em que o mesmo rolamento aparece sob multiplos tamanhos de falha (ex.: UORED-VAFCLS), e no CWRU ela nao resolve a classe saudavel. Util como citacao curta e de autoridade (Bechhoefer e referencia em PHM industrial).

**Knap, Jachymczyk, Lalik (2026)** — Leakage-Safe, Reproducible Benchmarking for Vibration-Based Fault Diagnosis  
`https://doi.org/10.36001/phme.2026.v9i1.4924`  
Benchmark reprodutivel e livre de vazamento para diagnostico cross-domain, com codigo aberto (github.com/1Sensor/pdm-bench). Afirma que particao em nivel de JANELA e cenarios fonte-alvo mal definidos levam a conclusoes excessivamente otimistas. Define 6 cenarios fonte-alvo fixos com separacao treino-teste em NIVEL DE GRAVACAO (recording-level) sobre CWRU e Paderborn. Achado que nos e util como nuance: a dificuldade dos cenarios e altamente heterogenea - alguns cenarios de transferencia estao efetivamente saturados enquanto outros permanecem substancialmente mais dificeis. Isso sugere que reportar um unico numero medio (como nosso 63,2% +/- 19,2%) esconde variancia estrutural, e que o desvio-padrao alto que observamos e esperado. Tambem nota que modelos de deep learning frequentemente atingem desempenho superior mas suas conclusoes sao sensiveis a inicializacao.

**Smith, Randall (2015)** — Rolling element bearing diagnostics using the Case Western Reserve University data: A benchmark study  
`https://doi.org/10.1016/j.ymssp.2015.04.021`  
Critica FUNDACIONAL ao CWRU, anterior a discussao de ML, com 2443 citacoes. Aplica tres tecnicas classicas de diagnostico a TODO o dataset CWRU e classifica cada registro em categorias de diagnosticabilidade: Y1 (claramente diagnosticavel com caracteristicas classicas no tempo e na frequencia), Y2 (claramente diagnosticavel mas com caracteristicas nao-classicas), P1 (provavelmente diagnosticavel - componentes discretos nas frequencias de falha esperadas mas nao dominantes no espectro de envelope), P2 (potencialmente diagnosticavel - componentes borrados que parecem coincidir com as frequencias esperadas), N1 (nao diagnosticavel para a falha especificada, mas com outros problemas identificaveis como folga/looseness) e N2 (nao diagnosticavel e praticamente indistinguivel de ruido). Consequencia direta para nos: parte dos registros CWRU e ROTULADA como falha mas nao contem assinatura de falha detectavel - portanto uma acuracia de 99% em split aleatorio e literalmente impossivel por via fisica, o que e evidencia independente de que aquele numero e memorizacao. Fornece recomendacoes de como usar os dados para testar novos algoritmos.

</details>

**Números citáveis:** NUMEROS DIRETAMENTE CITAVEIS (todos extraidos de fonte primaria aberta e conferidos):

--- Vieira, Bauler, Rosa & Silva, MSSP v.258, art. 114640 (2026) --- espinha dorsal da nossa argumentacao
CWRU, Tabela 13 (experimento controlado, treino fixo, so o teste muda), Macro AUROC:
  sem vazamento: 63,17% +/- 10,84% (tempo) | 64,34% +/- 9,29% (frequencia) | 63,89% +/- 9,26% (envelope)
  vazamento de nivel de rolamento (condition-wise): 100,00% +/- 0,00% | 99,96% +/- 0,13% | 99,79% +/- 0,54%
  vazamento de segmentacao: 100,00% | 100,00% | 100,00%
  p-valores (teste t pareado unicaudal): 7,11e-8 | 1,93e-8 a 2,02e-8 | 1,88e-8 a 1,70e-8
PU, Tabela 12, Macro AUROC:
  sem vazamento: 54,25% +/- 17,79% | 61,25% +/- 17,96% | 76,98% +/- 8,51%
  condition-wise: 86,88% +/- 14,55% | 92,27% +/- 11,80% | 87,79% +/- 18,50%  (ganho de 32,6 p.p. no dominio do tempo)
  repetition-wise: 98,57% +/- 2,15% | 100,00% +/- 0,00% | 99,99% +/- 0,01%   (ganho de 44,3 p.p. no dominio do tempo)
  segmentacao: 98,56% +/- 2,16% | 100,00% | 100,00% +/- 0,01%
UORED-VAFCLS, Tabela 11, Macro AUROC:
  sem vazamento: 87,25% +/- 6,03% | 90,21% +/- 5,57% | 87,34% +/- 7,71%
  vazamento de rolamento: +3,0 / +3,9 / +6,4 p.p. -> 90,23% | 94,15% | 93,79%
  vazamento de segmentacao: +12,6 / +9,8 / +12,5 p.p. -> 99,88% +/- 0,39% | 100,00% +/- 0,00% | 99,88% +/- 0,39%
CWRU sob protocolo correto, Tabela 10 (Macro AUROC) - NUMERO-CHAVE PARA DEFENDER MODELOS RASOS:
  WDCNN tempo 63,22% +/- 10,24% | WDCNN frequencia 70,90% +/- 8,95% | WDCNN envelope 74,51% +/- 9,43%
  Random Forest (tempo + espectro de envelope) 85,06% +/- 8,92% | SVM 81,06% +/- 6,76%
Survey de prevalencia: 195 artigos MSSP de 2025 recuperados; 18 analisados; 8 (44%) split aleatorio; 9 (50%) condition-wise; 1 (6%) nao especificado.
Toy problem: 48 rolamentos simulados, 24 saudaveis / 24 com falha, 40 amostras por rolamento, 3 descritores preditivas + 48 descritores de identidade (51 no total); teto teorico de acuracia = 90,30%; testes com vazamento EXCEDERAM esse teto.
Numero de sinais de treino nos experimentos: ~24 (UORED), ~700 (PU), apenas 3 (CWRU); overlap de 75%, 0% e 95% respectivamente.
Codigo: github.com/gama-ufsc/bearing-data-leakage

--- Abburi et al., PHM Society Conference v.15 (2023) --- a faixa BAIXA da queda
CWRU multiclasse, acuracia (split por rolamento vs split aleatorio):
  SVM + STFT: 0,700 vs 0,851  (F-macro 0,658 vs 0,865)
  Naive Bayes + RFFT: 0,695 vs 0,858  (F-macro 0,693 vs 0,833)
XJTU multiclasse:
  SVM + STFT: 0,890 vs 0,988 | Naive Bayes + RFFT: 0,728 vs 0,910

--- Wheat, von Mohrenschildt, Habibi & Al-Ani, IEEE Access v.12, p.169879-169895 (2024) ---
Variacoes de desempenho SUPERIORES A 40 PONTOS PERCENTUAIS de acuracia dependendo apenas da metodologia de particao. 6 metodos (PCA, SPCA, LDA x analise de frequencia e de envelope), 2 datasets (McMaster, Paderborn), 3 particoes (run-to-run, day-to-day, part-to-part).

--- Varejão et al., MSSP v.235, art. 112822 (2025) ---
40 de 41 estudos revisados que usam CWRU (2008-2020) empregaram desenho experimental suscetivel a similarity bias (~97,6%).

--- Rauber et al. (2021) + Varejão et al. (2025), via Vieira et al. ---
Problemas de particao de dados em MAIS DE 90% dos artigos publicados na area.

--- Shamim et al., arXiv:2607.16493 (2026) --- corroboracao secundaria
Split ingenuo infla a acuracia de 20-60% genuinos para 99,9%. C-MAPSS com 19.976 janelas livres de vazamento: 84,12% +/- 0,96%.

--- MAFAULDA, pagina oficial UFRJ (verificada) --- para a secao de materiais e para a ameaca a validade
1951 sequencias | 50 kHz | 5 s por amostra (250.000 pontos) | 8 canais (1 tacometro, 6 acelerometros IMI 601A01 e 604B31 em underhang e overhang com 3 eixos cada, 1 microfone) | 737 a 3686 rpm (passos de ~60 rpm), ou seja 12,3 a 61,4 Hz de frequencia de eixo.
Distribuicao de classes: normal 49 | desalinhamento horizontal 197 | desalinhamento vertical 301 | desbalanceamento 333 | falha de rolamento underhang 558 | falha de rolamento overhang 513.
APENAS 3 ROLAMENTOS DEFEITUOSOS (um por elemento: pista externa, esferas/gaiola, pista interna) em 2 posicoes; massas adicionais de 0, 6, 20 e 35 g; desbalanceamento 6-35 g; desalinhamento 0,5-2,0 mm (horizontal) e 0,51-1,90 mm (vertical).

--- Smith & Randall, MSSP v.64-65, p.100-131 (2015) --- 2443 citacoes
Categorias de diagnosticabilidade de cada registro CWRU: Y1, Y2 (diagnosticavel), P1, P2 (parcial), N1, N2 (nao diagnosticavel; N2 = indistinguivel de ruido).

--- Contagens de citacao (Semantic Scholar, ago/2026), uteis para justificar escolha de referencias ---
Smith & Randall 2015: 2443 | Zhao et al. 2020: 301+ | Hendriks et al. 2022: 158 | Rauber et al. 2021: 93 | Wheat et al. 2024: 8 | Varejão et al. 2025: 4

**Lacunas neste eixo:** 1) VAZAMENTO EM DETECCAO NAO-SUPERVISIONADA DE ANOMALIA: toda a literatura de vazamento encontrada trata de classificacao SUPERVISIONADA. Nao localizei nenhum paper que analise vazamento de dados em one-class / Isolation Forest / autoencoder para rolamentos. Como o KAELIX combina Isolation Forest (A4) com particao por grupo (A3), essa interacao nao tem precedente direto - o que e simultaneamente uma lacuna e uma oportunidade de contribuicao original do TCC. Em particular, ninguem discute que treinar o detector so em 'normal' e depois particionar por rolamento e impossivel no CWRU (unica configuracao saudavel) e no MAFAULDA (49 sequencias normais de uma unica montagem).

2) O CWRU NAO PERMITE SPLIT LIMPO DA CLASSE SAUDAVEL: Vieira et al. tiveram de EXCLUIR completamente os sinais saudaveis do experimento de vazamento no CWRU (Secao 6.3), porque o dataset contem uma unica configuracao de rolamento saudavel. Isso significa que nenhum protocolo GroupKFold no CWRU consegue ser honesto na tarefa binaria normal-vs-falha, que e exatamente a tarefa do KAELIX. Hendriks (2022) e Abburi (2023) tambem falham nesse ponto especifico. Nao existe solucao publicada - so a alternativa de usar outro dataset.

3) MAFAULDA E ESTRUTURALMENTE PIOR QUE O CWRU PARA GroupKFold POR ROLAMENTO: confirmei na pagina oficial (www02.smt.ufrj.br/~offshore/mfs) que o MAFAULDA tem 1951 sequencias, 50 kHz, 5 s (250.000 amostras), 8 canais, 737-3686 rpm, mas apenas TRES rolamentos defeituosos (um por elemento: pista externa, esferas/gaiola, pista interna) montados em duas posicoes (underhang/overhang), mais uma unica configuracao normal (49 sequencias). Logo, split bearing-wise e literalmente IMPOSSIVEL no MAFAULDA: com 1 rolamento por classe de falha, treinar e testar em rolamentos disjuntos zera o treino. O maximo possivel e split por rotacao/carga (condition-wise) ou por arquivo - e a literatura classifica ambos como vazamento de nivel de rolamento (no PU isso inflou 32,6 p.p.). Nenhum paper que encontrei faz essa critica ao MAFAULDA explicitamente; a unica fonte que aplica protocolo anti-vazamento a ele e o FISHER (IEEE TII), e mesmo assim so em nivel de gravacao ('sealed split'), nao de rolamento. Isso deve ser declarado como AMEACA A VALIDADE no TCC, nao escondido.

4) NENHUM ESTUDO DE VAZAMENTO EM BAIXA TAXA DE AMOSTRAGEM / MEMS: todos os benchmarks usam acelerometros piezoeletricos a 12, 48, 50 ou 64 kHz. Nao ha nada sobre como o vazamento se comporta quando a banda e limitada a 1 kHz (nosso A1). Hipotese nao testada na literatura e testavel por nos: com banda reduzida, restam menos assinaturas fisicas de falha e MAIS peso relativo para artefatos de identidade do sensor/montagem, o que tenderia a AUMENTAR o ganho ilusorio do split aleatorio. Cruzar A1 com A3 seria contribuicao inedita.

5) SEM LITERATURA SOBRE VAZAMENTO EM DISPOSITIVOS IoT DE BORDA: nenhum dos papers avalia o cenario de deployment real do KAELIX (um dispositivo colado permanentemente em UM motor especifico). Ha inclusive um contra-argumento legitimo nao publicado que precisamos enderecar de forma honesta: se o dispositivo e calibrado por motor, o cenario de deployment e mais proximo de 'mesmo rolamento, condicao futura' do que de 'rolamento nunca visto', o que tornaria o split bearing-wise pessimista DEMAIS para o nosso caso de uso. A resposta correta e reportar AMBOS os numeros e declarar qual cenario cada um representa - nao escolher o mais conveniente.

6) SEM CONSENSO SOBRE METRICA: Abburi et al. e Vieira et al. defendem Macro AUROC / F-score em vez de acuracia por causa do desbalanceamento, e Abburi recomenda reportar tambem dummy classifiers como baseline. Nosso A3 reporta acuracia. Falta na literatura uma recomendacao consolidada para o caso binario normal-vs-anomalia com prevalencia realista (falha rara), que e o nosso caso.

---

## Eixo 3 — Banda de acelerômetros MEMS para falha de rolamento

**Achado confrontado:** A1 · **Veredito da busca:** ALINHADO

| Paper | Ano | Veículo | Relação | Meta |
|---|---|---|---|---|
| Randall, Antoni. *Rolling element bearing diagnostics—A tutorial* | 2011 | Mechanical Systems and Signal Processing (MSS | confirma | ✓ |
| Fidali, Augustyn, Ochmann, Uchman. *Evaluation of the Diagnostic Sensitivity of Digital Vibration Sensors Based on C* | 2024 | Sensors (MDPI) | confirma | ✓ |
| Jakobsen. *Low cost MEMS accelerometer and microphone based condition monitoring sensor, wi* | 2024 | HardwareX | confirma | ✓ |
| Kolok, Hodon, Sevcik, Hotz, Remy. *Low-Cost IoT-Based Predictive Maintenance Using Vibration* | 2025 | Sensors (MDPI) | confirma | ✓ |
| Albarbar, Mekid, Starr, Pietruszkiewicz. *Suitability of MEMS Accelerometers for Condition Monitoring: An experimental stu* | 2008 | Sensors (MDPI) | confirma | ✓ |
| Hu, Xiang, Xu, Lin. *Frequency Loss and Recovery in Rolling Bearing Fault Detection* | 2019 | Chinese Journal of Mechanical Engineering | confirma | ✓ |
| El Bouharrouti, Morinigo-Sotelo, Belahcen. *Multi-Rate Vibration Signal Analysis for Bearing Fault Detection in Induction Ma* | 2024 | Machines (MDPI) | contradiz | ✓ |
| Maruthi, Hegde. *Application of MEMS Accelerometer for Detection and Diagnosis of Multiple Faults* | 2016 | IEEE Sensors Journal | matiza | ✓ |
| Antoni, Randall. *The spectral kurtosis: application to the vibratory surveillance and diagnostics* | 2006 | Mechanical Systems and Signal Processing (MSS | confirma | ✓ |
| Landi, Prato, Fort, Mugnaini, Vignoli, Facello, Mazzoleni, M. *Highly Reliable Multicomponent MEMS Sensor for Predictive Maintenance Management* | 2023 | Micromachines (MDPI) | confirma | ✓ |
| Antoni. *Fast computation of the kurtogram for the detection of transient faults* | 2007 | Mechanical Systems and Signal Processing (MSS | confirma | ✓ |
| Sharma, Kaur, Mangal, Kohli. *Investigating bearing and gear vibrations with a Micro-Electro-Mechanical System* | 2024 | Results in Engineering | confirma | ✓ |

<details><summary>Achados detalhados</summary>

**Randall, Antoni (2011)** — Rolling element bearing diagnostics—A tutorial  
`https://doi.org/10.1016/j.ymssp.2010.07.017`  
Referência canônica do envelope/HFRT. Estabelece que o defeito localizado gera impactos que excitam ressonâncias estruturais de ALTA frequência (tipicamente kHz), e que a informação diagnóstica (BPFO/BPFI/BSF) está na MODULAÇÃO dessa banda, não no espectro direto. O procedimento recomendado é: pré-branqueamento -> seleção de banda de ressonância -> demodulação de envelope -> espectro de envelope. MSSP 25(2):485-520.

**Fidali, Augustyn, Ochmann, Uchman (2024)** — Evaluation of the Diagnostic Sensitivity of Digital Vibration Sensors Based on Capacitive MEMS Accelerometers  
`https://doi.org/10.3390/s24144463`  
É O PAPER MAIS PRÓXIMO DE A1. Comparou 2 sensores MEMS comerciais (SE1 Balluff BCM0002: 2–2500 Hz, ±16 g; SE2 Banner QM30VT2: 10–4000 Hz) contra piezo de referência PCB T352C34 (0,5–10 kHz) em 11 rolamentos de esferas (6 sadios, 5 com defeito induzido: pista externa, interna, elemento rolante, gaiola). Conclusão explícita: a sensibilidade diagnóstica DEPENDE DO LIMITE SUPERIOR DE BANDA do sensor. Pico e pico-a-pico foram os descritores mais sensíveis; RMS mais sensível a falha de lubrificação. CURTOSE E FATOR DE CRISTA tiveram sensibilidade MENOR nos MEMS que no piezo, especialmente para dano de gaiola. Veredito dos autores: MEMS de 2,5–4 kHz servem para monitoramento contínuo de falhas de intensidade média-alta, mas o piezo de 10 kHz é superior para dano incipiente. Sensors 24(14):4463.

**Jakobsen (2024)** — Low cost MEMS accelerometer and microphone based condition monitoring sensor, with LoRa and Bluetooth Low Energy radio  
`https://doi.org/10.1016/j.ohx.2024.e00525`  
EVIDÊNCIA ARQUITETURAL DIRETA para A1, e o hardware mais parecido com o KAELIX (LoRa + MCU baixo custo + bateria). O autor usa DOIS acelerômetros com papéis separados: ADXL1002 (25 ug/sqrt(Hz), resposta plana DC–11 kHz, ressonância 21 kHz, amostrado a 40 kHz) para DEFEITO DE ROLAMENTO INCIPIENTE; e ADXL362 (550 ug/sqrt(Hz), até 200 Hz, ODR 400 Hz) explicitamente apenas para DESBALANCEAMENTO e rotação (<200 Hz). Ou seja: um projetista de sensor IoT low-cost com as mesmas restrições do KAELIX concluiu que um acelerômetro de baixa banda/alto ruído NÃO serve para rolamento e adicionou um segundo sensor de 11 kHz. Defeito de pista externa confirmado com Fo e harmônicos na faixa 0–700 Hz do espectro de envelope. HardwareX 18:e00525.

**Kolok, Hodon, Sevcik, Hotz, Remy (2025)** — Low-Cost IoT-Based Predictive Maintenance Using Vibration  
`https://doi.org/10.3390/s25216610`  
RESPOSTA DIRETA A "MPU6050 SERVIU PARA QUAIS FALHAS?". Protótipo ESP32-C6 + MPU6050 (mesmo sensor e classe de MCU do KAELIX). Os autores avaliaram APENAS DESBALANCEAMENTO MECÂNICO (obstrução deliberada de roda) — nenhuma falha de rolamento. Descritores: RMS e energia espectral por FFT (Welch). Acurácia global ~73% (72,9% +/- 2,4% em 5-fold CV), recall >67%. O MPU6050 opera internamente a 1 kHz mas o streaming efetivo do protótipo foi ~2 Hz. O paper reconhece que MEMS operam em bandas úteis "até dezenas de kHz dependendo do modelo" e restringe a análise a desbalanceamento de baixa frequência, sem especificação quantitativa para rolamento. Sensors 25(21):6610.

**Albarbar, Mekid, Starr, Pietruszkiewicz (2008)** — Suitability of MEMS Accelerometers for Condition Monitoring: An experimental study  
`https://doi.org/10.3390/s8020784`  
Estudo seminal de "MEMS serve ou não serve". Três MEMS capacitivos anonimizados vs piezo ICP de referência (1–2000 Hz, 100 mV/g). Faixas: MEMS(A) 1–6000 Hz, MEMS(B) 1–10000 Hz, MEMS(C) 1500 Hz. O MEMS(C), justamente o de banda mais estreita, apresentou distorção substancial, sensibilidade instável (63–111 mV/g) e má linearidade de resposta em frequência, sendo declarado INADEQUADO para monitoramento de condição de máquinas. A e B foram satisfatórios acima de ~150 Hz, mas com "muito ruído, incluindo picos extras não interpretáveis". Sensors 8(2):784-799.

**Hu, Xiang, Xu, Lin (2019)** — Frequency Loss and Recovery in Rolling Bearing Fault Detection  
`https://doi.org/10.1186/s10033-019-0349-3`  
Fornece as frequências de ressonância REAIS medidas em bancada de rolamento: respostas ressonantes identificadas na faixa 1000–4000 Hz (picos em ~1500 Hz, ~2800 Hz e ~4000 Hz), com amostragem a 12,8 kHz e 12 kHz. TODAS estão acima do Nyquist de 500 Hz do MPU6050 a 1 kHz — sustenta numericamente A1. Mostra ainda que as próprias frequências características (BPFO 97,2 Hz e BPFI 162,8 Hz no N205) podem DESAPARECER do espectro FFT por cancelamento de fase entre múltiplas respostas ressonantes ("frequency loss"), mesmo com banda adequada. Fator de atenuação xi=600 na simulação; recuperação com filtro morfológico combinado eleva a amplitude ~5x. CJME 32:35.

**El Bouharrouti, Morinigo-Sotelo, Belahcen (2024)** — Multi-Rate Vibration Signal Analysis for Bearing Fault Detection in Induction Machines Using Supervised Learning Classifiers  
`https://doi.org/10.3390/machines12010017`  
CONTRA-EVIDÊNCIA MAIS FORTE CONTRA A1. Reamostrou sinais de vibração de 48 kHz até 1 kHz por downsampling fracionário e treinou modelos lineares, tree-based (XGBoost) e redes neurais (LSTM) para 10 condições de falha de rolamento. Conclusão dos autores: "melhores acurácias de treino NÃO são sistematicamente obtidas ao treinar com sinais amostrados em frequência relativamente alta" — depende do algoritmo. Motivação explícita: empresas querem reduzir a resolução do sensor para cortar custo. Descritores p2p e RMS foram as mais discriminantes entre sadio e falho. RESSALVA CRÍTICA PARA O TCC: é classificação supervisionada em dataset de laboratório com falhas semeadas, sem controle de vazamento por ensaio (ver A3), e não é diagnóstico físico de BPFO — a alta acurácia pode vir de assinatura de banda larga/estado do ensaio, não da frequência característica. Machines 12(1):17.

**Maruthi, Hegde (2016)** — Application of MEMS Accelerometer for Detection and Diagnosis of Multiple Faults in the Roller Element Bearings of Three Phase Induction Motor  
`https://doi.org/10.1109/JSEN.2015.2476561`  
NUANCE IMPORTANTE. Detectou múltiplas falhas em rolamentos de motor de indução trifásico usando acelerômetro MEMS de baixo custo (ADXL322JCP, faixa de banda selecionável na casa de poucos kHz) com FFT do espectro DIRETO de vibração — sem envelope. As frequências características de falha e as bandas laterais em torno da fundamental aparecem no espectro, sob condições de sem carga, monofasamento e tensão desbalanceada. Ou seja: o espectro direto com MEMS de banda modesta DETECTA rolamento quando o defeito já é severo/semeado — coerente com o "contraste 20x" de A1 (não é zero), mas sem demonstração de detecção incipiente nem comparação de contraste contra envelope. IEEE Sensors J. 16(1):145-152. (Conteúdo extraído de resumo/abstract; não abri o PDF completo.)

**Antoni, Randall (2006)** — The spectral kurtosis: application to the vibratory surveillance and diagnostics of rotating machines  
`https://doi.org/10.1016/j.ymssp.2004.09.002`  
Formaliza a curtose espectral: a curtose NÃO é um número global útil, e sim uma FUNÇÃO da frequência — ela indica em QUAL banda os transientes repetitivos do defeito são impulsivos. Isso é o fundamento teórico do argumento de A1: a curtose calculada no sinal de banda base 0–500 Hz mede a impulsividade de uma banda onde o defeito quase não tem energia; a curtose útil vive na banda de ressonância. MSSP 20(2):308-331.

**Landi, Prato, Fort, Mugnaini, Vignoli, Facello, Ma (2023)** — Highly Reliable Multicomponent MEMS Sensor for Predictive Maintenance Management of Rolling Bearings  
`https://doi.org/10.3390/mi14020376`  
Mostra o que a comunidade considera "MEMS adequado para rolamento": cubo com três ADXL1005Z ortogonais, banda 10 Hz–25 kHz (banda de exatidão 10% em 12 kHz), amostragem 50 kHz na calibração e 160 kHz nos ensaios de falha, referência piezo B&K 4426. Frequências de falha emuladas: BPFO 361 Hz, BPFI 488 Hz, BSF 161 Hz — todas de baixa frequência, MAS a detecção depende das respostas ressonantes de até 10 kHz. Isto é o contraste exato de A1: as frequências-alvo cabem em 500 Hz, o mecanismo de deteccao nao cabe. Micromachines 14(2):376.

</details>

**Números citáveis:** BANDAS DE SENSOR (para tabela comparativa do TCC): MPU6050 ODR 1 kHz -> Nyquist 500 Hz, ~400 ug/sqrt(Hz) (datasheet, seu projeto). ADXL362: 550 ug/sqrt(Hz) em +/-2 g, medição até 200 Hz, ODR 400 Hz — usado SÓ para desbalanceamento/rotação (Jakobsen 2024). ADXL1002: 25 ug/sqrt(Hz) em +/-50 g, resposta plana DC–11 kHz, ressonância 21 kHz, amostrado a 40 kHz — usado para rolamento incipiente (Jakobsen 2024). ADXL1001: 30 ug/sqrt(Hz), +/-100 g (datasheet ADI). ADXL1005Z: 10 Hz–25 kHz, banda de exatidão 10% em 12 kHz (Landi 2023). Balluff BCM0002: 2–2500 Hz; Banner QM30VT2: 10–4000 Hz; PCB T352C34 (piezo ref.): 0,5–10000 Hz (Fidali 2024). Piezo ICP de referência: 1–2000 Hz, 100 mV/g (Albarbar 2008). MEMS testados por Albarbar 2008: 1–6000 Hz, 1–10000 Hz e 1500 Hz (este último REPROVADO para CM). TAXAS DE AMOSTRAGEM: ADXL1002 a 40 kHz (Jakobsen 2024); 50 kHz na calibração e 160 kHz nos ensaios de falha (Landi 2023); 12,8 kHz e 12 kHz (Hu 2019); MAFAULDA 50 kHz, 5 s, 1951 séries multivariadas; CWRU 12 kHz e 48 kHz; El Bouharrouti varreu 48 kHz -> 1 kHz. RESSONÂNCIAS DE ROLAMENTO MEDIDAS: 1500, 2800 e 4000 Hz (faixa 1000–4000 Hz), Hu 2019. Faixa geral citada na área: ressonâncias excitadas por impacto tipicamente 1–30 kHz; filtragem de envelope tipicamente 500 Hz–20 kHz. FREQUÊNCIAS CARACTERÍSTICAS (mostram que o alvo é baixa frequência mas o mecanismo não): BPFO 361 Hz, BPFI 488 Hz, BSF 161 Hz (Landi 2023); BPFO 97,2 Hz e BPFI 162,8 Hz no N205 a 1440 rpm (Hu 2019). DESEMPENHO: MPU6050 + ESP32-C6, só desbalanceamento: 72,9% +/- 2,4% (5-fold CV), recall >67% (Kolok 2025); recuperação de amplitude ~5x com filtro morfológico (Hu 2019); limiar de acurácia de 95% adotado como referência de projeto de dataset por Sehri & Dumond, IJPHM 16(2), 2025, DOI 10.36001/ijphm.2025.v16i2.4372. NORMATIVO: ISO 13373-1/-2 recomenda ACELERAÇÃO como grandeza para rolamentos e engrenagens (falhas de alta frequência) e indica 10 kHz como limite superior adequado, podendo ser AUMENTADO para rolamentos/engrenagens, mesmo além da faixa linear recomendada pelo fabricante do transdutor — contraste direto com os 500 Hz do KAELIX.

**Lacunas neste eixo:** 1) NINGUÉM PUBLICOU O NÚMERO QUE VOCÊS TÊM. Não encontrei nenhum trabalho que quantifique a degradação do CONTRASTE DIAGNÓSTICO (razão pico-BPFO/ruído de fundo) como função contínua da banda do sensor, com o mesmo sinal, mesmo defeito e mesma métrica. A literatura fala em "early vs late stage", "sensível vs insensível", "banda de 2,5 kHz vs 10 kHz" — qualitativo. O par 413x (envelope na ressonância, 20 kHz) vs 20x (espectro direto, 1 kHz) é contribuição original e citável. 2) O ARTEFATO DE ALIASING NA CURTOSE NÃO ESTÁ NA LITERATURA REVISADA POR PARES DE ROLAMENTO. A observação de que, sem DLPF, 3,5 kHz dobra para 500 Hz e a curtose "parece" separar as classes só aparece descrita em notas de aplicação de fabricante (Analog Devices, "Elusive Tones: Aliasing Effects in Digital MEMS Accelerometers in Condition Monitoring") e em material técnico de instrumentação, nunca em MSSP/TII/Measurement como um resultado experimental de rolamento. Isso é um GAP publicável do TCC. 3) Nenhum estudo caracteriza o MPU6050 (ou qualquer IMU de consumo com ODR de 1 kHz) em falha de rolamento com antialiasing correto e comparação de curtose/fator de crista com e sem DLPF. Os trabalhos com MPU6050 param em desbalanceamento/desalinhamento. 4) Não achei análise de detectabilidade limitada por densidade de ruído (defeito mínimo detectável em função de ug/sqrt(Hz)) para IMUs de consumo — o MPU6050 a ~400 ug/sqrt(Hz) é ~16x mais ruidoso que o ADXL1002 (25 ug/sqrt(Hz)) e ~1,3x menos ruidoso que o ADXL362 (550 ug/sqrt(Hz), usado só para <200 Hz por Jakobsen). 5) O tema A1 x A3 é órfão: nenhum dos trabalhos de "MEMS de baixa banda funciona com ML" usa split por ensaio/GroupKFold, então as acurácias altas em baixa taxa de amostragem (El Bouharrouti) não estão validadas contra vazamento. 6) Não achei benchmark aberto com sinais gravados SIMULTANEAMENTE por MEMS de baixa banda e piezo no mesmo ponto de medição, que permitiria isolar o efeito de banda do efeito de montagem (A5).

---

## Eixo 4 — ISO 10816/20816 e integração aceleração→velocidade

**Achado confrontado:** A2 · **Veredito da busca:** ALINHADO

| Paper | Ano | Veículo | Relação | Meta |
|---|---|---|---|---|
| ISO/TC 108/SC 2 (norma internacional). *ISO 20816-3:2022 — Mechanical vibration — Measurement and evaluation of machine * | 2022 | ISO International Standard | confirma | ✓ |
| ISO/TC 108/SC 2 (norma internacional). *ISO 10816-3:2009 — Mechanical vibration — Evaluation of machine vibration by mea* | 2009 | ISO International Standard | confirma | ✓ |
| ISO/TC 108/SC 2 (norma internacional). *ISO 2954:2012 — Mechanical vibration of rotating and reciprocating machinery — R* | 2012 | ISO International Standard | confirma | ✓ |
| Brandt, Brincker. *Integrating time signals in frequency domain — Comparison with time domain integ* | 2014 | Measurement (Elsevier), vol. 58, pp. 511-519 | confirma | ✓ |
| Fidali, Augustyn, Ochmann, Uchman. *Evaluation of the Diagnostic Sensitivity of Digital Vibration Sensors Based on C* | 2024 | Sensors (MDPI), 24(14), art. 4463 | matiza | ✓ |
| Analog Devices (autoria individual NAO confirmada — pagina d. *MEMS Vibration Monitoring: From Acceleration to Velocity* | 2019 | Analog Dialogue (literatura tecnica de fabric | confirma | ✗ |
| Rodrigues, Pedroso, Silva, Leao Junior. *Performance evaluation of accelerometers ADXL345 and MPU6050 exposed to random v* | 2021 | Research, Society and Development, 10(15) (pe | contexto | ✓ |
| Albarbar, Mekid, Starr, Pietruszkiewicz. *Suitability of MEMS Accelerometers for Condition Monitoring: An Experimental Stu* | 2008 | Sensors (MDPI), 8(2), pp. 784-799 | contexto | ✓ |
| Landi, Prato, Fort, Mugnaini, Vignoli, Facello, Mazzoleni, M. *Highly Reliable Multicomponent MEMS Sensor for Predictive Maintenance Management* | 2023 | Micromachines (MDPI), 14(2), art. 376 | contexto | ✓ |
| Kolok, Hodon, Sevcik, Hotz, Remy. *Low-Cost IoT-Based Predictive Maintenance Using Vibration* | 2025 | Sensors (MDPI), 25(21), art. 6610 | contexto | ~ |

<details><summary>Achados detalhados</summary>

**ISO/TC 108/SC 2 (norma internacional) (2022)** — ISO 20816-3:2022 — Mechanical vibration — Measurement and evaluation of machine vibration — Part 3: Industrial machinery with a power rating above 15 kW and operating speeds between 120 r/min and 30 000 r/min  
`https://www.iso.org/standard/76652.html (texto verificado em copia integral do PDF ISO-20816-3-2022)`  
Fonte primaria lida integralmente. Clausula 4.3: o equipamento 'shall be capable of measuring broad-band root-mean-square (r.m.s.) vibration with flat response over a frequency range of at least 10 Hz to 1 000 Hz' (limite inferior <=2 Hz para maquinas proximas ou abaixo de 600 r/min). Mesma clausula: 'Where accelerometers are mounted on stationary parts of the machine (as is common practice), their output SHALL be integrated to provide a velocity signal' — e adverte que a dupla integracao para deslocamento 'may be used ... but caution shall be exercised due to the possibility of introducing high noise levels. High pass filtering and/or alternative digital computation of the displacement value can provide more accurate values.' Anexo A: zonas SO em velocidade e deslocamento RMS. Grupo 1 (>300 kW; H>=315 mm) rigido A/B 2,3 | B/C 4,5 | C/D 7,1 mm/s; flexivel 3,5 | 7,1 | 11,0 mm/s. Grupo 2 (15-300 kW; 160 mm<=H<315 mm) rigido 1,4 | 2,8 | 4,5 mm/s; flexivel 2,3 | 4,5 | 7,1 mm/s. Deslocamentos (22/45/71 um no Grupo 2 rigido) sao CALCULADOS da velocidade assumindo frequencia dominante de 10 Hz (Grupo 2) ou 12,5 Hz (Grupo 1). Anexo D da a justificativa fisica: 'vibration with the same r.m.s. velocity in the frequency range 10 Hz to 1 000 Hz can generally be considered to be of equal severity' e explicita que 'if displacement or acceleration were used for evaluation, the assessment criteria would vary with frequency'. Escopo: potencia >15 kW, 120 a 30 000 r/min; substitui ISO 10816-3:2009 + ISO 7919-3:2009.

**ISO/TC 108/SC 2 (norma internacional) (2009)** — ISO 10816-3:2009 — Mechanical vibration — Evaluation of machine vibration by measurements on non-rotating parts — Part 3: Industrial machines with nominal power above 15 kW and nominal speeds between 120 r/min and 15 000 r/min when measured in situ  
`https://www.iso.org/standard/50528.html (texto verificado em copia integral do PDF iso_10816_3_2009)`  
Fonte primaria lida integralmente. Clausula 3.2 (Measurement equipment): 'shall be capable of measuring broad-band root-mean-square (r.m.s.) vibration with flat response over a frequency range of at least 10 Hz to 1 000 Hz in accordance with the requirements of ISO 2954'; para maquinas proximas/abaixo de 600 r/min o limite inferior nao pode ser maior que 2 Hz. NOTA da mesma clausula: 'If the measurement equipment is also to be used for diagnostic purposes, an upper frequency limit higher than 1 000 Hz may be necessary.' Anexo A: 'At present, however, vibration zone boundary values are given ONLY in terms of velocity and displacement' e 'The limits apply to the broad-band r.m.s. values of vibration velocity and displacement in the frequency range from 10 Hz to 1 000 Hz, or for machines with speeds below 600 r/min from 2 Hz to 1 000 Hz.' NOTA 3 da Tabela A.2: 'At present it is not common practice to monitor the acceleration value of these machines.' Tabelas A.1/A.2 identicas as da ISO 20816-3:2022 (Grupo 2 rigido 1,4/2,8/4,5 mm/s). Grupo 1 = >300 kW ou H>=315 mm (mancais de deslizamento, 120-15 000 r/min); Grupo 2 = 15-300 kW ou 160<=H<315 mm (rolamentos, >600 r/min).

**ISO/TC 108/SC 2 (norma internacional) (2012)** — ISO 2954:2012 — Mechanical vibration of rotating and reciprocating machinery — Requirements for instruments for measuring vibration severity  
`https://www.iso.org/standard/21835.html (texto verificado na amostra oficial cdn.standards.iteh.ai/samples/21835)`  
Norma de instrumentacao invocada explicitamente pela ISO 10816-3 e ISO 20816-3. Fonte primaria (amostra oficial) lida. Clausula 5.3: 'The measurement frequency range of the vibration severity measuring instrument shall be from 10 Hz to 1 000 Hz but can include other ranges.' Clausula 5.4 + Tabela 2: a sensibilidade na banda passante nao pode desviar mais que os limites tabelados — NOTA 2: 'The limits in the pass-band are maintained from ISO 2954:1975 to be 10 % limits, here expressed in decibels' (+0,83 dB / -0,92 dB de ~12,6 Hz a 1 000 Hz, i.e. +-10%; a 10 Hz a sensibilidade NOMINAL ja e -3,01 dB = 0,707, com tolerancia +-2 dB). O elemento limitador de banda e um par de Butterworth de 3a ordem com f1=10 Hz (Q1=Q3=1/2) e f2=1 000 Hz (Q2=Q4=1/raiz2). Instrumento indica r.m.s. de VELOCIDADE em mm/s (Tabela 1). Clausula final: 'To avoid errors, it is necessary to state the 3 dB cut-off frequencies for the measurement frequency range as well as the measured value, e.g. vrms (2 Hz to 1 000 Hz) = 7,5 mm/s.'

**Brandt, Brincker (2014)** — Integrating time signals in frequency domain — Comparison with time domain integration  
`https://doi.org/10.1016/j.measurement.2014.09.004 (metadados confirmados no repositorio institucional Aarhus University Pure e SDU findresearcher)`  
Paper-semente do eixo. Compara 4 metodos: (i) DFT -> divisao por jw -> IDFT; (ii) weighted overlap-add (WOLA); (a) regra do trapezio; (b) filtro IIR otimizado. Conclusoes: o metodo 'intuitivo' DFT/jw/IDFT e o melhor para registros acima de ~16K amostras, com o filtro IIR otimizado com exatidao comparavel; WOLA e aceitavel em regime permanente mas deve ser evitado em transientes (problema de coerencia); e — literalmente — 'integration by the trapezoidal rule should be avoided, as it gives biased results, particularly for higher frequencies'. IMPORTANTE para o TCC: o vies do trapezio identificado por Brandt e um erro de AMPLITUDE dependente de frequencia (atenuacao crescente rumo a Nyquist), mecanismo DIFERENTE da deriva por offset/bias DC; nosso A2 mistura os dois.

**Fidali, Augustyn, Ochmann, Uchman (2024)** — Evaluation of the Diagnostic Sensitivity of Digital Vibration Sensors Based on Capacitive MEMS Accelerometers  
`https://doi.org/10.3390/s24144463`  
Unico paper encontrado que aplica explicitamente a banda 10-1000 Hz da ISO 20816 com sensores MEMS de banda limitada. Sensores comparados: SE1 (Balluff BCM0002, MEMS 3 eixos, 2-2 500 Hz, +-16 g, exatidao +-10% de 2 a 1 800 Hz), SE2 (Banner QM30VT2, MEMS 2 eixos, 10-4 000 Hz, +-10% a 25 C) contra referencia piezoeletrica PCB T352C34 (0,5-10 000 Hz, aquisicao a 100 kS/s, 10 s por medicao). 11 rolamentos rigidos de esferas (6 sadios, 5 com defeitos) a 600, 1 500 e 3 000 rpm. Achado central: 'the diagnostic sensitivity of the parameters depends on the upper-frequency band limit of the sensors'; os parametros mais sensiveis a falhas de fadiga sao pico e pico-a-pico de ACELERACAO, nao a vRMS. Referencia ISO 13373-3, ISO 10816/20816 e VDI 3832. Nuance para A2: sensores MEMS com Nyquist >=1,25 kHz conseguem entregar vRMS 10-1000 Hz conforme; o MPU6050 a 1 kHz ODR (Nyquist 500 Hz) fica abaixo desse patamar.

**Analog Devices (autoria individual NAO confirmada  (2019)** — MEMS Vibration Monitoring: From Acceleration to Velocity  
`https://www.analog.com/en/resources/analog-dialogue/articles/mems-vibration-monitoring-acceleration-to-velocity.html`  
Fonte do orcamento de ruido que falta na literatura academica. Numeros recorrentes em multiplos espelhos: para resolver a severidade na zona 'boa' (A) de uma maquina Classe 2 da ISO 10816-1 (VMIN = 1,12 mm/s), a 10 Hz o ruido de aceleracao precisa ser MENOR que 7,18 mg; o ADXL357, com filtro de banda de ruido de 10 Hz, resolve o menor nivel da ISO 10816-1 (0,28 mm/s) em ~1,5 Hz a 1 000 Hz. Reafirma que 'ISO 10816 uses rms velocity (10 Hz to 1 kHz) of the machine housing as a condition indicator' e que acelerometros exigem conversao para mm/s. ATENCAO DE CITACAO: nao consegui abrir a fonte primaria (analog.com bloqueou); autor e volume/numero da Analog Dialogue nao confirmados. Citar como literatura tecnica de fabricante, nunca como paper peer-reviewed.

</details>

**Números citáveis:** BANDA E INSTRUMENTACAO: resposta plana exigida "at least 10 Hz to 1 000 Hz" (ISO 10816-3:2009 cl. 3.2; ISO 20816-3:2022 cl. 4.3); limite inferior <=2 Hz para maquinas proximas/abaixo de 600 r/min; banda de avaliacao 2-1000 Hz para maquinas <600 r/min. ISO 2954:2012: tolerancia de banda passante +-10% (+0,83 dB / -0,92 dB) de ~12,6 Hz a 1 000 Hz; sensibilidade NOMINAL a 10 Hz = -3,01 dB (0,707) com tolerancia +-2 dB; limitacao de banda = Butterworth 3a ordem, f1=10 Hz (Q1=Q3=1/2), f2=1 000 Hz (Q2=Q4=1/raiz2); frequencia de referencia 79,4 Hz (ou ~160 Hz = 1000 rad/s); obrigacao de declarar os cortes de 3 dB junto ao valor. ZONAS (mm/s RMS, identicas em ISO 10816-3:2009 e ISO 20816-3:2022): Grupo 1 (>300 kW; H>=315 mm) rigido 2,3 / 4,5 / 7,1 e flexivel 3,5 / 7,1 / 11,0; Grupo 2 (15-300 kW; 160<=H<315 mm) rigido 1,4 / 2,8 / 4,5 e flexivel 2,3 / 4,5 / 7,1. Deslocamentos correspondentes Grupo 2 rigido 22 / 45 / 71 um, calculados da velocidade assumindo frequencia dominante de 10 Hz (12,5 Hz no Grupo 1). ESCOPO: ISO 20816-3:2022 vale para P>15 kW e 120-30 000 r/min; ISO 10816-3:2009 para 15 kW-50 MW e 120-15 000 r/min. INTEGRACAO: Brandt & Brincker 2014 — DFT/jw/IDFT e o melhor metodo para registros >16K amostras; filtro IIR otimizado com exatidao comparavel; WOLA so em regime permanente; trapezio "biased ... particularly for higher frequencies". RUIDO: para resolver a zona A da Classe 2 da ISO 10816-1 (VMIN=1,12 mm/s), a 10 Hz o ruido de aceleracao deve ser <7,18 mg; ADXL357 resolve 0,28 mm/s de ~1,5 a 1 000 Hz (fonte: Analog Dialogue, literatura de fabricante, metadados nao verificados). DERIVACAO NOSSA (nao e da literatura, marcar como calculo proprio): MPU6050 a 400 ug/raizHz integrado em 990 Hz => ~12,6 mg RMS, ~1,8x ACIMA do orcamento de 7,18 mg — o sensor nao resolve a fronteira A/B nem antes de considerar a banda. MEMS COMPARATIVOS: Fidali 2024 — Balluff BCM0002 2-2 500 Hz (+-10% de 2-1 800 Hz), Banner QM30VT2 10-4 000 Hz, referencia PCB T352C34 0,5-10 000 Hz a 100 kS/s; Landi 2023 — ADXL1005Z 10 Hz-25 kHz, banda de exatidao 10% ate 12 kHz, 2,004 mV/(m s^-2) a 10 Hz, calibracao ISO 16063-21:2003; Albarbar 2008 — MEMS C com sensibilidade medida 37-111 mV/g contra 450-550 mV/g de datasheet.

**Lacunas neste eixo:** (1) NENHUM paper quantifica o erro percentual de integracao no tempo vs frequencia especificamente para a metrica vRMS 10-1000 Hz da ISO 10816/20816. Brandt & Brincker quantificam o vies do trapezio de forma generica (deslocamento/velocidade em analise modal), nao no criterio da norma. Nossos numeros (+73%, +156%, +716%) nao tem equivalente publicado — isso e uma contribuicao real do TCC, e nao ha com o que confronta-los. (2) Nao existe estudo que meca quanto da energia de vRMS de um motor industrial esta na faixa 500-1000 Hz, ou seja, quanto um dispositivo truncado em 500 Hz subestima a severidade. Essa e a lacuna mais explorravel: um experimento simples com MAFAULDA (fs=50 kHz) computando vRMS(10-1000 Hz) vs vRMS(10-500 Hz) daria o numero que a literatura nao tem. (3) Nao ha paper avaliando MPU6050 (ou classe equivalente de IMU de 1 kHz) contra criterio ISO de velocidade; Fidali 2024 e o mais proximo, mas seus MEMS tem 2 500 e 4 000 Hz de banda. (4) A literatura de baixo custo (Kolok 2025, ESP32) cita ISO 10816 sem implementar a integracao nem verificar a banda — ha um vazio de rigor normativo que o TCC pode ocupar. (5) Nao encontrei implementacao open-source auditavel de "omega arithmetic + banda ISO 2954" — so blocos proprietarios (Beckhoff TF3600, sensores IO-Link) e utilitarios genericos de FFT.

---

## Eixo 5 — Sistemas IoT comparáveis, invólucro e térmica

**Achado confrontado:** A6 · **Veredito da busca:** PARCIALMENTE_ALINHADO

| Paper | Ano | Veículo | Relação | Meta |
|---|---|---|---|---|
| Kolok, Hodoň, Ševčík, Hotz, Remy. *Low-Cost IoT-Based Predictive Maintenance Using Vibration* | 2025 | Sensors (MDPI), 25(21):6610 | matiza | ✓ |
| Chevtchenko, dos Santos, Vieira, Mota, Rocha, Cruz, Araújo, . *Predictive Maintenance Model Based on Anomaly Detection in Induction Motors: A M* | 2023 | Proc. 33rd European Safety and Reliability Co | confirma | ✓ |
| Jakobsen (Aarhus University). *Low cost MEMS accelerometer and microphone based condition monitoring sensor, wi* | 2024 | HardwareX, 18:e00525 (Elsevier, open hardware | contradiz | ✓ |
| Antonini, Pincheira, Vecchio, Antonelli (FBK). *An Adaptable and Unsupervised TinyML Anomaly Detection System for Extreme Indust* | 2023 | Sensors (MDPI), 23(4):2344 | matiza | ✓ |
| Bently Nevada / Baker Hughes. *Ranger Pro Wireless Condition Monitoring Datasheet (125M5237 Rev. U)* | 2024 | Datasheet de fabricante | contradiz | ✓ |
| TRACTIAN. *Smart Trac Datasheet - Automated Machine Monitoring* | 2023 | Datasheet de fabricante (referencia de mercad | contradiz | ✓ |
| Erbessd Instruments. *PHANTOM Gen 3 Vibration Sensor Datasheet (EPH-V10E / EPH-V11E, rev. 11/2025)* | 2025 | Datasheet de fabricante | matiza | ✓ |
| Nabavi, Hajforoosh, Nabavi. *Battery Selection for Energy-Efficient IoT Devices: A Comparative Study of Longe* | 2025 | International Journal of Electrochemistry (Wi | contradiz | ✓ |
| Ma, Jiang, Tao, Song, Wu, Wang, Deng, Shang. *Temperature effect and thermal impact in lithium-ion batteries: A review* | 2018 | Progress in Natural Science: Materials Intern | confirma | ✓ |
| Ūselis, Serackis, Pomarnacki (Vilnius Gediminas TU). *Signal Processing Optimization in Resource-Limited IoT for Fault Prediction in R* | 2025 | Electronics (MDPI), 14(18):3670 | contexto | ✓ |
| Bisio, Garibotto, Grattarola, Iscra, Lavagetto, Sciarrone, Z. *Design, Implementation and Performance of an IIoT Node for Vibration Monitoring* | 2025 | IEEE International Symposium on Circuits and  | contexto | ✓ |
| Kumar, Terauds, Ajayakumar Raji, Semenako, Smolaninovs, Sics. *Design of a Lightweight Edge-AI System for Predictive Maintenance on ESP32-S3* | 2026 | Applied Sciences (MDPI), 16(11):5287 | contexto | ✓ |

<details><summary>Achados detalhados</summary>

**Kolok, Hodoň, Ševčík, Hotz, Remy (2025)** — Low-Cost IoT-Based Predictive Maintenance Using Vibration  
`10.3390/s25216610`  
Sistema quase identico ao KAELIX: ESP32-C6 + MPU6050 + Isolation Forest com contamination='auto' e 100 arvores, custo de hardware <30 EUR e <300 mW. Configuraram o DLPF interno do MPU6050 em 5 Hz. Resultado: acuracia ~73% (precision 0,755; recall 0,679; F1 0,715; ROC-AUC 0,780), validacao cruzada 5-fold 72,9% +/- 2,4%, ~900 amostras, UM unico tipo de falha (desbalanceamento por obstrucao parcial de roda). Limiar F1-otimo 0,018338 e limiar de recall maximo 0,089770. Nao discutem ISO 10816 nem banda util. Confirma que a arquitetura KAELIX e publicavel, e que na literatura ela entrega ~73%, nao 99%.

**Chevtchenko, dos Santos, Vieira, Mota, Rocha, Cruz (2023)** — Predictive Maintenance Model Based on Anomaly Detection in Induction Motors: A Machine Learning Approach Using Real-Time IoT Data  
`10.3850/978-981-18-8071-1_P578-cd`  
Dispositivo IoT brasileiro com ESP32, IMU ISM330DLCTR amostrada a 1 kHz (mesmo teto do MPU6050), 2 microfones SPH0645LM4H-B a 20 kHz montados no interior da carcaca (um embaixo, um em cima) e ima de neodimio na estrutura 'forte o bastante para fixar em qualquer superficie de aco'. Dataset proprio: 3 motores de 1 hp a 1000 rpm, 3750 amostras normais + 2250 anomalas. Resultados (validacao/teste): Isolation Forest sensibilidade 88,9/86,3% e ESPECIFICIDADE 61,6/67,4% (ou seja, 32,6%-38,6% da operacao NORMAL marcada como anomalia); LOF 90,8/77,6% e 74,5/72,1%; OC-SVM 73,1/47,9% e 63,4/36,5%. Inferencia: IF 21,40 ms, LOF 0,81 ms, OC-SVM 0,43 ms. Notam que o Motor 3 (1 ano de uso) tem assinatura normal diferente dos motores 1 e 2 (lote novo).

**Jakobsen (Aarhus University) (2024)** — Low cost MEMS accelerometer and microphone based condition monitoring sensor, with LoRa and Bluetooth Low Energy radio  
`10.1016/j.ohx.2024.e00525`  
No open-hardware mais proximo do KAELIX, o pe e o suporte de PCB sao de ALUMINIO usinado CNC, escolhidos explicitamente 'for thermal stability and stiffness'; so a tampa e impressa em 3D. Diz que a versao integralmente impressa em 3D e possivel mas o aluminio e preferido 'for mechanical transmission of vibrations'. Sensores: ADXL1002 (banda plana ate 11 kHz, ressonancia 21 kHz, 40 kHz de amostragem, 25 ug/sqrt(Hz)) + microfone ultrassonico 100 Hz-80 kHz a 100 kHz + ADXL362 (ate 200 Hz, 550 ug/sqrt(Hz)) para desbalanceamento. Bateria: LiSOCl2 AA LS14500 (PRIMARIA, ~700 Wh/kg) + supercapacitor de 100 mF para o pico de 120 mA do LoRa a 22 dBm. BOM US$180. Detectaram defeito de 5x0,5x0,25 mm na pista externa de um SKF2206 por envelope (Hilbert+FFT). Reportam autoressonancias de PCB/mecanica em 6-9 kHz.

**Antonini, Pincheira, Vecchio, Antonelli (FBK) (2023)** — An Adaptable and Unsupervised TinyML Anomaly Detection System for Extreme Industrial Environments  
`10.3390/s23042344`  
Isolation Forest treinado E executado DENTRO do ESP32 (WROVER-IE, 4 MB SPIRAM), IMU ICM-20948 amostrada a 1125 Hz, 10 descritores temporais incluindo energia via Parseval. Ponto critico para o A4: NAO usam contamination automatico - fixam um LIMIAR NORMALIZADO de score IF em 0,75, com minimo de 100 instancias para massa critica. Custos: inferencia 6,9-20,33 ms (10-50 arvores), 70,8-84,8 kB de RAM, treino 1,2-6,4 s e 536-1576 kB. Declaram explicitamente que 'uma avaliacao da acuracia de deteccao esta fora do escopo'. Apesar do titulo 'extreme industrial environments' (bomba submersa em ETE), NAO fornecem faixa de temperatura nem detalham involucro ('vamos projetar um involucro' fica como trabalho futuro).

**Bently Nevada / Baker Hughes (2024)** — Ranger Pro Wireless Condition Monitoring Datasheet (125M5237 Rev. U)  
`https://www.instrumart.com/assets/Bently-Nevada-Ranger-Pro-Datasheet.pdf`  
Referencia de mercado premium, li o PDF inteiro. Elemento sensor PIEZOELETRICO ceramico, +/-20 g pico. Aceleracao: eixo Z 5 Hz-10 kHz (+/-3 dB), X/Y 5 Hz-4 kHz; Fmax selecionavel 200/500/1000/2000/5000/10000 Hz. VELOCIDADE: 5-2000 Hz, 0-50 mm/s, Fmax 200/500/1000/2000 Hz (cobre integralmente a banda ISO 10816 de 10-1000 Hz). PeakDemod (envelope) so no eixo Z, Fmax ate 5000 Hz, banda minima de demodulacao 500/1000/2000/5000 Hz. Bateria: LiSOCl2 D 3,6 V SUBSTITUIVEL (Tadiran TLH-5930 etc.), ate 5 anos. Temperatura de operacao do aparelho -40 a 85 C, MAS a faixa Ta para area classificada e definida PELA BATERIA: -40 a 80 C (TLH-5930) ou -40 a 70 C (TL-5930/XL-205F/SL-2780) - 'operar em temperaturas extremas afeta negativamente a vida da bateria e pode danificar o sensor'. Carcaca: corpo em aco inox 316 + topo em PPS reforcado com vidro (alta temperatura, resistente a solvente e UV). Fixacao: rosca interna M6x1 mm x 5 mm (STUD), nao ima. 88 mm x 40 mm, 230 g sem bateria / 300 g com. IP67. Limite de vibracao 20 g pico.

**TRACTIAN (2023)** — Smart Trac Datasheet - Automated Machine Monitoring  
`https://tractian-webpage.s3.amazonaws.com/website/pages/sensor-inteligente/en/Datasheet_EN.pdf`  
Li o PDF. Corpo metalico com ressalto de centragem metalico; marcacao no proprio corpo: 90 C / -10 C, IP69K. Fixacao NAO INVASIVA por Ima, Rosca ou Epoxi - mas o texto diz explicitamente que 'o ima ajuda no processo de instalacao' e que 'idealmente a base deve ser COLADA no ativo para evitar queda e AUMENTAR A QUALIDADE DA AQUISICAO DE DADOS' (cola bicomponente acompanha o sensor). Ha ainda porca de travamento. Energia: bateria de LITIO PRIMARIA, 3 anos de autonomia amostrando a cada 10 min. Radio 2,4 GHz para o Smart Receiver (que sobe por LTE). Medicoes: Velocidade E Aceleracao (RMS, Pico, Pico-a-Pico, Fator de Crista) + espectro de velocidade e aceleracao com Pico e ENVELOPE + temperatura + horimetro. Ferramentas de analise: BPF, BPFI, BPFO, BSF, FTF, GMF, harmonicas. Armazenamento offline 250 amostras. 1 Smart Receiver = 15 sensores, raio 30-50 m.

**Erbessd Instruments (2025)** — PHANTOM Gen 3 Vibration Sensor Datasheet (EPH-V10E / EPH-V11E, rev. 11/2025)  
`https://www.erbessd-instruments.com/datasheets/phantom/phantom_g3_datasheet.pdf`  
Li o PDF. Unico produto comercial encontrado com carcaca declaradamente PLASTICA: 'Housing material: ABS, stainless steel' - plastico so no corpo, aco inox na base, com fixacao por parafuso 1/4-28 UNF. 47x33 mm, 185 g, IP69, temperatura de operacao -40 a 80 C. EPH-V11E (alta faixa): 0,5 Hz-10 kHz (X,Y) e 0,5-5,1 kHz (Z), taxa de amostragem selecionavel 25.600/12.800/6.400/3.200/1.600 Hz com Fmax correspondente 10.000/5.000/2.500/1.250/625 Hz, resolucao 240 ug, ruido espectral 630 ug/sqrt(Hz) @10 Hz, +/-8/16/32 g. EPH-V10E (alta sensibilidade): 0,5-4 kHz (X,Y), 0,5-1,8 kHz (Z), 60 ug, 130 ug/sqrt(Hz), +/-2/4/8 g. Bateria de LITIO PRIMARIA CR2477, 65.000 medicoes, consumo 6-9 uA em standby; graficos de descarga a 0/20/60 C. BLE 5.0, 2,4 GHz, 100 m.

**Nabavi, Hajforoosh, Nabavi (2025)** — Battery Selection for Energy-Efficient IoT Devices: A Comparative Study of Longevity Across Environmental Conditions  
`10.1155/ijel/7783200`  
Framework comparativo de escolha de bateria para IoT avaliando densidade de energia, auto-descarga, faixas de tensao e TEMPERATURA, custo e confiabilidade. Conclusao direta contra a escolha do KAELIX: recomendam Li-SOCl2 (primaria) para 'implantacoes de longo prazo e baixa potencia em AMBIENTES EXTREMOS, pela vida util e estabilidade superiores', e reservam as quimicas recarregaveis (LFP, NCA, NMC) para 'aplicacoes de alta potencia que exigem ciclagem frequente'. Um no de manutencao preditiva com 2,0 mW medios cai exatamente na primeira categoria.

</details>

**Números citáveis:** BANDA DE SENSORES COMERCIAIS (todos verificados em datasheet primario): Bently Nevada Ranger Pro - aceleracao Z 5 Hz-10 kHz (+/-3 dB), X/Y 5 Hz-4 kHz, Fmax 200/500/1000/2000/5000/10000 Hz; VELOCIDADE 5-2000 Hz, 0-50 mm/s, Fmax 200/500/1000/2000 Hz; PeakDemod (envelope) ate 5000 Hz com banda minima de demodulacao de 500/1000/2000/5000 Hz; +/-20 g pico; elemento piezoeletrico ceramico. Erbessd Phantom EPH-V11E - 0,5 Hz-10 kHz (X,Y), 0,5-5,1 kHz (Z), amostragem 25.600 Hz, resolucao 240 ug, ruido 630 ug/sqrt(Hz) @10 Hz; EPH-V10E - 0,5-4 kHz (X,Y), 0,5-1,8 kHz (Z), 60 ug, 130 ug/sqrt(Hz). TRACTIAN Smart Trac - amostragem ate 32 kHz, mede velocidade E aceleracao com RMS/Pico/Pico-a-Pico/Fator de Crista + espectro com envelope, ferramentas BPF/BPFI/BPFO/BSF/FTF/GMF. Petasense VM3 - 2 a 5.500 Hz +/-3 dB, amostragem 26,7 kHz, 16 bits (NAO VERIFIQUEI EM FONTE PRIMARIA - confirmar em petasense.com antes de citar). CONTRASTE DIRETO: o MPU6050 a 1 kHz de ODR (Nyquist 500 Hz) fica de 8x a 20x abaixo do piso comercial, e o Ranger Pro sozinho cobre a banda ISO 10816 de velocidade (10-1000 Hz) inteira, enquanto o KAELIX cobre metade. TERMICA E BATERIA: Ranger Pro operacao -40 a 85 C, mas Ta em area classificada limitada pela bateria a -40..80 C (TLH-5930) ou -40..70 C (TL-5930/Xeno XL-205F/Tadiran SL-2780); alarme de severidade de temperatura configuravel de 0 a 125 C medido na BASE do sensor; vida ate 5 anos. Erbessd -40 a 80 C, CR2477, 65.000 medicoes, 6-9 uA em standby. TRACTIAN -10 a 90 C marcado no corpo, IP69K, litio primario com 3 anos amostrando a cada 10 min, 250 amostras de buffer offline, 15 sensores por receiver em raio de 30-50 m. Ranger Pro: 88x40 mm, 230 g sem bateria / 300 g com, IP67, rosca M6x1 mm x 5 mm, limite de vibracao 20 g pico. Erbessd: 47x33 mm, 185 g, IP69, 1/4-28 UNF (o KAELIX tem 118 g - e o mais leve dos quatro). ISOLATION FOREST NA LITERATURA (municao direta para o A4): Chevtchenko et al. 2023 - IF sensibilidade 88,9%/86,3% e especificidade 61,6%/67,4% (validacao/teste), inferencia 21,40 ms; LOF 90,8/77,6% e 74,5/72,1% com 0,81 ms; OC-SVM 73,1/47,9% e 63,4/36,5% com 0,43 ms; dataset de 3750 normais + 2250 anomalas em 3 motores de 1 hp a 1000 rpm. Kolok et al. 2025 - IF com 100 arvores e contamination='auto': acuracia ~73%, precision 0,755, recall 0,679, F1 0,715, ROC-AUC 0,780, CV 5-fold 72,9 +/- 2,4%, limiares 0,018338 (F1) e 0,089770 (recall max). Antonini et al. 2023 - IF embarcado com LIMIAR FIXO de score normalizado em 0,75 (a alternativa correta ao contamination), 10-50 arvores, 6,9-20,33 ms de inferencia, 70,8-84,8 kB de RAM, treino no proprio ESP32 em 1,2-6,4 s. OUTROS BASELINES: Ūselis et al. 2025 (RP2040) 94,1% vibracao / 95,5% corrente-PCA / 83,2% descritores manuais, modelo 0,42->0,15 MB em 264 kB de RAM. Kumar et al. 2026 (ESP32-S3) 42,3 ms de inferencia INT8, recall de falha critica >0,924 com 50% de perda de rede. Jakobsen 2024 - BOM US$180, ADXL1002 com 11 kHz de banda plana / 21 kHz de ressonancia / 40 kHz de amostragem / 25 ug/sqrt(Hz), ADXL362 ate 200 Hz com 550 ug/sqrt(Hz), microfone 100 Hz-80 kHz, LiSOCl2 ~700 Wh/kg + supercap 100 mF para o pulso de 120 mA do LoRa a 22 dBm, DR0 europeu com payload de 51 bytes a 250 bit/s, autoressonancias de PCB em 6-9 kHz, defeito detectado de 5x0,5x0,25 mm num SKF2206. Kolok et al. 2025 - custo <30 EUR, <300 mW, DLPF do MPU6050 em 5 Hz.

**Lacunas neste eixo:** 1) TERMICA DE INVOLUCRO IMPRESSO EM 3D: nao encontrei NENHUM trabalho revisado por pares que caracterize termicamente (medido ou simulado) um involucro impresso em ASA/ABS/PETG/PC montado sobre carcaca quente de motor, com temperatura interna reportada. O A6 e, ate onde a busca alcanca, inedito - o que e bom para o TCC, mas significa que nao ha numero externo para calibrar os 44,8 C internos com 80 C de carcaca. 2) O TRADE-OFF EXPLICITO ISOLAMENTO-TERMICO x TRANSMISSIBILIDADE: ninguem publica os dois lados no MESMO involucro. Jakobsen (2024) escolhe aluminio citando 'estabilidade termica E rigidez' na mesma frase, mas nao quantifica nenhum dos dois. Essa e a contribuicao real disponivel para o KAELIX: mostrar que o ganho termico do ASA e pago em f_n (557 Hz vs 3273 Hz em aluminio). 3) LIMITE DE CARGA DE LiPo COMO RESTRICAO DE PROJETO: literatura zero, porque o campo inteiro usa celula primaria e portanto nunca carrega nada. A restricao dos 45 C nao esta refutada - esta ausente da conversa. Para o TCC isso deve virar uma pergunta de projeto ('por que recarregavel?'), nao um resultado. 4) VALIDACAO DE MONTAGEM: nenhum dos nos de baixo custo publicados mede a propria ressonancia de montagem. Jakobsen so nota de passagem autoressonancias de PCB em 6-9 kHz vistas no microfone; Bisio et al. (ISCAS 2025) fazem calibracao de sistema mas nao publicam f_n. Nao ha, portanto, precedente publicado contra o qual comparar os 557 Hz do A5. 5) ISO 10816 EM NO DE BAIXO CUSTO: nenhum dos trabalhos academicos abertos (Kolok, Chevtchenko, Antonini, Ūselis, Kumar, Bisio) menciona ISO 10816, banda de velocidade nem procedimento de integracao aceleracao->velocidade. Quem entrega velocidade conforme e so o produto comercial (Ranger Pro 5-2000 Hz; TRACTIAN espectro de velocidade). Rotular por ISO 10816 em hardware de 1 kHz e um territorio que a literatura simplesmente nao pisou. 6) MASSA DO SENSOR E MASS LOADING: nenhum trabalho de baixo custo discute o efeito da propria massa (118 g no KAELIX, 185 g no Erbessd, 300 g no Ranger Pro) sobre a estrutura medida. 7) IMA COMO UNICA FIXACAO: TRACTIAN e Chevtchenko usam ima, mas a TRACTIAN documenta que o ima e auxiliar de instalacao e que a base deve ser colada para qualidade de dado - ninguem publicou a degradacao quantitativa de banda entre ima-so e ima+epoxi em no IoT.

---


*58 referências catalogadas. Legenda de Meta: ✓ verificado (auto-declarado), ~ provável, ✗ não verificado.*
