"""Leitura paginada da tabela de resultados.

O PJe-Calc entrega o resultado da pesquisa num modal do RichFaces, 8 linhas por
pagina. Quando o modal nao aparece, a mesma leitura serve para a tabela
desenhada na propria pagina — dai as duas grades com a mesma interface.
"""

import time

from selenium.webdriver.common.by import By

from ...model.tabela import COLUNAS_PADRAO, Tabela

PAUSA_PAGINA = 1.2
MAX_PAGINAS = 200
PAGINAS_SEM_NOVIDADE = 2

ESPERA_MODAL = 15.0
INTERVALO_MODAL = 0.5

SELETOR_MODAL = 'div.rich-mpnl, div[class*="rich-mpnl"], div[class*="modalPanel"]'
SELETOR_DADOS = 'table.rich-table, table[class*="rich-table"]'

# O PJe-Calc deixa 43 divs com marca de modal no DOM, e os primeiros a ficarem
# visiveis sao a mascara escura e as bordas de redimensionar — todos sem tabela
# nenhuma dentro. Procurar "o modal visivel" entrega um deles e a extracao sai
# com zero linha, sem erro no caminho. O que identifica o modal certo e conter
# a rich-table dos dados; e dela, nao do modal, que saem cabecalho e linhas.
JS_MODAL = """
    function tabelaDeDados() {
        var todos = document.querySelectorAll(%s);
        for (var i = 0; i < todos.length; i++) {
            var el = todos[i];
            if (!el.offsetWidth || !el.offsetHeight) continue;
            var estilo = window.getComputedStyle(el);
            if (estilo.visibility === 'hidden' || estilo.display === 'none') continue;
            var tabela = el.querySelector(%s);
            if (tabela) return tabela;
        }
        return null;
    }
    function painelDeDados() {
        var tabela = tabelaDeDados();
        return tabela ? tabela.closest('div[class*="rich-mpnl"]') : null;
    }
""" % (repr(SELETOR_MODAL), repr(SELETOR_DADOS))


class Grade:
    """Interface comum: cabecalhos, linhas da pagina atual e botao de avanco."""

    def __init__(self, navegador, console):
        self._nav = navegador
        self._console = console

    def cabecalhos(self) -> list:
        raise NotImplementedError

    def linhas(self, tabela: Tabela) -> list:
        raise NotImplementedError

    def proxima_pagina(self):
        raise NotImplementedError

    def ler(self, nome) -> Tabela:
        time.sleep(PAUSA_PAGINA)
        # Dizer de onde vieram os cabecalhos, nao so quais sao: COLUNAS_PADRAO
        # e identico ao que a tela entrega, entao um log que so mostra os nomes
        # fica igual tendo lido a tela ou nao — e foi assim que uma extracao com
        # zero linha passou por normal.
        da_tela = self.cabecalhos()
        if not da_tela:
            self._console.aviso(f"  Cabecalhos ({nome}): a tela nao entregou, usando o padrao.")
        tabela = Tabela(colunas=da_tela or list(COLUNAS_PADRAO))
        self._console.info(f"  Cabecalhos ({nome}): {tabela.colunas}")

        sem_novidade = 0
        for pagina in range(1, MAX_PAGINAS + 1):
            if self._nav.tem_erro_interno:
                self._console.erro(f"Erro interno na pagina {pagina}.")
                self._nav.capturar(f"erro_pag_{nome}_{pagina:03d}", erro=True)
                break

            novos = tabela.estender(self.linhas(tabela))
            self._console.info(
                f"  Pag {pagina:3d}: +{novos:3d} novos | total: {len(tabela):5d}")

            # Paginas repetidas seguidas significam que o clique em 'proxima'
            # deixou de avancar: nao ha mais o que ler.
            sem_novidade = sem_novidade + 1 if novos == 0 else 0
            if sem_novidade >= PAGINAS_SEM_NOVIDADE:
                break

            botao = self.proxima_pagina()
            if not botao:
                self._console.ok(f"  Ultima pagina ({pagina}).")
                break
            try:
                self._nav.clicar(botao)
            except Exception as erro:
                self._console.aviso(f"  Erro ao paginar (pag {pagina}): {erro}")
                break
            time.sleep(PAUSA_PAGINA)

        self._console.ok(f"  {len(tabela)} registros lidos de {nome}.")
        return tabela


class GradeModal(Grade):
    """Modal rich:modalPanel — o caminho normal.

    Tudo e lido por JS a partir do modal visivel, nunca por XPath global: os
    modais escondidos tem a mesma marcacao e entrariam na conta, duplicando
    cabecalho e misturando linhas com a tabela do fundo da pagina.
    """

    def cabecalhos(self) -> list:
        nomes = self._nav.js(JS_MODAL + """
            var tabela = tabelaDeDados();
            if (!tabela) return null;
            var celulas = tabela.querySelectorAll('th, thead td');
            var nomes = [];
            for (var i = 0; i < celulas.length; i++) {
                var txt = (celulas[i].innerText || '').trim();
                if (txt) nomes.push(txt);
            }
            return nomes;
        """)
        return nomes or []

    def linhas(self, tabela) -> list:
        bruto = self._nav.js(JS_MODAL + """
            var tabela = tabelaDeDados();
            if (!tabela) return null;
            var corpo = tabela.querySelector('tbody');
            if (!corpo) return null;
            var linhas = [];
            var trs = corpo.querySelectorAll('tr');
            for (var i = 0; i < trs.length; i++) {
                var tds = trs[i].querySelectorAll('td');
                var valores = [];
                for (var j = 0; j < tds.length; j++) {
                    valores.push((tds[j].innerText || '').trim());
                }
                if (valores.length > 0) linhas.push(valores);
            }
            return linhas;
        """)
        if bruto is None:
            bruto = self._linhas_por_xpath()
        return [tabela.registro(v) for v in (bruto or []) if Tabela.e_linha_de_dado(v)]

    def _linhas_por_xpath(self) -> list:
        """Rede para o instante em que o AJAX esta remontando a tabela.

        Duas leituras vazias seguidas encerram o laco de paginacao achando que
        a tabela acabou — e a planilha sai truncada, com saida 0 e sem aviso.
        O filtro de competencia e que separa o dado da moldura do modal.
        """
        for xpath in (
            "//div[contains(@class,'rich-mpnl-body')]//table//tbody//tr",
            "//div[contains(@class,'rich-mpnl')]//table//tbody//tr",
        ):
            linhas = []
            for tr in self._nav.elementos(xpath):
                try:
                    linhas.append([td.text.strip() for td in tr.find_elements(By.TAG_NAME, "td")])
                except Exception:
                    continue
            if linhas:
                return linhas
        return []

    def proxima_pagina(self):
        """Pega o botao de PROXIMA (▶), nunca o de ULTIMA (▶|).

        No datascroller do RichFaces os dois sao irmaos no fim da fila:
          [|◀] [◀] [1] [2] ... [12] [▶] [▶|]
        o penultimo e o que avanca uma pagina.
        """
        return self._nav.js(JS_MODAL + """
            var painel = painelDeDados();
            if (!painel) return null;
            var botoes = Array.prototype.slice.call(painel.querySelectorAll(
                'td[class*="rich-datascr-button"], td[class*="rich-datascr-btn"]'
            )).filter(function (b) { return b.offsetParent !== null; });
            var botao = botoes[botoes.length - 2];
            if (!botao) return null;
            if ((botao.className || '').toLowerCase().indexOf('dis') !== -1) return null;
            return botao.querySelector('a') || botao;
        """)


class GradePagina(Grade):
    """Tabela desenhada na propria pagina — rede para layout inesperado."""

    def cabecalhos(self) -> list:
        for xpath in ("//table[.//tbody//tr]//th", "//th[@scope='col']",
                      "//table[.//tbody//tr]//thead//td"):
            nomes = [el.text.strip() for el in self._nav.elementos(xpath) if el.text.strip()]
            if nomes:
                return nomes
        return []

    def linhas(self, tabela) -> list:
        for xpath in (
            "//table[contains(@class,'rich-table')]//tbody//tr",
            "//table[@role='grid']//tbody//tr",
            "(//table[count(.//tbody//tr)>1])[1]//tbody//tr",
        ):
            linhas = []
            for tr in self._nav.elementos(xpath):
                try:
                    valores = [td.text.strip() for td in tr.find_elements(By.TAG_NAME, "td")]
                except Exception:
                    continue
                if any(any(c.isdigit() for c in v) for v in valores if v):
                    linhas.append(tabela.registro(valores))
            if linhas:
                return linhas
        return []

    def proxima_pagina(self):
        for xpath in (
            "//td[contains(@class,'rich-datascr-button') and not(contains(@class,'dis'))][last()]//a",
            "//a[contains(@class,'ui-paginator-next') and not(contains(@class,'disabled'))]",
            "//a[normalize-space(text())='>' or normalize-space(text())='»']",
        ):
            for botao in self._nav.clicaveis(xpath):
                classes = (botao.get_attribute("class") or "").lower()
                if "disabled" not in classes and "inativ" not in classes:
                    return botao
        return None


def grade_visivel(navegador, console, espera=ESPERA_MODAL) -> Grade:
    """Espera o modal aparecer; so desiste para a tabela da pagina no fim.

    Com 719 competencias o modal demora para montar, e decidir no primeiro
    olhar entregaria a tabela errada — de onde saem dezenas de linhas em vez
    de centenas, sem erro nenhum no caminho.
    """
    limite = time.monotonic() + espera
    while True:
        if navegador.js(JS_MODAL + "return tabelaDeDados() !== null;"):
            console.ok("  Modal detectado: extracao focada nele.")
            return GradeModal(navegador, console)
        if time.monotonic() >= limite:
            console.aviso("  Modal nao apareceu: extracao da tabela da pagina.")
            return GradePagina(navegador, console)
        time.sleep(INTERVALO_MODAL)
