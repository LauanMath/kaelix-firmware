#!/usr/bin/env python3
"""Macros do capítulo do sistema (values/sistema_values.tex).

Fontes, lidas sem alteração:
  - código-fonte dos dois repositórios (kaelix-firmware e kaelix-Ai-center), para as linhas de código e as
    contagens de testes em Go;
  - experiments/sistema/testes_nativos_20261107.log, saída de `taskpolicy -b pio test -e native`;
  - .pio/bench/ (fora do git), registros dos ensaios de 2 de novembro de 2026: build.log e build-tx.log
    (memória dos binários da coleta), c3-capture.log (rajadas), linkloss.log (transmissor sem gateway) e
    temp-db.dump (cópia do banco de teste das 08h46, lida com pg_restore em modo texto, sem restaurar).

Os registros de .pio/bench/ trazem nomes de rede e endereços do local e por isso ficam fora do repositório;
este script grava só os números.

Uso, a partir de docs/monografia/latex/:
  python3 scripts/build_sistema_values.py
Variável opcional: PG_RESTORE, caminho de um pg_restore 17 ou mais novo (o dump é do PostgreSQL 18).
"""
import datetime as dt
import hashlib
import json
import os
import pathlib
import re
import subprocess

LATEX = pathlib.Path(__file__).resolve().parents[1]
RAIZ = LATEX.parents[2]
AIC = RAIZ.parent / "kaelix-Ai-center"
BENCH = RAIZ / ".pio" / "bench"
TESTES = RAIZ / "experiments" / "sistema" / "testes_nativos_20261107.log"
SAIDA = LATEX / "values" / "sistema_values.tex"
DISPOSITIVO = "311D0470"
SUITES_CAMPO = ("test_protocol", "test_gateway_v3", "test_spool", "test_remote_logs", "test_crc16",
                "test_signal_processing", "test_vibration")
FUSO = dt.timezone(dt.timedelta(hours=-3))


def br(x, casas=1):
    s = f"{x:.{casas}f}".replace(".", ",")
    return s.replace("-", "\\textminus ")


def inteiro(n):
    s = f"{n:,}".replace(",", "\\,")
    return s


def linhas(arquivos):
    total = 0
    for a in arquivos:
        with open(a, encoding="utf-8", errors="replace") as f:
            total += sum(1 for _ in f)
    return total


def arquivos(base, padroes, excluir=()):
    out = []
    for p in padroes:
        for a in sorted(base.glob(p)):
            s = str(a)
            if a.is_file() and not any(e in s for e in excluir):
                out.append(a)
    return sorted(set(out))


def pg_restore():
    cand = [os.environ.get("PG_RESTORE", ""), "/opt/homebrew/opt/postgresql@18/bin/pg_restore",
            "/opt/homebrew/opt/postgresql@17/bin/pg_restore"]
    for c in cand:
        if c and pathlib.Path(c).exists():
            return c
    raise SystemExit("pg_restore 17 ou mais novo não encontrado (defina PG_RESTORE)")


def tabela(dump, nome):
    txt = subprocess.run([pg_restore(), "-f", "-", "--data-only", "-t", nome, str(dump)], check=True,
                         capture_output=True, text=True).stdout
    linhas_, ativo, colunas = [], False, []
    for ln in txt.splitlines():
        if ln.startswith(f"COPY public.{nome} "):
            colunas = [c.strip() for c in ln[ln.index("(") + 1:ln.index(")")].split(",")]
            ativo = True
            continue
        if ativo and ln == "\\.":
            break
        if ativo:
            linhas_.append(dict(zip(colunas, ln.split("\t"))))
    if not colunas:
        raise SystemExit(f"tabela {nome} ausente em {dump}")
    return linhas_


def instante(s):
    return dt.datetime.fromisoformat(s)


def memoria(log):
    txt = log.read_text()
    ram = re.search(r"RAM:.*?([\d.]+)% \(used (\d+) bytes from (\d+) bytes\)", txt)
    fla = re.search(r"Flash:.*?([\d.]+)% \(used (\d+) bytes from (\d+) bytes\)", txt)
    return (float(ram[1]), int(ram[2]), int(ram[3])), (float(fla[1]), int(fla[2]), int(fla[3]))


def main():
    m = {}

    # Linhas de código, com comentários e linhas em branco.
    tx = arquivos(RAIZ, ["src/transmitter/*.cpp", "src/transmitter/*.h", "src/sensors/vibration.*",
                         "src/power/watchdog.*", "src/power/rtc_watchdog.*"])
    gw = arquivos(RAIZ, ["src/gateway/*"])
    proto = arquivos(RAIZ, ["lib/kaelix_protocol/*"])
    comum = arquivos(RAIZ, ["lib/crc16/**/*", "lib/kaelix_status/**/*", "lib/signal_processing/**/*"])
    api = arquivos(AIC, ["apps/server/**/*.go"], excluir=("_test.go",))
    sql = arquivos(AIC, ["apps/server/**/*.sql"])
    contratos = arquivos(AIC, ["packages/contracts/**/*.go"], excluir=("_test.go",))
    mesa_go = arquivos(AIC, ["apps/desktop/**/*.go"], excluir=("_test.go", "node_modules", "wailsjs", "/build/"))
    mesa_ui = arquivos(AIC, ["apps/desktop/frontend/src/**/*.ts", "apps/desktop/frontend/src/**/*.tsx",
                             "apps/desktop/frontend/src/**/*.css"])
    testes_fw = arquivos(RAIZ, ["test/**/*.cpp", "test/**/*.h"])
    testes_go = arquivos(AIC, ["**/*_test.go"], excluir=("node_modules",))
    m.update(sisLinhasTransmissor=inteiro(linhas(tx)), sisLinhasGateway=inteiro(linhas(gw)),
             sisLinhasProtocolo=inteiro(linhas(proto)), sisLinhasComum=inteiro(linhas(comum)),
             sisLinhasApi=inteiro(linhas(api)), sisLinhasSql=inteiro(linhas(sql)),
             sisLinhasContratos=inteiro(linhas(contratos)), sisLinhasMesaGo=inteiro(linhas(mesa_go)),
             sisLinhasMesaUi=inteiro(linhas(mesa_ui)), sisLinhasTestesFirmware=inteiro(linhas(testes_fw)),
             sisLinhasTestesGo=inteiro(linhas(testes_go)))

    # Testes em Go: arquivos e funções Test, só contados.
    def funcoes(arqs):
        return sum(len(re.findall(r"^func Test\w*\(", a.read_text(), re.M)) for a in arqs)
    go_api = [a for a in testes_go if "/apps/server/" in str(a)]
    go_mesa = [a for a in testes_go if "/apps/desktop/" in str(a)]
    go_contr = [a for a in testes_go if "/packages/contracts/" in str(a)]
    m.update(sisGoArquivos=str(len(testes_go)), sisGoFuncoes=str(funcoes(testes_go)),
             sisGoFuncoesApi=str(funcoes(go_api)), sisGoFuncoesMesa=str(funcoes(go_mesa)),
             sisGoFuncoesContratos=str(funcoes(go_contr)))

    # Memória dos binários da coleta (compilação de 2 de novembro).
    for nome, log in (("Transmissor", BENCH / "build-tx.log"), ("Gateway", BENCH / "build.log")):
        (rp, ru, rt), (fp, fu, ft) = memoria(log)
        m[f"sisRam{nome}Pct"] = br(rp)
        m[f"sisRam{nome}Bytes"] = inteiro(ru)
        m[f"sisRam{nome}Total"] = inteiro(rt)
        m[f"sisFlash{nome}Pct"] = br(fp)
        m[f"sisFlash{nome}Bytes"] = inteiro(fu)
        m[f"sisFlash{nome}Total"] = inteiro(ft)

    # Versão do código da coleta. O firmware da coleta não tem commit: a versão é identificada pelo resumo
    # SHA-256 do código-fonte, e a data de modificação dos arquivos mostra que nada mudou depois das compilações
    # de 2 de novembro, de modo que os testes de 7 de novembro rodaram sobre o mesmo código.
    def inicio_compilacao(log):
        h, mi, s = map(int, re.search(r"== compilar (\d\d):(\d\d):(\d\d)", log.read_text()).groups())
        dia = dt.datetime.fromtimestamp(log.stat().st_mtime, FUSO).date()
        return dt.datetime(dia.year, dia.month, dia.day, h, mi, s, tzinfo=FUSO)

    def ultima_mudanca(arqs):
        return max(dt.datetime.fromtimestamp(a.stat().st_mtime, FUSO) for a in arqs)

    ini = [RAIZ / "platformio.ini"]
    fonte_tx, fonte_gw = tx + proto + comum + ini, gw + proto + comum + ini
    comp_tx, comp_gw = inicio_compilacao(BENCH / "build-tx.log"), inicio_compilacao(BENCH / "build.log")
    assert ultima_mudanca(fonte_tx) < comp_tx, "código do transmissor mudou depois da compilação da coleta"
    assert ultima_mudanca(fonte_gw) < comp_gw, "código do gateway mudou depois da compilação da coleta"
    assert ultima_mudanca(testes_fw) < dt.datetime.fromtimestamp(TESTES.stat().st_mtime, FUSO)
    resumo_fonte = hashlib.sha256()
    for a in sorted(set(fonte_tx + fonte_gw)):
        resumo_fonte.update(str(a.relative_to(RAIZ)).encode() + b"\0" + a.read_bytes() + b"\0")
    m.update(sisCompilaTransmissor=f"{comp_tx.hour}h{comp_tx.minute:02d}",
             sisCompilaGateway=f"{comp_gw.hour}h{comp_gw.minute:02d}",
             sisCodigoArquivos=str(len(set(fonte_tx + fonte_gw))),
             sisCodigoSha=resumo_fonte.hexdigest()[:12])

    # Testes nativos do firmware.
    txt = TESTES.read_text()
    resumo = re.search(r"(\d+) test cases: (\d+) succeeded in (\d+):(\d+):([\d.]+)", txt)
    casos = int(resumo[1])
    passaram = int(resumo[2])
    duracao = int(resumo[3]) * 3600 + int(resumo[4]) * 60 + float(resumo[5])
    por_suite = {}
    for s in re.findall(r"^test/(test_\w+)/\S+: \w+\t\[PASSED\]", txt, re.M):
        por_suite[s] = por_suite.get(s, 0) + 1
    falhas = len(re.findall(r"\t\[FAILED\]", txt))
    assert sum(por_suite.values()) == passaram and falhas == casos - passaram
    m.update(sisTestesSuites=str(len(por_suite)), sisTestesCasos=str(casos), sisTestesPassaram=str(passaram),
             sisTestesFalharam=str(casos - passaram), sisTestesDuracao=br(duracao),
             sisTestesCampoSuites=str(len(SUITES_CAMPO)),
             sisTestesCampoCasos=str(sum(por_suite[s] for s in SUITES_CAMPO)))
    algarismos = {"3": "Three", "16": "Sixteen"}
    for s, n in por_suite.items():
        nome = "".join(p.capitalize() for p in s.removeprefix("test_").split("_"))
        for num, palavra in algarismos.items():
            nome = nome.replace(num, palavra)
        assert nome.isalpha(), nome
        m[f"sisCasos{nome}"] = str(n)

    # Código de diagnóstico das telemetrias dos trechos analisados da coleta.
    import csv
    with open(RAIZ / "experiments" / "campo" / "dados" / "leituras.csv", encoding="utf-8") as f:
        campo = list(csv.DictReader(f))
    m.update(sisCampoTelemetrias=str(len(campo)),
             sisCampoDiagZero=str(sum(r["diag_code"] == "0" for r in campo)))

    # Rajadas com o transmissor junto ao gateway (c3-capture.log, 08h35).
    ondas = re.findall(r"\[WAVE\] seq=\d+ fragments=(\d+) sent=(\d+) rounds=(\d+) complete=(\d) took=(\d+)ms",
                       (BENCH / "c3-capture.log").read_text())
    um = [int(t) for _, _, r, _, t in ondas if r == "1"]
    dois = [(int(s), int(t)) for _, s, r, _, t in ondas if r == "2"]
    m.update(sisCapturaRajadas=str(len(ondas)), sisCapturaCompletas=str(sum(c == "1" for *_, c, _ in ondas)),
             sisCapturaUmaRodada=str(len(um)), sisCapturaUmaRodadaS=br(min(um) / 1000, 2),
             sisCapturaDuasRodadas=str(len(dois)), sisCapturaDuasRodadasEnvios=str(dois[0][0]),
             sisCapturaDuasRodadasS=br(dois[0][1] / 1000, 2))

    # Transmissor sem gateway (linkloss.log).
    ll = (BENCH / "linkloss.log").read_text()
    ciclos = re.findall(r"\[\+(\d+):(\d+):([\d.]+)\]\[kaelix\]\[INFO\]\[CYCLE\] seq=(\d+)", ll)
    boots = len(re.findall(r"\[BOOT\] transmitter", ll))
    fim = int(ciclos[-1][0]) * 3600 + int(ciclos[-1][1]) * 60 + float(ciclos[-1][2])
    fallback = re.search(r"gateway silent for (\d+) s; fallback power and no routine", ll)
    m.update(sisSemGatewayCiclos=str(len(ciclos)), sisSemGatewayMin=str(round(fim / 60)),
             sisSemGatewayReinicios=str(boots - 1), sisSemGatewayFallbackS=fallback[1])

    # Banco de teste da bancada (temp-db.dump).
    dump = BENCH / "temp-db.dump"
    leituras = [r for r in tabela(dump, "readings") if r["device_id"] == DISPOSITIVO]
    for r in leituras:
        r["p"] = json.loads(r["payload"])
    chave = [(r["p"]["boot_count"], r["p"]["device_sequence"]) for r in leituras]
    rssi = [r["p"]["rssi_dbm"] for r in leituras if r["p"].get("rssi_dbm") is not None]
    snr = [r["p"]["snr_db"] for r in leituras if r["p"].get("snr_db") is not None]
    taxa = [r["p"]["sample_rate_hz"] for r in leituras if r["p"].get("sample_rate_hz") is not None]
    m.update(sisBancoLeituras=str(len(leituras)), sisBancoDuplicatas=str(len(chave) - len(set(chave))),
             sisBancoRssiMin=br(min(rssi), 0), sisBancoRssiMax=br(max(rssi), 0),
             sisBancoSnrMin=br(min(snr), 2), sisBancoSnrMax=br(max(snr), 2),
             sisBancoTaxaMin=br(min(taxa), 2), sisBancoTaxaMax=br(max(taxa), 2))

    janelas = [w for w in tabela(dump, "waveforms") if w["device_id"] == DISPOSITIVO]
    completas = sha_ok = 0
    for w in janelas:
        md = json.loads(w["metadata"])
        completas += not md.get("fragments_missing")
        amostras = bytes.fromhex(w["samples"].removeprefix("\\\\x").removeprefix("\\x"))
        sha_ok += hashlib.sha256(amostras).hexdigest() == md.get("samples_sha256")
    m.update(sisBancoJanelas=str(len(janelas)), sisBancoJanelasCompletas=str(completas),
             sisBancoShaConfere=str(sha_ok))

    imagens = tabela(dump, "gateway_firmware")
    aplicadas = [i for i in imagens if i["state"] == "applied"]
    revertidas = [i for i in imagens if i["state"] == "failed" and "rolled back" in i["reason"]]
    sem_conf = [i for i in imagens if i["state"] == "failed" and "rolled back" not in i["reason"]]
    duracoes = [(instante(i["finished_at"]) - instante(i["offered_at"])).total_seconds() for i in aplicadas]
    tamanhos = [int(i["size"]) for i in aplicadas]
    m.update(sisOtaImagens=str(len(imagens)), sisOtaAplicadas=str(len(aplicadas)),
             sisOtaRevertidas=str(len(revertidas)), sisOtaSemConfirmacao=str(len(sem_conf)),
             sisOtaSemConfirmacaoBytes=inteiro(int(sem_conf[0]["size"])) if sem_conf else "0",
             sisOtaRevertidaVersao=revertidas[0]["version"].removeprefix("gateway-") if revertidas else "",
             sisOtaDuracaoMin=str(round(min(duracoes))), sisOtaDuracaoMax=str(round(max(duracoes))),
             sisOtaTamanhoMin=br(min(tamanhos) / 1e6, 2), sisOtaTamanhoMax=br(max(tamanhos) / 1e6, 2))

    comandos = sorted(tabela(dump, "device_commands"), key=lambda c: int(c["seq"]))

    def espera(c):
        return (instante(c["applied_at"]) - instante(c["created_at"])).total_seconds()
    captura = [c for c in comandos if c["kind"] == "capture_now"]
    reinicio = [c for c in comandos if c["kind"] == "reboot"]
    fabrica = [c for c in comandos if c["kind"] == "factory_reset"]
    m.update(sisComandoCapturaS=str(round(espera(captura[0]))),
             sisComandoCapturaForaMin=str(int(espera(captura[1]) // 60)),
             sisComandoCapturaForaS=str(round(espera(captura[1]) % 60)),
             sisComandoCapturaSemOndaMin=str(int(espera(captura[2]) // 60)),
             sisComandoCapturaSemOndaS=str(round(espera(captura[2]) % 60)),
             sisComandoReinicioMin=str(int(espera(reinicio[0]) // 60)),
             sisComandoReinicioS=str(round(espera(reinicio[0]) % 60)),
             sisComandoFabricaMin=str(int(espera(fabrica[0]) // 60)),
             sisComandoFabricaS=str(round(espera(fabrica[0]) % 60)))

    # Queda da API das 07h51min20s às 07h53min50s, com o gateway reiniciado às 07h52min35s (outage.log).
    queda_ini = dt.datetime(2026, 11, 2, 7, 51, 20, tzinfo=FUSO)
    queda_fim = dt.datetime(2026, 11, 2, 7, 53, 50, tzinfo=FUSO)
    depois = dt.datetime(2026, 11, 2, 7, 55, 20, tzinfo=FUSO)
    na_queda = [r for r in leituras if queda_ini <= instante(r["ingested_at"]) <= depois
                and int(r["queue_delay_ms"]) > 0]
    atrasos = [int(r["queue_delay_ms"]) / 1000 for r in na_queda]
    m.update(sisQuedaApiS=str(round((queda_fim - queda_ini).total_seconds())),
             sisQuedaLeiturasFlash=str(len(na_queda)),
             sisQuedaAtrasoMin=br(min(atrasos), 1), sisQuedaAtrasoMax=br(max(atrasos), 1))

    # Defeito de gravação (EBADF) na sessão 8d5bee6c do gateway: lacunas de sequência por inicialização do
    # transmissor e janelas sem a telemetria correspondente.
    sessao = [r for r in leituras if r["gateway_session_id"].startswith("8d5bee6c")]
    eventos = {r["event_seq"] for r in sessao}
    orfas = [json.loads(w["metadata"]) for w in janelas
             if w["gateway_session_id"].startswith("8d5bee6c") and w["event_seq"] not in eventos]
    perdidas = 0
    for b in sorted({r["p"]["boot_count"] for r in sessao}):
        vistas = {r["p"]["device_sequence"] for r in sessao if r["p"]["boot_count"] == b}
        com_janela = {o["device_sequence"] for o in orfas if o.get("boot_count") == b}
        faixa = range(min(vistas | com_janela), max(vistas | com_janela) + 1)
        perdidas += sum(q not in vistas for q in faixa)
    m.update(sisEbadfLeiturasPerdidas=str(perdidas), sisEbadfJanelasSemTelemetria=str(len(orfas)))

    with open(SAIDA, "w", encoding="utf-8") as f:
        f.write("%% Gerado por scripts/build_sistema_values.py; não editar à mão.\n")
        for k in sorted(m):
            f.write(f"\\newcommand{{\\{k}}}{{{m[k]}}}\n")
    for k in sorted(m):
        print(k, m[k])


if __name__ == "__main__":
    main()
