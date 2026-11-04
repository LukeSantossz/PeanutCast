"""API, testes de unidade: token, senha e limite de tentativas, sem HTTP."""
from datetime import timedelta

import bcrypt
import jwt
import pytest

from peanutcast import api

CHAVE = "chave-de-unidade-com-mais-de-32-bytes"


class Relogio:
    def __init__(self):
        self.agora = 1000.0

    def __call__(self):
        return self.agora


def test_limite_barra_a_sexta_tentativa_e_libera_depois_da_janela():
    relogio = Relogio()
    limite = api.Limite(maximo=5, janela=60, relogio=relogio)
    assert all(limite.permitir("1.2.3.4") is None for _ in range(5))
    espera = limite.permitir("1.2.3.4")
    assert espera == 60
    relogio.agora += 30
    assert limite.permitir("1.2.3.4") == 30
    relogio.agora += 30.5
    assert limite.permitir("1.2.3.4") is None


def test_limite_conta_cada_ip_em_separado():
    limite = api.Limite(maximo=1, janela=60, relogio=Relogio())
    assert limite.permitir("a") is None
    assert limite.permitir("b") is None
    assert limite.permitir("a") is not None


def test_token_leva_o_usuario_e_vence():
    token = api.criar_token("ana", CHAVE)
    assert api.ler_token(token, CHAVE) == "ana"
    vencido = api.criar_token("ana", CHAVE, validade=timedelta(seconds=-1))
    with pytest.raises(jwt.ExpiredSignatureError):
        api.ler_token(vencido, CHAVE)


def test_token_com_outra_chave_nao_vale():
    with pytest.raises(jwt.InvalidTokenError):
        api.ler_token(api.criar_token("ana", "outra-chave-com-mais-de-32-bytes-ok"), CHAVE)


def test_token_sem_algoritmo_nao_vale():
    sem_assinatura = jwt.encode({"sub": "ana"}, key=None, algorithm="none")
    with pytest.raises(jwt.InvalidTokenError):
        api.ler_token(sem_assinatura, CHAVE)


def test_senha_confere_so_com_hash_bcrypt():
    hash_ = bcrypt.hashpw(b"Senha#123", bcrypt.gensalt(rounds=4)).decode()
    assert api.senha_confere("Senha#123", hash_)
    assert not api.senha_confere("errada", hash_)
    # Senha ainda em texto puro no YAML (o painel nunca abriu) não serve para entrar pela API.
    assert not api.senha_confere("trocar123", "trocar123")
    assert not api.senha_confere("x", None)
