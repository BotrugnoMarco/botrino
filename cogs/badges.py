"""
Questo cog gestisce il sistema di badge e onorificenze.
"""
import discord
from discord.ext import commands
import logging
import queries

# Lista dei badge da inserire nel database all'avvio
# Formato: (id, nome, descrizione, icona, valore_controllo)
INITIAL_BADGES = [
    # Badge basati sull'attività
    (1, 'Chiacchierone', 'Invia un totale di 100 messaggi.', '💬', 100),
    (2, 'Veterano Vocale', 'Accumula 50 ore totali nei canali vocali.', '🎙️', 50 * 3600), # 50 ore in secondi
    (3, 'Notturno', 'Accumula 10 ore in vocale tra le 01:00 e le 05:00 del mattino.', '🦉', 10 * 3600),
    (4, 'Re delle Reazioni', 'Assegna un totale di 50 reazioni ai messaggi.', '✨', 50),
    # Badge basati sui traguardi
    (5, 'Maestro di Livello', 'Raggiungi il livello 25.', '🏆', 25),
    (6, 'Pioniere', 'Essere uno dei primi 10 membri ad aver interagito col bot.', '🚀', 10),
    (7, 'Sostenitore', 'Aver effettuato una donazione.', '☕', None), # Manuale
    # Badge basati su record e strisce
    (8, 'Maratoneta Vocale', 'Avere la sessione vocale ininterrotta più lunga del server.', '⏳', None), # Record
    (9, 'Super Sayan', 'Stabilire il record per il maggior numero di XP guadagnati in un solo giorno.', '⚡', None), # Record
    (10, 'Instancabile', 'Mantenere una striscia di attività (XP guadagnati) per 7 giorni di fila.', '🔥', 7),
    # Nuovi Badge
    (11, 'Veterano', 'Membro del server da almeno 1 anno.', '💎', 365), # Giorni
    (12, 'Faccia a Faccia', 'Usa la webcam in vocale per almeno 5 ore totali.', '📹', 5 * 3600),
    (13, 'Regista', 'Trasmetti in streaming (Go Live) per almeno 10 ore totali.', '🎥', 10 * 3600)
]

class Badges(commands.Cog):
    """
    Cog per la gestione dei badge.
    """
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        """
        Listener eseguito quando il bot è pronto.
        Inizializza i badge nel database.
        """
        await self._initialize_badges()

    async def _initialize_badges(self):
        """
        Popola la tabella 'badges' con i badge iniziali se non esistono già.
        """
        try:
            logging.info("Inizializzazione e verifica dei badge nel database...")
            for badge_id, name, description, icon, check_value in INITIAL_BADGES:
                self.bot.cursor.execute(queries.insert_badge_query, (badge_id, name, description, icon, check_value))
            self.bot.db.commit()
            logging.info("Badge inizializzati con successo.")
        except Exception as e:
            logging.error(f"Errore durante l'inizializzazione dei badge: {e}", exc_info=True)

    async def _check_and_award_badge(self, user_id, badge_id):
        """
        Controlla e assegna un badge a un utente se non lo ha già.
        Invia una notifica se il badge viene assegnato per la prima volta.
        """
        try:
            # Tenta di inserire il badge per l'utente. IGNORE previene errori se esiste già.
            self.bot.cursor.execute(queries.add_badge_to_user_query, (user_id, badge_id))
            self.bot.db.commit()

            # Se l'operazione ha inserito una nuova riga, significa che il badge è nuovo per l'utente.
            if self.bot.cursor.rowcount > 0:
                user = await self.bot.fetch_user(user_id)
                if not user:
                    return

                # Trova i dettagli del badge dalla lista iniziale
                badge_info = next((b for b in INITIAL_BADGES if b[0] == badge_id), None)
                if not badge_info:
                    return
                
                _, name, description, icon, _ = badge_info

                logging.info(f"Assegnato il badge '{name}' all'utente {user.name} (ID: {user_id}).")

                embed = discord.Embed(
                    title="🏅 Nuovo Badge Ottenuto!",
                    description=f"Congratulazioni, hai sbloccato il badge **{name}**!",
                    color=self.bot.PRIMARY_COLOR
                )
                embed.add_field(name=f"{icon} {name}", value=description)
                embed.set_thumbnail(url=user.display_avatar.url)
                
                if self.bot.KOFI_USERNAME:
                    embed.add_field(name="Supporto", value=f"[☕ Offrimi un caffè](https://ko-fi.com/{self.bot.KOFI_USERNAME})", inline=False)

                await user.send(embed=embed)

        except Exception as e:
            logging.error(f"Errore durante l'assegnazione del badge {badge_id} all'utente {user_id}: {e}", exc_info=True)


    @commands.command(name='badges', help="Mostra i badge guadagnati da un utente.")
    async def badges(self, ctx, member: discord.Member = None):
        """
        Mostra i badge guadagnati dall'utente specificato (o da se stesso).
        """
        target_user = member or ctx.author
        try:
            # Query per ottenere i badge dell'utente
            self.bot.cursor.execute(queries.get_user_badges_query, (target_user.id,))
            user_badges = self.bot.cursor.fetchall()

            if not user_badges:
                await ctx.send(f"{target_user.display_name} non ha ancora guadagnato nessun badge.")
                return

            embed = discord.Embed(
                title=f"🏅 Badge di {target_user.display_name}",
                color=self.bot.PRIMARY_COLOR
            )
            embed.set_thumbnail(url=target_user.display_avatar.url)

            for badge in user_badges:
                embed.add_field(
                    name=f"{badge['icon']} {badge['name']}",
                    value=badge['description'],
                    inline=False
                )
            
            if self.bot.KOFI_USERNAME:
                embed.add_field(name="Supporto", value=f"[☕ Offrimi un caffè](https://ko-fi.com/{self.bot.KOFI_USERNAME})", inline=False)

            await ctx.send(embed=embed)

        except Exception as e:
            logging.error(f"Errore nel comando badges: {e}", exc_info=True)
            await ctx.send("Si è verificato un errore durante la visualizzazione dei badge.")

    @commands.command(name='assegna_badge', help="Assegna manualmente un badge a un utente (Solo Admin).")
    @commands.has_permissions(administrator=True)
    async def assign_badge(self, ctx, member: discord.Member, badge_id: int):
        """
        Comando amministrativo per assegnare manualmente un badge (es. Sostenitore).
        """
        try:
            # Verifica se il badge esiste
            badge_info = next((b for b in INITIAL_BADGES if b[0] == badge_id), None)
            if not badge_info:
                await ctx.send("ID Badge non valido.")
                return

            await self._check_and_award_badge(member.id, badge_id)
            await ctx.send(f"Badge **{badge_info[1]}** assegnato a {member.display_name}.")
            
        except Exception as e:
            logging.error(f"Errore nell'assegnazione manuale del badge: {e}")
            await ctx.send("Errore durante l'assegnazione del badge.")

    @commands.command(name='force_check_badges', help="Forza il controllo dei badge per un utente.")
    @commands.has_permissions(administrator=True)
    async def force_check_badges(self, ctx, member: discord.Member = None):
        """
        Esegue manualmente il controllo dei badge per l'utente specificato.
        Utile se si pensa che un badge non sia stato assegnato correttamente.
        """
        target_user = member or ctx.author
        
        try:
            # Recupera le statistiche dell'utente
            self.bot.cursor.execute(queries.get_user_xp_query, (target_user.id,))
            user_stats = self.bot.cursor.fetchone()
            
            if not user_stats:
                await ctx.send(f"Nessun dato trovato per {target_user.display_name}.")
                return

            # Recupera il cog ActivityEvents per usare la sua funzione check_badges
            activity_cog = self.bot.get_cog('ActivityEvents')
            if activity_cog:
                await activity_cog.check_badges(target_user.id, ctx.guild.id, user_stats)
                await ctx.send(f"✅ Controllo badge completato per {target_user.display_name}. Se aveva i requisiti, i badge sono stati assegnati.")
            else:
                await ctx.send("❌ Errore: Cog ActivityEvents non trovato.")
        except Exception as e:
            logging.error(f"Errore nel comando force_check_badges: {e}", exc_info=True)
            await ctx.send("Si è verificato un errore durante il controllo.")

async def setup(bot):
    await bot.add_cog(Badges(bot))