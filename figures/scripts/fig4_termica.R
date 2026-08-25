# Figura 4 — O ASA protege a eletrônica; a bateria é o elo térmico mais fraco.
#
# Conclusão: por ser mau condutor, o ASA mantém o interior a 44,8 °C com carcaça a
# 80 °C, enquanto o alumínio entregaria 79,0 °C. O limitante não é o invólucro nem o
# ímã, mas o limite de carga da LiPo (45 °C) — e a base metálica que o item 8 pede
# exige quebra térmica para não violá-lo.
#
# Arquétipo: grade quantitativa com painel-herói (a).
# Uso: Rscript figures/scripts/fig4_termica.R

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

ref      <- rd("fig4_referencias.csv")
TI_80    <- ref$t_interna_80_asa[1]
TC_LIM   <- ref$t_carcaca_lim_carga[1]
LIM_CAR  <- ref$lim_carga_c[1]
LIM_DES  <- ref$lim_descarga_c[1]
B_ISO    <- ref$banda_iso_hz[1]

# vocabulário: azul = configuração segura, vermelho = problema, laranja = mitigação
cfg_cols <- c("Base ASA (atual)"        = pal[["signal_blue"]],
              "Base alumínio"           = pal[["accent_red"]],
              "Alumínio + quebra 2 mm"  = pal[["accent_orange"]])
cfg_tipo <- c("Base ASA (atual)"        = "solid",
              "Base alumínio"           = "solid",
              "Alumínio + quebra 2 mm"  = "42")

# ---------------------------------------------------------------------------
# a — painel-herói: temperatura interna vs. carcaça
# ---------------------------------------------------------------------------
tp <- rd("fig4a_temperatura.csv") |>
  mutate(config = factor(config, levels = names(cfg_cols)))

p_a <- ggplot(tp, aes(t_carcaca_c, t_interna_c, colour = config, linetype = config)) +
  annotate("rect", xmin = 30, xmax = 110, ymin = 30, ymax = LIM_CAR,
           fill = pal[["signal_blue"]], alpha = 0.08) +
  geom_hline(yintercept = LIM_CAR, linewidth = 0.35, linetype = "22",
             colour = pal[["neutral_dark"]]) +
  geom_hline(yintercept = LIM_DES, linewidth = 0.3, linetype = "12",
             colour = pal[["neutral_mid"]]) +
  geom_line(linewidth = 0.55) +
  annotate("text", x = 109, y = LIM_CAR - 2.8, hjust = 1, size = 1.75,
           colour = pal[["neutral_dark"]],
           label = "LiPo: limite de carga (45 °C)") +
  annotate("text", x = 109, y = LIM_DES - 2.8, hjust = 1, size = 1.75,
           colour = pal[["neutral_mid"]],
           label = "LiPo: degradação (60 °C)") +
  scale_colour_manual(values = cfg_cols) +
  scale_linetype_manual(values = cfg_tipo) +
  scale_x_continuous(limits = c(30, 110), breaks = seq(30, 110, 20),
                     expand = expansion(mult = c(0.01, 0.02))) +
  scale_y_continuous(limits = c(30, 112), breaks = seq(30, 110, 20),
                     expand = expansion(mult = c(0, 0.02))) +
  labs(title = "Por ser isolante, o ASA protege a eletrônica",
       subtitle = "trocar a base por metal inverte esse comportamento",
       x = "Temperatura da carcaça (°C)", y = "Temperatura interna (°C)") +
  theme(legend.position = "inside", legend.position.inside = c(0.015, 0.985),
        legend.justification = c(0, 1),
        legend.key.height = unit(2.1, "mm"), legend.key.width = unit(3.4, "mm"),
        legend.text = element_text(size = BASE - 1.3),
        legend.background = element_rect(fill = alpha("white", 0.8), colour = NA))

# ---------------------------------------------------------------------------
# b — limites por componente: quem cede primeiro
# ---------------------------------------------------------------------------
lm_ <- rd("fig4b_limites.csv") |>
  mutate(componente = factor(componente, levels = rev(componente[order(ordem)])),
         # codifica pela margem sobre a temperatura interna, não binário
         faixa = cut(margem_c, breaks = c(-Inf, 5, 40, Inf),
                     labels = c("crítica", "estreita", "confortável")))

faixa_cols <- c("crítica"     = pal[["accent_red"]],
                "estreita"    = pal[["accent_orange"]],
                "confortável" = pal[["signal_blue"]])

p_b <- ggplot(lm_, aes(limite_c, componente, fill = faixa)) +
  geom_col(width = 0.62) +
  geom_vline(xintercept = TI_80, linewidth = 0.55, colour = pal[["neutral_dark"]]) +
  geom_text(aes(label = sprintf("%.0f", limite_c)), hjust = -0.3, size = 1.8,
            colour = pal[["neutral_mid"]]) +
  annotate("segment", x = TI_80, xend = TI_80, y = 9.9, yend = 9.4,
           linewidth = 0.3, colour = pal[["neutral_dark"]]) +
  annotate("text", x = TI_80 + 4, y = 10.05, hjust = 0, size = 1.75,
           colour = pal[["neutral_dark"]],
           label = sprintf("interna: %.0f °C (carcaça a 80 °C)", TI_80)) +
  scale_fill_manual(values = faixa_cols, name = NULL) +
  scale_x_continuous(limits = c(0, 205), breaks = seq(0, 200, 50),
                     expand = expansion(mult = c(0, 0.02))) +
  coord_cartesian(ylim = c(0.5, 9.5), clip = "off") +
  labs(title = "A bateria cede muito antes do invólucro",
       subtitle = "cor: margem sobre a temperatura interna",
       x = "Limite térmico (°C)", y = NULL) +
  theme(legend.position = "inside", legend.position.inside = c(0.985, 0.30),
        legend.justification = c(1, 0.5), legend.direction = "vertical",
        legend.key.height = unit(1.9, "mm"), legend.key.width = unit(2.4, "mm"),
        legend.text = element_text(size = BASE - 1.4),
        legend.spacing.y = unit(0.2, "mm"),
        plot.margin = margin(6, 2, 2, 2))

# ---------------------------------------------------------------------------
# c — o trade-off entre os itens 4 e 8
# ---------------------------------------------------------------------------
tw <- rd("fig4c_tradeoff.csv")
tw$cor <- unname(cfg_cols)

p_c <- ggplot(tw, aes(f_n_hz, t_interna_c)) +
  annotate("rect", xmin = B_ISO, xmax = 1450, ymin = 30, ymax = LIM_CAR,
           fill = pal[["signal_teal"]], alpha = 0.16) +
  annotate("text", x = 1420, y = 34, hjust = 1, size = 1.75, fontface = "bold",
           colour = "#1F7A6C", label = "alvo: rígido e frio") +
  geom_hline(yintercept = LIM_CAR, linewidth = 0.35, linetype = "22",
             colour = pal[["neutral_dark"]]) +
  geom_vline(xintercept = B_ISO, linewidth = 0.35, linetype = "22",
             colour = pal[["neutral_dark"]]) +
  geom_point(aes(colour = config), size = 1.9, show.legend = FALSE) +
  geom_text(aes(label = config, colour = config), size = 1.75,
            lineheight = 0.92, hjust = 0, nudge_x = 34, nudge_y = 5.5,
            show.legend = FALSE) +
  scale_colour_manual(values = setNames(tw$cor, tw$config)) +
  scale_x_continuous(limits = c(450, 1450), breaks = seq(600, 1400, 200)) +
  scale_y_continuous(limits = c(30, 92), breaks = seq(30, 90, 20)) +
  labs(title = "Nenhuma configuração atende aos dois requisitos",
       subtitle = "vibração pede rigidez; térmica pede isolamento",
       x = "Frequência de montagem (Hz)", y = "Temperatura interna (°C)")

# ---------------------------------------------------------------------------
# d — a quebra térmica: pouca espessura já resolve
# ---------------------------------------------------------------------------
iso <- rd("fig4d_isolador.csv")

p_d <- ggplot(iso, aes(isolador_mm, t_interna_c)) +
  annotate("rect", xmin = -0.2, xmax = 5.2, ymin = 30, ymax = LIM_CAR,
           fill = pal[["signal_blue"]], alpha = 0.08) +
  geom_hline(yintercept = LIM_CAR, linewidth = 0.3, linetype = "22",
             colour = pal[["neutral_dark"]]) +
  geom_line(linewidth = 0.5, colour = pal[["accent_orange"]]) +
  geom_point(size = 0.9, colour = pal[["accent_orange"]]) +
  annotate("text", x = 5.1, y = LIM_CAR - 3.2, hjust = 1, size = 1.7,
           colour = pal[["neutral_dark"]], label = "limite de carga") +
  scale_x_continuous(limits = c(-0.2, 5.2), breaks = 0:5,
                     expand = expansion(mult = 0)) +
  scale_y_continuous(limits = c(38, 84), breaks = seq(40, 80, 20)) +
  labs(title = "0,5 mm de isolador recupera a maior parte",
       subtitle = "base de alumínio, carcaça a 80 °C",
       x = "Espessura da quebra térmica (mm)", y = "Temperatura\ninterna (°C)")

# ---------------------------------------------------------------------------
# montagem: herói (a) + limites (b) em cima; trade-off (c) e mitigação (d) embaixo
# ---------------------------------------------------------------------------
fig4 <- (p_a | p_b) / (p_c | p_d) +
  plot_layout(heights = c(1.1, 1)) +
  plot_annotation(tag_levels = "a") &
  tag_theme

save_pub(fig4, file.path(out_dir, "fig4_termica"),
         width_mm = 183, height_mm = 115)
