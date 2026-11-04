"""API, testes de contrato: o OpenAPI gravado em docs/ e as respostas reais.

Se o contrato mudar de propósito, regrave com `python -m peanutcast.api` e
revise o diff de docs/openapi.json antes de commitar.
"""
import json

from apoio_api import ADAMANTINA, NORMAL, cabecalho

from peanutcast import api
from peanutcast.caminhos import RAIZ

GRAVADO = RAIZ / "docs" / "openapi.json"
PROTEGIDAS = {
    ("get", "/api/v1/municipios/{codigo}"),
    ("post", "/api/v1/municipios/{codigo}/simulacao"),
    ("get", "/api/v1/usuarios/{usuario}/favoritos"),
    ("put", "/api/v1/usuarios/{usuario}/favoritos/{codigo}"),
    ("delete", "/api/v1/usuarios/{usuario}/favoritos/{codigo}"),
}


def test_contrato_gravado_bate_com_o_gerado():
    assert GRAVADO.exists(), "rode python -m peanutcast.api para gravar docs/openapi.json"
    assert json.loads(GRAVADO.read_text(encoding="utf-8")) == api.app.openapi()


def test_contrato_tem_os_recursos_da_spec():
    caminhos = api.app.openapi()["paths"]
    operacoes = {(metodo, caminho) for caminho, item in caminhos.items() for metodo in item}
    assert operacoes == PROTEGIDAS | {
        ("get", "/api/v1/saude"),
        ("post", "/api/v1/auth/token"),
        ("get", "/api/v1/municipios"),
        ("get", "/api/v1/previsao-sazonal"),
    }


def test_rotas_protegidas_declaram_o_token_e_o_401():
    contrato = api.app.openapi()
    assert contrato["components"]["securitySchemes"]["OAuth2PasswordBearer"]["flows"]["password"]["tokenUrl"] == "/api/v1/auth/token"
    for metodo, caminho in PROTEGIDAS:
        operacao = contrato["paths"][caminho][metodo]
        assert operacao["security"] == [{"OAuth2PasswordBearer": []}], caminho
        assert "401" in operacao["responses"], caminho
    assert "429" in contrato["paths"]["/api/v1/auth/token"]["post"]["responses"]
    favoritos = contrato["paths"]["/api/v1/usuarios/{usuario}/favoritos"]["get"]["responses"]
    assert "403" in favoritos


def test_respostas_seguem_os_modelos_declarados(cliente):
    h = cabecalho(cliente)
    casos = [
        (api.Saude, cliente.get("/api/v1/saude")),
        (api.ListaMunicipios, cliente.get("/api/v1/municipios")),
        (api.PrevisaoSazonal, cliente.get("/api/v1/previsao-sazonal")),
        (api.Token, cliente.post("/api/v1/auth/token", data={"username": "ana", "password": "Senha#123"})),
        (api.Ficha, cliente.get(f"/api/v1/municipios/{ADAMANTINA}", headers=h)),
        (api.Simulacao, cliente.post(f"/api/v1/municipios/{ADAMANTINA}/simulacao", json=NORMAL, headers=h)),
        (api.Favoritos, cliente.put(f"/api/v1/usuarios/ana/favoritos/{ADAMANTINA}", headers=h)),
    ]
    for modelo, resposta in casos:
        assert resposta.status_code == 200, (modelo.__name__, resposta.text)
        modelo.model_validate(resposta.json(), strict=False)
        assert set(resposta.json()) == set(modelo.model_fields), modelo.__name__


def test_erros_seguem_o_formato_detail(cliente):
    for resposta in (
        cliente.get(f"/api/v1/municipios/{ADAMANTINA}"),
        cliente.get("/api/v1/municipios/1", headers=cabecalho(cliente)),
    ):
        assert isinstance(resposta.json()["detail"], str)
