"""A ficha exportável do município, montada por fichaHtml() em painel.js.

Roda o JS no Node com o pacote real que o painel manda ao navegador. Pulado sem
Node ou sem dados/ e modelos/ (fora do Git; ver scripts/integrar.py).
"""
import itertools
import json
import math
import re
import shutil
import subprocess
from decimal import ROUND_HALF_UP, Decimal
from html.parser import HTMLParser

import pytest

from peanutcast import painel, previsao

NODE = shutil.which("node")
JS = painel.INTERFACE / "painel.js"

# Lê do stdin {pacote, pedidos} e devolve uma ficha por pedido.
RODAR = """
import { readFileSync } from 'node:fs';
const { iniciar, fichaHtml } = await import(process.argv[1]);
const { pacote, pedidos } = JSON.parse(readFileSync(0, 'utf8'));
iniciar(pacote);
const mun = Object.fromEntries(pacote.municipios.map(m => [m.nome, m]));
process.stdout.write(JSON.stringify(pedidos.map(p => fichaHtml(mun[p.nome], p.cen, p.c ?? mun[p.nome].cenarios[p.cen]))));
"""

# exportarFicha() com o navegador simulado: window.open, URL e o <a> do download.
EXPORTAR = """
import { readFileSync } from 'node:fs';
const { iniciar, fichaHtml, exportarFicha } = await import(process.argv[1]);
const { pacote, nome, bloqueado } = JSON.parse(readFileSync(0, 'utf8'));
iniciar(pacote);
const m = pacote.municipios.find(x => x.nome === nome), r = { abertos: [], baixados: [], revogados: [], timers: [] };
let blob;
URL.createObjectURL = b => { blob = b; return 'blob:1'; };
URL.revokeObjectURL = u => r.revogados.push(u);
globalThis.setTimeout = (f, ms) => { r.timers.push(ms); f(); };
globalThis.window = { open: (url, alvo) => { r.abertos.push([url, alvo]); return bloqueado ? null : {}; } };
globalThis.document = { createElement: () => ({ click() { r.baixados.push({ href: this.href, download: this.download }); } }) };
exportarFicha(m);
r.tipo = blob.type; r.igual = (await blob.text()) === fichaHtml(m, 'Normal', m.cenarios.Normal);
process.stdout.write(JSON.stringify(r));
"""
# vizinha() de painel.js: a safra de clima mais parecida, por pedido {nome, c}.
VIZINHA = """
import { readFileSync } from 'node:fs';
const { iniciar, vizinha } = await import(process.argv[1]);
const { pacote, pedidos } = JSON.parse(readFileSync(0, 'utf8'));
iniciar(pacote);
const mun = Object.fromEntries(pacote.municipios.map(m => [m.nome, m]));
process.stdout.write(JSON.stringify(pedidos.map(p => vizinha(mun[p.nome], p.c))));
"""
LONGE = 1.5  # o limite do alerta em painel.js, em desvios típicos
ROT = {"chuva_critica_mm": "Chuva", "temp_max_critica_c": "Máxima média",
       "radiacao_critica_mj_m2": "Radiação", "dias_calor_critica": "Dias acima de 35 °C"}
DEC = {"chuva_critica_mm": 0, "temp_max_critica_c": 1, "radiacao_critica_mj_m2": 1, "dias_calor_critica": 0}


@pytest.fixture(scope="module")
def pacote():
    if NODE is None:
        pytest.skip("sem Node no PATH")
    if not painel.pronto():
        pytest.skip("sem dados/tratados: rode scripts/integrar.py")
    # Sem a geometria: a ficha não usa, e o JSON fica bem menor.
    return json.loads(json.dumps(dict(painel._pacote(painel.dados.versao()), geo=None)))


@pytest.fixture(scope="module")
def modulo(tmp_path_factory):
    # .mjs para o Node ler como módulo sem depender de package.json.
    destino = tmp_path_factory.mktemp("js") / "painel.mjs"
    shutil.copy(JS, destino)
    return destino.as_uri()


def fichas(modulo, pacote, pedidos):
    saida = subprocess.run(
        [NODE, "--input-type=module", "-e", RODAR, modulo],
        input=json.dumps({"pacote": pacote, "pedidos": pedidos}),
        capture_output=True, text=True, encoding="utf-8", check=True,
    )
    return json.loads(saida.stdout)


def vizinhas(modulo, pacote, pedidos):
    saida = subprocess.run(
        [NODE, "--input-type=module", "-e", VIZINHA, modulo],
        input=json.dumps({"pacote": pacote, "pedidos": pedidos}),
        capture_output=True, text=True, encoding="utf-8", check=True,
    )
    return json.loads(saida.stdout)


def vizinha(pacote, m, clima):
    """A conta de vizinha() em Python: (ano, distância em desvios típicos)."""
    sd = pacote["modelo"]["sd"]
    distancias = [
        (ano, math.sqrt(sum(((clima[c] - m["clima"][c][i]) / s) ** 2 for c, s in zip(pacote["colunas"], sd))))
        for i, ano in enumerate(pacote["anos"])
        if all(m["clima"][c][i] is not None for c in pacote["colunas"])
    ]
    return min(distancias, key=lambda t: t[1])


def climas_de_teste(m):
    """Os cenários, cada variável no mínimo e no máximo, e cada par de variáveis nas pontas."""
    base = m["cenarios"]["Normal"]
    climas = [m["cenarios"][c] for c in previsao.CENARIOS]
    climas += [dict(base, **{c: m["lim"][c][p]}) for c in previsao.COLUNAS for p in (0, 1)]
    climas += [
        dict(base, **{a: m["lim"][a][pa], b: m["lim"][b][pb]})
        for a, b in itertools.combinations(previsao.COLUNAS, 2) for pa in (0, 1) for pb in (0, 1)
    ]
    return climas


def exportar(modulo, pacote, nome, bloqueado):
    saida = subprocess.run(
        [NODE, "--input-type=module", "-e", EXPORTAR, modulo],
        input=json.dumps({"pacote": pacote, "nome": nome, "bloqueado": bloqueado}),
        capture_output=True, text=True, encoding="utf-8", check=True,
    )
    return json.loads(saida.stdout)


def com_previsao(pacote):
    return [m for m in pacote["municipios"] if m["media"] is not None and m["cenarios"]]


def br(v, casas=0):
    """fmt() de painel.js: pt-BR, arredondando metade para cima."""
    q = Decimal(str(abs(v))).quantize(Decimal(1).scaleb(-casas), ROUND_HALF_UP)
    inteiro, _, frac = f"{q:,.{casas}f}".partition(".")
    return ("-" if v < 0 and q else "") + inteiro.replace(",", ".") + ("," + frac if frac else "")


def numero(txt):
    return float(txt.strip().replace(".", "").replace(",", ".").replace("−", "-").replace("+", ""))


class Tabelas(HTMLParser):
    """As linhas de cada <table class="...">, como listas de textos das células."""

    def __init__(self):
        super().__init__()
        self.tabelas, self._classe, self._linha, self._celula = {}, None, None, None

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self._classe = dict(attrs).get("class")
            self.tabelas.setdefault(self._classe, [])
        elif tag == "tr" and self._classe:
            self._linha = []
        elif tag in ("td", "th") and self._linha is not None:
            self._celula = ""

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._celula is not None:
            self._linha.append(self._celula.strip())
            self._celula = None
        elif tag == "tr" and self._linha is not None:
            self.tabelas[self._classe].append(self._linha)
            self._linha = None
        elif tag == "table":
            self._classe = None

    def handle_data(self, data):
        if self._celula is not None:
            self._celula += data


def tabelas(html):
    t = Tabelas()
    t.feed(html)
    return t.tabelas


def conta(pacote, m, clima):
    M = pacote["modelo"]
    return m["media"] + M["b"] + sum(
        k * (clima[c] - mu) / sd for c, k, mu, sd in zip(pacote["colunas"], M["coef"], M["mu"], M["sd"])
    )


def test_ficha_e_uma_pagina_completa(modulo, pacote):
    m = com_previsao(pacote)[0]
    (html,) = fichas(modulo, pacote, [{"nome": m["nome"], "cen": "Normal"}])
    assert html.lower().startswith("<!doctype html>")
    assert 'lang="pt-BR"' in html
    assert re.search(rf"<title>[^<]*{re.escape(m['nome'])}[^<]*</title>", html)
    assert "@media print" in html
    assert "src=" not in html and "<link" not in html


def test_ficha_traz_previsao_e_faixa(modulo, pacote):
    ms = com_previsao(pacote)
    pedidos = [{"nome": m["nome"], "cen": c} for m in ms for c in previsao.CENARIOS]
    erro = pacote["erro"]
    for p, html in zip(pedidos, fichas(modulo, pacote, pedidos)):
        v = next(m for m in ms if m["nome"] == p["nome"])["prev"][p["cen"]]
        for numero_esperado in (br(v), br(v - erro), br(v + erro)):
            assert numero_esperado in html, (p, numero_esperado)
        assert "ajustado" not in html, p


def test_porque_soma_a_previsao(modulo, pacote):
    ms = com_previsao(pacote)
    pedidos = [{"nome": m["nome"], "cen": c} for m in ms for c in previsao.CENARIOS]
    for p, html in zip(pedidos, fichas(modulo, pacote, pedidos)):
        linhas = tabelas(html)["porque"]
        partes, total = linhas[:-1], linhas[-1]
        assert len(partes) == 2 + len(previsao.COLUNAS), p
        assert total[0] == "Previsão", p
        # Cada parte vem arredondada ao kg: a soma pode errar meio kg por linha.
        assert abs(sum(numero(parte[-1]) for parte in partes) - numero(total[-1])) <= 0.5 * len(linhas), p


def test_ficha_nomeia_efeito_climatico(modulo, pacote):
    m = com_previsao(pacote)[0]
    (html,) = fichas(modulo, pacote, [{"nome": m["nome"], "cen": "Normal"}])
    assert "Efeito do clima simulado" in html
    codigo = JS.read_text(encoding="utf-8")
    assert "Clima do cenário" not in codigo
    assert codigo.count("NOME_EFEITO_CLIMA") >= 3


@pytest.mark.parametrize("ponta", [0, 1], ids=["minimo", "maximo"])
@pytest.mark.parametrize("coluna", previsao.COLUNAS)
def test_ficha_reflete_o_clima_ajustado(modulo, pacote, coluna, ponta):
    m, casas = com_previsao(pacote)[0], DEC[coluna]
    clima = dict(m["cenarios"]["Normal"], **{coluna: m["lim"][coluna][ponta]})
    (html,) = fichas(modulo, pacote, [{"nome": m["nome"], "cen": "Normal", "c": clima}])
    assert "ajustado" in html
    assert tabelas(html)["porque"][-1][-1] == br(conta(pacote, m, clima))
    linha = next(t for t in tabelas(html)["clima"] if t[0].startswith(ROT[coluna]))
    minimo, maximo = m["lim"][coluna]
    assert linha[1:] == [br(clima[coluna], casas), f"{br(minimo, casas)} a {br(maximo, casas)}"]


def test_ajuste_de_volta_ao_cenario_continua_ajustado(modulo, pacote):
    # A tela diz "ajustado" enquanto houver ajuste, mesmo com o controle de volta
    # ao valor do cenário; a ficha diz o mesmo.
    m = com_previsao(pacote)[0]
    (html,) = fichas(modulo, pacote, [{"nome": m["nome"], "cen": "Normal", "c": dict(m["cenarios"]["Normal"])}])
    assert "ajustado" in html
    assert tabelas(html)["porque"][-1][-1] == br(m["prev"]["Normal"])


@pytest.mark.parametrize("bloqueado", [False, True], ids=["aba_nova", "popup_bloqueado"])
def test_exportar_abre_aba_ou_baixa_arquivo(modulo, pacote, bloqueado):
    m = com_previsao(pacote)[0]
    r = exportar(modulo, pacote, m["nome"], bloqueado)
    assert r["abertos"] == [["blob:1", "_blank"]]
    assert r["igual"] and r["tipo"].startswith("text/html")
    assert r["timers"] == [60000] and r["revogados"] == ["blob:1"]
    if bloqueado:
        (baixado,) = r["baixados"]
        assert baixado["href"] == "blob:1"
        assert re.fullmatch(rf"peanutcast-[a-z0-9-]+-{pacote['proxima']}\.html", baixado["download"])
    else:
        assert r["baixados"] == []


def test_ficha_escapa_o_nome(modulo, pacote):
    m = com_previsao(pacote)[0]
    nome = 'Vila <b>&"Teste"'
    copia = dict(pacote, municipios=[dict(x, nome=nome) if x is m else x for x in pacote["municipios"]])
    (html,) = fichas(modulo, copia, [{"nome": nome, "cen": "Normal"}])
    assert nome not in html
    assert "Vila &lt;b&gt;&amp;&quot;Teste&quot;" in html


def test_ficha_traz_historico_e_limitacoes(modulo, pacote):
    m = com_previsao(pacote)[0]
    (html,) = fichas(modulo, pacote, [{"nome": m["nome"], "cen": "Normal"}])
    safras = [(a, h) for a, h in zip(pacote["anos"], m["hist"]) if h]
    linhas = tabelas(html)["hist"]
    corpo = [linha for linha in linhas if linha and linha[0].isdigit()]
    assert [int(linha[0]) for linha in corpo] == [a for a, _ in safras]
    assert [numero(linha[1]) for linha in corpo] == [h["r"] for _, h in safras]
    assert "Não é intervalo de confiança" in html
    assert "não prevê o tempo" in html


def test_vizinha_e_a_safra_mais_parecida(modulo, pacote):
    pedidos = [{"nome": m["nome"], "c": c} for m in com_previsao(pacote) for c in climas_de_teste(m)]
    ms = {m["nome"]: m for m in pacote["municipios"]}
    for p, js in zip(pedidos, vizinhas(modulo, pacote, pedidos)):
        ano, d = vizinha(pacote, ms[p["nome"]], p["c"])
        assert js["ano"] == ano and abs(js["d"] - d) < 1e-9, (p["nome"], js, ano, d)


def test_cenarios_nao_disparam_o_alerta(modulo, pacote):
    ms = com_previsao(pacote)
    for m in ms:
        for c in previsao.CENARIOS:
            assert vizinha(pacote, m, m["cenarios"][c])[1] <= LONGE, (m["nome"], c)
    pedidos = [{"nome": m["nome"], "cen": c} for m in ms for c in previsao.CENARIOS]
    for p, html in zip(pedidos, fichas(modulo, pacote, pedidos)):
        assert "nunca teve" not in html, p


def test_alerta_aparece_so_longe_das_safras(modulo, pacote):
    casos = [(m, c) for m in com_previsao(pacote) for c in climas_de_teste(m)]
    pedidos = [{"nome": m["nome"], "cen": "Normal", "c": c} for m, c in casos]
    lados = set()
    for (m, c), html in zip(casos, fichas(modulo, pacote, pedidos)):
        ano, d = vizinha(pacote, m, c)
        longe = d > LONGE
        lados.add(longe)
        assert ("nunca teve" in html) == longe, (m["nome"], c, d)
        if longe:
            assert f"safra mais parecida, {ano}, fica a {br(d, 1)} desvios" in html, (m["nome"], ano, d)
    assert lados == {True, False}


def test_vizinha_pula_ano_sem_clima(modulo, pacote):
    m = com_previsao(pacote)[0]
    clima = {c: [None, *serie[1:]] for c, serie in m["clima"].items()}
    copia = dict(pacote, municipios=[dict(x, clima=clima) if x is m else x for x in pacote["municipios"]])
    # Em JS, null - x vale -x: sem pular o ano, o clima zerado acharia o ano apagado.
    alvo = dict.fromkeys(previsao.COLUNAS, 0.0)
    (js,) = vizinhas(modulo, copia, [{"nome": m["nome"], "c": alvo}])
    ano, d = vizinha(copia, dict(m, clima=clima), alvo)
    assert js["ano"] == ano != pacote["anos"][0] and abs(js["d"] - d) < 1e-9
