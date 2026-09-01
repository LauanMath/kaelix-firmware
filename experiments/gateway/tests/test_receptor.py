"""Cadeia pacote -> ar -> gateway, exercitada sem hardware."""

from pathlib import Path

import pytest

from kaelix_gateway.packet import Leitura, PacketError, codificar, decodificar
from kaelix_gateway.receptor import ANOMALIAS_PARA_ALERTA, Receptor
from kaelix_gateway.simulador import Dispositivo, simular


def q(dev=1, boot=1, status=0, rms=0.19, temp=42.0):
    return codificar(Leitura(dev, boot, status, rms, temp))


# --- decodificação ---------------------------------------------------------

def test_ida_e_volta_preserva_os_campos():
    l = Leitura(0xA1B2C3D4, 142, 1, 0.4701, 44.8)
    v = decodificar(codificar(l))
    assert (v.device_id, v.boot_count, v.status) == (l.device_id, l.boot_count, l.status)
    assert v.rms == pytest.approx(l.rms, rel=1e-6)


def test_versao_desconhecida_e_recusada_antes_dos_campos():
    """Interpretar offsets de um layout que não se conhece produz leitura
    plausível e errada — pior que recusar."""
    b = bytearray(q()); b[0] = 99
    with pytest.raises(PacketError, match="vers"):
        decodificar(bytes(b))


@pytest.mark.parametrize("bit", [0, 7, 40, 100, 140])
def test_qualquer_bit_invertido_e_detectado(bit):
    b = bytearray(q()); b[bit // 8] ^= 1 << (bit % 8)
    with pytest.raises(PacketError):
        decodificar(bytes(b))


def test_tamanho_errado_e_recusado():
    with pytest.raises(PacketError, match="tamanho"):
        decodificar(q()[:-1])


# --- receptor --------------------------------------------------------------

def test_lacuna_de_sequencia_vira_perda_contabilizada():
    """boot_count é o que separa 'tudo bem' de 'não chega nada'."""
    r = Receptor()
    r.receber(q(boot=1), t=0)
    r.receber(q(boot=5), t=600)     # 2, 3 e 4 se perderam
    assert r.dispositivos[1].perdidos == 3
    assert r.dispositivos[1].recebidos == 2


def test_reinicio_do_contador_nao_conta_como_perda():
    """Reset zera o boot_count em RTC memory. Contar isso como perda
    inventaria milhares de pacotes perdidos."""
    r = Receptor()
    r.receber(q(boot=900), t=0)
    r.receber(q(boot=1), t=600)
    assert r.dispositivos[1].perdidos == 0


def test_alerta_exige_anomalias_seguidas():
    r = Receptor()
    for i in range(ANOMALIAS_PARA_ALERTA - 1):
        r.receber(q(boot=i + 1, status=1), t=i * 600)
    assert not any(e.tipo == "alerta" for e in r.eventos)
    r.receber(q(boot=ANOMALIAS_PARA_ALERTA, status=1), t=ANOMALIAS_PARA_ALERTA * 600)
    assert sum(1 for e in r.eventos if e.tipo == "alerta") == 1


def test_anomalia_isolada_nao_alerta_e_normal_fecha_o_alerta():
    r = Receptor()
    r.receber(q(boot=1, status=1), t=0)
    r.receber(q(boot=2, status=0), t=600)
    assert not any(e.tipo == "alerta" for e in r.eventos)
    for i in range(ANOMALIAS_PARA_ALERTA):
        r.receber(q(boot=3 + i, status=1), t=(2 + i) * 600)
    r.receber(q(boot=20, status=0), t=99999)
    assert any(e.tipo == "recuperado" for e in r.eventos)


def test_quadro_corrompido_e_registrado_e_nao_vira_leitura():
    r = Receptor()
    b = bytearray(q()); b[9] ^= 0xFF
    assert r.receber(bytes(b), t=0) is None
    assert r.resumo()["descartados"] == 1
    assert r.resumo()["recebidos"] == 0


def test_dispositivo_mudo_e_detectado():
    r = Receptor()
    r.receber(q(boot=1), t=0)
    assert r.mudos(agora=10 * 600) and not r.mudos(agora=600)


def test_armazenamento_persiste_uma_linha_por_leitura(tmp_path):
    arq = tmp_path / "hist.jsonl"
    r = Receptor(armazenamento=arq)
    for i in range(3):
        r.receber(q(boot=i + 1), t=i * 600)
    assert len(arq.read_text().strip().splitlines()) == 3


# --- cadeia completa, com o meio simulado ----------------------------------

def test_jitter_derruba_a_colisao_sistematica():
    """Sem deslocamento, dispositivos energizados juntos transmitem no
    mesmo instante e colidem TODOS os ciclos — o caso que a probabilidade
    de ALOHA não cobre, porque ela pressupõe fases aleatórias."""
    devs = [Dispositivo(device_id=i) for i in range(1, 9)]
    _, sem = simular(devs, ciclos=20, com_jitter=False)
    _, com = simular(devs, ciclos=20, com_jitter=True)
    assert sem["colisao"] == 160          # 8 dispositivos x 20 ciclos, todos
    assert com["colisao"] < sem["colisao"] * 0.05
    assert com["entregues"] > 150


def test_gateway_processa_uma_campanha_inteira():
    devs = [Dispositivo(device_id=i, p_anomalia=0.6 if i == 3 else 0.0) for i in range(1, 6)]
    quadros, meio = simular(devs, ciclos=40, p_perda=0.02, p_corrupcao=0.01)

    r = Receptor()
    for t, quadro in quadros:
        r.receber(quadro, t=t)
    s = r.resumo()

    assert s["dispositivos"] == 5
    assert s["recebidos"] + s["descartados"] == meio["entregues"]
    # Só o dispositivo 3 tem anomalia sustentada o bastante para alertar.
    alertados = {e.device_id for e in r.eventos if e.tipo == "alerta"}
    assert alertados == {3}
    # Perda no ar aparece como lacuna de sequência do lado do gateway.
    assert sum(d.perdidos for d in r.dispositivos.values()) > 0
