#!/usr/bin/env python3
"""Exporta os dados do protocolo de rádio v3 usados na seção 3 do TCC.

Nenhum número é digitado aqui. O layout dos quadros sai de um programa em C++
que inclui lib/kaelix_protocol/kaelix_protocol.h e imprime sizeof e offsetof de
cada campo, e os tempos no ar saem da própria airtime_ms() do cabeçalho. O
intervalo mínimo de ciclo reproduz CycleTimeSeconds() de
kaelix-Ai-center/packages/contracts/deviceconfig.go, com as constantes lidas
desse arquivo, e é conferido contra o valor do teste em Go.

Saídas, em experiments/figures/data/:
  tab_protocolo_quadros.csv     tamanho de cada quadro e cabeçalho
  tab_protocolo_telemetria.csv  campos da telemetria: deslocamento, bytes, tipo
  tab_protocolo_perfis.csv      perfis de rajada: taxa, tempo no ar, rajada, ciclo
  tab_protocolo_gravador.csv    registros do gravador e capacidade calculada
  fig13_ciclo.csv               linha do tempo de um ciclo com rajada (exemplo)
  fig13_parametros.csv          constantes usadas na linha do tempo

Uso (só biblioteca padrão; precisa de um compilador C++17 no PATH):
  python3 experiments/figures/scripts/export_protocolo_data.py
"""
from __future__ import annotations

import csv
import math
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIRMWARE = HERE.parents[2]
WORKSPACE = FIRMWARE.parent
DATA = HERE.parent / "data"
PROTOCOL_H = FIRMWARE / "lib" / "kaelix_protocol" / "kaelix_protocol.h"
CRC_DIR = FIRMWARE / "lib" / "crc16"
STATUS_DIR = FIRMWARE / "lib" / "kaelix_status"
RECORDS_H = FIRMWARE / "src" / "gateway" / "records.h"
SPOOL_H = FIRMWARE / "src" / "gateway" / "spool.h"
NETWORK_CPP = FIRMWARE / "src" / "gateway" / "network.cpp"
PARTITIONS = FIRMWARE / "partitions" / "gateway_16MB.csv"
DEVICECONFIG_GO = WORKSPACE / "kaelix-Ai-center" / "packages" / "contracts" / "deviceconfig.go"

# Fragmentos perdidos na primeira rodada da linha do tempo. É um exemplo, para
# mostrar a retransmissão seletiva; não vem de medição.
EXAMPLE_LOST = (7, 18)

STRUCTS = ("Telemetry", "ReplyHeader", "FragmentHeader", "BurstMap")
TYPE_BYTES = {"uint8_t": 1, "int8_t": 1, "char": 1, "uint16_t": 2, "int16_t": 2,
              "uint32_t": 4, "int32_t": 4, "float": 4, "uint64_t": 8}


def struct_fields(source: str, name: str) -> list[tuple[str, str]]:
    """Campos (tipo, nome) de uma struct empacotada, na ordem do cabeçalho."""
    m = re.search(r"struct __attribute__\(\(packed\)\) " + name + r" \{(.*?)\n\s*\};", source, re.S)
    if m is None:
        raise SystemExit(f"struct {name} não encontrada")
    fields = []
    for line in m.group(1).splitlines():
        line = line.split("//")[0].strip()
        f = re.match(r"([\w:]+) (\w+)(\[[^\]]+\])?;", line)
        if f:
            fields.append((f.group(1), f.group(2)))
    return fields


def compile_layout(source: str) -> dict:
    """Compila e roda um programa que imprime o layout e os tempos do cabeçalho real."""
    cxx = shutil.which("c++") or shutil.which("clang++") or shutil.which("g++")
    if cxx is None:
        raise SystemExit("sem compilador C++ no PATH")
    lines = ['#include <cstddef>', '#include <cstdio>', '#include "kaelix_protocol.h"',
             'using namespace kaelix::protocol;', 'int main() {']
    for s in STRUCTS:
        lines.append(f'  std::printf("struct,{s},%zu\\n", sizeof({s}));')
        for _, field in struct_fields(source, s):
            lines.append(f'  std::printf("field,{s},{field},%zu,%zu\\n", offsetof({s}, {field}), '
                         f'sizeof((({s}*)nullptr)->{field}));')
    consts = ["VERSION", "FRAGMENT_PAYLOAD", "BURST_MAP_BYTES", "MAX_FRAME", "CONFIG_BASE_BYTES",
              "CONFIG_ROUTINE_BYTES", "CONFIG_MAX_BYTES", "REPLY_MIN_FRAME", "REPLY_MAX_FRAME",
              "PREAMBLE_SYMBOLS", "CONTROL_SF", "CODING_RATE", "SYNC_WORD", "FRAGMENT_GAP_MS",
              "BURST_ROUNDS", "REPLY_WINDOW_MS", "REPLY_TURNAROUND_MS", "BURST_START_DELAY_MS",
              "DEFAULT_BURST_PROFILE", "MAX_ROUTINE", "MAX_WINDOW_SAMPLES", "MAX_WAVE_BYTES"]
    for c in consts:
        lines.append(f'  std::printf("const,{c},%lu\\n", (unsigned long)({c}));')
    lines += ['  std::printf("constf,CONTROL_FREQUENCY_MHZ,%.3f\\n", (double)CONTROL_FREQUENCY_MHZ);',
              '  std::printf("constf,CONTROL_BW_KHZ,%.3f\\n", (double)CONTROL_BW_KHZ);',
              '  DeviceConfig d{};',
              '  std::printf("default,cycle_interval_s,%u\\n", d.cycle_interval_s);',
              '  std::printf("default,window_samples,%u\\n", d.window_samples);',
              '  std::printf("default,channels,%u\\n", d.channels);',
              '  std::printf("default,burst_profile,%u\\n", d.burst_profile);',
              '  std::printf("default,tx_power_dbm,%d\\n", d.tx_power_dbm);',
              '  std::printf("default,wave_every,%u\\n", d.wave_every);',
              '  std::printf("default,link_loss_s,%lu\\n", (unsigned long)d.link_loss_s);',
              '  std::printf("default,checkin_interval_s,%u\\n", d.checkin_interval_s);',
              '  const unsigned frag = sizeof(FragmentHeader) + FRAGMENT_PAYLOAD + 2U;',
              '  std::printf("derived,fragment_frame_bytes,%u\\n", frag);',
              '  std::printf("derived,fragment_payload_default,%u\\n", fragment_payload(d.channels));',
              '  std::printf("derived,fragment_count_default,%u\\n", fragment_count(d.window_samples, d.channels));',
              '  std::printf("derived,wave_bytes_default,%lu\\n", (unsigned long)wave_bytes(d.window_samples, d.channels));',
              '  for (unsigned p = 0; p < BURST_PROFILE_COUNT; ++p) {',
              '    const BurstProfile b = BURST_PROFILES[p];',
              '    std::printf("profile,%u,%u,%.1f,%lu,%lu,%lu,%lu\\n", p, b.sf, (double)b.bw_khz,',
              '      (unsigned long)airtime_ms(frag, b.sf, b.bw_khz), (unsigned long)airtime_ms(sizeof(BurstMap), b.sf, b.bw_khz),',
              '      (unsigned long)burst_idle_ms(p), (unsigned long)burst_map_wait_ms(p));',
              '  }',
              '  const unsigned sizes[] = {sizeof(Telemetry), (unsigned)REPLY_MIN_FRAME, (unsigned)(REPLY_MIN_FRAME + CONFIG_BASE_BYTES),',
              '                            (unsigned)REPLY_MAX_FRAME, sizeof(BurstMap), frag};',
              '  for (unsigned s : sizes) for (unsigned p = 0; p < BURST_PROFILE_COUNT; ++p)',
              '    std::printf("airtime,%u,%u,%lu\\n", s, p, (unsigned long)airtime_ms(s, BURST_PROFILES[p].sf, BURST_PROFILES[p].bw_khz));',
              '  const unsigned last = wave_bytes(d.window_samples, d.channels) - (fragment_count(d.window_samples, d.channels) - 1U) * fragment_payload(d.channels);',
              '  std::printf("derived,last_fragment_frame_bytes,%u\\n", (unsigned)(sizeof(FragmentHeader) + last + 2U));',
              '  for (unsigned p = 0; p < BURST_PROFILE_COUNT; ++p)',
              '    std::printf("airtime,%u,%u,%lu\\n", (unsigned)(sizeof(FragmentHeader) + last + 2U), p, (unsigned long)airtime_ms(sizeof(FragmentHeader) + last + 2U, BURST_PROFILES[p].sf, BURST_PROFILES[p].bw_khz));',
              '  return 0;', '}']
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "layout.cpp"
        exe = Path(tmp) / "layout"
        src.write_text("\n".join(lines) + "\n", encoding="utf-8")
        subprocess.run([cxx, "-std=gnu++17", "-O0", "-Wno-invalid-offsetof", f"-I{PROTOCOL_H.parent}", f"-I{CRC_DIR}", f"-I{STATUS_DIR}",
                        str(src), str(CRC_DIR / "crc16.cpp"), "-o", str(exe)], check=True)
        out = subprocess.run([str(exe)], check=True, capture_output=True, text=True).stdout
    result = {"struct": {}, "field": [], "const": {}, "default": {}, "derived": {}, "profile": [], "airtime": {}}
    for row in csv.reader(out.splitlines()):
        kind = row[0]
        if kind == "struct":
            result["struct"][row[1]] = int(row[2])
        elif kind == "field":
            result["field"].append((row[1], row[2], int(row[3]), int(row[4])))
        elif kind in ("const", "default", "derived"):
            result[kind][row[1]] = int(row[2])
        elif kind == "constf":
            result["const"][row[1]] = float(row[2])
        elif kind == "profile":
            result["profile"].append(dict(code=int(row[1]), sf=int(row[2]), bw_khz=float(row[3]),
                                          fragment_ms=int(row[4]), map_ms=int(row[5]),
                                          idle_ms=int(row[6]), map_wait_ms=int(row[7])))
        elif kind == "airtime":
            result["airtime"][(int(row[1]), int(row[2]))] = int(row[3])
    return result


def go_constants() -> dict[str, float]:
    """Constantes de tempo do ciclo em deviceconfig.go."""
    text = DEVICECONFIG_GO.read_text(encoding="utf-8")
    names = ["acquisitionMarginS", "telemetryTimeS", "replyTimeS", "fragmentGapS", "burstMapTimeS",
             "fragmentPayloadSize", "fragmentOverhead"]
    out = {}
    for n in names:
        m = re.search(n + r"\s*=\s*([0-9.]+)", text)
        if m is None:
            raise SystemExit(f"{n} não encontrada em deviceconfig.go")
        out[n] = float(m.group(1))
    m = re.search(r'near\(t, "default cycle", CycleTimeSeconds\(cfg\), ([0-9.]+), ([0-9.]+)\)',
                  (DEVICECONFIG_GO.parent / "deviceconfig_test.go").read_text(encoding="utf-8"))
    out["test_default_cycle"], out["test_tolerance"] = float(m.group(1)), float(m.group(2))
    m = re.search(r"MinimumCycleInterval\(cfg\) != (\d+)",
                  (DEVICECONFIG_GO.parent / "deviceconfig_test.go").read_text(encoding="utf-8"))
    out["test_minimum"] = int(m.group(1))
    return out


def go_airtime_ms(payload: int, sf: int, bw: float) -> float:
    """LoRaAirtimeMS de deviceconfig.go: a mesma fórmula, sem arredondar para cima."""
    blocks = math.ceil((8 * payload - 4 * sf + 44) / (4 * sf))
    symbols = 8 + max(blocks * 5, 0)
    return (12.25 + symbols) * (1 << sf) / bw


def go_cycle_s(window: int, channels: int, sf: int, bw: float, g: dict) -> float:
    """CycleTimeSeconds de deviceconfig.go, com sinal bruto em todo ciclo."""
    count = bin(channels).count("1")
    frame = 2 * count
    payload = int(g["fragmentPayloadSize"]) - int(g["fragmentPayloadSize"]) % frame
    total = window * count * 2
    full, rest = divmod(total, payload)
    burst = full * go_airtime_ms(payload + int(g["fragmentOverhead"]), sf, bw)
    if rest:
        burst += go_airtime_ms(rest + int(g["fragmentOverhead"]), sf, bw)
    fragments = math.ceil(total / payload)
    return (window / 1000 + g["acquisitionMarginS"] + g["telemetryTimeS"] + g["replyTimeS"]
            + burst / 1000 + fragments * g["fragmentGapS"] + g["burstMapTimeS"])


def packed_size(source: str, name: str, known: dict[str, int]) -> int:
    """Tamanho de uma struct empacotada de records.h, somando os campos."""
    total = 0
    for ctype, field in struct_fields_with_arrays(source, name):
        base, count = ctype
        size = known.get(base.split("::")[-1], TYPE_BYTES.get(base))
        if size is None:
            raise SystemExit(f"tipo desconhecido {base} em {name}")
        total += size * count
    return total


def struct_fields_with_arrays(source: str, name: str):
    m = re.search(r"struct __attribute__\(\(packed\)\) " + name + r" \{(.*?)\n\s*\};", source, re.S)
    if m is None:
        raise SystemExit(f"struct {name} não encontrada")
    for line in m.group(1).splitlines():
        line = line.split("//")[0].strip()
        f = re.match(r"([\w:]+) (\w+)(?:\[([^\]]+)\])?;", line)
        if not f:
            continue
        count = 1
        if f.group(3):
            dim = f.group(3)
            count = int(dim) if dim.isdigit() else None
            if count is None:
                yield (f.group(1), dim), f.group(2)
                continue
        yield (f.group(1), count), f.group(2)


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    source = PROTOCOL_H.read_text(encoding="utf-8")
    lay = compile_layout(source)
    k, d, der = lay["const"], lay["default"], lay["derived"]
    S = lay["struct"]

    # Os tamanhos documentados na especificação e nos static_assert do cabeçalho.
    assert S["Telemetry"] == 71 and S["ReplyHeader"] == 20 and S["FragmentHeader"] == 12 and S["BurstMap"] == 44
    assert k["VERSION"] == 3

    # --- quadros -----------------------------------------------------------
    frag = der["fragment_frame_bytes"]
    with open(DATA / "tab_protocolo_quadros.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["quadro", "tipo", "bytes", "tempo_no_ar_controle_ms", "tempo_no_ar_rajada_padrao_ms"])
        p = d["burst_profile"]
        w.writerow(["telemetria", 1, S["Telemetry"], lay["airtime"][(S["Telemetry"], 0)], ""])
        w.writerow(["resposta sem configuração", 2, k["REPLY_MIN_FRAME"], lay["airtime"][(k["REPLY_MIN_FRAME"], 0)], ""])
        w.writerow(["resposta com configuração sem rotina", 2, k["REPLY_MIN_FRAME"] + k["CONFIG_BASE_BYTES"],
                    lay["airtime"][(k["REPLY_MIN_FRAME"] + k["CONFIG_BASE_BYTES"], 0)], ""])
        w.writerow(["resposta com configuração e 6 janelas", 2, k["REPLY_MAX_FRAME"], lay["airtime"][(k["REPLY_MAX_FRAME"], 0)], ""])
        w.writerow(["fragmento cheio", 3, frag, "", lay["airtime"][(frag, p)]])
        w.writerow(["último fragmento da janela padrão", 3, der["last_fragment_frame_bytes"], "",
                    lay["airtime"][(der["last_fragment_frame_bytes"], p)]])
        w.writerow(["mapa da rajada", 4, S["BurstMap"], "", lay["airtime"][(S["BurstMap"], p)]])

    # --- campos da telemetria -----------------------------------------------
    types = dict((f, t) for t, f in struct_fields(source, "Telemetry"))
    with open(DATA / "tab_protocolo_telemetria.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["campo", "deslocamento", "bytes", "tipo"])
        expected = 0
        for s, field, offset, size in lay["field"]:
            if s != "Telemetry":
                continue
            assert offset == expected, f"lacuna antes de {field}"
            expected = offset + size
            w.writerow([field, offset, size, types[field]])
        assert expected == S["Telemetry"]

    # --- perfis de rajada ---------------------------------------------------
    g = go_constants()
    window, channels = d["window_samples"], d["channels"]
    n_frag = der["fragment_count_default"]
    last_bytes = der["last_fragment_frame_bytes"]
    assert n_frag == 26 and der["fragment_payload_default"] == 240 and der["wave_bytes_default"] == 6144
    rows = []
    for prof in lay["profile"]:
        sf, bw, code = prof["sf"], prof["bw_khz"], prof["code"]
        rate_kbps = sf * bw / (1 << sf) * 4 / k["CODING_RATE"]  # CR 4/5
        burst_ms = (n_frag - 1) * prof["fragment_ms"] + lay["airtime"][(last_bytes, code)]
        cycle = go_cycle_s(window, channels, sf, bw, g)
        minimum = math.ceil(cycle - 1e-9)
        rows.append([code, sf, bw, f"{rate_kbps:.2f}", prof["fragment_ms"], prof["map_ms"], burst_ms,
                     f"{burst_ms + (n_frag - 1) * k['FRAGMENT_GAP_MS']}", f"{cycle:.3f}", minimum])
        if code == d["burst_profile"]:
            assert abs(cycle - g["test_default_cycle"]) <= g["test_tolerance"], cycle
            assert minimum == g["test_minimum"]
    with open(DATA / "tab_protocolo_perfis.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["codigo", "sf", "bw_khz", "taxa_kbps", "fragmento_ms", "mapa_ms", "rajada_no_ar_ms",
                    "rajada_com_intervalos_ms", "ciclo_api_s", "intervalo_minimo_s"])
        w.writerows(rows)

    # --- gravador ------------------------------------------------------------
    records = RECORDS_H.read_text(encoding="utf-8")
    known = {"Telemetry": S["Telemetry"]}
    reading = packed_size(records, "ReadingRecord", known)
    # WaveRecord termina em received[proto::BURST_MAP_BYTES].
    wave = 0
    for (base, count), field in struct_fields_with_arrays(records, "WaveRecord"):
        size = known.get(base.split("::")[-1], TYPE_BYTES.get(base))
        if isinstance(count, str):
            count = k[count.split("::")[-1]]
        wave += size * count
    header = sum(TYPE_BYTES[t] for t, _ in struct_fields(SPOOL_H.read_text(encoding="utf-8"), "RecordHeader"))
    assert header == 12
    part = None
    for line in PARTITIONS.read_text(encoding="utf-8").splitlines():
        if line.startswith("spool"):
            part = int(line.split(",")[4].strip(), 16)
    net = NETWORK_CPP.read_text(encoding="utf-8")
    seg = re.search(r"#define KAELIX_SPOOL_SEGMENT_BYTES \((\d+)U \* (\d+)U\)", net)
    segment = int(seg.group(1)) * int(seg.group(2))
    cap = re.search(r"totalBytes\(\)\) \* (\d+)ULL / (\d+)ULL", net)
    capacity = part * int(cap.group(1)) // int(cap.group(2))
    per_cycle = (reading + header) + (wave + der["wave_bytes_default"] + header)
    cycles = capacity // per_cycle
    hours = cycles * d["cycle_interval_s"] / 3600
    with open(DATA / "tab_protocolo_gravador.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["item", "valor"])
        w.writerows([["registro_cabecalho_bytes", header], ["leitura_bytes", reading],
                     ["janela_cabecalho_bytes", wave], ["janela_amostras_bytes", der["wave_bytes_default"]],
                     ["por_ciclo_bytes", per_cycle], ["particao_bytes", part], ["segmento_bytes", segment],
                     ["capacidade_bytes", capacity], ["ciclos", cycles], ["intervalo_s", d["cycle_interval_s"]],
                     ["horas", f"{hours:.2f}"]])

    # --- linha do tempo de um ciclo -------------------------------------------
    prof = lay["profile"][d["burst_profile"]]
    tel = lay["airtime"][(S["Telemetry"], 0)]
    reply = lay["airtime"][(k["REPLY_MIN_FRAME"], 0)]
    full = prof["fragment_ms"]
    last = lay["airtime"][(last_bytes, d["burst_profile"])]
    turn, gap, start = k["REPLY_TURNAROUND_MS"], k["FRAGMENT_GAP_MS"], k["BURST_START_DELAY_MS"]
    seg_rows = []

    def add(lane, kind, channel, t0, t1, label="", lost=False, rnd=0):
        seg_rows.append([lane, kind, channel, t0, t1, label, int(lost), rnd])

    t = 0
    add("transmissor", "aquisição", "nenhum", t, t + window, f"{window} amostras")
    t += window
    add("transmissor", "telemetria", "controle", t, t + tel, f"{S['Telemetry']} B")
    add("transmissor", "escuta", "controle", t + tel, t + tel + k["REPLY_WINDOW_MS"], "janela de escuta")
    t += tel
    add("gateway", "resposta", "controle", t + turn, t + turn + reply, f"{k['REPLY_MIN_FRAME']} B")
    t += turn + reply
    t += start
    pending = list(range(n_frag))
    rnd = 1
    while pending and rnd <= k["BURST_ROUNDS"]:
        received = []
        for i, idx in enumerate(pending):
            air = last if idx == n_frag - 1 else full
            lost = rnd == 1 and idx in EXAMPLE_LOST
            add("transmissor", "fragmento", "rajada", t, t + air, str(idx), lost, rnd)
            if not lost:
                received.append(idx)
            t += air
            if i < len(pending) - 1:
                t += gap
        add("gateway", "mapa", "rajada", t + turn, t + turn + prof["map_ms"], f"{S['BurstMap']} B", False, rnd)
        t += turn + prof["map_ms"]
        pending = [i for i in pending if i not in received]
        rnd += 1
    assert not pending
    with open(DATA / "fig13_ciclo.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["lado", "evento", "canal", "inicio_ms", "fim_ms", "rotulo", "perdido", "rodada"])
        w.writerows(seg_rows)
    with open(DATA / "fig13_parametros.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["parametro", "valor"])
        w.writerows([["intervalo_ciclo_ms", d["cycle_interval_s"] * 1000], ["fim_ms", t],
                     ["controle_sf", k["CONTROL_SF"]], ["controle_bw_khz", k["CONTROL_BW_KHZ"]],
                     ["rajada_sf", prof["sf"]], ["rajada_bw_khz", prof["bw_khz"]],
                     ["fragmentos", n_frag], ["perdidos_exemplo", " ".join(map(str, EXAMPLE_LOST))],
                     ["telemetria_ms", tel], ["resposta_ms", reply], ["fragmento_ms", full],
                     ["ultimo_fragmento_ms", last], ["mapa_ms", prof["map_ms"]],
                     ["intervalo_fragmentos_ms", gap], ["inicio_rajada_ms", start], ["volta_ms", turn],
                     ["escuta_ms", k["REPLY_WINDOW_MS"]]])
    print(f"telemetria {S['Telemetry']} B, {tel} ms; resposta {k['REPLY_MIN_FRAME']} B, {reply} ms; "
          f"fragmento {frag} B, {full} ms; {n_frag} fragmentos; ciclo de exemplo {t} ms; "
          f"gravador {hours:.2f} h com {cycles} ciclos")


if __name__ == "__main__":
    main()
