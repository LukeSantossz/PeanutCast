"""Cenários e previsão do painel."""
import pandas as pd
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
