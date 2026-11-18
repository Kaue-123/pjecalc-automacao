"""Tela 'Correção Monetária' (indices-gerais.jsf).

Abas horizontais no topo (TR, UFIR, IGP-M, INPC, IPCA, IPCA-E...), dois campos
de filtro — 'Tabela de *' e 'A partir de', ambos MM/AAAA — e o 'Pesquisar',
que no RichFaces e um <a> com A4J.AJAX.Submit, nao um input[type=submit].
"""

import time

from selenium.webdriver.common.by import By

from ...model.tabela import Tabela
from .grade import grade_visivel

PAUSA_CARGA = 2.0
PAUSA_MENU = 1.0
PAUSA_ABA = 1.5
PAUSA_ROLAGEM = 0.3
PAUSA_ANTES_PESQUISA = 1.0
PAUSA_PESQUISA = 2.5
PAUSA_FOCO = 0.15
PAUSA_CAMPO = 0.2

MINUSCULAS = "translate(%s,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz')"
TERMOS_PESQUISAR = ("pesquisar", "consultar", "buscar", "pesquisa", "filtrar", "ok")
LARGURA_SIDEBAR = 230   # a faixa de abas comeca depois do menu lateral
TIPOS_IGNORADOS = ("hidden", "submit", "button", "checkbox", "radio", "image")


class TelaCorrecaoMonetaria:
    def __init__(self, navegador, menu, console):
        self._nav = navegador
        self._menu = menu
        self._console = console

    def extrair(self, indice) -> Tabela:
        self._console.etapa(f"Extracao de {indice.nome} via Correcao Monetaria")

        if not self._abrir(indice):
            return Tabela()

        if not self._clicar_aba(indice.aba):
            self._nav.capturar(f"02_aba_{indice.nome}_falhou", erro=True)
            self._console.intervencao(
                f"Clique na aba '{indice.aba}' na faixa de abas no topo da tabela.")
        time.sleep(PAUSA_ABA)
        self._nav.capturar(f"03_aba_{indice.nome}_selecionada")

        self._preencher_datas(indice)
        self._nav.capturar(f"04_datas_preenchidas_{indice.nome}")

        # O blur de cada campo dispara a validacao A4J do inputDate. Pesquisar
        # no mesmo instante submete antes de o servidor registrar a competencia
        # nova, e a planilha sai com a faixa errada sem erro nenhum.
        time.sleep(PAUSA_ANTES_PESQUISA)
        if not self._pesquisar(indice.id_pesquisar):
            self._nav.capturar(f"05_pesquisar_falhou_{indice.nome}", erro=True)
            self._console.intervencao("Clique em 'Pesquisar' na tela.")
        time.sleep(PAUSA_PESQUISA)
        self._nav.capturar(f"06_resultados_{indice.nome}")

        if self._nav.tem_erro_interno:
            self._console.erro("Erro interno apos a pesquisa.")
            return Tabela()

        if not self._tem_resultados():
            self._nav.capturar(f"07_sem_dados_{indice.nome}", erro=True)
            self._console.intervencao("A tabela de resultados deve estar visivel.")

        return grade_visivel(self._nav, self._console).ler(indice.nome)

    # ── navegacao ────────────────────────────────────────────────

    def _abrir(self, indice) -> bool:
        self._menu.voltar_ao_inicio()
        time.sleep(PAUSA_MENU)
        self._menu.expandir_tabelas()
        time.sleep(PAUSA_MENU)

        if not self._menu.abrir("correcao_monetaria"):
            if not self._menu.clicar_subitem("Correção Monetária"):
                self._nav.capturar(f"correcao_falhou_{indice.nome}", erro=True)
                self._console.intervencao("Clique em 'Correção Monetária' no submenu.")

        time.sleep(PAUSA_CARGA)
        if self._nav.tem_erro_interno:
            self._console.erro("Erro interno ao abrir Correcao Monetaria.")
            return False

        self._nav.capturar(f"01_correcao_aberta_{indice.nome}")
        self._nav.salvar_dom(f"correcao_monetaria_{indice.nome}")
        return True

    def _clicar_aba(self, texto_aba) -> bool:
        """A faixa de abas e uma <tr> de <td>s. Para nao confundir um 'TR'
        qualquer da pagina com a aba, exige-se que a linha traga tambem outra
        aba conhecida."""
        self._console.info(f"  Clicando na aba '{texto_aba}'...")

        ancoras = [
            f"//tr[.//td[normalize-space(text())='{a}']"
            f" and .//td[normalize-space(text())='{b}']]"
            f"//td[normalize-space(text())='{texto_aba}']"
            for a, b in (("TR", "UFIR"), ("IPCA-E", "IPCA"))
        ]
        # A faixa de abas pode quebrar em mais de uma <tr> com a janela
        # estreita: ai o par exigido acima nao cai na mesma linha da aba.
        ancoras.append(
            f"//td[normalize-space(text())='{texto_aba}' and ancestor::tr["
            f".//td[normalize-space(text())='UFIR']"
            f" or .//td[normalize-space(text())='JAM']]]"
        )
        for xpath in ancoras:
            for el in self._nav.visiveis(xpath):
                self._nav.rolar_ate(el)
                time.sleep(PAUSA_ROLAGEM)
                if self._nav.clicar(el):
                    self._console.ok(f"Aba '{texto_aba}' clicada.")
                    return True

        clicou = self._nav.js("""
            var alvo = arguments[0], larguraMenu = arguments[1];
            var celulas = document.querySelectorAll('td, th');
            var achadas = [];
            for (var i = 0; i < celulas.length; i++) {
                var el = celulas[i];
                if (!el.offsetParent) continue;
                var txt = (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim();
                if (txt !== alvo) continue;
                var caixa = el.getBoundingClientRect();
                if (caixa.width < 5) continue;
                if (caixa.left < larguraMenu) continue;   // nao e aba, e menu
                achadas.push({el: el, x: caixa.left});
            }
            if (achadas.length) {
                achadas.sort(function (a, b) { return a.x - b.x; });
                achadas[0].el.scrollIntoView({block: 'center'});
                achadas[0].el.click();
                return true;
            }
            // Sem a aba, devolve o que ha de parecido e onde esta: e por aqui
            // que se descobre se o corte do menu lateral comeu o alvo, sem
            // precisar de um dump de DOM novo.
            var parecidas = [];
            for (var k = 0; k < celulas.length; k++) {
                var t = (celulas[k].innerText || '').replace(/\\s+/g, ' ').trim();
                if (t.length < 20 && t.toUpperCase().indexOf(alvo.toUpperCase()) !== -1) {
                    parecidas.push(t + '@x=' + Math.round(celulas[k].getBoundingClientRect().left));
                }
            }
            return parecidas.join('; ');
        """, texto_aba, LARGURA_SIDEBAR)
        if clicou is True:
            self._console.ok(f"Aba '{texto_aba}' clicada por texto exato.")
            return True

        self._console.aviso(f"Aba '{texto_aba}' nao encontrada. Parecidas: {clicou or 'nenhuma'}")
        return False

    # ── filtros ──────────────────────────────────────────────────

    def _preencher_datas(self, indice):
        self._console.info(
            f"  Preenchendo: Tabela de={indice.ate} | A partir de={indice.a_partir}")

        campos = (
            ("Tabela de*", indice.id_ate, "Tabela de", indice.ate),
            ("A partir de", indice.id_a_partir, "A partir de", indice.a_partir),
        )
        preenchidos = []
        for rotulo, id_jsf, texto_rotulo, valor in campos:
            preenchidos.append(self._preencher_campo(rotulo, id_jsf, texto_rotulo, valor))

        if not all(preenchidos):
            self._preencher_por_posicao(campos, preenchidos)

        if not all(preenchidos):
            self._nav.capturar("datas_nao_preenchidas", erro=True)
            self._console.intervencao(
                f"Preencha 'Tabela de*' = {indice.ate} e "
                f"'A partir de' = {indice.a_partir}.")

    def _preencher_campo(self, rotulo, id_jsf, texto_rotulo, valor) -> bool:
        """Pelo id JSF primeiro; o rotulo so socorre versao que renomeie ids."""
        campo = self._nav.por_id(id_jsf)
        if campo and self._escrever(campo, valor):
            self._console.ok(f"  '{rotulo}' = '{valor}' (por id)")
            return True

        campo = self._campo_ao_lado_do_rotulo(texto_rotulo)
        if campo and self._escrever(campo, valor):
            self._console.ok(f"  '{rotulo}' = '{valor}' (por rotulo)")
            return True

        self._console.aviso(f"  Campo '{rotulo}' nao encontrado por id nem por rotulo.")
        return False

    def _preencher_por_posicao(self, campos, preenchidos):
        """Ultimo recurso: o 1o e o 2o input editaveis do conteudo.

        Nao filtrar por coordenada: nesta tela o painel de consulta fica com
        'left' negativo, fora da viewport, e um filtro de posicao descartaria
        justamente os dois campos que interessam.
        """
        visiveis = [
            campo for campo in self._nav.por_tag("input")
            if campo.is_displayed() and campo.is_enabled()
            and campo.get_attribute("type") not in TIPOS_IGNORADOS
        ]
        for posicao, (rotulo, _, _, valor) in enumerate(campos):
            if preenchidos[posicao] or posicao >= len(visiveis):
                continue
            if self._escrever(visiveis[posicao], valor):
                preenchidos[posicao] = True
                self._console.ok(f"  '{rotulo}' = '{valor}' (por posicao[{posicao}])")

    def _escrever(self, campo, valor) -> bool:
        """Preenche sem TAB e sem ESC.

        Entre os dois inputs ha um botao de calendario: o TAB levaria o foco
        para ele e abriria o calendario. E o ESC, que pareceria a saida obvia
        para fechar esse calendario, e tratado pelo RichFaces como 'cancelar' —
        ele limpa o campo recem preenchido. O blur() abaixo fecha e preserva.
        """
        try:
            self._nav.rolar_ate(campo)
            self._nav.js("arguments[0].focus();", campo)
            time.sleep(PAUSA_FOCO)          # o calendario assenta o foco antes de limpar
            self._nav.js("arguments[0].value = '';", campo)
            campo.send_keys(valor)
            time.sleep(PAUSA_FOCO)          # o valor digitado assenta antes dos eventos
            self._nav.js("""
                var el = arguments[0];
                ['input', 'change', 'blur'].forEach(function (evento) {
                    el.dispatchEvent(new Event(evento, {bubbles: true}));
                });
            """, campo)
            time.sleep(PAUSA_CAMPO)
            return valor in (self._nav.js("return arguments[0].value;", campo) or "")
        except Exception as erro:
            self._console.aviso(f"    Erro ao escrever '{valor}': {erro}")
            return False

    def _campo_ao_lado_do_rotulo(self, rotulo):
        """Procura o <input> na celula seguinte a do rotulo — nao na <tr>
        inteira, que traz os dois campos e o botao de pesquisar juntos."""
        return self._nav.js("""
            var rotulo = arguments[0].toLowerCase().trim();
            var celulas = document.querySelectorAll('td, th, label, span');
            for (var i = 0; i < celulas.length; i++) {
                var celula = celulas[i];
                if (!celula.offsetParent) continue;
                var txt = (celula.innerText || celula.textContent || '').trim().toLowerCase();
                if (txt.indexOf(rotulo) === -1 || txt.length > 60) continue;

                var seletor = 'input[type=text], input[type=month],'
                            + ' input:not([type]):not([type=hidden])';
                var prox = celula.nextElementSibling;
                while (prox) {
                    var campo = prox.querySelector(seletor);
                    if (campo && campo.offsetParent && !campo.disabled && !campo.readOnly) {
                        return campo;
                    }
                    if (prox.querySelectorAll('input').length > 0) break;
                    prox = prox.nextElementSibling;
                }
                var proprio = celula.querySelector(seletor);
                if (proprio && proprio.offsetParent) return proprio;
            }
            return null;
        """, rotulo)

    # ── pesquisa ─────────────────────────────────────────────────

    def _pesquisar(self, id_botao) -> bool:
        botao = self._nav.por_id(id_botao)
        if botao and self._nav.clicar(botao):
            self._console.ok(f"Botao 'Pesquisar' clicado (id {id_botao})")
            return True

        for termo in TERMOS_PESQUISAR:
            for xpath in (
                f"//input[contains({MINUSCULAS % '@value'},'{termo}')]",
                f"//button[contains({MINUSCULAS % 'text()'},'{termo}')]",
                f"//a[contains({MINUSCULAS % 'text()'},'{termo}')"
                f" and not(contains(@class,'menu'))]",
            ):
                for el in self._nav.clicaveis(xpath):
                    if self._nav.clicar(el):
                        self._console.ok(f"Botao de pesquisa clicado: '{termo}'")
                        return True

        formularios = self._nav.por_tag("form")
        if formularios:
            try:
                self._nav.js("arguments[0].submit();", formularios[0])
                self._console.ok("Formulario submetido via JS.")
                return True
            except Exception as erro:
                self._console.aviso(f"Submit do formulario falhou: {erro}")
        return False

    def _tem_resultados(self) -> bool:
        if self._nav.tem_erro_interno:
            return False
        for tabela in self._nav.por_tag("table"):
            try:
                if len(tabela.find_elements(By.TAG_NAME, "tr")) < 3:
                    continue
                if sum(c.isdigit() for c in tabela.text) > 10:
                    return True
            except Exception:
                continue
        return False
