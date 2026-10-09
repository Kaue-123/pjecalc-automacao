import br.jus.trt8.pjecalcsa.container.Lancador;
import br.jus.trt8.pjecalcsa.container.TomCat;

import java.io.File;
import java.lang.reflect.Method;

/**
 * Sobe o PJe-Calc Cidadao como servico, sem interface grafica.
 *
 * O Lancador oficial so abre uma UI depois de subir o Tomcat, e no Wayland
 * essa UI e uma JFrame inutil. Ela so nao podia ser fechada porque era a
 * thread de eventos do AWT que segurava a JVM viva — as threads do Tomcat
 * embarcado sao daemon. Aqui o CountDownLatch faz esse papel.
 *
 * Detalhes em README.md, secao "Sem janela: o modo servico".
 */
public class PjeCalcServico {

    public static void main(String[] args) throws Exception {
        System.setProperty("caminho.instalacao", new File("").getAbsolutePath());

        // Privados no Lancador, e nao ha outro ponto de entrada.
        chamarPrivadoDoLancador("configurarVariaveisBase");
        chamarPrivadoDoLancador("validarPastaInstalador");

        new TomCat("tomcat").startTomcat();
        // SITE sai do proprio Lancador, preenchido por configurarVariaveisBase.
        System.out.println("PJe-Calc servindo em " + Lancador.SITE);

        // Segura a main ate o SIGTERM; o hook do Catalina fecha Tomcat e H2.
        new java.util.concurrent.CountDownLatch(1).await();
    }

    private static void chamarPrivadoDoLancador(String nome) throws Exception {
        Method m = Class.forName("br.jus.trt8.pjecalcsa.container.Lancador")
                .getDeclaredMethod(nome);
        m.setAccessible(true);
        m.invoke(null);
    }
}
