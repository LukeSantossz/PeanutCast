"""Leitura do dataset integrado para o painel.

O app não baixa nem trata nada: lê o que scripts/integrar.py gravou. Se o
arquivo não existe, devolve None e a tela explica o que rodar, em vez de
quebrar com um FileNotFoundError.
"""
import pandas as pd
import streamlit as st

from .caminhos import DATASET


@st.cache_data
def _ler(modificado_em):
    # O horário de modificação entra só para compor a chave do cache: rodar o
    # integrar.py de novo muda o horário e o app relê sem precisar reiniciar.
    # Sem sublinhado no nome de propósito: o st.cache_data ignora parâmetros
    # que começam com "_" na hora de montar a chave.
    return pd.read_csv(DATASET)


def carregar_dataset():
    if not DATASET.exists():
        return None
    return _ler(DATASET.stat().st_mtime)


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
