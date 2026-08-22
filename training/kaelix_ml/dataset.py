"""Carregamento dos datasets MAFAULDA e CWRU Bearing Dataset — e um
gerador de dados sintéticos para testar o pipeline ponta-a-ponta antes
dos arquivos reais chegarem em data/.

Princípio central: **o que sai daqui tem que se parecer com o que o
firmware mede**. O ESP32-S3 lê uma janela de 512 amostras a 1 kHz
(`VIBRATION_SAMPLES` em src/main.cpp, `SAMPLE_RATE_HZ` em
src/sensors/vibration.cpp); os datasets vêm a 50 kHz (MAFAULDA) ou
12/48 kHz (CWRU), com registros de segundos. Extrair features do
arquivo inteiro produziria um modelo que não se aplica ao dispositivo:
`dominant_freq_hz` chegaria a 25 kHz no treino e nunca passaria de
500 Hz em campo. Por isso todo sinal passa por `to_device_windows`
antes de virar feature.

Estado dos layouts:

- **MAFAULDA**: colunas e nomes de diretório CONFERIDOS contra a página
  oficial (www02.smt.ufrj.br/~offshore/mfs/page_01.html). Os arquivos
  vêm em 6 tarballs cujos nomes já são os diretórios esperados aqui.
- **CWRU**: o download oficial entrega arquivos .mat soltos, numerados
  (97.mat, 105.mat, ...), SEM estrutura de pastas — a condição de cada
  ensaio está numa tabela do site, não no nome. É preciso organizar em
  `normal/`, `ir/`, `or/`, `b/` antes de carregar; `cwru_label_from_path`
  falha alto até que isso seja feito, de propósito.
"""

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Iterator

import numpy as np
from scipy import signal

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

# Espelham o firmware. Mudar aqui exige mudar lá (e vice-versa), senão o
# modelo treinado deixa de corresponder ao que o dispositivo mede.
DEVICE_SAMPLE_RATE_HZ = 1000.0   # src/sensors/vibration.cpp::SAMPLE_RATE_HZ
DEVICE_WINDOW_SAMPLES = 512      # src/main.cpp::VIBRATION_SAMPLES

# Unidade canônica do pipeline. Os limiares ISO (labeling.py) partem de
# aceleração em g; qualquer fonte em m/s² é convertida na entrada.
CANONICAL_UNIT = "g"
GRAVITY_MS2 = 9.80665

# MAFAULDA: CSV sem cabeçalho, 8 colunas, 50 kHz, janelas de 5 s
# (250.000 linhas por arquivo). Ordem das colunas CONFERIDA contra a
# página oficial.
MAFAULDA_SAMPLE_RATE_HZ = 50_000.0
MAFAULDA_COLUMNS = [
    "tachometer",
    "underhang_axial",
    "underhang_radial",
    "underhang_tangential",
    "overhang_axial",
    "overhang_radial",
    "overhang_tangential",
    "microphone",
]

# Classe de falha codificada no diretório de topo do MAFAULDA. Só
# "normal" é operação sadia; todo o resto é anomalia de referência.
# CONFERIDO contra a página oficial: os 6 tarballs distribuídos são
# normal, horizontal-misalignment, vertical-misalignment, imbalance,
# underhang e overhang — 1951 arquivos, 13,0 GB.
MAFAULDA_FAULT_DIRS = {
    "normal": "normal",
    "imbalance": "imbalance",
    "horizontal-misalignment": "horizontal-misalignment",
    "vertical-misalignment": "vertical-misalignment",
    "underhang": "underhang-bearing",
    "overhang": "overhang-bearing",
}

# CWRU: arquivos .mat (scipy.io.loadmat), variáveis terminando em
# "_DE_time" (drive-end) ou "_FE_time" (fan-end), 12 kHz ou 48 kHz. A
# condição do ensaio NÃO está no arquivo nem no nome — o download
# oficial é uma lista de .mat numerados. Organizar em pastas antes de
# carregar; ver o cabeçalho do módulo.
CWRU_FAULT_DIRS = {
    "normal": "normal",
    "ir": "inner-race",
    "or": "outer-race",
    "b": "ball",
    "inner_race": "inner-race",
    "outer_race": "outer-race",
    "ball": "ball",
}


@dataclass
class VibrationSample:
    accel: np.ndarray       # série temporal de aceleração (unidade em `unit`)
    sample_rate_hz: float
    unit: str                # "g" ou "m/s2"
    label: str                # "normal" | "anomalous" | "unknown"
    source: str                # ex.: "mafaulda", "cwru", "synthetic"
    group: str = ""             # identidade do ensaio/arquivo — chave do GroupKFold
    fault_class: str = "unknown"  # classe fina de falha, para relatório


# ---------------------------------------------------------------------------
# Unidades
# ---------------------------------------------------------------------------

def convert_unit(sample: VibrationSample, target: str = CANONICAL_UNIT) -> VibrationSample:
    """Converte a aceleração para `target`. Falha alto em unidade
    desconhecida — antes o campo `unit` era escrito e nunca lido, e um
    dataset em m/s² era tratado como g silenciosamente."""
    if sample.unit == target:
        return sample
    factors = {("g", "m/s2"): GRAVITY_MS2, ("m/s2", "g"): 1.0 / GRAVITY_MS2}
    key = (sample.unit, target)
    if key not in factors:
        raise ValueError(f"conversão de unidade não suportada: {sample.unit!r} -> {target!r}")
    return replace(sample, accel=np.asarray(sample.accel, dtype=np.float64) * factors[key], unit=target)


# ---------------------------------------------------------------------------
# Alinhamento com o domínio do firmware
# ---------------------------------------------------------------------------

def _decimation_stages(q: int, max_stage: int = 13) -> list:
    """Fatora `q` em estágios <= max_stage. scipy.signal.decimate perde
    qualidade com fatores altos num passo só (recomendação da própria
    doc: q <= 13 para FIR)."""
    stages = []
    remaining = q
    while remaining > max_stage:
        for f in range(max_stage, 1, -1):
            if remaining % f == 0:
                stages.append(f)
                remaining //= f
                break
        else:
            break  # sobrou um primo grande — resolve no último passo
    if remaining > 1:
        stages.append(remaining)
    return stages


def resample_to(accel: np.ndarray, sample_rate_hz: float, target_rate_hz: float) -> np.ndarray:
    """Reamostra para `target_rate_hz` com anti-aliasing. Usa decimação
    FIR em estágios quando a razão é inteira (mesmo `ftype`/`zero_phase`
    validados nos notebooks); cai para `resample_poly` caso contrário."""
    x = np.asarray(accel, dtype=np.float64)
    if sample_rate_hz == target_rate_hz:
        return x
    if sample_rate_hz < target_rate_hz:
        raise ValueError(
            f"upsampling não faz sentido aqui: fonte {sample_rate_hz} Hz < alvo {target_rate_hz} Hz"
        )

    ratio = sample_rate_hz / target_rate_hz
    if abs(ratio - round(ratio)) < 1e-9:
        for q in _decimation_stages(int(round(ratio))):
            x = signal.decimate(x, q, ftype="fir", zero_phase=True)
        return x

    # Razão não inteira: resample_poly já embute o filtro anti-aliasing.
    from fractions import Fraction

    frac = Fraction(target_rate_hz / sample_rate_hz).limit_denominator(1000)
    return signal.resample_poly(x, frac.numerator, frac.denominator)


def to_device_windows(
    sample: VibrationSample,
    window_samples: int = DEVICE_WINDOW_SAMPLES,
    hop_samples: int = None,
    target_rate_hz: float = DEVICE_SAMPLE_RATE_HZ,
) -> list:
    """Converte um registro longo de dataset nas janelas que o firmware
    de fato enxerga: unidade canônica, `target_rate_hz`, blocos de
    `window_samples`. Sem sobreposição por padrão — janelas sobrepostas
    dentro do mesmo arquivo são quase-duplicatas e inflam a contagem de
    amostras sem acrescentar informação.

    O `group` é preservado em todas as janelas do mesmo registro, para
    que o `GroupKFold` mantenha o arquivo inteiro do mesmo lado do split.
    """
    hop = hop_samples or window_samples
    canonical = convert_unit(sample, CANONICAL_UNIT)
    x = resample_to(canonical.accel, canonical.sample_rate_hz, target_rate_hz)

    windows = []
    for start in range(0, len(x) - window_samples + 1, hop):
        windows.append(
            replace(
                canonical,
                accel=x[start:start + window_samples],
                sample_rate_hz=target_rate_hz,
            )
        )
    return windows


# ---------------------------------------------------------------------------
# Rótulo de referência lido do caminho do arquivo
# ---------------------------------------------------------------------------

def _label_from_path(path: Path, fault_dirs: dict, dataset: str) -> tuple:
    """Procura, nas partes do caminho, um diretório de classe conhecido.
    Levanta ValueError se não achar: rotular errado em silêncio é pior
    que parar, porque contamina o treino inteiro sem deixar rastro."""
    parts = [p.lower() for p in path.parts]
    for part in parts:
        if part in fault_dirs:
            fault_class = fault_dirs[part]
            return fault_class, ("normal" if fault_class == "normal" else "anomalous")
    raise ValueError(
        f"não foi possível determinar a classe de falha de {path} — nenhum diretório "
        f"reconhecido do {dataset} no caminho. Esperado um de: {sorted(fault_dirs)}. "
        f"Ajuste {dataset.upper()}_FAULT_DIRS em dataset.py contra a árvore real."
    )


def mafaulda_label_from_path(path: Path) -> tuple:
    """(classe_de_falha, rótulo) a partir da estrutura de diretórios do
    MAFAULDA. O dataset traz a verdade de referência no caminho — o
    pipeline antes descartava isso e derivava tudo dos limiares ISO."""
    return _label_from_path(Path(path), MAFAULDA_FAULT_DIRS, "mafaulda")


def cwru_label_from_path(path: Path) -> tuple:
    """(classe_de_falha, rótulo) do CWRU. A condição não está dentro do
    .mat; depende de como o pacote foi organizado em pastas."""
    return _label_from_path(Path(path), CWRU_FAULT_DIRS, "cwru")


# ---------------------------------------------------------------------------
# Leitores
# ---------------------------------------------------------------------------

def load_mafaulda_csv(path: Path, channel: str = "underhang_radial", label: str = "unknown") -> VibrationSample:
    """Lê um CSV do MAFAULDA e retorna a coluna de vibração escolhida.
    Ordem das colunas conferida contra a página oficial; a unidade (g) é
    a documentada para os acelerômetros do MFS."""
    if channel not in MAFAULDA_COLUMNS:
        raise ValueError(f"canal desconhecido: {channel}")
    col_idx = MAFAULDA_COLUMNS.index(channel)
    data = np.loadtxt(path, delimiter=",")
    accel = data[:, col_idx]
    return VibrationSample(
        accel=accel,
        sample_rate_hz=MAFAULDA_SAMPLE_RATE_HZ,
        unit="g",
        label=label,
        source="mafaulda",
        group=str(path),
    )


def load_cwru_mat(path: Path, sample_rate_hz: float = 12_000.0, label: str = "unknown") -> VibrationSample:
    """Lê um arquivo .mat do CWRU Bearing Dataset (canal drive-end).
    Passe `sample_rate_hz=48_000.0` para os ensaios de 48 kHz — o valor
    não está no arquivo."""
    from scipy.io import loadmat

    mat = loadmat(str(path))
    de_keys = [k for k in mat.keys() if k.endswith("_DE_time")]
    if not de_keys:
        raise KeyError(f"nenhuma variável '*_DE_time' encontrada em {path}")
    accel = mat[de_keys[0]].flatten()
    return VibrationSample(
        accel=accel,
        sample_rate_hz=sample_rate_hz,
        unit="g",
        label=label,
        source="cwru",
        group=str(path),
    )


def iter_dataset_files(subdir: str, pattern: str) -> Iterator[Path]:
    """Varre `data/<subdir>/` **recursivamente**. O MAFAULDA vem
    organizado em subdiretórios por tipo e severidade de falha; com o
    `glob` não recursivo de antes, a busca devolvia zero arquivos e o
    treino caía no fallback sintético como se nada tivesse sido baixado."""
    folder = DATA_DIR / subdir
    if not folder.exists():
        raise FileNotFoundError(
            f"{folder} não existe — anexe os arquivos do dataset em data/{subdir}/ "
            "(ver training/kaelix_ml/dataset.py para o layout esperado)."
        )
    yield from sorted(folder.rglob(pattern))


DATASET_READERS = {
    "mafaulda": ("*.csv", load_mafaulda_csv, mafaulda_label_from_path),
    "cwru": ("*.mat", load_cwru_mat, cwru_label_from_path),
}


def load_cached_windows(subdir: str) -> list:
    """Lê as janelas já convertidas de `data/cache/<subdir>-*.npz`.

    O cache é gerado por `kaelix_ml.ingest` e existe porque o bruto do
    MAFAULDA ocupa ~31 GB extraídos enquanto o que o treino consome cabe
    em ~36 MB. Devolve [] se não houver cache."""
    cache_dir = DATA_DIR / "cache"
    if not cache_dir.exists():
        return []

    from .ingest import arrays_to_windows

    windows = []
    for path in sorted(cache_dir.glob(f"{subdir}-*.npz")):
        windows.extend(arrays_to_windows(np.load(path, allow_pickle=False)))
    return windows


def load_device_windows(subdir: str) -> list:
    """Carrega um dataset inteiro já no domínio do firmware: rótulo lido
    do caminho, unidade canônica, 1 kHz, janelas de 512 amostras.

    Prefere o cache de `kaelix_ml.ingest`; cai para leitura dos CSVs
    brutos quando ele não existe."""
    cached = load_cached_windows(subdir)
    if cached:
        return cached

    if subdir not in DATASET_READERS:
        raise ValueError(f"dataset desconhecido: {subdir!r} — conhecidos: {sorted(DATASET_READERS)}")
    pattern, reader, labeler = DATASET_READERS[subdir]

    windows = []
    for path in iter_dataset_files(subdir, pattern):
        fault_class, label = labeler(path)
        sample = reader(path, label=label)
        sample = replace(sample, fault_class=fault_class)
        windows.extend(to_device_windows(sample))
    return windows


def generate_synthetic_dataset(
    n_normal: int = 200,
    n_anomalous: int = 60,
    n_samples: int = 1024,
    sample_rate_hz: float = DEVICE_SAMPLE_RATE_HZ,
    seed: int = 42,
) -> list:
    """Sinais sintéticos para validar o pipeline (features -> treino ->
    export) ponta-a-ponta enquanto os dados reais não chegam. NÃO
    substitui o treino real com MAFAULDA/CWRU.

    "Normal": senoide de baixa amplitude + ruído gaussiano leve.
    "Anômalo": harmônicos de maior amplitude + impulsos periódicos
    (simula desbalanceamento/defeito de rolamento) — maior amplitude,
    curtose e fator de crista, como um defeito real produziria.

    Cada amostra recebe um `group` próprio: são ensaios independentes,
    e é isso que permite ao GroupKFold funcionar também no modo
    sintético.
    """
    rng = np.random.default_rng(seed)
    t = np.arange(n_samples) / sample_rate_hz
    samples = []

    for i in range(n_normal):
        freq = rng.uniform(45, 55)
        amp = rng.uniform(0.5, 1.0)
        noise = rng.normal(0, 0.05, n_samples)
        x = amp * np.sin(2 * np.pi * freq * t) + noise
        samples.append(VibrationSample(
            accel=x, sample_rate_hz=sample_rate_hz, unit="g", label="normal",
            source="synthetic", group=f"synthetic-normal-{i:04d}", fault_class="normal",
        ))

    for i in range(n_anomalous):
        freq = rng.uniform(45, 55)
        amp = rng.uniform(2.0, 4.0)
        harmonics = amp * np.sin(2 * np.pi * freq * t) + 0.5 * amp * np.sin(2 * np.pi * 2 * freq * t)
        impulse_period = max(2, int(sample_rate_hz / rng.uniform(8, 15)))
        impulses = np.zeros(n_samples)
        impulses[::impulse_period] = amp * rng.uniform(1.5, 3.0)
        noise = rng.normal(0, 0.1, n_samples)
        x = harmonics + impulses + noise
        samples.append(VibrationSample(
            accel=x, sample_rate_hz=sample_rate_hz, unit="g", label="anomalous",
            source="synthetic", group=f"synthetic-anomalous-{i:04d}", fault_class="synthetic-fault",
        ))

    rng.shuffle(samples)
    return samples
