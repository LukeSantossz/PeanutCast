"""API, testes de integração: rotas, segurança e favoritos pelo HTTP.

Os testes de segurança usam um pacote falso e rodam sempre. Os que conferem os
números contra o painel leem dados/ e são pulados sem ela.
"""
import json
from datetime import timedelta

import pytest
from apoio_api import ADAMANTINA, ARCO_IRIS, FALSO, NORMAL, SENHA, cabecalho, entrar
from fastapi.testclient import TestClient

from peanutcast import api, favoritos, painel

# --- Rotas públicas -------------------------------------------------------

def test_saude(cliente):
    r = cliente.get("/api/v1/saude")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "versao": "falso-1"}


def test_municipios_publico_com_os_tres_cenarios(cliente):
    r = cliente.get("/api/v1/municipios")
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["safra"] == 2027 and corpo["erro_kg_ha"] == 600.0
    ada, arco = corpo["municipios"]
    assert ada == {"codigo": ADAMANTINA, "nome": "Adamantina", "media_recente": 3000.0,
                   "previsao": {"Seco": 2950.0, "Normal": 3050.0, "Chuvoso": 3150.0}}
    assert arco["previsao"] is None and arco["media_recente"] is None


def test_previsao_sazonal(cliente):
    r = cliente.get("/api/v1/previsao-sazonal")
    assert r.status_code == 200
    assert r.json()["cenario"] == "Chuvoso"
    assert r.json()["municipios"][str(ADAMANTINA)] == {"cenario": "Chuvoso", "probabilidade": 0.45}


def test_previsao_sazonal_fora_da_epoca_e_404(cliente):
    api.app.dependency_overrides[api.obter_pacote] = lambda: dict(FALSO, boletim=None)
    assert cliente.get("/api/v1/previsao-sazonal").status_code == 404


def test_sem_dados_a_api_responde_503(ambiente, monkeypatch):
    monkeypatch.setattr(painel, "pronto", lambda: False)
    r = TestClient(api.app).get("/api/v1/municipios")
    assert r.status_code == 503


# --- Autenticação ---------------------------------------------------------

def test_login_devolve_token_bearer(cliente):
    r = entrar(cliente)
    assert r.status_code == 200
    assert r.json()["token_type"] == "bearer"
    assert r.json()["expira_em"] == 1800
    assert api.ler_token(r.json()["access_token"], "chave-de-teste-com-mais-de-32-bytes") == "ana"


@pytest.mark.parametrize("usuario,senha", [("ana", "errada"), ("ninguem", SENHA)])
def test_login_errado_e_401_com_a_mesma_mensagem(cliente, usuario, senha):
    r = entrar(cliente, usuario, senha)
    assert r.status_code == 401
    assert r.json()["detail"] == "Usuário ou senha incorretos."


def test_chave_do_ambiente_tem_prioridade(cliente, monkeypatch):
    monkeypatch.setenv("PEANUTCAST_API_CHAVE", "chave-do-ambiente-com-mais-de-32-bytes")
    token = entrar(cliente).json()["access_token"]
    assert api.ler_token(token, "chave-do-ambiente-com-mais-de-32-bytes") == "ana"


def test_rota_protegida_sem_token_e_401(cliente):
    r = cliente.get(f"/api/v1/municipios/{ADAMANTINA}")
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("token", [
    api.criar_token("ana", "chave-de-teste-com-mais-de-32-bytes", validade=timedelta(seconds=-1)),
    api.criar_token("ana", "chave-errada-com-mais-de-32-bytes-ok"),
    "nao-e-um-jwt",
])
def test_token_vencido_adulterado_ou_invalido_e_401(cliente, token):
    r = cliente.get(f"/api/v1/municipios/{ADAMANTINA}", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_token_de_usuario_apagado_e_401(cliente):
    token = api.criar_token("fantasma", "chave-de-teste-com-mais-de-32-bytes")
    r = cliente.get(f"/api/v1/municipios/{ADAMANTINA}", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_sexta_tentativa_de_login_no_minuto_e_429(cliente):
    for _ in range(5):
        assert entrar(cliente, senha="errada").status_code == 401
    r = entrar(cliente)
    assert r.status_code == 429
    assert int(r.headers["retry-after"]) > 0


# --- Ficha e simulação ----------------------------------------------------

def test_ficha_com_decomposicao_que_soma_a_previsao(cliente):
    r = cliente.get(f"/api/v1/municipios/{ADAMANTINA}", params={"cenario": "Chuvoso"}, headers=cabecalho(cliente))
    assert r.status_code == 200
    f = r.json()
    assert f["cenario"] == "Chuvoso" and f["safra"] == 2027
    assert f["previsao"] == pytest.approx(3150.0)
    assert f["faixa"] == pytest.approx([2550.0, 3750.0])
    d = f["decomposicao"]
    assert d["media_recente"] + d["tendencia"] + sum(d["clima"].values()) == pytest.approx(f["previsao"])
    # Cada contribuição é medida contra o clima médio do treino (o mu do modelo).
    assert d["referencia"] == dict(zip(FALSO["colunas"], map(float, FALSO["modelo"]["mu"])))
    assert d["clima"]["chuva_critica_mm"] == pytest.approx(100 * (600 - 500) / 100)
    assert f["cptec"] == {"cenario": "Chuvoso", "probabilidade": 0.45}
    assert f["historico"] == [{"ano": 2023, "rendimento_kg_ha": 2900, "area_colhida_ha": 1000, "producao_t": 2900}]


def test_ficha_cenario_invalido_e_422(cliente):
    r = cliente.get(f"/api/v1/municipios/{ADAMANTINA}", params={"cenario": "Diluvio"}, headers=cabecalho(cliente))
    assert r.status_code == 422


@pytest.mark.parametrize("codigo", [9999999, ARCO_IRIS])
def test_ficha_de_municipio_desconhecido_ou_sem_dados_e_404(cliente, codigo):
    assert cliente.get(f"/api/v1/municipios/{codigo}", headers=cabecalho(cliente)).status_code == 404


def test_simulacao_avisa_extrapolacao(cliente):
    corpo = {**NORMAL, "chuva_critica_mm": 900.0}
    r = cliente.post(f"/api/v1/municipios/{ADAMANTINA}/simulacao", json=corpo, headers=cabecalho(cliente))
    assert r.status_code == 200
    s = r.json()
    assert s["previsao"] == pytest.approx(3050.0 + 400.0)
    assert s["extrapolacao"] == ["chuva_critica_mm"]


def test_simulacao_dentro_do_historico_nao_avisa(cliente):
    r = cliente.post(f"/api/v1/municipios/{ADAMANTINA}/simulacao", json=NORMAL, headers=cabecalho(cliente))
    assert r.json()["previsao"] == pytest.approx(3050.0)
    assert r.json()["extrapolacao"] == []


@pytest.mark.parametrize("campo,valor", [("chuva_critica_mm", -1), ("temp_max_critica_c", 80), ("dias_calor_critica", 200)])
def test_simulacao_com_clima_fisicamente_impossivel_e_422(cliente, campo, valor):
    r = cliente.post(f"/api/v1/municipios/{ADAMANTINA}/simulacao", json={**NORMAL, campo: valor}, headers=cabecalho(cliente))
    assert r.status_code == 422


@pytest.mark.parametrize("valor", ["NaN", "Infinity", "-Infinity"])
def test_simulacao_com_numero_nao_finito_e_422_e_nao_500(cliente, valor):
    # O json do Python aceita NaN e Infinity; o erro 422 precisa sair em JSON válido.
    corpo = json.dumps({**NORMAL, "chuva_critica_mm": "X"}).replace('"X"', valor)
    h = {**cabecalho(cliente), "Content-Type": "application/json"}
    r = cliente.post(f"/api/v1/municipios/{ADAMANTINA}/simulacao", content=corpo, headers=h)
    assert r.status_code == 422
    assert r.json()["detail"][0]["loc"] == ["body", "chuva_critica_mm"]


def test_simulacao_sem_campo_e_422(cliente):
    corpo = dict(NORMAL)
    corpo.pop("dias_calor_critica")
    r = cliente.post(f"/api/v1/municipios/{ADAMANTINA}/simulacao", json=corpo, headers=cabecalho(cliente))
    assert r.status_code == 422


# --- Favoritos ------------------------------------------------------------

def test_favoritos_guardar_repetir_e_tirar(cliente, ambiente):
    h = cabecalho(cliente)
    url = f"/api/v1/usuarios/ana/favoritos/{ADAMANTINA}"
    assert cliente.put(url, headers=h).status_code == 200
    r = cliente.put(url, headers=h)
    assert r.json() == {"usuario": "ana", "municipios": [{"codigo": ADAMANTINA, "nome": "Adamantina"}]}
    # O mesmo arquivo que o painel lê, pelo nome do município.
    assert favoritos.listar("ana") == ["Adamantina"]
    assert cliente.get("/api/v1/usuarios/ana/favoritos", headers=h).json()["municipios"][0]["codigo"] == ADAMANTINA
    assert cliente.delete(url, headers=h).json()["municipios"] == []
    assert cliente.delete(url, headers=h).status_code == 200
    assert favoritos.listar("ana") == []


def test_favoritos_de_outro_usuario_e_403(cliente):
    h = cabecalho(cliente, "bruno")
    assert cliente.get("/api/v1/usuarios/ana/favoritos", headers=h).status_code == 403
    assert cliente.put(f"/api/v1/usuarios/ana/favoritos/{ADAMANTINA}", headers=h).status_code == 403
    assert favoritos.listar("ana") == []


def test_favorito_de_municipio_desconhecido_e_404(cliente):
    assert cliente.put("/api/v1/usuarios/ana/favoritos/123", headers=cabecalho(cliente)).status_code == 404


# --- Cabeçalhos e CORS ----------------------------------------------------

def test_cabecalhos_de_seguranca(cliente):
    publico = cliente.get("/api/v1/saude")
    assert publico.headers["x-content-type-options"] == "nosniff"
    assert publico.headers["x-frame-options"] == "DENY"
    assert publico.headers["referrer-policy"] == "no-referrer"
    protegido = cliente.get("/api/v1/usuarios/ana/favoritos", headers=cabecalho(cliente))
    assert protegido.headers["cache-control"] == "no-store"
    assert entrar(cliente).headers["cache-control"] == "no-store"


def test_cors_libera_so_a_origem_do_painel(cliente):
    preflight = {"Access-Control-Request-Method": "GET", "Access-Control-Request-Headers": "Authorization"}
    ok = cliente.options("/api/v1/municipios", headers={"Origin": "http://localhost:8501", **preflight})
    assert ok.headers["access-control-allow-origin"] == "http://localhost:8501"
    outra = cliente.options("/api/v1/municipios", headers={"Origin": "http://malicioso.example", **preflight})
    assert outra.status_code == 400
    assert "access-control-allow-origin" not in outra.headers


# --- Com os dados reais ---------------------------------------------------

@pytest.fixture
def real(ambiente):
    if not painel.pronto():
        pytest.skip("sem dados/tratados: rode scripts/integrar.py")
    return TestClient(api.app), painel._pacote(painel.dados.versao())


def test_municipios_batem_com_o_painel(real):
    cliente, pacote = real
    corpo = cliente.get("/api/v1/municipios").json()
    assert len(corpo["municipios"]) == 24
    for item, m in zip(corpo["municipios"], pacote["municipios"]):
        assert item["codigo"] == m["codigo"]
        assert (item["previsao"] or {}) == m["prev"]


def test_simulacao_com_o_clima_normal_da_a_previsao_normal(real):
    cliente, pacote = real
    m = next(x for x in pacote["municipios"] if x["prev"])
    r = cliente.post(f"/api/v1/municipios/{m['codigo']}/simulacao", json=m["cenarios"]["Normal"], headers=cabecalho(cliente))
    assert r.status_code == 200
    assert r.json()["previsao"] == pytest.approx(m["prev"]["Normal"], abs=0.01)
    d = r.json()["decomposicao"]
    assert d["media_recente"] + d["tendencia"] + sum(d["clima"].values()) == pytest.approx(r.json()["previsao"])
    assert list(d["referencia"]) == pacote["colunas"]
    assert list(d["referencia"].values()) == pytest.approx(pacote["modelo"]["mu"])
