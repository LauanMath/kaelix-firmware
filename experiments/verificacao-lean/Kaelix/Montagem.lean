/-
  Kaelix/Montagem.lean — o invólucro como elo da cadeia de medição.

  Verifica os números de §4.2.3 do TCC (procedência E: modelagem sobre as
  cotas do desenho), pelas fórmulas fechadas da Eq. 3.3:

      k_base  = 16π𝒟/a²,   𝒟 = E h³ / [12(1−ν²)]      placa circular engastada
      k_res   = EA/L                                    ressalto em compressão
      k_corpo = 3EI/L³,    I = [ℓ⁴ − (ℓ−2t)⁴]/12        viga tubular engastada
      1/k     = Σ 1/kᵢ                                  molas em série
      f_n     = (1/2π)·√(k/m)                           um grau de liberdade
      T(f)    = 1/√[(1−r²)² + (2ζr)²],  r = f/f_n       transmissibilidade

  Nada aqui é ensaio: são as cotas do desenho e o módulo de folha do material.
  A verificação é de que os números relatados decorrem destas fórmulas, não de
  que o invólucro real se comporte assim — as condições de contorno
  idealizadas estão declaradas em §3.4 do TCC.

  Unidades SI ao longo de todo o arquivo.
-/
import Kaelix.Racional

set_option maxRecDepth 4000000

namespace Kaelix
namespace Montagem

open Q Intv

/-! ## Cotas e materiais -/

/-- Módulo de elasticidade do ASA impresso, 2,0 GPa (valor de folha, maciço). -/
def eASA : Intv := qi 2000000000
/-- Alumínio, 69 GPa. -/
def eAL : Intv := qi 69000000000
/-- Aço, 200 GPa. -/
def eACO : Intv := qi 200000000000
/-- Coeficiente de Poisson do ASA. -/
def nu : Intv := qdi 35 2
/-- Massa suspensa no caminho: 118 g. -/
def massa : Intv := qdi 118 3

/-- Espessura efetiva da base, 6 mm. -/
def hBase : Intv := qdi 6 3
/-- Raio efetivo da base em flexão: raio do ressalto + 13 mm = 27 mm. -/
def aBase : Intv := qdi 27 3
/-- Ressalto de centragem: Ø28 mm, 3,3 mm de altura. -/
def dRessalto : Intv := qdi 28 3
def lRessalto : Intv := qdi 33 4
/-- Corpo tubular: 50 mm de lado, parede 3,5 mm, 78 mm de altura. -/
def ladoCorpo : Intv := qdi 50 3
def paredeCorpo : Intv := qdi 35 4
def altCorpo : Intv := qdi 78 3

/-! ## Rigidez de cada elo -/

/-- Rigidez flexional da placa, 𝒟 = E h³/[12(1−ν²)]. -/
def rigidezFlexional (E : Intv) : Intv := E * hBase ^ 3 / (12 * (1 - nu ^ 2))

/-- Base como placa circular engastada com carga central: k = 16π𝒟/a². -/
def kBase (E : Intv) : Intv := 16 * piI * rigidezFlexional E / aBase ^ 2

/-- Ressalto em compressão axial: k = EA/L. -/
def kRessalto (E : Intv) : Intv :=
  E * (piI * (dRessalto / 2) ^ 2) / lRessalto

/-- Momento de inércia da seção tubular quadrada. -/
def inerciaCorpo : Intv := (ladoCorpo ^ 4 - (ladoCorpo - 2 * paredeCorpo) ^ 4) / 12

/-- Corpo como viga tubular engastada com carga na ponta: k = 3EI/L³. -/
def kCorpo (E : Intv) : Intv := 3 * E * inerciaCorpo / altCorpo ^ 3

/-- Associação em série dos três elos. -/
def kTotal (E : Intv) : Intv :=
  1 / (1 / kBase E + 1 / kRessalto E + 1 / kCorpo E)

theorem elos_positivos :
    positivo (kBase eASA) ∧ positivo (kRessalto eASA) ∧ positivo (kCorpo eASA) := by decide

/-- Rigidez do caminho em ASA: 1,446 3 MN/m. O TCC relata 1,45·10⁶ N/m. -/
theorem rigidez_do_caminho : entre 1446297 (kTotal eASA) 1446298 := by decide

/-! ## Frequência de montagem

    f_n = (1/2π)√(k/m). Enunciada como enquadramento da RAIZ de k/(m(2π)²):
    nenhum número real aparece, e π entra pelo intervalo `piI`. -/

/-- Quadrado da frequência de montagem, em Hz². -/
def fnQuadrado (E : Intv) : Intv := kTotal E / (massa * (2 * piI) ^ 2)

/-- Valor relatado no TCC: 557 Hz. Enquadramento verificado: 557,19–557,20. -/
theorem freq_montagem_ASA : ehRaiz (fnQuadrado eASA) ⟨dec 55719 2, dec 55720 2⟩ := by decide

/-- Cai dentro da banda que o dispositivo pretende medir (até 500 Hz é a banda
    do sensor; até 1000 Hz, a exigida pela norma ao instrumento). -/
theorem freq_montagem_dentro_da_banda_iso : entre 0 (fnQuadrado eASA) (1000 * 1000) := by decide

/-- A regra prática da acelerometria pede f_n ≥ 3 × a maior frequência de
    interesse, isto é, 3 kHz para a banda normativa. O obtido reprova por
    fator maior que cinco: 5 × 557,2 < 3000. -/
theorem reprova_regra_3x_por_fator_5 :
    ehRaiz (fnQuadrado eASA) ⟨dec 55719 2, dec 55720 2⟩ ∧ (5 : Q) * dec 55720 2 < 3000 := by
  decide

/-! ## Onde está a flexibilidade -/

def flexTotal (E : Intv) : Intv := 1 / kBase E + 1 / kRessalto E + 1 / kCorpo E
def fracaoBase (E : Intv) : Intv := (1 / kBase E) / flexTotal E * 100
def fracaoRessalto (E : Intv) : Intv := (1 / kRessalto E) / flexTotal E * 100
def fracaoCorpo (E : Intv) : Intv := (1 / kCorpo E) / flexTotal E * 100

/-- Base 51,1 %, ressalto 0,4 %, corpo 48,5 % — como relatado no TCC. -/
theorem decomposicao_da_flexibilidade :
    entre (dec 5112 2) (fracaoBase eASA) (dec 5113 2)
    ∧ entre (dec 387 3) (fracaoRessalto eASA) (dec 388 3)
    ∧ entre (dec 4848 2) (fracaoCorpo eASA) (dec 4849 2) := by decide

/-- As frações somam 100 %, o que confere a decomposição. -/
theorem fracoes_somam_100 :
    entre (dec 9999 2) (fracaoBase eASA + fracaoRessalto eASA + fracaoCorpo eASA)
      (dec 10001 2) := by decide

/-! ## Transmissibilidade de base -/

/-- Amortecimento adotado para o ASA. -/
def zeta : Intv := qdi 3 2

/-- r² = (f/f_n)² = (2πf)²·m/k, sem calcular f_n. -/
def r2 (E : Intv) (f : Q) : Intv := (2 * piI * pt f) ^ 2 * massa / kTotal E

/-- Denominador de T²: (1−r²)² + (2ζr)². -/
def gDen (E : Intv) (f : Q) : Intv := (1 - r2 E f) ^ 2 + 4 * zeta ^ 2 * r2 E f

/-- T² = 1/g. -/
def tQuad (E : Intv) (f : Q) : Intv := 1 / gDen E f

/-- A 500 Hz, o sensor lê 4,95 vezes o que o motor produz. O TCC relata
    "aproximadamente cinco vezes". -/
theorem transmissibilidade_em_500 :
    ehRaiz (tQuad eASA 500) ⟨dec 4948 3, dec 4949 3⟩ := by decide

/-! ### Onde o erro de amplitude passa de 10 %

    Erro > 10 % ⟺ T > 1,1 ⟺ T² > 1,21 ⟺ g < 1/1,21. Como T é crescente em f
    abaixo da ressonância, basta localizar a travessia entre dois inteiros. -/

/-- Em 168 Hz o erro ainda NÃO chegou a 10 %. -/
theorem erro_abaixo_de_10_em_168 : (1 / dec 121 2 : Q) < (gDen eASA 168).lo := by decide
/-- Em 169 Hz já passou. A travessia está em (168, 169) Hz; o TCC escreve
    168 Hz, que é o valor truncado. -/
theorem erro_acima_de_10_em_169 : (gDen eASA 169).hi < (1 / dec 121 2 : Q) := by decide

/-! ## Sensibilidade e materiais alternativos -/

/-- Dobrar a espessura da base (6 → 12 mm) leva f_n apenas a 749,5 Hz: o corpo
    tubular continua limitando. O TCC relata 750 Hz. -/
def hBaseDobrada : Intv := qdi 12 3
def kBaseDobrada : Intv := 16 * piI * (eASA * hBaseDobrada ^ 3 / (12 * (1 - nu ^ 2))) / aBase ^ 2
def fnQuadradoBaseDobrada : Intv :=
  (1 / (1 / kBaseDobrada + 1 / kRessalto eASA + 1 / kCorpo eASA)) / (massa * (2 * piI) ^ 2)

theorem base_dobrada_nao_resolve :
    ehRaiz fnQuadradoBaseDobrada ⟨dec 74953 2, dec 74954 2⟩ := by decide

/-- A mesma geometria em alumínio: 3272,8 Hz. O TCC relata 3273 Hz. -/
theorem freq_montagem_aluminio :
    ehRaiz (fnQuadrado eAL) ⟨dec 327278 2, dec 327279 2⟩ := by decide

/-- Em aço, 5572,0 Hz. -/
theorem freq_montagem_aco :
    ehRaiz (fnQuadrado eACO) ⟨dec 557195 2, dec 557197 2⟩ := by decide

/-- O alumínio atende a regra de 3× para a banda normativa; o ASA não. -/
theorem aluminio_atende_regra_3x : (3000 : Q) * 3000 < (fnQuadrado eAL).lo := by decide
theorem asa_nao_atende_regra_3x : (fnQuadrado eASA).hi < (3000 : Q) * 3000 := by decide

/-! ## Hipótese descartada: modos próprios dos painéis

    Placa retangular simplesmente apoiada, modo (1,1):
        f = (π/2)·√(𝒟/(ρh))·(1/a² + 1/b²). -/

/-- Massa específica do ASA. -/
def rhoASA : Intv := qi 1070
/-- Espessura de parede. -/
def hPainel : Intv := qdi 35 4

def fPainelQuadrado (a b : Intv) : Intv :=
  (piI / 2) ^ 2 * ((eASA * hPainel ^ 3 / (12 * (1 - nu ^ 2))) / (rhoASA * hPainel))
    * (1 / a ^ 2 + 1 / b ^ 2) ^ 2

/-- O painel mais baixo é a parede lateral (50 × 78 mm): 1307,2 Hz. -/
theorem painel_lateral :
    ehRaiz (fPainelQuadrado (qdi 50 3) (qdi 78 3)) ⟨dec 130724 2, dec 130725 2⟩ := by decide

/-- Fica acima da banda normativa inteira — a hipótese de ressonância de
    painel dentro da banda é descartada por margem de 30 %. -/
theorem painel_acima_da_banda_iso :
    (1000 : Q) * 1000 < (fPainelQuadrado (qdi 50 3) (qdi 78 3)).lo := by decide
theorem painel_acima_de_1300 :
    (1300 : Q) * 1300 < (fPainelQuadrado (qdi 50 3) (qdi 78 3)).lo := by decide

/-! ## Força inercial no pior caso normativo

    28 mm/s eficazes a 1000 Hz é o extremo da faixa considerada; a aceleração
    correspondente é a = 2πf·v. -/

def vSevero : Intv := qdi 28 3        -- 28 mm/s, em m/s
def fSevero : Intv := qi 1000
def aceleracaoSevera : Intv := 2 * piI * fSevero * vSevero
def forcaInercial : Intv := massa * aceleracaoSevera

/-- 175,9 m/s², isto é 17,9 g. -/
theorem aceleracao_severa : entre (dec 17592 2) aceleracaoSevera (dec 17594 2) := by decide
/-- Força inercial de 20,8 N sobre a fixação magnética. -/
theorem forca_inercial_20_8N : entre (dec 2075 2) forcaInercial (dec 2076 2) := by decide

end Montagem
end Kaelix
