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

`y` = rendimento em kg/ha. `X` = média das três safras anteriores do município mais o
clima da safra. Três modelos comparados (regressão linear, Random Forest e XGBoost)
contra dois palpites simples: essa mesma média e a repetição da safra anterior.

A média é das três últimas safras, e não de todas, porque o rendimento da região sobe
cerca de 80 kg/ha por ano. A média de todas fica para trás da tendência e daria ao
modelo um ganho que é tecnologia, não clima. Validação por ordem de tempo: cada ano de
2012 a 2022 é previsto por um modelo treinado só com os anos anteriores, e 2023 a 2025
ficam guardados como teste final. Detalhes e números em [`docs/dados.md`](docs/dados.md).

**O resultado do projeto não é o R² nem o MAE**, e sim a diferença entre o erro do
modelo e o erro do palpite da média. Essa diferença mede quanto o clima contribui, que
é a tese do PeanutCast. Se der perto de zero, a conclusão honesta é que clima municipal
agregado não prevê produtividade de amendoim, e isso também é resultado.

## Como rodar

```bash
python -m pip install -r requirements.txt
cp credenciais.exemplo.yaml credenciais.yaml   # depois troque a chave do cookie
python scripts/coletar.py                      # baixa IBGE, NASA POWER e o contorno dos municípios
python scripts/integrar.py                     # monta dados/tratados/dataset.csv
python scripts/analisar_dados.py               # opcional: os números das decisões
streamlit run app.py
```

A coleta baixa só o que ainda não existe em `dados/brutos/`; `--forcar` baixa tudo de
novo. Cada arquivo bruto ganha um `.origem.json` ao lado, com a fonte e a data do
download. A integração não acessa a internet e pode rodar quantas vezes precisar.

O app abre em `http://localhost:8501`. O usuário de exemplo é `lucas` com senha
`trocar123`. Na primeira execução a senha é convertida para hash e o arquivo é
regravado, então anote a senha antes se for mudar.

Para criar sua própria conta, use a aba **Criar conta** na tela de entrada. A senha
precisa de maiúscula, minúscula, número e símbolo.

`credenciais.yaml` e `dados/favoritos.json` ficam fora do Git: cada um tem os seus.

### O que já funciona

Cadastro, login, sair e a lista de municípios favoritos por usuário, da Semana 1.

Coleta e integração, das Semanas 2 a 4: 24 municípios, safras de 2000 a 2025, 518
linhas com rendimento publicado. O clima de cada safra é o de setembro do ano anterior
a março do ano da colheita, que é a janela da safra das águas.

Comparação entre modelos, das Semanas 6 e 7: `python scripts/comparar.py` roda as três
baselines e os modelos no walk-forward, em cerca de 40 segundos, e grava o resultado em
`modelos/comparacao.json`. Na validação, o melhor modelo com clima (regressão linear robusta,
clima de dezembro a fevereiro) ficou 4 kg/ha à frente da baseline mais forte sem clima,
dentro do ruído.

Avaliação final: `python scripts/avaliar_teste.py --abrir-teste`, com as regras no topo
do arquivo, registradas antes de o teste ser aberto em 24/09. No teste de 2023 a 2025 o
modelo com clima errou 842 kg/ha contra 908 da régua, e quase todo o ganho veio de 2024,
o ano da quebra.

Tabela modelável e protocolo de validação, da Semana 5: `peanutcast/atributos.py` monta
o X e o y sem olhar para o futuro, e `peanutcast/validacao.py` separa treino, validação e
teste. Os testes rodam com `python -m pytest`.

O painel tem três abas, adiantadas da Semana 8:

- **Município**: histórico de rendimento, clima de dezembro a fevereiro de cada safra e a
  previsão da próxima safra, com seletor de cenário (seco, normal, chuvoso), controles
  para ajustar o clima e a faixa de erro.
- **Comparar municípios**: mapa regional e tabela com os 24 municípios sob o mesmo
  cenário, com os favoritos marcados.
- **Modelos**: a tabela da validação e o peso de cada variável de clima na previsão.

A previsão usa o modelo principal da avaliação final, treinado com todas as safras. A
faixa de erro (± 647 kg/ha) é o erro médio ano a ano de 2012 a 2025.

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
  fontes.py                acesso às APIs do SIDRA, de malhas do IBGE e da NASA POWER
  dados.py                 leitura, pelo app, do que os scripts gravaram
  previsao.py              modelo do painel, cenários, faixa de erro e pesos do clima
  atributos.py             tabela modelável: o X e o y, sem olhar para o futuro
  validacao.py             walk-forward, teste reservado e métricas
  modelos.py               as duas baselines e os três modelos, nas duas formulações
scripts/
  coletar.py               baixa os dados brutos para dados/brutos/
  integrar.py              junta produção e clima em dados/tratados/dataset.csv
  analisar_dados.py        os números por trás das decisões de atributos e validação
  comparar.py              baselines e modelos no walk-forward, grava em modelos/
  avaliar_teste.py         avaliação final no teste de 2023 a 2025, com as regras registradas
tests/                     python -m pytest
docs/dados.md              fontes, regras de tratamento e dicionário de colunas
requirements.txt           versões travadas, iguais para os quatro
credenciais.exemplo.yaml   modelo do arquivo de login
.streamlit/config.toml     cores da marca
dados/                     baixados do IBGE e da NASA, fora do Git
modelos/                   modelos treinados, fora do Git
```
