# Registro das hipóteses, versão 3 (emenda)

Registrado em 7 de novembro de 2026, depois da aprovação do autor e antes de qualquer cálculo de H4. Esta emenda muda só a fonte dos dados de H4. A hipótese, o pré-processamento, o detector, o limiar, os estimandos, os critérios, os descritivos e os limites de H4 continuam os do `registro_v2.md` (SHA-256 `3246d219c3e799d4639cea0f4f04eec12763113009e49879563753ad60482004`). AP1 e AP2 já foram calculadas sob o registro v2, e o `registro_v1.md` continua valendo para H1 a H3 (SHA-256 `fd0afc8941d16b3a54405489172938302b7687f25b8596e17cbd719b0013e39d`).

## Motivo

- **Fordatis:** responde com erro 503 no arquivo e na página inicial desde a manhã de 7 de novembro de 2026, e a DOI 10.24406/fordatis/65.2 aponta para o mesmo servidor.
- **Cópia da versão 151.2 no Internet Archive:** termina em 2 GiB. A captura de 16/04/2020 tem 2.148.130.492 bytes no índice CDX, e pedidos a partir do byte 2.147.483.648 voltam sem nenhum byte. A captura de 03/04/2020 do mesmo arquivo, no endereço da versão 151, também tem 2.148.130.489 bytes. O arquivo de 2.671.806.282 bytes exigido pelo registro v2 não pode ser obtido dessas cópias.
- **Versão 151.3 no Internet Archive:** a captura de 14/12/2022, às 06:23:52, tem 2.950.920.556 bytes no índice CDX, mais que o arquivo original, de 2.950.666.199 bytes, e responde a pedidos por faixa além de 2 GiB.

## Equivalência entre as versões 151.2 e 151.3

O CRC-32 e o tamanho descomprimido de cada membro foram lidos no diretório central da versão 151.3 e nos cabeçalhos locais da cópia parcial da versão 151.2, os dois em 7 de novembro de 2026. Nos seis CSV presentes nas duas leituras, os valores são iguais:

| Membro | CRC-32 | Bytes descomprimidos |
|---|---|---|
| `0D.csv` | `ed3d4944` | 1.871.314.260 |
| `1D.csv` | `8fcf79c9` | 1.872.098.189 |
| `2D.csv` | `22532df2` | 1.872.431.356 |
| `3D.csv` | `d70ab505` | 1.871.406.764 |
| `4D.csv` | `32f9bfdc` | 1.875.865.527 |
| `0E.csv` | `c4675f4a` | 488.599.914 |

Os cabeçalhos de `1E.csv` a `4E.csv` da versão 151.2 ficam depois dos 2 GiB da cópia e não puderam ser comparados. Para esses quatro arquivos, a conferência é a de `4E` pelo número de linhas, abaixo. A versão 151.3 acrescenta, para cada conjunto, um arquivo `a1_tsfresh.npy`, que esta análise não usa.

## Mudanças em relação ao registro v2

- **Base:** Mey, Neudeck, Schneider e Enge-Rosenblatt, *Vibration Measurements on a Rotating Shaft at Different Unbalance Strengths*, Fraunhofer Fordatis, versão 151.3, DOI 10.24406/fordatis/65.3, arquivo `fraunhofer_eas_dataset_for_unbalance_detection_v2.zip` (2.950.666.199 bytes, tamanho informado pelo servidor original). Esta mudança substitui a frase do registro v2 que excluía a versão 151.3.
- **Fonte do arquivo:** a cópia do Internet Archive de 14/12/2022 (`web.archive.org/web/20221214062352id_/https://fordatis.fraunhofer.de/bitstream/fordatis/151.3/3/fraunhofer_eas_dataset_for_unbalance_detection_v2.zip`). Se a Fordatis voltar, o mesmo arquivo baixado dela também é aceito, com as mesmas conferências.
- **Membros usados:** só `0D.csv`, `0E.csv`, `1E.csv`, `2E.csv`, `3E.csv` e `4E.csv`, baixados por faixa de bytes, sem o ZIP inteiro.
- **Integridade:**
  - No download, o CRC-32 e o tamanho descomprimido de cada membro são conferidos com o diretório central do ZIP.
  - O SHA-256 de cada CSV é gravado em `registro_v3_dados.sha256` antes do cálculo de qualquer descritor, e o script de análise o confere.
  - O número de linhas de `0E` e de `4E` depois do descarte dos 50.000 primeiros valores é comparado com o dos cadernos dos autores (6.843.567 e 6.864.047), como no registro v2. Se algum dos dois diferir, a diferença é registrada antes de qualquer cálculo, e o autor decide se H4 é avaliada.
- **Licença:** Creative Commons Atribuição 4.0 Internacional (CC BY 4.0), conferida para a DOI 10.24406/fordatis/65.3 nos metadados da DataCite, em 7 de novembro de 2026 (registro v2). A citação da base usa a DOI da versão 151.3.

## O que já foi visto antes desta emenda

- Os resultados de H1 a H3 (registro v1) e de AP1 e AP2 (registro v2).
- Da base: o README e os metadados citados no registro v2 e a tabela de CRC-32 e tamanhos acima. O download dos seis CSV da versão 151.3 começou antes desta emenda. O script de download calcula só CRC-32, SHA-256 e número de linhas. Nenhum descritor foi calculado.

## Saídas

- `experiments/fraunhofer/baixar_membros_v2.py` grava os seis CSV em `experiments/fraunhofer/dados/v2/`, fora do git. O SHA-256 de cada um, gravado por esse script em `dados/v2/v2_membros.sha256`, é copiado para `registro_v3_dados.sha256` antes da análise.
- `experiments/fraunhofer/analise_h4.py` lê os CSV de `dados/v2/` e grava as mesmas saídas previstas no registro v2.

## Ambiente

Python 3.12 com numpy, scipy e scikit-learn, como nos registros v1 e v2. As versões usadas ficam gravadas na saída de cada cálculo.
