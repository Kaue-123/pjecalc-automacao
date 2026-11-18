"""Menu lateral de principal.jsf."""

import time

PAUSA_AJAX = 2.5
PAUSA_CLIQUE = 2.0
PAUSA_EXPANSAO = 1.2

# Ids estaveis do <li> no menu lateral (PJe-Calc 2.16.0). Sao muito mais
# confiaveis que casar o texto acentuado da tela ("Correção Monetária"), que
# quebra com entidades HTML e espacos nao-quebraveis.
ITENS = {
    "inicio": "li_tela_inicial",
    "correcao_monetaria": "li_tabelas_indices_gerais",
    "atualizacao": "li_tabelas_sincronizar",
}


class Menu:
    def __init__(self, navegador, console):
        self._nav = navegador
        self._console = console

    def abrir(self, item) -> bool:
        """Dispara o item pelo id do <li>, clicando no <a> interno.

        Funciona com o submenu colapsado: o <a> carrega o handler
        A4J.AJAX.Submit no onclick, e um clique via JS dispara o handler mesmo
        com o elemento em display:none.
        """
        li_id = ITENS[item]
        self._nav.exigir_sessao()
        resposta = self._nav.js("""
            var li = document.getElementById(arguments[0]);
            if (!li) return 'SEM_LI';
            var a = li.querySelector('a');
            if (!a) return 'SEM_A';
            var txt = (a.innerText || a.textContent || '').trim();
            a.click();
            return 'OK:' + txt;
        """, li_id)

        if not (isinstance(resposta, str) and resposta.startswith("OK:")):
            self._console.aviso(f"Item de menu '{li_id}' nao encontrado ({resposta}).")
            return False

        time.sleep(PAUSA_AJAX)
        if self._nav.tem_erro_interno:
            self._console.aviso(f"Erro interno apos acionar '{li_id}'.")
            self._nav.capturar(f"erro_menu_{li_id}", erro=True)
            return False
        self._console.ok(f"Menu acionado: '{resposta[3:]}' ({li_id})")
        return True

    def voltar_ao_inicio(self):
        """Volta clicando no menu, nao com driver.get(): o PJe-Calc guarda o
        estado da tela no servidor e um GET em principal.jsf descartaria tudo."""
        self._nav.exigir_sessao()
        if not self.abrir("inicio"):
            self._nav.ir_para_home()
        time.sleep(PAUSA_CLIQUE)

    def expandir_tabelas(self):
        """Abre o submenu 'Tabelas'. Puramente cosmetico — serve para os
        screenshots mostrarem o menu aberto; a navegacao real usa abrir()."""
        if self._submenu_aberto:
            return

        clicou = self._nav.js("""
            var lis = document.querySelectorAll('li.header, li[class^="header"]');
            for (var i = 0; i < lis.length; i++) {
                if ((lis[i].innerText || '').trim() === 'Tabelas') {
                    lis[i].click();
                    return true;
                }
            }
            return false;
        """)
        if clicou:
            time.sleep(PAUSA_EXPANSAO)

    @property
    def _submenu_aberto(self) -> bool:
        """Testa visibilidade real, nunca o page_source: o PJe-Calc renderiza
        todo o submenu no HTML e apenas esconde o container com display:none,
        de modo que procurar o texto no fonte responde 'aberto' com ele
        fechado — era esse o bug que fazia todos os cliques seguintes falharem.
        """
        try:
            return bool(self._nav.js("""
                var li = document.getElementById('li_tabelas_indices_gerais');
                return !!(li && li.offsetParent !== null);
            """))
        except Exception:
            return False

    def clicar_subitem(self, texto_exato) -> bool:
        """Rede de seguranca para quando o id do <li> mudar de nome."""
        for xpath in (
            f"//a[normalize-space(text())='{texto_exato}']",
            f"//span[normalize-space(text())='{texto_exato}']",
            f"//li[normalize-space(.)='{texto_exato}']//a",
            # Curinga: o item pode vir como <div> ou <td> numa versao nova, e e
            # justamente quando o id do <li> muda que esta rede e acionada.
            f"//*[normalize-space(text())='{texto_exato}']",
        ):
            for el in self._nav.visiveis(xpath):
                if not self._nav.clicar(el):
                    continue
                time.sleep(PAUSA_CLIQUE)
                if not self._nav.tem_erro_interno:
                    self._console.ok(f"Subitem clicado: '{texto_exato}'")
                    return True
                self._console.aviso(f"Erro interno apos clicar em '{texto_exato}'.")
                self.voltar_ao_inicio()
                return False
        return False
