/-
  Kaelix/Racional.lean — o núcleo aritmético das verificações.

  Duas camadas, nesta ordem:

  1. `Q`, racional exato representado como par de inteiros `num/den`, SEM
     normalização por máximo divisor comum. A normalização exigiria `Nat.gcd`,
     que é definido por recursão bem fundada e não reduz no núcleo (*kernel*)
     do Lean; sem ela, `decide` fecha cada comparação por multiplicação
     cruzada de inteiros, que o núcleo avalia com GMP. O preço é denominador
     grande, e não erro: toda conta aqui é exata.

  2. `Intv`, intervalo racional `[lo, hi]`, com aritmética de intervalos.
     É o que permite tratar π, raízes quadradas e raízes quartas sem números
     reais: cada grandeza irracional entra como um intervalo que a contém, e
     toda operação devolve um intervalo que contém o resultado verdadeiro.
     A conclusão `lo < x < hi` vale então para o valor real, não para um
     representante escolhido.

  BASE DE CONFIANÇA. O que o núcleo do Lean verifica é a aritmética. O que
  fica fora dele, e precisa ser lido pelo revisor humano:
    · as DEFINIÇÕES dos modelos físicos nos demais arquivos correspondem às
      fórmulas do Capítulo 3;
    · o enquadramento de π em `piI` (dígitos de constante conhecida);
    · a solidez da aritmética de intervalos implementada abaixo;
    · onde se afirma que uma raiz de equação está entre dois valores, a
      monotonicidade da função no intervalo, argumentada em comentário.
  Nenhum resultado aqui é medição, e nenhum valida o modelo físico: o que se
  verifica é que os números relatados decorrem das fórmulas declaradas.
-/

namespace Kaelix

/-- Racional exato `num/den`, com `den > 0` mantido por construção. -/
structure Q where
  num : Int
  den : Int
deriving Repr, DecidableEq

namespace Q

/-- Construtor que normaliza apenas o SINAL do denominador. -/
def mk' (n d : Int) : Q := if d < 0 then ⟨-n, -d⟩ else ⟨n, d⟩

instance : OfNat Q n := ⟨⟨Int.ofNat n, 1⟩⟩
instance : Add Q := ⟨fun a b => ⟨a.num * b.den + b.num * a.den, a.den * b.den⟩⟩
instance : Mul Q := ⟨fun a b => ⟨a.num * b.num, a.den * b.den⟩⟩
instance : Neg Q := ⟨fun a => ⟨-a.num, a.den⟩⟩
instance : Sub Q := ⟨fun a b => a + (-b)⟩
instance : Div Q := ⟨fun a b => mk' (a.num * b.den) (a.den * b.num)⟩

instance : LT Q := ⟨fun a b => a.num * b.den < b.num * a.den⟩
instance : LE Q := ⟨fun a b => a.num * b.den ≤ b.num * a.den⟩
instance (a b : Q) : Decidable (a < b) :=
  inferInstanceAs (Decidable (a.num * b.den < b.num * a.den))
instance (a b : Q) : Decidable (a ≤ b) :=
  inferInstanceAs (Decidable (a.num * b.den ≤ b.num * a.den))

def pow (a : Q) : Nat → Q
  | 0 => 1
  | n + 1 => a * pow a n
instance : HPow Q Nat Q := ⟨pow⟩

/-- Igualdade de VALOR (multiplicação cruzada), não de representação. -/
def eqv (a b : Q) : Prop := a.num * b.den = b.num * a.den
instance (a b : Q) : Decidable (eqv a b) :=
  inferInstanceAs (Decidable (a.num * b.den = b.num * a.den))

@[inherit_doc] infix:50 " ≡ " => eqv

/-- Denominador positivo: garante que `<`, `≤` e `≡` significam o que dizem. -/
def ok (a : Q) : Prop := 0 < a.den
instance (a : Q) : Decidable (ok a) := inferInstanceAs (Decidable (0 < a.den))

/-- `dec n e` é `n · 10⁻ᵉ`. Ex.: `dec 203 3` é 0,203. -/
def dec (n : Int) (e : Nat) : Q := ⟨n, (10 : Int) ^ e⟩

/-- Só para inspeção com `#eval`; nenhuma prova depende disto. A conversão
    passa por uma divisão inteira com 18 casas porque, sem normalização,
    numerador e denominador estouram a faixa de `Float` muito antes de o
    VALOR estourar. -/
def toFloat (a : Q) : Float :=
  let escala : Int := 10 ^ 18
  if a.den = 0 then 0.0 else Float.ofInt (a.num * escala / a.den) / Float.ofInt escala

end Q

open Q

/-- Intervalo racional fechado `[lo, hi]`. Um valor real `x` é representado
    por qualquer intervalo com `lo ≤ x ≤ hi`. -/
structure Intv where
  lo : Q
  hi : Q
deriving Repr

namespace Intv

/-- Intervalo degenerado: um racional exato. -/
def pt (x : Q) : Intv := ⟨x, x⟩

instance : OfNat Intv n := ⟨pt (OfNat.ofNat n)⟩
instance : Coe Q Intv := ⟨pt⟩

instance : Add Intv := ⟨fun a b => ⟨a.lo + b.lo, a.hi + b.hi⟩⟩
instance : Neg Intv := ⟨fun a => ⟨-a.hi, -a.lo⟩⟩
instance : Sub Intv := ⟨fun a b => ⟨a.lo - b.hi, a.hi - b.lo⟩⟩

def qmin (a b : Q) : Q := if a ≤ b then a else b
def qmax (a b : Q) : Q := if a ≤ b then b else a

/-- Produto pelo caso geral: extremos entre os quatro produtos de pontas.
    Vale para qualquer sinal dos operandos. -/
instance : Mul Intv := ⟨fun a b =>
  let p1 := a.lo * b.lo
  let p2 := a.lo * b.hi
  let p3 := a.hi * b.lo
  let p4 := a.hi * b.hi
  ⟨qmin (qmin p1 p2) (qmin p3 p4), qmax (qmax p1 p2) (qmax p3 p4)⟩⟩

/-- Inverso. SÓ é enquadramento válido se `0 ∉ [lo, hi]`; use com
    `naoContemZero` verificado. -/
def inv (a : Intv) : Intv := ⟨1 / a.hi, 1 / a.lo⟩
instance : Div Intv := ⟨fun a b => a * inv b⟩

def pow (a : Intv) : Nat → Intv
  | 0 => 1
  | n + 1 => a * pow a n
instance : HPow Intv Nat Intv := ⟨pow⟩

/-- Predicados decidíveis usados nos enunciados. -/
def positivo (a : Intv) : Prop := 0 < a.lo
def naoContemZero (a : Intv) : Prop := 0 < a.lo ∨ a.hi < 0
/-- `entre lo a hi`: todo valor do intervalo está estritamente em `(lo, hi)`. -/
def entre (lo : Q) (a : Intv) (hi : Q) : Prop := lo < a.lo ∧ a.hi < hi
/-- `menorQue a b`: todo valor de `a` é menor que todo valor de `b`. -/
def menorQue (a b : Intv) : Prop := a.hi < b.lo

instance (a : Intv) : Decidable (positivo a) := inferInstanceAs (Decidable (0 < a.lo))
instance (a : Intv) : Decidable (naoContemZero a) :=
  inferInstanceAs (Decidable (0 < a.lo ∨ a.hi < 0))
instance (lo : Q) (a : Intv) (hi : Q) : Decidable (entre lo a hi) :=
  inferInstanceAs (Decidable (lo < a.lo ∧ a.hi < hi))
instance (a b : Intv) : Decidable (menorQue a b) := inferInstanceAs (Decidable (a.hi < b.lo))

/-- `ehRaiz x r`: o intervalo `r` contém √x, para `x ≥ 0`.
    Justificativa: `r.lo ≥ 0`, `r.lo² ≤ x.lo` e `x.hi ≤ r.hi²` implicam
    `r.lo ≤ √x.lo ≤ √x ≤ √x.hi ≤ r.hi`, por monotonicidade de `t ↦ t²` em
    `t ≥ 0`. É assim que a raiz quadrada entra sem números reais. -/
def ehRaiz (x r : Intv) : Prop := 0 ≤ r.lo ∧ r.lo ^ 2 ≤ x.lo ∧ x.hi ≤ r.hi ^ 2
instance (x r : Intv) : Decidable (ehRaiz x r) :=
  inferInstanceAs (Decidable (0 ≤ r.lo ∧ r.lo ^ 2 ≤ x.lo ∧ x.hi ≤ r.hi ^ 2))

/-- `ehRaiz4 x r`: o intervalo `r` contém a raiz quarta de `x`. Mesmo
    argumento, com `t ↦ t⁴` monótona em `t ≥ 0`. -/
def ehRaiz4 (x r : Intv) : Prop := 0 ≤ r.lo ∧ r.lo ^ 4 ≤ x.lo ∧ x.hi ≤ r.hi ^ 4
instance (x r : Intv) : Decidable (ehRaiz4 x r) :=
  inferInstanceAs (Decidable (0 ≤ r.lo ∧ r.lo ^ 4 ≤ x.lo ∧ x.hi ≤ r.hi ^ 4))

/-- Largura relativa, só para inspeção. -/
def toFloat (a : Intv) : Float × Float := (a.lo.toFloat, a.hi.toFloat)

end Intv

/-- π enquadrado em dez casas: 3,141592653589793… -/
def piI : Intv := ⟨Q.dec 31415926535 10, Q.dec 31415926536 10⟩

/-- Atalhos de leitura para os arquivos de modelo. -/
abbrev qd := Q.dec
def qi (n : Int) : Intv := Intv.pt ⟨n, 1⟩
def qdi (n : Int) (e : Nat) : Intv := Intv.pt (Q.dec n e)
def qfrac (n d : Int) : Intv := Intv.pt (Q.mk' n d)

end Kaelix
