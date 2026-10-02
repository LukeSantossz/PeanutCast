"""Regras de senha: as da biblioteca, explicadas em português."""
import pytest

from peanutcast.auth import _Validador


@pytest.mark.parametrize(
    "senha, esperado",
    [
        ("Abcdefg1!", True),
        ("abcdefg1!", False),      # sem maiúscula
        ("Abcdefgh!", False),      # sem número
        ("Abcdefg12", False),      # sem símbolo
        ("Ab1!", False),           # curta
        ("Abcdéfg1!", False),      # acento
        ("Abc defg1!", False),     # espaço
    ],
)
def test_regra_e_a_da_biblioteca(senha, esperado):
    assert _Validador().validate_password(senha) is esperado


def test_mensagem_lista_so_o_que_falta():
    assert _Validador().diagnose_password("abcdefg1!") == "A senha precisa ter uma letra maiúscula."


def test_acento_e_explicado():
    # A biblioteca recusa acento sem dizer por quê; a mensagem dela saía vazia.
    assert _Validador().diagnose_password("Abcdéfg1!") == "A senha não pode ter acento nem espaço."
