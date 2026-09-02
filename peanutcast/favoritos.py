"""Municípios favoritos de cada usuário.

Guardados num único JSON no formato {usuario: [municipios]}. Não é banco de
dados e não precisa ser: são poucos usuários e uma lista curta por usuário.
Se um dia isso crescer, o formato troca sem mexer em quem chama as funções.
"""
import json

from .caminhos import FAVORITOS


def _ler_tudo():
    """Lê o arquivo inteiro. Devolve dicionário vazio se ele não existe."""
    if not FAVORITOS.exists():
        return {}
    try:
        return json.loads(FAVORITOS.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        # Arquivo corrompido não pode derrubar o app na cara do usuário.
        # Perder a lista de favoritos é ruim; não conseguir entrar é pior.
        return {}


def _gravar_tudo(dados):
    FAVORITOS.parent.mkdir(parents=True, exist_ok=True)
    FAVORITOS.write_text(
        json.dumps(dados, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def listar(usuario):
    """Municípios favoritos do usuário, em ordem alfabética."""
    return sorted(_ler_tudo().get(usuario, []))


def adicionar(usuario, municipio):
    dados = _ler_tudo()
    lista = dados.setdefault(usuario, [])
    if municipio not in lista:
        lista.append(municipio)
        _gravar_tudo(dados)
    return sorted(lista)


def remover(usuario, municipio):
    dados = _ler_tudo()
    lista = dados.get(usuario, [])
    if municipio in lista:
        lista.remove(municipio)
        _gravar_tudo(dados)
    return sorted(lista)


def alternar(usuario, municipio):
    """Adiciona se não está na lista, remove se está.

    É o que o botão de favoritar faz: um clique só, sem o usuário precisar
    saber em que estado a lista está.
    """
    if municipio in _ler_tudo().get(usuario, []):
        return remover(usuario, municipio)
    return adicionar(usuario, municipio)
