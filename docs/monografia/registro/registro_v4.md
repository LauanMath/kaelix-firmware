# Registro das hipóteses, versão 4 (emenda)

Registrado em 8 de novembro de 2026, a pedido do autor, antes de qualquer cálculo de AP3, AP4, AP5 ou AP6. Esta emenda não cria hipótese nem muda critério. Ela acrescenta quatro análises posteriores, pedidas pelos pareceres de uma banca simulada sobre o texto de 7 de novembro de 2026. Os registros anteriores continuam valendo sem alteração: `registro_v1.md` para H1 a H3 (SHA-256 `fd0afc8941d16b3a54405489172938302b7687f25b8596e17cbd719b0013e39d`), `registro_v2.md` para H4, AP1 e AP2 (SHA-256 `3246d219c3e799d4639cea0f4f04eec12763113009e49879563753ad60482004`) e `registro_v3.md` para a fonte dos dados de H4 (SHA-256 `9197884e633b87439c03ea3d56f5f129ee150db04a90db4b399e9638a8d054f8`). Os vereditos de H1 a H4, calculados com a semente 0, não mudam, e a monografia apresenta AP3 a AP6 como análises posteriores aos resultados.

Pré-processamento, descritores d1 a d6, detectores, limiar e reamostragem por blocos são os dos registros v1 e v2, salvo onde esta emenda diz outra coisa.

## O que já foi visto antes desta emenda

- **Resultados registrados:** H1 indeterminada, com 17,0 % das janelas da segunda rodada da calandra marcadas (intervalo de 6,4 % a 29,8 %) e 0,0 % na guilhotina; H2 refutada, com menor mudança detectável (MMD) de 0,55 a 3,20 mm/s nos cinco ensaios do critério; H3 refutada; H4 refutada, com falso alarme de 56,9 % em `0E`; AP1 não confirmada; AP2 calculada.
- **Variação entre sementes já calculada:** em H3, as dez florestas (sementes 0 a 9) não chegaram a 50 % em nenhuma máquina; em H4, o falso alarme em `0E` foi de 11,8 % a 71,8 % entre as sementes 0 a 9. H1 não teve análise de sementes.
- **Repouso:** 238 janelas com o transmissor parado sobre a mesa, de 14h00 a 14h59 (horário de Brasília) de 2 de novembro de 2026, exportadas depois do registro v1 (`experiments/campo/dados/repouso.csv` e `repouso.npz`). Já são conhecidos a densidade de ruído por eixo (com o eixo Z, vertical, incluindo a vibração da mesa) e a mediana de d1 em repouso, de 0,10 mm/s. O texto dividiu a MMD de H2 por esse valor e obteve razões de 5,2 a 30,5. Os pareceres apontaram que essa razão compara uma dispersão com um nível. A MMD em repouso nunca foi calculada.
- **Escores:** os escores das janelas de teste de H3 sem assinatura e com 2,8 mm/s na guilhotina e no compressor, e a distribuição dos escores de H4 por arquivo, com o limiar. Nenhum escore de ponto sintético fora da faixa do treino foi calculado.
- **Pareceres:** pediram a distribuição do falso alarme de H1 e H4 entre sementes e numa reamostragem que refaça modelo e limiar, intervalo para a MMD, MMD em repouso e um teste da saturação do Isolation Forest.

## AP3, falso alarme de H1 e H4 com outras sementes e com o treino reamostrado

**Motivo.** Os intervalos registrados reamostram só as janelas de teste. O limiar e o modelo foram estimados uma vez, com a semente 0.

**Casos.**

- H1: calandra e guilhotina, sentido registrado (treino na rodada 1, teste na rodada 2).
- H4: treino em `0D`; teste em `0E` (falso alarme) e em `1E` a `4E` (fração marcada). Os descritores de cada janela são os gravados por `analise_h4.py` em `experiments/fraunhofer/analise_registrada/janelas.csv` (variante principal), sem recálculo a partir dos CSV da base.

**AP3a, sementes.** Isolation Forest com `random_state` de 0 a 99, cada um com o seu limiar pelo procedimento do registro v1 (cinco blocos de janelas consecutivas, quantil de 95 %), com o mesmo treino e o mesmo teste.

- Estimandos, em cada caso: fração marcada com cada semente; mediana, percentis de 2,5 % e de 97,5 %, mínimo e máximo entre as 100 sementes; número de sementes com fração até 10 % e acima de 20 % (os limites dos critérios de H1 e H4).
- Em H4, também: mediana e percentis da fração marcada em cada nível de 1 a 4 e número de sementes em que os quatro níveis chegam a 50 %; número de sementes em que H4 seria corroborada, refutada ou indeterminada pelos critérios do registro v2, usando o intervalo do teste reamostrado de cada semente.
- Em H1, também: número de sementes em que H1 seria corroborada, refutada ou indeterminada pelos critérios do registro v1.

**AP3b, treino reamostrado.** 1.000 réplicas, com um gerador do numpy de semente 0 para todos os sorteios, na ordem das réplicas. Em cada réplica r:

1. o treino é reamostrado por blocos de cinco janelas consecutivas, sorteados com reposição até completar o número de janelas do treino, como na reamostragem do registro v1;
2. o limiar é recalculado com grupos de validação formados pelos blocos originais distintos sorteados: os blocos distintos, em ordem de tempo, são divididos em cinco grupos consecutivos (`numpy.array_split`), ou em um grupo por bloco quando há menos de cinco; todas as cópias de um bloco ficam no mesmo grupo, para que nenhuma janela receba escore de um modelo treinado com ela;
3. o Isolation Forest usa `random_state = r`;
4. cada conjunto de teste é reamostrado por blocos de cinco janelas consecutivas, como no registro v1;
5. a fração marcada é calculada em cada teste reamostrado.

- Estimando: intervalo de 95 % pelos percentis de 2,5 % e 97,5 % das 1.000 frações, em cada teste.
- Aplica-se a H1 na calandra (25 janelas de treino, cinco blocos) e a H4 (`0D`, 706 janelas). Na guilhotina, o treino tem 13 janelas em três blocos, e a reamostragem produz poucos conjuntos distintos; nela, só AP3a.

**Conferência antes do cálculo.** Com a semente 0, AP3a deve reproduzir exatamente as frações de `analise_registrada/h1.csv` e de `fraunhofer/analise_registrada/h4.csv`.

**Sem critério de decisão:** AP3 é uma estimativa. O texto apresenta a faixa ao lado do valor registrado.

## AP4, intervalo da menor mudança detectável

- **Ensaios:** os seis de H2, com a primeira rodada da guilhotina só como descrição, como no registro v1.
- **Procedimento:** d1 das janelas do ensaio em ordem de tempo (conferida pela hora de recepção e pela sequência, como na AP2); reamostragem por blocos de cinco janelas consecutivas, 2.000 réplicas, um gerador do numpy de semente 0 por ensaio; em cada réplica, MMD = quantil de 95 % − mediana, com `numpy.quantile` e interpolação linear, como em H2.
- **Estimandos:** intervalo de 95 % pelos percentis de 2,5 % e 97,5 %; fração das réplicas com MMD de 0,7 mm/s ou mais.
- **Conferência antes do cálculo:** a MMD dos dados originais reproduz `h2.csv`.
- **Limite declarado:** com 25 a 50 janelas, o quantil de 95 % depende das duas ou três janelas mais altas, e a reamostragem de quantis extremos em amostras pequenas tende a dar intervalos estreitos demais. O intervalo é aproximado.

## AP5, menor mudança detectável com o sensor em repouso

- **Dados:** as 238 janelas em repouso.
- **Procedimento:** pré-processamento do registro v1 (faixa do acelerômetro da janela, média removida, velocidade de 10 Hz a 184 Hz) com a taxa de amostragem medida de cada janela; velocidade eficaz de cada eixo; d1 = maior dos três eixos; d1 horizontal = maior entre X e Y, os eixos horizontais com o sensor sobre a mesa.
- **Estimandos:** mediana e MMD em repouso (quantil de 95 % − mediana) de d1 e de d1 horizontal, com intervalo por blocos como na AP4; razão entre a MMD de H2 de cada ensaio do critério e a MMD em repouso, para d1 e para d1 horizontal.
- **Conferência antes do cálculo:** com a taxa nominal de 1000 Hz, a mediana de d1 em repouso arredondada a duas casas reproduz o valor de 0,10 mm/s já publicado.
- **Leitura registrada:** uma razão acima de 1 indica que a variação de d1 entre janelas nas máquinas é maior que a do mesmo descritor com o sensor parado. A razão não separa a máquina da fixação, porque as duas estão no sinal das máquinas e nenhuma está no repouso.
- **Uso no texto:** a razão da AP5 substitui, no texto, a divisão da MMD pela mediana de d1 em repouso.

## AP6, escore do Isolation Forest fora da faixa do treino

**Motivo.** Cada árvore do Isolation Forest divide um nó entre o mínimo e o máximo das janelas desse nó. Uma janela além do máximo do treino num descritor segue o mesmo caminho em qualquer distância além dele, e o escore deixa de crescer. A AP6 mede esse escore máximo e o compara com o limiar.

**Modelos.** Os detectores principais com semente 0 e os limiares registrados: os quatro de H3 (dobradeira e compressor treinados na primeira metade do ensaio, guilhotina e calandra na rodada 1, que são também os modelos de H1) e o de H4 (`0D`).

**Pontos sintéticos**, no espaço do detector (d1, d2, d5 e d6 em logaritmo decimal; d3 e d4 sem transformação):

- referência: a mediana do treino em cada descritor;
- um descritor acima da faixa: a referência com o descritor j em máximo do treino + (máximo − mínimo do treino), para j = 1 a 6; e o mesmo abaixo da faixa, com mínimo − (máximo − mínimo);
- d1, d2 e d5 acima da faixa, os três descritores que a assinatura 1x de H3 aumenta, com os demais na referência;
- os seis descritores acima da faixa.

**Estimandos.** Escore de cada ponto e diferença para o limiar; número de pontos de um descritor com escore acima do limiar.

**Descritivo, com a injeção de H3** (assinatura 1x, fase sorteada, semente 0, grade de 0 a 2,8 mm/s): em cada máquina, a menor amplitude da grade em que a mediana de d5 das janelas de teste passa do máximo de d5 do treino; a mediana do escore das janelas de teste nessa amplitude e em 2,8 mm/s; o número de janelas de teste com d1, d2 ou d5 acima do máximo do treino em 2,8 mm/s.

**Leitura registrada.** Se o escore do ponto com d1, d2 e d5 acima da faixa ficar abaixo do limiar numa máquina, uma janela de teste que mude só esses três descritores não alcança o limiar nessa máquina em nenhuma amplitude. Nesse caso, a refutação de H3 nessa máquina se deve ao escore máximo do detector com aquele treino, e não à amplitude da assinatura.

**Conferência antes do cálculo.** Os escores das janelas de teste sem assinatura reproduzem os de `analise_registrada.py`; o escore de um ponto além da faixa não muda quando a distância além do máximo dobra.

## Saídas

- `experiments/campo/analise_posterior_v4.py` grava `experiments/campo/analise_posterior_v4/` (CSV de cada análise e `ambiente.json`) e `docs/monografia/latex/values/posterior_v4_values.tex`.

## Ambiente

Python 3.12 com numpy 2.5.2, scipy 1.18.0 e scikit-learn 1.9.0, as versões das análises registradas. As versões usadas ficam gravadas na saída.
