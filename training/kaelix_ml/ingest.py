"""Ingestão do MAFAULDA: baixa, converte para o domínio do firmware e
descarta o bruto.

Motivo de existir: o dataset tem ~12 GB comprimidos e ~31 GB extraídos,
mas o que o treino consome — janelas de 512 amostras a 1 kHz — cabe em
~36 MB. Guardar o bruto é desperdício de 3 ordens de grandeza. Este
módulo processa **uma classe por vez** e apaga os CSVs assim que o cache
está gravado, então o pico de disco é o maior tarball (~3,4 GB), não a
soma.

Uso:
    python -m kaelix_ml.ingest --all
    python -m kaelix_ml.ingest normal imbalance
    python -m kaelix_ml.ingest --all --keep-raw     # não apaga os CSVs

É resumível: classes já em cache são puladas (use --force para refazer).
"""

import argparse
import shutil
import socket
import sys
import tarfile
import time
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np

from . import dataset

MAFAULDA_BASE_URL = "https://www02.smt.ufrj.br/~offshore/mfs/database/mafaulda"
MAFAULDA_CLASSES = [
    "normal",
    "imbalance",
    "horizontal-misalignment",
    "vertical-misalignment",
    "underhang",
    "overhang",
]

CACHE_DIR = dataset.DATA_DIR / "cache"


def cache_path(subdir: str, cls: str) -> Path:
    return CACHE_DIR / f"{subdir}-{cls}.npz"


CHUNK_BYTES = 1 << 20
SOCKET_TIMEOUT_S = 30
MAX_RETRIES = 20


def _download(url: str, dest: Path, timeout: float = SOCKET_TIMEOUT_S,
              max_retries: int = MAX_RETRIES) -> None:
    """Baixa com retomada por HTTP Range e timeout por leitura.

    O servidor da UFRJ é lento e pendura conexões sem fechá-las: uma
    execução anterior ficou 7 horas parada em 53% porque
    `urllib.request.urlretrieve` não tem timeout por padrão. Aqui cada
    leitura tem prazo, e uma conexão morta vira retomada a partir do byte
    já gravado em vez de recomeço.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    for attempt in range(1, max_retries + 1):
        have = dest.stat().st_size if dest.exists() else 0
        req = urllib.request.Request(url)
        if have:
            req.add_header("Range", f"bytes={have}-")

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                resumed = resp.status == 206
                if have and not resumed:
                    have = 0  # servidor ignorou o Range: recomeça do zero
                total = have + int(resp.headers.get("Content-Length") or 0)

                with open(dest, "ab" if resumed else "wb") as f:
                    last_report = 0.0
                    while True:
                        chunk = resp.read(CHUNK_BYTES)
                        if not chunk:
                            break
                        f.write(chunk)
                        have += len(chunk)
                        now = time.time()
                        if now - last_report > 2.0:
                            pct = have / total * 100 if total else 0.0
                            rate = have / max(now - t0, 1e-9) / 1e6
                            print(f"\r    {dest.name}: {pct:5.1f}%  "
                                  f"({have/1e9:5.2f} GB, {rate:4.1f} MB/s)", end="", flush=True)
                            last_report = now

            if not total or have >= total:
                print(f"\r    baixado {dest.name}: {have/1e9:.2f} GB em {time.time()-t0:.0f}s")
                return
            raise urllib.error.URLError(f"conexão terminou em {have}/{total} bytes")

        except (socket.timeout, TimeoutError, urllib.error.URLError, ConnectionError, OSError) as exc:
            if attempt == max_retries:
                raise
            print(f"\n    [{attempt}/{max_retries}] {type(exc).__name__}: {exc} — "
                  f"retomando de {dest.stat().st_size/1e9:.2f} GB", file=sys.stderr)
            time.sleep(min(2 ** attempt, 30))


def _safe_extract(tarball: Path, into: Path) -> None:
    """Extrai validando antes. Um .tgz truncado por download interrompido
    falha aqui em vez de virar CSV pela metade."""
    try:
        with tarfile.open(tarball) as tf:
            tf.extractall(into, filter="data")
    except tarfile.ReadError as exc:
        tarball.unlink(missing_ok=True)
        raise RuntimeError(
            f"{tarball.name} corrompido ({exc}) — parcial descartado, rode de novo para rebaixar"
        ) from exc


def _windows_to_arrays(windows: list) -> dict:
    return {
        "accel": np.stack([w.accel for w in windows]).astype(np.float32),
        "label": np.array([w.label for w in windows]),
        "group": np.array([w.group for w in windows]),
        "fault_class": np.array([w.fault_class for w in windows]),
        "sample_rate_hz": np.array(dataset.DEVICE_SAMPLE_RATE_HZ),
    }


def arrays_to_windows(data) -> list:
    """Reconstrói VibrationSample a partir do .npz do cache."""
    rate = float(data["sample_rate_hz"])
    return [
        dataset.VibrationSample(
            accel=accel.astype(np.float64), sample_rate_hz=rate,
            unit=dataset.CANONICAL_UNIT, label=str(label), source="mafaulda",
            group=str(group), fault_class=str(fault),
        )
        for accel, label, group, fault in zip(
            data["accel"], data["label"], data["group"], data["fault_class"]
        )
    ]


def ingest_class(cls: str, keep_raw: bool = False, force: bool = False) -> int:
    """Baixa (se preciso), converte e cacheia uma classe. Devolve o
    número de janelas gravadas."""
    out = cache_path("mafaulda", cls)
    if out.exists() and not force:
        n = len(np.load(out, allow_pickle=False)["label"])
        print(f"[ingest] {cls}: já em cache ({n} janelas) — pulando")
        return n

    class_dir = dataset.DATA_DIR / "mafaulda" / cls
    tarball = dataset.DATA_DIR / "mafaulda" / f"{cls}.tgz"

    downloaded = False
    if not class_dir.exists():
        print(f"[ingest] {cls}: baixando")
        _download(f"{MAFAULDA_BASE_URL}/{cls}.tgz", tarball)
        print(f"    extraindo {tarball.name}")
        _safe_extract(tarball, dataset.DATA_DIR / "mafaulda")
        tarball.unlink()
        downloaded = True

    csvs = sorted(class_dir.rglob("*.csv"))
    if not csvs:
        raise FileNotFoundError(f"nenhum CSV em {class_dir}")

    windows = []
    t0 = time.time()
    for i, path in enumerate(csvs, 1):
        fault_class, label = dataset.mafaulda_label_from_path(path)
        sample = dataset.load_mafaulda_csv(path, label=label)
        from dataclasses import replace

        windows.extend(dataset.to_device_windows(replace(sample, fault_class=fault_class)))
        if i % 50 == 0 or i == len(csvs):
            print(f"\r    processando {cls}: {i}/{len(csvs)} arquivos, "
                  f"{len(windows)} janelas ({time.time()-t0:.0f}s)", end="", flush=True)
    print()

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out, **_windows_to_arrays(windows))
    print(f"[ingest] {cls}: {len(windows)} janelas -> {out.name} ({out.stat().st_size/1e6:.1f} MB)")

    if downloaded and not keep_raw:
        shutil.rmtree(class_dir)
        print(f"    bruto descartado ({cls}/) — o cache basta para o treino")

    return len(windows)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("classes", nargs="*", choices=MAFAULDA_CLASSES + [], default=[])
    parser.add_argument("--all", action="store_true", help="ingerir todas as classes")
    parser.add_argument("--keep-raw", action="store_true", help="não apagar os CSVs extraídos")
    parser.add_argument("--force", action="store_true", help="refazer classes já em cache")
    args = parser.parse_args(argv)

    classes = MAFAULDA_CLASSES if args.all else args.classes
    if not classes:
        parser.error("informe classes ou --all")

    total = 0
    for cls in classes:
        total += ingest_class(cls, keep_raw=args.keep_raw, force=args.force)
    print(f"\n[ingest] total: {total} janelas em cache ({CACHE_DIR})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
