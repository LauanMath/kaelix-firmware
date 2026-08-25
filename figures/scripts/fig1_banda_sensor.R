# Figura 1 — O limite de banda do MPU6050 descarta a evidência de defeito de rolamento.
#
# Conclusão: a banda de 500 Hz preserva a taxa de repetição do defeito (BPFO, 105 Hz)
# mas descarta a ressonância de 3,5 kHz que a carrega, reduzindo o contraste
# diagnóstico de 413x para 20x e anulando curtose e fator de crista.
#
# Arquétipo: grade quantitativa com painel-herói (a).
# Uso: Rscript figures/scripts/fig1_banda_sensor.R

# localiza o diretório do script sob Rscript ou source()
script_dir <- function() {
  a <- commandArgs(trailingOnly = FALSE)
  m <- grep("^--file=", a, value = TRUE)
  if (length(m)) return(dirname(normalizePath(sub("^--file=", "", m[1]))))
  "figures/scripts"
}
here <- script_dir()
source(file.path(here, "theme_kaelix.R"))

DATA <- file.path(here, "..", "data")
OUT  <- file.path(here, "..", "output")
dir.create(OUT, showWarnings = FALSE, recursive = TRUE)

rd <- function(f) readr::read_csv(file.path(DATA, f), show_col_types = FALSE)

BPFO <- 104.56
NYQ  <- 500

# ---------------------------------------------------------------------------
# a — painel-herói: onde a evidência vive no espectro
# ---------------------------------------------------------------------------
esp <- rd("fig1a_espectro.csv") |>
  mutate(condicao = factor(condicao, levels = c("sadio", "defeito")))

p_a <- ggplot(esp, aes(freq_hz, psd, colour = condicao)) +
  annotate("rect", xmin = 0, xmax = NYQ, ymin = 1e-11, ymax = 1e-1,
           fill = pal[["accent_orange"]], alpha = 0.13) +
  geom_line(linewidth = 0.3) +
  annotate("segment", x = 3500, xend = 3500, y = 2.5e-3, yend = 6e-4,
           linewidth = 0.28, colour = pal[["neutral_dark"]],
           arrow = arrow(length = unit(1, "mm"), type = "closed")) +
  annotate("text", x = 3620, y = 9e-3, size = 1.75, hjust = 0.42,
           colour = pal[["neutral_dark"]], lineheight = 0.95,
           label = "ressonância excitada\npelos impactos (3,5 kHz)") +
  annotate("text", x = 590, y = 1.2e-8, hjust = 0, size = 1.75,
           colour = "#8a5a00", lineheight = 0.95,
           label = "banda visível\nao MPU6050\n(≤ 500 Hz)") +
  scale_colour_manual(values = cond_cols) +
  scale_x_continuous(limits = c(0, 8000), breaks = seq(0, 8000, 2000),
                     labels = label_number(scale = 1e-3, suffix = " kHz"),
                     expand = expansion(mult = c(0.01, 0.02))) +
  scale_y_log10(limits = c(1e-11, 1e-1),
                breaks = 10^seq(-10, -2, 2), labels = label_log()) +
  labs(title = "A ressonância que carrega o defeito cai fora da banda do sensor",
       x = "Frequência", y = expression("PSD ("*m^2*s^-4*Hz^-1*")")) +
  theme(legend.position = "inside", legend.position.inside = c(0.99, 0.98),
        legend.justification = c(1, 1),
        legend.key.height = unit(2.2, "mm"),
        axis.title.x = element_text(margin = margin(t = 1)))

# ---------------------------------------------------------------------------
# b — contraste diagnóstico em BPFO por método
# ---------------------------------------------------------------------------
ctr <- rd("fig1b_contraste.csv") |>
  mutate(metodo_curto = factor(metodo_curto,
                               levels = c("envelope 20 kHz", "espectro 1 kHz")),
         tipo = ifelse(metodo_curto == "envelope 20 kHz", "correto", "incorreto"))

p_b <- ggplot(ctr, aes(metodo_curto, contraste, fill = tipo)) +
  geom_col(width = 0.5) +
  geom_text(aes(label = sprintf("%.0f×", contraste)),
            vjust = -0.5, size = 2.1, fontface = "bold") +
  annotate("text", x = 1.5, y = 345, size = 1.75, colour = pal[["neutral_mid"]],
           label = "queda de 21×") +
  scale_fill_manual(values = metodo_cols, guide = "none") +
  scale_x_discrete(labels = c("Envelope na\nressonância\n20 kHz",
                              "Espectro\ndireto\nMPU6050")) +
  scale_y_continuous(limits = c(0, 500), breaks = seq(0, 400, 200),
                     expand = expansion(mult = c(0, 0.05))) +
  labs(title = "Contraste em BPFO", x = NULL, y = "Razão defeito / sadio")

# ---------------------------------------------------------------------------
# c — features de impacto: separação entre classes por cadeia
# ---------------------------------------------------------------------------
feat <- rd("fig1c_features.csv") |>
  mutate(razao = defeito / sadio,
         cadeia = factor(cadeia, levels = c("Referência 20 kHz",
                                            "MPU6050 c/ antialias",
                                            "MPU6050 s/ antialias"),
                         labels = c("20 kHz", "MPU c/ AA", "MPU s/ AA")),
         feature = factor(feature, levels = c("curtose", "fator de crista",
                                              "pico", "pico-a-pico")))

cadeia_cols <- c("20 kHz"    = pal[["signal_blue"]],
                 "MPU c/ AA" = pal[["accent_red"]],
                 "MPU s/ AA" = pal[["accent_orange"]])

p_c <- ggplot(feat, aes(feature, razao, fill = cadeia)) +
  geom_hline(yintercept = 1, linewidth = 0.35, linetype = "22",
             colour = pal[["neutral_dark"]]) +
  geom_col(position = position_dodge(width = 0.75), width = 0.68) +
  annotate("text", x = 0.56, y = 1.16, hjust = 0, size = 1.7,
           colour = pal[["neutral_dark"]], label = "1,0 = não separa") +
  scale_fill_manual(values = cadeia_cols) +
  scale_y_continuous(limits = c(0, 3.7), breaks = 0:3,
                     expand = expansion(mult = c(0, 0.02))) +
  labs(title = "Nenhuma feature de impacto sobrevive à banda",
       subtitle = "inclui pico e pico-a-pico, que a literatura aponta como mais sensíveis",
       x = NULL, y = "Razão defeito / sadio") +
  theme(legend.position = "inside", legend.position.inside = c(0.99, 0.97),
        legend.justification = c(1, 1), legend.direction = "horizontal",
        legend.key.height = unit(2, "mm"), legend.key.width = unit(2.4, "mm"),
        legend.text = element_text(size = BASE - 1.3))

# ---------------------------------------------------------------------------
# d — dobramento por aliasing
# ---------------------------------------------------------------------------
ali <- rd("fig1d_aliasing.csv")

p_d <- ggplot(ali, aes(f_real_hz, f_aparente_hz)) +
  annotate("rect", xmin = 2830, xmax = 5270, ymin = 0, ymax = NYQ,
           fill = pal[["accent_orange"]], alpha = 0.10) +
  geom_segment(aes(xend = f_real_hz, yend = 0),
               linewidth = 0.26, colour = pal[["neutral_light"]]) +
  geom_point(size = 0.95, colour = pal[["accent_red"]]) +
  geom_text(aes(label = sprintf("%.0f", f_aparente_hz)),
            vjust = -0.9, size = 1.75, colour = pal[["accent_red"]]) +
  scale_x_continuous(limits = c(2830, 5270), breaks = ali$f_real_hz,
                     labels = label_number(scale = 1e-3, accuracy = 0.1)) +
  scale_y_continuous(limits = c(0, 640), breaks = seq(0, 500, 250)) +
  annotate("text", x = 2880, y = 560, hjust = 0, size = 1.7,
           colour = "#8a5a00", label = "banda do MPU6050") +
  labs(title = "Sem antialiasing, a energia reaparece em frequência falsa",
       x = "Frequência real da ressonância (kHz)",
       y = "Frequência\naparente (Hz)")

# ---------------------------------------------------------------------------
# montagem: herói à esquerda (a), evidência de apoio à direita (b, c),
# consequência prática embaixo (d) — hierarquia decrescente de importância
# ---------------------------------------------------------------------------
fig1 <- (p_a | (p_b / p_c + plot_layout(heights = c(1, 1.15)))) /
        p_d +
  plot_layout(heights = c(2.7, 1), widths = c(1.3, 1)) +
  plot_annotation(tag_levels = "a") &
  tag_theme

save_pub(fig1, file.path(OUT, "fig1_banda_sensor"),
         width_mm = 183, height_mm = 110)
