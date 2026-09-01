# Figura 7 — cadeia de comunicação exercitada por simulação.
# Arquétipo: grade quantitativa com painel-herói (a). 183 x 118 mm.

script_dir <- function() {
  a <- commandArgs(trailingOnly = FALSE); f <- sub("^--file=", "", a[grep("^--file=", a)])
  if (length(f)) dirname(normalizePath(f)) else getwd()
}
here <- script_dir()
source(file.path(here, "theme_kaelix.R"))
suppressPackageStartupMessages({ library(tibble) })
u <- function(x) enc2utf8(x)
DATA <- file.path(here, "..", "data"); OUT <- file.path(here, "..", "output")
rd <- function(f) readr::read_csv(file.path(DATA, f), show_col_types = FALSE)

modo_cols <- c("sem deslocamento" = pal[["accent_red"]],
               "com deslocamento" = pal[["signal_blue"]])

# (a) HERÓI — sem deslocamento a colisão não é probabilística, é total.
a <- rd("fig7a_jitter.csv") |> dplyr::mutate(modo = u(modo))
pa <- ggplot(a, aes(x = n_dispositivos, y = p_colisao, colour = modo)) +
  geom_line(linewidth = 0.55) + geom_point(size = 1.1) +
  scale_colour_manual(values = modo_cols) +
  scale_y_continuous(labels = scales::percent_format(accuracy = 1), limits = c(-0.02, 1.04)) +
  annotate("text", x = 30, y = 0.93, label = u("sem deslocamento: nenhum pacote chega"),
           size = 1.75, colour = pal[["accent_red"]], family = "Arial") +
  annotate("text", x = 30, y = 0.10, label = u("com deslocamento por device_id"),
           size = 1.75, colour = pal[["signal_blue"]], family = "Arial") +
  labs(title = "a", x = u("dispositivos energizados juntos"),
       y = u("quadros perdidos por colisão")) +
  theme_kaelix() + theme(legend.position = "none")

# (b) funil de 24 h
b <- rd("fig7b_funil.csv") |>
  dplyr::mutate(etapa = factor(u(etapa), levels = u(etapa[order(ordem)])),
                frac = n / max(n))
pb <- ggplot(b, aes(x = etapa, y = n)) +
  geom_col(fill = pal[["signal_blue"]], width = 0.62) +
  geom_text(aes(label = paste0(n, "\n", scales::percent(frac, accuracy = 0.1))),
            vjust = -0.25, size = 1.6, lineheight = 0.95, family = "Arial",
            colour = pal[["neutral_dark"]]) +
  scale_y_continuous(limits = c(0, 3450), expand = expansion(mult = c(0, 0.02))) +
  labs(title = "b", x = NULL, y = u("quadros em 24 h")) +
  theme_kaelix() +
  theme(axis.text.x = element_text(size = BASE - 1.5, angle = 20, hjust = 1))

# (c) alerta segue anomalia sustentada, não anomalia esporádica
cc <- rd("fig7c_alertas.csv") |>
  dplyr::mutate(rot = ifelse(sustentada, u("anomalia sustentada"), u("anomalia esporádica")))
pc <- ggplot(cc, aes(x = dispositivo, y = taxa_anomalia)) +
  geom_col(aes(fill = I(ifelse(alertou, pal[["accent_red"]], pal[["neutral_light"]]))),
           width = 0.68) +
  geom_point(data = dplyr::filter(cc, alertou), aes(y = taxa_anomalia + 0.075),
             shape = 25, size = 1.1, fill = pal[["accent_red"]],
             colour = pal[["accent_red"]]) +
  annotate("text", x = 9.5, y = 0.93, label = u("▼ alerta aberto"), size = 1.7,
           colour = pal[["accent_red"]], family = "Arial") +
  scale_y_continuous(labels = scales::percent_format(accuracy = 1), limits = c(0, 1.0)) +
  scale_x_continuous(breaks = c(0, 5, 10, 15)) +
  labs(title = "c", x = u("dispositivo"), y = u("ciclos anômalos")) +
  theme_kaelix()

# (d) o que o gateway reconstrói do que se perdeu
d <- rd("fig7d_deteccao.csv") |>
  dplyr::mutate(grandeza = factor(u(grandeza), levels = u(grandeza)),
                par = c("perda", "perda", "corrupção", "corrupção"))
pd <- ggplot(d, aes(x = grandeza, y = n)) +
  geom_col(aes(fill = I(ifelse(par == "perda", pal[["neutral_mid"]], pal[["signal_teal"]]))),
           width = 0.62) +
  geom_text(aes(label = n), vjust = -0.35, size = 1.75, family = "Arial",
            colour = pal[["neutral_dark"]]) +
  scale_y_continuous(limits = c(0, 92), expand = expansion(mult = c(0, 0.02))) +
  labs(title = "d", x = NULL, y = u("quadros")) +
  theme_kaelix() +
  theme(axis.text.x = element_text(size = BASE - 1.5, angle = 20, hjust = 1))

fig7 <- (pa | pb) / (pc | pd)
save_pub(fig7, file.path(OUT, "fig7_gateway"), width_mm = 183, height_mm = 118)
cat("fig7_gateway exportada\n")
