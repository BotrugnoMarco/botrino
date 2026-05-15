#!/bin/bash
# Gestione bot Discord (start, stop, restart, status, logs, update) con variabili da .env

# Carico le variabili da .env
set -a
source /home/botadmin/discord-bot/.env
set +a

send_discord() {
    MESSAGE=$1
    curl -H "Content-Type: application/json" -X POST -d "{\"content\": \"$MESSAGE\"}" $WEBHOOK_URL > /dev/null 2>&1
}

cd $BOT_DIR || exit

# Funzione per aggiornare il codice da Git
update_code() {
    echo "Aggiornamento del codice da Git..."

    # Ferma il bot prima di aggiornare
    $0 stop

    # Svuota il file di log prima di aggiornare
    : > $BOT_DIR/bot.log
    echo "File di log svuotato."

    # Esegue il pull del codice dal repository Git e cattura l'output
    git pull origin main 2>&1

    GIT_PULL_RESULT=$?

    if [ $GIT_PULL_RESULT -eq 0 ]; then
        echo "🆕 Codice aggiornato con successo."
        send_discord "🆕 Il codice del bot è stato **aggiornato** da Git."

        # Installa/aggiorna le dipendenze
        echo "Installazione/aggiornamento delle dipendenze..."
        source $VENV  # Attiva l'ambiente virtuale
        pip install -r requirements.txt
        deactivate # Disattiva l'ambiente virtuale

        # Riavvia il bot dopo l'aggiornamento
        $0 start
    else
        echo "❌ Errore durante l'aggiornamento del codice."
        # Cattura l'output di errore di git pull
        GIT_ERROR=$(git pull origin main 2>&1)
        echo "Errore Git: $GIT_ERROR"
        send_discord "❌ Errore durante l'aggiornamento del codice da Git. Errore: $GIT_ERROR"
    fi
}

case "$1" in
    start)
        if pgrep -f "python3 $BOT_SCRIPT" > /dev/null
        then
            echo "⚠️  Il bot è già in esecuzione!"
        else
            echo "✅ Avvio del bot..."
            source $VENV
            nohup python3 $BOT_SCRIPT > logs/bot.log 2>&1 &
            echo "Bot avviato (log in $BOT_DIR/bot.log)"
            send_discord "✅ Il bot è stato **avviato** sul server."
        fi
        ;;
    stop)
        if pgrep -f "python3 $BOT_SCRIPT" > /dev/null
        then
            echo "🛑 Arresto del bot..."
            pkill -f "python3 $BOT_SCRIPT"
            echo "Bot fermato."
            send_discord "🛑 Il bot è stato **fermato** manualmente."
        else
            echo "⚠️  Il bot non è in esecuzione."
        fi
        ;;
    restart)
        $0 stop
        sleep 2
        $0 start
        send_discord "🔄 Il bot è stato **riavviato**."
        ;;
    status)
        if PID=$(pgrep -f "python3 $BOT_SCRIPT")
        then
            START_TIME=$(ps -o etime= -p $PID)
            echo "✅ Il bot è in esecuzione (PID: $PID) da $START_TIME."
        else
            echo "❌ Il bot non è attivo."
        fi
        ;;
    logs)
        tail -f $BOT_DIR/bot.log
        ;;
    update)
        update_code
        ;;
    *)
        echo "Uso: $0 {start|stop|restart|status|logs|update}"
        exit 1
        ;;
esac

exit 0
