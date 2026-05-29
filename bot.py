import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import logging
import asyncio
import pytz
import aiohttp
from utils import database

# --- CONFIGURAZIONE ---
logging.basicConfig(filename='bot.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
load_dotenv()


# --- CLASSE BOT PERSONALIZZATA ---
class Botrino(commands.Bot):
    """
    Classe personalizzata del bot che estende commands.Bot per aggiungere funzionalità specifiche.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.active_sessions = {}  # Traccia le sessioni vocali attive (user_id: start_time)
        self.message_timestamps = {}  # Traccia i timestamp dei messaggi per il cooldown (user_id: timestamp)

        self.load_config()

    def load_config(self):
        """Carica le configurazioni dal file .env."""
        self.TOKEN = os.getenv("DISCORD_TOKEN")
        self.WEBHOOK_URL = os.getenv("WEBHOOK_URL")
        self.PRIMARY_COLOR = int(os.getenv("PRIMARY_COLOR", "2E8B57"), 16)
        self.KOFI_USERNAME = os.getenv("KOFI_USERNAME")
        self.REPORT_CHANNEL_ID = int(os.getenv("REPORT_CHANNEL_ID"))
        self.REPORT_EXCLUDE_CHANNEL_IDS = [int(cid) for cid in os.getenv("REPORT_EXCLUDE_CHANNEL_IDS", "").split(',') if cid]
        self.WELCOME_CHANNEL_ID = int(os.getenv("WELCOME_CHANNEL_ID"))
        self.UPDATES_CHANNEL_ID = int(os.getenv("UPDATES_CHANNEL_ID")) if os.getenv("UPDATES_CHANNEL_ID") else None
        self.AFK_CHANNEL_IDS = [int(cid) for cid in os.getenv("AFK_CHANNEL_IDS", "").split(',') if cid]
        self.AFK_MOVE_CHANNEL_ID = self.AFK_CHANNEL_IDS[0] if self.AFK_CHANNEL_IDS else None
        self.AFK_MOVE_TIMEOUT_MINUTES = int(os.getenv("AFK_MOVE_TIMEOUT_MINUTES", 30))
        self.AFK_EXCLUDED_USER_IDS = [int(uid) for uid in os.getenv("AFK_EXCLUDED_USER_IDS", "").split(',') if uid]
        self.AFK_EXEMPT_CHANNEL_IDS = [int(cid) for cid in os.getenv("AFK_EXEMPT_CHANNEL_IDS", "").split(',') if cid]
        self.BOT_TZ = pytz.timezone(os.getenv("ZONE", "UTC"))
        
        # Costanti per il sistema di XP
        self.XP_PER_MINUTE = int(os.getenv("XP_PER_MINUTE", 3))
        self.XP_PER_MESSAGE = int(os.getenv("XP_PER_MESSAGE", 2))
        self.XP_PER_REACTION = int(os.getenv("XP_PER_REACTION", 1))
        self.XP_FOR_REACTION_RECEIVED = int(os.getenv("XP_FOR_REACTION_RECEIVED", 2))
        self.BASE_XP_FOR_LEVEL_UP = int(os.getenv("BASE_XP_FOR_LEVEL_UP", 250))
        self.MESSAGE_COOLDOWN = int(os.getenv("MESSAGE_COOLDOWN", 30))
        
        # Ruoli-ricompensa per i livelli
        self.level_roles = {}
        level_roles_str = os.getenv("LEVEL_ROLES", "")
        if level_roles_str:
            try:
                # Converte la stringa "5:id1,15:id2" in un dizionario {5: id1, 15: id2}
                self.level_roles = {int(level): int(role_id) for level, role_id in (pair.split(':') for pair in level_roles_str.split(','))}
                logging.info(f"Caricati {len(self.level_roles)} ruoli-ricompensa.")
            except ValueError:
                self.level_roles = {}
                logging.error("Formato di LEVEL_ROLES non valido nel file .env. Esempio: '5:123,15:456'")


# --- INIZIALIZZAZIONE ---
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.reactions = True

bot = Botrino(command_prefix='!', intents=intents)
bot.remove_command('help')  # Rimuove il comando help di default per usare quello custom


# --- GESTIONE CICLO DI VITA ---
@bot.event
async def on_ready():
    """
    Eseguito quando il bot è pronto e connesso a Discord.
    """
    logging.info(f"Accesso effettuato come {bot.user}. Inizializzazione...")
    try:
        # Connessione al database
        bot.db, bot.cursor = await database.connect_to_db()
        
        # Task per mantenere attiva la connessione al DB
        asyncio.create_task(database.keep_db_alive(bot))
        
        # Caricamento di tutti i cogs (estensioni)
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                await bot.load_extension(f'cogs.{filename[:-3]}')
                logging.info(f"Caricato il cog: {filename}")
        
        # Ripristino delle sessioni vocali dopo il caricamento dei cogs
        activity_cog = bot.get_cog('ActivityEvents')
        if activity_cog:
            await activity_cog.resume_sessions()

        logging.info("Bot completamente inizializzato e pronto.")
    except Exception as e:
        logging.critical(f"Errore critico durante l'avvio: {e}", exc_info=True)
        await send_webhook(f"ERRORE CRITICO DURANTE L'AVVIO: {e}")

@bot.event
async def on_close():
    """
    Eseguito quando il bot si disconnette.
    """
    logging.info("Il bot si sta spegnendo...")
    activity_cog = bot.get_cog('ActivityEvents')
    if activity_cog:
        await activity_cog.save_all_voice_data()
    await database.close_db_connection(bot)
    logging.info("Spegnimento completato.")

@bot.event
async def on_error(event, *args, **kwargs):
    logging.error(f"Errore non gestito nell'evento '{event}'", exc_info=True)

@bot.event
async def on_command_error(ctx, error):
    """
    Gestore di errori globale per i comandi.
    """
    if isinstance(error, commands.CommandNotFound):
        return  # Ignora i comandi non trovati
    logging.error(f"Errore nel comando {ctx.command}: {error}", exc_info=True)
    await ctx.send("Si è verificato un errore durante l'esecuzione del comando.")

async def send_webhook(message):
    """
    Invia un messaggio a un webhook Discord, se configurato.
    """
    if not bot.WEBHOOK_URL:
        return
    async with aiohttp.ClientSession() as session:
        try:
            await session.post(bot.WEBHOOK_URL, json={"content": message})
        except Exception as e:
            logging.error(f"Eccezione durante l'invio del webhook: {e}")


# --- AVVIO ---
async def main():
    async with bot:
        await bot.start(bot.TOKEN)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except discord.errors.LoginFailure:
        logging.critical("Token non valido. Impossibile avviare il bot.")
    except Exception as e:
        logging.critical(f"Errore irreversibile: {e}", exc_info=True)