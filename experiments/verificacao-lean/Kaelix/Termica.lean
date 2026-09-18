/-
  Kaelix/Termica.lean — o caminho térmico e a margem de operação.

  Verifica os números de §4.4.1 do TCC pelo MESMO modelo concentrado que os
  produziu (`experiments/notebooks/analise-termica.ipynb`):

      R_cond = L/(kA)                                    condução em série
      Q_in   = (T_carcaça − T)/R                         entrada pelo caminho
      Q_out  = h_c(T)·A_ext·(T − T_amb)
               + εσA_ext[(T+273,15)⁴ − (T_amb+273,15)⁴]  convecção + radiação
      h_c(T) = 1,42·[(T − T_amb)/0,05]^{1/4}             placa vertical, ar

  A temperatura interna é a RAIZ de Q_in − Q_out. Como Q_in decresce em T e
  Q_out cresce em T, o resíduo é estritamente decrescente: mostrar que ele é
  positivo em T₁ e negativo em T₂ > T₁ localiza a raiz em (T₁, T₂). É essa a
  forma de todos os enunciados abaixo — a monotonicidade é o passo argumentado
  fora do Lean, e é elementar.

  A raiz quarta de h_c entra por enquadramento verificado (`ehRaiz4`): para
  cada temperatura avaliada há um intervalo racional cujas quartas potências
  cercam o argumento.

  ⚠ RESULTADO DIVERGENTE. Este arquivo NÃO confirma a temperatura interna de
  44,8 °C relatada no TCC. Pelo balanço acima, com carcaça a 80 °C, o resíduo
  já é NEGATIVO em 44,7 °C: a raiz está em 33,0 °C, não em 44,8 °C. O valor de
  44,8 °C é o que a iteração de ganho fixo do notebook devolve após 500 passos
  partindo de 55 °C — ela não convergiu. O próprio repositório registra a
  correção: `hardware/termica.py` grava `fig11_correcao.csv` com as duas
  leituras ("500 iterações" 44,841 °C contra "convergido" 33,005 °C), e o
  modelo em elementos finitos do mesmo arquivo dá 34,30 °C. Ver o README.
-/
import Kaelix.Racional

namespace Kaelix

set_option maxRecDepth 4000000

namespace Termica

open Q Intv

/-! ## Geometria e propriedades -/

/-- Condutividade térmica do ASA, W/(m·K). -/
def kASA : Intv := qdi 17 2
/-- Condutividade do alumínio, W/(m·K). -/
def kAL : Intv := qi 205
/-- Seção do caminho condutivo (ressalto Ø28 mm), em m². -/
def aSpigot : Intv := piI * qdi 14 3 ^ 2
/-- Área externa de troca com o ar: quatro paredes de 50 × 78 mm e a tampa. -/
def aExt : Intv := 4 * (qdi 50 3 * qdi 78 3) + qdi 50 3 ^ 2
/-- Emissividade de plástico fosco. -/
def eps : Intv := qdi 9 1
/-- Constante de Stefan-Boltzmann, W/(m²·K⁴). -/
def sigma : Intv := qdi 567 10
/-- Ambiente industrial adotado, °C. -/
def tAmb : Q := 30

/-- Resistência de condução de um elo, K/W. -/
def rCond (L : Intv) (k : Intv) : Intv := L / (k * aSpigot)

/-- Caminho em ASA: base de 6 mm mais ressalto de 3,3 mm. -/
def rASA : Intv := rCond (qdi 6 3) kASA + rCond (qdi 33 4) kASA
/-- O mesmo caminho em alumínio. -/
def rAL : Intv := rCond (qdi 6 3) kAL + rCond (qdi 33 4) kAL
/-- Base de alumínio com quebra térmica de 2 mm em ASA. -/
def rALiso : Intv := rCond (qdi 6 3) kAL + rCond (qdi 2 3) kASA + rCond (qdi 33 4) kAL

/-- 88,84 K/W. O TCC relata 88,8 K/W. -/
theorem resistencia_ASA : entre (dec 88843 3) rASA (dec 88845 3) := by decide
/-- 0,073 675 K/W. O TCC relata 0,074 K/W. -/
theorem resistencia_aluminio : entre (dec 736754 7) rAL (dec 736756 7) := by decide
/-- Razão entre as duas: 1205,9, que é a razão das condutividades. O TCC
    relata 1206 vezes. -/
theorem razao_das_resistencias : entre (dec 12058 1) (rASA / rAL) (dec 12059 1) := by decide
/-- Quebra térmica de 2 mm: 19,18 K/W. -/
theorem resistencia_com_quebra : entre (dec 19179 3) rALiso (dec 19181 3) := by decide

/-! ## Balanço em regime permanente -/

/-- Coeficiente da correlação de convecção natural. -/
def coefConv : Intv := qdi 142 2
/-- Argumento da raiz quarta: (T − T_amb)/0,05. -/
def argConv (T : Q) : Intv := (pt T - pt tAmb) / qdi 5 2

/-- Enquadramentos verificados da raiz quarta, um por temperatura avaliada. -/
def u58 : Intv := ⟨dec 27596690 7, dec 27596691 7⟩
def u60 : Intv := ⟨dec 27831576 7, dec 27831577 7⟩
def u62 : Intv := ⟨dec 28060662 7, dec 28060663 7⟩
def u294 : Intv := ⟨dec 41408245 7, dec 41408246 7⟩
def u300 : Intv := ⟨dec 41617914 7, dec 41617915 7⟩
def u978 : Intv := ⟨dec 55922259 7, dec 55922260 7⟩
def u982 : Intv := ⟨dec 55979352 7, dec 55979353 7⟩
def u200 : Intv := ⟨dec 37606030 7, dec 37606031 7⟩
def u206 : Intv := ⟨dec 37884957 7, dec 37884958 7⟩

theorem raizes_quartas_corretas :
    ehRaiz4 (argConv (dec 329 1)) u58 ∧ ehRaiz4 (argConv 33) u60
    ∧ ehRaiz4 (argConv (dec 331 1)) u62 ∧ ehRaiz4 (argConv (dec 447 1)) u294
    ∧ ehRaiz4 (argConv 45) u300 ∧ ehRaiz4 (argConv (dec 789 1)) u978
    ∧ ehRaiz4 (argConv (dec 791 1)) u982 ∧ ehRaiz4 (argConv 40) u200
    ∧ ehRaiz4 (argConv (dec 403 1)) u206 := by decide

/-- Calor dissipado para o ar: convecção natural mais radiação. -/
def qSaida (T : Q) (u : Intv) : Intv :=
  coefConv * u * aExt * (pt T - pt tAmb)
    + eps * sigma * aExt * ((pt T + qdi 27315 2) ^ 4 - (pt tAmb + qdi 27315 2) ^ 4)

/-- Resíduo do balanço: positivo, a temperatura sobe; negativo, desce. -/
def residuo (tCarcaca : Q) (R : Intv) (T : Q) (u : Intv) : Intv :=
  (pt tCarcaca - pt T) / R - qSaida T u

/-! ### Base em ASA, carcaça a 80 °C -/

/-- Em 32,9 °C o interior ainda aquece. -/
theorem asa_sobe_em_32_9 : 0 < (residuo 80 rASA (dec 329 1) u58).lo := by decide
/-- Em 33,1 °C já esfria. Logo a temperatura interna de equilíbrio está entre
    32,9 °C e 33,1 °C — isto é, 33,0 °C. -/
theorem asa_desce_em_33_1 : (residuo 80 rASA (dec 331 1) u62).hi < 0 := by decide

/-- REFUTAÇÃO do valor relatado: em 44,7 °C o balanço já é negativo por larga
    margem, então a raiz não pode estar em 44,8 °C. -/
theorem refuta_44_8 : (residuo 80 rASA (dec 447 1) u294).hi < 0 := by decide

/-! ### O limite da bateria

    A restrição de carga da célula de polímero de lítio é 45 °C. O TCC afirma
    que essa temperatura interna é alcançada com carcaça em torno de 81 °C. -/

/-- Com base em ASA, nem carcaça a 90 °C — o pior caso de projeto — leva o
    interior a 45 °C: o resíduo em 45 °C continua negativo. A afirmação de que
    a bateria é atingida com carcaça a 81 °C não se sustenta nesta
    configuração. -/
theorem asa_nao_atinge_45_nem_com_carcaca_90 :
    (residuo 90 rASA 45 u300).hi < 0 := by decide

/-- Com base de ALUMÍNIO, porém, a restrição é real e apertada: carcaça a
    46 °C já leva o interior a 45 °C. A conclusão qualitativa do TCC — a
    bateria é o elo térmico mais frágil — vale para a variante metálica, que é
    justamente a que a análise mecânica recomenda. -/
theorem aluminio_atinge_45_com_carcaca_46 :
    0 < (residuo 46 rAL 45 u300).lo := by decide

/-! ### Base de alumínio, carcaça a 80 °C -/

/-- Raiz entre 78,9 °C e 79,1 °C: confirma os 79,0 °C relatados. Com o caminho
    metálico o interior praticamente acompanha a carcaça. -/
theorem aluminio_79 :
    0 < (residuo 80 rAL (dec 789 1) u978).lo
    ∧ (residuo 80 rAL (dec 791 1) u982).hi < 0 := by decide

/-! ### Quebra térmica de 2 mm -/

/-- Raiz entre 40,0 °C e 40,3 °C. O relatório de origem registra 47,1 °C para
    esta configuração; o valor vem da mesma iteração não convergida. A
    conclusão de projeto — a quebra térmica recupera quase todo o isolamento
    mantendo o ganho de rigidez — é preservada, e reforçada. -/
theorem quebra_termica :
    0 < (residuo 80 rALiso 40 u200).lo
    ∧ (residuo 80 rALiso (dec 403 1) u206).hi < 0 := by decide

/-! ## Autoaquecimento

    Resistência do interior para o ar, 1/[(h_c + h_rad)·A_ext], com
    h_rad ≈ 4εσT³ (linearização com erro abaixo de 1 % nesta faixa). -/

def hRad (T : Q) : Intv := 4 * eps * sigma * (pt T + qdi 27315 2) ^ 3
def rExterna (T : Q) (u : Intv) : Intv := 1 / ((coefConv * u + hRad T) * aExt)

/-- Potência média do circuito: 2,0 mW. -/
def potencia : Intv := qdi 2 3
/-- Elevação de temperatura devida ao próprio circuito. -/
def deltaAuto : Intv := potencia * rExterna 33 u60

/-- 0,011 °C. O TCC relata 0,01 °C: o autoaquecimento é irrelevante e todo o
    calor vem de fora. Esta conclusão não depende do valor divergente acima —
    ela vale tanto a 33 °C quanto a 44,8 °C. -/
theorem autoaquecimento_desprezivel : entre (dec 112 4) deltaAuto (dec 113 4) := by decide
theorem autoaquecimento_abaixo_de_um_centesimo_de_grau :
    deltaAuto.hi < dec 2 2 := by decide

end Termica
end Kaelix
