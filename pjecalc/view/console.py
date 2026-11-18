"""Saida da automacao no terminal.

Unico lugar que escreve para o operador. A rodada mensal roda sem ninguem
olhando e o journal e o que sobra depois — por isso cada linha e carimbada.
"""

import sys
from datetime import datetime

LARGURA = 62


class Console:
    def __init__(self, saida=sys.stdout, entrada=sys.stdin):
        self._saida = saida
        self._entrada = entrada

    def _linha(self, msg, tag="   "):
        print(f"  [{datetime.now().strftime('%H:%M:%S')}][{tag}] {msg}", file=self._saida)

    def info(self, msg):
        self._linha(msg)

    def ok(self, msg):
        self._linha(msg, " OK")

    def aviso(self, msg):
        self._linha(msg, "AVS")

    def erro(self, msg):
        self._linha(msg, "ERR")

    def etapa(self, msg):
        self._linha(msg, "-->")

    def debug(self, msg):
        self._linha(msg, "DBG")

    def espaco(self):
        print(file=self._saida)

    def progresso(self):
        """Um ponto por tentativa, para a espera longa nao parecer travada."""
        print(".", end="", flush=True, file=self._saida)

    def abertura(self, titulo):
        regua = "=" * LARGURA
        print(f"\n{regua}\n  {titulo}", file=self._saida)
        print(f"  {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n{regua}", file=self._saida)

    def relatorio(self, resultados, pasta):
        """Fecho da rodada. A linha 'Pasta :' e lida pelo rodada-mensal.sh."""
        regua = "=" * LARGURA
        print(f"\n{regua}\n  CONCLUIDO", file=self._saida)
        for indice, tabela, arquivo in resultados:
            ate = f"ate {tabela.mais_recente}" if tabela else "sem dados"
            print(f"  {indice.nome:<6}: {len(tabela):5d} registros"
                  f"  -> {arquivo.name}  ({ate})", file=self._saida)
        print(f"  Pasta : {pasta}\n{regua}", file=self._saida)

    def intervencao(self, msg):
        """Pede uma acao manual na janela do Firefox.

        Sem terminal — que e o caso da rodada mensal — esperar por uma tecla
        travaria a unidade do systemd para sempre: melhor falhar dizendo qual
        etapa deixou de ser automatica.
        """
        self.aviso(msg)
        if not self._entrada.isatty():
            raise RuntimeError(f"Etapa manual necessaria em execucao nao-interativa: {msg}")
        input("  >> Pressione ENTER para continuar... ")
