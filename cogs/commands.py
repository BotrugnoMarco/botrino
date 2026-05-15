"""
Questo cog contiene tutti i comandi che gli utenti possono eseguire direttamente.
"""
import discord
from discord.ext import commands
from datetime import datetime, timedelta
import logging
import queries
from utils.formatters import format_duration, format_leaderboard
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
            await generate_report(self.bot, ctx.channel, "Report Ultime 24 Ore", start_date, end_date)
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
            embed = discord.Embed(title="🏆 Classifica Generale - Top 10 (Tempo Vocale)", color=self.bot.PRIMARY_COLOR)
            embed.description = format_leaderboard(final_rows[:10], lambda row: f"Tempo totale: **{format_duration(row['total_secs'])}**")
            
            if self.bot.KOFI_USERNAME:
                embed.description += f"\n\n[☕ Supporta il bot](https://ko-fi.com/{self.bot.KOFI_USERNAME})"
            
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
                
                embed = discord.Embed(title=f"🏅 Livello di {target_user.display_name}", color=self.bot.PRIMARY_COLOR)
                embed.set_thumbnail(url=target_user.display_avatar.url)
                embed.add_field(name="Livello", value=f"**{lvl}**", inline=True)
                embed.add_field(name="XP", value=f"**{xp}/{xp_needed}**", inline=True)

                # Barra di progresso
                progress = min(xp / xp_needed, 1.0) if xp_needed > 0 else 1.0
                bar = "🟩" * int(progress * 20) + "⬜" * (20 - int(progress * 20))
                embed.add_field(name="Progresso", value=f"`{bar}`", inline=False)
                
                if self.bot.KOFI_USERNAME:
                    embed.add_field(name="Supporto", value=f"[☕ Offrimi un caffè](https://ko-fi.com/{self.bot.KOFI_USERNAME})", inline=False)

                await ctx.send(embed=embed)
            else:
                await ctx.send(f"L'utente {target_user.display_name} non ha ancora guadagnato XP.")
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
            
            embed = discord.Embed(title="🏆 Classifica Livelli del Server", description="I 10 utenti con più esperienza.", color=self.bot.PRIMARY_COLOR)
            embed.description = format_leaderboard(rows, lambda row: f"Livello: **{row['level']}** (XP: {row['xp']})")
            
            if self.bot.KOFI_USERNAME:
                embed.description += f"\n\n[☕ Supporta il bot](https://ko-fi.com/{self.bot.KOFI_USERNAME})"

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
            embed = discord.Embed(title="🏆 Hall of Fame - Record del Server", description="Ecco i record attuali da battere!", color=self.bot.PRIMARY_COLOR)
            
            # Record XP Giornaliero
            self.bot.cursor.execute(queries.get_record_daily_xp_query)
            xp_record = self.bot.cursor.fetchone()
            max_xp = xp_record['max_daily_xp'] if xp_record and xp_record['max_daily_xp'] is not None else 0
            
            if max_xp > 0:
                holder = xp_record['nickname'] or xp_record['username']
                embed.add_field(name="⚡ Max XP in un giorno", value=f"**{max_xp} XP**\nDetenuto da: **{holder}**", inline=True)
            else:
                embed.add_field(name="⚡ Max XP in un giorno", value="Nessun record stabilito.", inline=True)

            # Record Sessione Vocale
            self.bot.cursor.execute(queries.get_record_voice_duration_query)
            voice_record = self.bot.cursor.fetchone()
            max_duration = voice_record['duration_seconds'] if voice_record and voice_record['duration_seconds'] is not None else 0
            
            if max_duration > 0:
                holder = voice_record['nickname'] or voice_record['username']
                duration_str = format_duration(max_duration)
                embed.add_field(name="⏳ Sessione Vocale più lunga", value=f"**{duration_str}**\nDetenuto da: **{holder}**", inline=True)
            else:
                embed.add_field(name="⏳ Sessione Vocale più lunga", value="Nessun record stabilito.", inline=True)

            if self.bot.KOFI_USERNAME:
                embed.add_field(name="Supporto", value=f"[☕ Offrimi un caffè](https://ko-fi.com/{self.bot.KOFI_USERNAME})", inline=False)

            await ctx.send(embed=embed)

        except Exception as e:
            logging.error(f"Errore nel comando records: {e}", exc_info=True)
            await ctx.send("Si è verificato un errore durante il recupero dei record.")

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
                records_held.append(f"⚡ **Max XP Giornaliero** ({xp_record['max_daily_xp']} XP)")

            # Record Sessione Vocale
            self.bot.cursor.execute(queries.get_record_voice_duration_query)
            voice_record = self.bot.cursor.fetchone()
            if voice_record and voice_record['id'] == target_user.id and voice_record['duration_seconds'] > 0:
                duration_str = format_duration(voice_record['duration_seconds'])
                records_held.append(f"⏳ **Sessione più lunga** ({duration_str})")

            # Calcoli per la barra XP
            xp, lvl = user_stats['xp'], user_stats['level']
            xp_needed = calculate_xp_for_level_up(lvl, self.bot.BASE_XP_FOR_LEVEL_UP)
            progress = min(xp / xp_needed, 1.0) if xp_needed > 0 else 1.0
            bar = "🟩" * int(progress * 10) + "⬜" * (10 - int(progress * 10))

            # Formattazione dati
            voice_time = format_duration(user_stats['voice_seconds'])
            night_time = format_duration(user_stats['night_voice_seconds'])
            badges_str = " ".join([f"{b['icon']} **{b['name']}**" for b in user_badges]) if user_badges else "Nessun badge guadagnato."

            embed = discord.Embed(title=f"👤 Profilo di {target_user.display_name}", color=self.bot.PRIMARY_COLOR)
            embed.set_thumbnail(url=target_user.display_avatar.url)
            
            # Sezione Livello
            embed.add_field(name="🏆 Livello & XP", value=f"Livello: **{lvl}**\nXP: **{xp}/{xp_needed}**\n`{bar}`", inline=False)
            
            # Sezione Statistiche Generali
            stats_desc = (
                f"💬 Messaggi: **{user_stats['message_count']}**\n"
                f"✨ Reazioni: **{user_stats['reaction_count']}**\n"
                f"🎙️ Tempo in Vocale: **{voice_time}**"
            )
            embed.add_field(name="📊 Statistiche Attività", value=stats_desc, inline=True)

            # Sezione Statistiche Avanzate
            adv_stats_desc = (
                f"🔥 Streak Attuale: **{user_stats['activity_streak']} giorni**\n"
                f"⚡ Record XP Giornaliero: **{user_stats['max_daily_xp']}**\n"
                f"🦉 Tempo Notturno: **{night_time}**"
            )
            embed.add_field(name="📈 Statistiche Avanzate", value=adv_stats_desc, inline=True)

            # Sezione Record
            if records_held:
                embed.add_field(name="🏆 Record Detenuti", value="\n".join(records_held), inline=False)

            # Sezione Badge
            embed.add_field(name="🏅 Badge", value=badges_str, inline=False)
            
            if self.bot.KOFI_USERNAME:
                embed.add_field(name="Supporto", value=f"[☕ Offrimi un caffè](https://ko-fi.com/{self.bot.KOFI_USERNAME})", inline=False)
            
            embed.set_footer(text=f"ID Utente: {target_user.id} • Membro dal: {target_user.joined_at.strftime('%d/%m/%Y')}")

            await ctx.send(embed=embed)

        except Exception as e:
            logging.error(f"Errore nel comando profile: {e}", exc_info=True)
            await ctx.send("Si è verificato un errore durante il recupero del profilo.")

    @commands.command(name='help_botrino', help="Mostra la lista dei comandi disponibili.")
    async def help_botrino(self, ctx):
        """
        Mostra un messaggio di aiuto con la lista di tutti i comandi disponibili.
        """
        embed = discord.Embed(title="🤖 Comandi disponibili — Botrino", description="Ecco la lista completa dei comandi che puoi usare:", color=self.bot.PRIMARY_COLOR)
        embed.add_field(name="`!report`", value="Mostra il report delle attività di oggi.", inline=False)
        embed.add_field(name="`!profile [utente]`", value="Visualizza il profilo completo con statistiche e badge.", inline=False)
        embed.add_field(name="`!leaderboard`", value="Visualizza la classifica del tempo trascorso in vocale.", inline=False)
        embed.add_field(name="`!level [utente]`", value="Mostra il livello e l'XP di un utente (o i tuoi).", inline=False)
        embed.add_field(name="`!level_leaderboard`", value="Mostra la classifica dei livelli.", inline=False)
        embed.add_field(name="`!donate`", value="Mostra il link per supportare lo sviluppo del bot.", inline=False)
        embed.add_field(name="`!help_botrino`", value="Mostra questo messaggio di aiuto.", inline=False)
        
        if self.bot.KOFI_USERNAME:
            embed.add_field(name="Supporto", value=f"[☕ Offrimi un caffè](https://ko-fi.com/{self.bot.KOFI_USERNAME})", inline=False)
        
        embed.set_footer(text="Botrino — il tuo assistente del Drunken’s Server 🍻", icon_url=self.bot.user.display_avatar.url)
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
            title="☕ Supporta lo Sviluppo!",
            description=f"Se apprezzi il mio lavoro e vuoi supportare lo sviluppo del bot, puoi offrirmi un caffè su Ko-fi!\n\n"
                        f"Ogni contributo è molto apprezzato e mi aiuta a mantenere il bot attivo e aggiornato.\n\n"
                        f"➡️ [**Dona su Ko-fi**](https://ko-fi.com/{kofi_username})",
            color=self.bot.PRIMARY_COLOR
        )
        embed.set_thumbnail(url="https://storage.ko-fi.com/cdn/cup-border.png")
        embed.set_footer(text="Grazie di cuore per il tuo supporto!")
        
        await ctx.send(embed=embed)

    @commands.command(name='announce_updates', hidden=True)
    @commands.has_permissions(administrator=True)
    async def announce_updates(self, ctx):
        """
        Invia un messaggio di annuncio con gli ultimi aggiornamenti nel canale configurato.
        """
        if not self.bot.UPDATES_CHANNEL_ID:
            await ctx.send("❌ Canale aggiornamenti non configurato. Aggiungi `UPDATES_CHANNEL_ID` al file .env.")
            return

        channel = self.bot.get_channel(self.bot.UPDATES_CHANNEL_ID)
        if not channel:
            await ctx.send("❌ Canale aggiornamenti non trovato.")
            return

        embed = discord.Embed(
            title="🚀 Aggiornamento Bot v2.0 - Badge, Profili e Streaming!",
            description="Siamo lieti di annunciare un grande aggiornamento per il bot! Ecco le novità:",
            color=self.bot.PRIMARY_COLOR
        )

        # Nuovi Comandi
        embed.add_field(
            name="🆕 Nuovi Comandi",
            value=(
                "**`!profile`**: Visualizza la tua scheda personale con livello, XP e badge.\n"
                "**`!records`**: Scopri i record attuali del server da battere (XP e Vocale)!"
            ),
            inline=False
        )

        # Lista Completa Badge
        embed.add_field(
            name="🏅 Lista Completa Badge",
            value=(
                "Ecco tutti i badge che puoi sbloccare:\n\n"
                "💬 **Chiacchierone**: Invia 100 messaggi.\n"
                "🎙️ **Veterano Vocale**: 50 ore in vocale.\n"
                "🦉 **Notturno**: 10 ore in vocale di notte (01-05).\n"
                "✨ **Re delle Reazioni**: Dai 50 reazioni.\n"
                "🏆 **Maestro di Livello**: Raggiungi il livello 25.\n"
                "🚀 **Pioniere**: Primi 10 utenti del bot.\n"
                "☕ **Sostenitore**: Effettua una donazione.\n"
                "⏳ **Maratoneta Vocale**: Record sessione più lunga.\n"
                "⚡ **Super Sayan**: Record XP giornaliero.\n"
                "🔥 **Instancabile**: Striscia attività di 7 giorni.\n"
                "💎 **Veterano**: Nel server da 1 anno.\n"
                "📹 **Faccia a Faccia**: 5 ore di webcam.\n"
                "🎥 **Regista**: 10 ore di streaming."
            ),
            inline=False
        )

        # Miglioramenti Tecnici
        embed.add_field(
            name="🛠️ Miglioramenti e Fix",
            value=(
                "• **Tracking Video & Stream**: Ora il bot traccia il tempo passato in video e streaming.\n"
                "• **Fix Sessioni**: Risolti problemi con il cambio canale e il reset delle strisce giornaliere.\n"
                "• **Link Supporto**: Aggiunto link Ko-fi per chi vuole supportare il progetto."
            ),
            inline=False
        )

        # Footer con link donazione
        if self.bot.KOFI_USERNAME:
            embed.add_field(
                name="☕ Supportaci",
                value=f"[Offrimi un caffè su Ko-fi](https://ko-fi.com/{self.bot.KOFI_USERNAME})",
                inline=False
            )

        embed.set_footer(text="Grazie per far parte della nostra community!")
        embed.timestamp = datetime.now(self.bot.BOT_TZ)

        try:
            await channel.send(embed=embed)
            await ctx.send(f"✅ Annuncio inviato con successo nel canale {channel.mention}.")
        except Exception as e:
            await ctx.send(f"❌ Errore durante l'invio dell'annuncio: {e}")

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