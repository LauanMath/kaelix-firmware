# Figura 21: planta baixa esquemática do galpão da coleta em campo de
# 2/11/2026, com as quatro máquinas ensaiadas e a sala onde ficou o computador.
#
# Origem da geometria: esboço do autor, sem escala. As coordenadas abaixo são
# pixels do esboço (x para a direita, y para baixo), medidas nas linhas e nas
# caixas coloridas do desenho; a figura conserva as proporções do esboço e não
# tem escala nem cotas. As interrupções do traço nas paredes do esboço são
# falhas do desenho à mão, e as paredes saem contínuas.
#
# Fora da figura, por não terem sido levantados: medidas, escala, norte,
# espessura real das paredes, tipo dos portões e posição do ponto de acesso
# Wi-Fi. O gateway acompanhou o transmissor de uma máquina a outra e não tem
# posição na planta.
#
# Representação, conforme o anexo da NBR 6492:1994 e o roteiro de planta baixa
# do IFSC:
#   - parede cortada em duas linhas paralelas, no traço mais grosso do desenho
#     (A-1.1.1); a espessura é simbólica, maior nas paredes externas;
#   - máquinas, degraus e borda do desnível em traço fino (A-1.1.2);
#   - porta com folha e arco de abertura (A-9.2, A-16);
#   - escada com a linha de percurso, que começa num círculo no primeiro
#     degrau e termina em seta no último (A-7);
#   - acesso com o símbolo de seta e o texto ACESSO (A-6);
#   - ambientes nomeados em maiúsculas (A-2.1.1, A-17);
#   - título do desenho com a escala embaixo, aqui SEM ESCALA (roteiro IFSC).
#
# Não há pacote de R para planta de arquitetura, e as bibliotecas de Python
# avaliadas (archit-app, ezdxf) não permitem fixar a fonte do documento com
# texto editável; por isso a planta é desenhada em ggplot2. O contorno das
# paredes é a união dos retângulos de parede, calculada numa grade, porque
# todas as paredes são ortogonais.
#
# Contrato: 160 mm de largura (\textwidth), Times New Roman como no corpo do
# texto, texto editável no SVG e no PDF.

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

# --- geometria do esboço (px) -----------------------------------------------
X0 <- 43; X1 <- 1646          # eixos das paredes esquerda e direita
Y_TOPO_VENDAS <- 36
Y_N2 <- 503                   # parede entre Vendas e o galpão; fachada
Y_DESNIVEL <- 841             # borda do nível 2 sobre o nível 1
Y_BASE <- 1443                # parede de baixo
X_VENDAS <- 612               # parede direita de Vendas
ESP <- c(externa = 18, interna = 12)   # espessura simbólica, px

# Eixos das paredes. ini/fim = TRUE prolonga a ponta em meia espessura para
# fechar o canto; FALSE deixa a ponta no limite do vão.
paredes <- tribble(
  ~x,       ~y,            ~xend,    ~yend,         ~tipo,     ~ini,  ~fim,
  X0,       Y_TOPO_VENDAS, X0,       Y_BASE,        "externa", TRUE,  TRUE,
  X0,       Y_TOPO_VENDAS, X_VENDAS, Y_TOPO_VENDAS, "externa", TRUE,  TRUE,
  X_VENDAS, Y_TOPO_VENDAS, X_VENDAS, Y_N2,          "externa", TRUE,  TRUE,
  X_VENDAS, Y_N2,          X1,       Y_N2,          "externa", TRUE,  TRUE,
  X1,       Y_N2,          X1,       896,           "externa", TRUE,  FALSE, # acesso
  X1,       1130,          X1,       Y_BASE,        "externa", FALSE, TRUE,
  X0,       Y_BASE,        287,      Y_BASE,        "externa", TRUE,  FALSE, # acesso
  554,      Y_BASE,        X1,       Y_BASE,        "externa", FALSE, TRUE,
  X0,       Y_N2,          443,      Y_N2,          "interna", TRUE,  FALSE, # escada
  1261,     Y_N2,          1261,     736,           "interna", TRUE,  TRUE,  # Engenharia
  1261,     736,           1298,     736,           "interna", TRUE,  FALSE, # porta
  1404,     736,           X1,       736,           "interna", FALSE, TRUE,
  988,      1291,          1309,     1291,          "interna", TRUE,  TRUE,  # compressor
  988,      1291,          988,      Y_BASE,        "interna", TRUE,  TRUE,
  1309,     1291,          1309,     Y_BASE,        "interna", TRUE,  TRUE
)

# Borda do desnível entre os níveis 2 e 1, interrompida pela escada.
desnivel <- tribble(
  ~x,  ~y,         ~xend, ~yend,
  X0,  Y_DESNIVEL, 653,   Y_DESNIVEL,
  762, Y_DESNIVEL, X1,    Y_DESNIVEL
)

# Escadas: limites, linhas dos degraus (como no esboço) e sentido de subida.
escadas <- list(
  list(x0 = 443, x1 = X_VENDAS - ESP[["externa"]] / 2, y_alto = Y_N2 + ESP[["interna"]] / 2,
       y_baixo = 584, degraus = c(536, 556)),
  list(x0 = 653, x1 = 762, y_alto = Y_DESNIVEL, y_baixo = 926, degraus = c(858, 881, 904))
)

# Cor de cada máquina: a mesma das figuras de resultados (COR_MAQ em
# docs/monografia/latex/figuras_src/resultados.py, esquema bright de Tol), aqui
# como preenchimento claro, para o nome em preto continuar legível. A cor
# repete o nome escrito na máquina e não é o único código.
COR_MAQ <- c(dobradeira = tol[["maq_dobradeira"]], guilhotina = tol[["maq_guilhotina"]],
             calandra = tol[["maq_calandra"]], compressor = tol[["maq_compressor"]])
clarear <- function(hex, a = 0.55) {
  v <- grDevices::col2rgb(hex)[, 1] * a + 255 * (1 - a)
  grDevices::rgb(v[1], v[2], v[3], maxColorValue = 255)
}

maquinas <- tribble(
  ~rotulo,                  ~maq,         ~x0,  ~y0,  ~x1,  ~y1,
  "CALANDRA\nPIRAMIDAL",    "calandra",   709,  582,  881,  700,
  "DOBRADEIRA",             "dobradeira", 813,  853,  1055, 926,
  "GUILHOTINA\nHIDRÁULICA", "guilhotina", 356,  905,  617,  1042,
  "",                       "compressor", 1081, 1304, 1195, 1401   # nome fora
)

# Porta da Engenharia: vão entre 1298 e 1404 na parede y = 736; folha aberta
# para dentro da sala, com dobradiça no batente da esquerda.
PORTA <- list(x_dob = 1298, x_vao = 1404, y_face = 736 - ESP[["interna"]] / 2)

# --- união das paredes numa grade ------------------------------------------
ret <- paredes |>
  mutate(t = ESP[tipo] / 2,
         horiz = y == yend,
         xmin = ifelse(horiz, pmin(x, xend) - ifelse(ini, t, 0), x - t),
         xmax = ifelse(horiz, pmax(x, xend) + ifelse(fim, t, 0), x + t),
         ymin = ifelse(horiz, y - t, pmin(y, yend) - ifelse(ini, t, 0)),
         ymax = ifelse(horiz, y + t, pmax(y, yend) + ifelse(fim, t, 0)))

contorno_uniao <- function(r) {
  xs <- sort(unique(c(r$xmin, r$xmax))); ys <- sort(unique(c(r$ymin, r$ymax)))
  cx <- head(xs, -1) + diff(xs) / 2; cy <- head(ys, -1) + diff(ys) / 2
  cheio <- matrix(FALSE, length(cx), length(cy))
  for (k in seq_len(nrow(r)))
    cheio[cx > r$xmin[k] & cx < r$xmax[k], cy > r$ymin[k] & cy < r$ymax[k]] <- TRUE
  cel <- function(i, j) i >= 1 && i <= length(cx) && j >= 1 && j <= length(cy) && cheio[i, j]
  seg <- list()
  for (i in seq_along(xs)) for (j in seq_along(cy))          # arestas verticais
    if (cel(i - 1, j) != cel(i, j)) seg[[length(seg) + 1]] <- c(xs[i], ys[j], xs[i], ys[j + 1])
  for (j in seq_along(ys)) for (i in seq_along(cx))          # arestas horizontais
    if (cel(i, j - 1) != cel(i, j)) seg[[length(seg) + 1]] <- c(xs[i], ys[j], xs[i + 1], ys[j])
  s <- as_tibble(do.call(rbind, seg), .name_repair = ~ c("x", "y", "xend", "yend"))
  # junta trechos colineares contíguos, para o traço não mostrar emendas
  bind_rows(
    s |> filter(x == xend) |> arrange(x, y) |> group_by(x) |>
      mutate(g = cumsum(c(TRUE, head(yend, -1) != y[-1]))) |> group_by(x, g) |>
      summarise(y = min(y), yend = max(yend), xend = first(xend), .groups = "drop"),
    s |> filter(y == yend) |> arrange(y, x) |> group_by(y) |>
      mutate(g = cumsum(c(TRUE, head(xend, -1) != x[-1]))) |> group_by(y, g) |>
      summarise(x = min(x), xend = max(xend), yend = first(yend), .groups = "drop")
  ) |> select(x, y, xend, yend)
}
contorno <- contorno_uniao(ret)

# --- conversão para o referencial do gráfico (y para cima) ------------------
fy <- function(y) Y_BASE - y

# --- estilo ------------------------------------------------------------------
PT_NOME <- 8; PT_MAQ <- 7
TS <- function(pt) pt / .pt
mm <- function(x) x / 0.7528  # espessura em mm para linewidth do ggplot2
LW_PAREDE <- mm(0.40)         # contorno cortado
LW_MEDIA  <- mm(0.20)         # esquadria, máquinas, degraus
LW_FINA   <- mm(0.13)         # arco da porta, borda do desnível
TINTA <- "black"

txt <- function(x, y, s, pt = PT_NOME, hjust = 0.5, vjust = 0.5, face = "plain")
  annotate("text", x = x, y = fy(y), label = u(s), size = TS(pt), family = FAMILY,
           hjust = hjust, vjust = vjust, colour = TINTA, lineheight = 0.9, fontface = face)
rect <- function(x0, x1, y0, y1, lw = LW_MEDIA, fill = "white", col = TINTA)
  annotate("rect", xmin = x0, xmax = x1, ymin = fy(y1), ymax = fy(y0),
           fill = fill, colour = col, linewidth = lw)
segs <- function(d, lw, lineend = "butt")
  geom_segment(data = d, aes(x = x, y = fy(y), xend = xend, yend = fy(yend)),
               colour = TINTA, linewidth = lw, lineend = lineend)
seta <- function(x, y, xend, yend, lw = LW_MEDIA, len = 1.4)
  annotate("segment", x = x, y = fy(y), xend = xend, yend = fy(yend), colour = TINTA,
           linewidth = lw, arrow = arrow(length = unit(len, "mm"), type = "open", angle = 25))

# Símbolo de acesso da NBR 6492 (A-6): seta vazada, ponta para dentro.
# (x, y) é a ponta; dir é o sentido da seta: "cima" ou "esquerda".
acesso <- function(x, y, dir, L = 62, W = 40, w = 14, H = 26) {
  # contorno em coordenadas locais: ponta na origem, seta apontando para +v
  v <- c(0, -H, -H, -L, -L, -H, -H, 0)
  h <- c(0, -W / 2, -w / 2, -w / 2, w / 2, w / 2, W / 2, 0)
  pts <- if (dir == "cima") tibble(px = x + h, py = y - v) else tibble(px = x - v, py = y + h)
  annotate("polygon", x = pts$px, y = fy(pts$py), fill = "white", colour = TINTA,
           linewidth = LW_MEDIA)
}

p <- ggplot() + theme_void(base_size = PT_NOME) + coord_fixed(expand = FALSE) +
  theme(plot.margin = margin(0, 0, 0, 0),
        plot.background = element_rect(fill = "white", colour = NA))

# Desnível e escadas.
p <- p + segs(desnivel, LW_FINA)
for (e in escadas) {
  xc <- (e$x0 + e$x1) / 2
  linhas <- tibble(x = e$x0, xend = e$x1, y = c(e$degraus, e$y_baixo), yend = y)
  lados <- tibble(x = c(e$x0, e$x1), xend = c(e$x0, e$x1), y = e$y_alto, yend = e$y_baixo)
  y_ini <- (max(e$degraus) + e$y_baixo) / 2           # meio do primeiro degrau
  p <- p + segs(linhas, LW_MEDIA) + segs(lados, LW_MEDIA) +
    annotate("point", x = xc, y = fy(y_ini), shape = 21, size = 1.1, stroke = 0.35,
             fill = "white", colour = TINTA) +
    seta(xc, y_ini - 5, xc, e$y_alto + 3)
}

# Máquinas.
for (i in seq_len(nrow(maquinas))) {
  m <- maquinas[i, ]
  p <- p + rect(m$x0, m$x1, m$y0, m$y1, fill = clarear(COR_MAQ[[m$maq]]))
  if (nzchar(m$rotulo)) p <- p + txt((m$x0 + m$x1) / 2, (m$y0 + m$y1) / 2, m$rotulo, pt = PT_MAQ)
}

# Computador portátil em vista superior: base, teclado e tela rebatida.
PC <- c(x0 = 1490, x1 = 1560, y_tela = 590, y_dob = 600, y_base = 640)
p <- p + rect(PC[["x0"]], PC[["x1"]], PC[["y_dob"]], PC[["y_base"]]) +
  rect(PC[["x0"]] + 4, PC[["x1"]] - 4, PC[["y_tela"]], PC[["y_dob"]]) +
  rect(PC[["x0"]] + 10, PC[["x1"]] - 10, PC[["y_dob"]] + 8, PC[["y_dob"]] + 24, lw = LW_FINA)

# Porta da Engenharia: folha e arco de abertura.
r_porta <- PORTA$x_vao - PORTA$x_dob
ang <- seq(0, pi / 2, length.out = 60)
arco <- tibble(x = PORTA$x_dob + r_porta * cos(ang), y = PORTA$y_face - r_porta * sin(ang))
p <- p + rect(PORTA$x_dob, PORTA$x_dob + 5, PORTA$y_face - r_porta, PORTA$y_face) +
  annotate("path", x = arco$x, y = fy(arco$y), colour = TINTA, linewidth = LW_FINA)

# Paredes: miolo branco e contorno grosso, por cima de tudo.
p <- p + geom_rect(data = ret, aes(xmin = xmin, xmax = xmax, ymin = fy(ymax), ymax = fy(ymin)),
                   fill = "white", colour = NA) +
  segs(contorno, LW_PAREDE, lineend = "square")

# Acessos do galpão.
p <- p +
  acesso(420, Y_BASE + ESP[["externa"]] / 2 + 14, "cima") +
  txt(420, Y_BASE + 118, "ACESSO", pt = PT_MAQ) +
  acesso(X1 + ESP[["externa"]] / 2 + 14, 1013, "esquerda") +
  txt(X1 + 50, 1013 + 50, "ACESSO", pt = PT_MAQ)

# Nomes dos ambientes e equipamentos.
p <- p +
  txt(327, 270, "VENDAS") +
  txt(260, 700, "NÍVEL 2") +
  txt(640, 1190, "NÍVEL 1") +
  txt(1453, 548, "ENGENHARIA") +
  txt(1525, 672, "COMPUTADOR", pt = PT_MAQ) +
  txt(1148, 1262, "COMPRESSOR DE PARAFUSO", pt = PT_MAQ)

# Título do desenho e escala.
p <- p +
  txt(X1 + 9, Y_BASE + 62, "PLANTA BAIXA", pt = 9, hjust = 1) +
  annotate("segment", x = X1 + 9 - 245, xend = X1 + 9, y = fy(Y_BASE + 82),
           yend = fy(Y_BASE + 82), linewidth = LW_MEDIA, colour = TINTA) +
  txt(X1 + 9, Y_BASE + 108, "SEM ESCALA", pt = PT_MAQ, hjust = 1)

# --- limites e exportação ----------------------------------------------------
XL <- c(X0 - 14, X1 + 120)
YL <- c(Y_TOPO_VENDAS - 14, Y_BASE + 135)
p <- p + scale_x_continuous(limits = XL) +
  scale_y_continuous(limits = rev(fy(YL)))

W_MM <- 160
H_MM <- W_MM * diff(YL) / diff(XL)
save_pub(p, file.path(OUT, "fig21_planta_local"), width_mm = W_MM, height_mm = H_MM)
