"""Configuracao da rodada, montada a partir do ambiente."""

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .model.competencia import mes_ano

RAIZ = Path(__file__).resolve().parent.parent
PORTA_PADRAO = 9257
TIMEOUT = 20


@dataclass(frozen=True)
class Configuracao:
    porta: int
    data_rodada: str      # DD-MM-AAAA, nome da pasta da rodada
    tr_ate: str           # ultima competencia pedida para a TR
    ipcae_ate: str        # ultima competencia pedida para a IPCA-E
    debug: bool
    sem_janela: bool
    saida: Path = RAIZ / "output"

    @classmethod
    def do_ambiente(cls, env=None, agora=None):
        env = os.environ if env is None else env
        agora = agora or datetime.now()
        return cls(
            porta=int(env.get("PJECALC_PORTA") or PORTA_PADRAO),
            data_rodada=agora.strftime("%d-%m-%Y"),
            # A TR do mes corrente entra por volta do dia 8 e a IPCA-E do mes
            # anterior por volta do dia 2: pedir alem do que existe cobre os
            # dois calendarios, e o PJe-Calc entrega ate onde tem sem reclamar.
            tr_ate=env.get("PJECALC_TR_ATE") or mes_ano(agora.year, agora.month + 1),
            ipcae_ate=env.get("PJECALC_IPCAE_ATE") or mes_ano(agora.year, agora.month),
            # Com debug sai screenshot e DOM de cada etapa; sem ele, so as
            # capturas de falha, unico registro visual de uma rodada sozinha.
            debug=env.get("PJECALC_DEBUG") == "1",
            sem_janela=cls._sem_janela(env),
        )

    @staticmethod
    def _sem_janela(env) -> bool:
        """Sem display nao da para abrir janela, entao num servidor o padrao e
        rodar sem ela. Havendo sessao grafica, a janela visivel ajuda quem
        depura. PJECALC_FF_HEADLESS=0/1 decide explicitamente."""
        padrao = "0" if (env.get("DISPLAY") or env.get("WAYLAND_DISPLAY")) else "1"
        return env.get("PJECALC_FF_HEADLESS", padrao) == "1"

    @property
    def home(self) -> str:
        return f"http://localhost:{self.porta}/pjecalc/pages/principal.jsf"

    @property
    def pasta_rodada(self) -> Path:
        return self.saida / self.data_rodada

    @property
    def perfil_firefox(self) -> Path:
        """Fica na raiz de output/, fora da pasta da rodada: e reaproveitado."""
        return self.saida / "_ff_profile"

    def planilha(self, indice) -> Path:
        return self.pasta_rodada / f"indices_{indice.nome}_TRT8_{self.data_rodada}.xlsx"
