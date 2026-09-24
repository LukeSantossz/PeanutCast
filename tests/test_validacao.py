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
