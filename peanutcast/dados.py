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


@st.cache_resource
def _modelo(modificado_em):
    tabela = atributos.montar(pd.read_csv(DATASET))
    return previsao.treinar(tabela), previsao.erro_medio(tabela)


def modelo_do_painel():
    """(modelo, erro médio da validação). Treina uma vez por versão do dataset."""
    return _modelo(_modificado_em(DATASET))


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
