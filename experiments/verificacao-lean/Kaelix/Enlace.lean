/-
  Kaelix/Enlace.lean — tempo no ar e orçamento de energia.

  Verifica os números de §4.4.2 do TCC. Este é o módulo mais forte da
  verificação: a fórmula de tempo no ar do SX127x e o orçamento de carga por
  ciclo são inteiramente racionais — não há π, raiz nem raiz de equação. Os
  tempos no ar saem como IGUALDADES EXATAS, e as autonomias como
  enquadramentos apertados por causa apenas do arredondamento da saída.

      T_sym = 2^SF / BW
      n     = 8 + ⌈(8·PL − 4·SF + 28 + 16·CRC) / (4(SF − 2·DE))⌉ · (CR + 4)
      T_ar  = (n_preâmbulo + 4,25)·T_sym + n·T_sym

  Parâmetros como fixados no firmware: PL = 20 bytes, preâmbulo 8 símbolos,
  BW = 125 kHz, CR = 4/5, CRC ligado. A fixação explícita desses parâmetros,
  em vez de herdá-los do padrão da biblioteca, é ela própria um resultado
  relatado no TCC.
-/
import Kaelix.Racional

namespace Kaelix
namespace Enlace

open Q

/-! ## Tempo no ar -/

def cargaUtilBytes : Nat := 20
def preambuloSimbolos : Nat := 8
def bandaKHz : Nat := 125
/-- Taxa de codificação 4/5 entra na fórmula como CR = 1. -/
def cr : Nat := 1
def crc : Nat := 1

/-- Divisão inteira para cima. -/
def divTeto (a b : Nat) : Nat := (a + b - 1) / b

/-- Otimização de baixa taxa, obrigatória em SF11 e SF12 a 125 kHz. -/
def deOpt (sf : Nat) : Nat := if sf ≥ 11 then 1 else 0

/-- Número de símbolos de carga útil. -/
def nSimbolos (sf : Nat) : Nat :=
  8 + divTeto (8 * cargaUtilBytes + 28 + 16 * crc - 4 * sf) (4 * (sf - 2 * deOpt sf)) * (cr + 4)

/-- Duração do símbolo, em segundos. -/
def tSimbolo (sf : Nat) : Q := ⟨(2 : Int) ^ sf, (bandaKHz : Int) * 1000⟩

/-- Tempo no ar, em segundos. -/
def tempoNoAr (sf : Nat) : Q := (dec 1225 2 + ⟨(nSimbolos sf : Int), 1⟩) * tSimbolo sf

theorem simbolos_por_sf : nSimbolos 7 = 43 ∧ nSimbolos 9 = 33 ∧ nSimbolos 12 = 28 := by decide

/-- SF9, o fator adotado: 185,344 ms exatos. O TCC relata 185 ms. -/
theorem tempo_no_ar_sf9 : tempoNoAr 9 ≡ dec 185344 6 := by decide
/-- SF7: 56,576 ms. -/
theorem tempo_no_ar_sf7 : tempoNoAr 7 ≡ dec 56576 6 := by decide
/-- SF12: 1318,912 ms. -/
theorem tempo_no_ar_sf12 : tempoNoAr 12 ≡ dec 1318912 6 := by decide

/-- O orçamento anterior assumia 150 ms sem derivação; o valor derivado dos
    parâmetros efetivamente fixados é 23 % maior. -/
theorem excede_os_150ms_assumidos : dec 150 3 < tempoNoAr 9 := by decide
theorem excede_em_mais_de_20_porcento : dec 12 1 * dec 150 3 < tempoNoAr 9 := by decide

/-! ## Orçamento de energia

    Correntes em mA, tempos em s, capacidade em mAh. -/

def iEsp32 : Q := 40
def iMpu6050 : Q := dec 39 1
def iRegulador : Q := dec 8 3
def iDeepSleep : Q := dec 10 3
def iLoraTx : Q := 90
def iLoraStandby : Q := dec 15 1
def iLoraSleep : Q := dec 2 4
def cicloS : Q := 600
def faseAtivaS : Q := 3
def capacidadeMah : Q := 2000
/-- Autodescarga da célula de polímero de lítio, ~2,5 %/mês. -/
def autodescargaMa : Q := dec 685 4

/-- Corrente média do ciclo: carga por ciclo dividida pelo período. -/
def correnteMedia (tTx iTx iRepousoAtivo iRepousoSleep : Q) : Q :=
  let qAtivo := (iEsp32 + iMpu6050 + iRepousoAtivo + iRegulador) * faseAtivaS
  let qTx := (iEsp32 + iMpu6050 + iTx + iRegulador) * tTx
  let qSleep := (iRepousoSleep + iDeepSleep + iRegulador) * cicloS
  (qAtivo + qTx + qSleep) / (faseAtivaS + tTx + cicloS)

/-- Autonomia em dias. -/
def autonomiaDias (tTx iTx iRepousoAtivo iRepousoSleep : Q) : Q :=
  capacidadeMah / (correnteMedia tTx iTx iRepousoAtivo iRepousoSleep + autodescargaMa) / 24

/-- Configuração do dispositivo: LoRa com rádio em sleep no repouso. -/
def autonomiaLoRa (sf : Nat) : Q :=
  autonomiaDias (tempoNoAr sf) iLoraTx iLoraStandby iLoraSleep

/-- SF7: 256,36 dias. O TCC relata 256 d no fator de espalhamento mais baixo. -/
theorem autonomia_sf7 : dec 25636 2 < autonomiaLoRa 7 ∧ autonomiaLoRa 7 < dec 25637 2 := by
  decide
/-- SF9, o adotado: 235,68 dias. O TCC relata 236 d. -/
theorem autonomia_sf9 : dec 23567 2 < autonomiaLoRa 9 ∧ autonomiaLoRa 9 < dec 23568 2 := by
  decide
/-- SF12: 137,91 dias. O TCC relata 138 d no fator mais alto. -/
theorem autonomia_sf12 : dec 13791 2 < autonomiaLoRa 12 ∧ autonomiaLoRa 12 < dec 13792 2 := by
  decide

/-- Ganho de sensibilidade entre os extremos, a 2,5 dB por passo de SF. -/
def ganhoDb (sfBaixo sfAlto : Nat) : Q := (⟨(sfAlto : Int) - (sfBaixo : Int), 1⟩ : Q) * dec 25 1
theorem ganho_entre_extremos : ganhoDb 7 12 ≡ dec 125 1 := by decide

/-- O custo do ganho: a autonomia cai abaixo de 55 % ao ir de SF7 a SF12. -/
theorem custo_do_ganho : 20 * autonomiaLoRa 12 < 11 * autonomiaLoRa 7 := by decide

/-! ### Comparações de §4.4.2 -/

/-- Rádio mantido em standby no repouso, em vez de sleep: 45,16 dias. O TCC
    relata 45 d. -/
def autonomiaSemSleep : Q := autonomiaDias (tempoNoAr 9) iLoraTx iLoraStandby iLoraStandby
theorem autonomia_sem_sleep :
    dec 4515 2 < autonomiaSemSleep ∧ autonomiaSemSleep < dec 4516 2 := by decide

/-- Wi-Fi, modelado em 5 s a 150 mA adicionais por transmissão: 43,92 dias.
    O TCC relata 44 d. -/
def autonomiaWifi : Q := autonomiaDias 5 150 0 0
theorem autonomia_wifi : dec 4391 2 < autonomiaWifi ∧ autonomiaWifi < dec 4392 2 := by decide

/-- O custo de deixar o rádio em standby equivale ao de adotar Wi-Fi — a
    afirmação do TCC, verificada: as duas autonomias diferem menos de 5 %. -/
theorem standby_equivale_a_wifi :
    20 * (autonomiaSemSleep - autonomiaWifi) < autonomiaWifi := by decide

/-- E o enlace adotado dura mais de cinco vezes o que duraria com Wi-Fi. -/
theorem lora_supera_wifi_cinco_vezes : 5 * autonomiaWifi < autonomiaLoRa 9 := by decide

end Enlace
end Kaelix
