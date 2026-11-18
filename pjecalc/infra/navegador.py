"""Adaptador do Selenium: tudo que fala com o Firefox passa por aqui."""

import sys
import time

from selenium import webdriver
from selenium.webdriver.common.by import By

PAUSA_CARGA = 3.0

LARGURA_JANELA = 1366
ALTURA_JANELA = 900

SINAIS_DE_ERRO = ("erro interno", "ocorreu um erro inesperado")


class JanelaFechada(RuntimeError):
    """A janela que o Selenium controla sumiu; nada mais funciona sem ela."""


class Navegador:
    """Primitivas sobre o driver, mais a captura de evidencia da rodada.

    O PJe-Calc 2.16 e uma SPA JSF que guarda o estado inteiro (tabela
    carregada, aba, filtros) no servidor, amarrado ao jsessionid. Por isso
    quase tudo aqui clica em vez de navegar por URL.
    """

    def __init__(self, driver, config, console):
        self._driver = driver
        self._config = config
        self._console = console

    @classmethod
    def abrir(cls, config, console):
        # Import local: o webdriver_manager so faz falta para abrir o navegador
        # de verdade, e carregá-lo no topo faria todo teste do pacote depender
        # dele. Ver dependencia-externa-no-topo-do-modulo-contamina-o-dominio.
        from selenium.webdriver.firefox.options import Options
        from selenium.webdriver.firefox.service import Service
        from webdriver_manager.firefox import GeckoDriverManager

        console.etapa("Iniciando Firefox...")
        options = Options()
        if sys.platform.startswith("win"):
            options.binary_location = r"C:\Program Files\Mozilla Firefox\firefox.exe"

        # Perfil dedicado mais -no-remote forcam uma instancia isolada: sem
        # isso o Firefox gruda numa janela ja aberta, encerra com status 0 e o
        # geckodriver perde a sessao.
        config.perfil_firefox.mkdir(parents=True, exist_ok=True)
        options.add_argument("-no-remote")
        options.add_argument("-profile")
        options.add_argument(str(config.perfil_firefox))
        if config.sem_janela:
            options.add_argument("-headless")   # desenha normalmente: as capturas saem

        driver = webdriver.Firefox(
            service=Service(GeckoDriverManager().install()), options=options)
        driver.set_window_size(LARGURA_JANELA, ALTURA_JANELA)
        console.ok("Driver pronto.")
        return cls(driver, config, console)

    def fechar(self):
        try:
            self._driver.quit()
        except Exception:
            pass

    # ── navegacao ────────────────────────────────────────────────

    def ir_para(self, url):
        self._driver.get(url)
        time.sleep(PAUSA_CARGA)

    def ir_para_home(self):
        self.ir_para(self._config.home)

    # ── primitivas de DOM ────────────────────────────────────────

    def js(self, script, *args):
        return self._driver.execute_script(script, *args)

    def elementos(self, xpath):
        try:
            return self._driver.find_elements(By.XPATH, xpath)
        except Exception:
            return []

    def visiveis(self, xpath):
        for el in self.elementos(xpath):
            try:
                if el.is_displayed():
                    yield el
            except Exception:
                continue   # elemento trocado pelo AJAX no meio da varredura

    def clicaveis(self, xpath):
        """Visiveis e habilitados."""
        for el in self.visiveis(xpath):
            try:
                if el.is_enabled():
                    yield el
            except Exception:
                continue

    def por_tag(self, tag):
        try:
            return self._driver.find_elements(By.TAG_NAME, tag)
        except Exception:
            return []

    def por_id(self, id_jsf):
        """getElementById aceita o ':' dos ids JSF sem escape; o XPath nao."""
        if not id_jsf:
            return None
        try:
            return self.js("return document.getElementById(arguments[0]);", id_jsf)
        except Exception:
            return None

    def clicar(self, elemento) -> bool:
        """Clica e diz se conseguiu; nunca estoura.

        Quem chama esta sempre no meio de uma lista de candidatos, e um
        elemento trocado pelo AJAX entre achar e clicar e rotina — tem de
        custar a proxima tentativa, nao a rodada inteira.
        """
        try:
            elemento.click()
            return True
        except Exception:
            pass
        try:
            self.js("arguments[0].click();", elemento)
            return True
        except Exception:
            return False

    def rolar_ate(self, elemento):
        self.js("arguments[0].scrollIntoView({block:'center'});", elemento)

    # ── estado da pagina ─────────────────────────────────────────

    @property
    def fonte(self) -> str:
        try:
            return self._driver.page_source.lower()
        except Exception:
            return ""

    def contem(self, *termos) -> bool:
        fonte = self.fonte
        return any(termo in fonte for termo in termos)

    @property
    def tem_erro_interno(self) -> bool:
        return self.contem(*SINAIS_DE_ERRO)

    @property
    def viva(self) -> bool:
        try:
            _ = self._driver.title
            return True
        except Exception:
            return False

    def exigir_sessao(self):
        if not self.viva:
            raise JanelaFechada(
                "A janela do Firefox controlada pelo script foi fechada.")

    # ── evidencia ────────────────────────────────────────────────

    def _destino(self, nome):
        self._config.pasta_rodada.mkdir(parents=True, exist_ok=True)
        return self._config.pasta_rodada / nome

    def capturar(self, nome, erro=False):
        """Screenshot da tela; so com debug, a nao ser que seja de falha."""
        if not (self._config.debug or erro):
            return
        try:
            self._driver.save_screenshot(str(self._destino(f"debug_{nome}.png")))
            self._console.debug(f"Screenshot: debug_{nome}.png")
        except Exception:
            pass

    def salvar_dom(self, nome, erro=False):
        """HTML da tela, pela mesma regra. E por onde se descobre id novo."""
        if not (self._config.debug or erro):
            return
        try:
            destino = self._destino(f"dom_{nome}.html")
            destino.write_text(self._driver.page_source, encoding="utf-8")
            self._console.debug(f"DOM salvo: dom_{nome}.html")
        except Exception:
            pass
