#!/usr/bin/env bash
# PJe-Calc Cidadao 2.16.0 — lancador para Linux
# O bundle oficial do TRT8 so traz .bat + JRE Windows, mas a aplicacao e Java puro
# (Tomcat 7 embarcado + H2). Aqui usamos um JDK 8 do mise no lugar do JRE embutido.
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
JAVA_HOME_8="${PJECALC_JAVA_HOME:-$HOME/.local/share/mise/installs/java/temurin-8.0.504+1}"
JAVA="$JAVA_HOME_8/bin/java"
JAVAC="$JAVA_HOME_8/bin/javac"
PIDFILE="$APP_DIR/.pjecalc.pid"
# Classe propria que sobe so o Tomcat, sem a UI do Lancador oficial. O fonte fica
# em scripts/servico/ no repositorio; o instalador compila para ca.
CLASSES_SERVICO="$APP_DIR/bin/servico"
FONTE_SERVICO="$APP_DIR/bin/servico/PjeCalcServico.java"
# Parametros que vieram do iniciarPjeCalc.bat do instalador oficial. O
# instalar-pjecalc-linux.sh extrai do .bat e grava aqui; nao ficam versionados.
ENVFILE="$APP_DIR/pjecalc.env"
[ -f "$ENVFILE" ] && . "$ENVFILE"
: "${PJECALC_TOKEN_SERVICOS:?faltando pjecalc.env — rode scripts/instalar-pjecalc-linux.sh}"
: "${PJECALC_SEGURANCA_CONTEXTO:=https://pje.trtXX.jus.br/pje-seguranca}"
LOGFILE="$APP_DIR/pjecalc.log"
URL="http://localhost:9257/pjecalc/pages/principal.jsf"
ARGS_JVM=(
  -Djava.awt.headless=true
  -Duser.timezone=GMT-3
  -Dfile.encoding=ISO-8859-1
  -Dseguranca.pjecalc.tokenServicos="$PJECALC_TOKEN_SERVICOS"
  -Dseguranca.pjekz.servico.contexto="$PJECALC_SEGURANCA_CONTEXTO"
  -Xms1024m -Xmx2048m -XX:MaxPermSize=512m
  -cp "bin/pjecalc.jar:$CLASSES_SERVICO" PjeCalcServico
)

# Java 8 e obrigatorio: em Java 21 o JBoss Seam/Drools quebra no encapsulamento
# de modulos (InaccessibleObjectException), mesmo com --add-opens.
[ -x "$JAVA" ] || { echo "Java 8 nao encontrado em $JAVA_HOME_8"; \
  echo "Instale com: mise install java@temurin-8.0.504+1"; exit 1; }

rodando() { [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; }

start() {
  if rodando; then echo "Ja esta rodando (pid $(cat "$PIDFILE")). URL: $URL"; return 0; fi
  cd "$APP_DIR"
  [ -f "$CLASSES_SERVICO/PjeCalcServico.class" ] || compilar_servico
  # Sem display e sem janela: o Main-Class do jar (Lancador) sobe o Tomcat e so
  # entao abre uma UI — icone de bandeja onde ha bandeja, e uma JFrame com os
  # botoes "Abrir o PjeCalc"/"Sair" onde nao ha, que e o caso no Wayland. Chamando
  # PjeCalcServico pulamos essa ultima etapa: nada de AWT, nada de -splash, e
  # headless=true deixa de ser problema porque ninguem mais pede SplashScreen.
  # setsid: solta o processo numa sessao propria, para ele nao morrer junto com
  # o terminal (ou com a limpeza de jobs de quem chamou o script).
  setsid nohup "$JAVA" "${ARGS_JVM[@]}" > "$LOGFILE" 2>&1 &
  echo $! > "$PIDFILE"
  echo -n "Subindo PJe-Calc"
  for _ in $(seq 1 90); do
    if [ "$(curl -s -o /dev/null -w '%{http_code}' "$URL" || true)" = "200" ]; then
      echo " OK"; echo "URL: $URL"; echo "Log: $LOGFILE"; return 0
    fi
    echo -n "."; sleep 2
  done
  echo " FALHOU"; tail -20 "$LOGFILE"; return 1
}

compilar_servico() {
  [ -f "$FONTE_SERVICO" ] || { echo "Falta $FONTE_SERVICO"; \
    echo "Copie de scripts/servico/ do repositorio, ou rode scripts/instalar-pjecalc-linux.sh"; exit 1; }
  [ -x "$JAVAC" ] || { echo "javac nao encontrado em $JAVA_HOME_8 (precisa do JDK, nao do JRE)"; exit 1; }
  "$JAVAC" -encoding UTF-8 -cp "$APP_DIR/bin/pjecalc.jar" -d "$CLASSES_SERVICO" "$FONTE_SERVICO"
}

stop() {
  if ! rodando; then echo "Nao esta rodando."; rm -f "$PIDFILE"; return 0; fi
  kill "$(cat "$PIDFILE")"
  for _ in $(seq 1 20); do rodando || break; sleep 1; done
  rodando && kill -9 "$(cat "$PIDFILE")" 2>/dev/null || true
  rm -f "$PIDFILE"; echo "Parado."
}

# Sem setsid e sem pidfile: quem controla o ciclo de vida e o supervisor
# (systemd), que precisa do java como processo principal da unidade.
foreground() {
  cd "$APP_DIR"
  [ -f "$CLASSES_SERVICO/PjeCalcServico.class" ] || compilar_servico
  exec "$JAVA" "${ARGS_JVM[@]}"
}

case "${1:-start}" in
  start)   start ;;
  foreground) foreground ;;
  stop)    stop ;;
  restart) stop; start ;;
  status)  if rodando; then echo "rodando (pid $(cat "$PIDFILE")) — $URL"; else echo "parado"; fi ;;
  abrir)   start && xdg-open "$URL" >/dev/null 2>&1 & ;;
  *) echo "uso: $0 {start|stop|restart|status|abrir|foreground}"; exit 1 ;;
esac
