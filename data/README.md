Datasets de vibração para o treino do modelo. **Não versionados** (ver
`.gitignore`) — baixe e extraia aqui.

Consumidos por `training/kaelix_ml/dataset.py`, que lê os arquivos
recursivamente, deriva o rótulo verdadeiro da estrutura de diretórios,
converte para a unidade canônica (g), decima para 1 kHz e fatia em janelas
de 512 amostras — o mesmo formato que `src/main.cpp` mede em campo.

```
data/
├── mafaulda/          # CSV, 50 kHz, 8 colunas (ver MAFAULDA_COLUMNS)
│   ├── normal/
│   ├── imbalance/
│   ├── horizontal-misalignment/
│   ├── vertical-misalignment/
│   ├── underhang/
│   └── overhang/
└── cwru/              # .mat, 12 ou 48 kHz, variáveis *_DE_time
    ├── normal/
    ├── ir/            # inner race
    ├── or/            # outer race
    └── b/             # ball
```

A árvore acima é a documentada publicamente e **ainda não foi conferida
contra o download real**. Se os nomes divergirem, o carregamento falha com
mensagem explícita — ajuste `MAFAULDA_FAULT_DIRS` / `CWRU_FAULT_DIRS` em
`training/kaelix_ml/dataset.py`. Falhar alto é proposital: rótulo errado em
silêncio contamina o treino inteiro sem deixar rastro.
