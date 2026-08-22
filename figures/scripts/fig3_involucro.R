# Figura 3 — O invólucro em ASA filtra o sinal antes que ele chegue ao sensor.
#
# Conclusão: o caminho elástico motor→base→spigot→corpo→sensor coloca a frequência
# de montagem em 557 Hz, dentro da banda de medição, com erro de amplitude acima de
# 10% a partir de 168 Hz — enquanto fixação magnética e modos de placa não são problema.
#
# Arquétipo: grade quantitativa com painel-herói (a).
# Uso: Rscript figures/scripts/fig3_involucro.R

script_dir <- function() {
  a <- commandArgs(trailingOnly = FALSE)
  m <- grep("^--file=", a, value = TRUE)
  if (length(m)) return(dirname(normalizePath(sub("^--file=", "", m[1]))))
  "figures/scripts"
}
here <- script_dir()
source(file.path(here, "theme_kaelix.R"))

data_dir <- file.path(here, "..", "data")
out_dir  <- file.path(here, "..", "output")
dir.create(out_dir, showWarnings = FALSE, recursive = TRUE)

rd <- function(f) readr::read_csv(file.path(data_dir, f), show_col_types = FALSE)

ref      <- rd("fig3_referencias.csv")
F_N      <- ref$f_n_asa_hz[1]
F_ERR10  <- ref$f_erro10_hz[1]
B_SENSOR <- ref$banda_sensor_hz[1]
B_ISO    <- ref$banda_iso_hz[1]

# ---------------------------------------------------------------------------
# a — painel-herói: transmissibilidade por material
# ---------------------------------------------------------------------------
tr <- rd("fig3d_transmissibilidade.csv")
ordem_mat <- tr |> dplyr::distinct(material, f_n_hz) |> dplyr::arrange(f_n_hz) |>
  mutate(rotulo = sprintf("%s  (%.0f Hz)", material, f_n_hz))
tr <- tr |> dplyr::left_join(dplyr::select(ordem_mat, material, rotulo2 = rotulo),
                             by = "material") |>
  mutate(rotulo = factor(rotulo2, levels = ordem_mat$rotulo))

cores_mat <- setNames(
  c(pal[["accent_red"]], pal[["signal_blue"]], pal[["neutral_dark"]]),
  ordem_mat$rotulo
)
tipos_mat <- setNames(c("solid", "solid", "42"), ordem_mat$rotulo)

p_a <- ggplot(tr, aes(freq_hz, T, colour = rotulo, linetype = rotulo)) +
  annotate("rect", xmin = 10, xmax = B_SENSOR, ymin = 0.04, ymax = 40,
           fill = pal[["signal_blue"]], alpha = 0.09) +
  annotate("rect", xmin = B_SENSOR, xmax = B_ISO, ymin = 0.04, ymax = 40,
           fill = pal[["accent_orange"]], alpha = 0.13) +
  geom_hline(yintercept = 1, linewidth = 0.35, linetype = "22",
             colour = pal[["neutral_mid"]]) +
  geom_line(linewidth = 0.5) +
  annotate("text", x = 70, y = 0.055, size = 1.75, colour = pal[["signal_blue"]],
           label = "banda do MPU6050") +
  annotate("text", x = 707, y = 0.055, size = 1.75, colour = "#8a5a00",
           label = "resto da\nbanda ISO", lineheight = 0.95) +
  annotate("segment", x = F_N, xend = F_N, y = 19, yend = 12.5,
           linewidth = 0.28, colour = pal[["accent_red"]],
           arrow = arrow(length = unit(1, "mm"), type = "closed")) +
  annotate("text", x = F_N, y = 27.5, size = 1.8, colour = pal[["accent_red"]],
           label = sprintf("ressonância de\nmontagem: %.0f Hz", F_N),
           lineheight = 0.95) +
  scale_colour_manual(values = cores_mat) +
  scale_linetype_manual(values = tipos_mat) +
  scale_x_log10(breaks = c(10, 30, 100, 300, 1000, 3000),
                labels = c("10", "30", "100", "300", "1000", "3000")) +
  scale_y_log10(limits = c(0.04, 40), breaks = c(0.1, 1, 10),
                labels = c("0,1", "1", "10")) +
  annotation_logticks(sides = "bl", size = 0.2,
                      short = unit(0.4, "mm"), mid = unit(0.7, "mm"),
                      long = unit(1.1, "mm")) +
  labs(title = "O que o sensor lê dividido pelo que o motor produz",
       subtitle = "mesma geometria, só o material muda",
       x = "Frequência (Hz)", y = "Transmissibilidade") +
  theme(legend.position = "inside", legend.position.inside = c(0.015, 0.985),
        legend.justification = c(0, 1),
        legend.key.height = unit(2.1, "mm"), legend.key.width = unit(3.4, "mm"),
        legend.text = element_text(size = BASE - 1.3),
        legend.background = element_rect(fill = alpha("white", 0.75), colour = NA))

# ---------------------------------------------------------------------------
# b — erro de amplitude dentro da banda do sensor
# ---------------------------------------------------------------------------
er <- rd("fig3e_erro.csv")

p_b <- ggplot(er, aes(freq_hz, erro_pct)) +
  geom_hline(yintercept = 10, linewidth = 0.3, linetype = "22",
             colour = pal[["neutral_mid"]]) +
  geom_area(fill = pal[["accent_red"]], alpha = 0.20) +
  geom_line(linewidth = 0.5, colour = pal[["accent_red"]]) +
  annotate("segment", x = F_ERR10, xend = F_ERR10, y = 0, yend = 10,
           linewidth = 0.3, linetype = "22", colour = pal[["neutral_dark"]]) +
  annotate("text", x = F_ERR10 + 18, y = 68, hjust = 0, size = 1.8,
           colour = pal[["neutral_dark"]], lineheight = 0.95,
           label = sprintf("erro passa de 10%%\na partir de %.0f Hz", F_ERR10)) +
  scale_x_continuous(limits = c(10, 500), breaks = seq(0, 500, 100),
                     expand = expansion(mult = c(0.01, 0.02))) +
  coord_cartesian(ylim = c(0, 130)) +
  scale_y_continuous(breaks = seq(0, 120, 40),
                     expand = expansion(mult = c(0, 0.02))) +
  labs(title = "Erro de amplitude na banda do sensor",
       subtitle = "consequência direta da ressonância em a",
       x = "Frequência (Hz)", y = "Erro (%)")

# ---------------------------------------------------------------------------
# c — de onde vem a flexibilidade
# ---------------------------------------------------------------------------
rg <- rd("fig3c_rigidez.csv") |>
  mutate(elo = factor(elo, levels = rev(elo[order(ordem)])),
         tipo = ifelse(flex_frac > 0.1, "incorreto", "correto"))

p_c <- ggplot(rg, aes(flex_frac, elo, fill = tipo)) +
  geom_col(width = 0.5) +
  geom_text(aes(label = scales::percent(flex_frac, accuracy = 0.1)),
            hjust = -0.12, size = 1.95) +
  scale_fill_manual(values = metodo_cols, guide = "none") +
  scale_x_continuous(limits = c(0, 0.66), labels = scales::percent_format(accuracy = 1),
                     breaks = seq(0, 0.6, 0.2),
                     expand = expansion(mult = c(0, 0.02))) +
  labs(title = "Base e corpo dividem quase toda a flexibilidade",
       subtitle = "o spigot é irrelevante: rigidez em série",
       x = "Fração da flexibilidade total", y = NULL) +
  theme(axis.text.y = element_text(lineheight = 0.85))

# ---------------------------------------------------------------------------
# d — hipóteses descartadas: fixação magnética
# ---------------------------------------------------------------------------
fx <- rd("fig3a_fixacao.csv")
mg <- rd("fig3a_margem.csv")

p_d <- ggplot(fx, aes(diametro_carcaca_mm, forca_N)) +
  geom_hline(yintercept = mg$forca_inercial_N[1], linewidth = 0.35,
             linetype = "22", colour = pal[["accent_red"]]) +
  geom_line(linewidth = 0.5, colour = pal[["signal_blue"]]) +
  geom_point(size = 0.9, colour = pal[["signal_blue"]]) +
  annotate("text", x = 500, y = mg$forca_inercial_N[1] + 4.5, hjust = 1,
           size = 1.75, colour = pal[["accent_red"]],
           label = sprintf("força inercial a %.0f g", mg$aceleracao_g[1])) +
  scale_x_continuous(breaks = c(100, 200, 300, 400, 500)) +
  scale_y_continuous(limits = c(0, 56), breaks = seq(0, 50, 25),
                     expand = expansion(mult = c(0, 0.03))) +
  labs(title = "Fixação: margem preservada",
       subtitle = "hipótese descartada", x = "Ø da carcaça (mm)",
       y = "Força de\nretenção (N)")

# ---------------------------------------------------------------------------
# e — hipóteses descartadas: modos das placas
# ---------------------------------------------------------------------------
md_ <- rd("fig3b_modos.csv") |>
  mutate(painel = factor(painel, levels = rev(c("Parede lateral", "Tampa", "Fundo"))))

p_e <- ggplot(md_, aes(f_apoiada_hz, painel)) +
  annotate("rect", xmin = 0, xmax = B_ISO, ymin = 0.4, ymax = 3.6,
           fill = pal[["accent_orange"]], alpha = 0.13) +
  geom_segment(aes(xend = f_engastada_hz, yend = painel),
               linewidth = 1.5, colour = pal[["signal_blue"]], alpha = 0.35) +
  geom_point(size = 1.1, colour = pal[["signal_blue"]]) +
  geom_point(aes(x = f_engastada_hz), size = 1.1, colour = pal[["signal_blue"]]) +
  annotate("text", x = 1150, y = 0.66, hjust = 0, size = 1.7, colour = "#8a5a00",
           label = "banda ISO") +
  scale_x_continuous(limits = c(0, 8200), breaks = seq(0, 8000, 2000),
                     labels = scales::label_number(scale = 1e-3, suffix = "k"),
                     expand = expansion(mult = c(0, 0.02))) +
  labs(title = "Painéis: modos acima da banda",
       subtitle = "hipótese descartada; barra = apoiada→engastada",
       x = "Frequência do modo fundamental (Hz)", y = NULL)

# ---------------------------------------------------------------------------
# montagem: herói (a) + consequência (b) em cima;
# diagnóstico (c) e hipóteses descartadas (d, e) embaixo
# ---------------------------------------------------------------------------
fig3 <- (p_a | p_b) / (p_c | (p_d / p_e)) +
  plot_layout(heights = c(1.25, 1), widths = c(1)) +
  plot_annotation(tag_levels = "a") &
  tag_theme

save_pub(fig3, file.path(out_dir, "fig3_involucro"),
         width_mm = 183, height_mm = 125)
