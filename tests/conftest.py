"""Fixtures da API: credenciais e favoritos num diretório temporário."""
import pytest
from apoio_api import FALSO, escrever_credenciais
from fastapi.testclient import TestClient

from peanutcast import api, favoritos


@pytest.fixture
def ambiente(tmp_path, monkeypatch):
    escrever_credenciais(tmp_path / "credenciais.yaml")
    monkeypatch.setattr(api, "CREDENCIAIS", tmp_path / "credenciais.yaml")
    monkeypatch.setattr(favoritos, "FAVORITOS", tmp_path / "favoritos.json")
    monkeypatch.delenv("PEANUTCAST_API_CHAVE", raising=False)
    api.limite_login.limpar()
    yield tmp_path
    api.app.dependency_overrides.clear()


@pytest.fixture
def cliente(ambiente):
    api.app.dependency_overrides[api.obter_pacote] = lambda: FALSO
    return TestClient(api.app)
