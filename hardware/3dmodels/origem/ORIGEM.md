# Modelos 3D de terceiros

A biblioteca do KiCad não traz corpo 3D para três footprints deste projeto —
nem a instalação local nem o repositório oficial `kicad-packages3D` têm
ESP32-S3-WROOM-1U, Ai-Thinker Ra-02 ou JST S2B-PH-SM4-TB. Os arquivos desta
pasta vieram da comunidade e estão AQUI COMO BAIXADOS, sem edição.

As versões alinhadas ficam um nível acima e são geradas por
`hardware/gen_3dmodels.py`, que aplica a transformação e CONFERE as cotas
contra o footprint. Nenhum arquivo desta pasta é usado direto pela placa.

| arquivo | componente | origem | licença |
|---|---|---|---|
| `wroom1u.step` | U1 ESP32-S3-WROOM-1U | [Lambosaurus/KicadLib](https://github.com/Lambosaurus/KicadLib) `Step/module/ESP32-S3-WROOM-1U.STEP` | MIT |
| `ra02.step` | U3 Ai-Thinker Ra-02 | [mithro/esp32-to-433mhz](https://github.com/mithro/esp32-to-433mhz) `hardware/3d/sx1278-lora-module.step` | Apache-2.0 |
| `jst.step` | J1 JST S2B-PH-SM4-TB | [arturo182/kicad-modules](https://github.com/arturo182/kicad-modules) `packages3D/Connector.3dshapes/S2B-PH-SM4-TB.step` | MIT |
| `lipo-2000mah-adafruit2011.step` | célula de referência do orçamento de energia | [adafruit/Adafruit_CAD_Parts](https://github.com/adafruit/Adafruit_CAD_Parts) `2011 2000mAh Battery` | MIT |
| `lipo-500mah-adafruit1578.step` | maior célula de catálogo que entra no vão | [adafruit/Adafruit_CAD_Parts](https://github.com/adafruit/Adafruit_CAD_Parts) `1578 500mAh battery` | MIT |

## Integridade

    06037d05aaa1940127b69baadd63fcbb76ba9f7f69717f7789735810c0756484  jst.step
    cde1f2fe047ceeaed014af076b08a75d97e699aa761d864a24c9a768c525e235  ra02.step
    f913932e97594461a5971a40dff8d53c90be6c1a7bb2da2fd58d6540b52c06bc  wroom1u.step

O `wroom1u.step` veio por Git LFS; o SHA256 acima confere com o `oid` do
ponteiro no repositório.

## O que precisou ser corrigido em cada um

Medido antes de usar, contra as cotas do footprint do projeto:

    WROOM-1U   18,00 x  3,35 x 19,20    deitado: Y é a espessura e Z o comprimento
    Ra-02      17,00 x 16,50 x  3,20    girado 90 graus, origem no canto (+8,50, -8,25)
    JST PH      7,90 x  8,65 x  5,60    alinhado; nenhuma transformação

Modelo de terceiro com eixo trocado é pior que modelo ausente: ele aparece,
parece certo de longe e mente sobre a altura. Por isso a conferência de cotas
está no gerador e falha a compilação, em vez de ficar num comentário.
