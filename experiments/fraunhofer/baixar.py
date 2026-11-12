"""Baixa a base de desbalanceamento da Fraunhofer (versão 151.2) e grava o SHA-256, como em registro_v2.md.

Fonte: a Fordatis; se ela não responder, a cópia do Internet Archive de 16/04/2020, aceita só com o tamanho
informado pelo servidor original (2.671.806.282 bytes). O que falta do arquivo é baixado em seis faixas paralelas,
cada uma com retomada (experiments/fraunhofer/dados/partes.json guarda as faixas entre execuções).

Depois do download, grava docs/monografia/registro/registro_v2_dados.sha256 (ZIP e cada CSV) e
experiments/fraunhofer/dados/linhas.json (linhas de dados de cada CSV, sem o cabeçalho), e compara as linhas de
0E e 4E, depois do descarte dos 50.000 primeiros valores, com as dos cadernos dos autores.

Uso, a partir de kaelix-firmware/:
  taskpolicy -b /usr/bin/python3 -I experiments/fraunhofer/baixar.py
"""
import hashlib
import json
import pathlib
import threading
import time
import urllib.error
import urllib.request
import zipfile

RAIZ = pathlib.Path(__file__).resolve().parents[2]
DADOS = RAIZ / "experiments" / "fraunhofer" / "dados"
ZIP = DADOS / "fraunhofer_eas_dataset_for_unbalance_detection_v1.zip"
SHA = RAIZ / "docs" / "monografia" / "registro" / "registro_v2_dados.sha256"
TAMANHO = 2_671_806_282
FONTES = [
    "https://fordatis.fraunhofer.de/bitstream/fordatis/151.2/1/fraunhofer_eas_dataset_for_unbalance_detection_v1.zip",
    "http://web.archive.org/web/20200416004552id_/https://fordatis.fraunhofer.de/bitstream/fordatis/151.2/1/"
    "fraunhofer_eas_dataset_for_unbalance_detection_v1.zip",
]
# Linhas depois do descarte dos 50.000 primeiros valores, nas saídas de data0E.describe() e data4E.describe()
# do caderno 2_Measurement_Setup.ipynb dos autores.
LINHAS_CADERNO = {"0E.csv": 6_843_567, "4E.csv": 6_864_047}
DESCARTE = 50_000
BLOCO = 1 << 20
PARTES = 6  # conexões paralelas; o Internet Archive entrega cerca de 75 kB/s por conexão


def responde(url):
    """Pede o primeiro byte e confere o tamanho total anunciado."""
    pedido = urllib.request.Request(url, headers={"Range": "bytes=0-0"})
    with urllib.request.urlopen(pedido, timeout=60) as r:
        faixa = r.headers.get("Content-Range", "")
        if r.status != 206 or not faixa.endswith(f"/{TAMANHO}"):
            raise RuntimeError(f"HTTP {r.status}, Content-Range '{faixa}'")


def baixar_faixa(url, a, b, parte, progresso, i):
    for _ in range(200):
        feito = parte.stat().st_size if parte.exists() else 0
        progresso[i] = feito
        if a + feito > b:
            return
        pedido = urllib.request.Request(url, headers={"Range": f"bytes={a + feito}-{b}"})
        try:
            with urllib.request.urlopen(pedido, timeout=120) as r:
                if r.status != 206:
                    raise RuntimeError(f"HTTP {r.status}")
                with open(parte, "ab") as f:
                    for bloco in iter(lambda: r.read(BLOCO), b""):
                        f.write(bloco)
                        progresso[i] += len(bloco)
        except (urllib.error.URLError, OSError, RuntimeError) as e:
            print(f"  parte {i}: {e}; retomando", flush=True)
            time.sleep(15)


def baixar(url):
    """Baixa o que falta do ZIP em PARTES faixas paralelas, cada uma com retomada, e junta no fim."""
    inicio = ZIP.stat().st_size if ZIP.exists() else 0
    if inicio >= TAMANHO:
        return True
    responde(url)
    plano = DADOS / "partes.json"
    if plano.exists():
        faixas = [tuple(x) for x in json.loads(plano.read_text())]
        if faixas[0][0] != inicio:
            raise RuntimeError("partes.json não corresponde ao arquivo parcial")
    else:
        passo = -(-(TAMANHO - inicio) // PARTES)
        faixas = [(inicio + k * passo, min(TAMANHO, inicio + (k + 1) * passo) - 1) for k in range(PARTES)]
        plano.write_text(json.dumps(faixas))
    partes = [DADOS / f"parte_{k}.bin" for k in range(len(faixas))]
    progresso = [0] * len(faixas)
    linhas = [threading.Thread(target=baixar_faixa, args=(url, a, b, p, progresso, k), daemon=True)
              for k, ((a, b), p) in enumerate(zip(faixas, partes))]
    for t in linhas:
        t.start()
    while any(t.is_alive() for t in linhas):
        time.sleep(60)
        print(f"  {(inicio + sum(progresso)) / 1e9:.2f} de {TAMANHO / 1e9:.2f} GB", flush=True)
    for (a, b), p in zip(faixas, partes):
        if not p.exists() or p.stat().st_size != b - a + 1:
            raise RuntimeError(f"{p.name} incompleta")
    with open(ZIP, "ab") as f:
        for p in partes:
            with open(p, "rb") as g:
                for bloco in iter(lambda: g.read(BLOCO), b""):
                    f.write(bloco)
    if ZIP.stat().st_size != TAMANHO:
        raise RuntimeError(f"tamanho {ZIP.stat().st_size} depois de juntar as partes")
    for p in partes:
        p.unlink()
    plano.unlink()
    return True


def main():
    DADOS.mkdir(parents=True, exist_ok=True)
    (DADOS / ".gitignore").write_text("*\n", encoding="utf-8")
    pronto = ZIP.exists() and ZIP.stat().st_size == TAMANHO
    for tentativa in range(30):
        if pronto:
            break
        for url in FONTES:
            try:
                print(f"tentativa {tentativa + 1}: {url}", flush=True)
                pronto = baixar(url)
                if pronto:
                    break
            except (urllib.error.URLError, OSError, RuntimeError) as e:
                print(f"  falhou: {e}", flush=True)
        if not pronto:
            time.sleep(20)
    if not pronto:
        raise SystemExit("download não concluído")
    if ZIP.stat().st_size != TAMANHO:
        raise SystemExit(f"tamanho {ZIP.stat().st_size}, esperado {TAMANHO}")

    linhas_sha = []
    h = hashlib.sha256()
    with open(ZIP, "rb") as f:
        for b in iter(lambda: f.read(BLOCO), b""):
            h.update(b)
    linhas_sha.append(f"{h.hexdigest()}  {ZIP.name}")
    contagem = {}
    with zipfile.ZipFile(ZIP) as z:
        for nome in sorted(z.namelist()):
            h, n, fim = hashlib.sha256(), 0, b"\n"
            with z.open(nome) as c:
                for b in iter(lambda: c.read(BLOCO), b""):
                    h.update(b)
                    n += b.count(b"\n")
                    fim = b[-1:]
            if fim != b"\n":
                n += 1  # último registro sem quebra de linha
            linhas_sha.append(f"{h.hexdigest()}  {nome}")
            contagem[nome] = n - 1
            print(f"{nome}: {n - 1} linhas de dados", flush=True)
    SHA.write_text("\n".join(linhas_sha) + "\n", encoding="utf-8")
    (DADOS / "linhas.json").write_text(json.dumps(contagem, indent=2), encoding="utf-8")
    for nome, esperado in LINHAS_CADERNO.items():
        obtido = contagem.get(nome, 0) - DESCARTE
        print(f"{nome}: {obtido} linhas depois do descarte; caderno dos autores: {esperado}; "
              f"{'igual' if obtido == esperado else 'DIFERENTE'}", flush=True)


if __name__ == "__main__":
    main()
