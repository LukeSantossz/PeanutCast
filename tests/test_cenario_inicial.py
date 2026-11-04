"""Cenário em que o painel abre, pela previsão sazonal do CPTEC, e o ranking.

Roda painel.js no Node com o pacote real. Pulado sem Node ou sem dados/.
"""
import json
import shutil
import subprocess

import pytest

from peanutcast import painel, previsao

NODE = shutil.which("node")

RODAR = """
import { readFileSync } from 'node:fs';
const { iniciar, S, mudarCenario, notaCptec, notaRegiao, ordem, fichaHtml } = await import(process.argv[1]);
const pacote = JSON.parse(readFileSync(0, 'utf8'));
const r = {};
iniciar(pacote);
r.inicial = S.cen;
r.regiao = notaRegiao();
r.notas = Object.fromEntries(pacote.municipios.map(m => [m.nome, notaCptec(m)]));
const m = pacote.municipios.find(x => x.cenarios && x.media != null);
r.ficha = fichaHtml(m, 'Normal', m.cenarios.Normal);
r.ranking = Object.fromEntries(['Seco', 'Normal', 'Chuvoso'].map(c => { mudarCenario(c); return [c, ordem().map(x => x.nome)]; }));
mudarCenario('Seco');
iniciar({ ...pacote, versao: 'outra' });
r.depois = S.cen;
process.stdout.write(JSON.stringify(r));
"""


@pytest.fixture(scope="module")
def pacote():
    if NODE is None:
        pytest.skip("sem Node no PATH")
    if not painel.pronto():
        pytest.skip("sem dados/tratados: rode scripts/integrar.py")
    return json.loads(json.dumps(dict(painel._pacote(painel.dados.versao()), geo=None)))


@pytest.fixture(scope="module")
def modulo(tmp_path_factory):
    destino = tmp_path_factory.mktemp("js") / "painel.mjs"
    shutil.copy(painel.INTERFACE / "painel.js", destino)
    return destino.as_uri()


def rodar(modulo, pacote):
    saida = subprocess.run([NODE, "--input-type=module", "-e", RODAR, modulo],
                           input=json.dumps(pacote), capture_output=True, text=True, encoding="utf-8", check=True)
    return json.loads(saida.stdout)


def com_boletim(pacote):
    a, b = pacote["municipios"][0], pacote["municipios"][1]
    return dict(pacote, proxima=2027, boletim={
        "cenario": "Chuvoso", "safra": 2027, "janela": "dez/2026 a fev/2027", "emissao": "set/2026",
        "municipios": {str(a["codigo"]): {"cen": "Chuvoso", "prob": 0.45}, str(b["codigo"]): {"cen": "Normal", "prob": None}},
    }), a["nome"], b["nome"]


def test_sem_previsao_abre_no_normal_e_avisa_quando_sai(modulo, pacote):
    r = rodar(modulo, dict(pacote, boletim=None, proxima=pacote["anos"][-1] + 1))
    assert r["inicial"] == "Normal"
    assert "meados de outubro" in r["regiao"]
    assert all(n == "" for n in r["notas"].values())


def test_com_previsao_abre_no_cenario_sugerido(modulo, pacote):
    p, _, _ = com_boletim(pacote)
    r = rodar(modulo, p)
    assert r["inicial"] == "Chuvoso"
    assert "Previsão sazonal do CPTEC" in r["regiao"]
    assert "set/2026" in r["regiao"] and "dez/2026 a fev/2027" in r["regiao"] and "chuvoso" in r["regiao"]


def test_troca_manual_nao_volta_para_o_sugerido(modulo, pacote):
    assert rodar(modulo, com_boletim(pacote)[0])["depois"] == "Seco"


def test_ficha_mostra_o_tercil_do_municipio(modulo, pacote):
    p, a, b = com_boletim(pacote)
    notas = rodar(modulo, p)["notas"]
    assert "45%" in notas[a] and "acima da normal" in notas[a]
    assert "perto da normal" in notas[b] and "%" not in notas[b]
    outros = [n for nome, n in notas.items() if nome not in (a, b)]
    assert outros and all(n == "" for n in outros)


def test_rotulo_da_safra_segue_a_previsao(modulo, pacote):
    r = rodar(modulo, com_boletim(pacote)[0])
    assert "safra 2027" in r["ficha"]


def test_ranking_ordena_pelo_cenario_escolhido(modulo, pacote):
    r = rodar(modulo, dict(pacote, boletim=None))
    prev = {m["nome"]: m["prev"] for m in pacote["municipios"] if m["media"] is not None and m["cenarios"]}
    for cenario in previsao.CENARIOS:
        valores = [prev[n][cenario] for n in r["ranking"][cenario]]
        assert valores == sorted(valores, reverse=True), cenario
        assert set(r["ranking"][cenario]) == set(prev)
