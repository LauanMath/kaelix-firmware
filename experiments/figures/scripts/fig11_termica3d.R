# Figura 11 — O ASA não protege: ele desconecta. E o modelo concentrado errava.
#
# Conclusão: com a carcaça a 90 °C, a cavidade fica em 34–35 °C, porque a
# entrada de calor pelos ímãs em ASA vale ~118 K/W contra ~5 K/W de troca com
# o ar. Quase todo o salto de 60 K é gasto nos primeiros milímetros da base. O
# modelo concentrado do notebook dava 47,5 °C, mas por não ter convergido: o
# mesmo balanço, resolvido até a raiz, dá 33,5 °C.
#
# Arquétipo: grade quantitativa com painel-herói (a).
# Uso: Rscript experiments/figures/scripts/fig11_termica3d.R
#      (dados: uv run --with gmsh --with numpy python hardware/termica.py)

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

perf <- rd("fig11_perfil.csv")
tran <- rd("fig11_transiente.csv")
corr <- rd("fig11_correcao.csv")
ref  <- rd("fig11_referencias.csv")

T_MOT <- ref$t_motor[1];  T_AMB <- ref$t_amb[1]
LIPO  <- ref$lipo_carga[1]
ver_cols <- c("v1" = pal[["signal_blue"]], "v2" = pal[["accent_red"]])

# --- (a) onde o salto de 60 K é gasto ---------------------------------------
pa <- ggplot(perf, aes(t_media, z_mm, colour = versao)) +
  annotate("rect", xmin = T_AMB, xmax = LIPO, ymin = -Inf, ymax = Inf,
           fill = pal[["signal_teal"]], alpha = 0.10) +
  geom_vline(xintercept = T_AMB, colour = pal[["neutral_mid"]],
             linetype = "22", linewidth = 0.35) +
  geom_vline(xintercept = T_MOT, colour = pal[["neutral_dark"]],
             linetype = "22", linewidth = 0.35) +
  geom_ribbon(aes(xmin = t_min, xmax = t_max, y = z_mm, fill = versao),
              inherit.aes = FALSE, alpha = 0.20, colour = NA) +
  geom_path(linewidth = 0.6) +
  annotate("text", x = T_MOT - 1.5, y = 62, label = "carcaça do motor",
           angle = 90, hjust = 1, size = (BASE - 1.4) / .pt,
           colour = pal[["neutral_dark"]]) +
  annotate("text", x = T_AMB + 1.5, y = 62, label = "ambiente",
           angle = 90, hjust = 1, size = (BASE - 1.4) / .pt,
           colour = pal[["neutral_mid"]]) +
  annotate("text", x = 60, y = 40, hjust = 0, size = (BASE - 1.3) / .pt,
           label = "os primeiros 4 mm de ASA\nengolem 33 dos 60 K") +
  annotate("segment", x = 66, y = 37, xend = 61, yend = 6,
           linewidth = 0.22, colour = pal[["neutral_dark"]]) +
  scale_colour_manual(values = ver_cols) +
  scale_fill_manual(values = ver_cols) +
  coord_cartesian(xlim = c(27, 93), ylim = c(0, 76), expand = FALSE) +
  labs(title = "a   Onde os 60 K se perdem",
       subtitle = "faixa = espalhamento em cada cota; área clara = abaixo dos 45 °C da LiPo",
       x = "temperatura (°C)", y = "altura a partir dos ímãs (mm)") +
  theme(legend.position = c(0.90, 0.55))

# --- (b) a dinâmica ---------------------------------------------------------
marcas <- data.frame(x = c(ref$tau_min[1], ref$t90_min[1]),
                     rot = c(sprintf("τ = %.0f min", ref$tau_min[1]),
                             sprintf("90%% em %.0f min", ref$t90_min[1])))
pb <- ggplot(tran, aes(t_s / 60, t_parede, colour = versao)) +
  geom_vline(data = marcas, aes(xintercept = x), inherit.aes = FALSE,
             colour = pal[["neutral_mid"]], linetype = "22", linewidth = 0.3) +
  geom_text(data = marcas, aes(x, 30.4, label = rot), inherit.aes = FALSE,
            hjust = -0.08, size = (BASE - 1.4) / .pt,
            colour = pal[["neutral_mid"]]) +
  geom_line(linewidth = 0.6) +
  scale_colour_manual(values = ver_cols) +
  coord_cartesian(xlim = c(0, 240), ylim = c(29.8, 36.5), expand = FALSE) +
  labs(title = "b   Meia hora de atraso, e para por aí",
       subtitle = "degrau da carcaça de 30 para 90 °C em t = 0",
       x = "tempo (min)", y = "parede da cavidade (°C)") +
  theme(legend.position = "none")

# --- (c) o modelo concentrado não tinha convergido --------------------------
pontos <- data.frame(t_carcaca = T_MOT,
                     t_interna = c(ref$t_int_v1[1], ref$t_int_v2[1]),
                     versao = c("v1", "v2"))
corr$modelo <- factor(corr$modelo,
                      levels = c("concentrado, 500 iterações",
                                 "concentrado, convergido"))
pc <- ggplot(corr, aes(t_carcaca, t_interna)) +
  geom_hline(yintercept = LIPO, colour = pal[["accent_red"]],
             linetype = "22", linewidth = 0.35) +
  annotate("text", x = 41, y = LIPO + 1.6, hjust = 0,
           label = "LiPo: limite de carga (45 °C)",
           size = (BASE - 1.4) / .pt, colour = pal[["accent_red"]]) +
  geom_line(aes(linetype = modelo, colour = modelo), linewidth = 0.55) +
  geom_point(data = pontos, aes(t_carcaca, t_interna, fill = versao),
             shape = 21, size = 1.8, colour = "white", stroke = 0.4,
             inherit.aes = FALSE) +
  scale_colour_manual(values = c("concentrado, 500 iterações" = pal[["accent_orange"]],
                                 "concentrado, convergido" = pal[["neutral_dark"]])) +
  scale_linetype_manual(values = c("concentrado, 500 iterações" = "42",
                                   "concentrado, convergido" = "solid")) +
  scale_fill_manual(values = ver_cols, guide = "none") +
  coord_cartesian(xlim = c(40, 120), ylim = c(29, 56), expand = FALSE) +
  labs(title = "c   O número antigo era iteração inacabada",
       subtitle = "mesmo balanço concentrado; pontos = FEM 3D a 90 °C",
       x = "carcaça do motor (°C)", y = "interior (°C)") +
  theme(legend.position = c(0.40, 0.86),
        legend.key.width = unit(5, "mm"),
        # o rótulo "120" do último tique saía da página pela direita
        plot.margin = margin(2, 8, 2, 2))

fig <- (pa | (pb / pc)) +
  patchwork::plot_layout(widths = c(1, 1.15)) &
  tag_theme

save_pub(fig, file.path(out_dir, "fig11_termica3d"),
         width_mm = 183, height_mm = 112)
