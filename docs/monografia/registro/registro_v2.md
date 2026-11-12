# Registro das hipóteses, versão 2 (emenda)

Registrado em 7 de novembro de 2026, depois da aprovação do autor e antes de qualquer cálculo de H4, AP1 ou AP2. Os critérios abaixo não mudam depois do resultado. Uma mudança vira nova emenda (`registro_v3.md`), e esta versão fica preservada com o seu `.sha256`.

Esta emenda acrescenta a hipótese H4 e duas análises posteriores, AP1 e AP2. O `registro_v1.md` continua valendo, sem alteração, para H1 a H3 (SHA-256 `fd0afc8941d16b3a54405489172938302b7687f25b8596e17cbd719b0013e39d`). Pré-processamento, descritores d1 a d6, detectores, limiar e incerteza são os do registro v1, salvo onde esta emenda diz outra coisa.

## O que já foi visto antes desta emenda

- **Resultados de H1 a H3:** H1 indeterminada, H2 e H3 refutadas (`experiments/campo/analise_registrada/`). AP1 e AP2 foram desenhadas depois desses resultados, para examinar por que H2 e H3 foram refutadas. Elas não mudam a avaliação de H2 e H3, e a monografia as apresenta como análises posteriores.
- **Ordem 1x nas janelas limpas:** a mediana de d5 (soma quadrática da 1x nos três eixos) é de 8,4 mm/s na dobradeira, 15,8 e 18,1 mm/s na calandra (rodadas 1 e 2), 4,5 mm/s no compressor e 1,2 mm/s na guilhotina (as duas rodadas). A 1x de cada eixo radial ainda não foi medida.
- **Intervalo entre janelas consecutivas:** mediana de 15 s nos ensaios da rodada 1 e de 11 s nos da rodada 2 (`janelas.csv`, coluna `recebida_utc`).
- **Base da Fraunhofer:** o artigo de Mey et al. (2020), com os resultados dos quatro métodos supervisionados, e os cadernos públicos dos autores (`github.com/deepinsights-analytica/ieee-etfa2020-paper`), que mostram as estatísticas gerais de `0E` e `4E` (desvio padrão de Vibration_1 de 0,0065 e 0,0148, na unidade da coluna) e figuras de Vibration_1. Também foram lidos o README da versão 151.2 (cópia do Internet Archive de 26/09/2020) e os metadados da base na DataCite. Nenhum arquivo de dados da base foi baixado.

## AP1, assinatura 1x com fase relativa fixa

**Motivo.** Em H3, a fase φ da assinatura foi sorteada por janela. Como o início da janela não é sincronizado com o eixo, a fase da assinatura em relação à 1x que a máquina já tem também ficou sorteada. Se a 1x existente num eixo tem amplitude A e a assinatura tem amplitude B < A, a amplitude da soma com fase relativa θ uniforme aumenta, em média, cerca de (B/A)²/4 em termos relativos. Um desbalanceamento real acrescenta uma força de fase fixa em relação ao desbalanceamento existente, porque a massa fica num ponto do rotor. Com resposta linear, a fase relativa θ é a mesma em todos os eixos.

**Procedimento.** Máquinas, divisão em treino e teste, detector principal, limiar e grade de $A_v$ (0 a 2,8 mm/s, passos de 0,05 mm/s) iguais aos de H3. Muda só a injeção:

- em cada janela de teste e em cada eixo radial $k$, a fase $\psi_k$ da 1x existente é o argumento do coeficiente da transformada de Fourier da janela limpa na frequência $f_r$, com janela de Hann e o mesmo preenchimento com zeros de 16 vezes usado na rotação;
- a assinatura somada ao eixo $k$ é $A_a \cos(2\pi f_r t + \psi_k + \theta)$, com $A_a = \sqrt{2}\, A_v\, 2\pi f_r$ convertida para g, como em H3;
- três casos: θ = 0° (em fase com a 1x existente), 90° e 180° (em oposição).

**Conferência antes do cálculo.** Somada a uma janela sintética com cosseno de fase conhecida, a assinatura com θ = 0° deve aumentar a amplitude da 1x do eixo em $A_v$, e com θ = 180°, reduzi-la em $A_v$, com erro de até 2 %.

**Previsão registrada.** Nas três máquinas em que a mediana de d5 passa de 2,8 mm/s (dobradeira, calandra e compressor), a fração detectada em $A_v$ = 2,8 mm/s com θ = 0° é maior que a de H3, com fase sorteada.

- **Confirmada:** nas três máquinas.
- **Não confirmada:** em ao menos uma.

**Descritivo.** Curvas F($A_v$) e A50 para os três valores de θ, nas quatro máquinas; variação média de d5 com $A_v$ para cada θ; mediana da 1x de cada eixo radial nas janelas limpas; detector secundário. Com θ = 180°, a amplitude diminui até $A_v$ igualar a 1x existente, e a regra dos 25 % do registro v1 trata redução e aumento do mesmo modo.

**Limite declarado.** A previsão supõe que a 1x existente se deve ao desbalanceamento. Se parte dela tiver outra origem (desalinhamento, folga, campo elétrico), a fase relativa de um desbalanceamento real não será a mesma em todos os eixos.

## AP2, mediana de k janelas por medição

**Motivo.** Em H2, a menor mudança detectável (MMD) de uma janela de 0,5 s foi de 0,55 a 3,20 mm/s. AP2 mede quanto a MMD diminui quando uma medição é a mediana de várias janelas.

**Procedimento.**

- Ensaios com ao menos 25 janelas (os cinco de H2 que entram no critério).
- Para k = 1 a 5, série das medianas móveis de d1 sobre k janelas consecutivas, com passo de uma janela (n − k + 1 valores).
- MMD_k = quantil de 95 % − mediana dessa série, como em H2. Com k = 1, MMD_1 reproduz H2, o que serve de conferência.
- k* = menor k com MMD_k abaixo de 0,7 mm/s, ou "não atingido até 5".
- Autocorrelação de d1 com defasagem de uma janela (Pearson), que indica se janelas consecutivas variam de forma independente.

**Sem critério de corroboração:** AP2 é uma estimativa.

**Limites declarados.** As janelas consecutivas da coleta estão separadas por 11 s a 15 s, e uma mediana de 5 janelas cobre cerca de 1 min. A AP2 não diz o que aconteceria com janelas adquiridas sem intervalo. Com 25 janelas e k = 5, a série tem 21 valores dependentes entre si, e o quantil de 95 % fica perto do máximo.

## H4, desbalanceamento real numa base pública

**Hipótese.** O detector principal, treinado só com a operação sem desbalanceamento, detecta desbalanceamento real desde o menor nível da base, com falso alarme de até 10 % depois da remontagem do suporte.

**Base.** Mey, Neudeck, Schneider e Enge-Rosenblatt, *Vibration Measurements on a Rotating Shaft at Different Unbalance Strengths*, Fraunhofer Fordatis, versão 151.2, DOI 10.24406/fordatis/65.2, arquivo `fraunhofer_eas_dataset_for_unbalance_detection_v1.zip` (2.671.806.282 bytes, tamanho informado pelo servidor original). É a versão citada pelo artigo: Mey et al., ETFA 2020, DOI 10.1109/ETFA46521.2020.9212000. A análise não usa a versão 151.3 (DOI 10.24406/fordatis/65.3, de 12/12/2022), que traz outro arquivo, `..._v2.zip`, de 2,88 GB, com CSV e NPY.

- **Bancada:** motor CC de comutação eletrônica (WEG UE 511 T), eixo de 12 mm, mancal de rolamento em bloco de aço galvanizado. O desbalanceamento é uma massa num suporte de náilon impresso em 3D, montado logo atrás do bloco do mancal.
- **Níveis:** 0 (suporte sem massa) e 1 a 4, com 45,9, 60,7, 75,5 e 152,1 mm·g.
- **Arquivos:** `0D` a `4D` (desenvolvimento, cerca de 107 min cada) e `0E` a `4E` (avaliação, cerca de 28 min cada), segundo o README. Entre as medições D e E, o desbalanceamento foi desmontado e remontado.
- **Colunas:** `V_in` (V), `Measured_RPM` (r/min), `Vibration_1` a `Vibration_3`, a 4096 Hz. São três acelerômetros PCB M607A11, no bloco do mancal e na fixação do motor. O artigo não informa a posição de cada coluna nem a unidade da vibração.
- **Rotação:** degraus de tensão de 20 s, percorridos duas vezes: em D, de 2,0 V a 10,05 V em passos de 0,05 V; em E, de 4,0 V a 8,1 V em passos de 0,1 V.
- **Fonte do arquivo:** a Fordatis; enquanto ela estiver fora do ar, a cópia do Internet Archive de 16/04/2020 (`web.archive.org/web/20200416004552/...`), aceita só se tiver os 2.671.806.282 bytes.
- **Integridade:** o SHA-256 do ZIP e de cada CSV é gravado em `registro_v2_dados.sha256` no download, antes do cálculo de qualquer descritor, e o script de análise o confere. A Fordatis não publica soma de verificação. Por isso, o número de linhas de `0E` e de `4E` depois do descarte dos 50.000 primeiros valores é comparado com o dos cadernos dos autores (6.843.567 e 6.864.047).
- **Licença:** Creative Commons Atribuição 4.0 Internacional (CC BY 4.0), conferida em 7 de novembro de 2026 nos metadados da DataCite dos DOIs 10.24406/fordatis/65, 65.2 e 65.3 e na cópia da página da versão 151.2 no Internet Archive (19/10/2026). A Fordatis estava fora do ar nessa data (erro 503). A licença exige a citação dos autores, do título e do DOI, e a indicação das modificações: recorte de rotação, janelas e corte em 184 Hz.

**Pré-processamento.**

- Descartados os primeiros 50.000 valores de cada arquivo, como no artigo.
- Janelas consecutivas, sem sobreposição, de 2.048 amostras: 0,5 s e resolução de 2,0 Hz, perto das 512 amostras a 1 kHz do Kaelix (0,51 s e 1,95 Hz).
- Entram as janelas com `V_in` constante em toda a janela e rotação média de 1750 a 1850 r/min, faixa que contém a rotação das máquinas da coleta (1786 a 1801 r/min). As duas primeiras janelas de cada degrau são descartadas, para excluir a mudança de rotação.
- As três colunas de vibração entram como os três canais, e a média de cada uma é removida em cada janela.
- Banda do Kaelix: os coeficientes acima de 184 Hz são anulados antes de d2, d3 e d4; a velocidade de d1 vai de 10 Hz a 184 Hz, como no registro v1. A 1x e a 2x, perto de 30 Hz e 60 Hz, estão nessa banda.
- Rotação $f_r$ de cada janela: o mesmo pico espectral do registro v1, com valor de busca igual à média de `Measured_RPM`/60 na janela.
- Como a unidade das colunas não é informada, d1, d2, d5 e d6 ficam na unidade da coluna. O detector usa esses descritores em logaritmo, e um fator de escala comum ao treino e ao teste não muda o resultado. d3 e d4 não têm unidade.

**Detector e limiar.** Isolation Forest e limiar como no registro v1 (100 árvores, `max_samples = min(256, n)`, `random_state = 0`, α = 5 %, cinco blocos de janelas consecutivas), com treino em todas as janelas de `0D` que passam pelo pré-processamento.

**Estimandos.**

- FA: fração das janelas de `0E` com escore acima do limiar.
- F_L: fração das janelas de `LE` com escore acima do limiar, para L = 1 a 4.
- Intervalo de 95 % de cada fração por reamostragem em blocos de cinco janelas consecutivas, 2.000 réplicas, semente 0. Sem correção de multiplicidade.

**Critérios.**

- **Corroborada:** FA de até 10 % e limite superior do intervalo de até 20 %, e F_L de 50 % ou mais nos quatro níveis.
- **Refutada:** FA acima de 20 %, ou F_L abaixo de 50 % em ao menos um nível.
- **Indeterminada:** os demais casos.

**Descritivo.** Menor nível com F_L de 50 % ou mais; correlação de Spearman entre o fator de desbalanceamento (0 a 152,1 mm·g) e a fração marcada; detector secundário; Isolation Forest com as sementes 0 a 9; só `Vibration_1`, o sensor usado pelos autores; banda completa (d2 a d4 sem corte, velocidade de 10 Hz a 1000 Hz), para medir o efeito do corte em 184 Hz; mediana de d5 por nível. Se a unidade das colunas for confirmada, d1 por nível em mm/s.

**Limites declarados.** A base foi medida numa bancada de laboratório com motor pequeno, eixo de 12 mm e sem carga. Os três sensores são uniaxiais e estão em dois pontos, enquanto o Kaelix usa um sensor triaxial num ponto. Nenhum ruído é acrescentado, e o sensor do Kaelix não é modelado. H4 avalia, portanto, o método de detecção diante de uma falha real. O desempenho do dispositivo em campo continua avaliado só por H1 a H3.

## Saídas

- `experiments/campo/analise_posterior.py` grava `experiments/campo/analise_posterior/` (AP1 e AP2) e `docs/monografia/latex/values/posterior_values.tex`.
- `experiments/fraunhofer/baixar.py` baixa a base e grava `registro_v2_dados.sha256`. `experiments/fraunhofer/analise_h4.py` grava `experiments/fraunhofer/analise_registrada/` e `docs/monografia/latex/values/h4_values.tex`. A base fica em `experiments/fraunhofer/dados/`, fora do git.

## Ambiente

Python 3.12 com numpy, scipy e scikit-learn, como no registro v1. As versões usadas ficam gravadas na saída de cada cálculo.
