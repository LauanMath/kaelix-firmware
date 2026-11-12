"""Controle de auditoria do TCC por hash, fora dos arquivos .tex.

Cada arquivo de texto do TCC tem um arquivo de auditoria em docs/monografia/audit/. Cada registro de versão traz a data, o
arquivo e o SHA-256 do .tex naquela versão. Os .tex não têm comentários de linha inteira: fontes, conferências e
aprovações ficam só na auditoria, para que nada desse controle chegue ao PDF.

Uso, da raiz do repositório:
/usr/bin/python3 docs/monografia/audit/audit.py                       # situação de cada arquivo
/usr/bin/python3 docs/monografia/audit/audit.py record ARQUIVO "nota" # registra a versão atual de ARQUIVO

ARQUIVO é o caminho relativo à pasta do modelo LaTeX, como chapters/01introducao.tex. O comando record acrescenta ao
arquivo de auditoria correspondente um registro com a data de hoje, o hash atual e a nota, e só aceita um .tex sem
comentários de linha inteira.
"""

import datetime
import hashlib
import re
import sys
from pathlib import Path

AUDIT = Path(__file__).resolve().parent
TEX = AUDIT.parent / "latex"
TRACKED = {
    "chapters/01introducao.tex": "section_1_introduction.md",
    "chapters/02fundamentacao.tex": "section_2_background.md",
    "chapters/03materiais_metodos.tex": "section_3_materials_methods.md",
    "chapters/04resultados.tex": "section_4_results.md",
    "chapters/05discussao.tex": "section_5_discussion.md",
    "chapters/06conclusao.tex": "section_6_conclusion.md",
    "pre-textuais/folha-aprovacao.tex": "front_matter.md",
    "pre-textuais/resumo.tex": "front_matter.md",
    "pre-textuais/abstract.tex": "front_matter.md",
    "pre-textuais/abrev.tex": "front_matter.md",
    "pre-textuais/simbolos.tex": "front_matter.md",
    "appendices/a_quadro_estudos.tex": "appendices.md",
    "appendices/b_dados_codigo.tex": "appendices.md",
    "appendices/c_tabelas.tex": "appendices.md",
    "appendices/d_telas.tex": "appendices.md",
    "appendices/e_protocolo.tex": "appendices.md",
}
ENTRY = re.compile(r"^### (\d{2}/\d{2}/\d{4}) · `([^`]+)` · SHA-256 `([0-9a-f]{64})`", re.M)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def comment_lines(path):
    """Linhas que são só comentário; o % precedido de barra invertida é o sinal de porcentagem."""
    return [n for n, line in enumerate(path.read_text().splitlines(), 1) if line.lstrip().startswith("%")]


def last_hash(tex_name):
    md = AUDIT / TRACKED[tex_name]
    found = [h for _, name, h in ENTRY.findall(md.read_text()) if name == tex_name] if md.exists() else []
    return found[-1] if found else None


def status():
    problems = 0
    for name in TRACKED:
        path = TEX / name
        comments = comment_lines(path)
        current, recorded = sha256(path), last_hash(name)
        if comments:
            state = f"COMENTÁRIOS NO .tex (linhas {', '.join(map(str, comments))})"
        elif recorded is None:
            state = "SEM REGISTRO"
        elif recorded != current:
            state = "ALTERADO DEPOIS DO ÚLTIMO REGISTRO"
        else:
            state = "ok"
        problems += state != "ok"
        print(f"{state:<36} {name}  {current[:12]}")
    return problems


def record(name, note):
    if name not in TRACKED:
        sys.exit(f"{name} não está entre os arquivos controlados")
    path = TEX / name
    if comment_lines(path):
        sys.exit(f"{name} tem comentários de linha inteira; leve o conteúdo para docs/monografia/audit/{TRACKED[name]} antes de registrar")
    today = datetime.date.today().strftime("%d/%m/%Y")
    entry = f"\n### {today} · `{name}` · SHA-256 `{sha256(path)}`\n\n{note.strip()}\n"
    with open(AUDIT / TRACKED[name], "a") as f:
        f.write(entry)
    print(entry.strip())


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "record":
        if len(sys.argv) != 4:
            sys.exit('uso: audit.py record ARQUIVO "nota"')
        record(sys.argv[2], sys.argv[3])
    else:
        sys.exit(1 if status() else 0)
