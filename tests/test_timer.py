"""
Agenda do timer: "dia 6, e se cair no fim de semana, na segunda seguinte".

O OnCalendar sozinho nao expressa isso — ele dispara nos dias 6, 7 e 8, e quem
descarta as sobras e o marcador de mes do rodada-mensal.sh. O que se testa aqui
e a outra metade: que o PRIMEIRO disparo de cada mes cai no dia certo.

Le a unidade de verdade, nao uma copia da expressao.
"""
import os
import re
import subprocess
import unittest
from datetime import date, timedelta

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UNIDADE_TIMER = os.path.join(RAIZ, "scripts", "pjecalc-indices.timer")
UNIDADE_SERVICO = os.path.join(RAIZ, "scripts", "pjecalc-indices.service")
MESES_CONFERIDOS = 24
ITERACOES = MESES_CONFERIDOS * 3 + 6


def campo(arquivo, chave):
    with open(arquivo, encoding="utf-8") as f:
        for linha in f:
            if linha.strip().startswith(chave + "="):
                return linha.strip().split("=", 1)[1]
    return None


def primeiro_dia_util_a_partir_de(ano, mes, dia):
    d = date(ano, mes, dia)
    while d.weekday() >= 5:            # 5 = sabado, 6 = domingo
        d += timedelta(days=1)
    return d


def disparos(expressao, iteracoes, tz=None):
    ambiente = dict(os.environ, TZ=tz) if tz else None
    saida = subprocess.run(
        ["systemd-analyze", "calendar", f"--iterations={iteracoes}", expressao],
        capture_output=True, text=True, check=True, env=ambiente).stdout
    datas = []
    for linha in saida.splitlines():
        if "Next elapse" in linha or "Iteration" in linha:
            m = re.search(r"(\d{4})-(\d{2})-(\d{2})", linha)
            if m:
                datas.append(date(*map(int, m.groups())))
    return datas


class TestAgenda(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.expressao = campo(UNIDADE_TIMER, "OnCalendar")
        cls.datas = disparos(cls.expressao, ITERACOES)

    def test_expressao_existe(self):
        self.assertIsNotNone(self.expressao, "OnCalendar sumiu da unidade")

    def test_horario_e_11h(self):
        self.assertIn("11:00:00", self.expressao)

    def test_fuso_vai_explicito(self):
        """Servidor costuma rodar em UTC, e ai '11:00' seria 8h no Brasil."""
        self.assertIn("America/", self.expressao)

    def test_agenda_nao_muda_se_a_maquina_estiver_em_utc(self):
        sob_utc = disparos(self.expressao, 12, tz="UTC")
        sob_local = disparos(self.expressao, 12)
        self.assertEqual(sob_utc, sob_local,
                         "a rodada mudaria de dia conforme o fuso do host")

    def test_nunca_dispara_em_fim_de_semana(self):
        fds = [d for d in self.datas if d.weekday() >= 5]
        self.assertEqual(fds, [], f"disparo em fim de semana: {fds}")

    def test_nunca_dispara_fora_dos_dias_6_7_8(self):
        fora = [d for d in self.datas if d.day not in (6, 7, 8)]
        self.assertEqual(fora, [], f"disparo fora da janela: {fora}")

    def test_todo_mes_tem_rodada_no_dia_6_ou_no_util_seguinte(self):
        """
        O caso que motiva tudo: sabado empurra para segunda, domingo tambem.

        Percorre os meses ESPERADOS, nao os que aparecem na saida — um mes sem
        disparo nenhum e justamente a falha que importa, e varrer so o que
        existe deixaria ela passar.
        """
        por_mes = {}
        for d in self.datas:
            por_mes.setdefault((d.year, d.month), []).append(d)

        ano, mes = min(por_mes)                      # o mes corrente pode ja ter passado
        for _ in range(MESES_CONFERIDOS):
            esperado = primeiro_dia_util_a_partir_de(ano, mes, 6)
            self.assertIn((ano, mes), por_mes,
                          f"{mes:02d}/{ano} ficaria SEM rodada nenhuma")
            self.assertEqual(min(por_mes[(ano, mes)]), esperado,
                             f"{mes:02d}/{ano}: esperado {esperado} ({esperado:%a}), "
                             f"veio {min(por_mes[(ano, mes)])}")
            ano, mes = (ano + 1, 1) if mes == 12 else (ano, mes + 1)

    def test_cobre_os_tres_casos_de_calendario(self):
        """A suite so vale se os meses conferidos incluirem sabado e domingo."""
        inicio = date.today().replace(day=1)
        semanas = set()
        for i in range(MESES_CONFERIDOS):
            ano, mes = divmod(inicio.month - 1 + i, 12)
            semanas.add(date(inicio.year + ano, mes + 1, 6).weekday())
        self.assertTrue(semanas & {5}, "nenhum dia 6 em sabado no periodo conferido")
        self.assertTrue(semanas & {6}, "nenhum dia 6 em domingo no periodo conferido")


class TestUnidades(unittest.TestCase):
    def test_persistent_ligado(self):
        """Sem Persistent, uma rodada perdida com a maquina desligada nunca acontece."""
        self.assertEqual(campo(UNIDADE_TIMER, "Persistent"), "true")

    def test_timer_aponta_para_o_servico_certo(self):
        self.assertEqual(campo(UNIDADE_TIMER, "Unit"), "pjecalc-indices.service")

    def test_timeout_maior_que_a_extracao(self):
        """A extracao passa de 10 min; timeout curto mataria a rodada no meio."""
        t = campo(UNIDADE_SERVICO, "TimeoutStartSec")
        self.assertRegex(t, r"^(\d+)min$")
        self.assertGreaterEqual(int(t[:-3]), 30)

    def test_servico_depende_do_pjecalc(self):
        self.assertIn("pjecalc.service", campo(UNIDADE_SERVICO, "Wants"))

    def test_caminho_do_repositorio_nao_esta_fixo(self):
        """O ExecStart versionado tem que ser o placeholder, nao a maquina de alguem."""
        self.assertIn("__PROJETO__", campo(UNIDADE_SERVICO, "ExecStart"))

    def test_unidades_validam_no_systemd(self):
        r = subprocess.run(["systemd-analyze", "verify", UNIDADE_TIMER],
                           capture_output=True, text=True)
        self.assertNotIn("Failed", r.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
