"""Apoio dos testes da API: pacote falso, credenciais de teste e login."""
import bcrypt
import yaml

SENHA = "Senha#123"
ADAMANTINA, ARCO_IRIS = 3500105, 3503356
NORMAL = {"chuva_critica_mm": 500.0, "temp_max_critica_c": 32.0, "radiacao_critica_mj_m2": 20.0, "dias_calor_critica": 5.0}

FALSO = {
    "versao": "falso-1",
    "anos": [2023, 2024],
    "proxima": 2027,
    "erro": 600.0,
    "colunas": list(NORMAL),
    "modelo": {"nome": "teste", "mu": [500, 32, 20, 5], "sd": [100, 1, 2, 5], "coef": [100, -50, 10, -20], "b": 50},
    "boletim": {
        "cenario": "Chuvoso", "safra": 2027, "janela": "dez/2026 a fev/2027", "emissao": "set/2026",
        "municipios": {str(ADAMANTINA): {"cen": "Chuvoso", "prob": 0.45}},
    },
    "municipios": [
        {
            "codigo": ADAMANTINA, "nome": "Adamantina", "media": 3000.0, "anosMedia": [2023, 2024],
            "hist": [{"r": 2900, "ac": 1000, "p": 2900}, None],
            "cenarios": {
                "Seco": {**NORMAL, "chuva_critica_mm": 400.0},
                "Normal": NORMAL,
                "Chuvoso": {**NORMAL, "chuva_critica_mm": 600.0},
            },
            "lim": {c: [v - 100, v + 100] for c, v in NORMAL.items()},
            "prev": {"Seco": 2950.0, "Normal": 3050.0, "Chuvoso": 3150.0},
        },
        {
            "codigo": ARCO_IRIS, "nome": "Arco-Íris", "media": None, "anosMedia": [],
            "hist": [None, None], "cenarios": None, "lim": None, "prev": {},
        },
    ],
}


def escrever_credenciais(caminho):
    hash_ = bcrypt.hashpw(SENHA.encode(), bcrypt.gensalt(rounds=4)).decode()
    caminho.write_text(yaml.safe_dump({
        "cookie": {"name": "c", "key": "chave-de-teste-com-mais-de-32-bytes", "expiry_days": 0},
        "credentials": {"usernames": {
            "ana": {"email": "ana@x.com", "first_name": "Ana", "last_name": "A", "password": hash_},
            "bruno": {"email": "bruno@x.com", "first_name": "Bruno", "last_name": "B", "password": hash_},
        }},
    }), encoding="utf-8")


def entrar(cliente, usuario="ana", senha=SENHA):
    return cliente.post("/api/v1/auth/token", data={"username": usuario, "password": senha})


def cabecalho(cliente, usuario="ana"):
    return {"Authorization": f"Bearer {entrar(cliente, usuario).json()['access_token']}"}
