"""
Questo cog gestisce tutti gli eventi legati all'attività degli utenti,
come la connessione ai canali vocali, l'invio di messaggi e le reazioni.
È il cuore della logica di tracciamento dell'XP e dei livelli.
"""
import discord
from discord.ext import commands
from datetime import datetime, timedelta, time
import logging
import queries
from utils.xp_utils import calculate_xp_for_level_up


class ActivityEvents(commands.Cog):
    """
    Cog per la gestione degli eventi di attività degli utenti.
    """
    def __init__(self, bot):
        self.bot = bot

    def calculate_voice_xp(self, duration_seconds: int) -> int:
        """
        Calcola l'XP guadagnato in base alla durata in un canale vocale.
        """
        if duration_seconds <= 0:
            return 0
        return int((duration_seconds / 60) * self.bot.XP_PER_MINUTE)

    def calculate_night_duration(self, start_time: datetime, end_time: datetime) -> int:
        """
        Calcola quanti secondi dell'intervallo [start_time, end_time] ricadono
        nella fascia oraria notturna (01:00 - 05:00).
        """
        total_night_seconds = 0
        current = start_time
        
        # Itera giorno per giorno se l'intervallo attraversa la mezzanotte
        while current < end_time:
            # Definisci l'inizio e la fine della notte per il giorno corrente
            night_start = current.replace(hour=1, minute=0, second=0, microsecond=0)
            night_end = current.replace(hour=5, minute=0, second=0, microsecond=0)
            
            # Se siamo già oltre le 05:00, passiamo alla notte del giorno dopo
            if current >= night_end:
                next_day = current.date() + timedelta(days=1)
                current = datetime.combine(next_day, time(0, 0), tzinfo=current.tzinfo)
                continue

            # Calcola l'intersezione
            overlap_start = max(current, night_start)
            overlap_end = min(end_time, night_end)
            
            if overlap_start < overlap_end:
                total_night_seconds += (overlap_end - overlap_start).total_seconds()
            
            # Avanza al prossimo giorno o alla fine dell'intervallo
            if end_time > night_end:
                 # Passa al giorno successivo
                next_day = current.date() + timedelta(days=1)
                current = datetime.combine(next_day, time(0, 0), tzinfo=current.tzinfo)
            else:
                break
                
        return int(total_night_seconds)

    async def update_xp_and_level(self, user_id: int, guild_id: int, xp_to_add: int):
        """
        Aggiorna l'XP di un utente, gestisce i passaggi di livello e assegna i ruoli-ricompensa.
        Gestisce anche l'XP giornaliero per il badge Super Sayan.
        """
        if xp_to_add <= 0:
            return
            
        try:
            self.bot.cursor.execute(queries.get_user_xp_query, (user_id,))
            result = self.bot.cursor.fetchone()

            if not result:
                # L'utente potrebbe non essere ancora nel DB, ad esempio se il primo evento è una reazione.
                # In questo caso, lo ignoriamo; verrà aggiunto da on_member_join o on_voice_state_update.
                return

            current_xp, current_level = int(result['xp']), int(result['level'])
            
            # Gestione XP Giornaliero
            today = datetime.now(self.bot.BOT_TZ).date()
            last_date = result['last_activity_date']
            current_daily_xp = result['daily_xp']
            max_daily_xp = result['max_daily_xp']

            if last_date != today:
                current_daily_xp = xp_to_add
            else:
                current_daily_xp += xp_to_add
            
            if current_daily_xp > max_daily_xp:
                max_daily_xp = current_daily_xp
                # Controllo Badge 9: Super Sayan (Record XP giornaliero)
                # Recupera il record attuale del server
                self.bot.cursor.execute(queries.get_server_max_daily_xp_query)
                server_max_result = self.bot.cursor.fetchone()
                server_max_xp = server_max_result['max_xp'] if server_max_result and server_max_result['max_xp'] is not None else 0
                
                # Se il nuovo max_daily_xp dell'utente supera o eguaglia il record del server, assegna il badge
                if max_daily_xp >= server_max_xp and max_daily_xp > 0:
                    badges_cog = self.bot.get_cog('Badges')
                    if badges_cog:
                        await badges_cog._check_and_award_badge(user_id, 9)
            
            self.bot.cursor.execute(queries.update_daily_xp_query, (current_daily_xp, max_daily_xp, user_id))

            # Gestione XP Totale e Livello
            new_xp = current_xp + xp_to_add
            xp_for_next_level = calculate_xp_for_level_up(current_level, self.bot.BASE_XP_FOR_LEVEL_UP)
            
            level_up = False
            # Ciclo per gestire più level-up in una sola volta
            while new_xp >= xp_for_next_level:
                new_xp -= xp_for_next_level
                current_level += 1
                level_up = True
                xp_for_next_level = calculate_xp_for_level_up(current_level, self.bot.BASE_XP_FOR_LEVEL_UP)

            self.bot.cursor.execute(queries.update_user_xp_level_query, (new_xp, current_level, user_id))
            self.bot.db.commit()
            logging.info(f"Utente {user_id}: +{xp_to_add} XP -> Totale: {new_xp}, Livello: {current_level}")

            if level_up:
                guild = self.bot.get_guild(guild_id)
                if guild:
                    try:
                        # Usa fetch_member per assicurarsi di avere i ruoli aggiornati (bypass cache)
                        member = await guild.fetch_member(user_id)
                    except discord.NotFound:
                        member = None

                    if member:
                        await self._assign_level_role(member, current_level)
                        
                        channel = self.bot.get_channel(self.bot.REPORT_CHANNEL_ID)
                        if channel:
                            await channel.send(f"🎉 Congratulazioni {member.mention}, sei salito al livello **{current_level}**!")
                else:
                    logging.warning(f"Impossibile trovare il server (guild) per l'utente {user_id} durante il level up.")

        except Exception as e:
            logging.error(f"Errore durante l'aggiornamento XP per {user_id}: {e}")
            self.bot.db.rollback()

    async def _assign_level_role(self, member: discord.Member, new_level: int):
        """
        Assegna a un membro il ruolo-ricompensa più alto che gli spetta in base al livello.
        Rimuove eventuali ruoli di livello inferiore.
        """
        if not self.bot.level_roles:
            return

        # Trova il ruolo più alto che l'utente dovrebbe avere
        highest_role_id_to_assign = 0
        for level_req, role_id in sorted(self.bot.level_roles.items(), reverse=True):
            if new_level >= level_req:
                highest_role_id_to_assign = role_id
                break
        
        if not highest_role_id_to_assign:
            return

        # Rimuove i ruoli di livello obsoleti
        role_ids_to_remove = [
            role.id for role in member.roles 
            if role.id in self.bot.level_roles.values() and role.id != highest_role_id_to_assign
        ]
        
        if role_ids_to_remove:
            roles_to_remove_obj = [member.guild.get_role(rid) for rid in role_ids_to_remove]
            valid_roles_to_remove = [r for r in roles_to_remove_obj if r]
            if valid_roles_to_remove:
                await member.remove_roles(*valid_roles_to_remove, reason="Aggiornamento ruolo di livello")
                logging.info(f"Rimossi ruoli obsoleti {[r.name for r in valid_roles_to_remove]} a {member.display_name}.")

        # Assegna il nuovo ruolo se l'utente non lo ha già
        new_role_obj = member.guild.get_role(highest_role_id_to_assign)
        if new_role_obj and new_role_obj not in member.roles:
            await member.add_roles(new_role_obj, reason=f"Raggiunto il livello {new_level}")
            logging.info(f"Assegnato il ruolo '{new_role_obj.name}' a {member.display_name}.")

    async def save_all_voice_data(self):
        """
        Salva i dati di tutte le sessioni vocali attive nel database.
        Chiamata durante lo spegnimento del bot per non perdere i progressi.
        """
        logging.info("Salvataggio dati vocali prima dello spegnimento...")
        for member_id, session_data in list(self.bot.active_sessions.items()):
            try:
                leave_time = datetime.now(self.bot.BOT_TZ)
                
                # Se l'utente non era mutato, calcola la durata dell'ultimo intervallo
                if not session_data.get('is_muted', False):
                    duration_seconds = (leave_time - session_data['last_update']).total_seconds()
                    session_data['total_duration'] += duration_seconds
                
                total_duration = int(session_data['total_duration'])
                xp_to_add = self.calculate_voice_xp(total_duration)
                
                # Aggiorna tempo totale in vocale
                self.bot.cursor.execute(queries.update_voice_seconds_query, (total_duration, member_id))

                # Calcola tempo notturno per l'ultimo segmento
                if not session_data.get('is_muted', False):
                    segment_end = leave_time
                    segment_start = session_data['last_update']
                    night_seconds = self.calculate_night_duration(segment_start, segment_end)
                    if night_seconds > 0:
                        self.bot.cursor.execute(queries.update_night_voice_seconds_query, (night_seconds, member_id))

                await self.update_xp_and_level(member_id, session_data.get('guild_id'), xp_to_add)
                
                # Aggiorna la striscia giornaliera anche qui per coerenza
                await self.update_streak(member_id)

                self.bot.cursor.execute(queries.update_voice_activity_query, (leave_time, total_duration, member_id))
                self.bot.db.commit()
            except Exception as e:
                logging.error(f"Errore salvataggio dati per utente {member_id}: {e}")
        logging.info("Salvataggio dati vocali completato.")

    async def resume_sessions(self):
        """
        All'avvio del bot, controlla gli utenti già nei canali vocali e
        crea una sessione per loro per iniziare a tracciare l'attività.
        """
        logging.info("Ripresa delle sessioni per gli utenti già connessi...")
        for guild in self.bot.guilds:
            for channel in guild.voice_channels:
                if channel.id in self.bot.AFK_CHANNEL_IDS: 
                    continue
                for member in channel.members:
                    if member.bot:
                        continue
                    
                    now = datetime.now(self.bot.BOT_TZ)
                    is_muted = member.voice.self_mute or member.voice.self_deaf
                    
                    self.bot.active_sessions[member.id] = {
                        'join_time': now,
                        'last_update': now,
                        'total_duration': 0,
                        'is_muted': is_muted,
                        'mute_start_time': now if is_muted else None,
                        'last_activity_time': now,
                        'guild_id': guild.id,
                        'video_start': now if member.voice.self_video else None,
                        'stream_start': now if member.voice.self_stream else None
                    }

                    self.bot.cursor.execute(queries.insert_user_query, (member.id, member.name, member.nick))
                    self.bot.cursor.execute(queries.insert_channel_query, (channel.id, channel.name))
                    self.bot.cursor.execute(queries.insert_voice_activity_query, (member.id, channel.id, now))
                    self.bot.db.commit()
                    logging.info(f"Ripresa e creata nuova sessione per {member.name}.")
        logging.info(f"Riprese {len(self.bot.active_sessions)} sessioni.")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """
        Gestisce gli eventi di entrata, uscita e cambio di stato nei canali vocali.
        """
        if member.bot: return

        now = datetime.now(self.bot.BOT_TZ)
        user_id = member.id

        # Rileva se l'utente si sta spostando tra canali validi (non AFK)
        is_moving = before.channel and after.channel and before.channel.id != after.channel.id and after.channel.id not in self.bot.AFK_CHANNEL_IDS

        # EVENTO: Uscita da un canale vocale o spostamento in AFK
        is_leaving = before.channel and (after.channel is None or after.channel.id in self.bot.AFK_CHANNEL_IDS)

        # EVENTO: Spostamento tra canali validi (senza chiudere la sessione)
        if is_moving and user_id in self.bot.active_sessions:
            try:
                self.bot.cursor.execute(queries.update_voice_activity_channel_query, (after.channel.id, user_id))
                self.bot.db.commit()
                logging.info(f"{member.name} si è spostato in {after.channel.name}. Sessione continuata.")
            except Exception as e:
                logging.error(f"Errore aggiornamento canale per {member.name}: {e}")
        
        if is_leaving and user_id in self.bot.active_sessions:
            session_data = self.bot.active_sessions.pop(user_id)
            
            if not session_data.get('is_muted', False):
                duration_seconds = (now - session_data['last_update']).total_seconds()
                session_data['total_duration'] += duration_seconds

            # Aggiorna tempo video e stream se attivi
            if session_data.get('video_start'):
                video_duration = (now - session_data['video_start']).total_seconds()
                self.bot.cursor.execute(queries.update_video_seconds_query, (video_duration, user_id))
            
            if session_data.get('stream_start'):
                stream_duration = (now - session_data['stream_start']).total_seconds()
                self.bot.cursor.execute(queries.update_stream_seconds_query, (stream_duration, user_id))

            total_duration = int(session_data['total_duration'])
            
            if total_duration > 0:
                # Aggiorna tempo totale in vocale (indipendentemente dall'XP)
                self.bot.cursor.execute(queries.update_voice_seconds_query, (total_duration, user_id))
                
                # Calcola e aggiorna tempo notturno
                segment_end = now
                segment_start = session_data['last_update']
                if not session_data.get('is_muted', False):
                    night_seconds = self.calculate_night_duration(segment_start, segment_end)
                    if night_seconds > 0:
                        self.bot.cursor.execute(queries.update_night_voice_seconds_query, (night_seconds, user_id))

                # Controllo Badge 8: Maratoneta Vocale (Record sessione)
                self.bot.cursor.execute(queries.get_server_max_voice_duration_query)
                max_duration_result = self.bot.cursor.fetchone()
                current_record = max_duration_result['max_duration'] if max_duration_result and max_duration_result['max_duration'] is not None else 0
                
                if total_duration >= current_record:
                     badges_cog = self.bot.get_cog('Badges')
                     if badges_cog:
                        await badges_cog._check_and_award_badge(user_id, 8)

            xp_to_add = self.calculate_voice_xp(total_duration)
            if xp_to_add > 0:
                await self.update_xp_and_level(user_id, member.guild.id, xp_to_add)
                
                # Aggiorna la striscia giornaliera anche per l'attività vocale
                await self.update_streak(user_id)

                # Controlla altri badge (basati su XP/Livello)
                self.bot.cursor.execute(queries.get_user_xp_query, (user_id,))
                user_stats = self.bot.cursor.fetchone()
                if user_stats:
                    await self.check_badges(user_id, member.guild.id, user_stats)
            
            self.bot.cursor.execute(queries.update_voice_activity_query, (now, total_duration, user_id))
            self.bot.db.commit()
            logging.info(f"Sessione terminata per {member.name}. Durata attiva: {total_duration}s.")

        # EVENTO: Entrata in un canale vocale valido (o spostamento da un altro canale)
        is_joining = after.channel and after.channel.id not in self.bot.AFK_CHANNEL_IDS and user_id not in self.bot.active_sessions
        if is_joining:
            is_muted = after.self_mute or after.self_deaf
            self.bot.active_sessions[user_id] = {
                'join_time': now, 'last_update': now, 'total_duration': 0,
                'is_muted': is_muted, 'mute_start_time': now if is_muted else None,
                'last_activity_time': now,
                'guild_id': member.guild.id,
                'video_start': now if after.self_video else None,
                'stream_start': now if after.self_stream else None
            }
            self.bot.cursor.execute(queries.insert_user_query, (user_id, member.name, member.nick))
            self.bot.cursor.execute(queries.insert_channel_query, (after.channel.id, after.channel.name))
            self.bot.cursor.execute(queries.insert_voice_activity_query, (user_id, after.channel.id, now))
            self.bot.db.commit()
            logging.info(f"Sessione iniziata per {member.name} in {after.channel.name}.")
            return

        # EVENTO: Cambio di stato (mute/unmute, cambio canale)
        if user_id in self.bot.active_sessions:
            session_data = self.bot.active_sessions[user_id]
            session_data['last_activity_time'] = now  # Aggiorna l'attività per il timer AFK

            was_muted = session_data['is_muted']
            is_now_muted = after.self_mute or after.self_deaf

            # GESTIONE VIDEO (CAM)
            was_video = session_data.get('video_start') is not None
            is_now_video = after.self_video
            
            if was_video and not is_now_video: # Video spento
                duration = (now - session_data['video_start']).total_seconds()
                self.bot.cursor.execute(queries.update_video_seconds_query, (duration, user_id))
                session_data['video_start'] = None
            elif not was_video and is_now_video: # Video acceso
                session_data['video_start'] = now

            # GESTIONE STREAM (GO LIVE)
            was_stream = session_data.get('stream_start') is not None
            is_now_stream = after.self_stream
            
            if was_stream and not is_now_stream: # Stream spento
                duration = (now - session_data['stream_start']).total_seconds()
                self.bot.cursor.execute(queries.update_stream_seconds_query, (duration, user_id))
                session_data['stream_start'] = None
            elif not was_stream and is_now_stream: # Stream acceso
                session_data['stream_start'] = now

            if was_muted != is_now_muted:
                if is_now_muted:  # L'utente si è mutato
                    # Aggiunge il tempo trascorso prima del mute
                    duration_seconds = (now - session_data['last_update']).total_seconds()
                    session_data['total_duration'] += duration_seconds
                    
                    # Aggiorna anche il tempo totale in vocale nel DB per sicurezza
                    self.bot.cursor.execute(queries.update_voice_seconds_query, (duration_seconds, user_id))
                    
                    # Calcola e aggiorna tempo notturno per questo segmento
                    night_seconds = self.calculate_night_duration(session_data['last_update'], now)
                    if night_seconds > 0:
                        self.bot.cursor.execute(queries.update_night_voice_seconds_query, (night_seconds, user_id))
                        self.bot.db.commit()

                    session_data['mute_start_time'] = now
                    logging.info(f"{member.name} si è mutato. Accumulo XP in pausa.")
                else:  # L'utente si è smutato
                    # Riprende a contare il tempo da ora
                    session_data['last_update'] = now
                    session_data['mute_start_time'] = None
                    logging.info(f"{member.name} si è smutato. Accumulo XP ripreso.")
                session_data['is_muted'] = is_now_muted

    @commands.Cog.listener()
    async def on_member_join(self, member):
        """
        Invia un messaggio di benvenuto quando un nuovo utente si unisce al server.
        """
        if member.bot: return
        
        # Aggiunge l'utente al database se non esiste
        self.bot.cursor.execute(queries.insert_user_query, (member.id, member.name, member.nick))
        self.bot.db.commit()
        
        channel = self.bot.get_channel(self.bot.WELCOME_CHANNEL_ID)
        if channel:
            embed = discord.Embed(
                title=f"Benvenuto/a {member.name}!",
                description=f"Ciao {member.mention}, benvenuto/a nel Drunken's Server! L’oste ti porge un boccale pieno 🍺...",
                color=self.bot.PRIMARY_COLOR
            )
            embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
            
            if self.bot.KOFI_USERNAME:
                embed.description += f"\n\n[☕ Supporta il bot](https://ko-fi.com/{self.bot.KOFI_USERNAME})"
            
            embed.set_footer(text=f"Sei il {member.guild.member_count}° membro!")
            await channel.send(embed=embed)

    async def check_badges(self, user_id: int, guild_id: int, user_stats: dict):
        """
        Controlla se l'utente soddisfa i requisiti per qualche badge e lo assegna.
        """
        badges_cog = self.bot.get_cog('Badges')
        if not badges_cog:
            return

        try:
            # Recupera tutti i badge e i loro requisiti dal DB
            self.bot.cursor.execute(queries.get_all_badges_query)
            all_badges = self.bot.cursor.fetchall()

            for badge in all_badges:
                badge_id = badge['id']
                check_value = badge['check_value']
                
                awarded = False
                
                # Logica specifica per ogni badge basata sull'ID
                if badge_id == 1 and check_value: # Chiacchierone (Messaggi)
                    if user_stats.get('message_count', 0) >= check_value:
                        awarded = True
                
                elif badge_id == 2 and check_value: # Veterano Vocale (Tempo in vocale)
                    if user_stats.get('voice_seconds', 0) >= check_value:
                        awarded = True

                elif badge_id == 3 and check_value: # Notturno (Ore in vocale notturne)
                    if user_stats.get('night_voice_seconds', 0) >= check_value:
                        awarded = True

                elif badge_id == 4 and check_value: # Re delle Reazioni (Reazioni date)
                    if user_stats.get('reaction_count', 0) >= check_value:
                        awarded = True
                
                elif badge_id == 5 and check_value: # Maestro di Livello (Livello)
                    if user_stats.get('level', 1) >= check_value:
                        awarded = True
                
                elif badge_id == 6 and check_value: # Pioniere (Primi 10 utenti)
                    # Controlla se l'utente è tra i primi 10 registrati nel DB
                    self.bot.cursor.execute(queries.get_first_users_query, (check_value,))
                    first_users = [row['id'] for row in self.bot.cursor.fetchall()]
                    
                    if user_id in first_users:
                        awarded = True

                elif badge_id == 8: # Maratoneta Vocale (Record sessione)
                    # Controlla se l'utente ha stabilito un nuovo record
                    self.bot.cursor.execute(queries.get_server_max_voice_duration_query)
                    max_duration_result = self.bot.cursor.fetchone()
                    server_record = max_duration_result['max_duration'] if max_duration_result and max_duration_result['max_duration'] is not None else 0
                    
                    if server_record > 0:
                        # Verifica se l'utente ha una sessione che eguaglia o supera il record
                        self.bot.cursor.execute(queries.check_user_voice_record_query, (user_id, server_record))
                        if self.bot.cursor.fetchone():
                            awarded = True

                elif badge_id == 9: # Super Sayan (Record XP giornaliero)
                    self.bot.cursor.execute(queries.get_server_max_daily_xp_query)
                    max_xp_result = self.bot.cursor.fetchone()
                    current_record_xp = max_xp_result['max_xp'] if max_xp_result and max_xp_result['max_xp'] is not None else 0
                    
                    if user_stats.get('max_daily_xp', 0) >= current_record_xp and current_record_xp > 0:
                        awarded = True

                elif badge_id == 10 and check_value: # Instancabile (Striscia giorni)
                    if user_stats.get('activity_streak', 0) >= check_value:
                        awarded = True

                elif badge_id == 11 and check_value: # Veterano (Giorni nel server)
                    # Recupera l'oggetto member per controllare joined_at
                    member = None
                    if guild_id:
                        guild = self.bot.get_guild(guild_id)
                        if guild:
                            member = guild.get_member(user_id)
                    
                    if member and member.joined_at:
                        days_in_server = (datetime.now(self.bot.BOT_TZ) - member.joined_at).days
                        if days_in_server >= check_value:
                            awarded = True

                elif badge_id == 12 and check_value: # Faccia a Faccia (Video)
                    if user_stats.get('video_seconds', 0) >= check_value:
                        awarded = True

                elif badge_id == 13 and check_value: # Regista (Stream)
                    if user_stats.get('stream_seconds', 0) >= check_value:
                        awarded = True

                if awarded:
                    await badges_cog._check_and_award_badge(user_id, badge_id)
        except Exception as e:
            logging.error(f"Errore durante il controllo dei badge per {user_id}: {e}")

    async def update_streak(self, user_id: int):
        """
        Aggiorna la striscia di attività giornaliera dell'utente.
        """
        try:
            self.bot.cursor.execute(queries.get_user_xp_query, (user_id,))
            result = self.bot.cursor.fetchone()
            if not result: return

            last_date = result['last_activity_date']
            current_streak = result['activity_streak']
            today = datetime.now(self.bot.BOT_TZ).date()

            if last_date is None:
                # Prima attività in assoluto
                new_streak = 1
            elif last_date == today:
                # Già attivo oggi, non cambiare nulla
                return
            elif (today - last_date).days == 1:
                # Attivo ieri, incrementa striscia
                new_streak = current_streak + 1
            else:
                # Saltato un giorno o più, resetta striscia
                new_streak = 1
            
            self.bot.cursor.execute(queries.update_streak_query, (today, new_streak, user_id))
            self.bot.db.commit()
            
        except Exception as e:
            logging.error(f"Errore aggiornamento streak per {user_id}: {e}")

    @commands.Cog.listener()
    async def on_message(self, message):
        """
        Assegna XP per l'invio di messaggi, con un cooldown.
        """
        if message.author.bot or not message.guild:
            return

        now = datetime.now(self.bot.BOT_TZ)
        user_id = message.author.id

        # Aggiorna l'orario dell'ultima attività per l'AFK timer
        if user_id in self.bot.active_sessions:
            self.bot.active_sessions[user_id]['last_activity_time'] = now

        # Gestisce il cooldown per evitare spam di XP
        last_message_time = self.bot.message_timestamps.get(user_id)
        if last_message_time and (now - last_message_time).total_seconds() < self.bot.MESSAGE_COOLDOWN:
            return

        self.bot.message_timestamps[user_id] = now
        xp_to_add = self.bot.XP_PER_MESSAGE
        try:
            # Assicura che l'utente esista nel DB (per utenti vecchi che non sono mai entrati in vocale)
            self.bot.cursor.execute(queries.insert_user_query, (message.author.id, message.author.name, message.author.nick))
            
            # Aggiorna conteggio messaggi
            self.bot.cursor.execute(queries.increment_message_count_query, (message.author.id,))
            
            # IMPORTANTE: update_xp_and_level deve essere chiamato PRIMA di update_streak
            # Altrimenti update_streak aggiorna la data a "oggi" e il reset dell'XP giornaliero non avviene mai.
            
            # Controlla per il level up e aggiunge XP
            await self.update_xp_and_level(message.author.id, message.guild.id, xp_to_add)

            # Aggiorna la striscia giornaliera
            await self.update_streak(message.author.id)

            # Recupera statistiche aggiornate per i badge
            self.bot.cursor.execute(queries.get_user_xp_query, (message.author.id,))
            user_stats = self.bot.cursor.fetchone()
            
            if user_stats:
                await self.check_badges(message.author.id, message.guild.id, user_stats)
            
            self.bot.db.commit()

        except mysql.connector.Error as err:
            logging.error(f"Errore MySQL: {err}")
        except Exception as e:
            logging.error(f"Errore in on_message: {e}")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        """
        Assegna XP quando un utente aggiunge una reazione a un messaggio.
        """
        if not payload.guild_id: return
        
        reactor = payload.member
        if not reactor or reactor.bot: return

        # Aggiorna l'attività per il timer AFK
        if reactor.id in self.bot.active_sessions:
            self.bot.active_sessions[reactor.id]['last_activity_time'] = datetime.now(self.bot.BOT_TZ)

        try:
            channel = self.bot.get_channel(payload.channel_id)
            if not channel: return
            
            message = await channel.fetch_message(payload.message_id)
            author = message.author

            # Non dare XP se l'autore è un bot o se l'utente reagisce a se stesso
            if author.bot or author.id == reactor.id: return
            
            # Assicura che l'utente esista nel DB
            self.bot.cursor.execute(queries.insert_user_query, (reactor.id, reactor.name, reactor.nick))

            # Aggiorna conteggio reazioni
            self.bot.cursor.execute(queries.increment_reaction_count_query, (reactor.id,))

            # Premia chi ha reagito
            await self.update_xp_and_level(reactor.id, payload.guild_id, self.bot.XP_PER_REACTION)

            # Aggiorna la striscia giornaliera (IMPORTANTE per evitare reset XP giornaliero)
            await self.update_streak(reactor.id)

            # Recupera statistiche aggiornate per i badge
            self.bot.cursor.execute(queries.get_user_xp_query, (reactor.id,))
            user_stats = self.bot.cursor.fetchone()
            
            if user_stats:
                await self.check_badges(reactor.id, payload.guild_id, user_stats)
            
            self.bot.db.commit()

        except discord.NotFound:
            pass  # Il messaggio potrebbe essere stato cancellato
        except Exception as e:
            logging.error(f"Errore in on_raw_reaction_add: {e}")

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before, after):
        """
        Aggiorna il nome del canale nel database quando viene modificato.
        """
        # Consideriamo solo i canali vocali e se il nome è cambiato
        if isinstance(after, discord.VoiceChannel) and before.name != after.name:
            try:
                self.bot.cursor.execute(queries.insert_channel_query, (after.id, after.name))
                self.bot.db.commit()
                logging.info(f"Canale '{before.name}' rinominato in '{after.name}'. DB aggiornato.")
            except Exception as e:
                logging.error(f"Errore durante l'aggiornamento del nome del canale {before.name}: {e}")

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        """
        Aggiorna il nome utente e il nickname nel database quando cambiano.
        """
        if before.display_name != after.display_name:
            self.bot.cursor.execute(queries.update_user_names_query, (after.name, after.nick, after.id))
            self.bot.db.commit()


async def setup(bot):
    await bot.add_cog(ActivityEvents(bot))