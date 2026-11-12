# Registro das hipóteses, versão 1

Registrado em 6 de novembro de 2026, depois da aprovação das hipóteses pelo autor e antes de qualquer cálculo que as avalie. Os critérios abaixo não mudam depois do resultado. Uma mudança vira emenda (`registro_v2.md`), e esta versão fica preservada com o seu `.sha256`.

## Dados

Somente os dados da coleta em campo de 2 de novembro de 2026, exportados do banco da API, em modo de leitura, por `experiments/campo/exportar_campo.py`:

| Arquivo | SHA-256 |
|---|---|
| `ensaios.csv` | `eb0730509cd4dfa818c2fa2ff60f1dd9a3ada0da26b3c60a315c65d51aff5cd1` |
| `leituras.csv` | `929db12213a90f7ed03eecfb15dda2181ce9c5a8a01a5a71bc1d703fcdfe63f0` |
| `janelas.csv` | `cf8ba6dfdcbe637c426006ba07807e5833fcfbe8d9c5a243ac953ec5d81934f6` |
| `janelas.npz` | `2ebcf5b91bbdcb652dd2c22a5f83612ec72c6f12ef263a00f8829563921a45d2` |

| Ensaio | Máquina | Rodada | Janelas | Eixo axial | Eixos radiais |
|---|---|---|---|---|---|
| 0 | Dobradeira | 1 | 50 | X | Y e Z |
| 1 | Guilhotina | 1 | 13 | Y | X e Z |
| 2 | Motor parado | 1 | 15 | não se aplica | não se aplica |
| 3 | Calandra | 1 | 25 | Y | X e Z |
| 4 | Compressor | 1 | 33 | Y | X e Z |
| 5 | Calandra | 2 | 47 | Y | X e Z |
| 6 | Guilhotina | 2 | 35 | Y | X e Z |

A orientação vem da anotação das coletas (variante 1, Y ao longo do eixo do motor, em guilhotina, calandra e compressor; variante 2 na dobradeira, com a placa deitada e o eixo axial em X).

## O que já foi visto antes deste registro

Em 2 e 5 de novembro, análises exploratórias usaram estes mesmos dados: Isolation Forest e regra por mediana e MAD entre rodadas, com outro conjunto de descritores (falso alarme de 0 % a 23 % e de 0 % a 38 %), repetibilidade da velocidade eficaz na calandra e na guilhotina, rotação e ordens. Essas leituras originaram as hipóteses e não as corroboram. A monografia declara isso.

## Pré-processamento e descritores

- Amostras inteiras de 16 bits convertidas em g pela faixa configurada (`accel_range` 1, ±4 g, 8192 contagens por g). Só os três canais de aceleração entram.
- Média de cada eixo removida em cada janela.
- Velocidade por integração no domínio da frequência, sem janela de ponderação, com os coeficientes fora de 10 Hz a 184 Hz anulados; valor eficaz pela soma dos coeficientes (Parseval).
- Rotação $f_r$ de cada janela: maior pico do espectro de aceleração somado nos três eixos, com janela de Hann e preenchimento com zeros até 16 vezes o tamanho da janela, na faixa de ±2,5 Hz em torno do valor de busca do ensaio (29,8 Hz, 30 Hz ou 59,8 Hz).
- Descritores por janela, independentes do sinal e da troca de eixos:
  - d1: velocidade eficaz de 10 Hz a 184 Hz, a maior entre os três eixos (mm/s);
  - d2: valor eficaz total da aceleração, raiz da soma dos quadrados dos três eixos (g);
  - d3: maior curtose em excesso entre os três eixos;
  - d4: maior fator de crista entre os três eixos;
  - d5: amplitude eficaz da ordem 1x em velocidade, raiz da soma dos quadrados dos três eixos (mm/s), lida no espectro com janela de Hann corrigida em amplitude;
  - d6: o mesmo para a ordem 2x.
- d1, d2, d5 e d6 entram nos detectores em logaritmo decimal.

## Detectores e limiar

- **Principal:** Isolation Forest do scikit-learn, 100 árvores, `max_samples = min(256, n)`, `random_state = 0`, sobre d1 a d6. O escore é o oposto de `score_samples` (maior é mais anômalo).
- **Secundário, descritivo:** regra por mediana e MAD, escore igual ao maior valor, entre d1 e d6, de |x − mediana| / (1,4826 · MAD), com mediana e MAD do treino.
- **Limiar:** α = 5 %. O treino é dividido em cinco blocos de janelas consecutivas; cada bloco recebe escore de um modelo ajustado nos outros quatro; o limiar é o quantil de 95 % desses escores fora do bloco. O modelo final é ajustado em todo o treino.
- **Incerteza:** reamostragem por blocos de cinco janelas consecutivas, 2.000 réplicas, intervalo de 95 % pelos percentis. Sem correção de multiplicidade.

## Critério de mudança da norma

0,7 mm/s, isto é, 25 % do limite B/C de 2,8 mm/s do grupo 2 em fundação rígida da ISO 20816-3 (Tabela de zonas da Fundamentação), o menor limite B/C da tabela. A regra dos 25 % do limite B/C foi conferida em Schwirzer (2002, VDI-Berichte n. 1715, p. 409 e seguintes), que descreve a série ISO 10816 ("ein Anstieg oder Abfall der Schwingungsgröße um 25 % der oberen Grenze der Zone B [ist] als wesentlich anzusehen"), e em fontes secundárias; o texto da ISO 20816-3 ainda precisa ser conferido. A velocidade deste trabalho vai de 10 Hz a 184 Hz, e não de 10 Hz a 1000 Hz; o valor serve de referência de tamanho de mudança, e não de classificação das máquinas. A guilhotina (9,2 kW) fica abaixo dos 15 kW da ISO 20816-3.

## H1, falso alarme entre rodadas

- **Máquinas:** calandra e guilhotina, as únicas com duas rodadas.
- **Estimando:** fração das janelas da rodada 2 com escore acima do limiar do detector principal treinado na rodada 1.
- **Corroborada:** fração de até 10 % e limite superior do intervalo de até 20 %, nas duas máquinas.
- **Refutada:** fração acima de 20 % em ao menos uma máquina.
- **Indeterminada:** os demais casos.
- **Descritivo:** o sentido inverso (rodada 2 para rodada 1) e o detector secundário.
- **Ressalva:** a rodada 1 da guilhotina tem 13 janelas, e o limiar dela se apoia em poucos escores.

## H2, menor mudança detectável

- **Ensaios:** os seis com a máquina em operação; o critério vale para os que têm ao menos 25 janelas (todos, exceto a rodada 1 da guilhotina, que entra só como descrição).
- **Regra:** alarme quando d1 passa do quantil de 95 % de d1 no próprio ensaio.
- **Estimando:** menor mudança detectável, MMD = quantil de 95 % − mediana de d1 (mm/s), que é o aumento da mediana que leva metade das janelas acima do limiar, com a dispersão mantida.
- **Corroborada:** MMD abaixo de 0,7 mm/s em todos os ensaios com ao menos 25 janelas.
- **Refutada:** MMD de 0,7 mm/s ou mais em ao menos um desses ensaios.
- **Descritivo:** MMD relativa à mediana, em porcentagem.

## H3, assinaturas injetadas

- **Treino e teste:** calandra e guilhotina, treino na rodada 1 e teste na rodada 2; dobradeira e compressor, treino na primeira metade das janelas do ensaio e teste na segunda metade, em ordem de tempo.
- **Assinatura 1x (desbalanceamento):** em cada janela de teste, soma, nos dois eixos radiais, de $A_a \sin(2\pi f_r t + \varphi)$ e $A_a \cos(2\pi f_r t + \varphi)$, com $f_r$ medida na janela limpa, fase $\varphi$ sorteada por janela (gerador do numpy, semente 0) e $A_a = \sqrt{2}\, A_v\, 2\pi f_r$, convertida para g, em que $A_v$ é a velocidade eficaz acrescentada em cada eixo radial.
- **Grade:** $A_v$ de 0 a 2,8 mm/s, em passos de 0,05 mm/s.
- **Estimandos:** fração detectada F(A_v) pelo detector principal, com o limiar do treino, e A50, a menor amplitude com F de 50 % ou mais, por interpolação linear entre os pontos da grade.
- **Corroborada:** A50 abaixo de 0,7 mm/s nas quatro máquinas e correlação de Spearman entre A_v e F de 0,9 ou mais em cada uma.
- **Refutada:** A50 de 0,7 mm/s ou mais, ou não atingido até 2,8 mm/s, em ao menos uma máquina, ou correlação abaixo de 0,9.
- **Descritivo:** assinatura 2x no eixo axial, com a mesma grade; detector secundário; Isolation Forest com as sementes 0 a 9.
- **Limite declarado:** a assinatura somada não reproduz a modulação, a variação de fase ao longo do tempo nem o caminho de transmissão de uma falha real.

## Ambiente

Python 3.12 com numpy, scipy e scikit-learn; as versões usadas ficam gravadas na saída de cada cálculo.
