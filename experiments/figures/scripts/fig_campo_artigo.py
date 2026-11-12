#!/usr/bin/env python3
"""Figura das máquinas e da posição do transmissor para o artigo da RECIMA21.

Junta, num bloco horizontal, as duas composições da monografia (fig19_maquinas e
fig16_montagem_campo), com uma coluna por máquina: em cima, a máquina inteira
(a a d); embaixo, o motor com o transmissor (T) e, quando aparece, o gateway (G)
(e a h). A figura ocupa a largura do texto com cerca de 56 mm de altura, e por
isso as letras dos painéis e as marcas são maiores que as da monografia.
Recortes, marcas e desfoque são os de fig16_fotos_campo.py, importados de lá,
e as saídas da monografia não mudam.

Saída: experiments/figures/output/campo/fig_campo_artigo.jpg

Uso:
  uv run python experiments/figures/scripts/fig_campo_artigo.py [PASTA_DAS_FOTOS]

Sem argumento, a pasta é a mesma de fig16_fotos_campo.py.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fig16_fotos_campo as base  # noqa: E402

LETRAS = "abcdefgh"
TAM_LETRA = 90     # cerca de 8 pt com o painel impresso a 37 mm de largura
ESCALA_MARCA = 1.8  # T e G com cerca de 7 pt


def painel_maquina(pasta: Path, item) -> Image.Image:
    _, nome, (x0, y0, x1, y1), desfocar = item
    foto = base.abrir(pasta, nome)
    for r in desfocar:
        foto.paste(foto.crop(r).filter(ImageFilter.GaussianBlur(28)), r[:2])
    W, H = foto.size
    recorte = foto.crop((round(x0 * W), round(y0 * H), round(x1 * W), round(y1 * H)))
    return recorte.resize(base.PAINEL_MONTAGEM, Image.LANCZOS)


def painel_montagem(pasta: Path, item) -> Image.Image:
    _, nome, (x0, y0, x1, y1), marcas = item
    pw, ph = base.PAINEL_MONTAGEM
    foto = base.abrir(pasta, nome)
    W, H = foto.size
    recorte = foto.crop((round(x0 * W), round(y0 * H), round(x1 * W), round(y1 * H)))
    painel = recorte.resize((pw, ph), Image.LANCZOS)
    d = ImageDraw.Draw(painel)
    for texto, (xp, yp), (xc, yc) in marcas:
        def local(x, y):
            return ((x - x0) / (x1 - x0) * pw, (y - y0) / (y1 - y0) * ph)
        base.seta(d, local(xp, yp), local(xc, yc), texto, escala=ESCALA_MARCA)
    return painel


def main() -> None:
    if len(sys.argv) > 1:
        pasta = Path(sys.argv[1])
    else:
        pasta = Path(os.environ.get("KAELIX_FOTOS_CAMPO", base.RAIZ.parent / ".temp" / "dados_de_campo"))
    pw, ph = base.PAINEL_MONTAGEM
    g = base.GUTTER
    folha = Image.new("RGB", (4 * pw + 3 * g, 2 * ph + g), "white")
    # As duas listas da monografia estão na mesma ordem de máquinas: dobradeira, guilhotina,
    # calandra e compressor. Letras na ordem de leitura: a a d em cima, e a h embaixo.
    for coluna, (maq, mont) in enumerate(zip(base.MAQUINAS, base.MONTAGEM)):
        for linha, painel in enumerate((painel_maquina(pasta, maq), painel_montagem(pasta, mont))):
            base.rotulo_painel(ImageDraw.Draw(painel), LETRAS[4 * linha + coluna], TAM_LETRA)
            folha.paste(painel, (coluna * (pw + g), linha * (ph + g)))
    destino = base.SAIDA / "fig_campo_artigo.jpg"
    folha.save(destino, quality=90, dpi=(380, 380))
    print(destino.relative_to(base.RAIZ), folha.size)


if __name__ == "__main__":
    main()
