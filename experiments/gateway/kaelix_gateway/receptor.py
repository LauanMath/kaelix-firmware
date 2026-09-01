"""Receptor: transforma quadros de rádio em histórico por dispositivo e
em alertas acionáveis.

É o elo que faltava entre "o dispositivo transmite" e "alguém age". Três
responsabilidades, e nenhuma delas é opcional:

1. CARIMBAR O TEMPO. O dispositivo não tem relógio — `boot_count` dá
   ordem, não instante. Quem sabe que horas são é este lado.
2. DETECTAR LACUNA. `boot_count` é monotônico por dispositivo; um salto
   significa pacote perdido, e perda silenciosa é indistinguível de
   máquina parada. Sem isto, o sistema não sabe a diferença entre
   "tudo bem" e "não chega nada há três dias".
3. DECIDIR QUANDO INCOMODAR. Um anômalo isolado é ruído; anômalos
   consecutivos são sinal. A regra de disparo mora aqui, e não no
   dispositivo, porque mudá-la no dispositivo exigiria regravar cada
   aparelho.
"""

import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path

from .packet import Leitura, PacketError, decodificar

# Anômalos consecutivos para abrir alerta. 1 dispararia com ruído de uma
# janela; valores altos atrasam o aviso. Com ciclo de 10 min, 3 significa
# ~30 min de anomalia sustentada.
ANOMALIAS_PARA_ALERTA = 3

# Ciclos sem notícia para considerar o dispositivo mudo. Com 10 min de
# ciclo, 6 é uma hora — acima da perda esperada por colisão, que fica em
# 1,5% para 20 dispositivos.
CICLOS_PARA_MUDO = 6


@dataclass
class EstadoDispositivo:
    device_id: int
    ultimo_boot: int = -1
    recebidos: int = 0
    perdidos: int = 0
    anomalias_seguidas: int = 0
    ultimo_visto: float = 0.0
    alerta_aberto: bool = False

    @property
    def taxa_perda(self) -> float:
        total = self.recebidos + self.perdidos
        return self.perdidos / total if total else 0.0


@dataclass
class Evento:
    tipo: str          # "leitura" | "alerta" | "recuperado" | "mudo" | "descartado"
    device_id: int
    t: float
    detalhe: str = ""


class Receptor:
    def __init__(self, armazenamento: Path | None = None):
        self.dispositivos: dict[int, EstadoDispositivo] = {}
        self.eventos: list[Evento] = []
        self.armazenamento = Path(armazenamento) if armazenamento else None
        if self.armazenamento:
            self.armazenamento.parent.mkdir(parents=True, exist_ok=True)

    def _reg(self, ev: Evento) -> None:
        self.eventos.append(ev)

    def receber(self, quadro: bytes, t: float | None = None) -> Leitura | None:
        """Processa um quadro. Devolve a leitura, ou None se o quadro foi
        descartado — e nesse caso o motivo fica registrado como evento, em
        vez de sumir."""
        t = time.time() if t is None else t
        try:
            leitura = decodificar(quadro)
        except PacketError as exc:
            self._reg(Evento("descartado", -1, t, str(exc)))
            return None

        d = self.dispositivos.setdefault(leitura.device_id, EstadoDispositivo(leitura.device_id))

        # Lacuna: boot_count salta mais de 1. Um reset do dispositivo zera
        # o contador em RTC memory, e isso aparece como salto negativo —
        # tratado como reinício, não como perda.
        if d.ultimo_boot >= 0:
            salto = leitura.boot_count - d.ultimo_boot
            if salto > 1:
                d.perdidos += salto - 1
                self._reg(Evento("mudo" if salto - 1 >= CICLOS_PARA_MUDO else "leitura",
                                 d.device_id, t, f"{salto - 1} ciclo(s) sem notícia"))
            elif salto <= 0:
                self._reg(Evento("leitura", d.device_id, t,
                                 f"contador reiniciou ({d.ultimo_boot} -> {leitura.boot_count})"))

        d.ultimo_boot = leitura.boot_count
        d.recebidos += 1
        d.ultimo_visto = t

        if leitura.anomalo:
            d.anomalias_seguidas += 1
            if d.anomalias_seguidas >= ANOMALIAS_PARA_ALERTA and not d.alerta_aberto:
                d.alerta_aberto = True
                self._reg(Evento("alerta", d.device_id, t,
                                 f"{d.anomalias_seguidas} leituras anômalas seguidas, "
                                 f"RMS {leitura.rms:.3f} g, {leitura.temperature_c:.1f} °C"))
        else:
            if d.alerta_aberto:
                d.alerta_aberto = False
                self._reg(Evento("recuperado", d.device_id, t, "leitura normal após alerta"))
            d.anomalias_seguidas = 0

        if self.armazenamento:
            with self.armazenamento.open("a") as f:
                f.write(json.dumps({"t": t, **asdict(leitura)}) + "\n")

        return leitura

    def mudos(self, agora: float, ciclo_s: float = 600.0) -> list[EstadoDispositivo]:
        """Dispositivos sem notícia há tempo demais. Silêncio não é
        ausência de problema: é ausência de informação."""
        limite = CICLOS_PARA_MUDO * ciclo_s
        return [d for d in self.dispositivos.values() if agora - d.ultimo_visto > limite]

    def resumo(self) -> dict:
        return {
            "dispositivos": len(self.dispositivos),
            "recebidos": sum(d.recebidos for d in self.dispositivos.values()),
            "perdidos": sum(d.perdidos for d in self.dispositivos.values()),
            "alertas": sum(1 for e in self.eventos if e.tipo == "alerta"),
            "descartados": sum(1 for e in self.eventos if e.tipo == "descartado"),
        }
