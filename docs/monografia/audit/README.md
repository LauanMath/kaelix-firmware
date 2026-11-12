# Auditoria da monografia

Fontes, conferências e aprovações do texto ficam nesta pasta, e não em comentários nos `.tex`, para que nada desse controle passe para o PDF. O padrão é o mesmo do outro TCC do autor.

- **Um arquivo por seção:** `section_1_introduction.md` a `section_6_conclusion.md`; `front_matter.md` para folha de aprovação, resumo, abstract, siglas e símbolos (capa e folha de rosto saem de `preambulo/dados.tex` e do estilo do iCEV); `appendices.md` para os apêndices.
- **Conteúdo:** as fontes e conferências de cada trecho e o registro de versões, com data, arquivo, SHA-256 do `.tex`, o que mudou e quem aprovou.
- **Situação:** `/usr/bin/python3 docs/monografia/audit/audit.py`, a partir de `kaelix-firmware/`, lista cada `.tex` e aponta o que foi alterado depois do último registro, o que não tem registro e o que tem comentário de linha inteira.
- **Registro novo:** depois de uma mudança aprovada, `/usr/bin/python3 docs/monografia/audit/audit.py record ARQUIVO "nota"`, com ARQUIVO relativo a `latex/`, como `chapters/01introducao.tex`.
