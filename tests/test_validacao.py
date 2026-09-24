"""O protocolo de D5: treino sempre antes da validação, teste nunca visto."""
import pandas as pd

from peanutcast import validacao


def tabela():
    anos = range(2003, 2026)
    return pd.DataFrame(
        {
            "codigo_ibge": [1] * len(anos),
            "ano": anos,
            "rendimento_kg_ha": [float(a) for a in anos],
        }
    )


def test_teste_fica_fora_do_desenvolvimento():
    desenvolvimento, teste = validacao.separar_teste(tabela())
    assert set(teste["ano"]) == set(validacao.ANOS_TESTE)
    assert not set(desenvolvimento["ano"]) & set(validacao.ANOS_TESTE)


def test_treino_so_tem_anos_anteriores():
    desenvolvimento, _ = validacao.separar_teste(tabela())
    for ano, treino, val in validacao.dobras(desenvolvimento):
        assert treino["ano"].max() < ano
        assert set(val["ano"]) == {ano}


def test_walk_forward_entrega_o_treino_da_dobra():
    desenvolvimento, _ = validacao.separar_teste(tabela())
    vistos = []

    def prever(treino, val):
        vistos.append((treino["ano"].max(), val["ano"].iloc[0]))
        return [treino["rendimento_kg_ha"].iloc[-1]] * len(val)

    previsoes = validacao.walk_forward(desenvolvimento, prever)
    assert all(ultimo_treino < validado for ultimo_treino, validado in vistos)
    assert set(previsoes["ano"]) == set(validacao.ANOS_VALIDACAO)
    # Repetir o ano anterior numa série que sobe 1 por ano erra exatamente 1.
    assert validacao.metricas(previsoes)["mae"] == 1


def test_formulacao_de_desvio_devolve_kg_ha():
    """Modelo que prevê desvio zero tem que devolver a própria média recente."""
    from sklearn.dummy import DummyRegressor

    from peanutcast import atributos, modelos

    dados = pd.DataFrame(
        {
            "codigo_ibge": 1,
            "ano": range(2000, 2008),
            "area_colhida_ha": 1000,
            "rendimento_kg_ha": [1000.0, 2000, 3000, 2000, 1000, 2000, 3000, 2000],
            **{c: 1.0 for c in atributos.CLIMA},
        }
    )
    tabela = atributos.montar(dados)
    zero = lambda: DummyRegressor(strategy="constant", constant=0.0)  # noqa: E731
    previsto = modelos.como_previsor(zero, desvio=True)(tabela, tabela)
    assert list(previsto) == list(tabela["rend_medio_munic"])


def test_media_corrigida_soma_so_o_desvio_do_treino():
    """A baseline corrigida usa o desvio médio do treino, nunca o da validação."""
    from peanutcast import modelos

    treino = pd.DataFrame({"rendimento_kg_ha": [1100.0, 1300.0], "rend_medio_munic": [1000.0, 1000.0]})
    val = pd.DataFrame({"rendimento_kg_ha": [9999.0], "rend_medio_munic": [2000.0]})
    previsto = modelos.BASELINES["Média corrigida pela tendência"](treino, val)
    assert list(previsto) == [2200.0]
