# Figura 10 — A placa passa em Steinberg; o invólucro é que a reprova.
#
# Conclusão: isolada, a v2 tem margem de 4,2x no critério de fadiga de junta
# de solda. Mas o modo do invólucro (1670 Hz) fica logo acima do modo da placa
# (1352 Hz), a transmissibilidade nessa razão vale 2,88, e a margem cai para
# 1,4x — vida da junta do módulo ESP32 de 43 h em zona C/D contínua, contra
# mais de 100 anos na v1. A regra da oitava de Steinberg falha em três das
# quatro combinações.
#
# Arquétipo: grade quantitativa com painel-herói (a).
# Uso: Rscript experiments/figures/scripts/fig10_vibracao.R
#      (dados: uv run --with numpy python hardware/vibracao.py)

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

tr   <- rd("fig10_transmissibilidade.csv")
marg <- rd("fig10_margens.csv")
sens <- rd("fig10_sensibilidade.csv")
ref  <- rd("fig10_referencias.csv")

FN <- c(v1 = ref$fn_v1[1], v2 = ref$fn_v2[1])
ver_cols <- c("v1" = pal[["signal_blue"]], "v2" = pal[["accent_red"]])

# O caso que decide é a carga no piso: é onde a montagem realmente põe a
# placa, e é o que aproxima os dois modos.
tr_piso <- dplyr::filter(tr, carga == "carga no piso")
modos <- data.frame(versao = names(FN), fn = as.numeric(FN),
                    fc = c(unique(tr_piso$f_chassi_hz[tr_piso$versao == "v1"]),
                           unique(tr_piso$f_chassi_hz[tr_piso$versao == "v2"])))
modos$t <- sapply(seq_len(nrow(modos)), function(i) {
  d <- tr_piso[tr_piso$versao == modos$versao[i], ]
  approx(d$freq_hz, d$t, modos$fn[i])$y
})
modos$rot <- sprintf("placa %s\n%.0f Hz  →  T = %.2f",
                     modos$versao, modos$fn, modos$t)
# posição do rótulo fixada à mão: sobre a curva, o traço cruza os glifos
modos$lx <- c(1500, 2200)
modos$ly <- c(0.25, 6.0)
modos$hj <- c(1, 0)

# --- (a) o chassi amplifica, e é aí que a v2 cai ----------------------------
pa <- ggplot(tr_piso, aes(freq_hz, t, colour = versao)) +
  geom_hline(yintercept = 1, colour = pal[["neutral_mid"]],
             linetype = "22", linewidth = 0.35) +
  geom_line(linewidth = 0.55) +
  geom_segment(data = modos, aes(x = fn, y = t, xend = lx, yend = ly),
               linewidth = 0.22, show.legend = FALSE) +
  geom_point(data = modos, aes(fn, t), size = 1.5) +
  geom_text(data = modos, aes(lx, ly, label = rot, hjust = hj),
            vjust = 0.5, size = (BASE - 1.3) / .pt, lineheight = 0.95,
            show.legend = FALSE) +
  scale_x_log10(breaks = c(100, 200, 500, 1000, 2000, 5000),
                labels = c("100", "200", "500", "1 k", "2 k", "5 k")) +
  scale_y_log10(breaks = c(0.1, 0.3, 1, 3, 10),
                labels = c("0,1", "0,3", "1", "3", "10")) +
  # o pico vale Q = 1/(2*zeta) = 16,7; com o teto em 16 ele saía cortado
  annotation_logticks(sides = "bl", linewidth = 0.22,
                      short = unit(0.5, "mm"), mid = unit(0.8, "mm"),
                      long = unit(1.2, "mm")) +
  scale_colour_manual(values = ver_cols) +
  coord_cartesian(xlim = c(100, 6000), ylim = c(0.06, 26), expand = FALSE) +
  labs(title = "a   O invólucro amplifica o que chega na placa",
       subtitle = paste0("uma curva por versão de invólucro (ζ = ",
                         ref$zeta_asa[1], "); o ponto marca onde cai o modo ",
                         "da placa daquela versão. Acima de 1 o chassi ",
                         "entrega mais do que recebe"),
       x = "frequência (Hz)", y = "transmissibilidade T") +
  theme(legend.position = "none")

# --- (b) margem por componente, antes e depois da correção ------------------
mb <- marg |>
  dplyr::select(versao, ref, margem, margem_corrigida) |>
  tidyr::pivot_longer(c(margem, margem_corrigida),
                      names_to = "caso", values_to = "m")
mb$caso <- factor(mb$caso, levels = c("margem", "margem_corrigida"),
                  labels = c("base rígida", "com o chassi"))
ordem <- marg |> dplyr::filter(versao == "v2") |>
  dplyr::arrange(margem_corrigida)
mb$ref <- factor(mb$ref, levels = ordem$ref)

pb <- ggplot(mb, aes(ref, m, colour = versao, shape = caso)) +
  geom_hline(yintercept = 1, colour = pal[["accent_red"]],
             linetype = "22", linewidth = 0.4) +
  # x discreto: `annotate` com x numérico cria uma escala contínua e o eixo
  # de fatores deixa de treinar ("Discrete value supplied to a continuous scale")
  annotate("text", x = ordem$ref[nrow(ordem)], y = 1.35,
           label = "abaixo disto reprova", hjust = 1,
           size = (BASE - 1.4) / .pt, colour = pal[["accent_red"]]) +
  geom_line(aes(group = interaction(versao, ref)),
            colour = pal[["neutral_light"]], linewidth = 0.4) +
  geom_point(size = 1.3) +
  scale_y_log10(breaks = c(1, 3, 10, 30, 100, 300),
                labels = c("1", "3", "10", "30", "100", "300")) +
  scale_colour_manual(values = ver_cols) +
  scale_shape_manual(values = c("base rígida" = 1, "com o chassi" = 16)) +
  coord_cartesian(ylim = c(0.8, 400), expand = TRUE) +
  labs(title = "b   Margem de Steinberg por componente",
       subtitle = "zona C/D contínua; cheio = já com o chassi — a v1 atenua, a v2 amplifica",
       x = NULL, y = "margem  Z adm / Z 3σ") +
  theme(legend.position = c(0.72, 0.26),
        legend.spacing.y = unit(0, "mm"),
        legend.box = "horizontal")

# --- (c) sensibilidade ------------------------------------------------------
sens$zona <- factor(sens$zona, levels = c("A/B", "B/C", "C/D"))
sens$q_rotulo <- factor(sens$q_rotulo,
                        levels = c("Q = 10", "Q = 20", "sqrt(fn)"))
pc <- ggplot(sens, aes(zona, margem, colour = versao, group = versao)) +
  geom_hline(yintercept = 1, colour = pal[["accent_red"]],
             linetype = "22", linewidth = 0.4) +
  geom_line(linewidth = 0.45) +
  geom_point(size = 1.1) +
  facet_wrap(~q_rotulo, nrow = 1) +
  scale_y_log10(breaks = c(1, 10, 100), labels = c("1", "10", "100")) +
  scale_colour_manual(values = ver_cols) +
  labs(title = "c   Sensibilidade ao amortecimento e à severidade",
       subtitle = "sem a correção do chassi; a ordem entre v1 e v2 não muda",
       x = "zona ISO 10816-3", y = "margem") +
  theme(legend.position = "none", panel.spacing = unit(2.6, "mm"))

fig <- (pa / (pb | pc)) +
  patchwork::plot_layout(heights = c(1, 1)) &
  tag_theme

save_pub(fig, file.path(out_dir, "fig10_vibracao"),
         width_mm = 183, height_mm = 122)
