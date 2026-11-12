"""Baixa da versão 151.3 da base da Fraunhofer só os CSV que a H4 usa (0D, 0E, 1E, 2E, 3E e 4E).

A Fordatis está fora do ar, e a cópia da versão 151.2 no Internet Archive termina em 2 GiB. A versão 151.3
(fraunhofer_eas_dataset_for_unbalance_detection_v2.zip, 2.950.666.199 bytes) tem uma captura completa no
Internet Archive, de 14/12/2022, que aceita pedidos por faixa de bytes. Os CSV dela têm o mesmo CRC-32 e o
mesmo tamanho dos da versão 151.2 nos membros que dá para comparar (0D a 4D e 0E); a 151.3 acrescenta
arquivos a1_tsfresh.npy, que a H4 não usa.

Para cada membro, o script lê o diretório central no fim do ZIP, baixa só os bytes comprimidos do membro em
faixas paralelas (com retomada), descomprime, confere CRC-32 e tamanho com o diretório central e grava o CSV
e o SHA-256 dele. Depois, conta as linhas de 0E e 4E depois do descarte dos 50.000 primeiros valores e
compara com os cadernos dos autores, como no registro v2.

Saídas, em experiments/fraunhofer/dados/v2/ (fora do git): os seis CSV, membros.json e v2_membros.sha256.

Uso, a partir de kaelix-firmware/:
  taskpolicy -b /usr/bin/python3 -I experiments/fraunhofer/baixar_membros_v2.py
"""
import concurrent.futures as cf
import hashlib
import json
import pathlib
import struct
import time
import urllib.error
import urllib.request
import zlib

RAIZ = pathlib.Path(__file__).resolve().parents[2]
DADOS = RAIZ / "experiments" / "fraunhofer" / "dados"
SAIDA = DADOS / "v2"
URL = ("http://web.archive.org/web/20221214062352id_/https://fordatis.fraunhofer.de/bitstream/fordatis/151.3/3/"
       "fraunhofer_eas_dataset_for_unbalance_detection_v2.zip")
TAMANHO = 2_950_666_199
MEMBROS = ["0D.csv", "0E.csv", "1E.csv", "2E.csv", "3E.csv", "4E.csv"]
LINHAS_CADERNO = {"0E.csv": 6_843_567, "4E.csv": 6_864_047}
DESCARTE = 50_000
FAIXA = 32 << 20  # 32 MiB por pedido
CONEXOES = 6
BLOCO = 1 << 20


def pedir(a, b, tentativas=200):
    for t in range(tentativas):
        try:
            req = urllib.request.Request(URL, headers={"Range": f"bytes={a}-{b}"})
            with urllib.request.urlopen(req, timeout=120) as r:
                faixa = r.headers.get("Content-Range", "")
                if r.status != 206 or not faixa.endswith(f"/{TAMANHO}"):
                    raise RuntimeError(f"HTTP {r.status}, Content-Range '{faixa}'")
                dados = r.read()
            if len(dados) != b - a + 1:
                raise RuntimeError(f"{len(dados)} bytes em vez de {b - a + 1}")
            return dados
        except (urllib.error.URLError, OSError, RuntimeError) as e:
            print(f"  bytes {a}-{b}: {e}; tentando de novo", flush=True)
            time.sleep(min(60, 5 * (t + 1)))
    raise SystemExit(f"faixa {a}-{b} não baixada")


def zip64(extra, campos):
    i = 0
    while i + 4 <= len(extra):
        tag, tam = struct.unpack_from("<HH", extra, i)
        if tag == 1:
            return [struct.unpack_from("<Q", extra, i + 4 + 8 * k)[0] for k in range(len(campos))]
        i += 4 + tam
    raise RuntimeError("campo ZIP64 ausente")


def diretorio_central():
    fim = pedir(TAMANHO - (1 << 18), TAMANHO - 1)
    base = TAMANHO - len(fim)
    k = fim.rfind(b"PK\x05\x06")
    n = struct.unpack_from("<H", fim, k + 10)[0]
    cd_ini = struct.unpack_from("<I", fim, k + 16)[0]
    if cd_ini == 0xFFFFFFFF or n == 0xFFFF:
        r = struct.unpack_from("<Q", fim, fim.rfind(b"PK\x06\x07") + 8)[0] - base
        n, _, cd_ini = struct.unpack_from("<QQQ", fim, r + 32)
    i, membros = cd_ini - base, {}
    for _ in range(n):
        if fim[i:i + 4] != b"PK\x01\x02":
            raise RuntimeError("diretório central fora do trecho lido")
        metodo = struct.unpack_from("<H", fim, i + 10)[0]
        crc, comp, desc = struct.unpack_from("<III", fim, i + 16)
        ln, le, lc = struct.unpack_from("<HHH", fim, i + 28)
        off = struct.unpack_from("<I", fim, i + 42)[0]
        nome = fim[i + 46:i + 46 + ln].decode()
        campos = [c for c, v in (("desc", desc), ("comp", comp), ("off", off)) if v == 0xFFFFFFFF]
        if campos:
            vals = dict(zip(campos, zip64(fim[i + 46 + ln:i + 46 + ln + le], campos)))
            desc, comp, off = vals.get("desc", desc), vals.get("comp", comp), vals.get("off", off)
        membros[nome] = {"metodo": metodo, "crc32": crc, "comprimido": comp, "descomprimido": desc, "offset": off}
        i += 46 + ln + le + lc
    return membros


def baixar_faixa(parte, a, b):
    if parte.exists() and parte.stat().st_size == b - a + 1:
        return
    parte.write_bytes(pedir(a, b))


def main():
    SAIDA.mkdir(parents=True, exist_ok=True)
    (DADOS / ".gitignore").write_text("*\n", encoding="utf-8")
    central = diretorio_central()
    tarefas, planos = [], {}
    for nome in MEMBROS:
        m = central[nome]
        if m["metodo"] != 8:
            raise RuntimeError(f"{nome}: método de compressão {m['metodo']}")
        cab = pedir(m["offset"], m["offset"] + 29)
        if cab[:4] != b"PK\x03\x04":
            raise RuntimeError(f"{nome}: cabeçalho local não encontrado")
        ln, le = struct.unpack_from("<HH", cab, 26)
        ini = m["offset"] + 30 + ln + le
        faixas = [(a, min(a + FAIXA, ini + m["comprimido"]) - 1) for a in range(ini, ini + m["comprimido"], FAIXA)]
        pasta = SAIDA / (nome + ".partes")
        pasta.mkdir(exist_ok=True)
        planos[nome] = [(pasta / f"{k:04d}.bin", a, b) for k, (a, b) in enumerate(faixas)]
        tarefas += planos[nome]
    total = sum(b - a + 1 for _, a, b in tarefas)
    print(f"{len(tarefas)} faixas, {total / 1e9:.2f} GB", flush=True)
    feito = 0
    with cf.ThreadPoolExecutor(CONEXOES) as ex:
        futuros = {ex.submit(baixar_faixa, p, a, b): b - a + 1 for p, a, b in tarefas}
        for f in cf.as_completed(futuros):
            f.result()
            feito += futuros[f]
            print(f"  {feito / 1e9:.2f} de {total / 1e9:.2f} GB", flush=True)

    linhas_sha, resumo = [], {}
    for nome in MEMBROS:
        m = central[nome]
        d = zlib.decompressobj(-15)
        crc, n, h, linhas, fim = 0, 0, hashlib.sha256(), 0, b"\n"
        with open(SAIDA / nome, "wb") as out:
            for parte, _, _ in planos[nome]:
                with open(parte, "rb") as g:
                    for bloco in iter(lambda: g.read(BLOCO), b""):
                        x = d.decompress(bloco)
                        if x:
                            out.write(x)
                            crc = zlib.crc32(x, crc)
                            h.update(x)
                            n += len(x)
                            linhas += x.count(b"\n")
                            fim = x[-1:]
            x = d.flush()
            if x:
                out.write(x)
                crc = zlib.crc32(x, crc)
                h.update(x)
                n += len(x)
                linhas += x.count(b"\n")
                fim = x[-1:]
        if crc != m["crc32"] or n != m["descomprimido"]:
            raise SystemExit(f"{nome}: CRC-32 {crc:08x} e {n} bytes; esperado {m['crc32']:08x} e {m['descomprimido']}")
        if fim != b"\n":
            linhas += 1
        resumo[nome] = {"crc32": f"{crc:08x}", "bytes": n, "linhas_de_dados": linhas - 1, "sha256": h.hexdigest()}
        linhas_sha.append(f"{h.hexdigest()}  {nome}")
        print(f"{nome}: CRC-32 {crc:08x} conferido, {n} bytes, {linhas - 1} linhas de dados", flush=True)
        for parte, _, _ in planos[nome]:
            parte.unlink()
        (SAIDA / (nome + ".partes")).rmdir()
    (SAIDA / "v2_membros.sha256").write_text("\n".join(linhas_sha) + "\n", encoding="utf-8")
    (SAIDA / "membros.json").write_text(json.dumps({"url": URL, "tamanho_zip": TAMANHO, "membros": resumo},
                                                   indent=2), encoding="utf-8")
    for nome, esperado in LINHAS_CADERNO.items():
        obtido = resumo[nome]["linhas_de_dados"] - DESCARTE
        print(f"{nome}: {obtido} linhas depois do descarte; caderno dos autores: {esperado}; "
              f"{'igual' if obtido == esperado else 'DIFERENTE'}", flush=True)


if __name__ == "__main__":
    main()
