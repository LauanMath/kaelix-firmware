/-
  Kaelix/Aquisicao.lean — o que a cadeia de aquisição permite medir.

  Verifica os números de §4.2 do TCC que decorrem de geometria de rolamento e
  de taxa de amostragem. Tudo aqui é racional exato: não entra π nem raiz, e
  por isso as frequências características saem como IGUALDADES, não como
  enquadramentos.

  Fonte dos parâmetros: Tabela 3.1 (caso de estudo), motor de 1750 rpm com
  rolamento SKF 6205, o mesmo do conjunto CWRU.
-/
import Kaelix.Racional

namespace Kaelix
namespace Aquisicao

open Q

/-! ## Parâmetros do caso de estudo -/

/-- Rotação nominal, em rpm. -/
def rotacaoRpm : Q := 1750
/-- Rotação em hertz: 29,1666… Hz. -/
def fr : Q := rotacaoRpm / 60
/-- Número de esferas do SKF 6205. -/
def nEsferas : Q := 9
/-- Razão entre diâmetro de esfera e diâmetro primitivo, d/D. -/
def razaoDiametros : Q := dec 203 3

/-- Taxa máxima do MPU6050, em hertz. -/
def fsDispositivo : Q := 1000
/-- Taxa da cadeia de referência de banda larga, em hertz. -/
def fsReferencia : Q := 20000
/-- Ressonância estrutural excitada pelos impactos, em hertz. -/
def fRessonancia : Q := 3500
/-- Extremos da banda exigida pela ISO 20816-3 ao instrumento, em hertz. -/
def isoBaixo : Q := 10
def isoAlto : Q := 1000

/-! ## Frequências características de defeito -/

/-- Passagem de esfera na pista externa: (N/2)·(1 − d/D)·f_r. -/
def bpfo : Q := (nEsferas / 2) * (1 - razaoDiametros) * fr
/-- Passagem de esfera na pista interna: (N/2)·(1 + d/D)·f_r. -/
def bpfi : Q := (nEsferas / 2) * (1 + razaoDiametros) * fr

/-- Frequência de Nyquist da cadeia do dispositivo. -/
def nyquist : Q := fsDispositivo / 2

theorem bpfo_ok : ok bpfo := by decide
theorem bpfi_ok : ok bpfi := by decide

/-- BPFO = 104,60625 Hz exatos. O TCC relata 104,6 Hz. -/
theorem bpfo_exata : bpfo ≡ ⟨16737, 160⟩ := by decide
theorem bpfo_arredonda_para_104_6 : dec 10460 2 < bpfo ∧ bpfo < dec 10461 2 := by decide

/-- BPFI = 157,89375 Hz exatos. O TCC relata 157,9 Hz. -/
theorem bpfi_exata : bpfi ≡ ⟨25263, 160⟩ := by decide
theorem bpfi_arredonda_para_157_9 : dec 15789 2 < bpfi ∧ bpfi < dec 15790 2 := by decide

/-- Rotação em hertz: 29,1666… O TCC relata 29,17 Hz. -/
theorem fr_arredonda_para_29_17 : dec 2916 2 < fr ∧ fr < dec 2917 2 := by decide

/-! ## O que cabe na banda

    O achado de §4.2 é uma separação de escalas: a TAXA DE REPETIÇÃO do
    defeito cabe na banda do dispositivo, e a PORTADORA que carrega a
    assinatura não cabe. As duas desigualdades abaixo são o achado inteiro. -/

theorem nyquist_500 : nyquist ≡ 500 := by decide

/-- A taxa de repetição do defeito está dentro da banda. -/
theorem bpfo_dentro_da_banda : bpfo < nyquist := by decide
theorem bpfi_dentro_da_banda : bpfi < nyquist := by decide

/-- A ressonância que carrega a evidência está fora. -/
theorem ressonancia_fora_da_banda : nyquist < fRessonancia := by decide

/-- E está fora por um fator sete exato: 3500 = 7 × 500. -/
theorem ressonancia_sete_vezes_nyquist : fRessonancia ≡ 7 * nyquist := by decide

/-- A banda exigida pela norma ao instrumento não é atendida: o dispositivo
    para em 500 Hz e a ISO 20816-3 pede resposta plana até 1000 Hz. É o que
    torna o truncamento violação de requisito, e não escolha de processamento. -/
theorem banda_iso_nao_atendida : nyquist < isoAlto := by decide
theorem metade_da_banda_iso : 2 * nyquist ≡ isoAlto := by decide

/-! ## Rebatimento (Eq. 3.2)

    Sem filtro passa-baixas configurado abaixo de f_s/2, uma componente em `f`
    é observada em |f − f_s·⌊f/f_s⌉|. Em inteiros, exato. -/

/-- Arredondamento ao inteiro mais próximo de `f/fs`, para `f, fs > 0`. -/
def arredonda (f fs : Int) : Int := (2 * f + fs) / (2 * fs)

/-- Frequência aparente após subamostragem sem filtro. -/
def fAparente (f fs : Int) : Int := (f - fs * arredonda f fs).natAbs

/-- A ressonância de 3,5 kHz reaparece EXATAMENTE em 500 Hz — sobre a própria
    frequência de Nyquist, onde nada existe fisicamente. -/
theorem alias_da_ressonancia : fAparente 3500 1000 = 500 := by decide

/-- Na cadeia de referência de 20 kHz a mesma componente não é rebatida. -/
theorem sem_alias_na_referencia : fAparente 3500 20000 = 3500 := by decide

/-- O rebatimento não é peculiaridade de 3,5 kHz: qualquer componente acima de
    Nyquist cai dentro da banda. Amostra de casos. -/
theorem alias_varios : fAparente 1500 1000 = 500 ∧ fAparente 2500 1000 = 500
    ∧ fAparente 1200 1000 = 200 ∧ fAparente 4300 1000 = 300 := by decide

end Aquisicao
end Kaelix
