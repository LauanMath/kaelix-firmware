# Figura 9 — A v2 aproximou os capacitores e piorou o PDN.
#
# Conclusão: encurtar a distância euclidiana capacitor–pino não melhorou a rede
# de alimentação. O roteador da v2 inseriu duas vias no caminho do capacitor de
# bulk do ESP32-S3, a indutância de laço subiu de 5,5 para 7,6 nH, e a
# impedância vista pelo pino passa a exceder o alvo acima de 6 MHz — onde a v1
# permanecia abaixo dele em toda a faixa.
#
# Arquétipo: grade quantitativa com painel-herói (a).
# Uso: Rscript experiments/figures/scripts/fig9_pdn.R
#      (dados: uv run --with numpy python hardware/pdn.py)

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

z    <- rd("fig9_pdn_impedancia.csv")
caps <- rd("fig9_pdn_capacitores.csv")
ref  <- rd("fig9_pdn_referencias.csv")

Z_ALVO <- ref$z_alvo_ohm[1]
F_CONF <- ref$f_confiavel_hz[1]

# vocabulário: azul = v1 (referência), vermelho = v2 (a que piorou),
# cinza = contexto. Vermelho fica reservado à perda, como nas outras figuras.
ver_cols <- c("v1" = pal[["signal_blue"]], "v2" = pal[["accent_red"]])
carga_ord <- c("ESP32-S3", "Ra-02", "MPU6050")

z$carga <- factor(z$carga, levels = carga_ord)
caps$versao <- factor(caps$versao, levels = c("v1", "v2"))

# --- (a) impedância vista de cada carga -------------------------------------
rot_alvo <- sprintf("alvo %.0f mΩ  (%.0f mV / %.0f mA)",
                    Z_ALVO * 1000, ref$ondulacao_v[1] * 1000,
                    ref$degrau_a[1] * 1000)

pa <- ggplot(z, aes(freq_hz, z_ohm, colour = versao)) +
  # ymin/ymax finitos: com -Inf/Inf o eixo log transforma para NaN e o
  # retângulo simplesmente não desenha (avisos "NaNs produced").
  annotate("rect", xmin = F_CONF, xmax = max(z$freq_hz),
           ymin = 0.008, ymax = 20, fill = pal[["neutral_light"]], alpha = 0.6) +
  geom_hline(yintercept = Z_ALVO, colour = pal[["neutral_dark"]],
             linetype = "22", linewidth = 0.35) +
  geom_line(linewidth = 0.5) +
  facet_wrap(~carga, nrow = 1) +
  # Notação de engenharia em vez de 10^n: o expoente sobrescrito do
  # label_log renderiza a 4,2 pt (0,7 x os 6,0 pt do eixo), abaixo do piso de
  # 5 pt, e o "8" do 10^8 ainda saía 0,5 pt para fora da página.
  scale_x_log10(breaks = 10^(3:8),
                labels = c("1 k", "10 k", "100 k", "1 M", "10 M", "100 M")) +
  scale_y_log10(labels = function(v) ifelse(v < 1, sprintf("%.2f", v),
                                            sprintf("%.0f", v)),
                breaks = c(0.01, 0.1, 1, 10)) +
  annotation_logticks(sides = "bl", linewidth = 0.22,
                      short = unit(0.5, "mm"), mid = unit(0.8, "mm"),
                      long = unit(1.2, "mm")) +
  scale_colour_manual(values = ver_cols) +
  coord_cartesian(xlim = c(1e3, 1e8), ylim = c(0.008, 20), expand = FALSE) +
  labs(title = "a   Impedância do PDN vista do pino de alimentação",
       subtitle = paste0(rot_alvo,
                         ";  faixa cinza: acima de 50 MHz responde o ",
                         "encapsulamento, não a placa"),
       x = "frequência (Hz)", y = "|Z| (Ω)") +
  theme(legend.position = c(0.055, 0.86),
        legend.key.width = unit(4, "mm"),
        # 6 mm entre facetas: com 3,2 o "100 M" de uma faceta encostava no
        # "1 k" da seguinte e as duas se liam como um rótulo só
        panel.spacing = unit(6, "mm"),
        # margem à direita: o rótulo "100 M" da última faceta encostava na
        # borda da página e saía 0,5 pt para fora
        plot.margin = margin(2, 7, 2, 2))

# --- (b) mecanismo: de onde vem a indutância --------------------------------
mec <- caps |>
  dplyr::select(versao, cap, valor, l_pista_nh, l_vias_nh) |>
  tidyr::pivot_longer(c(l_pista_nh, l_vias_nh),
                      names_to = "parte", values_to = "nh")
mec$parte <- factor(mec$parte, levels = c("l_vias_nh", "l_pista_nh"),
                    labels = c("vias", "pista"))
mec$rotulo <- paste0(mec$cap, "\n", mec$valor)
ordem <- caps |> dplyr::filter(versao == "v2") |>
  dplyr::arrange(dplyr::desc(l_total_nh))
mec$rotulo <- factor(mec$rotulo,
                     levels = paste0(ordem$cap, "\n", ordem$valor))

# O eixo é CORTADO em 10 nH. Sem isso a barra de 36 nH do C8 na v1 ocupa o
# painel inteiro e a comparação v1 x v2 dos outros cinco — que é a conclusão
# da figura — some. O valor cortado vai anotado, e o corte é declarado.
TETO <- 10
estouro <- caps |> dplyr::filter(l_total_nh > TETO) |>
  dplyr::mutate(rotulo = paste0(cap, "\n", valor))
estouro$rotulo <- factor(estouro$rotulo, levels = levels(mec$rotulo))

pb <- ggplot(mec, aes(rotulo, nh, fill = parte)) +
  geom_col(width = 0.62, colour = NA) +
  geom_label(data = estouro,
             aes(rotulo, TETO * 0.90,
                 label = sprintf("%.1f nH \u2191", l_total_nh)),
             inherit.aes = FALSE, size = (BASE - 1.4) / .pt,
             colour = pal[["neutral_dark"]], fontface = "bold",
             fill = "white", label.size = 0, label.padding = unit(0.5, "mm")) +
  facet_wrap(~versao, nrow = 1) +
  scale_fill_manual(values = c("vias" = pal[["accent_orange"]],
                               "pista" = pal[["neutral_mid"]])) +
  # clip "on": com "off" a barra cortada do C8 desenha para fora do painel e
  # atravessa a figura inteira como uma faixa cinza.
  coord_cartesian(ylim = c(0, TETO), expand = FALSE, clip = "on") +
  labs(title = "b   Composição da indutância de laço",
       subtitle = paste0("cada via passante custa 1,30 nH; a pista, 781 pH/mm.",
                         "  Eixo cortado em ", TETO, " nH"),
       x = NULL, y = "L de laço (nH)") +
  theme(legend.position = c(0.87, 0.80),
        axis.text.x = element_text(size = BASE - 1.2, lineheight = 1.0,
                                   margin = margin(t = 1.2)),
        panel.spacing = unit(2.6, "mm"))

# --- (c) por que a régua antiga enganava ------------------------------------
lim <- c(0, max(caps$pista_mm) * 1.08)
# Deslocamento de rótulo fixado à mão: são três pontos e eles se sobrepõem
# quando anotados no mesmo sentido. Determinístico, ao contrário de um
# repulsor com semente.
mkrot <- function(cap_, ver_, dx, dy, hj) {
  r <- caps |> dplyr::filter(cap == cap_, versao == ver_)
  dplyr::mutate(r, lx = euclid_mm + dx, ly = pista_mm + dy, hj = hj,
                txt = sprintf("%s (%s)  %.1f\u00d7", cap, versao,
                              pista_mm / euclid_mm))
}
rots <- dplyr::bind_rows(mkrot("C8", "v1",  1.7,  0.0, 0),
                         mkrot("C3", "v1",  2.0,  3.0, 0),
                         mkrot("C3", "v2",  2.0, -3.2, 0))

pc <- ggplot(caps, aes(euclid_mm, pista_mm, colour = versao)) +
  geom_abline(slope = 1, intercept = 0, colour = pal[["neutral_mid"]],
              linetype = "22", linewidth = 0.35) +
  # deslocada da linha: sobre ela, o traço cruza os glifos
  annotate("text", x = 26.5, y = 23.0, label = "pista = distância",
           size = (BASE - 1.4) / .pt, colour = pal[["neutral_mid"]],
           hjust = 0, angle = 45) +
  geom_point(size = 1.1) +
  geom_segment(data = rots, aes(x = euclid_mm, y = pista_mm, xend = lx, yend = ly),
               linewidth = 0.22, show.legend = FALSE) +
  geom_text(data = rots, aes(lx, ly, label = txt, hjust = hj),
            size = (BASE - 1.4) / .pt, vjust = 0.5, show.legend = FALSE) +
  scale_colour_manual(values = ver_cols) +
  coord_fixed(ratio = 1, xlim = lim, ylim = lim, expand = FALSE) +
  labs(title = "c   Pista roteada × linha reta",
       subtitle = "a régua mede a reta; o laço vê a pista",
       x = "distância capacitor–pino (mm)", y = "comprimento roteado (mm)") +
  theme(legend.position = "none")

fig <- (pa / (pb | pc)) +
  patchwork::plot_layout(heights = c(1.05, 1)) &
  tag_theme

save_pub(fig, file.path(out_dir, "fig9_pdn"), width_mm = 183, height_mm = 118)
