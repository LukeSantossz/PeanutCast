"""Cenários e previsão do painel."""
import numpy as np
import pandas as pd
import pytest
from sklearn.dummy import DummyRegressor

from peanutcast import previsao


def clima_de_nove_anos():
    return pd.DataFrame(
        {
            "chuva_critica_mm": [300, 350, 400, 500, 550, 600, 700, 750, 800],
            "temp_max_critica_c": [33, 33, 32, 31, 31, 31, 30, 30, 29],
            "radiacao_critica_mj_m2": [23, 23, 22, 22, 22, 21, 21, 20, 20],
            "dias_calor_critica": [20, 15, 10, 5, 4, 3, 1, 0, 0],
        }
    )


def test_cenarios_vem_dos_tercos_da_chuva():
    cenarios = previsao.cenarios(clima_de_nove_anos())
    assert list(cenarios.index) == previsao.CENARIOS
    assert cenarios.loc["Seco", "chuva_critica_mm"] == 350
    assert cenarios.loc["Normal", "chuva_critica_mm"] == 550
    assert cenarios.loc["Chuvoso", "chuva_critica_mm"] == 750
    # O seco carrega o calor que os anos secos tiveram, não um calor inventado.
    assert cenarios.loc["Seco", "dias_calor_critica"] == 15


def test_limites_sao_o_minimo_e_o_maximo_observados():
    limites = previsao.limites(clima_de_nove_anos())
    assert limites.loc["min", "chuva_critica_mm"] == 300
    assert limites.loc["max", "dias_calor_critica"] == 20


def test_previsao_e_a_media_mais_o_desvio_do_modelo():
    modelo = DummyRegressor(strategy="constant", constant=150.0).fit(
        clima_de_nove_anos()[previsao.COLUNAS], [0] * 9
    )
    clima = clima_de_nove_anos().iloc[0]
    assert previsao.prever(modelo, 3000.0, clima) == 3150.0


def tabela_sintetica(ultimo_rendimento=None):
    """Dois municípios de 2003 a 2014, já no formato de atributos.montar()."""
    gerador = np.random.default_rng(7)
    linhas = []
    for codigo in (1, 2):
        for ano in range(2003, 2015):
            clima = {
                "chuva_critica_mm": gerador.uniform(300, 800),
                "temp_max_critica_c": gerador.uniform(29, 34),
                "radiacao_critica_mj_m2": gerador.uniform(20, 24),
                "dias_calor_critica": int(gerador.integers(0, 30)),
            }
            media = 2000 + 80 * (ano - 2003)
            linhas.append(
                {"codigo_ibge": codigo, "ano": ano, "rend_medio_munic": media,
                 "rendimento_kg_ha": media + 0.5 * (clima["chuva_critica_mm"] - 550)
                 - 20 * clima["dias_calor_critica"] + gerador.normal(0, 100), **clima}
            )
    tabela = pd.DataFrame(linhas)
    if ultimo_rendimento is not None:
        tabela.loc[tabela["ano"] == 2014, "rendimento_kg_ha"] = ultimo_rendimento
    return tabela


def test_decomposicao_soma_a_previsao():
    tabela = tabela_sintetica()
    modelo = previsao.treinar(tabela)
    clima = tabela.iloc[5]
    partes = previsao.decompor(modelo, 3000.0, clima)
    total = partes["media"] + partes["tendencia"] + sum(partes["clima"].values())
    assert total == pytest.approx(previsao.prever(modelo, 3000.0, clima))


def test_parametros_refazem_a_conta_do_modelo():
    # É a conta que o navegador faz enquanto o usuário arrasta um controle.
    # Se o modelo do painel deixar de ser linear, este teste avisa.
    tabela = tabela_sintetica()
    modelo = previsao.treinar(tabela)
    p = previsao.parametros(modelo)
    for _, linha in tabela.iterrows():
        x = linha[previsao.COLUNAS].to_numpy(dtype=float)
        conta = p["intercepto"] + np.sum(np.array(p["coef"]) * (x - p["media"]) / p["desvio"])
        assert conta + 3000.0 == pytest.approx(previsao.prever(modelo, 3000.0, linha))


def test_previsto_por_safra_nao_olha_o_futuro():
    original = previsao.previsto_por_safra(tabela_sintetica())
    alterado = previsao.previsto_por_safra(tabela_sintetica(ultimo_rendimento=99999))
    antes = original["ano"] < 2014
    pd.testing.assert_frame_equal(original[antes], alterado[antes])
    assert set(original["ano"]) == {2012, 2013, 2014}


def test_erro_medio_e_a_media_do_erro_por_safra():
    tabela = tabela_sintetica()
    por_safra = previsao.previsto_por_safra(tabela)
    esperado = (por_safra["real"] - por_safra["previsto"]).abs().mean()
    assert previsao.erro_medio(tabela) == pytest.approx(esperado)
