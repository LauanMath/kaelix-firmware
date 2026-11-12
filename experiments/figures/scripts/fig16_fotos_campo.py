#!/usr/bin/env python3
"""Monta as figuras fotográficas da coleta em campo de 2 de novembro de 2026.

As fotos ficam fora do repositório, porque mostram a instalação industrial onde
a coleta foi feita e a publicação depende de autorização da empresa. Por isso,
as saídas também ficam fora do git, em experiments/figures/output/campo/ (ver
.gitignore). O texto do TCC usa \\IfFileExists e compila sem elas.

Os recortes e as marcas estão abaixo, em coordenadas relativas da foto já
girada pela orientação EXIF (0 a 1 na largura e na altura). As posições do
transmissor e do gateway foram conferidas pelo autor das fotos.

Saídas, em experiments/figures/output/campo/:
  fig16_montagem_campo.jpg  posição do transmissor nas quatro máquinas
  fig19_maquinas.jpg        as quatro máquinas inteiras
  fig17_pagina_coleta.jpg   telas da página de coleta no celular
  fig18_aplicativo.jpg      telas do aplicativo de mesa, recortadas
  apB_*.jpg                 as mesmas telas e outras, inteiras, para o Apêndice B

Uso:
  uv run python experiments/figures/scripts/fig16_fotos_campo.py [PASTA_DAS_FOTOS]

Sem argumento, a pasta é ../.temp/dados_de_campo, relativa à raiz do
repositório, ou a da variável KAELIX_FOTOS_CAMPO.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from matplotlib import font_manager
from PIL import Image, ImageDraw, ImageFont, ImageOps

RAIZ = Path(__file__).resolve().parents[3]
SAIDA = RAIZ / "experiments" / "figures" / "output" / "campo"

# Painel: (rótulo, arquivo, recorte (x0, y0, x1, y1), marcas [(texto, ponta, cauda)]).
# T marca o transmissor; G, o gateway. Recortes com proporção 4:3.
MONTAGEM = [
    ("a", "dobradeira/dobradeira_motor.jpeg", (0.00, 0.00, 0.80, 0.80),
     [("T", (0.37, 0.25), (0.20, 0.10))]),
    ("b", "guilhotina/guilhotina_motor_back_1.jpg", (0.183, 0.274, 0.728, 1.00),
     [("T", (0.43, 0.70), (0.30, 0.90))]),
    ("c", "calandra/calandra_motor.jpeg", (0.00, 0.074, 1.00, 0.637),
     [("T", (0.70, 0.39), (0.88, 0.58)), ("G", (0.22, 0.52), (0.08, 0.38))]),
    ("d", "compressor/compressor_back_2.jpeg", (0.335, 0.38, 0.78, 0.827),
     [("T", (0.572, 0.50), (0.43, 0.43)), ("G", (0.505, 0.765), (0.40, 0.70))]),
]
PAINEL_MONTAGEM = (1200, 900)

# Máquinas inteiras: (rótulo, arquivo, recorte relativo 4:3, regiões a desfocar em pixels da foto girada).
# Na calandra, a placa de um carro e o logotipo da empresa, ao fundo, são desfocados.
MAQUINAS = [
    ("a", "dobradeira/dobradeira_front.jpeg", (0.0, 0.0, 1.0, 1.0), []),
    ("b", "guilhotina/guilhotina_front.jpeg", (0.0, 0.0, 1.0, 1.0), []),
    ("c", "calandra/calandra_front_view.jpeg", (0.0, 0.0, 1.0, 1.0), [(2690, 940, 2870, 1120)]),
    ("d", "compressor/compressor_back_specs.jpg", (300 / 4160, 0.0, 3420 / 4160, 1.0), []),
]

# Telas: (rótulo, arquivo, faixa vertical mantida em pixels, retângulos a cobrir).
# Os retângulos cobrem o nome da rede Wi-Fi do local, em pixels da captura.
TELAS = [
    ("a", "phone_page_coletor/IMG_6128.PNG", (130, 2190), [(560, 1950, 1090, 2020)]),
    ("b", "phone_page_coletor/IMG_6129.PNG", (190, 2250), [(560, 458, 1090, 528)]),
    ("c", "phone_page_coletor/IMG_6151.PNG", (130, 2190), [(560, 1925, 1090, 1995)]),
]
LARGURA_TELA = 760
FAIXA_ROTULO = 84  # faixa branca acima de cada tela, para a letra do painel

# Aplicativo de mesa: (rótulo, arquivo, recorte em pixels da captura de 3824 × 2336).
# Os recortes tiram a barra lateral e o título da janela e mantêm a área de conteúdo.
APLICATIVO = [
    ("a", "kaelix-desktop-app/Screenshot 2026-11-02 at 08.52.06.png", (1012, 236, 3692, 1079)),
    ("b", "kaelix-desktop-app/Screenshot 2026-11-02 at 15.06.09.png", (535, 236, 3692, 1180)),
    ("c", "kaelix-desktop-app/Screenshot 2026-11-02 at 15.06.30.png", (535, 236, 3692, 1312)),
]
LARGURA_APLICATIVO = 2400

# Apêndice B: telas inteiras, sem recorte, compostas sobre fundo branco (a sombra da janela é
# transparente). Só o nome da rede Wi-Fi de casa é coberto, na tela de gateways.
APENDICE = [
    ("apB_1_monitoramento.jpg", "Screenshot 2026-11-02 at 13.20.49.png", []),
    ("apB_2_logs.jpg", "Screenshot 2026-11-02 at 08.53.24.png", []),
    ("apB_3_motores.jpg", "Screenshot 2026-11-02 at 08.52.19.png", []),
    ("apB_4_gateways.jpg", "Screenshot 2026-11-02 at 08.52.12.png", [(560, 612, 700, 666)]),
    ("apB_5_transmissores.jpg", "Screenshot 2026-11-02 at 08.52.06.png", []),
    ("apB_6_coletas.jpg", "Screenshot 2026-11-02 at 15.06.09.png", []),
    ("apB_7_sinal.jpg", "Screenshot 2026-11-02 at 15.06.30.png", []),
]
LARGURA_APENDICE = 3000

GUTTER = 24
COR_SETA = (230, 159, 0)  # laranja da paleta de Okabe e Ito, com contorno preto
CINZA_COBERTURA = (95, 98, 104)


def fonte(tamanho: int) -> ImageFont.FreeTypeFont:
    caminho = font_manager.findfont(font_manager.FontProperties(family=["Arial", "DejaVu Sans"], weight="bold"))
    return ImageFont.truetype(caminho, tamanho)


def abrir(pasta: Path, nome: str) -> Image.Image:
    return ImageOps.exif_transpose(Image.open(pasta / nome)).convert("RGB")


def rotulo_painel(desenho: ImageDraw.ImageDraw, texto: str, tamanho: int) -> None:
    f = fonte(tamanho)
    margem = tamanho // 3
    caixa = desenho.textbbox((0, 0), texto, font=f)
    w, h = caixa[2] - caixa[0], caixa[3] - caixa[1]
    desenho.rectangle((0, 0, w + 2 * margem, h + 2 * margem), fill="white")
    desenho.text((margem - caixa[0], margem - caixa[1]), texto, font=f, fill="black")


def seta(desenho: ImageDraw.ImageDraw, ponta, cauda, texto: str, escala: float) -> None:
    import math

    (xp, yp), (xc, yc) = ponta, cauda
    ang = math.atan2(yp - yc, xp - xc)
    cab = 34 * escala
    larg = 22 * escala
    base = (xp - cab * math.cos(ang), yp - cab * math.sin(ang))
    nx, ny = -math.sin(ang), math.cos(ang)
    triangulo = [(xp, yp), (base[0] + nx * larg / 2, base[1] + ny * larg / 2),
                 (base[0] - nx * larg / 2, base[1] - ny * larg / 2)]
    desenho.line([cauda, base], fill="black", width=int(12 * escala))
    desenho.polygon(triangulo, fill="black")
    desenho.line([cauda, base], fill=COR_SETA, width=int(6 * escala))
    menor = [(xp - 4 * escala * math.cos(ang), yp - 4 * escala * math.sin(ang)),
             (base[0] + nx * (larg / 2 - 4 * escala), base[1] + ny * (larg / 2 - 4 * escala)),
             (base[0] - nx * (larg / 2 - 4 * escala), base[1] - ny * (larg / 2 - 4 * escala))]
    desenho.polygon(menor, fill=COR_SETA)
    f = fonte(int(44 * escala))
    caixa = desenho.textbbox((0, 0), texto, font=f)
    w, h = caixa[2] - caixa[0], caixa[3] - caixa[1]
    m = int(8 * escala)
    x0, y0 = xc - w / 2 - m, yc - h / 2 - m
    desenho.rectangle((x0, y0, x0 + w + 2 * m, y0 + h + 2 * m), fill="white", outline="black", width=int(3 * escala))
    desenho.text((x0 + m - caixa[0], y0 + m - caixa[1]), texto, font=f, fill="black")


def montagem(pasta: Path) -> Path:
    pw, ph = PAINEL_MONTAGEM
    folha = Image.new("RGB", (2 * pw + GUTTER, 2 * ph + GUTTER), "white")
    for i, (rot, nome, (x0, y0, x1, y1), marcas) in enumerate(MONTAGEM):
        foto = abrir(pasta, nome)
        W, H = foto.size
        recorte = foto.crop((round(x0 * W), round(y0 * H), round(x1 * W), round(y1 * H)))
        painel = recorte.resize((pw, ph), Image.LANCZOS)
        d = ImageDraw.Draw(painel)
        for texto, (xp, yp), (xc, yc) in marcas:
            def local(x, y):
                return ((x - x0) / (x1 - x0) * pw, (y - y0) / (y1 - y0) * ph)
            seta(d, local(xp, yp), local(xc, yc), texto, escala=1.0)
        rotulo_painel(d, rot, 60)
        folha.paste(painel, ((i % 2) * (pw + GUTTER), (i // 2) * (ph + GUTTER)))
    destino = SAIDA / "fig16_montagem_campo.jpg"
    folha.save(destino, quality=90, dpi=(380, 380))
    return destino


def maquinas(pasta: Path) -> Path:
    from PIL import ImageFilter

    pw, ph = PAINEL_MONTAGEM
    folha = Image.new("RGB", (2 * pw + GUTTER, 2 * ph + GUTTER), "white")
    for i, (rot, nome, (x0, y0, x1, y1), desfocar) in enumerate(MAQUINAS):
        foto = abrir(pasta, nome)
        for r in desfocar:
            foto.paste(foto.crop(r).filter(ImageFilter.GaussianBlur(28)), r[:2])
        W, H = foto.size
        recorte = foto.crop((round(x0 * W), round(y0 * H), round(x1 * W), round(y1 * H)))
        painel = recorte.resize((pw, ph), Image.LANCZOS)
        rotulo_painel(ImageDraw.Draw(painel), rot, 60)
        folha.paste(painel, ((i % 2) * (pw + GUTTER), (i // 2) * (ph + GUTTER)))
    destino = SAIDA / "fig19_maquinas.jpg"
    folha.save(destino, quality=90, dpi=(380, 380))
    return destino


def telas(pasta: Path) -> Path:
    paineis = []
    for rot, nome, (ya, yb), cobrir in TELAS:
        tela = abrir(pasta, nome)
        d = ImageDraw.Draw(tela)
        for r in cobrir:
            d.rounded_rectangle(r, radius=12, fill=CINZA_COBERTURA)
        tela = tela.crop((0, ya, tela.width, yb))
        alt = round(tela.height * LARGURA_TELA / tela.width)
        tela = tela.resize((LARGURA_TELA, alt), Image.LANCZOS)
        painel = Image.new("RGB", (LARGURA_TELA, alt + FAIXA_ROTULO), "white")
        painel.paste(tela, (0, FAIXA_ROTULO))
        d = ImageDraw.Draw(painel)
        f = fonte(54)
        caixa = d.textbbox((0, 0), rot, font=f)
        d.text((-caixa[0], (FAIXA_ROTULO - (caixa[3] - caixa[1])) // 2 - caixa[1]), rot, font=f, fill="black")
        paineis.append(painel)
    altura = max(p.height for p in paineis)
    folha = Image.new("RGB", (len(paineis) * LARGURA_TELA + (len(paineis) - 1) * GUTTER, altura), "white")
    for i, p in enumerate(paineis):
        folha.paste(p, (i * (LARGURA_TELA + GUTTER), 0))
    destino = SAIDA / "fig17_pagina_coleta.jpg"
    folha.save(destino, quality=90, dpi=(380, 380))
    return destino


def aplicativo(pasta: Path) -> Path:
    paineis = []
    for rot, nome, caixa_recorte in APLICATIVO:
        tela = abrir(pasta, nome).crop(caixa_recorte)
        alt = round(tela.height * LARGURA_APLICATIVO / tela.width)
        tela = tela.resize((LARGURA_APLICATIVO, alt), Image.LANCZOS)
        painel = Image.new("RGB", (LARGURA_APLICATIVO, alt + FAIXA_ROTULO), "white")
        painel.paste(tela, (0, FAIXA_ROTULO))
        d = ImageDraw.Draw(painel)
        f = fonte(60)
        caixa = d.textbbox((0, 0), rot, font=f)
        d.text((-caixa[0], (FAIXA_ROTULO - (caixa[3] - caixa[1])) // 2 - caixa[1]), rot, font=f, fill="black")
        paineis.append(painel)
    folha = Image.new("RGB", (LARGURA_APLICATIVO, sum(p.height for p in paineis) + GUTTER * (len(paineis) - 1)),
                      "white")
    y = 0
    for p in paineis:
        folha.paste(p, (0, y))
        y += p.height + GUTTER
    destino = SAIDA / "fig18_aplicativo.jpg"
    folha.save(destino, quality=90, dpi=(380, 380))
    return destino


def apendice(pasta: Path) -> list[Path]:
    destinos = []
    for saida, nome, cobrir in APENDICE:
        original = Image.open(pasta / "kaelix-desktop-app" / nome).convert("RGBA")
        tela = Image.new("RGBA", original.size, "white")
        tela.alpha_composite(original)
        tela = tela.convert("RGB")
        d = ImageDraw.Draw(tela)
        for r in cobrir:
            d.rounded_rectangle(r, radius=10, fill=CINZA_COBERTURA)
        alt = round(tela.height * LARGURA_APENDICE / tela.width)
        tela = tela.resize((LARGURA_APENDICE, alt), Image.LANCZOS)
        destino = SAIDA / saida
        tela.save(destino, quality=90, dpi=(476, 476))
        destinos.append(destino)
    return destinos


def main() -> None:
    if len(sys.argv) > 1:
        pasta = Path(sys.argv[1])
    else:
        pasta = Path(os.environ.get("KAELIX_FOTOS_CAMPO", RAIZ.parent / ".temp" / "dados_de_campo"))
    if not pasta.is_dir():
        sys.exit(f"pasta das fotos não encontrada: {pasta}")
    SAIDA.mkdir(parents=True, exist_ok=True)
    for destino in (maquinas(pasta), montagem(pasta), telas(pasta), aplicativo(pasta), *apendice(pasta)):
        print(destino.relative_to(RAIZ), Image.open(destino).size, f"{destino.stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
