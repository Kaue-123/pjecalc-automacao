"""Os indices de correcao monetaria que a automacao extrai."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Indice:
    """Um indice da tela de Correcao Monetaria (indices-gerais.jsf).

    Os ids JSF foram conferidos no DOM da versao 2.16.0 e sao inconsistentes
    entre as abas: a TR carrega 'Indice' no meio do id e a IPCA-E nao.
    """

    nome: str          # identifica o arquivo e a aba da planilha
    aba: str           # texto exato da aba na tela, sensivel a caixa
    a_partir: str      # primeira competencia da serie
    ate: str           # ultima competencia pedida
    id_ate: str
    id_a_partir: str
    id_pesquisar: str


def catalogo(config) -> list:
    """Monta os indices com as datas-limite calculadas para esta rodada."""
    return [
        Indice(
            nome="TR",
            aba="TR",
            a_partir="01/1967",
            ate=config.tr_ate,
            id_ate="formulario:mesAnoConsultaIndiceTRInputDate",
            id_a_partir="formulario:aPartirDeIndiceTRInputDate",
            id_pesquisar="formulario:cmdVisualizarIndiceTR",
        ),
        Indice(
            nome="IPCAE",
            aba="IPCA-E",
            a_partir="01/1992",
            ate=config.ipcae_ate,
            id_ate="formulario:mesAnoConsultaIPCAEInputDate",
            id_a_partir="formulario:aPartirDeIPCAEInputDate",
            id_pesquisar="formulario:cmdVisualizarIPCAE",
        ),
    ]
