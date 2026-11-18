"""Tela 'Atualização de Tabelas e Índices': baixa do TRT 8 o que ha de novo."""

import time

from selenium.webdriver.support.ui import Select

PAUSA_CARGA = 2.0
INTERVALO_SONDA = 4.0
MAX_SONDAS = 60          # 4 min

# Para PULAR a atualizacao, so a frase inteira serve: um "recentes dispon"
# solto em qualquer rotulo da tela faria a rodada do mes inteira passar por
# cima da base velha, com saida 0 e cara de sucesso. Ja para reconhecer que a
# atualizacao TERMINOU, depois do clique, vale o termo frouxo.
JA_ATUALIZADO = ("mais recentes disponíveis", "ja possui", "já possui")
CONCLUIDO = ("sucesso", "atualizado", "conclu", "finaliz", "recentes dispon") + JA_ATUALIZADO

MINUSCULAS = "translate(%s,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz')"


class TelaAtualizacao:
    def __init__(self, navegador, menu, console):
        self._nav = navegador
        self._menu = menu
        self._console = console

    def executar(self) -> bool:
        self._menu.voltar_ao_inicio()
        self._menu.expandir_tabelas()

        if not self._menu.abrir("atualizacao"):
            if not self._menu.clicar_subitem("Atualização de Tabelas e Índices"):
                self._console.intervencao(
                    "Clique em 'Atualização de Tabelas e Índices' no submenu.")

        time.sleep(PAUSA_CARGA)
        self._nav.capturar("tela_atualizacao")
        self._nav.salvar_dom("tela_atualizacao")

        if self._nav.contem(*JA_ATUALIZADO):
            self._console.ok("Tabelas ja estao atualizadas (alerta confirmado).")
            return True

        self._selecionar_trt8()
        time.sleep(1)

        if not self._clicar_atualizar_online():
            self._console.intervencao("Clique em 'Atualizar Online' e aguarde concluir.")
            return True

        return self._aguardar_conclusao()

    def _aguardar_conclusao(self) -> bool:
        self._console.info("Aguardando atualizacao...")
        for _ in range(MAX_SONDAS):
            time.sleep(INTERVALO_SONDA)
            self._console.progresso()
            if self._nav.tem_erro_interno:
                self._console.espaco()
                self._console.aviso("Erro interno durante a atualizacao.")
                self._nav.capturar("erro_atualizacao", erro=True)
                self._menu.voltar_ao_inicio()
                return False
            if self._nav.contem(*CONCLUIDO):
                self._console.espaco()
                self._console.ok("Atualizacao concluida.")
                return True
        self._console.espaco()
        self._console.aviso("Timeout na atualizacao. Seguindo assim mesmo.")
        return True

    def _selecionar_trt8(self):
        for elemento in self._nav.por_tag("select"):
            try:
                combo = Select(elemento)
                for opcao in combo.options:
                    texto = opcao.text.lower()
                    if ("8" in texto and "trt" in texto) or "par" in texto or "amap" in texto:
                        combo.select_by_visible_text(opcao.text)
                        self._console.ok(f"TRT selecionado: '{opcao.text}'")
                        return
                opcoes = [o.text for o in combo.options if o.text.strip()]
                if opcoes:
                    self._console.aviso(f"TRT 8 nao esta entre as opcoes: {opcoes}")
            except Exception:
                continue

        self._nav.capturar("selecao_trt_falhou", erro=True)
        self._console.intervencao("Selecione 'TRT 8a Região' na tela.")

    def _clicar_atualizar_online(self) -> bool:
        for xpath in (
            f"//input[contains({MINUSCULAS % '@value'},'atualiz')]",
            f"//button[contains({MINUSCULAS % 'text()'},'atualiz')]",
            f"//a[contains(@class,'btn') and contains({MINUSCULAS % 'text()'},'atualiz')]",
            "//input[@type='submit']",
            "//button[@type='submit']",
        ):
            for el in self._nav.clicaveis(xpath):
                rotulo = (el.get_attribute("value") or el.text or "").strip()
                if self._nav.clicar(el):
                    self._console.ok(f"Botao clicado: '{rotulo}'")
                    return True
        return False
