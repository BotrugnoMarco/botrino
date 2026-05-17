"""
Questo cog gestisce tutte le operazioni pianificate (tasks) del bot,
come i report giornalieri/settimanali, l'assegnazione periodica di XP
e il controllo degli utenti AFK.
"""
import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta, time
import logging
import queries
from utils.formatters import send_report_embed

def merge_intervals(intervals: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    """
    Unisce una lista di intervalli di tempo (start, end) sovrapposti o adiacenti.
    """
    if not intervals:
        return []
    
    intervals.sort(key=lambda x: x[0])  # Ordina per data di inizio
    
    merged = [intervals[0]]
    for current_start, current_end in intervals[1:]:
        last_start, last_end = merged[-1]
        
        if current_start <= last_end:  # Se c'è sovrapposizione
            merged[-1] = (last_start, max(last_end, current_end))  # Estende l'intervallo precedente
        else:
            merged.append((current_start, current_end))  # Aggiunge un nuovo intervallo
            
    return merged

async def generate_report(bot, channel: discord.TextChannel, title: str, start_date: datetime, end_date: datetime):
    """
    Logica principale per generare e inviare un report di attività vocale per un dato intervallo.
    """
    logging.info(f"Generazione del report '{title}' (Da: {start_date} A: {end_date})")
    try:
        bot.cursor.execute(queries.report_query, (end_date, start_date))
        session_rows = bot.cursor.fetchall()

        # Aggrega i dati per utente
        user_report = {}
        for row in session_rows:
            user_id = row['user_id']
            duration = row['duration_seconds'] or 0
            if user_id not in user_report:
                user_report[user_id] = {
                    'user_id': user_id, 'username': row['username'],
                    'nickname': row['nickname'], 'level': row['level'], 'total_secs': 0
                }
            user_report[user_id]['total_secs'] += duration

        # Aggrega e unisce gli intervalli di attività per canale
        channel_intervals = {}
        for row in session_rows:
            if not row['join_time'] or not row['leave_time']: continue
            
            # Salta i canali esclusi dal report
            if row['channel_id'] in bot.REPORT_EXCLUDE_CHANNEL_IDS:
                continue

            # Rende le date dal DB "aware" usando il fuso orario del bot
            join_time_aware = bot.BOT_TZ.localize(row['join_time'])
            leave_time_aware = bot.BOT_TZ.localize(row['leave_time'])

            channel_id = row['channel_id']
            if channel_id not in channel_intervals:
                channel_intervals[channel_id] = []
            
            # Assicura che gli intervalli siano all'interno della finestra del report
            interval_start = max(join_time_aware, start_date)
            interval_end = min(leave_time_aware, end_date)
            if interval_start < interval_end:
                channel_intervals[channel_id].append((interval_start, interval_end))

        channel_report = {}
        for channel_id, intervals in channel_intervals.items():
            merged = merge_intervals(intervals)
            total_seconds = sum((end - start).total_seconds() for start, end in merged)
            if total_seconds > 0:
                channel_report[channel_id] = {
                    'channel_id': channel_id,
                    'channel_name': next((r['channel_name'] for r in session_rows if r['channel_id'] == channel_id), str(channel_id)),
                    'total_activity_seconds': total_seconds
                }

        # Ordina i risultati
        user_rows = sorted(user_report.values(), key=lambda x: x['total_secs'], reverse=True)
        channel_rows = sorted(channel_report.values(), key=lambda x: x['total_activity_seconds'], reverse=True)

        await send_report_embed(
            channel, title, user_rows,
            channel_report_rows=channel_rows, color=bot.PRIMARY_COLOR,
            kofi_username=bot.KOFI_USERNAME
        )
    except Exception as e:
        logging.error(f"Errore durante la generazione del report '{title}': {e}", exc_info=True)


class ScheduledTasks(commands.Cog):
    """
    Cog per la gestione dei task pianificati.
    """
    def __init__(self, bot):
        self.bot = bot
        
        # Avvio dei task periodici
        self.xp_gain_task.start()
        self.check_afk_users.start()

        # Configurazione e avvio dei task ad orario fisso
        daily_report_time = time(9, 0, tzinfo=self.bot.BOT_TZ)
        self.daily_report.change_interval(time=daily_report_time)
        self.daily_report.start()

        weekly_report_time = time(10, 0, tzinfo=self.bot.BOT_TZ)
        self.weekly_report.change_interval(time=weekly_report_time)
        self.weekly_report.start()

    def cog_unload(self):
        """Funzione chiamata alla disattivazione del cog per fermare i task."""
        self.daily_report.cancel()
        self.weekly_report.cancel()
        self.xp_gain_task.cancel()
        self.check_afk_users.cancel()

    # --- Comandi di simulazione per debug ---
    @commands.command(name="sim_daily", hidden=True)
    @commands.is_owner()
    async def simulate_daily_report(self, ctx):
        """(Solo Owner) Simula l'esecuzione del report giornaliero."""
        await ctx.send("▶️ Simulazione del report giornaliero avviata...")
        await self.daily_report()
        await ctx.send("✅ Simulazione completata.")

    @commands.command(name="sim_weekly", hidden=True)
    @commands.is_owner()
    async def simulate_weekly_report(self, ctx):
        """(Solo Owner) Simula l'esecuzione del report settimanale."""
        await ctx.send("▶️ Simulazione del report settimanale avviata...")
        await self.weekly_report()
        await ctx.send("✅ Simulazione completata.")

    @simulate_daily_report.error
    @simulate_weekly_report.error
    async def on_simulation_error(self, ctx, error):
        if isinstance(error, commands.NotOwner):
            await ctx.send("❌ Questo comando può essere usato solo dal proprietario del bot.")
        else:
            await ctx.send(f"Si è verificato un errore: {error}")

    @tasks.loop(minutes=5)
    async def xp_gain_task(self):
        """
        Task periodico che assegna XP agli utenti attivi nei canali vocali.
        Viene eseguito ogni 5 minuti.
        """
        now = datetime.now(self.bot.BOT_TZ)
        activity_cog = self.bot.get_cog('ActivityEvents')
        if not activity_cog: return

        for user_id, session_data in self.bot.active_sessions.copy().items():
            if session_data.get('is_muted', False):
                continue

            try:
                duration_seconds = (now - session_data['last_update']).total_seconds()
                
                if duration_seconds >= 60:  # Assegna XP solo se è passato almeno un minuto
                    xp_to_add = self.bot.XP_PER_MINUTE * int(duration_seconds / 60)
                    
                    if xp_to_add > 0:
                        guild_id = session_data.get('guild_id')
                        if not guild_id:
                            logging.warning(f"guild_id non trovato per l'utente {user_id} in xp_gain_task.")
                            continue
                        
                        session_data['total_duration'] += duration_seconds
                        await activity_cog.update_xp_and_level(user_id, guild_id, xp_to_add)
                        session_data['last_update'] = now # Resetta il timer
            except Exception as e:
                logging.error(f"Errore nell'assegnazione XP a {user_id}: {e}")

    @tasks.loop()
    async def daily_report(self):
        """
        Task che invia un report giornaliero delle attività vocali.
        L'orario è configurato nell'__init__.
        """
        channel = self.bot.get_channel(self.bot.REPORT_CHANNEL_ID)
        if not channel:
            logging.error("Canale di report giornaliero non trovato.")
            return
        
        # Calcola l'intervallo delle ultime 24 ore
        end_date = datetime.now(self.bot.BOT_TZ)
        start_date = end_date - timedelta(days=1)
        
        await generate_report(self.bot, channel, "Report Ultime 24 Ore", start_date, end_date)

    @tasks.loop()
    async def weekly_report(self):
        """
        Invia un report settimanale ogni lunedì mattina.
        L'orario è configurato nell'__init__.
        """
        now_in_tz = datetime.now(self.bot.BOT_TZ)
        if now_in_tz.weekday() != 0:  # 0 = Lunedì
            return 

        channel = self.bot.get_channel(self.bot.REPORT_CHANNEL_ID)
        if not channel:
            logging.error("Canale di report settimanale non trovato.")
            return

        # Calcola le date della settimana passata (da Lunedì a Domenica)
        today = now_in_tz.date()
        start_of_last_week = today - timedelta(days=today.weekday() + 7)
        end_of_last_week = start_of_last_week + timedelta(days=7)
        
        # Converte le date in datetime
        start_date = datetime.combine(start_of_last_week, time.min, tzinfo=self.bot.BOT_TZ)
        end_date = datetime.combine(end_of_last_week, time.min, tzinfo=self.bot.BOT_TZ)

        await generate_report(self.bot, channel, "Report Settimanale", start_date, end_date)

    @tasks.loop(minutes=1.0)
    async def check_afk_users(self):
        """
        Controlla periodicamente gli utenti inattivi (mutati) e li sposta
        nel canale AFK se superano il timeout configurato.
        """
        if not self.bot.AFK_MOVE_CHANNEL_ID: return

        now = datetime.now(self.bot.BOT_TZ)
        afk_channel = self.bot.get_channel(self.bot.AFK_MOVE_CHANNEL_ID)
        if not afk_channel: return

        timeout_seconds = self.bot.AFK_MOVE_TIMEOUT_MINUTES * 60

        for user_id, session_data in self.bot.active_sessions.copy().items():
            if user_id in self.bot.AFK_EXCLUDED_USER_IDS:
                continue

            # Controlla solo utenti mutati che hanno un timestamp di inizio mute
            if not session_data.get('is_muted') or not session_data.get('mute_start_time'):
                continue

            duration_muted = (now - session_data['mute_start_time']).total_seconds()
            if duration_muted > timeout_seconds:
                member = afk_channel.guild.get_member(user_id)
                if member and member.voice and member.voice.channel.id != afk_channel.id:
                    # Salta i canali esenti dall'AFK
                    if member.voice.channel.id in self.bot.AFK_EXEMPT_CHANNEL_IDS:
                        continue
                    try:
                        reason = f"Inattività (mutato per >{self.bot.AFK_MOVE_TIMEOUT_MINUTES} min)."
                        await member.move_to(afk_channel, reason=reason)
                        logging.info(f"Spostato {member.name} nel canale AFK. Motivo: {reason}")
                    except Exception as e:
                        logging.error(f"Impossibile spostare l'utente {user_id}: {e}")

    @xp_gain_task.before_loop
    @check_afk_users.before_loop
    @daily_report.before_loop
    @weekly_report.before_loop
    async def before_tasks(self):
        """Attende che il bot sia pronto prima di avviare i task."""
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(ScheduledTasks(bot))