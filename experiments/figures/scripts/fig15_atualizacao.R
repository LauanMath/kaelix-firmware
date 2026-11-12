# Figura 15: memória flash do gateway (a), lida de partitions/gateway_16MB.csv, e
# o caminho de uma atualização sem cabo com retorno automático (b). Conferido em:
#   src/gateway/network.cpp (run_ota, check_ota_state, confirm_ota_after_sync,
#     verifyRollbackLater)
#   kaelix-Ai-center/apps/server/internal/store/firmware.go e sync.go (estados
#     pending, offered, downloaded, applied, failed)
# Contrato: 160 x 104 mm, Arial de 5 a 7 pt, texto editável, SVG/PDF/TIFF 600 dpi.

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
dec <- function(x, d = 1) formatC(x, format = "f", digits = d, decimal.mark = ",")

# --- a: partições -------------------------------------------------------------
raw <- readLines(file.path(here, "..", "..", "..", "partitions", "gateway_16MB.csv"), encoding = "UTF-8")
raw <- raw[!grepl("^\\s*#", raw) & nzchar(trimws(raw))]
part <- do.call(rbind, lapply(strsplit(raw, ","), function(f) {
  f <- trimws(f)
  data.frame(nome = f[1], tipo = f[2], subtipo = f[3], inicio = strtoi(sub("0x", "", f[4]), 16L),
             tamanho = strtoi(sub("0x", "", f[5]), 16L))
}))
MiB <- 1024^2
FLASH <- 16 * MiB
stopifnot(max(part$inicio + part$tamanho) == FLASH)
USO <- c(nvs = "configuração gravada", otadata = "imagem a iniciar", app0 = "Aplicação A",
         app1 = "Aplicação B", spool = "Gravador de leituras e janelas", coredump = "Registro de falha")
part <- part |>
  mutate(fim = inicio + tamanho, x0 = inicio / MiB, x1 = fim / MiB,
         grande = tamanho >= MiB,
         rot = ifelse(grande, sprintf("%s (%s MiB)", USO[nome], mapply(dec, tamanho / MiB, ifelse(tamanho %% MiB == 0, 0, 2))),
                      sprintf("%s, %s KiB", USO[nome], dec(tamanho / 1024, 0))),
         # O gravador guarda o que chega pela rajada: o amarelo-claro da rajada na Figura do ciclo de rádio.
         fill = dplyr::case_when(subtipo %in% c("ota_0", "ota_1") ~ tol[["cinza_claro"]],
                                 nome == "spool" ~ tol[["lora_claro"]],
                                 TRUE ~ "white"))
reserved <- data.frame(x0 = 0, x1 = min(part$inicio) / MiB)
small <- dplyr::filter(part, !grande)
left <- dplyr::filter(small, x1 < 1)
right <- dplyr::filter(small, x0 > 8)
left_txt <- sprintf("Antes de %s KiB: carregador e tabela de partições (%s KiB), %s",
                    dec(max(left$fim) / 1024, 0), dec(min(part$inicio) / 1024, 0),
                    paste(sprintf("%s (%s KiB)", USO[left$nome], dec(left$tamanho / 1024, 0)), collapse = " e "))
right_txt <- sprintf("%s, %s KiB", USO[right$nome], dec(right$tamanho / 1024, 0))

pa <- ggplot() +
  geom_rect(data = reserved, aes(xmin = x0, xmax = x1, ymin = 0.6, ymax = 1.4), fill = "white",
            colour = pal[["neutral_dark"]], linewidth = 0.3) +
  geom_rect(data = part, aes(xmin = x0, xmax = x1, ymin = 0.6, ymax = 1.4, fill = I(fill)),
            colour = pal[["neutral_dark"]], linewidth = 0.3) +
  # Texto preto sobre os preenchimentos claros: contraste acima de 4,5:1, como pede a Nature.
  geom_text(data = dplyr::filter(part, grande), aes(x = (x0 + x1) / 2, y = 1, label = u(rot)),
            size = TS(-0.5), family = FAMILY, colour = "black") +
  annotate("segment", x = 0.03, xend = 0.03, y = 1.4, yend = 1.72, linewidth = 0.25, colour = pal[["neutral_dark"]]) +
  annotate("text", x = 0.03, y = 1.85, label = u(left_txt), hjust = 0, size = TS(-0.8), family = FAMILY) +
  annotate("segment", x = mean(c(right$x0, right$x1)), xend = mean(c(right$x0, right$x1)), y = 1.4, yend = 1.72,
           linewidth = 0.25, colour = pal[["neutral_dark"]]) +
  annotate("text", x = right$x1, y = 1.85, label = u(right_txt), hjust = 1, size = TS(-0.8), family = FAMILY) +
  scale_x_continuous(breaks = seq(0, 16, by = 2), limits = c(0, 16), expand = c(0.005, 0)) +
  scale_y_continuous(limits = c(0.55, 2.05), expand = c(0, 0)) +
  labs(x = u("Endereço na memória flash (MiB)"), y = NULL) +
  theme_kaelix(SIZE) +
  theme(axis.line.y = element_blank(), axis.ticks.y = element_blank(), axis.text.y = element_blank(),
        axis.line.x = element_line(linewidth = 0.6 / .pt), axis.ticks.x = element_line(linewidth = 0.6 / .pt))

# --- b: atualização com retorno -------------------------------------------------
box <- function(x, y, w, h, title, state = NULL, fill = "white", lty = "solid", dy = 0.07) {
  out <- list(annotate("rect", xmin = x - w / 2, xmax = x + w / 2, ymin = y - h / 2, ymax = y + h / 2,
                       fill = fill, colour = "black", linewidth = 0.35, linetype = lty),
              annotate("text", x = x, y = y + if (is.null(state)) 0 else dy, label = u(title),
                       size = TS(-0.7), family = FAMILY, lineheight = 0.95))
  if (!is.null(state)) out <- c(out, list(
    annotate("text", x = x, y = y - h / 2 + 0.07, label = u(sprintf("API: %s", state)), size = TS(-0.9),
             family = FAMILY, fontface = "italic", colour = "black")))
  out
}
ar <- function(x0, y0, x1, y1, col = pal[["neutral_dark"]], lty = "solid")
  annotate("segment", x = x0, y = y0, xend = x1, yend = y1, colour = col, linetype = lty, linewidth = 0.4,
           arrow = arrow(length = unit(1.1, "mm"), type = "closed"))
tag <- function(x, y, s, hjust = 0.5)
  annotate("text", x = x, y = y, label = u(s), size = TS(-0.9), family = FAMILY, hjust = hjust, colour = "black")

W <- 0.175; Hb <- 0.30
xs <- c(0.10, 0.315, 0.53, 0.745)
YT <- 0.75; YB <- 0.20
pb <- ggplot() + theme_void(base_size = SIZE) +
  scale_x_continuous(limits = c(0, 1), expand = c(0, 0)) +
  scale_y_continuous(limits = c(0, 1), expand = c(0, 0)) +
  box(xs[1], YT, W, Hb, "Aplicativo envia\no binário à API", "pendente") +
  box(xs[2], YT, W, Hb, "Sincronização oferece\nversão, SHA-256,\ntamanho e caminho", "oferecido") +
  box(xs[3], YT, W, Hb, "Baixa por HTTPS\ne grava no espaço\nde aplicação que\nnão está em uso", "baixado", dy = 0.045) +
  box(xs[4], YT, W, Hb, "Confere tamanho\ne SHA-256, marca\na imagem nova\ne reinicia") +
  box(0.92, YT, 0.14, Hb, "Imagem nova\nem verificação", fill = "#F3F3F3") +
  box(0.745, YB, W, Hb, "Primeira sincronização\nbem-sucedida confirma\na imagem nova", "aplicado") +
  box(0.92, YB, 0.14, Hb, "Reinício antes da\nconfirmação: volta à\nimagem anterior", "falhou", lty = "22") +
  box(0.53, YB, W, Hb, "Tamanho ou SHA-256\ndiferente: continua na\nimagem atual", "falhou", lty = "22") +
  ar(xs[1] + W / 2, YT, xs[2] - W / 2, YT) + ar(xs[2] + W / 2, YT, xs[3] - W / 2, YT) +
  ar(xs[3] + W / 2, YT, xs[4] - W / 2, YT) + ar(xs[4] + W / 2, YT, 0.92 - 0.07, YT) +
  ar(0.92, YT - Hb / 2, 0.92, YB + Hb / 2, col = tol[["cinza_escuro"]], lty = "22") +
  ar(0.89, YT - Hb / 2, 0.80, YB + Hb / 2) +
  ar(xs[4] - 0.03, YT - Hb / 2, xs[3] + 0.02, YB + Hb / 2, col = tol[["cinza_escuro"]], lty = "22") +
  tag(0.93, 0.475, "Trava ou\nreinicia", hjust = 0) +
  tag(0.835, 0.475, "Sincroniza", hjust = 1) +
  tag(0.60, 0.50, "Falha na\nconferência", hjust = 1) +
  annotate("text", x = 0.03, y = YB, hjust = 0, size = TS(-0.8), family = FAMILY, lineheight = 0.95,
           colour = "black",
           label = u("Uma atualização que falhou fica encerrada\nna API e não é oferecida de novo. A versão\nem execução é informada a cada sincronização."))

fig <- (pa / pb) + patchwork::plot_layout(heights = c(0.42, 1)) +
  patchwork::plot_annotation(tag_levels = "a") &
  theme(plot.tag = element_text(size = 8, face = "bold", family = FAMILY))

save_pub(fig, file.path(OUT, "fig15_atualizacao"), width_mm = 160, height_mm = 104)
