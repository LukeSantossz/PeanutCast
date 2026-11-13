"""API REST do PeanutCast, em FastAPI.

Serve o mesmo pacote do painel (painel._pacote): municípios, previsão nos três
cenários, ficha com a decomposição, simulação com o clima que o cliente mandar,
a previsão sazonal do CPTEC e os favoritos de cada usuário. Não tem modelo nem
regra própria: a conta é a mesma de previsao.decompor, com os parâmetros que o
painel já manda para o navegador.

Rodar:     uvicorn peanutcast.api:app --port 8000
Swagger:   http://localhost:8000/docs   (ReDoc em /redoc, contrato em /openapi.json)
Contrato:  python -m peanutcast.api     (regrava docs/openapi.json)

Segurança:
- login pelo fluxo OAuth2 password, que devolve um JWT HS256 de 30 minutos. A
  senha é conferida com bcrypt contra o hash do credenciais.yaml, o mesmo do
  painel, e só vale para quem já tem hash: senha em texto puro no YAML (o painel
  ainda não abriu) não entra;
- a chave do JWT vem de PEANUTCAST_API_CHAVE, ou da chave do cookie do YAML,
  que fica fora do Git;
- 5 tentativas de login por minuto por IP, contadas em memória (429);
- favoritos só do próprio usuário (403);
- CORS só para o painel, e cabeçalhos contra sniffing, iframe e cache.
"""
import json
import math
import os
import threading
import time
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta
from functools import cache
from typing import Annotated, Literal

import bcrypt
import jwt
import yaml
from fastapi import Depends, FastAPI, HTTPException, Path, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, ConfigDict, Field

from . import dados, favoritos, painel
from .caminhos import CREDENCIAIS, RAIZ
from .municipios import MUNICIPIOS

V1 = "/api/v1"
URL_TOKEN = f"{V1}/auth/token"
VALIDADE = timedelta(minutes=30)
ALGORITMO = "HS256"
ORIGENS = ["http://localhost:8501"]
CONTRATO = RAIZ / "docs" / "openapi.json"

Cenario = Literal["Seco", "Normal", "Chuvoso"]
CODIGOS = {nome: codigo for codigo, nome in MUNICIPIOS.items()}


# --- Modelos --------------------------------------------------------------

class Erro(BaseModel):
    detail: str


class Saude(BaseModel):
    status: str = Field(examples=["ok"])
    versao: str = Field(description="Muda quando algum arquivo de dados muda.")


class Token(BaseModel):
    access_token: str = Field(description="JWT para o cabeçalho Authorization: Bearer.")
    token_type: str = Field(examples=["bearer"])
    expira_em: int = Field(description="Validade do token, em segundos.", examples=[1800])


class Clima(BaseModel):
    """O clima de dezembro a fevereiro, a fase crítica do amendoim."""

    model_config = ConfigDict(json_schema_extra={"examples": [{
        "chuva_critica_mm": 520.0, "temp_max_critica_c": 31.8,
        "radiacao_critica_mj_m2": 21.5, "dias_calor_critica": 4.0,
    }]})

    chuva_critica_mm: float = Field(ge=0, le=3000, description="Chuva de dez a fev, em mm.")
    temp_max_critica_c: float = Field(ge=0, le=50, description="Máxima média de dez a fev, em °C.")
    radiacao_critica_mj_m2: float = Field(ge=0, le=40, description="Radiação média, em MJ/m²/dia.")
    dias_calor_critica: float = Field(ge=0, le=91, description="Dias acima de 35 °C de dez a fev.")


class MunicipioResumo(BaseModel):
    codigo: int = Field(description="Código IBGE de 7 dígitos.", examples=[3500105])
    nome: str = Field(examples=["Adamantina"])
    media_recente: float | None = Field(description="Média das safras recentes, em kg/ha.")
    previsao: dict[Cenario, float] | None = Field(description="Rendimento previsto em kg/ha, por cenário; null sem dados.")


class ListaMunicipios(BaseModel):
    safra: int = Field(description="Safra prevista.", examples=[2027])
    erro_kg_ha: float = Field(description="Erro médio do modelo, a meia largura da faixa.")
    municipios: list[MunicipioResumo]


class Tercil(BaseModel):
    cenario: Cenario
    probabilidade: float | None = Field(description="Probabilidade do tercil; null quando é o normal.")


class PrevisaoSazonal(BaseModel):
    cenario: Cenario | None = Field(description="Tercil mais frequente na região.")
    safra: int
    janela: str = Field(examples=["dez/2026 a fev/2027"])
    emissao: str = Field(description="Mês da emissão do CPTEC usada.", examples=["set/2026"])
    municipios: dict[str, Tercil] = Field(description="Tercil por código IBGE.")


class Decomposicao(BaseModel):
    """Partes que somam a previsão, em kg/ha.

    É a explicação individual da previsão: com o modelo linear do painel, cada
    contribuição de clima é o valor SHAP exato da variável, com as safras do
    treino como fundo, e média recente + tendência é o valor base.
    """

    media_recente: float
    tendencia: float = Field(description="Quanto a safra fica acima da média recente com o clima médio.")
    clima: dict[str, float] = Field(description="Contribuição de cada variável de clima (valor SHAP, kg/ha).")
    referencia: dict[str, float] = Field(
        description="Clima médio das safras do treino: cada contribuição mede a distância do clima usado até ele.",
        examples=[{"chuva_critica_mm": 525.0, "temp_max_critica_c": 30.9,
                   "radiacao_critica_mj_m2": 22.0, "dias_calor_critica": 8.6}],
    )


class Safra(BaseModel):
    ano: int
    rendimento_kg_ha: float | None
    area_colhida_ha: float | None
    producao_t: float | None


class Ficha(BaseModel):
    codigo: int
    nome: str
    safra: int
    cenario: Cenario
    clima: Clima
    previsao: float = Field(description="Rendimento previsto, em kg/ha.")
    faixa: list[float] = Field(description="Previsão menos e mais o erro médio, em kg/ha.")
    decomposicao: Decomposicao
    cptec: Tercil | None = Field(description="Tercil do CPTEC no município, quando há previsão sazonal.")
    historico: list[Safra]


class Simulacao(BaseModel):
    codigo: int
    nome: str
    safra: int
    clima: Clima
    previsao: float
    faixa: list[float]
    decomposicao: Decomposicao
    extrapolacao: list[str] = Field(description="Variáveis fora do mínimo e do máximo já vistos no município.")
    aviso: str | None


class MunicipioRef(BaseModel):
    codigo: int
    nome: str


class Favoritos(BaseModel):
    usuario: str
    municipios: list[MunicipioRef]


# --- Segurança ------------------------------------------------------------

class Limite:
    """Janela deslizante de tentativas por chave (o IP), em memória.

    Basta para um processo só. Com mais de um processo, cada um conta o seu.
    """

    def __init__(self, maximo=5, janela=60, relogio=time.monotonic):
        self.maximo, self.janela, self.relogio = maximo, janela, relogio
        self._tentativas = defaultdict(deque)
        self._trava = threading.Lock()

    def permitir(self, chave):
        """None se a tentativa pode seguir; se não, os segundos até liberar."""
        with self._trava:
            agora = self.relogio()
            fila = self._tentativas[chave]
            while fila and agora - fila[0] >= self.janela:
                fila.popleft()
            if len(fila) >= self.maximo:
                return max(1, math.ceil(self.janela - (agora - fila[0])))
            fila.append(agora)
            return None

    def limpar(self):
        with self._trava:
            self._tentativas.clear()


limite_login = Limite()


def criar_token(usuario, chave, validade=VALIDADE):
    agora = datetime.now(UTC)
    return jwt.encode({"sub": usuario, "iat": agora, "exp": agora + validade}, chave, algorithm=ALGORITMO)


def ler_token(token, chave):
    """O usuário do token. Levanta jwt.InvalidTokenError se ele não vale."""
    return jwt.decode(token, chave, algorithms=[ALGORITMO], options={"require": ["exp", "sub"]})["sub"]


@cache
def _hash_qualquer():
    return bcrypt.hashpw(b"ninguem", bcrypt.gensalt()).decode()


def senha_confere(senha, hash_):
    """Só aceita hash bcrypt. Sem hash, compara com um qualquer para gastar o
    mesmo tempo e não revelar quais usuários existem."""
    valido = isinstance(hash_, str) and hash_.startswith("$2")
    try:
        bateu = bcrypt.checkpw(senha.encode(), (hash_ if valido else _hash_qualquer()).encode())
    except ValueError:
        return False
    return valido and bateu


def _configuracao():
    if not CREDENCIAIS.exists():
        raise HTTPException(503, f"{CREDENCIAIS.name} não encontrado: copie credenciais.exemplo.yaml.")
    return yaml.safe_load(CREDENCIAIS.read_text(encoding="utf-8")) or {}


def _usuarios():
    return (_configuracao().get("credentials") or {}).get("usernames") or {}


def _chave():
    return os.environ.get("PEANUTCAST_API_CHAVE") or _configuracao()["cookie"]["key"]


def _nao_autenticado(detalhe):
    return HTTPException(401, detalhe, headers={"WWW-Authenticate": "Bearer"})


_esquema = OAuth2PasswordBearer(tokenUrl=URL_TOKEN, auto_error=False)


def usuario_atual(token: Annotated[str | None, Depends(_esquema)]) -> str:
    if not token:
        raise _nao_autenticado("Faça login: falta o token.")
    try:
        usuario = ler_token(token, _chave())
    except jwt.InvalidTokenError:
        raise _nao_autenticado("Token inválido ou vencido.") from None
    if usuario not in _usuarios():
        raise _nao_autenticado("Token inválido ou vencido.")
    return usuario


Usuario = Annotated[str, Depends(usuario_atual)]


# --- Dados ----------------------------------------------------------------

def obter_pacote():
    if not painel.pronto():
        raise HTTPException(503, "Sem dados: rode scripts/coletar.py e scripts/integrar.py.")
    return painel._pacote(dados.versao())


Pacote = Annotated[dict, Depends(obter_pacote)]
Codigo = Annotated[int, Path(description="Código IBGE do município.", examples=[3500105])]


def _municipio(pacote, codigo, previsivel=False):
    m = next((x for x in pacote["municipios"] if x["codigo"] == codigo), None)
    if m is None:
        raise HTTPException(404, f"Município {codigo} não é atendido pelo PeanutCast.")
    if previsivel and not m["prev"]:
        raise HTTPException(404, f"Sem dados suficientes para prever {m['nome']}.")
    return m


def _decompor(pacote, media, clima):
    """A conta de previsao.decompor com os parâmetros do pacote."""
    p = pacote["modelo"]
    partes = {
        c: coef * (clima[c] - mu) / sd
        for c, coef, mu, sd in zip(pacote["colunas"], p["coef"], p["mu"], p["sd"])
    }
    referencia = dict(zip(pacote["colunas"], map(float, p["mu"])))
    return Decomposicao(media_recente=media, tendencia=p["b"], clima=partes, referencia=referencia)


def _faixa(pacote, previsao):
    return [max(0.0, previsao - pacote["erro"]), previsao + pacote["erro"]]


def _tercil(leitura):
    return None if leitura is None else Tercil(cenario=leitura["cen"], probabilidade=leitura["prob"])


# --- Aplicação ------------------------------------------------------------

app = FastAPI(
    title="PeanutCast API",
    version="1.0.0",
    description=(
        "Previsão do rendimento de amendoim nos 24 municípios da Alta Paulista, "
        "com o mesmo modelo do painel.\n\n"
        "Para as rotas com cadeado, clique em **Authorize** e entre com o usuário "
        "e a senha do painel. O token vale 30 minutos."
    ),
    openapi_tags=[
        {"name": "Sistema", "description": "Estado da API."},
        {"name": "Autenticação", "description": "Login e token JWT."},
        {"name": "Municípios", "description": "Previsão, ficha e simulação."},
        {"name": "Clima", "description": "Previsão sazonal do CPTEC."},
        {"name": "Favoritos", "description": "Municípios guardados por usuário."},
    ],
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ORIGENS,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def cabecalhos_de_seguranca(request: Request, chamar):
    resposta = await chamar(request)
    resposta.headers["X-Content-Type-Options"] = "nosniff"
    resposta.headers["X-Frame-Options"] = "DENY"
    resposta.headers["Referrer-Policy"] = "no-referrer"
    if "authorization" in request.headers or request.url.path == URL_TOKEN:
        resposta.headers["Cache-Control"] = "no-store"
    return resposta


def _finito(valor):
    """NaN e Infinity viram texto: o 422 repete a entrada, e JSON não tem esses números."""
    if isinstance(valor, float) and not math.isfinite(valor):
        return str(valor)
    if isinstance(valor, dict):
        return {k: _finito(v) for k, v in valor.items()}
    if isinstance(valor, list):
        return [_finito(v) for v in valor]
    return valor


@app.exception_handler(RequestValidationError)
async def entrada_invalida(request: Request, erro: RequestValidationError):
    return JSONResponse(status_code=422, content={"detail": _finito(jsonable_encoder(erro.errors()))})


def _erro(codigo, descricao, exemplo):
    return {codigo: {"model": Erro, "description": descricao,
                     "content": {"application/json": {"example": {"detail": exemplo}}}}}


E401 = _erro(401, "Sem token, ou token vencido ou inválido.", "Token inválido ou vencido.")
E403 = _erro(403, "Favoritos de outro usuário.", "Só o próprio usuário vê e muda os seus favoritos.")
E404 = _erro(404, "Município desconhecido ou sem dados.", "Município 1234567 não é atendido pelo PeanutCast.")
E503 = _erro(503, "Dados ainda não coletados.", "Sem dados: rode scripts/coletar.py e scripts/integrar.py.")


@app.get(f"{V1}/saude", response_model=Saude, tags=["Sistema"], responses=E503, summary="Estado da API")
def saude(pacote: Pacote):
    return Saude(status="ok", versao=pacote["versao"])


@app.post(
    URL_TOKEN, response_model=Token, tags=["Autenticação"], summary="Login",
    responses=_erro(401, "Usuário ou senha incorretos.", "Usuário ou senha incorretos.")
    | _erro(429, "Mais de 5 tentativas no minuto.", "Muitas tentativas de login. Tente de novo em instantes."),
)
def entrar(request: Request, formulario: Annotated[OAuth2PasswordRequestForm, Depends()]):
    """Troca usuário e senha do painel por um token JWT de 30 minutos."""
    espera = limite_login.permitir(request.client.host if request.client else "desconhecido")
    if espera is not None:
        raise HTTPException(429, "Muitas tentativas de login. Tente de novo em instantes.",
                            headers={"Retry-After": str(espera)})
    cadastro = _usuarios().get(formulario.username) or {}
    if not senha_confere(formulario.password, cadastro.get("password")):
        raise _nao_autenticado("Usuário ou senha incorretos.")
    token = criar_token(formulario.username, _chave())
    return Token(access_token=token, token_type="bearer", expira_em=int(VALIDADE.total_seconds()))


@app.get(f"{V1}/municipios", response_model=ListaMunicipios, tags=["Municípios"], responses=E503,
         summary="Municípios e previsão nos três cenários")
def listar_municipios(pacote: Pacote):
    return ListaMunicipios(
        safra=pacote["proxima"],
        erro_kg_ha=pacote["erro"],
        municipios=[
            MunicipioResumo(codigo=m["codigo"], nome=m["nome"], media_recente=m["media"], previsao=m["prev"] or None)
            for m in pacote["municipios"]
        ],
    )


@app.get(f"{V1}/municipios/{{codigo}}", response_model=Ficha, tags=["Municípios"],
         responses=E401 | E404 | E503, summary="Ficha do município")
def ficha(codigo: Codigo, pacote: Pacote, _usuario: Usuario,
          cenario: Annotated[Cenario, Query(description="Cenário de clima.")] = "Normal"):
    """Previsão no cenário, faixa de erro, decomposição, tercil do CPTEC e histórico."""
    m = _municipio(pacote, codigo, previsivel=True)
    clima = m["cenarios"][cenario]
    previsao = m["prev"][cenario]
    boletim = pacote.get("boletim") or {}
    return Ficha(
        codigo=codigo, nome=m["nome"], safra=pacote["proxima"], cenario=cenario, clima=Clima(**clima),
        previsao=previsao, faixa=_faixa(pacote, previsao), decomposicao=_decompor(pacote, m["media"], clima),
        cptec=_tercil(boletim.get("municipios", {}).get(str(codigo))),
        historico=[
            Safra(ano=ano, rendimento_kg_ha=h["r"], area_colhida_ha=h["ac"], producao_t=h["p"])
            for ano, h in zip(pacote["anos"], m["hist"]) if h is not None
        ],
    )


@app.post(f"{V1}/municipios/{{codigo}}/simulacao", response_model=Simulacao, tags=["Municípios"],
          responses=E401 | E404 | E503, summary="Simular com outro clima")
def simular(codigo: Codigo, clima: Clima, pacote: Pacote, _usuario: Usuario):
    """Previsão com o clima do corpo. Avisa as variáveis fora do que o município já viveu."""
    m = _municipio(pacote, codigo, previsivel=True)
    valores = clima.model_dump()
    partes = _decompor(pacote, m["media"], valores)
    previsao = partes.media_recente + partes.tendencia + sum(partes.clima.values())
    lim = m["lim"] or {}
    fora = [c for c in pacote["colunas"] if c in lim and not lim[c][0] <= valores[c] <= lim[c][1]]
    return Simulacao(
        codigo=codigo, nome=m["nome"], safra=pacote["proxima"], clima=clima, previsao=previsao,
        faixa=_faixa(pacote, previsao), decomposicao=partes, extrapolacao=fora,
        aviso=(f"Clima fora do histórico de {m['nome']}: a previsão extrapola o que o modelo viu." if fora else None),
    )


@app.get(f"{V1}/previsao-sazonal", response_model=PrevisaoSazonal, tags=["Clima"],
         responses=_erro(404, "Sem previsão do CPTEC para a safra.", "Sem previsão sazonal do CPTEC para a próxima safra.") | E503,
         summary="Previsão sazonal do CPTEC")
def previsao_sazonal(pacote: Pacote):
    """Tercil de chuva de dez a fev, pela emissão do CPTEC de setembro ou outubro."""
    b = pacote.get("boletim")
    if not b:
        raise HTTPException(404, "Sem previsão sazonal do CPTEC para a próxima safra.")
    return PrevisaoSazonal(
        cenario=b["cenario"], safra=b["safra"], janela=b["janela"], emissao=b["emissao"],
        municipios={k: _tercil(v) for k, v in b["municipios"].items()},
    )


def _dono(usuario, atual):
    if usuario != atual:
        raise HTTPException(403, "Só o próprio usuário vê e muda os seus favoritos.")


def _favoritos(usuario, nomes):
    return Favoritos(usuario=usuario, municipios=[
        MunicipioRef(codigo=CODIGOS[n], nome=n) for n in nomes if n in CODIGOS
    ])


def _nome(codigo):
    if codigo not in MUNICIPIOS:
        raise HTTPException(404, f"Município {codigo} não é atendido pelo PeanutCast.")
    return MUNICIPIOS[codigo]


@app.get(f"{V1}/usuarios/{{usuario}}/favoritos", response_model=Favoritos, tags=["Favoritos"],
         responses=E401 | E403, summary="Listar favoritos")
def listar_favoritos(usuario: str, atual: Usuario):
    _dono(usuario, atual)
    return _favoritos(usuario, favoritos.listar(usuario))


@app.put(f"{V1}/usuarios/{{usuario}}/favoritos/{{codigo}}", response_model=Favoritos, tags=["Favoritos"],
         responses=E401 | E403 | E404, summary="Guardar favorito")
def guardar_favorito(usuario: str, codigo: Codigo, atual: Usuario):
    """Idempotente: guardar de novo não duplica."""
    _dono(usuario, atual)
    return _favoritos(usuario, favoritos.adicionar(usuario, _nome(codigo)))


@app.delete(f"{V1}/usuarios/{{usuario}}/favoritos/{{codigo}}", response_model=Favoritos, tags=["Favoritos"],
            responses=E401 | E403 | E404, summary="Tirar favorito")
def tirar_favorito(usuario: str, codigo: Codigo, atual: Usuario):
    """Idempotente: tirar o que não está guardado não dá erro."""
    _dono(usuario, atual)
    return _favoritos(usuario, favoritos.remover(usuario, _nome(codigo)))


if __name__ == "__main__":
    CONTRATO.parent.mkdir(parents=True, exist_ok=True)
    CONTRATO.write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"contrato gravado em {CONTRATO}")
