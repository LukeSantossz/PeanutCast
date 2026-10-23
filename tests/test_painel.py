"""O pacote que o painel manda para o navegador.

Os testes com o pacote real leem dados/ e modelos/, que ficam fora do Git, e
são pulados se `scripts/integrar.py` ainda não rodou nesta máquina.
"""
import json

import pandas as pd
import pytest

from peanutcast import painel, previsao
from peanutcast.municipios import MUNICIPIOS


@pytest.fixture(scope="module")
def pacote():
    if not painel.pronto():
        pytest.skip("sem dados/tratados: rode scripts/integrar.py")
    return painel._pacote(painel.dados.versao())


def com_previsao(pacote):
    """Os municípios que o navegador trata como previsíveis (temPrev em painel.js)."""
    return [m for m in pacote["municipios"] if m["media"] is not None and m["cenarios"]]


def test_pacote_vira_json_sem_nan(pacote):
    json.dumps(pacote, allow_nan=False)


def test_pacote_traz_os_24_municipios(pacote):
    assert [m["codigo"] for m in pacote["municipios"]] == list(MUNICIPIOS)
    assert com_previsao(pacote)


def test_series_tem_um_valor_por_ano(pacote):
    anos = len(pacote["anos"])
    for m in pacote["municipios"]:
        assert len(m["hist"]) == anos, m["nome"]
        for coluna in previsao.COLUNAS:
            assert len(m["clima"][coluna]) == anos, (m["nome"], coluna)


def test_navegador_refaz_a_previsao_de_cada_cenario(pacote):
    # A conta de prever() em painel.js, com os números que o navegador recebe.
    M = pacote["modelo"]
    for m in com_previsao(pacote):
        assert set(m["prev"]) == set(previsao.CENARIOS), m["nome"]
        for cenario in previsao.CENARIOS:
            x = m["cenarios"][cenario]
            conta = m["media"] + M["b"] + sum(
                k * (x[c] - mu) / sd for c, k, mu, sd in zip(pacote["colunas"], M["coef"], M["mu"], M["sd"])
            )
            assert abs(conta - m["prev"][cenario]) < 0.01, (m["nome"], cenario)


def test_cenarios_ficam_dentro_dos_limites(pacote):
    for m in (m for m in pacote["municipios"] if m["cenarios"]):
        for cenario in previsao.CENARIOS:
            for c in previsao.COLUNAS:
                minimo, maximo = m["lim"][c]
                assert minimo <= m["cenarios"][cenario][c] <= maximo, (m["nome"], cenario, c)


def test_municipio_sem_safra_valida_fica_sem_previsao():
    anos = list(range(2000, 2010))
    dataset = pd.DataFrame(
        {"codigo_ibge": 1, "ano": anos, "area_colhida_ha": 50.0, "producao_t": 100.0, "rendimento_kg_ha": 2000.0}
    )
    clima = pd.DataFrame({"codigo_ibge": 1, "ano": anos, **{c: 1.0 for c in previsao.COLUNAS}})
    por_safra = pd.DataFrame(columns=["codigo_ibge", "ano", "previsto", "real"])
    m = painel._municipio(1, "Teste", dataset, clima, None, anos, 0, None, por_safra)
    assert m["media"] is None
    assert m["anosMedia"] == []
    assert m["prev"] == {}
    json.dumps(m, allow_nan=False)
