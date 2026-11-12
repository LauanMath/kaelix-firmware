#!/usr/bin/env python3
"""Monta a figura do transmissor e do gateway usados na coleta em campo de 2 de novembro de 2026.

As fotos ficam fora do repositório, em ../.temp/device, relativa à raiz. A saída vai para
experiments/figures/output/campo/, junto com as outras fotos da coleta (ver fig16_fotos_campo.py).

Os recortes estão em coordenadas relativas da foto já girada pela orientação EXIF (0 a 1 na
largura e na altura). Os rótulos dos componentes do painel (c) são desenhados aqui, sobre a foto
sem rótulos (IMG_6183.jpeg). Setas, caixas de texto, letras dos painéis e espaço entre painéis
saem impressos no mesmo tamanho da figura da montagem em campo (fig16_montagem_campo.jpg), que
também entra com a largura do texto.

Saída:
  fig20_dispositivos.jpg  (a) os dois fechados; (b) peças; (c) bloco do transmissor; (d) gateway aberto

Uso:
  uv run --no-project --with pillow --with matplotlib python experiments/figures/scripts/fig20_dispositivos.py [PASTA]
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fig16_fotos_campo import GUTTER, PAINEL_MONTAGEM, RAIZ, SAIDA, abrir, rotulo_painel, seta  # noqa: E402

# Linhas da folha: cada painel é (rótulo, arquivo, recorte (x0, y0, x1, y1), marcas [(texto, ponta, cauda)]).
# As marcas estão em coordenadas relativas da foto inteira, e o texto fica centrado na cauda.
# Os painéis de uma linha têm a mesma altura, e as duas linhas, a mesma largura.
# Pontas do painel (c), nas mesmas posições da versão rotulada pelo autor (tramissor_labels.jpg):
# conector USB-C da ESP32-C3, camada do meio do rádio, conector do TP4056 e base do bloco.
LINHAS = [
    [("a", "final_assembly.jpeg", (0.05, 0.08, 0.95, 0.98), []),
     ("b", "devices_disassembly.png", (0.0, 0.0, 1.0, 1.0), [])],
    [("c", "IMG_6183.jpeg", (0.18, 0.06, 0.93, 0.81),
      [("ESP32-C3 Super Mini", (0.700, 0.357), (0.755, 0.235)),
       ("LoRa Ra-02", (0.427, 0.435), (0.300, 0.330)),
       ("TP4056", (0.379, 0.488), (0.255, 0.470)),
       ("MPU-6050", (0.611, 0.552), (0.700, 0.660))]),
     ("d", "gateway_disassembly.jpeg", (0.20, 0.30, 0.80, 0.90), [])],
]
LARGURA = 2600
# As duas figuras entram com \textwidth; a escala leva os elementos desenhados em pixels por
# fig16_fotos_campo.py (folha de 2 × 1200 + GUTTER px) ao mesmo tamanho impresso nesta folha.
ESCALA = LARGURA / (2 * PAINEL_MONTAGEM[0] + GUTTER)
ESPACO = round(GUTTER * ESCALA)


def montar(pasta: Path) -> Path:
    linhas = []
    for paineis in LINHAS:
        recortes = []
        for rot, nome, caixa, marcas in paineis:
            foto = abrir(pasta, nome)
            W, H = foto.size
            x0, y0, x1, y1 = caixa
            recortes.append((rot, foto.crop((round(x0 * W), round(y0 * H), round(x1 * W), round(y1 * H))), caixa, marcas))
        # Altura comum que faz a linha ocupar a largura total.
        proporcoes = [r.width / r.height for _, r, _, _ in recortes]
        altura = round((LARGURA - ESPACO * (len(recortes) - 1)) / sum(proporcoes))
        linha = Image.new("RGB", (LARGURA, altura), "white")
        x = 0
        for (rot, recorte, (x0, y0, x1, y1), marcas), p in zip(recortes, proporcoes):
            largura = round(altura * p) if rot != recortes[-1][0] else LARGURA - x
            painel = recorte.resize((largura, altura), Image.LANCZOS)
            d = ImageDraw.Draw(painel)
            for texto, (xp, yp), (xc, yc) in marcas:
                def local(u, v):
                    return ((u - x0) / (x1 - x0) * largura, (v - y0) / (y1 - y0) * altura)
                seta(d, local(xp, yp), local(xc, yc), texto, escala=ESCALA)
            rotulo_painel(d, rot, round(60 * ESCALA))
            linha.paste(painel, (x, 0))
            x += largura + ESPACO
        linhas.append(linha)
    folha = Image.new("RGB", (LARGURA, sum(l.height for l in linhas) + ESPACO * (len(linhas) - 1)), "white")
    y = 0
    for linha in linhas:
        folha.paste(linha, (0, y))
        y += linha.height + ESPACO
    destino = SAIDA / "fig20_dispositivos.jpg"
    folha.save(destino, quality=90, dpi=(410, 410))
    return destino


def main() -> None:
    if len(sys.argv) > 1:
        pasta = Path(sys.argv[1])
    else:
        pasta = Path(os.environ.get("KAELIX_FOTOS_DISPOSITIVOS", RAIZ.parent / ".temp" / "device"))
    if not pasta.is_dir():
        sys.exit(f"pasta das fotos não encontrada: {pasta}")
    SAIDA.mkdir(parents=True, exist_ok=True)
    destino = montar(pasta)
    print(destino.relative_to(RAIZ), Image.open(destino).size, f"{destino.stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
