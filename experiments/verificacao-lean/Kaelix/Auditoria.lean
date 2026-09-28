/-
  Kaelix/Auditoria.lean — o que a verificação depende, e os valores em decimal.

  Duas coisas, ambas visíveis na saída de `lake build`:

  1. `#print axioms`: toda prova deste projeto é por `decide`, isto é, por
     avaliação no núcleo do Lean. Nenhuma usa `sorry`, `Classical.choice`,
     `propext` ou `Quot.sound`. A saída abaixo registra isso por escrito, um
     teorema de cada módulo.

  2. `#eval`: os mesmos valores em decimal, para conferência a olho contra as
     tabelas do TCC. NENHUMA prova depende destes `#eval` — eles usam
     aritmética de ponto flutuante e estão aqui só para leitura.
-/
import Kaelix.Racional
import Kaelix.Aquisicao
import Kaelix.Integracao
import Kaelix.Montagem
import Kaelix.Termica
import Kaelix.Enlace

namespace Kaelix
namespace Auditoria

#print axioms Aquisicao.bpfo_exata
#print axioms Integracao.vrms_analitico
#print axioms Montagem.freq_montagem_ASA
#print axioms Termica.refuta_44_8
#print axioms Enlace.tempo_no_ar_sf9

open Q Intv

private def raizFloat (x : Intv) : Float := Float.sqrt x.lo.toFloat

-- Aquisição.
#eval (Aquisicao.bpfo.toFloat, Aquisicao.bpfi.toFloat, Aquisicao.nyquist.toFloat)
#eval Aquisicao.fAparente 3500 1000

-- Integração: velocidade eficaz analítica, em mm/s.
#eval raizFloat Integracao.vRms2 * 1000
-- Deriva de 0,02 m/s² em janela de 4 s e de 6 s, em mm/s.
#eval (raizFloat (Integracao.derivaRms2 4) * 1000, raizFloat (Integracao.derivaRms2 6) * 1000)

-- Montagem: rigidez em N/m e frequência em Hz.
#eval (Montagem.kTotal Montagem.eASA).toFloat
#eval (raizFloat (Montagem.fnQuadrado Montagem.eASA),
       raizFloat (Montagem.fnQuadrado Montagem.eAL),
       raizFloat (Montagem.fnQuadrado Montagem.eACO))
-- Frações de flexibilidade, em %.
#eval ((Montagem.fracaoBase Montagem.eASA).toFloat,
       (Montagem.fracaoRessalto Montagem.eASA).toFloat,
       (Montagem.fracaoCorpo Montagem.eASA).toFloat)
-- Transmissibilidade a 500 Hz.
#eval raizFloat (Montagem.tQuad Montagem.eASA 500)

-- Térmica: resistências em K/W e resíduos do balanço em W.
#eval (Termica.rASA.toFloat, Termica.rAL.toFloat, Termica.rALiso.toFloat)
-- Resíduo do balanço com carcaça a 80 °C e base em ASA, avaliado em 32,9 °C,
-- 33,1 °C e 44,7 °C. Os dois primeiros trocam de sinal — a raiz está entre
-- eles; o terceiro mostra a distância até o valor relatado no TCC.
#eval ((Termica.residuo 80 Termica.rASA (dec 329 1) Termica.u58).toFloat,
       (Termica.residuo 80 Termica.rASA (dec 331 1) Termica.u62).toFloat,
       (Termica.residuo 80 Termica.rASA (dec 447 1) Termica.u294).toFloat)

-- Enlace: tempo no ar em ms e autonomia em dias.
#eval ((Enlace.tempoNoAr 7).toFloat * 1000, (Enlace.tempoNoAr 9).toFloat * 1000,
       (Enlace.tempoNoAr 12).toFloat * 1000)
#eval ((Enlace.autonomiaLoRa 7).toFloat, (Enlace.autonomiaLoRa 9).toFloat,
       (Enlace.autonomiaLoRa 12).toFloat, Enlace.autonomiaSemSleep.toFloat,
       Enlace.autonomiaWifi.toFloat)

end Auditoria
end Kaelix
