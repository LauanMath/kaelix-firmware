# Figura 6 — arquitetura do sistema em camadas, do sensor no motor ao
# manutentor. Segue o modelo de três camadas usual em arquitetura IoT
# (percepção/borda, rede, aplicação), com a estrela desenhada como
# estrela e o protocolo anotado em cada enlace.
# Contrato: 183 x 108 mm, 6,5 pt, texto editável, SVG/PDF/TIFF 600 dpi.

script_dir <- function() {
  a <- commandArgs(trailingOnly = FALSE); f <- sub("^--file=", "", a[grep("^--file=", a)])
  if (length(f)) dirname(normalizePath(f)) else getwd()
}
here <- script_dir()
source(file.path(here, "theme_kaelix.R"))
suppressPackageStartupMessages({ library(tibble); library(grid) })
u <- function(x) enc2utf8(x)
OUT <- file.path(here, "..", "output")

EST <- c(pronto = pal[["signal_blue"]], parcial = pal[["accent_orange"]],
         ausente = pal[["accent_red"]], bloqueado = pal[["neutral_mid"]])

# --- camadas ---------------------------------------------------------------
camadas <- tibble::tribble(
  ~xmin, ~xmax, ~rot,                          ~sub,
  0.005, 0.335, "Percepção / borda",           "aquisição, extração e decisão no nó",
  0.345, 0.630, "Rede",                        "transporte sem fio e concentração",
  0.640, 0.995, "Aplicação",                   "persistência, alerta e ação"
)

# --- máquinas com nó acoplado (a estrela sai daqui) ------------------------
maquinas <- tibble::tibble(
  rot = c(u("perfiladeira"), u("compressor"), u("calandra")),
  y   = c(0.80, 0.55, 0.30),
  est = c("bloqueado", "bloqueado", "bloqueado")
)
NO_X <- 0.175; NO_W <- 0.115; NO_H <- 0.115
GW <- c(x = 0.435, y = 0.55, w = 0.135, h = 0.155)

nos <- dplyr::mutate(maquinas,
  xmin = NO_X, xmax = NO_X + NO_W, ymin = y - NO_H/2, ymax = y + NO_H/2)

# raios da estrela: cada nó converge ao mesmo gateway
raios <- dplyr::transmute(nos, x1 = xmax, y1 = y, x2 = GW["x"], y2 = GW["y"])

# --- blocos da aplicação ---------------------------------------------------
app <- tibble::tribble(
  ~rot,               ~det,                    ~x,    ~y,   ~est,
  "broker / API",     "valida CRC e sequência", 0.665, 0.72, "pronto",
  "histórico",        "uma linha por leitura",  0.665, 0.46, "pronto",
  "painel e alerta",  "entrega ao manutentor",  0.845, 0.59, "ausente"
) |> dplyr::mutate(w = 0.130, h = 0.135,
                   xmin = x, xmax = x + w, ymin = y - h/2, ymax = y + h/2)

# --- enlaces com protocolo anotado -----------------------------------------
enlaces <- tibble::tribble(
  ~x1, ~y1, ~x2, ~y2, ~rot, ~sub, ~tipo,
  GW["x"] + GW["w"], GW["y"], 0.665, 0.60, "LoRa → aplicação", "", "fio"
)
gw_para_app <- tibble::tribble(
  ~x1, ~y1, ~x2, ~y2,
  GW[["x"]] + GW[["w"]], GW[["y"]], app$xmin[1], app$y[1],
  GW[["x"]] + GW[["w"]], GW[["y"]], app$xmin[2], app$y[2]
)
app_interno <- tibble::tibble(
  x1 = app$xmax[1], y1 = app$y[1], x2 = app$xmin[3], y2 = app$y[3] + 0.03)
app_interno2 <- tibble::tibble(
  x1 = app$xmax[2], y1 = app$y[2], x2 = app$xmin[3], y2 = app$y[3] - 0.03)

p <- ggplot() +
  # faixas de camada
  geom_rect(data = camadas, aes(xmin = xmin, xmax = xmax, ymin = 0.155, ymax = 0.94),
            fill = "grey97", colour = pal[["neutral_light"]], linewidth = 0.3) +
  geom_text(data = camadas, aes(x = (xmin + xmax)/2, y = 0.985, label = u(rot)),
            size = 2.1, fontface = "bold", family = "Arial", colour = pal[["neutral_dark"]]) +
  geom_text(data = camadas, aes(x = (xmin + xmax)/2, y = 0.955, label = u(sub)),
            size = 1.55, family = "Arial", colour = pal[["neutral_mid"]]) +

  # estrela: raios antes dos blocos, para passarem por baixo
  geom_segment(data = raios, aes(x = x1, y = y1, xend = x2, yend = y2),
               linewidth = 0.32, linetype = "22", colour = pal[["neutral_dark"]]) +
  # backhaul e ligações internas da aplicação
  geom_segment(data = gw_para_app, aes(x = x1, y = y1, xend = x2, yend = y2),
               linewidth = 0.38, colour = pal[["neutral_dark"]],
               arrow = arrow(length = unit(1.0, "mm"), type = "closed")) +
  geom_segment(data = rbind(app_interno, app_interno2),
               aes(x = x1, y = y1, xend = x2, yend = y2),
               linewidth = 0.38, colour = pal[["neutral_dark"]],
               arrow = arrow(length = unit(1.0, "mm"), type = "closed")) +

  # máquinas
  geom_rect(data = nos, aes(xmin = 0.020, xmax = 0.115, ymin = ymin, ymax = ymax),
            fill = "white", colour = pal[["neutral_mid"]], linewidth = 0.4) +
  geom_text(data = nos, aes(x = 0.0675, y = y, label = rot),
            size = 1.6, family = "Arial", colour = pal[["neutral_dark"]]) +
  geom_segment(data = nos, aes(x = 0.115, y = y, xend = NO_X, yend = y),
               linewidth = 0.45, colour = pal[["neutral_dark"]]) +

  # nós Kaelix
  geom_rect(data = nos, aes(xmin = xmin, xmax = xmax, ymin = ymin, ymax = ymax,
                            fill = I(EST[est])), colour = NA) +
  geom_text(data = nos, aes(x = (xmin + xmax)/2, y = y + 0.022, label = u("nó Kaelix")),
            colour = "white", size = 1.75, fontface = "bold", family = "Arial") +
  geom_text(data = nos, aes(x = (xmin + xmax)/2, y = y - 0.022,
                            label = u("MPU6050 · NTC")),
            colour = "white", size = 1.4, family = "Arial") +

  # gateway
  annotate("rect", xmin = GW[["x"]], xmax = GW[["x"]] + GW[["w"]],
           ymin = GW[["y"]] - GW[["h"]]/2, ymax = GW[["y"]] + GW[["h"]]/2,
           fill = EST[["pronto"]], colour = NA) +
  annotate("text", x = GW[["x"]] + GW[["w"]]/2, y = GW[["y"]] + 0.028,
           label = u("gateway"), colour = "white", size = 1.9,
           fontface = "bold", family = "Arial") +
  annotate("text", x = GW[["x"]] + GW[["w"]]/2, y = GW[["y"]] - 0.002,
           label = u("SX1278 + SBC"), colour = "white", size = 1.4, family = "Arial") +
  annotate("text", x = GW[["x"]] + GW[["w"]]/2, y = GW[["y"]] - 0.032,
           label = u("CRC · lacuna · alerta"), colour = "white", size = 1.3, family = "Arial") +

  # aplicação
  geom_rect(data = app, aes(xmin = xmin, xmax = xmax, ymin = ymin, ymax = ymax,
                            fill = I(EST[est])), colour = NA) +
  geom_text(data = app, aes(x = (xmin + xmax)/2, y = y + 0.020, label = u(rot)),
            colour = "white", size = 1.75, fontface = "bold", family = "Arial") +
  geom_text(data = app, aes(x = (xmin + xmax)/2, y = y - 0.020, label = u(det)),
            colour = "white", size = 1.35, family = "Arial") +

  # anotações de protocolo, que é o que falta num diagrama de caixas
  annotate("text", x = 0.487, y = 0.310, label = u("LoRa 433 MHz · SF9"),
           size = 1.6, family = "Arial", colour = pal[["neutral_dark"]], hjust = 0.5) +
  annotate("text", x = 0.487, y = 0.278, label = u("20 B a cada 10 min · 185 ms no ar"),
           size = 1.4, family = "Arial", colour = pal[["neutral_mid"]], hjust = 0.5) +
  annotate("text", x = 0.487, y = 0.246, label = u("estrela · sem downlink"),
           size = 1.4, family = "Arial", colour = pal[["neutral_mid"]], hjust = 0.5) +
  annotate("text", x = 0.617, y = 0.685, label = u("MQTT"), size = 1.5,
           family = "Arial", colour = pal[["neutral_dark"]], hjust = 0.5) +
  annotate("text", x = 0.152, y = 0.238, label = u("fixação magnética"),
           size = 1.4, family = "Arial", colour = pal[["neutral_mid"]], hjust = 0.5) +
  annotate("text", x = 0.0675, y = 0.198, label = u("equipamentos da planta"),
           size = 1.4, family = "Arial", colour = pal[["neutral_mid"]], hjust = 0.5) +

  scale_x_continuous(limits = c(0, 1), expand = c(0, 0)) +
  scale_y_continuous(limits = c(0.14, 1.0), expand = c(0, 0)) +
  theme_void(base_size = BASE) + theme(plot.margin = margin(2, 2, 1, 2))

leg <- tibble::tibble(
  x = c(0.06, 0.34, 0.64), 
  txt = c("implementado e testado", "não existe", "bloqueado por hardware"),
  cor = unname(EST[c("pronto", "ausente", "bloqueado")]))
pl <- ggplot(leg) +
  geom_rect(aes(xmin = x, xmax = x + 0.020, ymin = 0.3, ymax = 0.7, fill = I(cor)), colour = NA) +
  geom_text(aes(x = x + 0.028, y = 0.5, label = u(txt)), hjust = 0, size = 1.7,
            family = "Arial", colour = pal[["neutral_dark"]]) +
  scale_x_continuous(limits = c(0, 1), expand = c(0, 0)) +
  scale_y_continuous(limits = c(0, 1), expand = c(0, 0)) + theme_void()

save_pub(p / pl + patchwork::plot_layout(heights = c(1, 0.07)),
         file.path(OUT, "fig6_cadeia"), width_mm = 183, height_mm = 92)
cat("fig6_cadeia exportada\n")
