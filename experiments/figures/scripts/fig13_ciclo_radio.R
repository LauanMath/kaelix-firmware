# Figura 13: linha do tempo de um ciclo de medição com sinal bruto, calculada a
# partir dos tempos no ar e das esperas de lib/kaelix_protocol/kaelix_protocol.h.
# Dados: fig13_ciclo.csv e fig13_parametros.csv (export_protocolo_data.py).
# Contrato: 160 x 92 mm, Arial de 5 a 7 pt, texto editável, SVG/PDF/TIFF 600 dpi.
# A perda dos fragmentos 7 e 18 na primeira tentativa é um exemplo, não medição.

script_dir <- function() {
  a <- commandArgs(trailingOnly = FALSE); f <- sub("^--file=", "", a[grep("^--file=", a)])
  if (length(f)) dirname(normalizePath(f)) else getwd()
}
here <- script_dir()
source(file.path(here, "theme_kaelix.R"))
# Padrão da Nature (guia de figuras da Nature, pedido do usuário em 08/11/2026): Arial, texto de 5 a 7 pt,
# todo o texto em preto e rótulos com inicial maiúscula, como nas figuras da seção de resultados. O tema
# compartilhado continua em Times para as figuras que ainda não passaram ao padrão.
FAMILY <- "Arial"
DATA <- file.path(here, "..", "data")
OUT <- file.path(here, "..", "output")
u <- function(x) enc2utf8(x)
SIZE <- 7

seg <- readr::read_csv(file.path(DATA, "fig13_ciclo.csv"), show_col_types = FALSE)
par <- readr::read_csv(file.path(DATA, "fig13_parametros.csv"), show_col_types = FALSE,
                       col_types = readr::cols(.default = "c"))
P <- setNames(par$valor, par$parametro)
num <- function(k) as.numeric(P[[k]])
dec <- function(x, d = 1) formatC(x, format = "f", digits = d, decimal.mark = ",")

# Faixas: o transmissor em cima, o gateway embaixo.
LANE <- c(transmissor = 2, gateway = 1)
H <- 0.32
seg <- seg |>
  mutate(y = LANE[lado], s0 = inicio_ms / 1000, s1 = fim_ms / 1000,
         cor = dplyr::case_when(evento == "escuta" ~ "escuta",
                                evento == "aquisição" ~ "aquisição",
                                perdido == 1 ~ "perdido",
                                TRUE ~ canal))

# Os dois perfis são do mesmo rádio LoRa: o mesmo matiz, com o escuro no canal de controle e o claro na rajada.
COR <- c(controle = tol[["lora"]], rajada = tol[["lora_claro"]],
         `aquisição` = tol[["cinza_claro"]], perdido = "white", escuta = NA)
ROT <- c(controle = u(sprintf("Canal de controle (SF%s, %s kHz)", P[["controle_sf"]], dec(num("controle_bw_khz"), 0))),
         rajada = u(sprintf("Perfil de rajada (SF%s, %s kHz)", P[["rajada_sf"]], dec(num("rajada_bw_khz"), 0))),
         `aquisição` = u("Aquisição, sem rádio"),
         perdido = u("Fragmento perdido (exemplo)"))

solid <- dplyr::filter(seg, evento != "escuta")
listen <- dplyr::filter(seg, evento == "escuta")
lost <- dplyr::filter(seg, perdido == 1)

base_plot <- function(d, xlim, breaks) {
  ggplot(d) +
    geom_rect(data = listen, aes(xmin = s0, xmax = s1, ymin = y - H, ymax = y + H),
              fill = NA, colour = pal[["neutral_dark"]], linewidth = 0.3, linetype = "22") +
    geom_rect(aes(xmin = s0, xmax = s1, ymin = y - H, ymax = y + H, fill = cor),
              colour = ifelse(d$cor == "perdido", pal[["neutral_dark"]], NA), linewidth = 0.3) +
    geom_point(data = dplyr::filter(lost, s0 >= xlim[1], s1 <= xlim[2]),
               aes(x = (s0 + s1) / 2, y = y), shape = 4, size = 1.4, stroke = 0.45,
               colour = pal[["neutral_dark"]]) +
    scale_fill_manual(values = COR, breaks = names(ROT), labels = ROT, na.translate = FALSE,
                      guide = guide_legend(override.aes = list(
                        colour = c(NA, NA, NA, pal[["neutral_dark"]]), linewidth = 0.3))) +
    scale_y_continuous(breaks = unname(LANE), labels = c(expression("Transmissor"), expression(italic("Gateway"))),
                       limits = c(0.45, 2.75), expand = c(0, 0)) +
    scale_x_continuous(breaks = breaks, labels = function(x) dec(x, ifelse(max(breaks) > 3, 0, 1)),
                       expand = c(0, 0)) +
    coord_cartesian(xlim = xlim, clip = "on") +
    labs(x = substitute(paste(a, italic(t), " (s)"), list(a = u("Tempo desde o início do ciclo, "))), y = NULL) +
    theme_kaelix(SIZE) +
    theme(axis.line.y = element_blank(), axis.ticks.y = element_blank(),
          axis.line.x = element_line(linewidth = 0.6 / .pt), axis.ticks.x = element_line(linewidth = 0.6 / .pt),
          legend.position = "bottom", legend.key.size = unit(2.6, "mm"),
          legend.text = element_text(size = SIZE - 0.5))
}

frag <- dplyr::filter(seg, evento == "fragmento")
r1 <- dplyr::filter(frag, rodada == 1); r2 <- dplyr::filter(frag, rodada == 2)
burst_start <- min(r1$s0)
cycle_end <- num("fim_ms") / 1000
interval <- num("intervalo_ciclo_ms") / 1000
maps <- dplyr::filter(seg, evento == "mapa")

# a: ciclo inteiro, até o início do ciclo seguinte.
ann_y <- 2.52
pa <- base_plot(solid, c(0, interval), seq(0, interval, by = 1)) +
  annotate("segment", x = interval, xend = interval, y = 0.55, yend = 2.45,
           linewidth = 0.3, linetype = "42", colour = pal[["neutral_mid"]]) +
  annotate("text", x = interval - 0.06, y = 0.62, hjust = 1, size = (SIZE - 0.6) / .pt,
           family = FAMILY, colour = "black",
           label = u(sprintf("Início do ciclo seguinte (%s s)", dec(interval, 0)))) +
  annotate("segment", x = burst_start, xend = max(r1$s1), y = ann_y, yend = ann_y,
           linewidth = 0.3, colour = pal[["neutral_dark"]]) +
  annotate("text", x = (burst_start + max(r1$s1)) / 2, y = ann_y + 0.13, size = (SIZE - 0.5) / .pt,
           family = FAMILY, colour = "black",
           label = u(sprintf("Tentativa 1: %d fragmentos em %s s", nrow(r1), dec(max(r1$s1) - burst_start)))) +
  annotate("segment", x = min(r2$s0), xend = max(r2$s1), y = ann_y, yend = ann_y,
           linewidth = 0.3, colour = pal[["neutral_dark"]]) +
  annotate("text", x = min(r2$s0), y = ann_y + 0.13, hjust = 0,
           size = (SIZE - 0.5) / .pt, family = FAMILY, colour = "black",
           label = u(sprintf("Tentativa 2: %d fragmentos", nrow(r2)))) +
  annotate("text", x = mean(c(maps$s0[1], maps$s1[1])), y = 1 - H - 0.12, size = (SIZE - 0.6) / .pt,
           family = FAMILY, colour = "black", label = u("Mapas")) +
  annotate("text", x = cycle_end + 0.08, y = 1.5, hjust = 0, size = (SIZE - 0.6) / .pt,
           family = FAMILY, colour = "black",
           label = u(sprintf("Fim da rajada: %s s", dec(cycle_end, 2)))) +
  theme(legend.position = "none")

# b: detalhe do início, onde ficam as esperas curtas.
zx <- c(0.45, burst_start + 0.55)
tel <- dplyr::filter(seg, evento == "telemetria")
rep <- dplyr::filter(seg, evento == "resposta")
lab <- function(x, y, txt, hjust = 0.5) annotate("text", x = x, y = y, label = u(txt), hjust = hjust,
                                                  size = (SIZE - 0.5) / .pt, family = FAMILY,
                                                  colour = "black")
pb <- base_plot(solid, zx, seq(0.6, 1.8, by = 0.2)) +
  lab(mean(c(tel$s0, tel$s1)), 2 + H + 0.14, sprintf("Telemetria, %s ms", P[["telemetria_ms"]])) +
  lab(mean(c(listen$s0, listen$s1)), 2 + H + 0.14, sprintf("Escuta de até %s ms", P[["escuta_ms"]])) +
  lab(mean(c(rep$s0, rep$s1)), 1 - H - 0.14, sprintf("Resposta, %s ms", P[["resposta_ms"]])) +
  lab(rep$s0 - 0.008, 1 - H - 0.14, sprintf("Volta de %s ms", P[["volta_ms"]]), hjust = 1) +
  lab(burst_start + 0.02, 2 + H + 0.14, sprintf("Fragmentos de %s ms, com %s ms entre eles",
                                                P[["fragmento_ms"]], P[["intervalo_fragmentos_ms"]]), hjust = 0) +
  annotate("segment", x = rep$s1, xend = burst_start, y = 1.52, yend = 1.52, linewidth = 0.3,
           colour = pal[["neutral_dark"]], arrow = arrow(ends = "both", length = unit(0.8, "mm"))) +
  lab(rep$s1 + (burst_start - rep$s1) / 2, 1.42, sprintf("%s ms", P[["inicio_rajada_ms"]])) +
  lab(zx[1] + 0.01, 2 - H - 0.14, "Aquisição", hjust = 0)

fig <- (pa / pb) + patchwork::plot_layout(heights = c(1, 1), guides = "collect") +
  patchwork::plot_annotation(tag_levels = "a") &
  theme(plot.tag = element_text(size = 8, face = "bold", family = FAMILY), legend.position = "bottom")

save_pub(fig, file.path(OUT, "fig13_ciclo_radio"), width_mm = 160, height_mm = 92)
