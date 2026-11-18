"""Orquestracao da rodada: atualizar as tabelas, extrair os indices, gravar."""

import time

from ..infra.navegador import JanelaFechada, Navegador
from ..infra.paginas.atualizacao import TelaAtualizacao
from ..infra.paginas.correcao_monetaria import TelaCorrecaoMonetaria
from ..infra.paginas.menu import Menu
from ..infra.planilha import RepositorioPlanilha
from ..model.indice import catalogo
from ..model.tabela import Tabela

TITULO = "PJe-Calc — Extracao Indices TRT 8 (TR e IPCA-E)"
PAUSA_ENTRE_ETAPAS = 2.0

SUCESSO = 0
FALHA = 1

AVISO_JANELA = (
    "O script abriu uma janela DEDICADA do Firefox (perfil isolado).",
    "Toda acao manual pedida deve ser feita NESSA janela.",
    "NAO feche essa janela ate o script terminar.",
)


class ControladorExtracao:
    def __init__(self, config, console):
        self._config = config
        self._console = console
        self._planilhas = RepositorioPlanilha(console)

    def executar(self) -> int:
        self._console.abertura(TITULO)
        self._config.pasta_rodada.mkdir(parents=True, exist_ok=True)
        navegador = None
        try:
            navegador = Navegador.abrir(self._config, self._console)
            return self._rodar(navegador)
        except KeyboardInterrupt:
            self._console.aviso("Interrompido.")
            return FALHA
        except JanelaFechada as erro:
            self._console.erro(str(erro))
            self._console.erro("Os dados extraidos ate aqui foram perdidos.")
            self._console.erro("Rode de novo e NAO feche a janela que o script abre.")
            return FALHA
        except Exception as erro:
            self._console.erro(f"Erro inesperado: {erro}")
            if navegador and navegador.viva:
                navegador.capturar("erro_fatal", erro=True)
            import traceback
            traceback.print_exc()
            return FALHA
        finally:
            if navegador:
                navegador.fechar()
                self._console.info("Navegador encerrado.")

    def _rodar(self, navegador) -> int:
        menu = Menu(navegador, self._console)
        navegador.ir_para_home()

        self._console.espaco()
        for linha in AVISO_JANELA:
            self._console.aviso(linha)
        self._console.espaco()

        if navegador.tem_erro_interno:
            self._console.erro("O PJe-Calc respondeu com erro na home. Ele esta no ar?")
            return FALHA
        self._console.ok("PJe-Calc acessivel.")

        indices = catalogo(self._config)
        total_etapas = len(indices) + 2

        self._console.etapa(f"ETAPA 1/{total_etapas}  Atualizacao de tabelas do TRT 8")
        TelaAtualizacao(navegador, menu, self._console).executar()
        time.sleep(PAUSA_ENTRE_ETAPAS)

        tela = TelaCorrecaoMonetaria(navegador, menu, self._console)
        extraidas = {}
        for numero, indice in enumerate(indices, start=2):
            self._console.espaco()
            self._console.etapa(
                f"ETAPA {numero}/{total_etapas}  Extracao {indice.nome} "
                f"(aba '{indice.aba}', de {indice.a_partir} ate {indice.ate})")
            extraidas[indice] = self._extrair(tela, indice)

        self._console.espaco()
        self._console.etapa(f"ETAPA {total_etapas}/{total_etapas}  Salvando arquivos")
        resultados = [
            (indice, tabela, self._config.planilha(indice))
            for indice, tabela in extraidas.items()
        ]
        gravadas = [
            self._planilhas.salvar(tabela, indice.nome, arquivo)
            for indice, tabela, arquivo in resultados
        ]

        self._console.relatorio(resultados, self._config.pasta_rodada)
        # Planilha faltando tem de derrubar a rodada: quem chama so olha o
        # codigo de saida, e um sucesso falso aqui vira mes sem indice.
        return SUCESSO if all(gravadas) else FALHA

    def _extrair(self, tela, indice) -> Tabela:
        """Um indice que falha nao leva o outro junto."""
        try:
            return tela.extrair(indice)
        except JanelaFechada:
            raise
        except Exception as erro:
            self._console.erro(f"Falha ao extrair {indice.nome}: {erro}")
            return Tabela()
