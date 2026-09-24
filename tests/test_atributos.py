"""A regra de ouro de atributos.py: nenhuma coluna olha para o futuro."""
import pandas as pd
import pytest

from peanutcast import atributos


def painel(rendimentos, area=1000, codigo=1):
    """Um município com um rendimento por ano, a partir de 2000."""
    return pd.DataFrame(
        {
            "codigo_ibge": codigo,
            "ano": range(2000, 2000 + len(rendimentos)),
            "area_colhida_ha": area,
            "rendimento_kg_ha": rendimentos,
        }
    )


def test_media_usa_so_as_safras_anteriores():
    tabela = atributos.montar(painel([1000, 2000, 3000, 4000, 5000]))
    linha_2003 = tabela.set_index("ano").loc[2003]
    assert linha_2003["rend_medio_munic"] == 2000       # média de 2000 a 2002
    assert linha_2003["rend_safra_anterior"] == 3000


def test_mudar_o_futuro_nao_muda_o_passado():
    original = atributos.montar(painel([1000, 2000, 3000, 4000, 5000, 6000]))
    alterado = atributos.montar(painel([1000, 2000, 3000, 4000, 5000, 99999]))
    colunas = ["rend_medio_munic", "rend_safra_anterior", "safras_anteriores"]
    pd.testing.assert_frame_equal(original[colunas], alterado[colunas])


def test_media_fica_na_janela():
    rendimentos = [100] * 10 + [5000] * atributos.JANELA_SAFRAS + [0]
    tabela = atributos.montar(painel(rendimentos)).set_index("ano")
    assert tabela.loc[2000 + len(rendimentos) - 1, "rend_medio_munic"] == 5000


def test_historico_curto_sai():
    tabela = atributos.montar(painel([1000] * 5))
    assert tabela["ano"].min() == 2000 + atributos.SAFRAS_ANTERIORES_MIN
    assert (tabela["safras_anteriores"] >= atributos.SAFRAS_ANTERIORES_MIN).all()


def test_area_pequena_sai_e_nao_entra_na_media():
    dados = painel([1000, 1000, 1000, 9000, 1000])
    dados.loc[3, "area_colhida_ha"] = atributos.AREA_MINIMA_HA - 1
    tabela = atributos.montar(dados).set_index("ano")
    assert 2003 not in tabela.index
    assert tabela.loc[2004, "rend_medio_munic"] == 1000


def test_municipios_nao_se_misturam():
    dados = pd.concat([painel([1000] * 4, codigo=1), painel([5000] * 4, codigo=2)])
    tabela = atributos.montar(dados).set_index("codigo_ibge")
    assert tabela.loc[1, "rend_medio_munic"] == 1000
    assert tabela.loc[2, "rend_medio_munic"] == 5000


def test_separar_devolve_os_atributos_de_d1():
    dados = painel([1000] * 5)
    for coluna in atributos.CLIMA:
        dados[coluna] = 1.0
    x, y = atributos.separar(atributos.montar(dados))
    assert list(x.columns) == atributos.ATRIBUTOS
    assert y.name == atributos.ALVO
