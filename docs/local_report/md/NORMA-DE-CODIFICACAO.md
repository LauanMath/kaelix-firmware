# Norma de codificação do Kaelix (NC-KAELIX)

**Versão:** 1.0 · **Escopo:** `lib/`, `src/`, `test/` · **Linguagem:** C++17 (`-std=gnu++17`)
**Documentos irmãos:** [`ARQUITETURA-SOFTWARE.md`](ARQUITETURA-SOFTWARE.md) (camadas, memória, erro, paridade) · [`ANALISE-DE-FALHAS.md`](ANALISE-DE-FALHAS.md) (FMEA, estado seguro, watchdog)

---

## 0. Por que esta norma tem 41 regras e não 300

MISRA C++:2008 tem 228 regras. JSF++ tem 221. Nenhuma delas foi escrita para um
dispositivo de 500 linhas de firmware feito por uma pessoa. Adotar a norma
inteira produziria dois resultados previsíveis: a maior parte das regras não
teria como ser verificada, e a equipe aprenderia que a norma é decoração —
momento em que ela para de proteger até nas regras que importavam.

**A seleção é o trabalho de engenharia deste documento.** Cada regra abaixo
entrou porque fecha um modo de falha que a FMEA levantou, ou porque torna
verificável uma propriedade que a arquitetura afirma. As que não entraram não
foram esquecidas — foram descartadas por não pagarem o próprio custo aqui.

O critério de admissão foi um só:

> Uma regra entra se for possível dizer **qual falha do Kaelix ela impede** e
> **como sua violação é detectada** (compilador, análise estática, teste ou
> revisão). Regra sem falha associada é estilo; regra sem detecção é intenção.

### O que o Kaelix está protegendo

Todas as 41 regras servem a um único invariante de produto:

> **O dispositivo nunca afirma o que não mediu.**

Um Kaelix silencioso é um buraco visível na sequência de `boot_count`, e o
gateway o detecta. Um Kaelix que transmite `NORMAL` a partir de um buffer de
zeros de um acelerômetro que não existe é indetectável, induz confiança e
destrói o valor de todo o sistema. É por isso que várias regras aqui parecem
paranoicas com sentinelas, NaN e vereditos: elas estão todas defendendo o mesmo
flanco.

### Como ler uma regra

```
NC-<ÁREA>-<NN>  Enunciado — a forma imperativa, verificável.
  Por quê:      uma linha. Se não couber em uma linha, a regra está errada.
  Base:         MISRA C++ / JSF++ / Power of Ten correspondente.
  CERTO/ERRADO: código real do Kaelix.
```

Os exemplos marcados **(histórico)** são código que existiu neste repositório e
foi substituído; a razão da substituição está registrada nos comentários do
arquivo citado. Eles não são hipóteses didáticas — são os defeitos reais que
motivaram a regra.

**Sobre as citações normativas.** Os números referem-se a MISRA C++:2008 e a
JSF++ (Lockheed Martin, 2005). Onde a correspondência é temática e não literal,
a citação vem pelo assunto, não pelo número. "Power of Ten" refere-se às dez
regras de Holzmann (JPL/NASA, 2006), usadas aqui porque são as mais próximas do
regime deste dispositivo: laços limitados, sem heap, sem recursão, retorno
sempre verificado.

### Áreas

| Área | Assunto | Regras |
|---|---|---|
| `NC-ARQ` | Dependência entre camadas | 4 |
| `NC-MEM` | Política de memória | 3 |
| `NC-FLX` | Fluxo de controle: laços, recursão, cotas | 4 |
| `NC-ERR` | Tratamento e propagação de erro | 5 |
| `NC-CTR` | Validação de parâmetro e contratos | 3 |
| `NC-INI` | Inicialização de variáveis | 2 |
| `NC-CNV` | Tipos, conversões e casts | 3 |
| `NC-FPU` | Ponto flutuante | 4 |
| `NC-CST` | const-correctness e constantes | 2 |
| `NC-ESC` | Escopo e visibilidade | 2 |
| `NC-NOM` | Nomes | 3 |
| `NC-HDR` | Cabeçalhos e inclusão | 2 |
| `NC-COM` | Comentários | 2 |
| `NC-BLD` | Build e verificação | 2 |
| | **Total** | **41** |

---

## 1. NC-ARQ — Dependência entre camadas

A regra de dependência é a única regra desta norma que, sozinha, decide se o
projeto continua testável. Todas as outras podem ser violadas em um arquivo
sem contaminar o resto; esta não.

Recapitulando `ARQUITETURA-SOFTWARE.md §1`: **L0** contrato (`lib/kaelix_status/`),
**L1** matemática pura (`lib/*/`), **L2** drivers (`src/sensors|ml|comms|power/`),
**L3** orquestração (`src/main.cpp`). `L(n)` depende de `L(n-1)` e abaixo,
nunca do contrário.

### NC-ARQ-01 — `lib/` nunca inclui nada de `src/`. Sem exceção.

**Por quê:** é essa proibição — e só ela — que mantém o ambiente `native` capaz
de compilar e testar toda a matemática do firmware sem hardware.
**Base:** JSF++ AV-33 (dependências de inclusão); DO-178C, independência de verificação.
**Detecção:** `pio test -e native` quebra na compilação. Adicionalmente,
`grep -rn 'Arduino\.h\|esp_\|driver/\|RadioLib' lib/` deve não retornar nada.

```cpp
// CERTO — lib/signal_processing/signal_processing.h
#include <cstddef>
#include "kaelix_status.h"      // L0, a única dependência de projeto permitida a L1

// ERRADO — L1 alcançando o SDK: a suíte native deixa de compilar e a
// matemática deixa de ser verificável sem um ESP32 na mesa.
#include <Arduino.h>
```

### NC-ARQ-02 — Camadas irmãs não se enxergam. Tipo compartilhado por dois módulos desce para L0/L1. `#include "../outra_area/x.h"` é proibido.

**Por quê:** dois módulos de L2 que se incluem acoplam decisões independentes —
o formato de fio passa a depender do módulo de inferência.
**Base:** JSF++ AV-3 (acoplamento); Parnas, ocultação de informação.
**Detecção:** `grep -rn '#include "\.\./' src/*/` — só `../machine_state.h` é
tolerado hoje, e por pouco tempo (ver DEV-013).

```cpp
// CERTO — src/machine_state.h, na raiz de src/
// `ml` PRODUZ MachineState, `comms` o coloca no ar, e nenhum dos dois inclui
// o outro. Antes desta separação, src/comms/lora.h incluía ../ml/model.h só
// para alcançar um enum — e o layout do pacote LoRa passava a depender do
// módulo de ML.
namespace kaelix { enum class MachineState : uint8_t { Normal, Anomalous, Unknown }; }

// ERRADO (atual, registrado como DEV-013) — src/ml/model.h
#include "../sensors/vibration.h"   // L2 → L2, atravessando fronteira de área
// `VibrationFeatures` é produzido pela matemática de L1 e consumido por dois
// módulos de L2. O lugar dele é L1, ao lado de lib/signal_processing.
```

### NC-ARQ-03 — Só L2 e L3 incluem `<Arduino.h>`, `esp_*.h`, `driver/*.h` ou bibliotecas de terceiros.

**Por quê:** a fronteira entre "matemática que posso provar no host" e "código
que só roda com hardware" precisa ser um fato da build, não uma intenção.
**Base:** MISRA C++ 18-0-x (uso restrito de biblioteca); JSF++ AV-16 (portabilidade).

```cpp
// CERTO — lib/thermistor/thermistor.cpp converte NTC → °C com <cmath> e nada mais.
//         src/sensors/temperature.cpp é quem chama analogReadMilliVolts().
//         A conversão é testada no host; a leitura do ADC não precisa ser.

// ERRADO — a equação B implementada dentro do driver, chamando analogRead()
//          na mesma função. A matemática passa a exigir um NTC físico para
//          ser verificada, e a paridade com features.py deixa de ser aferível.
```

### NC-ARQ-04 — Só L3 decide o que o dispositivo faz com um erro. L1 e L2 relatam.

**Por quê:** política de degradação espalhada por módulos vira comportamento
emergente — ninguém consegue afirmar, na defesa, o que o dispositivo faz quando
o sensor morre.
**Base:** JSF++ AV-115 (informação de erro é testada por quem pode agir); DO-178C, arquitetura de particionamento.

```cpp
// CERTO — src/main.cpp: o único `if` do firmware que decide um veredito.
if (kaelix::is_ok(model) && kaelix::is_ok(vibration)) {
    model = kml::model_infer(features, temperature_c, &state);
}
// Sem features válidas não há inferência: `state` fica Unknown e o pacote
// carrega o porquê no byte `diag`.

// ERRADO (histórico) — main.cpp registrava que vibration_init() falhou e
// seguia para vibration_read_features(), que devolvia features de um buffer
// de zeros. RMS=0, curtose=0, crista=0 é o vetor que o Isolation Forest
// classifica como "máquina sadia". O dispositivo transmitia saúde a partir
// de um acelerômetro morto, com CRC válido.
```

---

## 2. NC-MEM — Política de memória

### NC-MEM-01 — Nenhuma alocação dinâmica. Nem após a inicialização, nem durante: o Kaelix não tem fase de inicialização.

Proibidos em L1, L2 e L3: `new`, `delete`, `malloc`, `free`, `std::vector`,
`std::string`, `std::function` e qualquer container que aloque.
Permitidos: `std::array`, ponteiro cru com tamanho explícito, `constexpr`,
buffers de escopo de arquivo dimensionados em tempo de compilação.

**Por quê:** 144 ciclos por dia × 8 meses ≈ 35 000 pares alocação/liberação no
mesmo heap, sem nenhum recurso para diagnosticar fragmentação numa máquina
parafusada sem ninguém por perto — e uma falha de alocação com `-fno-exceptions`
vira `abort()` → pânico → boot loop a ~40 mA, ou seja, bateria morta em ~2 dias
contra os ~241 de projeto.
**Base:** MISRA C++ 18-4-1; JSF++ AV-206; Power of Ten 3.
**Detecção:** `grep -rn '\bnew\b\|malloc\|std::vector\|std::string' lib/ src/`;
`clang-tidy` com `cppcoreguidelines-no-malloc`.

```cpp
// CERTO — src/comms/lora.cpp
// O construtor do SX1278 exige um Module*, mas NÃO exige que ele venha de new:
// um objeto de duração estática serve. Esta é a diferença entre um desvio
// "imposto pela biblioteca" e uma alocação que ninguém tinha examinado.
Module lora_module(LORA_CS_PIN, LORA_DIO0_PIN, LORA_RST_PIN);
SX1278 radio(&lora_module);

// ERRADO (histórico) — src/comms/lora.cpp
SX1278 radio = new Module(LORA_CS_PIN, LORA_DIO0_PIN, LORA_RST_PIN);
// Um ponteiro nunca conferido, alocado durante a inicialização estática,
// antes de setup() e antes de qualquer log existir. Falha = brick mudo.
```

```cpp
// CERTO — lib/signal_processing/signal_processing.cpp
float s_fft_re[FFT_MAX_N];   // 2 KB em .bss, nunca liberado, nunca fragmentado
float s_fft_im[FFT_MAX_N];

// ERRADO (histórico) — mesma função
std::vector<float> re(n), im(n);   // 4 KB alocados e liberados por ciclo
```

### NC-MEM-02 — Todo buffer é derivado de uma constante de configuração única. Nada é dimensionado por número solto, e a derivação é verificada por `static_assert`.

**Por quê:** um `512` escrito à mão em três módulos é três chances de eles
divergirem, e a divergência aparece como estouro de buffer ou espectro errado,
não como erro de compilação.
**Base:** JSF++ AV-151 (magic numbers); MISRA C++ 5-0-x (consistência dimensional).

```cpp
// CERTO — a cadeia inteira desce de uma constante, com verificação em cada elo.
// lib/signal_processing/signal_processing.h
constexpr size_t VIBRATION_SAMPLES = 512;
constexpr size_t FFT_MAX_N = VIBRATION_SAMPLES;
static_assert((FFT_MAX_N & (FFT_MAX_N - 1)) == 0, "FFT radix-2 exige potência de 2");

// src/sensors/vibration.h
inline constexpr uint16_t VIBRATION_MAX_SAMPLES = static_cast<uint16_t>(FFT_MAX_N);
static_assert(FFT_MAX_N <= UINT16_MAX, "o contador de amostras é uint16_t");

// src/main.cpp
constexpr uint16_t VIBRATION_SAMPLES_PER_CYCLE = static_cast<uint16_t>(ksens::VIBRATION_SAMPLES);
static_assert(VIBRATION_SAMPLES_PER_CYCLE <= ksens::VIBRATION_MAX_SAMPLES,
              "o bloco pedido não cabe no buffer estático de amostras");

// ERRADO — float buf[512]; em vibration.cpp e for (i = 0; i < 512; ++i) em
// main.cpp. Mudar a taxa de amostragem exige lembrar de três lugares.
```

### NC-MEM-03 — Objeto de duração estática com construtor só pode existir no namespace anônimo da própria unidade de tradução, e só pode ser alcançado a partir de `setup()`.

**Por quê:** a ordem de inicialização entre unidades de tradução não é definida;
um objeto estático de uma TU que dependa de outro de outra TU é um defeito que
aparece só depois de um relink.
**Base:** JSF++ AV-217 (ordem de inicialização entre TUs); MISRA C++ 3-3-x.

```cpp
// CERTO — src/comms/lora.cpp, com a justificativa registrada no próprio arquivo:
// ambos têm duração estática, são `static` no escopo anônimo, nenhuma outra
// unidade os toca, e só as funções deste arquivo os alcançam — todas chamadas
// a partir de setup(). A dependência de ordem entre TUs não existe aqui por
// construção, e não por coincidência.

// ERRADO — um objeto estático em um header, ou um estático de lora.cpp cujo
// construtor lesse uma constante inicializada dinamicamente em temperature.cpp.
```

---

## 3. NC-FLX — Fluxo de controle: laços, recursão, cotas

Esta área existe por um motivo de energia, não de elegância: um dispositivo
travado acordado consome ~40 mA e esvazia 2000 mAh em ~2 dias, contra os ~241
dias de projeto. Um laço sem cota é a forma mais barata de matar o produto.

### NC-FLX-01 — Todo laço tem cota superior provável antes de entrar nele.

A cota é (a) uma constante de compilação, (b) um parâmetro já validado contra
uma constante de compilação, ou (c) demonstrável a partir da própria variável de
controle — e, neste último caso, o argumento fica escrito em comentário.

**Por quê:** sem cota não há WCET; sem WCET, o orçamento de 3,0 s de fase ativa
e os 309 µA médios são chute, não engenharia.
**Base:** Power of Ten 2; JSF++ AV-119 e AV-201; DO-178C, análise de tempo de execução.

```cpp
// CERTO (a) — cota constante. src/comms/lora.cpp
constexpr uint8_t LORA_SLEEP_MAX_ATTEMPTS = 3;
for (uint8_t attempt = 0U; attempt < LORA_SLEEP_MAX_ATTEMPTS; ++attempt) { ... }
// É um laço com limite constante, não um "tenta até dar certo": cada tentativa
// custa tempo na janela ativa, e um rádio que não responde a três tentativas
// com reset entre elas não vai responder à quarta.

// CERTO (c) — cota demonstrada, com o argumento escrito. lib/signal_processing
// Bit-reversal: o laço externo é limitado por n; o interno por log2(n) — `bit`
// começa em n/2 e é dividido por dois a cada passo, então chega a 0 em no
// máximo log2(n) iterações, e `j & 0` é falso, o que encerra o laço.
for (size_t i = 1U, j = 0U; i < n; ++i) {
    size_t bit = n >> 1U;
    for (; (j & bit) != 0U; bit >>= 1U) { j ^= bit; }
    ...
}
// Borboletas: (n/2)·log2(n), com n <= 512 ⇒ no máximo 2304 borboletas.
```

### NC-FLX-02 — Laço cujo limite venha de barramento, modelo ou pacote tem cota **constante** e um `Status` próprio para quando ela estourar.

**Por quê:** dado externo pode estar corrompido; um limite lido de dado
corrompido não é um limite.
**Base:** Power of Ten 2 e 7; MISRA C++ 0-1-x (código alcançável).

```cpp
// CERTO — lib/isolation_forest/isolation_forest.cpp (REQ-ML-002)
// A cota efetiva é a menor entre a profundidade declarada pela árvore e a
// constante do projeto: uma max_depth corrompida não pode alargar a cota.
int32_t traversal_depth_limit(const IsolationTree& tree) {
    const int32_t declared = static_cast<int32_t>(tree.max_depth);
    if (declared >= 0 && declared < ISOLATION_TREE_MAX_DEPTH) { return declared; }
    return ISOLATION_TREE_MAX_DEPTH;
}
for (int32_t depth = 0; depth <= depth_limit; ++depth) {
    if (node < 0 || node >= static_cast<int32_t>(tree.n_nodes)) {
        return kaelix::Status::ModelMalformed;
    }
    ...
}
return kaelix::Status::ModelDepthExceeded;   // a cota estourou, e isso é dito

// ERRADO (histórico) — mesma função
while (tree.feature[node] != -1) { node = ...; }
// Uma árvore com ciclo (um bit invertido na flash basta) gira para sempre.
// O sintoma em campo é a bateria acabando em dois dias, sem nenhum pacote.
```

### NC-FLX-03 — Recursão proibida, direta e indireta. Sem `goto`, `setjmp`/`longjmp`, `alloca`, ponteiro de função no caminho quente. Função `[[noreturn]]` não termina por caminho nenhum.

**Por quê:** sem recursão o pico de pilha é estático e analisável; um `[[noreturn]]`
que retorna cai num epílogo que o compilador pode ter omitido — execução em
endereço arbitrário.
**Base:** Power of Ten 1 e 9; JSF++ AV-119 (recursão) e AV-189 (`goto`); MISRA C++ 6-6-x, 17-0-5.

```cpp
// CERTO — src/power/sleep.cpp
[[noreturn]] void deep_sleep_now() {
    esp_deep_sleep_start();
    esp_restart();      // se o impossível acontecer, o estado seguro é reiniciar
    for (;;) { }        // e este laço existe para que a função não termine
}                       // por caminho nenhum, nem mesmo o impossível.

// CERTO — a travessia do Isolation Forest é iterativa, e deve continuar sendo.
// Uma árvore percorrida recursivamente com profundidade vinda de dado
// corrompido consome pilha proporcional ao dado.
```

### NC-FLX-04 — Nenhuma função de `lib/` ou `src/*/` alimenta o watchdog, e nunca dentro de um laço. Só `src/main.cpp` alimenta, entre fases.

**Por quê:** alimentar o cão dentro do laço que pode travar é a forma clássica de
neutralizá-lo — o laço trava alimentando. Concentrando a alimentação nas junções
do ciclo, o watchdog mede **progresso**, não atividade de CPU.
**Base:** `ANALISE-DE-FALHAS.md §6.3`; REQ-SEG-32.
**Detecção:** `grep -rn 'wdt_reset\|wdt_feed\|watchdog_feed' lib/ src/` — só pode
aparecer em `src/power/watchdog.cpp` (definição) e `src/main.cpp` (chamada).

```cpp
// CERTO — src/main.cpp, nas junções de fase e em nenhum outro lugar
cycle = feed_watchdog(cycle);   // e o retorno entra no acumulador como qualquer outro

// CERTO — src/comms/lora.cpp: o laço de 3 tentativas de sleep NÃO alimenta o
// watchdog. Se as três tentativas travarem, é exatamente disso que o WDT-1
// precisa saber.

// ERRADO — um esp_task_wdt_reset() dentro do laço de aquisição das 512
// amostras. Um I2C que nunca responde passa a travar com o cão alimentado.
```

---

## 4. NC-ERR — Tratamento e propagação de erro

### NC-ERR-01 — Tudo que pode falhar devolve `kaelix::Status`, nunca `bool`. Um valor de `Status` publicado nunca é reutilizado com outro significado.

**Por quê:** as seis funções que antes devolviam `bool` devolviam todas o mesmo
`false`, e "rádio LoRa não inicializou" pode ser antena solta, SPI mudo, chip
ausente ou frequência recusada — quatro deslocamentos de manutenção diferentes.
**Base:** JSF++ AV-115; `ARQUITETURA-SOFTWARE.md §5`; REQ-SYS-002.

```cpp
// CERTO — src/comms/lora.cpp: o driver traduz o código do RadioLib para o
// vocabulário do projeto, preservando a distinção que o bool colapsava.
case RADIOLIB_ERR_CHIP_NOT_FOUND:      return kaelix::Status::RadioAbsent;
case RADIOLIB_ERR_SPI_WRITE_FAILED:    return kaelix::Status::RadioBusSilent;
case RADIOLIB_ERR_INVALID_FREQUENCY:   return kaelix::Status::RadioConfigRejected;
// RF_ABSENT, SPI_SILENT e RF_CFG_REJ são três respostas diferentes para o
// técnico — e o terceiro nem é defeito de peça, é bug de firmware.

// ERRADO — bool lora_init();
```

O byte `diag` do pacote é decodificado por número no gateway: **acrescentar um
valor a `Status` é escolher a faixa do subsistema e nunca reutilizar um número
já publicado.** A faixa alta identifica o subsistema (`0x1_` vibração, `0x2_`
temperatura, `0x3_` modelo, `0x4_` rádio, `0x5_` plataforma), o que permite
triar em campo sem a tabela completa.

### NC-ERR-02 — Toda função que devolve `Status` é `[[nodiscard]]`, e o retorno é sempre consumido.

**Por quê:** o retorno descartado de `lora_sleep()` custa 900 mA·s por ciclo —
5,5× o orçamento inteiro do dispositivo — e o único sintoma é a bateria durar
45 dias em vez de 241. Ninguém percebe.
**Base:** MISRA C++ 0-1-7; Power of Ten 7; JSF++ AV-115.
**Detecção:** `-Wunused-result` com `-Werror` (ver NC-BLD-01).

```cpp
// CERTO — src/comms/lora.h
[[nodiscard]] kaelix::Status lora_sleep();
// CERTO — src/main.cpp, enter_safe_state()
const Status radio_sleep = kcomms::lora_sleep();
log_phase("rf_sleep", radio_sleep);
status = kaelix::status_first_error(status, radio_sleep);

// ERRADO (histórico) — lora_sleep(); com o retorno no chão.
```

### NC-ERR-03 — Propagação por `KAELIX_CHECK` (primeiro erro encerra a cadeia) ou acumulação por `status_first_error` (primeiro erro vence, o ciclo continua). Nunca por reconstrução ad-hoc.

**Por quê:** o Kaelix não aborta na primeira falha — ele degrada e segue até
conseguir transmitir o diagnóstico. Um erro posterior e derivado não pode
sobrescrever a causa raiz.
**Base:** `ARQUITETURA-SOFTWARE.md §5`; JSF++ AV-115.

```cpp
// CERTO — cadeia que precisa parar: lib/isolation_forest/isolation_forest.cpp
for (int32_t i = 0; i < n_trees; ++i) {
    float path = 0.0f;
    KAELIX_CHECK(isolation_tree_path_length(trees[i], features, n_features, &path));
    total_path += path;
}

// CERTO — ciclo que precisa continuar: src/main.cpp
cycle = kaelix::status_first_error(cycle, vibration);
cycle = kaelix::status_first_error(cycle, temperature);
cycle = kaelix::status_first_error(cycle, model);
// Sensor morto não impede a transmissão do diagnóstico do sensor morto.
```

Corolário registrado no próprio `main.cpp`: um status que é propriedade do
**build** e não do **ciclo** (o `watchdog` armado, que depende de o core ter a
API do RTC WDT) entra no acumulador **por último** — somado primeiro, venceria o
"primeiro erro vence" em todos os pacotes e esconderia justamente as falhas de
sensor que o campo precisa ver.

### NC-ERR-04 — Em caminho de erro, parâmetro de saída **não é escrito**, ou é escrito com a sentinela **antes de qualquer coisa poder falhar**. A escolha é declarada no header.

**Por quê:** o pior desfecho possível deste projeto é um destino meio escrito que
o chamador leia como medição.
**Base:** JSF++ AV-114; MISRA C++ 8-5-1.

```cpp
// CERTO, forma A (não escreve) — src/sensors/temperature.h
// "Em erro, `*out_c` NÃO é escrito: quem chama decide o que colocar no pacote."

// CERTO, forma B (sentinela primeiro) — src/ml/model.cpp
kaelix::Status model_infer(..., kaelix::MachineState* out_state) {
    KAELIX_REQUIRE(out_state != nullptr, kaelix::Status::NullPointer);
    *out_state = kaelix::MachineState::Unknown;   // primeira instrução com efeito
    ...   // a partir daqui, todo `return` de erro deixa o veredito em Unknown
}

// CERTO, forma B — lib/signal_processing: *out_hz = 0.0f antes de qualquer
// validação, "de modo que nenhum caminho de erro deixe o destino indefinido".
```

### NC-ERR-05 — Sentinela nunca é um valor plausível. Todo caminho de falha produz `MachineState::Unknown`, e valor não medido é `NaN`, nunca `0.0f`.

**Por quê:** `0 °C` é uma temperatura perfeitamente plausível e `RMS = 0` é uma
máquina parada perfeitamente plausível. Um sentinela que se disfarça de medição
é a falha silenciosa que este firmware existe para eliminar; `NaN` não é
confundível com leitura, sobrevive a qualquer aritmética posterior e é
detectável com um único `std::isfinite`.
**Base:** IEEE-754; `ANALISE-DE-FALHAS.md §7`; REQ-VIB-003, REQ-TMP-002.

```cpp
// CERTO — lib/thermistor/thermistor.h e src/main.cpp
inline constexpr float NTC_READING_INVALID = std::numeric_limits<float>::quiet_NaN();
constexpr float MEASUREMENT_INVALID = std::numeric_limits<float>::quiet_NaN();

// ERRADO (histórico) — lib/thermistor: clamp do ratio em [0,001; 0,999].
// Convertia as duas falhas mais prováveis do NTC em temperaturas de aparência
// plausível: +349,7 °C para fio em curto e -77,2 °C para fio rompido, ambas
// transmitidas ao gateway com CRC válido. Um clamp silencia a falha exatamente
// onde ela precisava gritar.
```

**Contrato que acompanha a sentinela:** nunca transmitir o `float` sem o
`Status` junto. `NaN` no pacote sem o código de diagnóstico é defeito do
chamador.

---

## 5. NC-CTR — Validação de parâmetro e contratos

### NC-CTR-01 — Toda função pública valida seus parâmetros antes do primeiro efeito observável — inclusive antes da primeira divisão.

**Por quê:** validar depois de já ter dividido, alocado ou transformado é
validar o resultado do próprio defeito.
**Base:** Power of Ten 7; JSF++ AV-114; MISRA C++ 8-5-1.

```cpp
// CERTO — lib/thermistor/thermistor.cpp
NTC_REQUIRE(adc_max > 0, kaelix::Status::InvalidArgument);
NTC_REQUIRE(std::isfinite(r_fixed_ohm) && r_fixed_ohm > 0.0f, kaelix::Status::InvalidArgument);
const float ratio = static_cast<float>(adc_raw) / static_cast<float>(adc_max);

// ERRADO (histórico) — mesma função: a divisão vinha primeiro. Com adc_max == 0
// ela produzia 0/0 = NaN, e as guardas por clamp seguintes usavam `<` e `>`,
// ambas falsas para NaN — o NaN atravessava intacto até o pacote LoRa.

// CERTO — lib/signal_processing: as guardas de banda são validadas ANTES da
// FFT. No código anterior, o teste de `bin_hz` vinha depois de já ter alocado
// 4 KB e rodado a transformada inteira.
```

### NC-CTR-02 — Violação de contrato e falha de campo são classes distintas e recebem tratamentos distintos: contrato usa `KAELIX_REQUIRE*` (aborta em desenvolvimento, devolve status em produção); falha de campo usa `if` explícito e não aborta em build nenhum.

**Por quê:** violação de contrato é bug **nosso** e o pior resultado possível é
ela devolver um número plausível. Falha de campo é o motivo de o dispositivo
existir e acontece com o firmware correto — se um fio rompido abortasse na
bancada, a equipe desligaria a asserção, e aí o modelo de erro inteiro morre.
**Base:** `ARQUITETURA-SOFTWARE.md §5`; JSF++ AV-114; Power of Ten 5.

```cpp
// CERTO — lib/thermistor/thermistor.cpp
// Contrato: constante de datasheet errada no código. Aborta em dev.
NTC_REQUIRE(std::isfinite(beta) && beta > 0.0f, kaelix::Status::InvalidArgument);

// Campo: NTC em curto. Relatado, nunca abortado.
if (ratio <= NTC_RATIO_SHORTED_MAX) {
    set_status(out_status, kaelix::Status::ThermistorShorted);
    return NTC_READING_INVALID;
}

// CERTO — lib/isolation_forest/isolation_forest.cpp: árvore inconsistente é
// DADO (header mal gerado, bit invertido na flash), e a política de §5 é
// "o ciclo continua". Uma macro que aborta não consegue implementar um status
// cuja política é seguir degradado — por isso `if` explícito, em qualquer build.
if (!tree_arrays_present(tree) || tree.n_nodes <= 0) {
    return kaelix::Status::ModelMalformed;
}
```

Em produção (`-D KAELIX_PRODUCTION`) nada aborta: o Kaelix fica oito meses numa
máquina sem ninguém por perto, e abortar transforma um bug num dispositivo morto
que não conta o que aconteceu. **Disponibilidade do caminho de diagnóstico vale
mais que fail-fast em campo.**

### NC-CTR-03 — Ponteiro é validado antes de qualquer dereferência; índice vindo de dado é validado antes de indexar; `n` sobre buffer estático é validado na fronteira pública contra a constante de dimensionamento.

**Por quê:** o ESP32-S3 não tem MPU — uma leitura fora do array não falha, ela
devolve lixo com cara de número. E com buffer estático, `n > FFT_MAX_N` deixa de
ser "aloca mais" e passa a ser estouro de buffer.
**Base:** Power of Ten 7 e 9; MISRA C++ 5-0-15/5-0-16; JSF++ AV-215.

```cpp
// CERTO — lib/isolation_forest: índice conferido ANTES de indexar
if (node < 0 || node >= static_cast<int32_t>(tree.n_nodes)) {
    return kaelix::Status::ModelMalformed;
}
// e o índice de feature, que vem do dado e não do código:
if (feature_index >= n_features) { return kaelix::Status::IndexOutOfRange; }

// CERTO — lib/signal_processing, fronteira pública de dominant_frequency()
KAELIX_REQUIRE_VALUE(n <= FFT_MAX_N, Status::LengthOutOfRange, 0.0f);
// e a verificação mais grave das três, porque a FFT radix-2 com n não potência
// de 2 não falha alto — ela lê e escreve fora do buffer e devolve um espectro
// errado (estouro comprovado com AddressSanitizer em n = 6):
KAELIX_REQUIRE(is_power_of_two(n), Status::LengthNotPowerOfTwo);

// CERTO — pré-condição de ORDEM também é verificada, não convencionada:
KAELIX_REQUIRE(s_initialized, kaelix::Status::NotInitialized);
// "a ordem init → read é contrato, e contrato não verificado é convenção."
```

**Exceção deliberada, e ela é uma regra:** `lora_sleep()` **não** verifica
`s_initialized`, porque precisa funcionar justamente quando o init falhou — um
chip alimentado e nunca configurado ainda consome standby. Recusar por falta de
init seria proteger o contrato à custa da bateria. Toda exceção a NC-CTR-03
precisa desse tipo de argumento escrito no ponto da exceção.

---

## 6. NC-INI — Inicialização de variáveis

### NC-INI-01 — Toda variável é inicializada na declaração. Agregados usam `{}`. Declaração sem inicializador exige justificativa no ponto.

**Por quê:** uma variável não inicializada em C++ tem valor indeterminado, e no
Kaelix ela seria lida como medição.
**Base:** MISRA C++ 8-5-1; JSF++ AV-142; Power of Ten 6.

```cpp
// CERTO — src/main.cpp e src/power/watchdog.cpp
ksens::VibrationFeatures features{};
kcomms::LoraPacket packet{};
esp_task_wdt_config_t config{};
float rms = MEASUREMENT_INVALID;
MachineState state = MachineState::Unknown;
float best_mag = -1.0f;

// DESVIO REGISTRADO (DEV-008) — src/main.cpp
RTC_NOINIT_ATTR RetainedState s_retained;
// Deliberadamente NÃO inicializada: `.rtc.data` é RECARREGADA da imagem em
// qualquer boot que não seja despertar de deep sleep, o que zerava o
// boot_count justamente num reset por watchdog — apagando a evidência de
// instabilidade, que é a informação de manutenção mais valiosa (FM-33).
// O preço é conteúdo arbitrário após power-on, reconhecido por palavra
// mágica + CRC-16 e distinguido de corrupção real por reset_was_power_on().
```

### NC-INI-02 — Resultado é calculado em locais e publicado no destino de uma vez só, no fim.

**Por quê:** nenhum caminho de erro pode deixar a saída meio escrita — um `out`
com dois campos válidos e dois de lixo é indistinguível de uma medição.
**Base:** JSF++ AV-114; princípio de atomicidade de saída.

```cpp
// CERTO — src/sensors/vibration.cpp
const float rms = compute_rms(samples, n);
const float kurtosis = compute_kurtosis(samples, n);
const float crest_factor = compute_crest_factor(samples, n);
float dominant_freq_hz = 0.0f;
KAELIX_CHECK(dominant_frequency_scratch(..., &dominant_freq_hz));
if (!std::isfinite(rms) || !std::isfinite(kurtosis) ||
    !std::isfinite(crest_factor) || !std::isfinite(dominant_freq_hz)) {
    return kaelix::Status::NotFinite;
}
out->rms = rms;              // só agora
out->kurtosis = kurtosis;
out->crest_factor = crest_factor;
out->dominant_freq_hz = dominant_freq_hz;

// CERTO — src/comms/lora.cpp: make_packet monta um LoraPacket local completo,
// calcula o CRC sobre ele e só então faz `*out = packet;`.
```

---

## 7. NC-CNV — Tipos, conversões e casts

### NC-CNV-01 — Sem cast estilo C e sem notação funcional. Conversão é `static_cast` explícita e visível.

**Por quê:** `(uint16_t)x` esconde qual das cinco conversões o compilador vai
escolher; `static_cast` recusa as perigosas em tempo de compilação.
**Base:** MISRA C++ 5-2-4; JSF++ AV-185.
**Detecção:** `clang-tidy` `google-readability-casting`, `cppcoreguidelines-pro-type-cstyle-cast`.

### NC-CNV-02 — Nenhuma conversão implícita que perca informação ou mude a sinalização. Tipos de largura fixa (`uint16_t`, `int32_t`, `size_t`). Condição de `if`/`while` é `bool`.

**Por quê:** promoção implícita a `int` com sinal num deslocamento é
comportamento que muda de plataforma, e o valor calculado continua parecendo
certo até não parecer.
**Base:** MISRA C++ 5-0-6, 5-0-13, 3-9-2; JSF++ AV-180; `-Wsign-conversion`.

```cpp
// CERTO — lib/crc16/crc16.cpp, com a intenção escrita
// `crc << 1` promoveria uint16_t a `int` COM SINAL e o resultado seria
// reconvertido implicitamente. O número calculado é o mesmo; o que muda é não
// depender mais de promoção implícita para um tipo com sinal.
const uint32_t shifted = static_cast<uint32_t>(crc) << 1U;
crc = ((crc & 0x8000U) != 0U) ? static_cast<uint16_t>(shifted ^ 0x1021U)
                              : static_cast<uint16_t>(shifted);

// ERRADO (histórico) — mesma função
crc ^= data[i] << 8;             // promove a int e reatribui implicitamente
if (crc & 0x8000) { ... }        // condição é int, não bool
```

### NC-CNV-03 — `reinterpret_cast` só na fronteira de serialização, e sempre acompanhado de `static_assert` de layout. Conversão de ponto flutuante para inteiro só depois de o domínio estar provado.

**Por quê:** converter um `float` negativo ou gigante para tipo sem sinal é
comportamento indefinido, e uma guarda por clamp é cega a isso. Serializar uma
struct sem travar o layout é combinar um formato de fio com o compilador.
**Base:** MISRA C++ 5-2-7, 5-0-x; JSF++ AV-182.

```cpp
// CERTO — src/comms/lora.h: o cast de serialização é legítimo porque o layout
// é travado por asserção de build.
static_assert(sizeof(LoraPacket) == 21, "layout do pacote mudou — atualize PACKET_VERSION e o gateway");
static_assert(offsetof(LoraPacket, crc) == sizeof(LoraPacket) - sizeof(uint16_t),
              "o CRC precisa ser o último membro do pacote");
// Sem o segundo assert, reordenar a struct passaria a calcular o CRC sobre a
// região errada — e emissor e receptor continuariam concordando entre si, o
// que torna o erro invisível em teste de laço fechado.

// CERTO — lib/signal_processing: float → size_t só depois de provado o domínio
const float k_lo_real = std::ceil(band_lo_hz / bin_hz);
if (k_lo_real > static_cast<float>(k_max)) { return Status::Ok; }
size_t k_lo = 1U;
if (k_lo_real > 1.0f) { k_lo = static_cast<size_t>(k_lo_real); }

// CERTO — src/sensors/temperature.cpp: a faixa é conferida ANTES do cast.
const uint32_t mv_raw = analogReadMilliVolts(NTC_ADC_PIN);
if (mv_raw > ADC_MAX_PLAUSIBLE_MV) { return kaelix::Status::AdcOutOfRange; }
const uint16_t mv = static_cast<uint16_t>(mv_raw);
// Truncar primeiro esconderia exatamente o valor absurdo que a verificação procura.
```

---

## 8. NC-FPU — Ponto flutuante

Esta área tem uma restrição que as normas de referência não têm: **a paridade
numérica com `training/kaelix_ml/features.py` é invariante inegociável**
(`ARQUITETURA-SOFTWARE.md §7`). Se um refactor mudar qualquer valor calculado, o
modelo treinado deixa de corresponder ao que o dispositivo mede — e a falha é
silenciosa: não aparece na compilação, não aparece em teste de tipo, e o
dispositivo continua transmitindo vereditos com aparência normal.

### NC-FPU-01 — Sem `==` e `!=` entre `float`/`double`. A única exceção é a guarda de divisão contra zero exato espelhada do Python, registrada como DEV-003.

**Por quê:** igualdade de ponto flutuante depende de arredondamento, de ordem de
operações e de nível de otimização.
**Base:** MISRA C++ 6-2-2; JSF++ AV-197.

```cpp
// CERTO — src/sensors/vibration.cpp: quando a pergunta é "o sensor devolveu
// literalmente o mesmo padrão de bits?", a resposta é memcmp, não `==`.
// Comparação bit a bit não é só permitida — é a pergunta CERTA aqui: um
// acelerômetro vivo tem ruído no bit menos significativo mesmo em repouso.
if (std::memcmp(&samples[i], &samples[0], sizeof(float)) != 0) { all_identical = false; }

// DESVIO DEV-003 — lib/signal_processing/signal_processing.cpp
if (m2 == 0.0) { return 0.0f; }     // idêntico a features.py:30
if (rms == 0.0f) { return 0.0f; }   // idêntico a features.py:38
// Trocar por tolerância quebraria a paridade. NÃO É PARA "CORRIGIR".
```

### NC-FPU-02 — Guarda contra valor inválido é escrita na forma negada, para capturar `NaN`.

**Por quê:** toda comparação com `NaN` é falsa. `x <= 0` não pega `NaN`;
`!(x > 0)` pega. `a < lo || a > hi` deixa `NaN` passar; `!(a >= lo && a <= hi)`
recusa. Esta é a diferença entre um `NaN` transmitido com CRC válido e um
diagnóstico.
**Base:** IEEE-754; MISRA C++ 6-2-2; `ANALISE-DE-FALHAS.md` Grupo B.

```cpp
// CERTO — lib/signal_processing
if (!(bin_hz > 0.0f)) { return Status::InvalidArgument; }
// CERTO — src/sensors/temperature.cpp, com a razão escrita ao lado
if (!(celsius >= TEMPERATURE_MIN_C && celsius <= TEMPERATURE_MAX_C)) {
    return kaelix::Status::TemperatureImplausible;
}
// CERTO — lib/thermistor
if (!(std::isfinite(celsius) && celsius > -KELVIN_OFFSET)) { ... }

// ERRADO
if (celsius < TEMPERATURE_MIN_C || celsius > TEMPERATURE_MAX_C) { ... }  // NaN passa
```

### NC-FPU-03 — Nenhum valor não finito atravessa a fronteira de um módulo sem estar acompanhado do `Status` que o explica.

**Por quê:** o detector não pode falhar na direção "máquina sadia". `score > limiar`
com `score` `NaN` avalia falso e devolveria `Normal` — o detector falhando
exatamente na direção em que não pode falhar.
**Base:** REQ-VIB-003; `Status::ScoreNotFinite`, `Status::NotFinite`.

```cpp
// CERTO — três barreiras em série, e nenhuma é redundante:
// lib/isolation_forest — última barreira da matemática
if (!std::isfinite(score)) { return kaelix::Status::ScoreNotFinite; }
// src/ml/model.cpp — cinto e suspensórios sobre a garantia de lib/
KAELIX_ENSURE(std::isfinite(score), kaelix::Status::ScoreNotFinite);
// src/sensors/vibration.cpp — as quatro features, antes de publicar
if (!std::isfinite(rms) || !std::isfinite(kurtosis) || ...) { return Status::NotFinite; }
```

### NC-FPU-04 — Acumulação em `double`, resultado em `float`. A ordem das operações é contrato de paridade e não se reorganiza. `-ffast-math` e equivalentes são proibidos.

**Por quê:** `-ffast-math` autoriza o compilador a reassociar operações e a
assumir que `NaN` não existe — as duas coisas que as regras acima dependem que
sejam falsas. E "um fator constante multiplica todos os bins por igual e não
moveria o argmax" é exatamente o tipo de raciocínio que quebra paridade: em
paridade numérica nada se muda porque "não deveria importar".
**Base:** IEEE-754; JSF++ AV-202; `ARQUITETURA-SOFTWARE.md §7`.

```cpp
// CERTO — lib/signal_processing/signal_processing.cpp
double sum_sq = 0.0;
for (size_t i = 0; i < n; ++i) {
    sum_sq += static_cast<double>(samples[i]) * static_cast<double>(samples[i]);
}
return static_cast<float>(std::sqrt(sum_sq / static_cast<double>(n)));

// CERTO — M_PI não faz parte do C++ padrão (é extensão POSIX/GNU): com
// -std=c++17 estrito, que é o que os analisadores usam, o arquivo não
// compilaria. Mesmos dígitos, mesmo valor double.
constexpr double K_PI = 3.14159265358979323846;
```

**Regra de processo que acompanha:** toda mudança em `lib/` roda
`pio test -e native` e `pytest` em `training/tests/` antes e depois — **inclusive
mudanças "só de organização"**. Trocar `std::vector` por buffer estático não
deveria mudar nenhum bit, e é justamente por isso que precisa ser demonstrado.

---

## 9. NC-CST — const-correctness e constantes

### NC-CST-01 — Local não modificado é `const`. Parâmetro ponteiro ou referência não modificado é `const`.

**Por quê:** `const` num parâmetro é a declaração, verificável pelo compilador,
de que a função **lê** e não **altera** — o que num firmware com buffers
compartilhados em `.bss` é informação de segurança, não de estilo.
**Base:** MISRA C++ 7-1-1, 7-1-2; JSF++ AV-134/AV-135.
**Detecção:** `clang-tidy` `misc-const-correctness`, `readability-non-const-parameter`.

```cpp
// CERTO — assinaturas de L1: a entrada é const, a saída é ponteiro nomeado
float compute_rms(const float* samples, size_t n);
kaelix::Status isolation_tree_path_length(const IsolationTree& tree,
                                          const float* features,
                                          int32_t n_features, float* out_path);
// CERTO — locais
const float rms = compute_rms(samples, n);
const Status radio_sleep = kcomms::lora_sleep();
const int32_t feature_index = static_cast<int32_t>(tree.feature[node]);
```

### NC-CST-02 — Constante é `constexpr`, nunca `#define`. Nenhum número mágico: toda constante de origem física traz a derivação ou a fonte no ponto da declaração.

**Por quê:** `constexpr` tem tipo e pode ser verificada por `static_assert`;
`#define` não tem nem uma coisa nem outra. E uma constante sem derivação é uma
decisão de engenharia que ninguém consegue revisar nem defender.
**Base:** MISRA C++ 16-2-1; JSF++ AV-29/AV-31/AV-151; `ARQUITETURA-SOFTWARE.md §3`.

```cpp
// CERTO — src/comms/lora.cpp: a fonte é o datasheet, e está escrita
// "O datasheet pede RST em nível baixo por mais de 100 µs e 5 ms de espera
//  antes do primeiro acesso."
constexpr uint32_t LORA_RESET_PULSE_MS = 1;
constexpr uint32_t LORA_RESET_SETTLE_MS = 5;

// CERTO — src/sensors/temperature.cpp: a derivação torna o número revisável
// "Acima de Vcc mais a margem de calibração do eFuse (~10%) não existe tensão
//  possível neste divisor: o que existe é atenuação errada, pino não roteado
//  ao ADC ou leitura de outro canal."
constexpr uint32_t ADC_MAX_PLAUSIBLE_MV = 3630;
static_assert(ADC_MAX_PLAUSIBLE_MV >= VCC_MV, "o teto do ADC não pode ficar abaixo de Vcc");

// CERTO — lib/thermistor/thermistor.h traz a tabela R×T inteira e a conta que
// leva de ratio ≤ 0,02 a "+149,0 °C, impossível" antes de declarar o limiar.

// ERRADO
#define LORA_SETTLE 5
delay(5);
if (mv > 3630) { ... }
```

---

## 10. NC-ESC — Escopo e visibilidade

### NC-ESC-01 — Tudo que não é interface pública vive no namespace anônimo do `.cpp`. Declaração no menor escopo possível, no ponto de uso.

**Por quê:** o que não tem ligação externa não pode ser alcançado por engano de
outro módulo, e o compilador pode provar coisas sobre ele que não conseguiria
provar de outro modo.
**Base:** MISRA C++ 3-3-2, 7-3-1; JSF++ AV-136; Power of Ten 6.

```cpp
// CERTO — padrão seguido em todo o firmware
namespace kaelix::sensors {
namespace {
float s_samples[VIBRATION_MAX_SAMPLES];
bool s_initialized = false;
constexpr bool is_power_of_two(uint16_t n) { ... }
} // namespace
...
} // namespace kaelix::sensors

// ERRADO (atual, pendência aberta) — src/power/sleep.cpp
static constexpr gpio_num_t PERIPHERALS_POWER_PIN = GPIO_NUM_5;
// Declarada FORA de `namespace kaelix::power` e com `static` em vez de
// namespace anônimo — a única inconsistência de escopo do firmware. Não é um
// defeito, é uma exceção sem razão, e exceção sem razão é o que corrói a norma.
```

### NC-ESC-02 — `using namespace` proibido em headers e em `.cpp` de produção. Use alias de namespace ou `using` de nome específico.

**Por quê:** `main.cpp` inclui todos os módulos e é o arquivo mais exposto a
colisão de nomes — e já houve dois enums chamados `Status` neste projeto, cuja
troca compilava sem um aviso sequer.
**Base:** MISRA C++ 7-3-4; JSF++ AV-32.

```cpp
// CERTO — src/main.cpp: origem visível, sem verbosidade
namespace ksens = kaelix::sensors;
namespace kml = kaelix::ml;
namespace kcomms = kaelix::comms;
namespace kpower = kaelix::power;
using kaelix::MachineState;
using kaelix::Status;

// CERTO — lib/isolation_forest: dentro de `namespace kaelix::ml`, o nome curto
// `Status` resolveria para kaelix::ml::Status sempre que src/ml/model.h já
// tivesse sido incluído — e a troca compila. Enquanto os dois enums existirem,
// ali se escreve `kaelix::Status` por extenso, em toda assinatura.

// DESVIO DEV-010 — test/test_crc16/test_crc16.cpp
using namespace kaelix::comms;   // tolerado só em test/, nunca em lib/ ou src/
```

---

## 11. NC-NOM — Nomes

### NC-NOM-01 — A tabela de convenções de `ARQUITETURA-SOFTWARE.md §3` é normativa.

| Elemento | Convenção | Exemplo |
|---|---|---|
| Diretório e arquivo | `snake_case`, nome do módulo | `lib/signal_processing/signal_processing.h` |
| Namespace | `kaelix::<área>`; `kaelix` puro só para L0 | `kaelix::sensors`, `kaelix::detail` |
| Tipo | `PascalCase` | `VibrationFeatures`, `LoraPacket`, `Status` |
| Enumerador | `PascalCase`, sempre `enum class` | `Status::SensorAbsent` |
| Função | `snake_case`, verbo primeiro | `compute_rms`, `lora_send` |
| Função exportada de L2 | prefixada pelo módulo | `vibration_init`, `temperature_read_celsius` |
| Variável, parâmetro, membro | `snake_case`, sem prefixo húngaro | `sample_rate_hz` |
| Constante `constexpr` | `UPPER_SNAKE_CASE` | `DOMINANT_BAND_LO_HZ` |
| Macro | `KAELIX_` + `UPPER_SNAKE_CASE`; privada de header, sufixo `_` | `KAELIX_REQUIRE`, `KAELIX_ASSERT_FAIL_` |
| Teste | `test/test_<mod>/test_<mod>.cpp`, caso `test_<função>_<condição>_<esperado>` | `test_rms_of_sine_wave` |

**Base:** JSF++ AV-46 a AV-59; MISRA C++ 2-10-x.
**Detecção:** `clang-tidy` `readability-identifier-naming`.

### NC-NOM-02 — Toda grandeza física carrega a unidade como sufixo. Obrigatório, sem exceção.

Sufixos em uso: `_hz`, `_ms`, `_us`, `_s`, `_mv`, `_ohm`, `_c`, `_k`, `_dbm`,
`_ua`, `_ma`, `_mah`, `_rad`, `_percent`, `_bytes`.

**Por quê:** custo zero, e elimina por construção a classe de erro mais cara que
existe em software embarcado — a que confunde uma unidade com outra numa
conversão. `float temperature` é proibido; `float temperature_c` é obrigatório.
**Base:** JSF++ AV-48; prática de projeto (Mars Climate Orbiter).

```cpp
// CERTO — em uso em todo o firmware
float sample_rate_hz;  uint16_t vcc_mv;  float r_fixed_ohm;  float temperature_c;
constexpr uint32_t WATCHDOG_ACTIVE_RTC_MS = 20000U;
constexpr uint32_t WATCHDOG_SLEEP_MARGIN_PERCENT = 120U;

// ERRADO (atual, pendência aberta) — lib/signal_processing, fft_radix2()
const double ang = -2.0 * K_PI / static_cast<double>(len);   // é um ÂNGULO em radianos
// Deve ser `ang_rad`. É a única grandeza física sem sufixo no firmware.
```

### NC-NOM-03 — Estado de escopo de arquivo é prefixado `s_`. Macro só onde função não serve.

**Por quê:** `s_` marca, no ponto de uso e sem consultar a declaração, que
aquele nome é estado que sobrevive à chamada — o que num superloop de um disparo
é a diferença entre uma variável e um invariante de ciclo. Macro é aceitável
apenas quando precisa de `__FILE__`/`__LINE__` ou de um `return` no escopo do
chamador, isto é: o conteúdo de `kaelix_status.h`, e nada mais.
**Base:** MISRA C++ 16-0-4, 16-2-1; JSF++ AV-29/AV-31; Power of Ten 8.

```cpp
// CERTO — s_samples, s_fft_re, s_fft_im, s_initialized, s_retained
// CERTO — a única família de macros do projeto, todas inexprimíveis como função:
//         KAELIX_REQUIRE / KAELIX_REQUIRE_VALUE / KAELIX_REQUIRE_VOID /
//         KAELIX_ENSURE / KAELIX_CHECK  (+ NTC_REQUIRE, local a thermistor.cpp,
//         com `#undef` ao fim do arquivo — o escopo da macro é o arquivo)
```

---

## 12. NC-HDR — Cabeçalhos e inclusão

### NC-HDR-01 — Todo header abre com `#pragma once`, compila sozinho e inclui o que usa. Constante em header é `inline constexpr`.

**Por quê:** um header que só compila depois de outro cria uma ordem de inclusão
implícita que quebra na primeira reorganização. E `inline constexpr` dá uma
entidade única no programa, em vez de uma cópia por unidade de tradução.
**Base:** MISRA C++ 16-2-1 (mecanismo de inclusão única), 3-1-1, 3-2-x; JSF++ AV-35.

```cpp
// CERTO — lib/thermistor/thermistor.h declara o que precisa
#pragma once
#include <cstdint>
#include <limits>          // por std::numeric_limits, usado logo abaixo
#include "kaelix_status.h"
inline constexpr float NTC_RATIO_SHORTED_MAX = 0.02f;

// PENDÊNCIA — inconsistência real: lib/signal_processing/signal_processing.h usa
// `constexpr size_t VIBRATION_SAMPLES = 512;` (sem `inline`), enquanto
// src/sensors/vibration.h usa `inline constexpr uint16_t VIBRATION_MAX_SAMPLES`.
// Não é bug — é uma cópia por TU em vez de uma entidade única. Uniformizar
// para `inline constexpr` em todos os headers.
```

### NC-HDR-02 — Ordem de inclusão fixa, em blocos separados por linha em branco. Arquivo gerado nunca é editado à mão e traz o aviso no topo.

Ordem: (1) o header do próprio módulo, (2) headers do projeto, (3) SDK e
terceiros, (4) biblioteca padrão.

**Por quê:** o header do próprio módulo vindo primeiro prova, a cada compilação,
que ele é autossuficiente. E editar `isolation_forest_data.h` à mão quebra a
correspondência com o modelo treinado sem deixar rastro no pipeline — o
dispositivo passa a inferir com árvores que não existem em lugar nenhum.
**Base:** JSF++ AV-33; `ARQUITETURA-SOFTWARE.md §3` e §7.4.

```cpp
// CERTO — src/comms/lora.cpp
#include "lora.h"

#include "../machine_state.h"
#include "crc16.h"
#include "kaelix_status.h"

#include <Arduino.h>
#include <RadioLib.h>

#include <cstdint>

// PENDÊNCIA — src/ml/isolation_forest_data.h é gerado por export_cpp.py e
// hoje NÃO traz o cabeçalho "GERADO POR … NÃO EDITAR" que §3 exige. O
// gerador deve emiti-lo junto com os dados.
```

---

## 13. NC-COM — Comentários

### NC-COM-01 — O comentário responde **por quê**, nunca **o quê**. Contrato no header; razão da decisão na implementação.

**Por quê:** o *o quê* já está no código e vai divergir dele na primeira
alteração; o *por quê* não está em lugar nenhum e é o que uma banca, um revisor
ou você daqui a seis meses precisa para não desfazer a decisão por engano.
**Base:** JSF++ AV-127/AV-129; prática de revisão.

```cpp
// CERTO — lib/signal_processing/signal_processing.h
// "Por que velocidade e não aceleração: aceleração escala com ω², então o
//  espectro de aceleração é dominado pelo conteúdo de alta frequência —
//  tipicamente um modo estrutural da montagem, que é o mesmo com a máquina
//  sadia ou defeituosa. Medido no MAFAULDA: o pico de aceleração fica em
//  117 Hz independente da rotação (correlação com a rotação real: -0,018)."
// Um comentário que impede um refactor "óbvio" e traz o número que o sustenta.

// CERTO — todo bloco de não-reentrância, de derivação de limiar e de política
// de erro deste firmware segue o mesmo padrão: decisão, alternativa
// descartada, e o custo aceito.

// ERRADO
i++;  // incrementa i
```

Corolário: **propriedade perigosa se declara.** `dominant_frequency` não é
reentrante e o header diz isso em maiúsculas, com o argumento de por que é
verificável neste dispositivo (superloop de um disparo, sem escalonador, sem
ISR) e o que fazer se um segundo contexto de execução aparecer.

### NC-COM-02 — Todo `TODO` nomeia a fase ou o dono. Código não escrito falha alto: `Status::NotImplemented`, nunca `Ok`, nunca `false`.

**Por quê:** um caminho não implementado que devolve sucesso é a forma mais
direta de o dispositivo afirmar o que não mediu.
**Base:** JSF++ AV-127; REQ-VIB-003.

```cpp
// CERTO — src/sensors/vibration.cpp
// "TODO (Fase 2): rajada de `n` amostras pelo FIFO do MPU6050 [...] Devolver
//  NotImplemented (e não `false`, e muito menos Ok) é o que impede o ciclo de
//  seguir como se houvesse acelerômetro: o código ainda não escrito precisa
//  falhar alto, não silenciar."
return kaelix::Status::NotImplemented;

// CERTO — src/power/watchdog.cpp: quando a API do RTC WDT não existe no core
// instalado, watchdog_arm_active_phase() devolve NotImplemented e o gateway
// fica sabendo que a rede externa não existe naquele build. "Silenciar isso
// seria pior: o invariante de 20 s deixaria de valer sem que ninguém soubesse."
```

---

## 14. NC-BLD — Build e verificação

### NC-BLD-01 — A build é limpa com `-Wall -Wextra -Werror`, sem exceções e sem RTTI. Aviso é erro.

Flags exigidas nos dois ambientes de `platformio.ini`:

```ini
build_flags =
    -std=gnu++17
    -Wall -Wextra -Werror
    -Wconversion -Wsign-conversion -Wshadow -Wfloat-equal -Wswitch-enum
    -fno-exceptions -fno-rtti
```

**Por quê:** metade das regras desta norma (NC-CNV-02, NC-ERR-02, NC-FPU-01,
NC-ESC-01) são verificáveis pelo compilador e por mais ninguém — sem `-Werror`
elas voltam a ser intenção. `-fno-exceptions` e `-fno-rtti` não são otimização:
o modelo de erro deste projeto é `Status`, e um `throw` vindo de uma biblioteca
de terceiros num firmware sem `catch` é `abort()` → pânico → boot loop a ~40 mA.
**Base:** Power of Ten 10; JSF++ AV-208 (exceções), AV-212; MISRA C++ 15-x.

> **ESTADO ATUAL: PENDENTE (DEV-014).** `platformio.ini` hoje traz apenas
> `-D CORE_DEBUG_LEVEL=3`, `-D BOARD_HAS_PSRAM` e `-std=gnu++17`. Nenhuma flag
> de aviso, e nenhum `-fno-exceptions` — embora vários comentários do firmware
> raciocinem explicitamente sobre o comportamento "com `-fno-exceptions`". A
> premissa está documentada no código e ausente da build. É a pendência de
> maior retorno por linha alterada deste documento.

### NC-BLD-02 — Todo invariante de layout, dimensionamento ou acoplamento com o mundo externo é verificado por `static_assert`.

**Por quê:** uma divergência que quebra a build custa cinco minutos; a mesma
divergência descoberta em campo custa um deslocamento de manutenção e uma série
histórica contaminada.
**Base:** Power of Ten 5 e 10; JSF++ AV-16.

```cpp
// CERTO — os cinco que já existem, e a falha que cada um transforma em erro de build
static_assert(sizeof(Status) == 1, ...);                 // o byte diag do pacote
static_assert(sizeof(LoraPacket) == 21, ...);            // o formato de fio
static_assert(offsetof(LoraPacket, crc) == sizeof(LoraPacket) - sizeof(uint16_t), ...);
static_assert(N_FEATURES == 4,                           // treino × inferência
              "model.cpp monta o vetor de features na mão — atualize junto com export_cpp.py");
static_assert(CYCLE_DEADLINE_MS < kpower::WATCHDOG_TASK_TIMEOUT_S * 1000U,
              "a cota de software precisa disparar antes do Task WDT");

// PENDÊNCIA aberta em src/ml/model.cpp: o assert de N_FEATURES pega a
// QUANTIDADE de features; só um FEATURE_ORDER_HASH exportado pelo treino pega
// a ORDEM. Uma reordenação no Python avalia o modelo com os eixos trocados de
// forma igualmente silenciosa.
```

---

## 15. Registro de desvios

> Um desvio é uma regra desta norma que um trecho de código não cumpre, com
> justificativa aceita, risco declarado e revisão marcada. **Desvio registrado é
> engenharia; desvio não registrado é dívida.** Esconder desvios não os elimina
> — elimina só a possibilidade de alguém decidir sobre eles.

A numeração continua a de `ARQUITETURA-SOFTWARE.md §8`: há **um** registro de
desvios no projeto, não dois.

| ID | Regra | Onde | Justificativa e risco aceito | Revisão |
|---|---|---|---|---|
| **DEV-001** | NC-MEM-01 — sem heap | `src/comms/lora.cpp`, `new Module(...)` | **FECHADO.** A hipótese registrada na arquitetura era que o RadioLib impunha o `new`. A verificação mostrou que **não impõe**: o construtor do `SX1278` exige um `Module*`, não um ponteiro alocado. O código passou a usar `Module lora_module(...); SX1278 radio(&lora_module);` no namespace anônimo. **O desvio não foi justificado — foi eliminado**, e isso é a resposta certa quando a alternativa existe. Reabrir apenas se alguma versão futura do RadioLib exigir o ponteiro alocado; nesse caso o risco é uma alocação única, em inicialização estática, nunca liberada, de tamanho fixo, sem fragmentação possível porque nada mais aloca. | — |
| **DEV-002** | Cobertura de teste em L2 | `src/sensors/vibration.cpp`, `vibration_acquire` | Testá-la exigiria o duplê de I2C que `§2` da arquitetura recomenda não construir. **Risco:** a função de aquisição real (ainda não escrita) entra em produção sem teste automatizado. **Mitigação:** mantê-la reduzida a um laço de leitura, com **toda** a decisão em `vibration_features_from_samples`, que é testada no host. | quando houver segundo sensor |
| **DEV-003** | NC-FPU-01 — sem igualdade de float | `signal_processing.cpp` (`m2 == 0.0`, `rms == 0.0f`) | Comparação contra zero exato é a guarda de divisão correta aqui, e é **idêntica** à de `features.py:30,38`. Trocar por tolerância quebraria a paridade numérica. **Risco: nenhum** — o denominador exatamente zero é o único caso que a guarda precisa pegar. | não revisar — é intencional |
| **DEV-004** | MISRA C++ 16-0-4 — sem macro função-símile | `lib/kaelix_status/kaelix_status.h`; `NTC_REQUIRE` em `thermistor.cpp` | `KAELIX_REQUIRE*`, `KAELIX_ENSURE` e `KAELIX_CHECK` capturam `__FILE__`/`__LINE__` e executam um `return` no escopo do chamador: **inexprimível como função**. **Risco:** `cond` é avaliada duas vezes em `NTC_REQUIRE`. **Mitigação:** toda condição usada ali é pura e barata (comparação de escalar); a alternativa — guardar `cond` numa variável — faria o build de desenvolvimento imprimir o nome da variável em vez do texto da condição, perdendo a informação pela qual a asserção existe. `NTC_REQUIRE` tem `#undef` ao fim do arquivo. | não revisar |
| **DEV-005** | MISRA C++ 16-2-1 — mecanismo padrão de inclusão única | todos os headers | `#pragma once` não é C++ padrão. **Risco:** teórico — um compilador sem suporte. **Aceito porque:** os dois toolchains do projeto (xtensa-esp32s3-gcc e o do host) suportam; `#pragma once` elimina por construção a colisão de macro de guarda, que é o modo de falha real desse mecanismo. | não revisar |
| **DEV-006** | MISRA C++ 6-4-6 — `switch` termina em `default` | `status_to_string`, `subsystem_to_string`, `machine_state_to_string` | Deliberado: **sem `default`, acrescentar um valor ao enum sem tratá-lo vira aviso de `-Wswitch`** em vez de virar `"?"` em silêncio. O retorno após o `switch` cobre o byte fora do enum (memória corrompida ou pacote decodificado do ar). **Risco:** nenhum; o caminho de saída existe, só não está na cláusula `default`. Depende de NC-BLD-01 estar em vigor para valer. | não revisar |
| **DEV-007** | MISRA C++ 5-2-7 / JSF++ AV-182 — sem `reinterpret_cast` | `lora.cpp` (`make_packet`, `packet_is_valid`, `lora_send`), `main.cpp` (`retained_crc`) | Serializar uma struct para bytes e calcular CRC sobre eles exige a conversão. **Risco:** o CRC passa a depender do layout, e um layout que muda em silêncio produz emissor e receptor concordando entre si sobre a região errada — invisível em teste de laço fechado. **Mitigação:** `static_assert` de `sizeof` e de `offsetof(crc)` nas duas structs; `PACKET_VERSION` no fio. | não revisar |
| **DEV-008** | NC-INI-01 — toda variável inicializada | `src/main.cpp`, `RTC_NOINIT_ATTR RetainedState s_retained` | `.rtc.data` é recarregada da imagem em todo boot que não seja despertar de deep sleep, zerando o `boot_count` justamente num reset por watchdog — apagando a evidência de instabilidade (FM-33). `.noinit` preserva. **Risco:** conteúdo arbitrário após power-on. **Mitigação:** palavra mágica `0x4B4C5831` + CRC-16 sobre os campos, com `reset_was_power_on()` distinguindo "primeiro boot da vida" de `RtcStateCorrupt`. | não revisar |
| **DEV-009** | C++ padrão | `__attribute__((packed))` em `LoraPacket`; `RTC_NOINIT_ATTR`; `[[noreturn]]` sobre APIs do IDF | Extensões de GCC/ESP-IDF sem equivalente padrão para controlar layout de fio e seção de memória. **Risco:** o firmware não é portátil para outro toolchain. **Aceito:** o alvo é um só, e a alternativa (serialização campo a campo) troca uma extensão bem definida por código manual mais fácil de errar. | se houver segundo alvo |
| **DEV-010** | NC-ESC-02 — sem `using namespace` | `test/test_crc16/`, `test_thermistor/` etc. | Legibilidade dos casos de teste. **Risco:** colisão de nomes dentro de um arquivo de teste — contido, porque nenhum teste inclui mais de um módulo de produção. **Limite do desvio:** vale só em `test/`; em `lib/` e `src/` a regra é absoluta. | não revisar |
| **DEV-011** | Toda a norma | `RadioLib`, `I2Cdevlib-MPU6050`, core Arduino-ESP32 | **Bibliotecas de terceiros não são auditadas contra esta norma.** Elas alocam no heap, usam construções que a norma proíbe e não expõem `Status`. **Risco real e aceito:** a política de memória do Kaelix vale para o código do Kaelix, não para a pilha inteira. **Mitigações:** (a) superfície de uso mínima e explícita — do RadioLib usamos `begin`, `setOutputPower`, `transmit`, `sleep`, e nada mais; (b) `from_radiolib()` traduz todo código de retorno para o vocabulário do projeto na fronteira; (c) o reset do SX1278 é feito por GPIO segundo o datasheet, e não por `radio.reset()`, porque "depender do datasheet é mais estável que depender da versão da biblioteca"; (d) o watchdog cobre um travamento dentro de biblioteca de terceiros do mesmo jeito que cobre o nosso. | a cada atualização de `lib_deps` |
| **DEV-012** | Argumentos padrão | `dominant_frequency(..., band_lo_hz = …, band_hi_hz = …)`; `out_status = nullptr` em `lib/thermistor` | Argumento padrão esconde parte da assinatura no ponto de chamada. **Risco:** baixo aqui — os padrões são as constantes ISO 10816-3 do próprio módulo, e `out_status = nullptr` é o que permite validar sem quebrar a paridade de assinatura exigida por `§7`. **Aceito** como o menor custo entre as alternativas (duplicar a função, ou obrigar todo chamador a passar `nullptr`). | não revisar |
| **DEV-013** | NC-ARQ-02 — camadas irmãs não se enxergam | `src/ml/model.h` inclui `../sensors/vibration.h` | `VibrationFeatures` é compartilhado por `ml` e `sensors`. **Risco:** o módulo de inferência passa a depender do módulo de aquisição; uma mudança em `vibration.h` recompila e potencialmente altera `ml`. **Destino definido:** `VibrationFeatures` desce para L1, ao lado de `lib/signal_processing`, que é quem produz os quatro números — como `MachineState` já desceu para a raiz de `src/`. Não movido nesta rodada por posse de arquivo. | próxima rodada |
| **DEV-014** | NC-BLD-01 — build com `-Werror`, sem exceções | `platformio.ini` | As flags de aviso e `-fno-exceptions`/`-fno-rtti` **não estão na build**, embora o código raciocine sobre elas. **Risco: alto e assimétrico** — sem `-Werror`, as regras NC-CNV-02, NC-ERR-02, NC-FPU-01 e o desvio DEV-006 deixam de ser verificadas por quem as verificaria de graça; sem `-fno-exceptions`, um `throw` de terceiro num firmware sem `catch` vira pânico e boot loop a ~40 mA. **Aceito temporariamente** apenas porque ligar `-Werror` num código que ainda não compilou sob ele exige uma passada dedicada. | **próxima rodada — prioridade 1** |

### Desvios que este projeto **não** concede

Registrar o que não é negociável é parte do registro:

- **Nenhuma exceção a NC-ARQ-01.** `lib/` incluir `src/` derruba a testabilidade
  do projeto inteiro, e não há justificativa que compense.
- **Nenhuma exceção a NC-ERR-05.** Nenhum caminho de falha pode produzir
  `MachineState::Normal`, nem um valor não medido que não seja `NaN`.
- **Nenhuma exceção a NC-FLX-02.** Laço com limite vindo de dado externo sem
  cota constante é o modo de falha que mata a bateria em dois dias.
- **Nenhuma exceção a NC-FPU-04** sem rodar a suíte de paridade antes e depois.

---

## 16. Pendências que esta norma cria

Achados reais da leitura do código, em ordem de retorno por esforço. Nenhum
deles foi alterado — este documento não edita código.

| # | Pendência | Onde | Regra |
|---|---|---|---|
| 1 | Ligar `-Wall -Wextra -Werror -fno-exceptions -fno-rtti` nos dois ambientes | `platformio.ini` | NC-BLD-01 / DEV-014 |
| 2 | `VibrationFeatures` desce para L1 | `src/ml/model.h` | NC-ARQ-02 / DEV-013 |
| 3 | Cabeçalho "GERADO POR … NÃO EDITAR" no arquivo gerado | `src/ml/isolation_forest_data.h` | NC-HDR-02 |
| 4 | `FEATURE_ORDER_HASH` exportado e conferido por `static_assert` | `training/kaelix_ml/export_cpp.py`, `src/ml/model.cpp` | NC-BLD-02 |
| 5 | `PERIPHERALS_POWER_PIN` para dentro de `namespace kaelix::power { namespace { … } }` | `src/power/sleep.cpp` | NC-ESC-01 |
| 6 | `const double ang` → `ang_rad` | `lib/signal_processing/signal_processing.cpp` | NC-NOM-02 |
| 7 | `for (int bit = 0; bit < 8; ++bit)` → `int32_t`/`size_t` | `lib/crc16/crc16.cpp` | NC-CNV-02 |
| 8 | Uniformizar `inline constexpr` em constantes de header | `lib/signal_processing/signal_processing.h` | NC-HDR-01 |
| 9 | `tools/check_layers.sh` com os três `grep` de NC-ARQ e o de NC-FLX-04 | — | NC-ARQ-01/02/03 |
| 10 | `.clang-tidy` com o mapeamento da tabela abaixo | — | §17 |

---

## 17. Como cada regra é verificada

Uma norma que não é executável é decoração. A coluna "quem pega" é o critério de
admissão do §0 aplicado de volta a cada regra.

| Verificador | Regras que ele cobre |
|---|---|
| **Compilador** (`-Werror` + flags de NC-BLD-01) | NC-ERR-02 (`-Wunused-result`), NC-CNV-02 (`-Wconversion`, `-Wsign-conversion`), NC-FPU-01 (`-Wfloat-equal`), NC-ESC-01 (`-Wshadow`), DEV-006 (`-Wswitch`) |
| **`static_assert`** | NC-MEM-02, NC-CNV-03, NC-BLD-02 |
| **`pio test -e native`** | NC-ARQ-01 e NC-ARQ-03 (`lib/` que inclua `<Arduino.h>` não compila), NC-FPU-04 (paridade) |
| **`grep` / `tools/check_layers.sh`** | NC-ARQ-02, NC-ARQ-03, NC-MEM-01, NC-FLX-04 |
| **`clang-tidy`** | NC-CNV-01 (`google-readability-casting`), NC-CST-01 (`misc-const-correctness`), NC-NOM-01 (`readability-identifier-naming`), NC-MEM-01 (`cppcoreguidelines-no-malloc`), NC-HDR-01 (`misc-include-cleaner`) |
| **Teste unitário** | NC-CTR-01/02/03 (as suítes exercitam as guardas, inclusive por `fork()` para os caminhos que abortam), NC-ERR-04, NC-FPU-02/03 |
| **Revisão humana** | NC-ARQ-04, NC-FLX-01 (o argumento da cota), NC-CTR-02 (a classificação contrato × campo), NC-ERR-05, NC-CST-02 (a derivação da constante), NC-COM-01/02 |

### Checklist de revisão — a versão de uma página

Se um revisor só tiver dois minutos, são estas as perguntas. Elas cobrem os
modos de falha que efetivamente aconteceram neste repositório.

1. **Algum caminho novo pode produzir `Normal` ou um número plausível sem ter medido?** (NC-ERR-04, NC-ERR-05, NC-ARQ-04)
2. **Todo laço novo tem cota, e a cota vem de constante e não de dado?** (NC-FLX-01, NC-FLX-02)
3. **Algum `Status` de retorno ficou sem consumidor?** (NC-ERR-02)
4. **Toda função nova valida ponteiro, índice e `n` antes do primeiro efeito?** (NC-CTR-01, NC-CTR-03)
5. **Alguma guarda de ponto flutuante deixa `NaN` passar por não estar na forma negada?** (NC-FPU-02)
6. **Alguma coisa aloca?** (NC-MEM-01)
7. **A mudança tocou `lib/`? A suíte de paridade rodou antes e depois?** (NC-FPU-04)
8. **Alguma grandeza física entrou sem sufixo de unidade?** (NC-NOM-02)
9. **Alguma inclusão nova atravessa camada ou área?** (NC-ARQ-01, NC-ARQ-02)
10. **O que não dá para cumprir virou linha no §15, ou virou silêncio?**

---

## 18. Base normativa

- **MISRA C++:2008** — *Guidelines for the use of the C++ language in critical
  systems*. Fonte de NC-CNV, NC-FPU-01, NC-CST-01, NC-ESC-02, NC-HDR-01,
  NC-MEM-01.
- **JSF++ (2005)** — *Joint Strike Fighter Air Vehicle C++ Coding Standards*,
  Lockheed Martin. Fonte de NC-MEM-01 (AV-206), NC-FLX-03 (AV-119), NC-ERR-02
  (AV-115), NC-NOM, NC-BLD-01 (AV-208).
- **Holzmann, G. (2006)** — *The Power of Ten: Rules for Developing
  Safety-Critical Code*, IEEE Computer / NASA-JPL. Fonte de NC-FLX-01/02,
  NC-CTR-01/03, NC-BLD-01/02. Adotado aqui porque é a norma cujo regime — laços
  limitados, sem heap, sem recursão, retorno sempre verificado, análise estática
  obrigatória — mais se aproxima do de um dispositivo que precisa sobreviver
  oito meses sem manutenção.
- **DO-178C** — usado como **referência de método**, não como objetivo de
  certificação: rastreabilidade requisito↔código↔teste (`ARQUITETURA-SOFTWARE.md §9`),
  determinismo de memória e de tempo, e registro formal de desvios.
- **IEEE-754** — premissa de NC-FPU inteira.
- **ISO 10816-3** — origem da banda de análise de 10–1000 Hz (`DOMINANT_BAND_*_HZ`).

**O que este documento não afirma.** O Kaelix não é software certificado, não
foi submetido a nenhuma autoridade e não pretende ser. O que ele adota das
normas acima são as **práticas de organização, determinismo e rastreabilidade** —
porque elas resolvem problemas que este dispositivo tem de verdade, e porque
cada uma delas pode ser defendida apontando para a falha concreta que impede.
Uma regra adotada por autoridade, e não por consequência, seria exatamente o
tipo de decisão que esta norma existe para evitar.
