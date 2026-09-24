"""Compara as baselines e os três modelos no walk-forward da validação.

Rodar depois do integrar.py:

    python scripts/comparar.py

Imprime a tabela de comparação e grava em modelos/:
  comparacao.json     métricas e parâmetros de cada previsor, com a data
  previsoes_validacao.csv   uma linha por município-ano validado

Não toca nos anos de teste. O teste é aberto uma vez, pelo avaliar_teste.py,
depois de o modelo final estar escolhido.
"""
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

from peanutcast import atributos, caminhos, modelos, validacao  # noqa: E402

BASELINE_PRINCIPAL = "Média das 3 últimas safras"


def parametros(nome):
    fabrica = modelos.FABRICAS.get(nome.split(" (")[0])
    if fabrica is None:
        return None
    modelo = fabrica()
    passos = getattr(modelo, "steps", None)
    final = passos[-1][1] if passos else modelo
    return {k: v for k, v in final.get_params().items() if v is not None and not callable(v)}


def main():
    tabela = atributos.montar(pd.read_csv(caminhos.DATASET))
    desenvolvimento, _ = validacao.separar_teste(tabela)

    todas, linhas = [], []
    for nome, prever in modelos.PREVISORES.items():
        print(f"walk-forward: {nome}...")
        previsoes = validacao.walk_forward(desenvolvimento, prever)
        por_ano = validacao.metricas_por_ano(previsoes)
        linhas.append({"previsor": nome, **validacao.metricas(previsoes), "mae_desvio_entre_anos": por_ano.std()})
        todas.append(previsoes.assign(previsor=nome))

    resultado = pd.DataFrame(linhas).set_index("previsor")
    referencia = resultado.loc[BASELINE_PRINCIPAL, "mae"]
    resultado["ganho_sobre_baseline"] = referencia - resultado["mae"]

    print()
    print(resultado.round(2).to_string())
    melhor = resultado.drop(index=list(modelos.BASELINES)).sort_values("mae").iloc[0]
    print(
        f"\nMelhor modelo: {melhor.name}, MAE {melhor['mae']:.0f} kg/ha. "
        f"Ganho sobre a baseline: {melhor['ganho_sobre_baseline']:+.0f} kg/ha "
        f"(desvio do MAE entre anos: {melhor['mae_desvio_entre_anos']:.0f})."
    )

    caminhos.MODELOS.mkdir(parents=True, exist_ok=True)
    pd.concat(todas).to_csv(caminhos.MODELOS / "previsoes_validacao.csv", index=False)
    registro = {
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        "anos_validacao": [min(validacao.ANOS_VALIDACAO), max(validacao.ANOS_VALIDACAO)],
        "linhas_validadas": int(resultado["n"].iloc[0]),
        "atributos": atributos.ATRIBUTOS,
        "previsores": {
            nome: {**{k: float(v) for k, v in linha.items()}, "parametros": parametros(nome)}
            for nome, linha in resultado.iterrows()
        },
    }
    (caminhos.MODELOS / "comparacao.json").write_text(
        json.dumps(registro, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
