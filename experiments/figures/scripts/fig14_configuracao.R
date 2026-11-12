# Figura 14: caminho de uma configuração nova do aplicativo até o transmissor e
# como a API chega aos estados pendente, enviado pelo rádio e aplicado.
# Diagrama de sequência sem escala de tempo. Conferido em:
#   kaelix-Ai-center/apps/server/internal/store/config.go (ConfigState, applyTelemetry)
#   kaelix-Ai-center/apps/server/internal/store/sync.go (resposta da sincronização)
#   src/gateway/records.h (DeviceTable: pending_for, mark_radiated, clear_except)
#   src/gateway/main.cpp (handle_telemetry) e src/gateway/network.cpp (send_sync)
#   src/transmitter/main.cpp (apply_new_config, update_link) e
#   lib/kaelix_protocol/kaelix_protocol.h (link_update)
# Contrato: 160 x 112 mm, 7 pt, texto editável, SVG/PDF/TIFF 600 dpi.

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
OUT <- file.path(here, "..", "output")
u <- function(x) enc2utf8(x)
SIZE <- 7
TS <- function(d = 0) (SIZE + d) / .pt

X <- c(app = 0.10, api = 0.36, gw = 0.64, tx = 0.90)
TOP <- 0.94; BOTTOM <- 0.03
# Cores de Tol com o papel de theme_kaelix.R: preto para HTTPS, amarelo-escuro para o rádio LoRa e
# cinza-escuro para a rede do próprio computador; o tipo de linha repete a distinção.
CH <- c(https = tol[["preto"]], lora = tol[["lora"]], local = tol[["cinza_escuro"]])
LT <- c(https = "solid", lora = "42", local = "solid")

p <- ggplot() + theme_void(base_size = SIZE) +
  scale_x_continuous(limits = c(0, 1), expand = c(0, 0)) +
  scale_y_continuous(limits = c(0, 1), expand = c(0, 0)) +
  theme(plot.margin = margin(1, 1, 1, 1))

head_box <- function(x, label, parse = FALSE) list(
  annotate("rect", xmin = x - 0.085, xmax = x + 0.085, ymin = TOP - 0.025, ymax = TOP + 0.04,
           fill = "#F3F3F3", colour = "black", linewidth = 0.35),
  annotate("text", x = x, y = TOP + 0.0075, label = label, parse = parse, size = TS(), fontface = "bold",
           family = FAMILY),
  annotate("segment", x = x, xend = x, y = TOP - 0.025, yend = BOTTOM, linewidth = 0.3,
           linetype = "22", colour = pal[["neutral_mid"]]))
msg <- function(from, to, y, label, kind, n, parse = FALSE, above = TRUE) {
  x0 <- X[[from]]; x1 <- X[[to]]
  list(annotate("segment", x = x0, xend = x1, y = y, yend = y, colour = CH[[kind]], linetype = LT[[kind]],
                linewidth = 0.45, arrow = arrow(length = unit(1.2, "mm"), type = "closed")),
       # rótulo no meio do trecho entre o círculo do passo e a ponta da seta, para não encostar no círculo;
       # o de duas linhas cresce para cima, a partir de logo acima da seta
       annotate("text", x = (x0 + sign(x1 - x0) * 0.045 + x1) / 2,
                y = y + if (!above) -0.018 else if (grepl("\n", label)) 0.008 else 0.018,
                vjust = if (above && grepl("\n", label)) 0 else 0.5, lineheight = 0.95,
                label = label, parse = parse,
                size = TS(-0.6), family = FAMILY, colour = "black"),
       annotate("point", x = x0 + sign(x1 - x0) * 0.022, y = y + 0.018, shape = 21, size = 3.2,
                fill = "white", colour = "black", stroke = 0.35),
       annotate("text", x = x0 + sign(x1 - x0) * 0.022, y = y + 0.018, label = n, size = TS(-1),
                family = FAMILY, fontface = "bold"))
}
note <- function(x, y, label, w = 0.16, h = 0.045, fill = "white", lty = "solid", parse = FALSE, hjust = 0.5)
  list(annotate("rect", xmin = x - w / 2, xmax = x + w / 2, ymin = y - h / 2, ymax = y + h / 2,
                fill = fill, colour = pal[["neutral_dark"]], linewidth = 0.3, linetype = lty),
       annotate("text", x = x, y = y, label = label, parse = parse, size = TS(-0.8), family = FAMILY,
                colour = "black", lineheight = 0.95))
state <- function(y, label) list(
  annotate("label", x = X[["api"]] - 0.012, y = y, label = u(label), size = TS(-0.7), family = FAMILY, hjust = 1,
           fontface = "bold", label.size = 0.3, label.r = unit(0.6, "mm"), fill = "white",
           colour = "black", label.padding = unit(0.6, "mm")))

p <- p + head_box(X[["app"]], u("Aplicativo")) + head_box(X[["api"]], "API") +
  head_box(X[["gw"]], 'bolditalic("Gateway")', parse = TRUE) + head_box(X[["tx"]], u("Transmissor"))

y <- c(0.875, 0.80, 0.73, 0.62, 0.545, 0.455, 0.375, 0.29, 0.21)
p <- p +
  msg("app", "api", y[1], u("Configuração nova"), "local", "1") +
  state(y[1] - 0.035, sprintf("pendente (versão v)")) +
  msg("gw", "api", y[2], u("Sincronização, a cada 5 s"), "https", "2") +
  msg("api", "gw", y[3], u("Configuração v do transmissor"), "https", "3") +
  note(X[["gw"]], y[3] - 0.045, u("Grava na tabela de transmissores"), w = 0.24, h = 0.038) +
  msg("tx", "gw", y[4], u("Telemetria, versão v \u2212 1"), "lora", "4") +
  msg("gw", "tx", y[5], u("Resposta com a\nconfiguração v"), "lora", "5") +
  note(X[["tx"]], y[5] - 0.048, u("Aplica v como provisória\ne guarda a anterior"), w = 0.18, h = 0.05) +
  msg("gw", "api", y[6], u("Sincronização: v\nenviada pelo rádio"), "https", "6") +
  state(y[6] - 0.035, "enviado") +
  msg("tx", "gw", y[7], u("Telemetria, versão v"), "lora", "7") +
  note(X[["tx"]], y[7] - 0.048, u("Ouve a resposta\ne confirma v"), w = 0.18, h = 0.05) +
  msg("gw", "api", y[8], u("Leitura com versão v"), "https", "8") +
  state(y[8] - 0.035, "aplicado") +
  msg("api", "gw", y[9], u("Sincronização sem\neste transmissor"), "https", "9") +
  note(X[["gw"]], y[9] - 0.042, u("Deixa de repassar v"), w = 0.2, h = 0.038) +
  note(0.685, 0.055, u("Sem resposta durante o prazo de perda do enlace depois do passo 5, o transmissor volta\nà configuração anterior e recusa v se ela voltar. Se o silêncio durar mais um prazo,\nele eleva a potência para 17 dBm e deixa de seguir a rotina, sem parar de medir."),
       w = 0.60, h = 0.075, fill = "#F3F3F3", lty = "22")

leg <- tibble::tibble(x = c(0.03, 0.30, 0.56),
                      kind = c("local", "https", "lora"),
                      txt = u(c("HTTP no próprio computador", "HTTPS na rede local", "LoRa")))
pl <- ggplot(leg) + theme_void() +
  geom_segment(aes(x = x, xend = x + 0.05, y = 0.5, yend = 0.5, colour = I(CH[kind]),
                   linetype = I(LT[kind])), linewidth = 0.45) +
  geom_text(aes(x = x + 0.06, y = 0.5, label = txt), hjust = 0, size = TS(-0.6), family = FAMILY) +
  scale_x_continuous(limits = c(0, 1), expand = c(0, 0)) + scale_y_continuous(limits = c(0, 1))

save_pub(p / pl + patchwork::plot_layout(heights = c(1, 0.05)),
         file.path(OUT, "fig14_configuracao"), width_mm = 160, height_mm = 112)
