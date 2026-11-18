"""Ponto de entrada: python -m pjecalc"""

import sys

from .config import Configuracao
from .controller.extracao import ControladorExtracao
from .view.console import Console


def main() -> int:
    return ControladorExtracao(Configuracao.do_ambiente(), Console()).executar()


if __name__ == "__main__":
    sys.exit(main())
