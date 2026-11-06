"""
Questo cog contiene tutti i comandi che gli utenti possono eseguire direttamente.
"""
import discord
from discord.ext import commands
from datetime import datetime, timedelta
import logging
import queries
import theme
from utils.formatters import format_duration, format_leaderboard, build_records_embed, get_effective_streak
from cogs.tasks import generate_report
from utils.xp_utils import calculate_xp_for_level_up


class UserCommands(commands.Cog):
    """
    Cog per i comandi utente.
    """
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='report', help="Mostra il report delle ultime 24 ore.")
    async def report(self, ctx):
        """
        Genera e invia il report delle attività delle ultime 24 ore nel canale corrente.
        """
        try:
            end_date = datetime.now(self.bot.BOT_TZ)
            start_date = end_date - timedelta(days=1)
            await generate_report(self.bot, ctx.channel, theme.REPORT_DAILY_TITLE, start_date, end_date)
        except Exception as e:
            logging.error(f"Errore nel comando report: {e}", exc_info=True)
            await ctx.send("Si è verificato un errore durante la generazione del report.")

    @commands.command(name='leaderboard', help="Visualizza la classifica generale del tempo totale.")
    async def leaderboard(self, ctx):
        """
        Mostra la classifica dei 10 utenti con più tempo trascorso nei canali vocali.
        I dati sono in tempo reale, includendo le sessioni attive.
        """
        try:
            now = datetime.now(self.bot.BOT_TZ)
            
            # Recupera i dati storici dal DB e converte i Decimal in float
            self.bot.cursor.execute(queries.leaderboard_query)
            rows = self.bot.cursor.fetchall()
            leaderboard_data = {row['user_id']: row for row in rows}
            for user_id in leaderboard_data:
                leaderboard_data[user_id]['total_secs'] = float(leaderboard_data[user_id]['total_secs'])

            # Aggiunge il tempo delle sessioni vocali attualmente attive
            for user_id, session_data in self.bot.active_sessions.items():
                if not session_data.get('is_muted', False):
                    current_duration = (now - session_data['last_update']).total_seconds()
                    total_duration = session_data['total_duration'] + current_duration
                    
                    if user_id in leaderboard_data:
                        leaderboard_data[user_id]['total_secs'] += total_duration
                    else:
                        # Se un utente è in vocale ma non ha dati storici, lo aggiungiamo
                        member = ctx.guild.get_member(user_id)
                        if member:
                            leaderboard_data[user_id] = {
                                'user_id': user_id, 
                                'username': member.name, 
                                'nickname': member.nick, 
                                'level': 1, # Livello di default
                                'total_secs': total_duration
                            }
            
            # Ordina i dati finali e formatta l'embed
            final_rows = sorted(leaderboard_data.values(), key=lambda x: x['total_secs'], reverse=True)
            embed = discord.Embed(title=theme.LEADERBOARD_VOICE_TITLE, color=self.bot.PRIMARY_COLOR)
            embed.description = format_leaderboard(final_rows[:10], lambda row: f"Tempo totale: **{format_duration(row['total_secs'])}**")
            
            if self.bot.KOFI_USERNAME:
                embed.description += f"\n\n{theme.kofi_link(self.bot.KOFI_USERNAME)}"
            embed.set_footer(text=theme.FOOTER)

            await ctx.send(embed=embed)
        except Exception as e:
            logging.error(f"Errore nel comando leaderboard: {e}", exc_info=True)
            await ctx.send("Si è verificato un errore durante la visualizzazione della classifica.")

    @commands.command(name='level', help="Mostra il livello e l'XP di un utente.")
    async def level(self, ctx, member: discord.Member = None):
        """
        Mostra il livello, l'XP e la barra di progresso per l'utente specificato (o se stesso).
        """
        target_user = member or ctx.author
        try:
            self.bot.cursor.execute(queries.get_user_xp_query, (target_user.id,))
            user_data = self.bot.cursor.fetchone()
            
            if user_data:
                xp, lvl = user_data['xp'], user_data['level']
                xp_needed = calculate_xp_for_level_up(lvl, self.bot.BASE_XP_FOR_LEVEL_UP)
                
                embed = discord.Embed(title=theme.LEVEL_TITLE.format(name=target_user.display_name), color=self.bot.PRIMARY_COLOR)
                embed.set_thumbnail(url=target_user.display_avatar.url)
                embed.add_field(name="Livello", value=f"**{lvl}**", inline=True)
                embed.add_field(name="XP", value=f"**{xp}/{xp_needed}**", inline=True)

                # Barra di progresso
                progress = min(xp / xp_needed, 1.0) if xp_needed > 0 else 1.0
                bar = theme.progress_bar(progress, 12)
                embed.add_field(name="Progresso", value=bar, inline=False)
                
                if self.bot.KOFI_USERNAME:
                    embed.add_field(name=theme.KOFI_FIELD_NAME, value=theme.kofi_link(self.bot.KOFI_USERNAME), inline=False)
                embed.set_footer(text=theme.FOOTER)

                await ctx.send(embed=embed)
            else:
                await ctx.send(f"{target_user.display_name} non ha ancora guadagnato XP al Thermopolium.")
        except Exception as e:
            logging.error(f"Errore nel comando level: {e}", exc_info=True)
            await ctx.send("Si è verificato un errore.")

    @commands.command(name='level_leaderboard', help="Mostra la classifica dei livelli.")
    async def level_leaderboard(self, ctx):
        """
        Mostra la classifica dei 10 utenti con il livello più alto nel server.
        """
        try:
            self.bot.cursor.execute(queries.level_leaderboard_query)
            rows = self.bot.cursor.fetchall()
            
            embed = discord.Embed(title=theme.LEADERBOARD_LEVEL_TITLE, color=theme.COLOR_GOLD)
            embed.description = format_leaderboard(rows, lambda row: f"Livello: **{row['level']}** (XP: {row['xp']})")
            
            if self.bot.KOFI_USERNAME:
                embed.description += f"\n\n{theme.kofi_link(self.bot.KOFI_USERNAME)}"
            embed.set_footer(text=theme.FOOTER)

            await ctx.send(embed=embed)
        except Exception as e:
            logging.error(f"Errore nel comando level_leaderboard: {e}", exc_info=True)
            await ctx.send("Si è verificato un errore.")

    @commands.command(name='records', help="Mostra i record attuali del server.")
    async def records(self, ctx):
        """
        Mostra i record attuali del server da battere (XP giornaliero, Sessione più lunga, ecc.).
        """
        try:
            embed = build_records_embed(self.bot)
            await ctx.send(embed=embed)
        except Exception as e:
            logging.error(f"Errore nel comando records: {e}", exc_info=True)
            await ctx.send("Si è verificato un errore durante il recupero dei record.")

    @commands.command(name='annuncio_thermopolium', help="(Admin) Pubblica l'annuncio dell'apertura del Thermopolium.")
    @commands.has_permissions(administrator=True)
    async def annuncio_thermopolium(self, ctx, channel: discord.TextChannel = None):
        """
        Fa pubblicare al bot l'annuncio della nuova identità del server.
        Senza argomenti lo invia nel canale corrente; opzionalmente in un canale indicato.
        """
        target = channel or ctx.channel
        try:
            embed = discord.Embed(
                title="🍷 Salve a tutti: il Thermopolium apre i battenti!",
                description=(
                    "Il vecchio pub ha chiuso e al suo posto c'è un bancone di Pompei. "
                    "Stessa compagnia, stesse sere fino a tardi, un'insegna nuova. "
                    "Io sono Botrino, l'Automa costruito dall'Oste per servire al bancone: "
                    "vi verso una calda e vi racconto cosa è cambiato."
                ),
                color=self.bot.PRIMARY_COLOR
            )
            embed.add_field(
                name="🏛️ I gradi",
                value=(
                    " → ".join(theme.RANKS) + "\n"
                    "Si sale parlando, stando in vocale e reagendo ai messaggi. "
                    "Chi aveva già un grado lo conserva: è cambiato solo il nome."
                ),
                inline=False
            )
            embed.add_field(
                name="🏅 I traguardi",
                value=(
                    "I badge hanno nomi nuovi, dalla 💬 **Voce del Foro** al 🔥 **Fuoco di Vesta**, "
                    "ma quelli che avete già guadagnato restano vostri. Li trovate con `!badges` e nel `!profile`."
                ),
                inline=False
            )
            embed.add_field(
                name="🏺 Le sale",
                value=(
                    "🛋️ il **Triclinio** per stare insieme, 🎲 i **Tavoli** dei Dadi e delle Tessere per giocare, "
                    "📚 la **Biblioteca** per studiare e 🏟️ il **Colosseo** per guardare le partite insieme."
                ),
                inline=False
            )
            embed.add_field(
                name="📜 Il registro",
                value=(
                    "Ogni mattina pubblico l'**Acta Diurna** con le ultime 24 ore e ogni lunedì il registro della settimana. "
                    "I primati migliori finiscono sull'**Albo d'Onore**: `!records`."
                ),
                inline=False
            )

            if self.bot.KOFI_USERNAME:
                embed.add_field(name=theme.KOFI_FIELD_NAME, value=theme.kofi_link(self.bot.KOFI_USERNAME), inline=False)

            embed.set_footer(text=f"L'Oste e {theme.BOT_TITLE}")
            embed.timestamp = discord.utils.utcnow()

            await target.send(embed=embed)
            if target.id != ctx.channel.id:
                await ctx.send(f"✅ Annuncio pubblicato in {target.mention}.")
        except discord.Forbidden:
            await ctx.send(f"❌ Non ho i permessi per scrivere in {target.mention}.")
        except Exception as e:
            logging.error(f"Errore nel comando annuncio_thermopolium: {e}", exc_info=True)
            await ctx.send("Si è verificato un errore durante la pubblicazione dell'annuncio.")

    @commands.command(name='profile', help="Mostra il profilo completo di un utente.")
    async def profile(self, ctx, member: discord.Member = None):
        """
        Mostra un profilo dettagliato dell'utente, incluse statistiche, livello e badge.
        """
        target_user = member or ctx.author
        try:
            # Recupera statistiche utente
            self.bot.cursor.execute(queries.get_user_xp_query, (target_user.id,))
            user_stats = self.bot.cursor.fetchone()

            if not user_stats:
                await ctx.send(f"Nessun dato trovato per {target_user.display_name}.")
                return

            # Recupera badge utente
            self.bot.cursor.execute(queries.get_user_badges_query, (target_user.id,))
            user_badges = self.bot.cursor.fetchall()

            # Controlla se l'utente detiene dei record
            records_held = []
            
            # Record XP Giornaliero
            self.bot.cursor.execute(queries.get_record_daily_xp_query)
            xp_record = self.bot.cursor.fetchone()
            if xp_record and xp_record['id'] == target_user.id and xp_record['max_daily_xp'] > 0:
                records_held.append(f"{theme.RECORD_DAILY_XP}: **{xp_record['max_daily_xp']} XP** in un giorno")

            # Record Sessione Vocale
            self.bot.cursor.execute(queries.get_record_voice_duration_query)
            voice_record = self.bot.cursor.fetchone()
            if voice_record and voice_record['id'] == target_user.id and voice_record['duration_seconds'] > 0:
                duration_str = format_duration(voice_record['duration_seconds'])
                records_held.append(f"{theme.RECORD_LONGEST_SESSION}: sessione di **{duration_str}**")

            # Calcoli per la barra XP
            xp, lvl = user_stats['xp'], user_stats['level']
            xp_needed = calculate_xp_for_level_up(lvl, self.bot.BASE_XP_FOR_LEVEL_UP)
            progress = min(xp / xp_needed, 1.0) if xp_needed > 0 else 1.0
            bar = theme.progress_bar(progress, 10)

            # Formattazione dati
            voice_time = format_duration(user_stats['voice_seconds'])
            night_time = format_duration(user_stats['night_voice_seconds'])
            badges_str = " ".join([f"{b['icon']} **{b['name']}**" for b in user_badges]) if user_badges else theme.NO_BADGES

            embed = discord.Embed(title=theme.PROFILE_TITLE.format(name=target_user.display_name), color=self.bot.PRIMARY_COLOR)
            embed.set_thumbnail(url=target_user.display_avatar.url)
            
            # Sezione Livello
            embed.add_field(name="🏛️ Livello e XP", value=f"Livello: **{lvl}**\nXP: **{xp}/{xp_needed}**\n{bar}", inline=False)
            
            # Sezione Statistiche Generali
            stats_desc = (
                f"💬 Messaggi: **{user_stats['message_count']}**\n"
                f"✨ Reazioni: **{user_stats['reaction_count']}**\n"
                f"🛋️ Tempo in vocale: **{voice_time}**"
            )
            embed.add_field(name="📊 Attività", value=stats_desc, inline=True)

            # Sezione Statistiche Avanzate
            # Streak "effettiva": il valore memorizzato si aggiorna solo con l'attività,
            # quindi va corretto a schermo se la striscia è ormai interrotta.
            today = datetime.now(self.bot.BOT_TZ).date()
            current_streak = get_effective_streak(
                user_stats['activity_streak'], user_stats['last_activity_date'], today
            )
            adv_stats_desc = (
                f"🔥 Giorni di fila: **{current_streak}**\n"
                f"⚡ Miglior giornata: **{user_stats['max_daily_xp']} XP**\n"
                f"🦉 Tempo notturno: **{night_time}**"
            )
            embed.add_field(name="📈 Imprese", value=adv_stats_desc, inline=True)

            # Sezione Record
            if records_held:
                embed.add_field(name="🏆 Sull'Albo d'Onore", value="\n".join(records_held), inline=False)

            # Sezione Badge
            embed.add_field(name="🏅 Traguardi", value=badges_str, inline=False)
            
            if self.bot.KOFI_USERNAME:
                embed.add_field(name=theme.KOFI_FIELD_NAME, value=theme.kofi_link(self.bot.KOFI_USERNAME), inline=False)

            embed.set_footer(text=theme.PROFILE_JOINED.format(date=target_user.joined_at.strftime('%d/%m/%Y')))

            await ctx.send(embed=embed)

        except Exception as e:
            logging.error(f"Errore nel comando profile: {e}", exc_info=True)
            await ctx.send("Si è verificato un errore durante il recupero del profilo.")

    @commands.command(name='help_botrino', help="Mostra la lista dei comandi disponibili.")
    async def help_botrino(self, ctx):
        """
        Mostra un messaggio di aiuto con la lista di tutti i comandi disponibili.
        """
        embed = discord.Embed(title=theme.HELP_TITLE, description=theme.HELP_TEXT, color=self.bot.PRIMARY_COLOR)
        embed.add_field(name="`!profile [utente]`", value="La tavoletta con livello, imprese e traguardi.", inline=False)
        embed.add_field(name="`!level [utente]`", value="Livello e XP, con la barra di avanzamento.", inline=False)
        embed.add_field(name="`!badges [utente]`", value="I traguardi incisi sulla parete.", inline=False)
        embed.add_field(name="`!records`", value="L'Albo d'Onore con i primati del Thermopolium.", inline=False)
        embed.add_field(name="`!leaderboard`", value="I più assidui: classifica del tempo in vocale.", inline=False)
        embed.add_field(name="`!level_leaderboard`", value="Le stelle del Thermopolium: classifica dei livelli.", inline=False)
        embed.add_field(name="`!report`", value="L'Acta Diurna: l'attività vocale delle ultime 24 ore.", inline=False)
        embed.add_field(name="`!donate`", value="Offri una calda all'Automa.", inline=False)
        embed.add_field(name="`!help_botrino`", value="Questo elenco.", inline=False)

        embed.set_footer(text=theme.FOOTER, icon_url=self.bot.user.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.command(name='donate', help='Mostra il link per supportare il bot.')
    async def donate(self, ctx):
        """
        Mostra un embed con il link per effettuare una donazione su Ko-fi.
        """
        kofi_username = self.bot.KOFI_USERNAME

        if not kofi_username:
            await ctx.send("Il link per la donazione non è stato configurato. Contatta un amministratore.")
            return

        embed = discord.Embed(
            title=theme.DONATE_TITLE,
            description=f"{theme.DONATE_TEXT}\n\n➡️ [**Dona su Ko-fi**]({theme.kofi_url(kofi_username)})",
            color=theme.COLOR_GOLD
        )
        embed.set_thumbnail(url="https://storage.ko-fi.com/cdn/cup-border.png")
        embed.set_footer(text=theme.DONATE_FOOTER)

        await ctx.send(embed=embed)

    @commands.command(name='say', help="Fa inviare un messaggio al bot in un canale specifico.")
    @commands.has_permissions(administrator=True)
    async def say(self, ctx, channel: discord.TextChannel, *, message: str):
        """
        Fa inviare un messaggio al bot nel canale specificato.
        """
        try:
            await channel.send(message)
            await ctx.send(f"Messaggio inviato in {channel.mention}")
        except Exception as e:
            logging.error(f"Errore nel comando say: {e}", exc_info=True)
            await ctx.send("Si è verificato un errore durante l'invio del messaggio.")


async def setup(bot):
    await bot.add_cog(UserCommands(bot))