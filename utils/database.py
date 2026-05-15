"""
Questo modulo gestisce la connessione e la comunicazione con il database MySQL.
"""
import mysql.connector
import logging
import os
import asyncio
import queries

async def connect_to_db():
    """
    Stabilisce la connessione al database utilizzando le credenziali dall'ambiente
    e restituisce gli oggetti di connessione e cursore.
    """
    try:
        db = mysql.connector.connect(
            host=os.getenv("MYSQL_HOST"),
            user=os.getenv("MYSQL_USER"),
            password=os.getenv("MYSQL_PASSWORD"),
            database=os.getenv("MYSQL_DB"),
            autocommit=False  # Disabilitiamo l'autocommit per gestire le transazioni manualmente
        )
        # Usiamo dictionary=True per ottenere i risultati come dizionari
        cursor = db.cursor(dictionary=True)
        logging.info("Connessione al database stabilita con successo.")
        return db, cursor
    except mysql.connector.Error as err:
        logging.error(f"Errore di connessione al database: {err}", exc_info=True)
        raise

async def close_db_connection(bot):
    """
    Chiude in modo sicuro la connessione al database.
    """
    try:
        if hasattr(bot, 'cursor') and bot.cursor:
            bot.cursor.close()
        if hasattr(bot, 'db') and bot.db and bot.db.is_connected():
            bot.db.close()
        logging.info("Connessione al database chiusa correttamente.")
    except Exception as e:
        logging.error(f"Errore durante la chiusura della connessione al DB: {e}", exc_info=True)

async def keep_db_alive(bot):
    """
    Task periodico che esegue una semplice query per mantenere attiva la connessione
    al database ed evitare timeout.
    """
    while True:
        await asyncio.sleep(3600)  # Esegui ogni ora
        try:
            if not hasattr(bot, 'db') or not bot.db.is_connected():
                logging.warning("Connessione al DB persa. Tentativo di riconnessione...")
                bot.db, bot.cursor = await connect_to_db()
            else:
                # Esegue una query leggera per mantenere la connessione
                bot.cursor.execute(queries.keep_alive_query)
                bot.cursor.fetchone()
                logging.debug("Eseguita query keep-alive per il database.")
        except Exception as e:
            logging.error(f"Errore nel task keep-alive del DB: {e}", exc_info=True)
            # In caso di errore, tenta di riconnettersi al prossimo ciclo
            if hasattr(bot, 'db') and bot.db.is_connected():
                bot.db.close()