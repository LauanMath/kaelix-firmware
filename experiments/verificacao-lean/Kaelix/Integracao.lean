/-
  Kaelix/Integracao.lean — conversão normativa de aceleração para velocidade.

  Verifica os números de §4.3.1 do TCC (Tabela 4.2). Duas coisas distintas:

  · O VALOR DE REFERÊNCIA 6,7524 mm/s é analítico e é verificado aqui de ponta
    a ponta: é a raiz de a²/(2(2πf)²) com a = 3,0 m/s² e f = 50 Hz.

  · Os resultados das cinco variantes de integração (11,69 / 17,31 / 6,7525 /
    55,08 mm/s) são de SIMULAÇÃO sobre sinal sintetizado (procedência S), e
    portanto NÃO são reproduzíveis por aritmética fechada. O que se verifica
    aqui é a conta que explica o maior deles: a deriva que um viés contínuo
    injeta na integração no tempo. Para janela T, a velocidade acumulada é
    a₀·t, cujo valor eficaz em [0, T] é a₀T/√3 — e é essa, não o sinal, que
    domina o resultado.

  Unidades SI: aceleração em m/s², velocidade em m/s. Em comentário, mm/s.
-/
import Kaelix.Racional

namespace Kaelix
namespace Integracao

open Q Intv

/-! ## Sinal de referência -/

/-- Amplitude de pico da senoide de teste: 3,0 m/s². -/
def aPico : Intv := qi 3
/-- Frequência da senoide de teste: 50 Hz. -/
def fTeste : Intv := qi 50

/-- Quadrado da velocidade eficaz analítica: v² = a²/(2·(2πf)²), em (m/s)².
    A integração de uma senoide divide a amplitude por 2πf; o valor eficaz
    divide por √2. Aqui as duas coisas aparecem juntas, ao quadrado, para que
    nenhuma raiz precise ser tomada. -/
def vRms2 : Intv := aPico ^ 2 / (2 * (2 * piI * fTeste) ^ 2)

theorem denominador_nao_nulo : naoContemZero (2 * (2 * piI * fTeste) ^ 2) := by decide

/-- Valor relatado no TCC, enquadrado: 6,752_37 a 6,752_38 mm/s. -/
def vRmsRelatado : Intv := ⟨dec 67523700 10, dec 67523800 10⟩

/-- O valor analítico exato está dentro do enquadramento relatado. Com quatro
    casas, 6,7524 mm/s — que é como o TCC o escreve. -/
theorem vrms_analitico : ehRaiz vRms2 vRmsRelatado := by decide

/-- E o mesmo, na forma em que o texto o usa: entre 6,7523 e 6,7525 mm/s. -/
theorem vrms_arredonda_para_6_7524 : ehRaiz vRms2 ⟨dec 67523 7, dec 67525 7⟩ := by decide

/-! ## A deriva do viés contínuo

    Integração no tempo acumula o viés: v(t) = v_osc(t) + a₀t. O termo a₀t tem
    valor eficaz a₀T/√3 na janela [0, T], e cresce SEM LIMITE com a janela. É
    por isso que o filtro passa-alta não resolve: ele não impede a soma
    cumulativa de acumular o próprio transiente de borda. -/

/-- Viés contínuo dentro da especificação do MPU6050: 0,02 m/s². -/
def vies : Q := dec 2 2

/-- Quadrado do valor eficaz da deriva a₀t na janela [0, T]. -/
def derivaRms2 (T : Q) : Intv := pt ((vies * T) ^ 2 / 3)

/-- Janela de 4 s: deriva de 46,188 mm/s. -/
theorem deriva_4s : ehRaiz (derivaRms2 4) ⟨dec 46188 6, dec 46189 6⟩ := by decide
/-- Janela de 6 s: deriva de 69,282 mm/s. -/
theorem deriva_6s : ehRaiz (derivaRms2 6) ⟨dec 69282 6, dec 69283 6⟩ := by decide

/-- O valor relatado na Tabela 4.2 para a variante com viés — 55,08 mm/s —
    está dentro da faixa que a fórmula fechada prevê para janelas de 4 a 6 s.
    O TCC não declara a janela usada na simulação; esta é a verificação
    possível sem ela, e é a que se afirma: ordem de grandeza e mecanismo. -/
theorem relatado_55_08_na_faixa :
    dec 46188 6 < dec 5508 5 ∧ dec 5508 5 < dec 69282 6 := by decide

/-- A deriva sozinha supera em mais de seis vezes o valor correto inteiro.
    Isto é o achado: o erro não é de precisão, é de mecanismo. -/
theorem deriva_domina_o_sinal : 6 * vRmsRelatado.hi < dec 46188 6 := by decide

/-! ## Consequência normativa

    Fronteiras de zona da ISO 10816-3 / 20816-3, classe III (máquina grande
    sobre fundação rígida), em mm/s. -/

def zonaAB : Q := dec 18 1     -- 1,8 mm/s
def zonaBC : Q := dec 45 1     -- 4,5 mm/s
def zonaCD : Q := dec 112 1    -- 11,2 mm/s

/-- Um sinal em zona A lido sob viés por integração no tempo aparece acima do
    limite C/D — e com folga de mais de quatro vezes. A deriva é aditiva e
    independente do sinal, então a conclusão não depende de qual sinal em zona
    A se considere. -/
theorem zona_A_vira_alem_de_D : 4 * zonaCD < 1000 * dec 46188 6 := by decide

/-- O valor correto, 6,75 mm/s, fica entre B/C e C/D: zona C. -/
theorem referencia_em_zona_C :
    zonaBC < 1000 * vRmsRelatado.lo ∧ 1000 * vRmsRelatado.hi < zonaCD := by decide

/-- Por que a integração na frequência é imune ao viés: o termo contínuo está
    em 0 Hz e a máscara que a própria norma impõe começa em 10 Hz. Este
    enunciado é trivial de propósito — ele É o argumento inteiro, e o que a
    verificação faz é registrar que a premissa usada é a da norma. -/
def isoBaixo : Q := 10
theorem continua_fora_da_mascara : (0 : Q) < isoBaixo := by decide

end Integracao
end Kaelix
