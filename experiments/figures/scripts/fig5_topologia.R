# Figura 5 — comparação de arquiteturas topológicas de rede.
# Arquétipo: composto liderado por esquema. Painel (a) é o herói.
# Contrato: 183 x 150 mm, tipografia 6,5 pt, texto editável, SVG/PDF/TIFF 600 dpi.

script_dir <- function() {
  a <- commandArgs(trailingOnly = FALSE)
  f <- sub("^--file=", "", a[grep("^--file=", a)])
  if (length(f)) dirname(normalizePath(f)) else getwd()
}
here <- script_dir()
source(file.path(here, "theme_kaelix.R"))

# Os literais deste arquivo foram parseados antes de o tema ajustar o
# locale; enc2utf8() marca a codificação para o dispositivo gráfico.
u <- function(x) enc2utf8(x)


suppressPackageStartupMessages({ library(tibble); library(tidyr); library(grid) })

DATA <- file.path(here, "..", "data")
OUT  <- file.path(here, "..", "output")
rd <- function(f) readr::read_csv(file.path(DATA, f), show_col_types = FALSE)

# ---------------------------------------------------------------------------
# (a) HERÓI — cada arranjo como grafo de estrela, em grade 2x2.
# Desenhar a estrela como estrela, e não escrever "xN", é o que distingue
# um diagrama de topologia de uma tabela comparativa com caixas.
# ---------------------------------------------------------------------------
COL_NO   <- pal[["neutral_mid"]]
COL_GW   <- pal[["signal_teal"]]
COL_SRV  <- pal[["neutral_dark"]]
COL_FALT <- pal[["accent_red"]]

topos <- tibble::tribble(
  ~topo,     ~cx, ~cy, ~rot,                             ~nota,
  "atual",   0.00, 1.0, "A   Atual",                     "sem receptor",
  "esp32",   0.52, 1.0, "B   Gateway ESP32",             "1 canal · sem downlink",
  "sbc",     0.00, 0.0, "C   Gateway SBC",               "1 canal · armazena e publica",
  "lorawan", 0.52, 0.0, "D   LoRaWAN",                   "8 canais · downlink classe A"
)

# posições relativas dentro de cada célula (largura 0,46, altura 0,86)
NO_X <- 0.030; NO_W <- 0.088; NO_H <- 0.075
GW_X <- 0.205; GW_W <- 0.105; GW_H <- 0.135
SR_X <- 0.360; SR_W <- 0.092; SR_H <- 0.105
DY   <- c(0.155, 0.000, -0.155)      # três nós por estrela
CY   <- 0.395                        # centro vertical da célula

celulas <- topos |>
  dplyr::rowwise() |>
  dplyr::mutate(dummy = 1) |>
  dplyr::ungroup()

nos <- tidyr::expand_grid(topos, dy = DY) |>
  dplyr::mutate(xmin = cx + NO_X, xmax = cx + NO_X + NO_W,
                yc = cy + CY + dy, ymin = yc - NO_H/2, ymax = yc + NO_H/2)

gw <- dplyr::mutate(topos,
  xmin = cx + GW_X, xmax = cx + GW_X + GW_W,
  yc = cy + CY, ymin = yc - GW_H/2, ymax = yc + GW_H/2,
  falta = topo == "atual")

srv <- dplyr::filter(topos, topo != "atual") |>
  dplyr::mutate(xmin = cx + SR_X, xmax = cx + SR_X + SR_W,
                yc = cy + CY, ymin = yc - SR_H/2, ymax = yc + SR_H/2,
                txt = c("servidor", "broker\n+ painel", "network\nserver"))

raios <- dplyr::left_join(nos, dplyr::select(gw, topo, gx = xmin, gy = yc), by = "topo") |>
  dplyr::transmute(x1 = xmax, y1 = yc, x2 = gx, y2 = gy)

backhaul <- dplyr::left_join(dplyr::select(srv, topo, sx = xmin, sy = yc),
                             dplyr::select(gw, topo, gx = xmax, gy = yc), by = "topo") |>
  dplyr::transmute(x1 = gx, y1 = gy, x2 = sx, y2 = sy)

# downlink existe só no LoRaWAN; desenhar seta de volta onde não há seria
# representar capacidade inexistente.
# Abaixo da estrela, para não cruzar os raios. Só o LoRaWAN tem downlink;
# desenhar seta de volta nos demais representaria capacidade inexistente.
downlink <- dplyr::filter(gw, topo == "lorawan") |>
  dplyr::transmute(x1 = xmin, y1 = cy + 0.205, x2 = cx + NO_X + NO_W, y2 = cy + 0.205,
                   xr = xmin + 0.012, cx = cx)

pa <- ggplot() +
  geom_segment(data = raios, aes(x = x1, y = y1, xend = x2, yend = y2),
               linewidth = 0.28, linetype = "22", colour = pal[["neutral_dark"]]) +
  geom_segment(data = backhaul, aes(x = x1, y = y1, xend = x2, yend = y2),
               linewidth = 0.38, colour = pal[["neutral_dark"]],
               arrow = arrow(length = unit(0.9, "mm"), type = "closed")) +
  geom_segment(data = downlink, aes(x = x1, y = y1, xend = x2, yend = y2),
               linewidth = 0.3, linetype = "22", colour = pal[["signal_blue"]],
               arrow = arrow(length = unit(0.9, "mm"), type = "closed", ends = "last")) +
  geom_text(data = downlink, aes(x = xr, y = y1, label = u("downlink")),
            hjust = 0, size = 1.4, family = "Arial", colour = pal[["signal_blue"]]) +

  geom_rect(data = nos, aes(xmin = xmin, xmax = xmax, ymin = ymin, ymax = ymax),
            fill = COL_NO, colour = NA) +
  geom_text(data = nos, aes(x = (xmin + xmax)/2, y = yc, label = u("nó")),
            colour = "white", size = 1.5, family = "Arial") +

  geom_rect(data = dplyr::filter(gw, !falta),
            aes(xmin = xmin, xmax = xmax, ymin = ymin, ymax = ymax), fill = COL_GW, colour = NA) +
  geom_rect(data = dplyr::filter(gw, falta),
            aes(xmin = xmin, xmax = xmax, ymin = ymin, ymax = ymax),
            fill = "white", colour = COL_FALT, linewidth = 0.35, linetype = "31") +
  geom_text(data = dplyr::filter(gw, falta), aes(x = (xmin + xmax)/2, y = yc, label = "?"),
            colour = COL_FALT, size = 2.2, family = "Arial") +
  geom_text(data = dplyr::filter(gw, !falta),
            aes(x = (xmin + xmax)/2, y = yc,
                label = u(c("ESP32", "Raspberry\nPi", "concen-\ntrador"))),
            colour = "white", size = 1.5, lineheight = 0.95, family = "Arial") +

  geom_rect(data = srv, aes(xmin = xmin, xmax = xmax, ymin = ymin, ymax = ymax),
            fill = COL_SRV, colour = NA) +
  geom_text(data = srv, aes(x = (xmin + xmax)/2, y = yc, label = u(txt)),
            colour = "white", size = 1.4, lineheight = 0.95, family = "Arial") +

  geom_text(data = topos, aes(x = cx + 0.020, y = cy + 0.78, label = u(rot)),
            hjust = 0, size = 2.0, fontface = "bold", family = "Arial",
            colour = pal[["neutral_dark"]]) +
  geom_text(data = topos, aes(x = cx + 0.020, y = cy + 0.115, label = u(nota)),
            hjust = 0, size = 1.5, family = "Arial", colour = pal[["neutral_mid"]]) +

  scale_x_continuous(limits = c(0, 0.985), expand = c(0, 0)) +
  scale_y_continuous(limits = c(0.06, 1.87), expand = c(0, 0)) +
  labs(title = "a") +
  theme_void(base_size = BASE) +
  theme(plot.title = element_text(size = 7, face = "bold", hjust = 0),
        plot.margin = margin(2, 2, 0, 2))

# ---------------------------------------------------------------------------
# (b) o botão que liga alcance e autonomia
# ---------------------------------------------------------------------------
b <- rd("fig5b_sf_tradeoff.csv")
pb <- ggplot(b, aes(x = ganho_db, y = autonomia_dias)) +
  geom_line(linewidth = 0.4, colour = pal[["neutral_mid"]]) +
  geom_point(aes(colour = I(ifelse(atual, pal[["accent_red"]], pal[["signal_blue"]])),
                 size = I(ifelse(atual, 1.5, 0.9)))) +
  # vjust alternado: SF7..SF10 ficam a menos de 1 mm um do outro no eixo x,
  # e rótulos todos acima colidiriam entre si.
  geom_text(aes(label = paste0("SF", sf),
                vjust = ifelse(sf %% 2 == 0, -1.15, 1.9)),
            size = 1.7, family = "Arial", colour = pal[["neutral_dark"]]) +
  annotate("text", x = 6.4, y = 258, label = u("escolha atual"), size = 1.7,
           colour = pal[["accent_red"]], family = "Arial") +
  scale_y_continuous(limits = c(115, 285), breaks = seq(140, 280, 70)) +
  labs(title = "b", x = "ganho de enlace (dB)", y = u("autonomia do nó (dias)")) +
  theme_kaelix()

# ---------------------------------------------------------------------------
# (c) o limite de escala
# ---------------------------------------------------------------------------
cc <- rd("fig5c_colisao.csv") |> dplyr::mutate(sf = factor(paste0("SF", sf), c("SF7","SF9","SF12")))
pc <- ggplot(cc, aes(x = n_nos, y = p_colisao, colour = sf)) +
  geom_line(linewidth = 0.45) +
  scale_colour_manual(values = c(SF7 = pal[["neutral_light"]], SF9 = pal[["signal_blue"]],
                                 SF12 = pal[["accent_orange"]])) +
  # Escala vai ate o maximo real do dado (35,6% para SF12 em 100 nos).
  # Um limite mais apertado esconderia justamente o regime em que a
  # topologia de canal unico deixa de funcionar.
  scale_y_continuous(labels = scales::percent_format(accuracy = 1),
                     limits = c(0, 0.37), breaks = seq(0, 0.35, 0.1)) +
  annotate("text", x = 84, y = 0.325, label = "SF12", size = 1.7,
           colour = pal[["accent_orange"]], family = "Arial") +
  annotate("text", x = 90, y = 0.083, label = "SF9", size = 1.7,
           colour = pal[["signal_blue"]], family = "Arial") +
  annotate("text", x = 92, y = 0.032, label = "SF7", size = 1.7,
           colour = pal[["neutral_mid"]], family = "Arial") +
  scale_x_continuous(breaks = c(1, 25, 50, 75, 100)) +
  labs(title = "c", x = "dispositivos por gateway", y = u("colisão por transmissão")) +
  theme_kaelix() + theme(legend.position = "none")

# ---------------------------------------------------------------------------
# (d) o que a escolha de enlace custa em bateria
# ---------------------------------------------------------------------------
d <- rd("fig5d_enlace.csv") |>
  dplyr::mutate(enlace = u(gsub("\\\\n", "\n", enlace)),
                enlace = factor(enlace, levels = enlace[order(dias)]),
                destaque = dias > 200)
pd <- ggplot(d, aes(x = enlace, y = dias)) +
  geom_col(aes(fill = I(ifelse(destaque, pal[["signal_blue"]], pal[["neutral_light"]]))),
           width = 0.62) +
  geom_text(aes(label = paste0(round(dias), " d")), vjust = -0.45, size = 1.75,
            family = "Arial", colour = pal[["neutral_dark"]]) +
  scale_y_continuous(limits = c(0, 285), expand = expansion(mult = c(0, 0.02))) +
  labs(title = "d", x = NULL, y = u("autonomia do nó (dias)")) +
  theme_kaelix() +
  theme(axis.text.x = element_text(size = BASE - 1.2, lineheight = 0.9))

fig5 <- pa / (pb | pc | pd) + patchwork::plot_layout(heights = c(1.35, 1))

save_pub(fig5, file.path(OUT, "fig5_topologia"), width_mm = 183, height_mm = 152)
cat("fig5_topologia exportada\n")
