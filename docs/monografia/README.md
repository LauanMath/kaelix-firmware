# Monografia

Fonte LaTeX da monografia (modelo do iCEV, abnTeX2) e o que produz os números, as tabelas e as figuras dela. A monografia não cita arquivos; este README é o lugar desse inventário.

- `latex/`: fonte da monografia. Compile com `make` (saída em `latex/build/main.pdf`).
- `registro/`: registros das hipóteses, gravados antes do cálculo, cada um com o seu `.sha256`. Ver `registro/README.md`. A monografia não reproduz esses textos: o apêndice do registro descreve, em prosa, o que cada registro acrescentou e o que já se conhecia antes dele.
- `audit/`: auditoria do texto, fora do `.tex`.

## Números do texto

Os números citados no texto não são digitados: os scripts abaixo leem os dados exportados e gravam macros do LaTeX em `latex/values/`, que `latex/main.tex` carrega. Não edite `latex/values/` à mão; mude o script e rode de novo.

| Script | O que faz |
|---|---|
| **`experiments/campo/`** | |
| `exportar_campo.py` | Exporta do banco da API, em modo de leitura, os ensaios, a telemetria e as janelas de sinal bruto dos trechos analisados. |
| `exportar_complementos.py` | Exporta, também em modo de leitura, as janelas com o transmissor em repouso e o histórico de rajadas do *gateway*. |
| `gravidade_por_ensaio.py` | Calcula a gravidade média por eixo em cada ensaio, que indica a face da carcaça em que o transmissor foi colado. |
| `analise_registrada.py` | Avalia H1 a H3, como no registro v1, e grava `hipoteses_values.tex`. |
| `analise_descritiva.py` | Calcula os resultados descritivos (ruído, rotação, espectros, rajadas e resposta a mudanças de condição) e grava `descritivos_values.tex`. |
| `analise_posterior.py` | Calcula a AP1 e a AP2, como no registro v2, e grava `posterior_values.tex`. |
| `analise_posterior_v4.py` | Calcula a AP3 a AP6, como no registro v4, e grava `posterior_v4_values.tex`; os descritores de H4 vêm da saída de `analise_h4.py`. |
| `analise_posterior_v4_descricao.py` | Descreve, fora do registro, por que o intervalo do nível 4 da AP3 foi de 0 % a 100 %, e grava `posterior_v4_descricao_values.tex`. |
| **`experiments/fraunhofer/`** | |
| `baixar_membros_v2.py` | Baixa os seis CSV da base pública usados em H4 e confere o CRC-32 e o tamanho de cada um, como no registro v3. |
| `analise_h4.py` | Avalia H4, como nos registros v2 e v3, e grava `h4_values.tex`. |
| **`docs/monografia/latex/scripts/`** | |
| `build_field_values.py` | Lê os dados exportados e grava `campo_values.tex`. |
| `build_results_values.py` | Lê os resultados das análises e grava `resultados_values.tex`. |
| `build_dados_values.py` | Confere o SHA-256 dos dados contra os valores registrados e as versões das bibliotecas nas três análises, e grava `dados_values.tex`. |
| `build_sistema_values.py` | Conta as linhas de código e os testes, lê a memória dos binários, a saída dos testes do *firmware* e os registros e o banco de teste dos ensaios de 2 de novembro, confere que o código do *firmware* não mudou depois das compilações da coleta e grava `sistema_values.tex`. |
| `build_tabelas_ensaio.py` | Lê as saídas de `analise_registrada.py` e `analise_descritiva.py`, sem recalcular, e grava as linhas das tabelas de dados por ensaio em `tabelas_ensaio_values.tex`. |
| **`docs/monografia/latex/figuras_src/`** | |
| `resultados.py` | Gera as figuras da seção de resultados. |
| `posteriores_h4.py` | Gera as figuras da H4 e da AP1; recalcula o escore da H4 e confere a fração marcada contra a saída de `analise_h4.py`. |
| **`experiments/figures/scripts/`** | Geram as figuras com fotos e os diagramas do sistema e dos materiais e métodos. |

Os registros e a cópia do banco de teste dos ensaios de 2 de novembro ficam fora do repositório (`.pio/bench/`), porque trazem nomes de rede e endereços do local, e `build_sistema_values.py` grava só os números.

## Integridade dos dados

- Coleta em campo (`experiments/campo/dados/`): o SHA-256 de `ensaios.csv`, `leituras.csv`, `janelas.csv` e `janelas.npz` está em `registro/registro_v1.md`, gravado antes do cálculo. Os demais arquivos (`repouso.*`, `rajadas.csv`, `gravidade_por_ensaio.csv`) foram exportados depois do registro v1.
- Base da Fraunhofer (`experiments/fraunhofer/dados/v2/`, fora do git): o SHA-256 dos seis CSV está em `registro/registro_v3_dados.sha256`, gravado no download.
- `build_dados_values.py` confere todos esses valores antes de gravar as macros.

## Ambiente

As análises gravam as versões usadas em `ambiente.json`, junto com as saídas (`experiments/campo/analise_registrada/`, `experiments/campo/analise_posterior/`, `experiments/campo/analise_posterior_v4/`, `experiments/fraunhofer/analise_registrada/`). O *firmware* é compilado com o PlatformIO, na plataforma `espressif32` com o *framework* Arduino, e o rádio usa a biblioteca RadioLib 7.7.1.
