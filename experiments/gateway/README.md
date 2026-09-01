# Gateway

Receptor dos pacotes do Kaelix: valida integridade, reconstrói o histórico por
dispositivo e decide quando abrir alerta.

Existe como componente separado porque três responsabilidades não cabem no nó.
O dispositivo não tem relógio — o contador de partida dá ordem, não instante.
Não sabe se um pacote seu chegou, então quem detecta lacuna na sequência é o
outro lado. E a regra de disparo do alerta precisa ser alterável sem regravar
cada aparelho fisicamente.

## Módulos

| Módulo | Responsabilidade |
|---|---|
| `packet.py` | Decodifica o quadro de 20 bytes, valida versão e CRC-16 |
| `receptor.py` | Estado por dispositivo, lacuna de sequência, alerta, persistência |
| `simulador.py` | Gera tráfego com colisão, perda e corrupção, para exercitar a cadeia sem rádio |

## Acoplamento com o firmware

`packet.py` espelha `struct LoraPacket` de `src/comms/lora.h`. Se o layout mudar
de um lado e não do outro, o gateway passa a ler lixo com CRC válido. Duas
defesas:

1. **Versão no primeiro byte.** O decodificador recusa formato que não conhece,
   em vez de interpretar campos deslocados.
2. **Teste de paridade.** `tests/test_paridade_crc.py` compila `lib/crc16` com
   `g++` e compara contra a implementação Python em 204 casos — mesmo método que
   `training/tests/test_export_cpp.py` usa para o Isolation Forest. Um CRC que
   diverge é pior que um ausente: valida quadro corrompido e rejeita íntegro.

## Rodar

```bash
python -m pytest experiments/gateway/tests/          # 19 testes
./tools/run-all-tests.sh                 # junto com as demais suítes
```

Requer `pytest`; o teste de paridade requer `g++`.

## Limites

O simulador cobre colisão, perda e corrupção de bit. **Não cobre propagação** —
alcance e margem de enlace dependem de medição em campo, e não há como derivá-los
de modelo sem medir.

Nada aqui rodou contra rádio real. O que os testes exercitam é a cadeia lógica
do pacote, não o enlace físico.
