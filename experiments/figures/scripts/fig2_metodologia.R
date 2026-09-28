# Figura 2 — Três escolhas metodológicas alteram os resultados mais do que o
# efeito que se pretende medir.
#
# Conclusão: integração no domínio errado, split que vaza assinatura de ensaio e
# limiar herdado do default produzem erros de 73-716%, +36 pontos de acurácia
# aparente e 42% de falso alarme, respectivamente.
#
# Arquétipo: grade quantitativa, três blocos de evidência independentes.
# Uso: Rscript experiments/figures/scripts/fig2_metodologia.R

script_dir <- function() {
  a <- commandArgs(trailingOnly = FALSE)
  m <- grep("^--file=", a, value = TRUE)
  if (length(m)) return(dirname(normalizePath(sub("^--file=", "", m[1]))))
  "experiments/figures/scripts"
}
here <- script_dir()
source(file.path(here, "theme_kaelix.R"))

data_dir <- file.path(here, "..", "data")
out_dir  <- file.path(here, "..", "output")
dir.create(out_dir, showWarnings = FALSE, recursive = TRUE)

rd <- function(f) readr::read_csv(file.path(data_dir, f), show_col_types = FALSE)

v_exato <- rd("fig2_referencia.csv")$valor_exato_mm_s[1]

# ---------------------------------------------------------------------------
# a — erro de cada método de integração contra o valor analítico
# ---------------------------------------------------------------------------
intg <- rd("fig2a_integracao.csv") |>
  mutate(metodo = factor(metodo, levels = rev(metodo[order(ordem)])),
         tipo = ifelse(correto, "correto", "incorreto"))

p_a <- ggplot(intg, aes(rms_mm_s, metodo, fill = tipo)) +
  geom_vline(xintercept = v_exato, linewidth = 0.4,
             colour = pal[["neutral_dark"]], linetype = "22") +
  geom_col(width = 0.6) +
  geom_text(aes(label = ifelse(abs(erro_pct) < 1, "exato",
                               sprintf("%+.0f%%", erro_pct))),
            hjust = -0.15, size = 1.9,
            colour = ifelse(intg$correto, pal[["signal_blue"]], pal[["accent_red"]])) +
  annotate("text", x = v_exato, y = 5.72, size = 1.75, hjust = -0.08,
           colour = pal[["neutral_dark"]],
           label = sprintf("valor analítico exato: %.2f mm/s", v_exato)) +
  scale_fill_manual(values = metodo_cols, guide = "none") +
  scale_x_continuous(limits = c(0, 72), breaks = seq(0, 60, 20),
                     expand = expansion(mult = c(0, 0.02))) +
  coord_cartesian(clip = "off") +
  labs(title = "Só a integração na frequência recupera a velocidade correta",
       subtitle = "senoide de 3,0 m/s² a 50 Hz, cuja integral é conhecida analiticamente",
       x = "Velocidade RMS medida (mm/s)", y = NULL) +
  theme(axis.text.y = element_text(lineheight = 0.85),
        plot.margin = margin(2, 8, 2, 2))

# ---------------------------------------------------------------------------
# b — a deriva que produz o erro de 716%
# ---------------------------------------------------------------------------
der <- rd("fig2b_deriva.csv") |>
  mutate(metodo = factor(metodo, levels = c("no tempo, sem passa-alta", "na frequência")))

p_b <- ggplot(der, aes(tempo_s, velocidade_mm_s, colour = metodo)) +
  geom_hline(yintercept = v_exato, linewidth = 0.35,
             colour = pal[["neutral_dark"]], linetype = "22") +
  geom_line(linewidth = 0.22) +
  scale_colour_manual(values = c("no tempo, sem passa-alta" = pal[["accent_red"]],
                                 "na frequência" = pal[["signal_blue"]])) +
  scale_x_continuous(breaks = seq(0, 4, 1), expand = expansion(mult = 0.01)) +
  scale_y_continuous(limits = c(-25, 105), breaks = seq(0, 100, 50)) +
  labs(title = "Um bias de 0,02 m/s² faz a integração no tempo derivar",
       subtitle = "offset dentro da especificação do MPU6050",
       x = "Tempo (s)", y = "Velocidade (mm/s)") +
  theme(legend.position = "inside", legend.position.inside = c(0.02, 0.97),
        legend.justification = c(0, 1), legend.key.height = unit(2.2, "mm"))

# ---------------------------------------------------------------------------
# c — vazamento de dados no split
# ---------------------------------------------------------------------------
spl   <- rd("fig2c_split.csv")
folds <- rd("fig2c_folds.csv")
base  <- rd("fig2c_baseline.csv")$baseline[1]

spl <- spl |> mutate(estrategia = factor(estrategia, levels = estrategia[order(ordem)]),
                     tipo = ifelse(tipo == "correto", "correto", "incorreto"))

p_c <- ggplot(spl, aes(estrategia, media, fill = tipo)) +
  geom_hline(yintercept = base, linewidth = 0.35,
             colour = pal[["neutral_mid"]], linetype = "22") +
  geom_col(width = 0.5) +
  geom_errorbar(aes(ymin = media - desvio, ymax = pmin(media + desvio, 1)),
                width = 0.13, linewidth = 0.3) +
  geom_point(data = folds, aes(x = 2, y = acuracia), inherit.aes = FALSE,
             position = position_jitter(width = 0.1, height = 0, seed = 1),
             size = 0.75, colour = pal[["neutral_dark"]], alpha = 0.85) +
  geom_text(aes(label = sprintf("%.3f", media), y = media + desvio + 0.05),
            size = 2.1, fontface = "bold") +
  annotate("text", x = 2.46, y = base + 0.04, hjust = 1, size = 1.7,
           colour = pal[["neutral_mid"]], label = "chute") +
  scale_fill_manual(values = metodo_cols, guide = "none") +
  scale_y_continuous(limits = c(0, 1.14), breaks = seq(0, 1, 0.25),
                     expand = expansion(mult = c(0, 0.02))) +
  labs(title = "Vazamento no split",
       subtitle = "pontos: folds do split por ensaio",
       x = NULL, y = "Acurácia") +
  theme(axis.text.x = element_text(lineheight = 0.85),
        axis.title.y = element_text(margin = margin(r = 0)),
        plot.margin = margin(2, 2, 2, 0))

# ---------------------------------------------------------------------------
# d — contamination controla o falso alarme, não a qualidade
# ---------------------------------------------------------------------------
cont <- rd("fig2d_contamination.csv") |>
  mutate(contamination = factor(contamination,
                                levels = c("0.5", "0.2", "0.1", "0.01", "auto")),
         tipo = ifelse(is_default, "incorreto", "correto"))

p_d <- ggplot(cont, aes(contamination, falso_alarme, fill = tipo)) +
  geom_col(width = 0.58) +
  geom_text(aes(label = percent(falso_alarme, accuracy = 0.1)),
            vjust = -0.45, size = 1.85) +
  annotate("text", x = 5, y = 0.545, size = 1.7, colour = pal[["accent_red"]],
           label = "default") +
  scale_fill_manual(values = metodo_cols, guide = "none") +
  scale_y_continuous(limits = c(0, 0.62), labels = percent_format(accuracy = 1),
                     breaks = seq(0, 0.5, 0.25),
                     expand = expansion(mult = c(0, 0.02))) +
  labs(title = "O default marca 42% como anomalia",
       subtitle = "detecção foi 100% em todos os casos",
       x = "contamination", y = "Falso alarme")

# ---------------------------------------------------------------------------
# e — a banda limita o detector onde importa
# ---------------------------------------------------------------------------
roc <- rd("fig2e_roc.csv")

p_e <- ggplot(roc, aes(fpr, tpr, colour = banda, linetype = banda)) +
  annotate("rect", xmin = 0, xmax = 0.05, ymin = 0, ymax = 1,
           fill = pal[["orange_wash"]], alpha = 0.13) +
  geom_abline(linewidth = 0.3, linetype = "22", colour = pal[["neutral_mid"]]) +
  geom_line(linewidth = 0.45) +
  annotate("text", x = 0.10, y = 0.42, hjust = 0, size = 1.7,
           colour = "#8a5a00", lineheight = 0.95,
           label = "operação realista\n(falso alarme ≤ 5%)") +
  scale_colour_manual(values = setNames(
    c(pal[["signal_blue"]], pal[["accent_red"]]),
    c(grep("20 kHz", unique(roc$banda), value = TRUE),
      grep("MPU", unique(roc$banda), value = TRUE)))) +
  scale_linetype_manual(values = setNames(
    c("solid", "31"),
    c(grep("20 kHz", unique(roc$banda), value = TRUE),
      grep("MPU", unique(roc$banda), value = TRUE)))) +
  scale_x_continuous(limits = c(0, 1), breaks = seq(0, 1, 0.5)) +
  scale_y_continuous(limits = c(0, 1), breaks = seq(0, 1, 0.5)) +
  coord_fixed() +
  labs(title = "A banda decide o defeito sutil",
       subtitle = "pAUC revela perda 4x maior que a AUC",
       x = "Falso alarme", y = "Detecção") +
  theme(legend.position = "inside", legend.position.inside = c(0.97, 0.13),
        legend.justification = c(1, 0.5), legend.direction = "vertical",
        legend.key.height = unit(1.9, "mm"), legend.key.width = unit(2.8, "mm"),
        legend.text = element_text(size = BASE - 1.5),
        legend.spacing.y = unit(0.2, "mm"))

# ---------------------------------------------------------------------------
# montagem: integração (a, b) | validação (c) | modelo (d, e)
# ---------------------------------------------------------------------------
fig2 <- (p_a | p_b) / (p_c | p_d | p_e) +
  plot_layout(heights = c(1, 1.05), widths = c(1)) +
  plot_annotation(tag_levels = "a") &
  tag_theme

save_pub(fig2, file.path(out_dir, "fig2_metodologia"),
         width_mm = 183, height_mm = 112)
