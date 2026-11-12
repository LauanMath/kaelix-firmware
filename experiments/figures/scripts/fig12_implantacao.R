# Figura 12: componentes do sistema de coleta e onde cada um roda, com os
# enlaces e o caminho de uma janela medida até a linha no banco (círculos 1 a 6).
# Diagrama sem dado numérico; portas, perfis e nomes conferidos em:
#   kaelix-Ai-center/apps/server/cmd/api/main.go (8080, 8443, API_WEB_ADDR)
#   kaelix-Ai-center/deploy/.env.service (API_WEB_ADDR na porta 8444)
#   kaelix-Ai-center/apps/server/internal/mdns/mdns.go (_kaelix._tcp)
#   lib/kaelix_protocol/kaelix_protocol.h (433 MHz, SF9/125 kHz, perfis de rajada)
#   src/gateway/network.cpp (gravador em LittleFS, rede própria, TLS fixado)
# Contrato: 160 x 98 mm, 7 pt, texto editável, SVG/PDF/TIFF 600 dpi.

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
# FIG_ANON=1 gera a versão do artigo da RECIMA21, em fig12_implantacao_anon: sem o nome do serviço,
# que é o do projeto (avaliação cega), e sem os detalhes de implementação que o artigo não usa (portas,
# bibliotecas, sistema operacional, pareamento), trocados pelo que cada etapa faz com a medição.
# Sem a variável, a saída é a de sempre, usada na monografia.
ANON <- identical(Sys.getenv("FIG_ANON"), "1")
art <- function(monografia, artigo) if (ANON) artigo else monografia
MDNS <- if (ANON) "Anúncio mDNS do serviço da API" else "Anúncio mDNS do serviço _kaelix._tcp"
u <- function(x) enc2utf8(x)
SIZE <- 7
TS <- function(d = 0) (SIZE + d) / .pt

GROUP <- "#F3F3F3"
# Cores de Tol com o papel de theme_kaelix.R: amarelo-escuro para o rádio LoRa, preto para HTTPS e cinzas
# para a rede do próprio computador e a configuração inicial; o tipo de linha repete a distinção.
LINK <- c(lora = tol[["lora"]], https = tol[["preto"]],
          local = tol[["cinza_escuro"]], pareamento = tol[["cinza"]])
LTY <- c(lora = "42", https = "solid", local = "solid", pareamento = "22")

p <- ggplot() + theme_void(base_size = SIZE) +
  scale_x_continuous(limits = c(0, 1), expand = c(0, 0)) +
  scale_y_continuous(limits = c(0, 1), expand = c(0, 0)) +
  theme(plot.margin = margin(1, 1, 1, 1))

rect <- function(x0, x1, y0, y1, fill = "white", lty = "solid", col = "black", lw = 0.35)
  annotate("rect", xmin = x0, xmax = x1, ymin = y0, ymax = y1, fill = fill, colour = col,
           linetype = lty, linewidth = lw)
txt <- function(x, y, s, d = 0, face = "plain", hjust = 0.5, col = "black", vjust = 0.5)
  annotate("text", x = x, y = y, label = u(s), size = TS(d), fontface = face, family = FAMILY,
           hjust = hjust, vjust = vjust, colour = col, lineheight = 0.95)
arr <- function(x0, y0, x1, y1, kind, both = FALSE)
  annotate("segment", x = x0, y = y0, xend = x1, yend = y1, colour = LINK[[kind]],
           linetype = LTY[[kind]], linewidth = 0.45,
           arrow = arrow(length = unit(1.2, "mm"), type = "closed", ends = if (both) "both" else "last"))
step <- function(x, y, n) list(
  annotate("point", x = x, y = y, shape = 21, size = 3.4, fill = "white", colour = "black", stroke = 0.35),
  annotate("text", x = x, y = y, label = n, size = TS(-0.8), family = FAMILY, fontface = "bold"))

pm <- function(x, y, expr, d = 0, hjust = 0.5, col = "black")
  annotate("text", x = x, y = y, label = expr, parse = TRUE, size = TS(d), family = FAMILY,
           hjust = hjust, colour = col)

# Rede local: gateway, computador e celular.
p <- p + rect(0.313, 0.995, 0.015, 0.905, fill = NA, lty = "22", col = pal[["neutral_mid"]], lw = 0.3) +
  txt(0.445, 0.885, "Rede Wi-Fi do local, sem internet", d = -0.5, hjust = 0, col = tol[["cinza_escuro"]])

# Transmissor.
p <- p + rect(0.005, 0.195, 0.27, 0.80, fill = GROUP) +
  txt(0.100, 0.765, "Transmissor", face = "bold") + txt(0.100, 0.725, "ESP32-C3", d = -0.5) +
  rect(0.018, 0.182, 0.55, 0.67) + txt(0.100, 0.632, "Acelerômetro e\ngiroscópio", d = -0.7) +
  txt(0.100, 0.575, "I2C, 6 canais a 1 kHz", d = -0.8, col = tol[["cinza_escuro"]]) +
  rect(0.018, 0.182, 0.30, 0.42) + txt(0.100, 0.375, "Rádio Ra-02 (SX1278)", d = -0.7) +
  txt(0.100, 0.340, art("SPI", ""), d = -0.8, col = tol[["cinza_escuro"]]) +
  txt(0.100, 0.49, art("Descritores, rotina,\nconfiguração gravada", "Janela de 0,512 s\ne indicadores"), d = -0.8, col = tol[["cinza_escuro"]])

# Gateway.
p <- p + rect(0.322, 0.512, 0.27, 0.80, fill = GROUP) +
  pm(0.417, 0.765, 'bolditalic("Gateway")') +
  txt(0.417, 0.725, "ESP32-S3", d = -0.5) +
  rect(0.334, 0.500, 0.55, 0.67) + txt(0.417, 0.625, "Rádio Ra-02 (SX1278)", d = -0.7) +
  txt(0.417, 0.590, art("Tarefa do rádio", ""), d = -0.8, col = tol[["cinza_escuro"]]) +
  rect(0.334, 0.500, 0.30, 0.42) + txt(0.417, 0.375, "Gravador em flash", d = -0.7) +
  txt(0.417, 0.340, art("Segmentos, CRC-32", "Até a confirmação da API"), d = -0.8, col = tol[["cinza_escuro"]]) +
  txt(0.417, 0.49, art("Wi-Fi, TLS, sincronização,\natualização com retorno", "Wi-Fi e HTTPS"), d = -0.8, col = tol[["cinza_escuro"]])

# Celular.
p <- p + rect(0.322, 0.512, 0.045, 0.165) + txt(0.417, 0.130, "Celular", face = "bold", d = -0.3) +
  txt(0.417, 0.078, "Navegador: página de coleta", d = -0.8, col = tol[["cinza_escuro"]])

# Computador.
p <- p + rect(0.615, 0.988, 0.045, 0.860, fill = GROUP) +
  txt(0.8015, 0.828, art("Computador (macOS, na tomada)", "Computador no local"), face = "bold") +
  rect(0.630, 0.973, 0.47, 0.785) + txt(0.8015, 0.755, art("API em Go", "API"), face = "bold", d = -0.3) +
  pm(0.645, 0.705, art('paste("Porta 8443, HTTPS: rotas do ", italic("gateway"))',
                       'paste("Recebe telemetrias e janelas do ", italic("gateway"))'), d = -0.8, hjust = 0) +
  txt(0.645, 0.665, art("Porta 8444, HTTPS: página de coleta", "Grava cada leitura uma só vez"), d = -0.8, hjust = 0) +
  pm(0.645, 0.625, art('"Porta 8080, HTTP: todas as rotas, só local"',
                       'paste("Envia configurações ao ", italic("gateway"))'), d = -0.8, hjust = 0) +
  txt(0.645, 0.565, art(MDNS, "Serve a página de coleta"), d = -0.8, hjust = 0, col = tol[["cinza_escuro"]]) +
  txt(0.645, 0.515, art("Serviço do sistema, com reinício automático", ""), d = -0.8, hjust = 0, col = tol[["cinza_escuro"]]) +
  rect(0.630, 0.790, 0.08, 0.36) + txt(0.710, 0.275, "PostgreSQL", face = "bold", d = -0.3) +
  txt(0.710, 0.185, "Leituras, janelas,\nconfigurações, coletas", d = -0.8, col = tol[["cinza_escuro"]]) +
  rect(0.813, 0.973, 0.08, 0.36) + txt(0.893, 0.275, "Aplicativo de mesa", face = "bold", d = -0.3) +
  txt(0.893, 0.185, art("Wails (Go e React),\nSQLite local", "Configuração e\nacompanhamento"), d = -0.8, col = tol[["cinza_escuro"]])

# Enlaces.
p <- p +
  arr(0.195, 0.62, 0.322, 0.62, "lora") + arr(0.322, 0.53, 0.195, 0.53, "lora") +
  txt(0.2585, 0.725, "LoRa, 433 MHz", d = -0.6) +
  txt(0.2585, 0.665, "Telemetria,\nfragmentos", d = -0.9) +
  txt(0.2585, 0.485, art("Resposta,\nmapa", "Resposta,\nfragmentos\nrecebidos"), d = -0.9) +
  arr(0.512, 0.665, 0.630, 0.665, "https") +
  txt(0.571, 0.735, art("HTTPS,\ncertificado\nfixado", "HTTPS"), d = -0.9) +
  annotate("path", x = c(0.512, 0.580, 0.580, 0.630), y = c(0.105, 0.105, 0.545, 0.545),
           colour = LINK[["https"]], linetype = LTY[["https"]], linewidth = 0.45,
           arrow = arrow(length = unit(1.2, "mm"), type = "closed")) +
  txt(0.546, 0.135, "HTTPS", d = -0.9) +
  arr(0.710, 0.47, 0.710, 0.36, "local", both = TRUE) +
  arr(0.893, 0.36, 0.893, 0.47, "local", both = TRUE) +
  txt(0.903, 0.415, "HTTP local", d = -0.9, hjust = 0)
# Configuração inicial (pareamento): só na monografia; o artigo não trata dela.
if (!ANON) p <- p +
  annotate("path", x = c(0.94, 0.94, 0.417, 0.417), y = c(0.860, 0.955, 0.955, 0.80),
           colour = LINK[["pareamento"]], linetype = LTY[["pareamento"]], linewidth = 0.45,
           arrow = arrow(length = unit(1.2, "mm"), type = "closed")) +
  pm(0.685, 0.978, 'paste("Configuração inicial: o computador entra na rede própria do ", italic("gateway"))',
     d = -0.8)


# Caminho de uma janela até o banco.
p <- p + step(0.035, 0.705, "1") + step(0.2585, 0.575, "2") + step(0.334, 0.42, "3") +
  step(0.571, 0.625, "4") + step(0.650, 0.33, "5") + step(0.833, 0.33, "6")

save_pub(p, file.path(OUT, if (ANON) "fig12_implantacao_anon" else "fig12_implantacao"), width_mm = 160, height_mm = 98)
