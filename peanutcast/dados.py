"""Leitura, pelo painel, do que os scripts gravaram em disco.

O app não baixa nem trata nada: lê o que scripts/integrar.py e
scripts/comparar.py gravaram. Se um arquivo não existe, a função devolve None
e a tela explica o que rodar, em vez de quebrar com um FileNotFoundError.

O horário de modificação do arquivo entra na chave do cache: rodar um script
de novo muda o horário e o app relê sem precisar reiniciar. O parâmetro não
começa com "_" de propósito, porque o st.cache_data ignora esses na chave.
"""
import json

import pandas as pd
import streamlit as st

from . import atributos, previsao
from .caminhos import CLIMA_SAFRAS, DATASET, MALHAS, MODELOS

COMPARACAO = MODELOS / "comparacao.json"
TESTE = MODELOS / "teste.json"


def _modificado_em(arquivo):
    return arquivo.stat().st_mtime if arquivo.exists() else None


@st.cache_data
def _ler_csv(caminho, modificado_em):
    return pd.read_csv(caminho)


@st.cache_data
def _ler_json(caminho, modificado_em):
    return json.loads(caminho.read_text(encoding="utf-8"))


def carregar_dataset():
    if not DATASET.exists():
        return None
    return _ler_csv(DATASET, _modificado_em(DATASET))


def carregar_clima():
    """Clima de todas as safras, uma linha por município e ano."""
    if not CLIMA_SAFRAS.exists():
        return None
    return _ler_csv(CLIMA_SAFRAS, _modificado_em(CLIMA_SAFRAS))


def carregar_malhas():
    if not MALHAS.exists():
        return None
    return _ler_json(MALHAS, _modificado_em(MALHAS))


def carregar_comparacao():
    """Resultado do último scripts/comparar.py, ou None se ele nunca rodou."""
    if not COMPARACAO.exists():
        return None
    return _ler_json(COMPARACAO, _modificado_em(COMPARACAO))


def carregar_teste():
    """Resultado do scripts/avaliar_teste.py, ou None se o teste não foi aberto."""
    if not TESTE.exists():
        return None
    return _ler_json(TESTE, _modificado_em(TESTE))


@st.cache_resource
def _modelo(modificado_em):
    tabela = atributos.montar(pd.read_csv(DATASET))
    por_safra = previsao.previsto_por_safra(tabela)
    return previsao.treinar(tabela), previsao.erro_medio(tabela, por_safra), por_safra


def modelo_do_painel():
    """(modelo, erro médio da validação). Treina uma vez por versão do dataset."""
    modelo, erro, _ = _modelo(_modificado_em(DATASET))
    return modelo, erro


def previsto_por_safra():
    """O que o modelo do painel teria previsto em cada safra desde 2012, sem vê-la."""
    return _modelo(_modificado_em(DATASET))[2]


def versao():
    """Muda quando qualquer arquivo lido pelo painel muda. O navegador usa
    para saber se precisa recalcular o que guardou da última vez."""
    return "-".join(str(_modificado_em(a)) for a in (DATASET, CLIMA_SAFRAS, MALHAS, COMPARACAO, TESTE))


def historico(dataset, municipio):
    """Safras do município, uma linha por ano do recorte.

    Ano sem rendimento publicado vira linha com valores vazios, não some. É o
    que faz o gráfico mostrar um buraco em vez de ligar 2008 a 2010 como se
    2009 tivesse existido.
    """
    anos = range(dataset["ano"].min(), dataset["ano"].max() + 1)
    return (
        dataset[dataset["municipio"] == municipio]
        .set_index("ano")
        .reindex(anos)
        .rename_axis("ano")
        .reset_index()
    )
