# PeanutCast

**Previsão de produtividade do amendoim com Machine Learning. Alta Paulista, SP.**

Painel preditivo que estima o rendimento em kg/ha por município, cruzando o histórico
de safra do IBGE/SIDRA-PAM com dados climáticos da NASA POWER. A decisão que o produto
muda é de pré-plantio: em qual município arrendar área e quanto plantar.

Projeto Integrador de Laboratório de Big Data em Agricultura · execução de 31/08/2026 a
31/10/2026 · equipe de quatro integrantes: Lucas dos Santos Gonçalves, Luís Otávio,
Matheus Betteli e Jonah Kunihiro.

## O que este repositório guarda

Só o código do PeanutCast. A documentação do MVP, as entregas do curso e o material do
professor ficam fora do git, na pasta `mvp/` da máquina local.

Documento binário não tem diff: um `.pptx` no histórico é ruído, porque ninguém
consegue revisar o que mudou de uma versão para a outra. O material do professor, além
disso, não é nosso para redistribuir. Documento que precisa circular é compartilhado
como arquivo.

## Fontes de dados

| Fonte | O que fornece |
|---|---|
| IBGE / SIDRA-PAM | Área plantada, área colhida, produção e rendimento por município e ano |
| NASA POWER | Precipitação, temperaturas, umidade, radiação e vento |

Municípios: 24 das microrregiões de Marília, Tupã e Adamantina, entre eles Tupã,
Marília, Pompéia, Herculândia, Quintana, Garça e Adamantina. Bastos ficou de fora: o
IBGE não registra amendoim lá desde 2007.

## O que o produto faz

Três camadas:

| Camada | O que entrega |
|---|---|
| **Projetar** | Rendimento esperado em kg/ha, por município, antes do plantio |
| **Explicar** | Quais fatores climáticos pesam em cada resultado, com histórico e comparação |
| **Simular** | Cenário seco, normal ou chuvoso, e qual município aguenta melhor o ano ruim |

Duas coisas que o produto **não** faz, e que valem estar escritas aqui porque são
decisões, não limitações acidentais:

- **Não prevê o tempo.** O usuário escolhe um cenário climático e o modelo responde o
  rendimento naquele cenário. É simulação condicional.
- **Não emite intervalo de confiança estatístico.** A faixa em volta da previsão é o
  erro médio histórico do modelo, medido na validação por ordem de tempo.

## Modelo

`y` = rendimento em kg/ha. `X` = média histórica do município, calculada só com anos
anteriores, mais o clima da safra. Três modelos comparados (regressão linear, Random
Forest e XGBoost) contra dois palpites simples: a média histórica do município e a
repetição do ano anterior.

**O resultado do projeto não é o R² nem o MAE**, e sim a diferença entre o erro do
modelo e o erro do palpite da média. Essa diferença mede quanto o clima contribui, que
é a tese do PeanutCast. Se der perto de zero, a conclusão honesta é que clima municipal
agregado não prevê produtividade de amendoim, e isso também é resultado.

## Como rodar

```bash
python -m pip install -r requirements.txt
cp credenciais.exemplo.yaml credenciais.yaml   # depois troque a chave do cookie
streamlit run app.py
```

O app abre em `http://localhost:8501`. O usuário de exemplo é `lucas` com senha
`trocar123`. Na primeira execução a senha é convertida para hash e o arquivo é
regravado, então anote a senha antes se for mudar.

Para criar sua própria conta, use a aba **Criar conta** na tela de entrada. A senha
precisa de maiúscula, minúscula, número e símbolo.

`credenciais.yaml` e `dados/favoritos.json` ficam fora do Git: cada um tem os seus.

### O que já funciona

Cadastro, login, sair e a lista de municípios favoritos por usuário. É a entrega da
Semana 1. O gráfico do histórico chega na Semana 3 e a previsão na Semana 8; os dois
lugares já estão marcados na tela.

A sessão dura enquanto a aba fica aberta. Recarregar a página pede login de novo, e
isso é de propósito: está explicado em `credenciais.exemplo.yaml`.

## Estrutura

```
app.py                     tela do painel, ponto de entrada do Streamlit
peanutcast/
  auth.py                  cadastro, login e sair
  favoritos.py             municípios favoritos por usuário
  caminhos.py              onde ficam dados, modelos e credenciais
  municipios.py            lista de municípios atendidos
requirements.txt           versões travadas, iguais para os quatro
credenciais.exemplo.yaml   modelo do arquivo de login
.streamlit/config.toml     cores da marca
dados/                     baixados do IBGE e da NASA, fora do Git
modelos/                   modelos treinados, fora do Git
```
