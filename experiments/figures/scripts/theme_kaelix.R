# Tema e utilitários compartilhados pelas figuras do Kaelix.
#
# Locale UTF-8 antes de tudo. Com LC_CTYPE=C — que é o default de um
# Rscript disparado de um shell sem locale configurado — o R trata os
# bytes UTF-8 individualmente, nchar("nó") devolve 3 em vez de 2, e o
# dispositivo gráfico não mapeia os glifos acentuados: "nó" sai como
# "n..". As figuras que leem rótulo de CSV escapam disso porque o readr
# marca a codificação; as que têm texto no próprio fonte, não.
local({
  for (loc in c("pt_BR.UTF-8", "en_US.UTF-8", "C.UTF-8")) {
    if (nzchar(suppressWarnings(Sys.setlocale("LC_CTYPE", loc)))) break
  }
})
# Segue o contrato de figura: tipografia 6.5 pt, texto editável no SVG/PDF,
# uma família neutra + uma de sinal + uma de destaque.

suppressPackageStartupMessages({
  library(ggplot2)
  library(patchwork)
  library(dplyr)
  library(readr)
  library(scales)
})

# --- paleta -----------------------------------------------------------------
# neutra para contexto, azul para a condição de referência/correta,
# vermelho reservado a perda de desempenho e erro metodológico.
#
# Duas famílias por matiz, com papéis distintos:
#   *_series : marcas de linha, ponto e barra. Contraste >= 3:1 contra o fundo.
#   *_wash   : faixas de anotação desenhadas com alpha 0.10-0.16, onde o baixo
#              contraste é intencional e o preenchimento não codifica série.
# Misturar os dois papéis foi o defeito da versão anterior: teal e laranja
# claros serviam de série em fig1/fig4/fig5/fig7/fig11 e ficavam abaixo de 3:1.
#
# Verificado com o validador de paletas (checagens de faixa de luminosidade,
# piso de croma, separação sob daltonismo, piso de visão normal e contraste):
#   #3182BD, #8C2D1E, #06775A, #8a5a00 -> todas as checagens passam
#   pior par sob deutanopia: #06775A/#8C2D1E, dE 8.6; visão normal dE 15.4
pal <- c(
  neutral_dark  = "#272727",
  neutral_mid   = "#767676",
  neutral_light = "#D8D8D8",
  signal_blue   = "#3182BD",
  signal_teal   = "#06775A",   # série: escurecido de #33B5A5 (contraste 2.47)
  accent_red    = "#8C2D1E",   # escuro: separa de signal_blue em cinza
  accent_orange = "#8a5a00",   # série: escurecido de #E28E2C (contraste 2.51)
  teal_wash     = "#33B5A5",   # faixa de anotação apenas, nunca série
  orange_wash   = "#E28E2C"    # faixa de anotação apenas, nunca série
)

# vocabulário visual fixo, reusado em todos os painéis das duas figuras
cond_cols   <- c("sadio" = pal[["signal_blue"]], "defeito" = pal[["accent_red"]])
metodo_cols <- c("correto" = pal[["signal_blue"]], "incorreto" = pal[["accent_red"]])

BASE <- 6.5

# A família precisa casar com o corpo do documento que consome a figura. O TCC
# compõe em Times (pacote `times` no principal.tex); uma figura em Arial lê-se
# como elemento colado de outro documento, e essa era a queixa visual principal.
# Para voltar a sans, trocar a linha abaixo — nada mais depende disso.
FAMILY <- "Times New Roman"

theme_kaelix <- function(base_size = BASE, base_family = FAMILY) {
  theme_classic(base_size = base_size, base_family = base_family) +
    theme(
      axis.line    = element_line(linewidth = 0.35, colour = "black"),
      axis.ticks   = element_line(linewidth = 0.35, colour = "black"),
      axis.title   = element_text(size = base_size),
      axis.text    = element_text(size = base_size - 0.5, colour = "black"),
      legend.title = element_blank(),
      legend.text  = element_text(size = base_size - 0.7),
      legend.key.size = unit(2.6, "mm"),
      legend.margin   = margin(0, 0, 0, 0),
      legend.background = element_blank(),
      strip.text   = element_text(size = base_size - 0.3, face = "bold"),
      strip.background = element_blank(),
      plot.title   = element_text(size = base_size + 0.3, face = "bold",
                                  margin = margin(b = 1.5)),
      plot.subtitle = element_text(size = base_size - 0.7,
                                   colour = pal[["neutral_mid"]],
                                   margin = margin(b = 2.5)),
      plot.margin  = margin(2, 2, 2, 2),
      panel.grid   = element_blank()
    )
}

theme_set(theme_kaelix())

# --- exportação -------------------------------------------------------------
# Larguras Nature: 89 mm (coluna simples), 183 mm (largura dupla).
save_pub <- function(plot, filename, width_mm = 183, height_mm = 120, dpi = 600) {
  w <- width_mm / 25.4
  h <- height_mm / 25.4

  svglite::svglite(paste0(filename, ".svg"), width = w, height = h)
  print(plot); invisible(dev.off())

  grDevices::cairo_pdf(paste0(filename, ".pdf"), width = w, height = h, family = FAMILY)
  print(plot); invisible(dev.off())

  ragg::agg_tiff(paste0(filename, ".tiff"), width = w, height = h,
                 units = "in", res = dpi, compression = "lzw")
  print(plot); invisible(dev.off())

  ragg::agg_png(paste0(filename, ".png"), width = w, height = h,
                units = "in", res = 300)
  print(plot); invisible(dev.off())

  cat(sprintf("  %s  [svg pdf tiff png]  %.0f x %.0f mm\n",
              basename(filename), width_mm, height_mm))
}

tag_theme <- theme(plot.tag = element_text(size = 8, face = "bold"),
                   plot.tag.position = c(0, 1))
