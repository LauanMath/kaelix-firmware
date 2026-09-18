# Verificação formal dos cálculos do TCC — Lean 4

Este projeto reproduz, em Lean 4, os cálculos de forma fechada que sustentam os
resultados de procedência **E** (modelagem sobre especificação) e o valor de
referência analítico da Tabela 4.2 do TCC. São **76 teoremas**, todos fechados
por avaliação no núcleo (*kernel*) do Lean, sem `sorry` e sem depender de
nenhum axioma — nem `Classical.choice`, nem `propext`, nem `Quot.sound`. O
arquivo `Kaelix/Auditoria.lean` registra isso por escrito na saída da
compilação.

## O que isto verifica, e o que não verifica

**Verifica:** que os números relatados decorrem, por aritmética exata, das
fórmulas declaradas no Capítulo 3 e dos parâmetros declarados no desenho, no
firmware e nas tabelas de material.

**Não verifica:** que os modelos descrevam o dispositivo real. Nenhum ensaio
físico alimenta nada aqui, e as condições de contorno idealizadas continuam
sendo as declaradas em §3.4. Resultado de procedência **S** (sinal
sintetizado) e **M** (dado real decimado) está fora do alcance do método: são
saídas de simulação e de treinamento, não consequências de fórmula fechada.
Onde o TCC relata um número dessa origem, este projeto ou fica em silêncio ou
verifica a conta que o *explica* — e diz qual das duas coisas está fazendo.

## Como rodar

Não há dependências externas, nem mesmo Mathlib; só o compilador. Nada é
baixado.

```sh
lake build          # compila e verifica os 76 teoremas (~6 s)
```

Exige Lean 4.33.1 (`lean-toolchain`). Se `lake` não estiver no `PATH`:
`export PATH="$HOME/.elan/bin:$PATH"`.

A saída de `lake build` inclui, do `Kaelix/Auditoria.lean`, os `#print axioms`
e os valores em decimal de cada grandeza, para conferência a olho contra as
tabelas do TCC.

## Método: por que não há números reais aqui

Lean sem Mathlib não tem ℝ, e π e as raízes não são racionais. Em vez de
importar uma biblioteca de análise, o projeto usa **aritmética de intervalos
sobre racionais exatos** (`Kaelix/Racional.lean`):

* `Q` é um racional `num/den` sem normalização por MDC. A normalização
  exigiria `Nat.gcd`, que não reduz no núcleo; sem ela, cada comparação vira
  uma multiplicação cruzada de inteiros que o núcleo avalia com GMP. O preço é
  denominador grande, nunca erro de arredondamento.
* `Intv` é um par `[lo, hi]`. Toda grandeza irracional entra como intervalo
  que a contém — π em dez casas, e cada raiz por enquadramento verificado
  (`ehRaiz`, `ehRaiz4`: basta checar `lo² ≤ x ≤ hi²`, e a monotonicidade de
  `t ↦ t²` faz o resto). Toda operação devolve intervalo que contém o
  resultado verdadeiro, então `lo < x < hi` no fim vale para o valor real, e
  não para um representante escolhido.

Isso também é o que permite verificar raiz de equação transcendente sem
resolver nada: mostrar que o resíduo do balanço térmico é positivo em `T₁` e
negativo em `T₂` localiza a raiz em `(T₁, T₂)`, dado que o resíduo é monótono
— e essa monotonicidade é elementar e está argumentada em comentário.

## O que fica fora do núcleo, e portanto precisa de leitura humana

1. As **definições** de cada modelo correspondem às fórmulas do Capítulo 3.
   Elas estão no topo de cada arquivo, curtas e comentadas, justamente para
   isso.
2. O enquadramento de π (`piI`) usa dígitos de constante conhecida.
3. A solidez da aritmética de intervalos implementada em `Racional.lean`.
4. Os argumentos de **monotonicidade** que transformam duas avaliações de sinal
   na localização de uma raiz.

Fora isso, nada é acreditado: nem os valores do TCC, nem os das planilhas, nem
os dos notebooks.

## Mapa: valor no TCC → teorema

| §  | Valor relatado | Teorema | Veredito |
|----|----------------|---------|----------|
| 4.2.1 | Nyquist 500 Hz para f_s de 1 kHz | `Aquisicao.nyquist_500` | confirma |
| 4.2.1 | BPFO 104,6 Hz | `Aquisicao.bpfo_exata` (104,606 25 exatos) | confirma |
| 4.2.1 | BPFI 157,9 Hz | `Aquisicao.bpfi_exata` (157,893 75 exatos) | confirma |
| 4.2.1 | defeito na banda, ressonância fora | `bpfo_dentro_da_banda`, `ressonancia_fora_da_banda` | confirma |
| 4.2.1 | 3,5 kHz rebate em 500 Hz | `Aquisicao.alias_da_ressonancia` (igualdade exata) | confirma |
| 4.2.1 | banda ISO (10–1000 Hz) não atendida | `Aquisicao.banda_iso_nao_atendida` | confirma |
| 4.2.3 | rigidez do caminho 1,45·10⁶ N/m | `Montagem.rigidez_do_caminho` (1 446 297,8) | confirma |
| 4.2.3 | frequência de montagem 557 Hz | `Montagem.freq_montagem_ASA` (557,196) | confirma |
| 4.2.3 | transmissibilidade ≈ 5× em 500 Hz | `Montagem.transmissibilidade_em_500` (4,9488) | confirma |
| 4.2.3 | erro de amplitude > 10 % em 168 Hz | `erro_abaixo_de_10_em_168`, `erro_acima_de_10_em_169` | confirma com ressalva: a travessia está em (168, 169) Hz, então em 168 Hz o erro ainda é 9,98 % |
| 4.2.3 | flexibilidade 51,1 / 0,4 / 48,5 % | `Montagem.decomposicao_da_flexibilidade` | confirma |
| 4.2.3 | base dobrada → 750 Hz | `Montagem.base_dobrada_nao_resolve` (749,53) | confirma |
| 4.2.3 | alumínio → 3273 Hz | `Montagem.freq_montagem_aluminio` (3272,79) | confirma |
| 4.2.3 | painéis acima de 1300 Hz | `Montagem.painel_lateral` (1307,25) | confirma |
| 4.2.3 | prática pede f_n ≥ 3 kHz | `Montagem.reprova_regra_3x_por_fator_5` | confirma |
| 4.3.1 | referência analítica 6,7524 mm/s | `Integracao.vrms_analitico` (6,752 372) | confirma |
| 4.3.1 | viés de 0,02 m/s² leva a 55,08 mm/s | `Integracao.relatado_55_08_na_faixa` | parcial: a fórmula fechada da deriva dá 46,2 mm/s (janela de 4 s) a 69,3 mm/s (6 s), faixa que contém o valor relatado. O TCC não declara a janela da simulação; sem ela, a verificação é de mecanismo e ordem de grandeza |
| 4.3.1 | sinal de zona A classificado além de D | `Integracao.zona_A_vira_alem_de_D` | confirma |
| 4.4.1 | resistência do caminho em ASA 88,8 K/W | `Termica.resistencia_ASA` (88,844) | confirma |
| 4.4.1 | em alumínio 0,074 K/W; razão 1206× | `resistencia_aluminio`, `razao_das_resistencias` | confirma |
| 4.4.1 | **temperatura interna 44,8 °C com carcaça a 80 °C** | `Termica.asa_sobe_em_32_9`, `asa_desce_em_33_1`, **`refuta_44_8`** | **refuta: o balanço dá 33,0 °C** |
| 4.4.1 | **bateria a 45 °C com carcaça em torno de 81 °C** | `Termica.asa_nao_atinge_45_nem_com_carcaca_90` | **refuta na configuração em ASA**; vale na de alumínio (`aluminio_atinge_45_com_carcaca_46`) |
| 4.4.1 | base de alumínio → 79,0 °C | `Termica.aluminio_79` | confirma |
| 4.4.1 | autoaquecimento de 2,0 mW → 0,01 °C | `Termica.autoaquecimento_desprezivel` (0,0113) | confirma |
| 4.4.2 | tempo no ar 185 ms | `Enlace.tempo_no_ar_sf9` (185,344 ms, igualdade exata) | confirma |
| 4.4.2 | 256 d no SF mais baixo, 138 d no mais alto | `Enlace.autonomia_sf7`, `autonomia_sf12` | confirma |
| 4.4.2 | 12,5 dB entre os extremos | `Enlace.ganho_entre_extremos` | confirma |
| 4.4.2 | Wi-Fi 44 d contra 236 d no enlace adotado | `Enlace.autonomia_wifi`, `autonomia_sf9` | confirma |
| 4.4.2 | rádio em standby: 45 d | `Enlace.autonomia_sem_sleep` | confirma |

Sem cobertura, por serem de procedência S ou M: contraste de 413× e 20×,
tabela de detecção por modo de falha, os 42,1 % de falso alarme, a queda de
área parcial, a inflação por vazamento e os resultados das cinco variantes de
integração (exceto a referência analítica e a deriva). Também não coberta
nesta rodada: a força de retenção magnética (7–30 %), que depende de um modelo
de ímã com duas raízes quadradas e não foi formalizada.

## A divergência térmica, em detalhe

O valor de 44,8 °C vem da célula 8 de `analise-termica.ipynb`, que resolve o
balanço por iteração de ganho fixo: 500 passos de `T += 0,005·(Q_in − Q_out)`
partindo de `T = (80 + 30)/2 = 55 °C`. A iteração caminha na direção certa, mas
em 500 passos ainda não chegou à raiz — parou em 44,8 °C a caminho de 33 °C.

Isso não é conjectura. O próprio repositório registra a correção: o bloco final
de `hardware/termica.py` grava `experiments/figures/data/fig11_correcao.csv`
com as duas leituras lado a lado, e para carcaça a 80 °C elas são **44,841 °C
("500 iterações")** e **33,005 °C ("convergido")**. O modelo em elementos
finitos do mesmo arquivo, com o motor a 90 °C, dá **34,30 °C**. O que este
projeto acrescenta é a prova de que 44,8 °C não pode ser a raiz: o resíduo já é
negativo, e por larga margem (−2,79 W), em 44,7 °C.

Duas consequências para o texto do TCC:

1. **O número precisa mudar** em §4.4.1, de 44,8 °C para ≈ 33 °C — e com ele o
   "temperatura interna alcançada com carcaça em torno de 81 °C".
2. **O achado principal muda de forma, não de direção.** Com base em ASA a
   bateria nunca atinge o limite de carga de 45 °C, nem com a carcaça a 90 °C;
   o invólucro plástico isola bem demais para isso. Mas a análise mecânica de
   §4.2.3 recomenda base metálica — e com base de alumínio bastam **46 °C de
   carcaça** para o interior chegar a 45 °C. O conflito entre elos que o TCC
   enuncia continua de pé, e fica mais nítido: não é que a bateria limite o
   projeto atual, é que ela limita exatamente a correção que o projeto precisa
   fazer. A quebra térmica de 2 mm, que o relatório de origem propõe, leva o
   interior a 40,1 °C com carcaça a 80 °C (`Termica.quebra_termica`) — e é,
   pelos números corrigidos, a saída que fecha os dois requisitos.

## Organização

```
Kaelix/Racional.lean    núcleo: racional exato Q, intervalos Intv, π, raízes
Kaelix/Aquisicao.lean   banda, BPFO/BPFI, Nyquist, rebatimento        (17)
Kaelix/Integracao.lean  velocidade eficaz analítica, deriva do viés   (10)
Kaelix/Montagem.lean    rigidez, f_n, transmissibilidade, painéis     (20)
Kaelix/Termica.lean     resistências, balanço, limite da bateria      (14)
Kaelix/Enlace.lean      tempo no ar, orçamento de energia             (15)
Kaelix/Auditoria.lean   #print axioms e valores em decimal
```
