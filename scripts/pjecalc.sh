#!/usr/bin/env bash
# PJe-Calc Cidadao 2.16.0 — lancador para Linux
# O bundle oficial do TRT8 so traz .bat + JRE Windows, mas a aplicacao e Java puro
# (Tomcat 7 embarcado + H2). Aqui usamos um JDK 8 do mise no lugar do JRE embutido.
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
JAVA_HOME_8="${PJECALC_JAVA_HOME:-$HOME/.local/share/mise/installs/java/temurin-8.0.504+1}"
JAVA="$JAVA_HOME_8/bin/java"
PIDFILE="$APP_DIR/.pjecalc.pid"
# Parametros que vieram do iniciarPjeCalc.bat do instalador oficial. O
# instalar-pjecalc-linux.sh extrai do .bat e grava aqui; nao ficam versionados.
ENVFILE="$APP_DIR/pjecalc.env"
[ -f "$ENVFILE" ] && . "$ENVFILE"
: "${PJECALC_TOKEN_SERVICOS:?faltando pjecalc.env — rode scripts/instalar-pjecalc-linux.sh}"
: "${PJECALC_SEGURANCA_CONTEXTO:=https://pje.trtXX.jus.br/pje-seguranca}"
LOGFILE="$APP_DIR/pjecalc.log"
URL="http://localhost:9257/pjecalc/pages/principal.jsf"

# Java 8 e obrigatorio: em Java 21 o JBoss Seam/Drools quebra no encapsulamento
# de modulos (InaccessibleObjectException), mesmo com --add-opens.
[ -x "$JAVA" ] || { echo "Java 8 nao encontrado em $JAVA_HOME_8"; \
  echo "Instale com: mise install java@temurin-8.0.504+1"; exit 1; }

rodando() { [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; }

start() {
  if rodando; then echo "Ja esta rodando (pid $(cat "$PIDFILE")). URL: $URL"; return 0; fi
  cd "$APP_DIR"
  # Precisa de display (XWayland serve). Em -Djava.awt.headless=true o Java 8
  # estoura HeadlessException em SplashScreen.getSplashScreen() e derruba o
  # processo antes do Tomcat subir. O -splash e o que mantem a thread main viva.
  # setsid: solta o processo numa sessao propria, para ele nao morrer junto com
  # o terminal (ou com a limpeza de jobs de quem chamou o script).
  setsid nohup "$JAVA" \
    -splash:pjecalc_splash.gif \
    -Duser.timezone=GMT-3 \
    -Dfile.encoding=ISO-8859-1 \
    -Dseguranca.pjecalc.tokenServicos="$PJECALC_TOKEN_SERVICOS" \
    -Dseguranca.pjekz.servico.contexto="$PJECALC_SEGURANCA_CONTEXTO" \
    -Xms1024m -Xmx2048m -XX:MaxPermSize=512m \
    -jar bin/pjecalc.jar > "$LOGFILE" 2>&1 &
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

stop() {
  if ! rodando; then echo "Nao esta rodando."; rm -f "$PIDFILE"; return 0; fi
  kill "$(cat "$PIDFILE")"
  for _ in $(seq 1 20); do rodando || break; sleep 1; done
  rodando && kill -9 "$(cat "$PIDFILE")" 2>/dev/null || true
  rm -f "$PIDFILE"; echo "Parado."
}

case "${1:-start}" in
  start)   start ;;
  stop)    stop ;;
  restart) stop; start ;;
  status)  if rodando; then echo "rodando (pid $(cat "$PIDFILE")) — $URL"; else echo "parado"; fi ;;
  abrir)   start && xdg-open "$URL" >/dev/null 2>&1 & ;;
  *) echo "uso: $0 {start|stop|restart|status|abrir}"; exit 1 ;;
esac
