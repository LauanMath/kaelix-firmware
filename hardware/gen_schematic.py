"""Gera o esquemático KiCad do Kaelix a partir da netlist declarada aqui.

Por que gerado e não desenhado à mão: a netlist abaixo é a ÚNICA fonte da
verdade, e ela é conferível linha a linha contra o firmware. Um esquemático
desenhado no editor diverge do firmware em silêncio; este quebra no ERC.

Pinos conferidos contra:
  variants/esp32s3/pins_arduino.h   SDA=8 SCL=9 SS=10 MOSI=11 SCK=12 MISO=13
  src/comms/lora.cpp:21-23          NSS=10 DIO0=14 RST=21
  src/sensors/temperature.cpp:17    NTC = GPIO4 (ADC1_CH3)
  src/power/sleep.cpp:18            corte = GPIO5
  lib/thermistor/thermistor.h:63    divisor 3V3_SW -> 10k -> nó -> NTC -> GND

Corte de energia dos periféricos — por que high-side e não low-side:

  A versão anterior cortava o RETORNO A GND do MPU6050 com um BC337. Isso
  não desliga o sensor: os pull-ups de 4k7 continuam em +3V3 e injetam
  corrente em SDA/SCL, que entra pelos diodos de ESD do MPU6050 e o mantém
  parcialmente alimentado, com o GND dele flutuando em Vce(sat). O corte
  precisa ser do lado ALTO, e precisa levar os pull-ups junto.

  Q1 (P-MOSFET) abre e fecha o rail +3V3_SW. Q2 (NPN) inverte o nível: o
  GPIO5 é ativo-alto (como o firmware já supõe em peripherals_power()) e o
  gate do P-MOSFET precisa de nível baixo para conduzir.

    GPIO5 alto -> Q2 conduz -> gate ~0,1 V -> Vgs ~ -3,2 V -> Q1 conduz
    GPIO5 baixo/Hi-Z -> R8 segura a base em 0 -> Q2 corta -> R4 puxa o
    gate a +3V3 -> Vgs = 0 -> Q1 corta

  O estado seguro (periféricos DESLIGADOS) é o que vale com o pino
  flutuando. Isso importa: durante o deep sleep quem segura o nível é
  gpio_hold_en(), e o R8 é a rede de segurança se o hold falhar.

  Ficam em +3V3_SW: MPU6050 (VDD e VLOGIC), os pull-ups R2/R3 do I2C, o
  topo do divisor do NTC (R1) e o desacoplamento C4 desse rail.

Conectividade por rótulo global: cada pino recebe um toco e um rótulo. O ERC
valida por nome de net, não por geometria — o que torna a geração robusta e o
resultado conferível.

Rodar:  python3 hardware/gen_schematic.py
"""

import os
import pathlib
import sys
import uuid as _uuid

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from sexpr import parse, dump, head, find, find1, sym, st  # noqa: E402

KLIB = pathlib.Path("/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols")

# O projeto KiCad é versionado por diretório: cada versão é autocontida, com
# seu .kicad_sch, .kicad_pcb, .kicad_pro e derivados. O ESQUEMÁTICO é idêntico
# entre versões — o que muda de uma para outra é a placa (contorno, placement,
# roteamento). Gerar o esquemático em cada uma custa nada e evita que uma
# versão dependa de arquivo que mora na outra.
VERSAO = os.environ.get("KAELIX_PCB", "v1")
OUT = pathlib.Path(__file__).resolve().parent / "pcb" / VERSAO
OUT.mkdir(parents=True, exist_ok=True)
ROOT_UUID = "b7c1e2a0-0000-4000-8000-000000000000"
PROJ = "kaelix"

_n = [0]
def uid():
    _n[0] += 1
    return str(_uuid.UUID(int=0xC0FFEE00 + _n[0]))


# =====================================================================
# Biblioteca de símbolos
# =====================================================================
_cache = {}
def lib(name):
    if name not in _cache:
        _cache[name] = {s[1][1]: s for s in find(parse((KLIB / f"{name}.kicad_sym").read_text())[0], "symbol")}
    return _cache[name]


def _pinos(defn, nome_base):
    pins = []
    for sub in defn:
        if not (isinstance(sub, list) and head(sub) == "symbol"):
            continue
        for p in find(sub, "pin"):
            at = find1(p, "at")
            pins.append({
                "num": find1(p, "number")[1][1],
                "name": find1(p, "name")[1][1],
                "x": float(at[1][1]), "y": float(at[2][1]),
                "ang": float(at[3][1]) if len(at) > 3 else 0.0,
            })
    return pins


def resolve(libname, symname):
    """Devolve (definição achatada, lista de pinos). `extends` é resolvido."""
    if libname == "kaelix" and symname == "HT7333":
        return simbolo_ht7333()
    table = lib(libname)
    s = table[symname]
    ext = find1(s, "extends")

    # Sem `extends` a definição da biblioteca é copiada VERBATIM. Reconstruí-la
    # a partir de uma lista de elementos "que interessam" era a origem do
    # warning `lib_symbol_mismatch` do ERC: o PWR_FLAG traz (power),
    # (in_pos_files), (duplicate_pin_numbers_are_jumpers) e (embedded_fonts),
    # e todos caíam fora. O ERC compara a cópia embutida no .kicad_sch com a
    # da biblioteca elemento a elemento — omitir qualquer um é divergir.
    if ext is None:
        defn = [sym("symbol"), st(f"{libname}:{symname}")] + \
               [e for e in s[2:] if isinstance(e, list)]
        return defn, _pinos(defn, symname)

    base = table[ext[1][1]]
    body = [e for e in base if isinstance(e, list) and head(e) == "symbol"]
    props = [e for e in s if isinstance(e, list) and head(e) == "property"]
    keep = [e for e in base if isinstance(e, list)
            and head(e) in ("pin_numbers", "pin_names", "exclude_from_sim", "in_bom",
                            "on_board", "power", "in_pos_files",
                            "duplicate_pin_numbers_are_jumpers", "embedded_fonts")]
    # sub-símbolos herdam o nome do PAI; renomeia para o filho
    renamed = []
    for sub in body:
        sub = [x for x in sub]
        sub[1] = st(sub[1][1].replace(base[1][1], symname, 1))
        renamed.append(sub)
    defn = [sym("symbol"), st(f"{libname}:{symname}")] + keep + props + renamed
    pins = []
    for sub in renamed:
        for p in find(sub, "pin"):
            at = find1(p, "at")
            pins.append({
                "num": find1(p, "number")[1][1],
                "name": find1(p, "name")[1][1],
                "x": float(at[1][1]), "y": float(at[2][1]),
                "ang": float(at[3][1]) if len(at) > 3 else 0.0,
            })
    return defn, pins


# ---------------------------------------------------------------------
# Símbolo próprio: HT7333
# ---------------------------------------------------------------------
# A biblioteca do KiCad não traz o HT7333. Emprestar a identidade de outro
# LDO (o LD1117, por exemplo, consome mA em repouso contra os ~8 µA do
# HT7333) falsearia a BOM exatamente no componente de que depende o
# orçamento de energia. Símbolo declarado aqui, com a numeração de pino
# marcada como PENDENTE — SOT-89-3 varia por fabricante.
def simbolo_ht7333():
    def pino(nome, num, tipo, x, y, ang):
        return [sym("pin"), sym(tipo), sym("line"),
                [sym("at"), sym(str(x)), sym(str(y)), sym(str(ang))],
                [sym("length"), sym("2.54")],
                [sym("name"), st(nome), [sym("effects"), [sym("font"),
                    [sym("size"), sym("1.27"), sym("1.27")]]]],
                [sym("number"), st(num), [sym("effects"), [sym("font"),
                    [sym("size"), sym("1.27"), sym("1.27")]]]]]
    corpo = [sym("symbol"), st("HT7333_0_1"),
             [sym("rectangle"),
              [sym("start"), sym("-5.08"), sym("2.54")],
              [sym("end"), sym("5.08"), sym("-5.08")],
              [sym("stroke"), [sym("width"), sym("0.254")], [sym("type"), sym("default")]],
              [sym("fill"), [sym("type"), sym("background")]]]]
    pinos = [sym("symbol"), st("HT7333_1_1"),
             pino("VIN", "1", "power_in", -7.62, 0, 0),
             pino("GND", "2", "power_in", 0, -7.62, 90),
             pino("VOUT", "3", "power_out", 7.62, 0, 180)]
    defn = [sym("symbol"), st("kaelix:HT7333"),
            [sym("pin_names"), [sym("offset"), sym("0.254")]],
            [sym("exclude_from_sim"), sym("no")],
            [sym("in_bom"), sym("yes")], [sym("on_board"), sym("yes")],
            corpo, pinos]
    pins = [{"num": "1", "name": "VIN", "x": -7.62, "y": 0.0, "ang": 0.0},
            {"num": "2", "name": "GND", "x": 0.0, "y": -7.62, "ang": 90.0},
            {"num": "3", "name": "VOUT", "x": 7.62, "y": 0.0, "ang": 180.0}]
    return defn, pins

# =====================================================================
# Netlist — fonte da verdade
# =====================================================================
# (ref, lib, símbolo, footprint, valor, x, y, {pino: net})
NC = "~NC~"

COMPONENTES = [
    # WROOM-1U e não -1: o courtyard do -1 mede 48 x 41,2 mm por causa da zona de
    # exclusão da antena impressa, contra 19,5 x 20,1 mm do -1U. Num disco de 40 mm
    # a exclusão do -1 é inviável — e a antena impressa é inútil dentro de um
    # invólucro preso por ímã a uma carcaça metálica. Wi-Fi/BT não são usados.
    # A KiCad não traz símbolo do -1U; a pinagem é idêntica à do -1.
    ("U1", "RF_Module", "ESP32-S3-WROOM-1", "RF_Module:ESP32-S3-WROOM-1U",
     "ESP32-S3-WROOM-1U-N16R8", 160, 110, {
        "1": "GND", "40": "GND", "41": "GND", "2": "+3V3",
        "3": "EN", "27": "IO0",
        "6": "VBAT_SENSE",
        "4": "NTC_SENSE", "5": "PERIPH_EN",
        "12": "SDA", "17": "SCL",
        "18": "LORA_NSS", "19": "SPI_MOSI", "20": "SPI_SCK", "21": "SPI_MISO",
        "22": "LORA_DIO0", "23": "LORA_RST",
        "36": "UART_RX", "37": "UART_TX",
        **{p: NC for p in ("7", "8", "9", "10", "11", "13", "14", "15", "16",
                           "24", "25", "26", "28", "29", "30", "31", "32", "33",
                           "34", "35", "38", "39")}}),

    ("U2", "Sensor_Motion", "MPU-6050", "Sensor_Motion:InvenSense_QFN-24_4x4mm_P0.5mm",
     "MPU-6050", 60, 110, {
        "8": "+3V3_SW", "13": "+3V3_SW",
        "18": "GND", "9": "GND",
        "1": "GND", "11": "GND",
        "23": "SCL", "24": "SDA",
        "10": "MPU_REGOUT", "20": "MPU_CPOUT",
        **{p: NC for p in ("2", "3", "4", "5", "6", "7", "12", "14", "15", "16",
                           "17", "19", "21", "22")}}),

    ("U3", "RF_Module", "Ai-Thinker-Ra-02", "RF_Module:Ai-Thinker-Ra-01-LoRa",
     "Ai-Thinker Ra-02 (SX1278)", 265, 110, {
        "1": "GND", "2": "GND", "9": "GND", "16": "GND",
        "3": "+3V3", "4": "LORA_RST", "5": "LORA_DIO0",
        "12": "SPI_SCK", "13": "SPI_MISO", "14": "SPI_MOSI", "15": "LORA_NSS",
        **{p: NC for p in ("6", "7", "8", "10", "11")}}),

]

# (ref, símbolo, footprint, valor, x, y, net_pino1, net_pino2)
PASSIVOS = [
    ("R1", "R", "Resistor_SMD:R_0805_2012Metric", "10k", 40, 165, "+3V3_SW", "NTC_SENSE"),
    ("RT1", "Thermistor_NTC", "Resistor_SMD:R_0805_2012Metric", "NTC 10k B3950",
     40, 195, "NTC_SENSE", "GND"),
    ("R2", "R", "Resistor_SMD:R_0805_2012Metric", "4k7", 100, 60, "+3V3_SW", "SDA"),
    ("R3", "R", "Resistor_SMD:R_0805_2012Metric", "4k7", 120, 60, "+3V3_SW", "SCL"),
    ("R6", "R", "Resistor_SMD:R_0805_2012Metric", "10k", 200, 60, "+3V3", "EN"),
    ("R7", "R", "Resistor_SMD:R_0805_2012Metric", "10k", 220, 60, "+3V3", "IO0"),
    # --- rede do load switch (ver bloco no cabeçalho) ---
    # R4 puxa o gate a +3V3: com Q2 cortado, Vgs = 0 e Q1 fica ABERTO.
    # 100k custa 33 µA só durante os 3 s de fase ativa (0,1 mA*s por ciclo).
    ("R4", "R", "Resistor_SMD:R_0805_2012Metric", "100k", 140, 30, "+3V3", "PERIPH_GATE"),
    # R5 limita a base de Q2: (3,3 - 0,7)/10k = 260 µA, com folga de ganho
    # de sobra para os ~4 mA de coletor que R4 impõe.
    ("R5", "R", "Resistor_SMD:R_0805_2012Metric", "10k", 160, 30, "PERIPH_EN", "PERIPH_BASE"),
    # R8 define o estado com o GPIO em Hi-Z: base em 0 V -> periféricos
    # desligados. É o que protege o orçamento de energia se gpio_hold_en()
    # falhar no deep sleep.
    ("R8", "R", "Resistor_SMD:R_0805_2012Metric", "100k", 180, 30, "PERIPH_BASE", "GND"),
    ("C1", "C", "Capacitor_SMD:C_0805_2012Metric", "100n", 240, 60, "EN", "GND"),
    ("C2", "C", "Capacitor_SMD:C_0805_2012Metric", "100n", 200, 200, "+3V3", "GND"),
    ("C3", "C", "Capacitor_SMD:C_0805_2012Metric", "10u", 220, 200, "+3V3", "GND"),
    ("C4", "C", "Capacitor_SMD:C_0805_2012Metric", "100n", 20, 110, "+3V3_SW", "GND"),
    ("C5", "C", "Capacitor_SMD:C_0805_2012Metric", "100n", 20, 140, "MPU_REGOUT", "GND"),
    ("C6", "C", "Capacitor_SMD:C_0805_2012Metric", "2n2", 20, 170, "MPU_CPOUT", "GND"),
    ("C7", "C", "Capacitor_SMD:C_0805_2012Metric", "100n", 300, 200, "+3V3", "GND"),
    ("C8", "C", "Capacitor_SMD:C_0805_2012Metric", "10u", 320, 200, "+3V3", "GND"),
    ("C9", "C", "Capacitor_SMD:C_0805_2012Metric", "1u", 300, 60, "VBAT", "GND"),
    ("C10", "C", "Capacitor_SMD:C_0805_2012Metric", "1u", 320, 60, "+3V3", "GND"),

    # --- medição da tensão da bateria -------------------------------------
    # REQ-SEG-29 (reduzir a potência de TX abaixo de um limiar), REQ-SEG-53
    # (telemetria que transforma FM-26 em inclinação de descarga visível) e o
    # heartbeat do estado QUARENTENA dependem deste nó. Ele não existia: a net
    # VBAT tocava só o conector, o capacitor de entrada e o regulador.
    #
    # 1M/1M e não 100k/100k: o divisor fica ligado o tempo todo (a bateria é
    # anterior ao load switch e não pode ser cortada), então a corrente dele
    # entra inteira no orçamento. 3,7 V / 2 M = 1,85 µA, contra 18,5 µA com
    # 100k — 0,6% do orçamento contra 6%. O preço é impedância de fonte de
    # 500 k, alta demais para o sample-and-hold do ADC do ESP32-S3; é o C11
    # que paga esse preço, servindo de reservatório de carga na amostragem.
    #
    # Faixa: 4,2 V (cheia) -> 2,10 V no nó; 3,0 V (vazia) -> 1,50 V. Dentro
    # da janela útil do ADC nos dois extremos, sem atenuação no limite.
    ("R9",  "R", "Resistor_SMD:R_0805_2012Metric", "1M", 360, 30, "VBAT", "VBAT_SENSE"),
    ("R10", "R", "Resistor_SMD:R_0805_2012Metric", "1M", 360, 90, "VBAT_SENSE", "GND"),
    ("C11", "C", "Capacitor_SMD:C_0805_2012Metric", "100n", 400, 90, "VBAT_SENSE", "GND"),

    # --- filtro do nó do ADC do NTC ---------------------------------------
    # FM-08 raciocina sobre "a constante de tempo do nó (capacitância de
    # filtro x 10 k)" — o texto pressupunha um capacitor que não existia.
    # Sem ele o ADC amostra um nó cuja impedância vai de 5 k a 25 °C para
    # 9,8 k a -40 °C, e a injeção de carga do sample-and-hold vira erro de
    # leitura. Constante de tempo: 100 n x 9,8 k = 1 ms no pior caso, folgada
    # dentro dos 100 ms de PERIPHERAL_SETTLE_MS.
    ("C12", "C", "Capacitor_SMD:C_0805_2012Metric", "100n", 60, 195, "NTC_SENSE", "GND"),
]

# Regulador e conectores
EXTRAS = [
    # PENDENTE: numeração de pino do HT7333 em SOT-89-3 varia por fabricante —
    # conferir contra a folha de dados antes de fabricar.
    ("U4", "kaelix", "HT7333", "Package_TO_SOT_SMD:SOT-89-3",
     "HT7333", 340, 110, {"1": "VBAT", "2": "GND", "3": "+3V3"}),
    # SI2301: P-MOSFET de nível lógico. Vgs(th) típico -0,9 V, Rds(on)
    # ~50 mohm a Vgs = -2,5 V -> 3,9 mA do MPU6050 caem 0,2 mV no canal.
    # Um MOSFET de nível padrão (Vgs(th) -2 a -4 V) não fecharia em 3,3 V.
    ("Q1", "Transistor_FET", "Q_PMOS_GSD", "Package_TO_SOT_SMD:SOT-23",
     "SI2301CDS", 140, 60, {"1": "PERIPH_GATE", "2": "+3V3", "3": "+3V3_SW"}),
    # BC847B em SOT-23 no lugar do BC337 em TO-92: a placa é um disco de
    # 40 mm montado dos dois lados; não há espaço para through-hole.
    ("Q2", "Transistor_BJT", "Q_NPN_BEC", "Package_TO_SOT_SMD:SOT-23",
     "BC847B", 180, 60, {"1": "PERIPH_BASE", "2": "GND", "3": "PERIPH_GATE"}),

    # Proteção de polaridade invertida. DRENO na bateria e FONTE na carga,
    # não o contrário: é a orientação que põe o diodo de corpo CONTRA a
    # corrente reversa. Com a bateria certa, o diodo conduz primeiro, a fonte
    # sobe, Vgs fica em ~-3,1 V e o canal fecha com ~60 mohm (8 mV nos 130 mA
    # de pico da TX). Com a bateria invertida, o diodo fica reversamente
    # polarizado e Vgs = 0: nada passa.
    #
    # Gate direto em GND: |Vgs| = 3,7 V no pior caso, contra os +/-8 V de
    # Vgs(max) do SI2301 — não precisa de zener de proteção de gate.
    ("Q3", "Transistor_FET", "Q_PMOS_GSD", "Package_TO_SOT_SMD:SOT-23",
     "SI2301CDS", 380, 20, {"1": "GND", "2": "VBAT", "3": "VBAT_RAW"}),

    ("J1", "Connector_Generic", "Conn_01x02", "Connector_JST:JST_PH_S2B-PH-SM4-TB_1x02-1MP_P2.00mm_Horizontal",
     "LiPo 3,7V", 380, 60, {"1": "VBAT_RAW", "2": "GND"}),
    ("J2", "Connector_Generic", "Conn_01x06", "Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical",
     "UART/BOOT", 380, 160, {"1": "GND", "2": "+3V3", "3": "UART_TX",
                             "4": "UART_RX", "5": "EN", "6": "IO0"}),
]

# =====================================================================
# Carga da bateria — só a partir da v3
# =====================================================================
# Até a v2 a placa não tinha como carregar a célula: nenhum CI carregador,
# nenhum conector de entrada. O invólucro trazia o furo de USB-C e os
# relatórios falavam em "recarga por USB-C", mas a netlist não. v1 e v2 ficam
# como estão — a v2 é revisão mecânica por regra (pcb/README.md), e circuito
# novo em versão velha tornaria impossível atribuir diferença medida.
#
# BQ21040 e não TP4056/MCP73831: é o único dos três com monitor de
# temperatura da CÉLULA pronto para NTC de 10 k. O pino TS polariza o NTC com
# 50 µA e suspende a carga com V_TS < 275 mV (45 °C) ou V_TS > 1250 mV (0 °C).
# O limite de 45 °C que a análise térmica usa deixa de ser recomendação da
# folha de dados da célula e passa a ser imposto pelo hardware.
#
# O NTC do TS NÃO é o RT1. Os limiares do BQ21040 estão calibrados para
# β ≈ 3370 (103AT-2, folha de dados §9.2); o B3950 do RT1 cortaria perto de
# 39 °C. RT2 é dedicado, na face de cima, sob a célula e longe do U5 — lê a
# placa, que fica ACIMA da célula durante a carga, então o corte vem cedo,
# nunca tarde (hardware/termica_carga.py).
#
# Corrente de carga: 200 mA, R_ISET = K_ISET / I = 540 / 0,2 = 2,7 k. O
# carregador é linear e dissipa I·(V_USB − V_bat) DENTRO do invólucro; o
# modelo térmico dá 15 K/W da potência à placa. Com 200 mA a placa fica em
# 36,7 °C na bancada e entre 41,1 e 44,3 °C no motor a 90 °C — abaixo do corte
# de 45 °C, mas no motor quente com 0,7 a 3,9 K de folga. Com 250 mA o TS já
# pode cortar no motor quente; com 500 mA corta nos três cenários. Carga
# completa em ~12 h.
#
# Saída do carregador em VBAT, DEPOIS do Q3 de polaridade. Em VBAT_RAW, uma
# célula invertida conduziria pelo diodo de ESD do pino OUT mesmo sem USB, e
# a proteção deixaria de existir. Em VBAT o risco que sobra exige falha dupla
# (célula invertida E USB ligado): o carregador sobe VBAT, liga o canal do
# Q3 e injeta a corrente de pré-carga na célula invertida até VBAT cair
# abaixo do Vgs(th). O conector JST-PH é polarizado; o risco fica declarado.
#
# CHG_N vai ao IO7, GPIO de RTC: o firmware sabe se está carregando e pode
# até acordar do deep sleep na borda. Sem pull-up externo — o dreno aberto
# não consome nada fora da carga; o pull-up interno é ligado só na leitura.
#
# USB-C só de energia: CC1 e CC2 com 5,1 k para GND (Rd) são o que faz uma
# fonte C-para-C entregar VBUS. Sem eles, só cabo A-para-C carregaria.
COM_CARGA = VERSAO not in ("v1", "v2")
if COM_CARGA:
    _u1 = COMPONENTES[0]
    assert _u1[0] == "U1" and _u1[7]["7"] == NC
    COMPONENTES[0] = _u1[:7] + ({**_u1[7], "7": "CHG_N"},)
    COMPONENTES.append(
        ("U5", "Battery_Management", "BQ21040DBV", "Package_TO_SOT_SMD:SOT-23-6",
         "BQ21040DBV", 120, 280, {
            "1": "CHG_TS", "2": "VBAT", "3": "CHG_N", "4": "CHG_ISET",
            "5": "GND", "6": "VBUS"}))
    PASSIVOS += [
        ("R11", "R", "Resistor_SMD:R_0805_2012Metric", "5k1", 40, 250, "CC1", "GND"),
        ("R12", "R", "Resistor_SMD:R_0805_2012Metric", "5k1", 40, 280, "CC2", "GND"),
        ("R13", "R", "Resistor_SMD:R_0805_2012Metric", "2k7", 160, 250, "CHG_ISET", "GND"),
        ("RT2", "Thermistor_NTC", "Resistor_SMD:R_0805_2012Metric",
         "NTC 10k B3380 (103AT)", 160, 280, "CHG_TS", "GND"),
        # entrada e saída do BQ21040: 1 a 10 µF pela folha de dados
        ("C13", "C", "Capacitor_SMD:C_0805_2012Metric", "1u", 80, 250, "VBUS", "GND"),
        ("C14", "C", "Capacitor_SMD:C_0805_2012Metric", "1u", 200, 280, "VBAT", "GND"),
        # C_TS da folha de dados (0,22 µF típico). Opcional lá; aqui não: o RT2
        # fica sob a célula, a ~25 mm do U5, e o nó de 10 k divide a placa com
        # os surtos de TX do rádio. Um disparo espúrio do TS suspende a carga.
        ("C15", "C", "Capacitor_SMD:C_0805_2012Metric", "220n", 200, 250, "CHG_TS", "GND"),
    ]
    EXTRAS.append(
        ("J3", "Connector", "USB_C_Receptacle_PowerOnly_6P",
         "Connector_USB:USB_C_Receptacle_GCT_USB4125-xx-x_6P_TopMnt_Horizontal",
         "USB-C 5V", 20, 300, {
            "A9": "VBUS", "B9": "VBUS", "A12": "GND", "B12": "GND",
            "A5": "CC1", "B5": "CC2", "SH": "GND"}))

# O ERC exige que toda net de potência tenha um pino de SAÍDA de potência.
# +3V3 vem do VOUT do HT7333, mas +3V3_SW vem do dreno de Q1, que é passivo:
# sem o flag o ERC acusa VDD/VLOGIC do MPU6050 como entrada não alimentada.
# Com carga, VBAT passa a ter saída de potência de verdade (OUT do U5) e o
# flag dela sairia em conflito; VBUS vem do conector, que é passivo.
PWR_FLAGS = [("GND", 175, 40), ("VBAT", 225, 40), ("+3V3_SW", 120, 30)]
if COM_CARGA:
    PWR_FLAGS = [f for f in PWR_FLAGS if f[0] != "VBAT"] + [("VBUS", 60, 250)]


# =====================================================================
# Emissão
# =====================================================================
S = []
LIBSYMS = {}


def prop(nome, val, x, y, oculto=True):
    e = [sym("property"), st(nome), st(val), [sym("at"), sym(str(x)), sym(str(y)), sym("0")],
         [sym("effects"), [sym("font"), [sym("size"), sym("1.27"), sym("1.27")]]]]
    if oculto:
        e[-1].append([sym("hide"), sym("yes")])
    return e


GRADE = 1.27

def snap(v):
    return round(v / GRADE) * GRADE


def coloca(ref, libname, symname, fp, valor, x, y, mapa):
    x, y = snap(x), snap(y)
    defn, pins = resolve(libname, symname)
    LIBSYMS[f"{libname}:{symname}"] = defn
    inst = [sym("symbol"), [sym("lib_id"), st(f"{libname}:{symname}")],
            [sym("at"), sym(str(x)), sym(str(y)), sym("0")], [sym("unit"), sym("1")],
            [sym("exclude_from_sim"), sym("no")], [sym("in_bom"), sym("yes")],
            [sym("on_board"), sym("yes")], [sym("dnp"), sym("no")],
            [sym("uuid"), st(uid())],
            prop("Reference", ref, x, snap(y - 12.7), oculto=False),
            prop("Value", valor, x, snap(y + 12.7), oculto=False),
            prop("Footprint", fp, x, y, oculto=True),
            prop("Datasheet", "~", x, y, oculto=True),
            prop("Description", "", x, y, oculto=True)]
    for p in pins:
        inst.append([sym("pin"), st(p["num"]), [sym("uuid"), st(uid())]])
    inst.append([sym("instances"), [sym("project"), st(PROJ),
                 [sym("path"), st(f"/{ROOT_UUID}"),
                  [sym("reference"), st(ref)], [sym("unit"), sym("1")]]]])
    S.append(inst)

    for p in pins:
        net = mapa.get(p["num"])
        if net is None:
            continue
        px, py = x + p["x"], y - p["y"]
        a = int(p["ang"]) % 360
        dx, dy = {0: (-1, 0), 180: (1, 0), 90: (0, 1), 270: (0, -1)}[a]
        ex, ey = px + dx * 3.81, py + dy * 3.81
        if net == NC:
            S.append([sym("no_connect"), [sym("at"), sym(f"{px:g}"), sym(f"{py:g}")],
                      [sym("uuid"), st(uid())]])
            continue
        S.append([sym("wire"), [sym("pts"), [sym("xy"), sym(f"{px:g}"), sym(f"{py:g}")],
                  [sym("xy"), sym(f"{ex:g}"), sym(f"{ey:g}")]],
                  [sym("stroke"), [sym("width"), sym("0")], [sym("type"), sym("default")]],
                  [sym("uuid"), st(uid())]])
        lang = {(-1, 0): 180, (1, 0): 0, (0, 1): 270, (0, -1): 90}[(dx, dy)]
        S.append([sym("global_label"), st(net), [sym("shape"), sym("passive")],
                  [sym("at"), sym(f"{ex:g}"), sym(f"{ey:g}"), sym(str(lang))],
                  [sym("effects"), [sym("font"), [sym("size"), sym("1.27"), sym("1.27")]],
                   [sym("justify"), sym("left")]],
                  [sym("uuid"), st(uid())]])


for ref, lb, sn, fp, val, x, y, mapa in COMPONENTES:
    coloca(ref, lb, sn, fp, val, x, y, mapa)
for ref, sn, fp, val, x, y, n1, n2 in PASSIVOS:
    coloca(ref, "Device", sn, fp, val, x, y, {"1": n1, "2": n2})
for ref, lb, sn, fp, val, x, y, mapa in EXTRAS:
    coloca(ref, lb, sn, fp, val, x, y, mapa)
for i, (net, x, y) in enumerate(PWR_FLAGS, 1):
    coloca(f"#FLG{i}", "power", "PWR_FLAG", "", "PWR_FLAG", x, y, {"1": net})

doc = [sym("kicad_sch"), [sym("version"), sym("20231120")], [sym("generator"), st("kaelix_gen")],
       [sym("uuid"), st(ROOT_UUID)], [sym("paper"), st("A2")],
       [sym("lib_symbols")] + list(LIBSYMS.values())] + S + \
      [[sym("sheet_instances"), [sym("path"), st("/"), [sym("page"), st("1")]]]]

(OUT / "kaelix.kicad_sch").write_text(dump(doc) + "\n", encoding="utf-8")

# A biblioteca do símbolo próprio também sai daqui. Era o último arquivo
# derivado mantido à mão: se `simbolo_ht7333()` mudasse e o .kicad_sym não,
# o ERC acusaria lib_symbol_mismatch — melhor não haver o que divergir.
_defn, _pins = simbolo_ht7333()
_lib = [sym("kicad_symbol_lib"), [sym("version"), sym("20231120")],
        [sym("generator"), st("kaelix_gen")],
        [sym("symbol"), st("HT7333")] + [e for e in _defn[2:] if isinstance(e, list)]]
(OUT / "kaelix.kicad_sym").write_text(dump(_lib) + "\n", encoding="utf-8")

# A tabela de bibliotecas mora ao lado do projeto e é o que faz o KiCad achar
# o símbolo próprio. Com o projeto versionado por diretório ela precisa existir
# em cada versão — gerada, não copiada, para não haver duas verdades.
(OUT / "sym-lib-table").write_text(
    '(sym_lib_table\n'
    '  (version 7)\n'
    '  (lib (name "kaelix")(type "KiCad")(uri "${KIPRJMOD}/kaelix.kicad_sym")'
    '(options "")(descr "Símbolos próprios do Kaelix"))\n'
    ')\n', encoding="utf-8")
# Restrições de fabricação. Furo mínimo de 0,2 mm NÃO é folga para o DRC
# passar: o footprint do WROOM-1U traz 12 vias térmicos de 0,2 mm sob o módulo.
# Manter 0,3 mm exigiria editar o footprint; aceitar 0,2 mm exige casa que faça
# furo de 0,2 mm, processo de custo extra. A decisão fica registrada aqui.
#
# A folga da netclass é 0,15 mm, e não os 0,2 mm herdados: o MPU6050 é um
# QFN-24 de 0,5 mm de passo e, com 0,2 mm, o obstáculo inflado de um pad
# cobre a linha de centro do pad vizinho e nenhum escape fecha. A derivação
# está em hardware/router.py. 0,15 mm de folga com traço de 0,2 mm está
# dentro do processo padrão de duas camadas.
import json as _json
_regras = {"min_through_hole_diameter": 0.2,
           "min_hole_clearance": 0.25,
           "min_hole_to_hole": 0.25,
           "min_clearance": 0.15,
           "min_track_width": 0.15,
           "min_via_diameter": 0.4}
_classe = {"name": "Default", "clearance": 0.15, "track_width": 0.2,
           "via_diameter": 0.6, "via_drill": 0.3,
           "microvia_diameter": 0.3, "microvia_drill": 0.1,
           "diff_pair_gap": 0.25, "diff_pair_width": 0.2, "diff_pair_via_gap": 0.25,
           "line_style": 0, "pcb_color": "rgba(0, 0, 0, 0.000)",
           "schematic_color": "rgba(0, 0, 0, 0.000)",
           "wire_width": 6, "bus_width": 12}
_pro = {"board": {"design_settings": {"rules": _regras,
                                      "track_widths": [0.0, 0.2],
                                      "via_dimensions": [{"diameter": 0.0, "drill": 0.0},
                                                         {"diameter": 0.6, "drill": 0.3}]}},
        "net_settings": {"classes": [_classe], "meta": {"version": 3}},
        "schematic": {},
        "meta": {"filename": "kaelix.kicad_pro", "version": 1}}
(OUT / "kaelix.kicad_pro").write_text(_json.dumps(_pro, indent=2) + "\n")
print(f"gerado: {OUT}/kaelix.kicad_sch  ({len(S)} elementos, {len(LIBSYMS)} símbolos)")
