"""Avaliação final: abre o teste de 2023 a 2025 com os modelos já escolhidos.

    python scripts/avaliar_teste.py --abrir-teste

Regras registradas em 24/09, antes de o teste ser aberto pela primeira vez.
Este arquivo entrou no git antes de qualquer número do teste existir, e o
histórico do git é a prova disso. Mudar as regras depois de rodar o script
transforma o teste em validação e o número deixa de valer.

  1. Modelo principal: regressão linear robusta (Huber) com o clima da fase
     crítica, a melhor na validação. A Ridge com o mesmo clima é reportada
     ao lado, como verificação. Se ela se sair melhor, isso é reportado, mas
     a principal não muda.
  2. Régua: média corrigida pela tendência com a mediana, a baseline mais
     forte na validação. O ganho do clima é medido contra ela.
  3. Os modelos são treinados com as safras até 2022 e preveem 2023, 2024 e
     2025 de uma vez. Nenhum parâmetro, variável ou regra muda depois.
  4. O resultado é reportado qualquer que seja, inclusive ganho negativo.

Grava o resultado em modelos/teste.json.
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

from peanutcast import atributos, caminhos, modelos, validacao  # noqa: E402

PRINCIPAL = "Regressão Linear (Huber)"
VERIFICACAO = "Regressão Linear (Ridge)"
REGUA = "Média corrigida pela tendência (mediana)"


def prever_teste(prever, desenvolvimento, teste):
    return pd.DataFrame(
        {
            "ano": teste["ano"].to_numpy(),
            "codigo_ibge": teste["codigo_ibge"].to_numpy(),
            "real": teste[atributos.ALVO].to_numpy(),
            "previsto": prever(desenvolvimento, teste),
        }
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--abrir-teste",
        action="store_true",
        help="confirma que o modelo está congelado e o teste pode ser aberto",
    )
    if not parser.parse_args().abrir_teste:
        parser.error("o teste só abre com --abrir-teste; leia as regras no topo do arquivo")

    tabela = atributos.montar(pd.read_csv(caminhos.DATASET))
    desenvolvimento, teste = validacao.separar_teste(tabela)

    previsores = {
        **modelos.BASELINES,
        f"{PRINCIPAL} (principal)": modelos.como_previsor(
            modelos.AJUSTADOS[PRINCIPAL], desvio=True, colunas=atributos.CLIMA_CRITICO
        ),
        f"{VERIFICACAO} (verificação)": modelos.como_previsor(
            modelos.AJUSTADOS[VERIFICACAO], desvio=True, colunas=atributos.CLIMA_CRITICO
        ),
    }

    linhas, por_ano = [], {}
    for nome, prever in previsores.items():
        previsoes = prever_teste(prever, desenvolvimento, teste)
        linhas.append({"previsor": nome, **validacao.metricas(previsoes)})
        por_ano[nome] = validacao.metricas_por_ano(previsoes)

    resultado = pd.DataFrame(linhas).set_index("previsor")
    resultado["ganho_sobre_regua"] = resultado.loc[REGUA, "mae"] - resultado["mae"]
    mae_por_ano = pd.DataFrame(por_ano).T

    print(f"Teste: {len(teste)} linhas, safras {sorted(teste['ano'].unique())}")
    print(f"Treino: {len(desenvolvimento)} linhas, até {desenvolvimento['ano'].max()}\n")
    print(resultado.round(2).to_string())
    print("\nMAE por safra do teste:")
    print(mae_por_ano.round(0).to_string())

    caminhos.MODELOS.mkdir(parents=True, exist_ok=True)
    (caminhos.MODELOS / "teste.json").write_text(
        json.dumps(
            {
                "gerado_em": datetime.now().isoformat(timespec="seconds"),
                "regua": REGUA,
                "principal": PRINCIPAL,
                "verificacao": VERIFICACAO,
                "metricas": resultado.to_dict(orient="index"),
                "mae_por_ano": {k: {str(a): v for a, v in d.items()} for k, d in mae_por_ano.to_dict(orient="index").items()},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
