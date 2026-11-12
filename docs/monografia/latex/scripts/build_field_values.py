"""Gera values/campo_values.tex com os números descritivos da coleta em campo.

Lê os arquivos exportados por experiments/campo/exportar_campo.py (ensaios.csv, leituras.csv, janelas.csv) e escreve
um \\newcommand por número. O texto da monografia usa só essas macros; nenhum número da coleta é digitado à mão.

Uso, a partir de docs/monografia/latex/: make values
"""
import csv
import hashlib
import pathlib
import re
import statistics

AQUI = pathlib.Path(__file__).resolve().parent
DADOS = AQUI.parents[3] / "experiments" / "campo" / "dados"
SAIDA = AQUI.parent / "values" / "campo_values.tex"

NOMES = {("Dobradeira", "1"): "DobradeiraUm", ("Guilhotina", "1"): "GuilhotinaUm", ("Guilhotina", "2"): "GuilhotinaDois",
         ("Calandra", "1"): "CalandraUm", ("Calandra", "2"): "CalandraDois", ("Compressor", "1"): "CompressorUm",
         ("Motor parado", "1"): "MotorParado"}


def inteiro(n):
    return f"{n:,}".replace(",", ".").replace("-", "\\textminus ")


def decimal(x, casas):
    return f"{x:.{casas}f}".replace(".", ",")


def main():
    ensaios = list(csv.DictReader(open(DADOS / "ensaios.csv", encoding="utf-8")))
    leituras = list(csv.DictReader(open(DADOS / "leituras.csv", encoding="utf-8")))
    janelas = list(csv.DictReader(open(DADOS / "janelas.csv", encoding="utf-8")))
    nome = {e["ensaio"]: NOMES[(e["maquina"], e["rodada"])] for e in ensaios}

    v = {}
    v["campoEnsaios"] = inteiro(sum(1 for e in ensaios if e["maquina"] != "Motor parado"))
    v["campoMaquinas"] = inteiro(len({e["maquina"] for e in ensaios if e["maquina"] != "Motor parado"}))
    v["campoJanelas"] = inteiro(len(janelas))
    v["campoLeituras"] = inteiro(len(leituras))
    parados = {e["ensaio"] for e in ensaios if e["maquina"] == "Motor parado"}
    v["campoJanelasOperacao"] = inteiro(sum(1 for j in janelas if j["ensaio"] not in parados))

    lacunas = 0
    for e in ensaios:
        seq = sorted(int(r["device_sequence"]) for r in leituras if r["ensaio"] == e["ensaio"])
        lacunas += sum(b - a - 1 for a, b in zip(seq, seq[1:]) if b > a + 1)
    v["campoLacunas"] = inteiro(lacunas)
    # Oração para "a sequência das telemetrias ...", sem "0 lacunas" no texto.
    v["campoLacunasTexto"] = ("não teve nenhuma lacuna" if lacunas == 0 else
                              "teve uma lacuna" if lacunas == 1 else f"teve {inteiro(lacunas)} lacunas")

    taxas = [float(r["sample_rate_hz"]) for r in leituras if r["sample_rate_hz"]]
    v["campoTaxaMin"] = decimal(min(taxas), 2)
    v["campoTaxaMax"] = decimal(max(taxas), 2)
    v["campoDesvioTaxaMax"] = decimal(max(abs(t - 1000.0) / 1000.0 * 100 for t in taxas), 2)

    potencias = {r["tx_power_dbm"] for r in leituras}
    if len(potencias) != 1:
        raise SystemExit(f"potência de transmissão variou na coleta: {sorted(potencias)}")
    v["campoPotenciaTx"] = inteiro(int(potencias.pop()))

    rssi = [float(r["rssi_dbm"]) for r in leituras if r["rssi_dbm"]]
    v["campoRssiMin"] = inteiro(int(min(rssi)))
    v["campoRssiMax"] = inteiro(int(max(rssi)))

    for e in ensaios:
        chave = nome[e["ensaio"]]
        v[f"campoJanelas{chave}"] = inteiro(sum(1 for j in janelas if j["ensaio"] == e["ensaio"]))
        rms = [float(r["rms_g"]) for r in leituras if r["ensaio"] == e["ensaio"]]
        v[f"campoRms{chave}"] = decimal(statistics.median(rms) * 1000, 1)
        v[f"campoInicio{chave}"] = e["inicio_local"][:5].replace(":", "h")
        v[f"campoFim{chave}"] = e["fim_local"][:5].replace(":", "h")
        # Temperatura do sensor informada na telemetria: mediana do ensaio, em graus Celsius.
        temp = [float(r["temperature_c"]) for r in leituras if r["ensaio"] == e["ensaio"] and r["temperature_c"]]
        v[f"campoTemp{chave}"] = decimal(statistics.median(temp), 1)
        if e["rotacao_busca_hz"]:
            v[f"campoBusca{chave}"] = decimal(float(e["rotacao_busca_hz"]), 1)

    # Faixa das medianas de temperatura dos ensaios em operação, por rodada.
    for rodada, chave in (("1", "Um"), ("2", "Dois")):
        meds = [statistics.median(float(r["temperature_c"]) for r in leituras if r["ensaio"] == e["ensaio"] and r["temperature_c"])
                for e in ensaios if e["rodada"] == rodada and e["maquina"] != "Motor parado"]
        v[f"campoTempRodada{chave}Min"] = decimal(min(meds), 1)
        v[f"campoTempRodada{chave}Max"] = decimal(max(meds), 1)

    # Intervalo entre os inícios das duas rodadas, pelos horários em hora e minuto da Tabela de ensaios.
    def minutos(hora):
        h, m = hora.split(":")[:2]
        return int(h) * 60 + int(m)
    for maquina in ("Calandra", "Guilhotina"):
        inicio = {e["rodada"]: minutos(e["inicio_local"]) for e in ensaios if e["maquina"] == maquina}
        dif = inicio["2"] - inicio["1"]
        v[f"campoIntervalo{maquina}"] = f"{dif // 60}~h~{dif % 60:02d}~min"

    # Intervalo entre ciclos por rodada, pela mediana das diferenças entre recebimentos consecutivos do mesmo ensaio.
    from datetime import datetime, timedelta
    for rodada, chave in (("1", "Um"), ("2", "Dois")):
        difs = []
        for e in ensaios:
            if e["rodada"] != rodada or e["maquina"] == "Motor parado":
                continue
            ts = sorted(datetime.fromisoformat(r["recebida_utc"]) for r in leituras if r["ensaio"] == e["ensaio"])
            difs += [(b - a).total_seconds() for a, b in zip(ts, ts[1:])]
        ciclo = round(statistics.median(difs))
        v[f"campoCiclo{chave}"] = inteiro(ciclo)
        v[f"campoCobertura{chave}"] = decimal(100 * 0.512 / ciclo, 1)

    repouso = list(csv.DictReader(open(DADOS / "repouso.csv", encoding="utf-8")))
    rajadas = list(csv.DictReader(open(DADOS / "rajadas.csv", encoding="utf-8")))
    v["campoJanelasRepouso"] = inteiro(len(repouso))
    # recebida_utc está em UTC; o texto usa a hora local (UTC-3).
    horas = sorted(datetime.fromisoformat(r["recebida_utc"]) - timedelta(hours=3) for r in repouso)
    v["campoRepousoInicio"] = horas[0].strftime("%Hh%M")
    v["campoRepousoFim"] = horas[-1].strftime("%Hh%M")
    v["campoRajadas"] = inteiro(len(rajadas))
    v["campoRajadasInicio"] = min(r["hora_local"] for r in rajadas)[:5].replace(":", "h")
    v["campoRajadasFim"] = max(r["hora_local"] for r in rajadas)[:5].replace(":", "h")

    # Registro das hipóteses: início do SHA-256, conferido contra o arquivo.
    registro = AQUI.parents[1] / "registro"
    sha_gravado = (registro / "registro_v1.sha256").read_text(encoding="utf-8").split()[0]
    sha_calculado = hashlib.sha256((registro / "registro_v1.md").read_bytes()).hexdigest()
    if sha_gravado != sha_calculado:
        raise SystemExit("registro_v1.md não confere com registro_v1.sha256")
    v["registroShaCurto"] = sha_gravado[:8]
    # Emendas do registro (v2: H4, AP1 e AP2; v3: fonte dos dados de H4), conferidas do mesmo modo.
    for versao, chave in ((2, "Dois"), (3, "Tres")):
        gravado = (registro / f"registro_v{versao}.sha256").read_text(encoding="utf-8").split()[0]
        if gravado != hashlib.sha256((registro / f"registro_v{versao}.md").read_bytes()).hexdigest():
            raise SystemExit(f"registro_v{versao}.md não confere com registro_v{versao}.sha256")
        v[f"registro{chave}ShaCurto"] = gravado[:8]
    # Frações marcadas nas análises exploratórias anteriores ao registro, como o próprio registro as declara.
    texto = (registro / "registro_v1.md").read_text(encoding="utf-8")
    m = re.search(r"falso alarme de (\d+) % a (\d+) % e de (\d+) % a (\d+) %", texto)
    if not m:
        raise SystemExit("frações exploratórias não encontradas em registro_v1.md")
    for chave, valor in zip(("ExplIfMin", "ExplIfMax", "ExplMadMin", "ExplMadMax"), m.groups()):
        v[f"registro{chave}"] = inteiro(int(valor))

    linhas = ["% Gerado por scripts/build_field_values.py; não editar à mão."]
    linhas += [f"\\newcommand{{\\{k}}}{{{v[k]}}}" for k in sorted(v)]
    SAIDA.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    print(f"{len(v)} valores em {SAIDA}")


if __name__ == "__main__":
    main()
