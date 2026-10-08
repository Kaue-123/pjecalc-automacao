import br.jus.trt8.pjecalcsa.container.TomCat;

import java.io.File;
import java.lang.reflect.Method;

/**
 * Sobe o PJe-Calc Cidadao como servico, sem interface grafica.
 *
 * O Lancador oficial (br.jus.trt8.pjecalcsa.container.Lancador) faz tres coisas:
 * prepara as variaveis e o banco, sobe o Tomcat e so entao abre uma UI. A UI e
 * um icone na bandeja do sistema quando ha bandeja; quando nao ha -- Wayland,
 * por exemplo -- ele cai numa JFrame com dois botoes ("Abrir o PjeCalc" e
 * "Sair") que fica parada na tela sem servir para nada em uso automatizado.
 *
 * Aqui repetimos as duas primeiras etapas e paramos antes da terceira, sem
 * precisar de display nenhum. Em compensacao a main tem de ficar bloqueada: as
 * threads do Tomcat embarcado sao daemon, quem segurava a JVM viva era
 * justamente a thread de eventos do AWT que a UI criava.
 */
public class PjeCalcServico {

    public static void main(String[] args) throws Exception {
        System.setProperty("caminho.instalacao", new File("").getAbsolutePath());

        // Privados no Lancador, e nao ha outro ponto de entrada: configuram a
        // porta/URL e convertem o persistence.xml pendente da instalacao.
        chamarPrivadoDoLancador("configurarVariaveisBase");
        chamarPrivadoDoLancador("validarPastaInstalador");

        new TomCat("tomcat").startTomcat();
        System.out.println("PJe-Calc servindo em http://localhost:9257/pjecalc");

        // Segura a main (nao-daemon) ate chegar um SIGTERM. O hook de desligamento
        // do Catalina cuida de parar o Tomcat e fechar o H2.
        new java.util.concurrent.CountDownLatch(1).await();
    }

    private static void chamarPrivadoDoLancador(String nome) throws Exception {
        Method m = Class.forName("br.jus.trt8.pjecalcsa.container.Lancador")
                .getDeclaredMethod(nome);
        m.setAccessible(true);
        m.invoke(null);
    }
}
