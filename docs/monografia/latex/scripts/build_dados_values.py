#!/usr/bin/env python3
"""Confere o SHA-256 dos dados e grava as versões do ambiente citadas na seção de análise estatística.

Confere, antes de gravar, o SHA-256 de cada arquivo contra o valor registrado:
  - registros das hipóteses: docs/monografia/registro/registro_v{1,2,3}.sha256;
  - dados da coleta: a tabela "Dados" de registro_v1.md (ensaios, leituras, janelas);
  - CSV da base da Fraunhofer: docs/monografia/registro/registro_v3_dados.sha256.
Os arquivos exportados depois do registro v1 (repouso, rajadas, gravidade) não têm valor registrado e entram com
o SHA-256 calculado aqui. A base da Fraunhofer fica fora do git; sem ela, o script usa o valor registrado e avisa.

Grava docs/monografia/latex/values/dados_values.tex (versões das bibliotecas) e
a macro \\linhasSha, com as linhas do quadro.

Uso, a partir de kaelix-firmware/:
  /usr/bin/python3 -I docs/monografia/latex/scripts/build_dados_values.py
"""
import hashlib
import json
import pathlib
import re
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[4]
REGISTRO = RAIZ / "docs" / "monografia" / "registro"
CAMPO = RAIZ / "experiments" / "campo" / "dados"
FRAUNHOFER = RAIZ / "experiments" / "fraunhofer" / "dados" / "v2"
VALORES = RAIZ / "docs" / "monografia" / "latex" / "values"
AMBIENTES = [RAIZ / "experiments" / "campo" / "analise_registrada" / "ambiente.json",
             RAIZ / "experiments" / "campo" / "analise_posterior" / "ambiente.json",
             RAIZ / "experiments" / "fraunhofer" / "analise_registrada" / "ambiente.json"]


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def lista_sha(p):
    return {l.split("  ")[1]: l.split("  ")[0] for l in p.read_text(encoding="utf-8").splitlines() if l.strip()}


def tex(s):
    return s.replace("_", r"\_")


def main():
    linhas = []

    # Registros das hipóteses
    for v in (1, 2, 3):
        nome = f"registro_v{v}.md"
        esperado = lista_sha(REGISTRO / f"registro_v{v}.sha256")[nome]
        if sha(REGISTRO / nome) != esperado:
            sys.exit(f"SHA-256 de {nome} diferente do gravado")
        linhas.append(("Registro das hipóteses", nome, esperado))

    # Dados da coleta registrados no registro v1
    tabela = re.findall(r"\| `([^`]+)` \| `([0-9a-f]{64})` \|", (REGISTRO / "registro_v1.md").read_text(encoding="utf-8"))
    registrados = dict(tabela)
    for nome, esperado in registrados.items():
        if sha(CAMPO / nome) != esperado:
            sys.exit(f"SHA-256 de {nome} diferente do registro v1")
        linhas.append(("Coleta em campo", nome, esperado))
    for nome in sorted(p.name for p in CAMPO.iterdir() if p.is_file() and p.name not in registrados):
        linhas.append(("Coleta em campo", nome, sha(CAMPO / nome)))

    # CSV da base da Fraunhofer (registro v3)
    gravado = lista_sha(REGISTRO / "registro_v3_dados.sha256")
    for nome, esperado in gravado.items():
        p = FRAUNHOFER / nome
        if p.exists():
            if sha(p) != esperado:
                sys.exit(f"SHA-256 de {nome} diferente do gravado no download")
        else:
            print(f"aviso: {p} ausente; usado o SHA-256 gravado no registro", file=sys.stderr)
        linhas.append(("Base da Fraunhofer", nome, esperado))

    # Versões do ambiente: as três análises precisam usar as mesmas
    amb = [json.loads(p.read_text(encoding="utf-8")) for p in AMBIENTES]
    for chave in ("python", "numpy", "scipy", "sklearn"):
        if len({a[chave] for a in amb}) != 1:
            sys.exit(f"versões diferentes de {chave} entre as análises: {[a[chave] for a in amb]}")
    a0, ah4 = amb[0], amb[2]
    valores = {"ambPython": a0["python"], "ambNumpy": a0["numpy"], "ambScipy": a0["scipy"],
               "ambSklearn": a0["sklearn"], "ambPandas": ah4["pandas"]}

    VALORES.mkdir(parents=True, exist_ok=True)
    corpo, grupo_anterior = [], None
    for grupo, nome, h in linhas:
        if grupo != grupo_anterior:
            if grupo_anterior is not None:
                corpo.append("\\addlinespace")
            corpo.append(f"\\multicolumn{{2}}{{@{{}}l}}{{\\textit{{{grupo}}}}} \\\\")
            grupo_anterior = grupo
        corpo.append(f"\\texttt{{{tex(nome)}}} & \\texttt{{\\scriptsize {h}}} \\\\")
    # As linhas do quadro vão numa macro: \input dentro de tabular impede \multicolumn no início da linha.
    (VALORES / "dados_values.tex").write_text(
        "% Gerado por scripts/build_dados_values.py; não editar à mão.\n"
        + "".join(f"\\newcommand{{\\{k}}}{{{v}}}\n" for k, v in sorted(valores.items()))
        + "\\newcommand{\\linhasSha}{%\n" + "\n".join(corpo) + "\n}\n", encoding="utf-8")
    print(f"{len(linhas)} arquivos; versões {valores}")


if __name__ == "__main__":
    main()
