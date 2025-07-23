import discord
from discord.ext import commands, tasks
import asyncio
import re
import random
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytz

GIVEAWAYS_FILE = Path("giveaways.json")
FINISHED_GIVEAWAYS_FILE = Path("finished_giveaways.json")
PARIS_TZ = pytz.timezone("Europe/Paris")

class GiveawayButton(discord.ui.View):
    def __init__(self, ctx, message, end_time, bot):
        super().__init__(timeout=None)
        self.ctx = ctx
        self.bot = bot
        self.message = message
        self.end_time = end_time
        self.participants = set()
        self.cancelled = False
        self.cog = ctx.cog if hasattr(ctx, 'cog') else None

    @discord.ui.button(label="🎉 Participer", style=discord.ButtonStyle.green)
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id in self.participants:
            self.participants.remove(interaction.user.id)
            await interaction.response.send_message("❌ Tu ne participes plus au giveaway.", ephemeral=True)
        else:
            self.participants.add(interaction.user.id)
            await interaction.response.send_message("✅ Tu participes au giveaway !", ephemeral=True)

        # Référence correcte au cog
        if hasattr(self.bot, 'get_cog'):
            cog = self.bot.get_cog('Giveaway')
            if cog:
                cog.save_giveaways()

class ParticipantsView(discord.ui.View):
    def __init__(self, ctx, participants, message_id, giveaway_description):
        super().__init__(timeout=120)
        self.ctx = ctx
        self.participants = participants
        self.message_id = message_id
        self.giveaway_description = giveaway_description
        self.page = 0
        self.per_page = 15
        self.total_pages = (len(participants) - 1) // self.per_page + 1 if participants else 1

    def format_page(self):
        start = self.page * self.per_page
        end = start + self.per_page
        chunk = self.participants[start:end]

        lines = []
        for i, uid in enumerate(chunk, start=start):
            member = self.ctx.guild.get_member(uid)
            if member:
                lines.append(f"`{i+1:02d}.` {member.mention} • `{member.display_name}`")
            else:
                lines.append(f"`{i+1:02d}.` ❌ Utilisateur quitté • `ID: {uid}`")

        embed = discord.Embed(
            title=f"🎉 Participants du Giveaway",
            description=f"**Lot :** {self.giveaway_description}\n\n" + ("\n".join(lines) if lines else "Aucun participant"),
            color=0x00d4ff
        )
        embed.set_footer(text=f"ID du Giveaway: {self.message_id} • Page {self.page+1}/{self.total_pages}")
        return embed

    @discord.ui.button(emoji="⬅️", style=discord.ButtonStyle.blurple, disabled=True)
    async def left_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("❌ Seul l'organisateur peut naviguer.", ephemeral=True)

        self.page = max(0, self.page - 1)

        # Mettre à jour l'état des boutons
        self.left_button.disabled = (self.page == 0)
        self.right_button.disabled = (self.page >= self.total_pages - 1)

        await interaction.response.edit_message(embed=self.format_page(), view=self)

    @discord.ui.button(emoji="➡️", style=discord.ButtonStyle.blurple)
    async def right_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("❌ Seul l'organisateur peut naviguer.", ephemeral=True)

        self.page = min(self.total_pages - 1, self.page + 1)

        # Mettre à jour l'état des boutons
        self.left_button.disabled = (self.page == 0)
        self.right_button.disabled = (self.page >= self.total_pages - 1)

        await interaction.response.edit_message(embed=self.format_page(), view=self)

    @discord.ui.button(emoji="🔄", style=discord.ButtonStyle.secondary, label="Actualiser")
    async def refresh_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("❌ Seul l'organisateur peut actualiser.", ephemeral=True)

        # Récupérer les participants actuels
        cog = self.ctx.bot.get_cog('Giveaway')
        if cog and self.message_id in cog.active_giveaways:
            self.participants = list(cog.active_giveaways[self.message_id].participants)
            self.total_pages = (len(self.participants) - 1) // self.per_page + 1 if self.participants else 1
            self.page = min(self.page, self.total_pages - 1)

            # Mettre à jour l'état des boutons
            self.left_button.disabled = (self.page == 0)
            self.right_button.disabled = (self.page >= self.total_pages - 1)

        await interaction.response.edit_message(embed=self.format_page(), view=self)

    async def on_timeout(self):
        # Désactiver tous les boutons au timeout
        for item in self.children:
            item.disabled = True
        try:
            # Essayer de modifier le message si possible
            await self.message.edit(view=self)
        except:
            pass

class Giveaway(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_giveaways = {}
        self._loaded_data = {}
        self._finished_giveaways = {}
        self.load_giveaways()
        self.load_finished_giveaways()

    def cog_load(self):
        """Appelé quand le cog est chargé"""
        self.check_giveaways.start()

    def cog_unload(self):
        """Appelé quand le cog est déchargé"""
        self.check_giveaways.cancel()

    def is_staff(self, user):
        """Vérifier si l'utilisateur est un membre du staff"""
        try:
            staff_cog = self.bot.get_cog('StaffManager')
            if staff_cog and hasattr(staff_cog, 'is_staff'):
                return staff_cog.is_staff(user)
            return False
        except:
            return False

    def parse_duration(self, duration_str):
        matches = re.findall(r'(\d+)([dhm])', duration_str.lower())
        if not matches:
            return None
        total_seconds = 0
        for value, unit in matches:
            value = int(value)
            if unit == 'd': total_seconds += value * 86400
            elif unit == 'h': total_seconds += value * 3600
            elif unit == 'm': total_seconds += value * 60
        return total_seconds if total_seconds > 0 else None

    def format_remaining(self, delta_seconds):
        if delta_seconds <= 0:
            return "Terminé"
        minutes, seconds = divmod(delta_seconds, 60)
        hours, minutes = divmod(minutes, 60)
        days, hours = divmod(hours, 24)
        parts = []
        if days: parts.append(f"{days}j")
        if hours: parts.append(f"{hours}h")
        if minutes: parts.append(f"{minutes}m")
        return " ".join(parts) or "moins d'une minute"

    def save_giveaways(self):
        data = {}
        now = datetime.now(timezone.utc)
        for mid, view in self.active_giveaways.items():
            if view.cancelled or view.end_time < now:
                continue
            embed = view.message.embeds[0] if view.message.embeds else None
            data[str(mid)] = {
                "end_time": view.end_time.isoformat(),
                "participants": list(view.participants),
                "channel_id": view.ctx.channel.id,
                "guild_id": view.ctx.guild.id,
                "author_id": view.ctx.author.id if hasattr(view.ctx, 'author') and view.ctx.author else None,
                "description": embed.description if embed else ""
            }
        try:
            GIVEAWAYS_FILE.write_text(json.dumps(data, indent=4))
        except Exception as e:
            print(f"Erreur sauvegarde giveaways: {e}")

    def load_giveaways(self):
        if GIVEAWAYS_FILE.exists():
            try:
                self._loaded_data = json.loads(GIVEAWAYS_FILE.read_text())
            except Exception as e:
                print(f"Erreur chargement giveaways: {e}")
                self._loaded_data = {}
        else:
            self._loaded_data = {}

    def save_finished_giveaways(self):
        try:
            FINISHED_GIVEAWAYS_FILE.write_text(json.dumps(self._finished_giveaways, indent=4))
        except Exception as e:
            print(f"Erreur sauvegarde giveaways terminés: {e}")

    def load_finished_giveaways(self):
        if FINISHED_GIVEAWAYS_FILE.exists():
            try:
                self._finished_giveaways = json.loads(FINISHED_GIVEAWAYS_FILE.read_text())
            except Exception as e:
                print(f"Erreur chargement giveaways terminés: {e}")
                self._finished_giveaways = {}
        else:
            self._finished_giveaways = {}

    @tasks.loop(seconds=30)
    async def check_giveaways(self):
        now = datetime.now(timezone.utc)
        for message_id, view in list(self.active_giveaways.items()):
            if view.cancelled:
                continue
            remaining = (view.end_time - now).total_seconds()
            if remaining <= 0:
                await self.end_giveaway(view)

    @check_giveaways.before_loop
    async def before_check_giveaways(self):
        await self.bot.wait_until_ready()

    async def end_giveaway(self, view):
        """Fonction corrigée pour terminer un giveaway"""
        message = view.message

        # Obtenir le canal depuis le message
        channel = message.channel
        guild = channel.guild

        # Sauvegarder dans les giveaways terminés avant de supprimer
        embed = message.embeds[0] if message.embeds else None
        winner_id = None
        winner_mention = None
        giveaway_description = embed.description if embed else "Lot non spécifié"

        if view.participants:
            winner_id = random.choice(list(view.participants))
            winner = guild.get_member(winner_id)
            winner_mention = winner.mention if winner else f"<@{winner_id}>"

        self._finished_giveaways[str(message.id)] = {
            "end_time": view.end_time.isoformat(),
            "participants": list(view.participants),
            "winner_id": winner_id,
            "channel_id": channel.id,
            "guild_id": guild.id,
            "description": giveaway_description,
            "finished_at": datetime.now(timezone.utc).isoformat()
        }

        # Supprimer des giveaways actifs
        self.active_giveaways.pop(message.id, None)
        self.save_giveaways()
        self.save_finished_giveaways()

        # Supprimer le message du giveaway
        try:
            await message.delete()
        except discord.NotFound:
            pass
        except Exception as e:
            print(f"Erreur lors de la suppression du message du giveaway: {e}")

        # Annoncer le résultat
        if view.participants and winner_id:
            winner = guild.get_member(winner_id)
            if winner:
                embed = discord.Embed(
                    title="🎉 Giveaway terminé !",
                    description=f"Félicitations {winner.mention}, tu as gagné : **{giveaway_description}** !",
                    color=discord.Color.green()
                )
                await channel.send(embed=embed)
            else:
                embed = discord.Embed(
                    title="🎉 Giveaway terminé",
                    description=f"Le gagnant du giveaway a quitté le serveur. (ID: {winner_id})",
                    color=discord.Color.orange()
                )
                await channel.send(embed=embed)
        else:
            embed = discord.Embed(
                title="❌ Giveaway terminé",
                description=f"Aucun participant au giveaway : **{giveaway_description}**",
                color=discord.Color.red()
            )
            await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_ready(self):
        print("Chargement des giveaways sauvegardés...")
        now = datetime.now(timezone.utc)

        for mid, info in self._loaded_data.items():
            try:
                message_id = int(mid)
                channel = self.bot.get_channel(info["channel_id"])
                if not channel:
                    print(f"Canal {info['channel_id']} introuvable pour le giveaway {mid}")
                    continue

                try:
                    msg = await channel.fetch_message(message_id)
                except discord.NotFound:
                    print(f"Message {message_id} introuvable")
                    continue

                end_time = datetime.fromisoformat(info["end_time"])
                if end_time.tzinfo is None:
                    end_time = end_time.replace(tzinfo=timezone.utc)

                # Si le giveaway est déjà expiré, le terminer immédiatement
                if end_time <= now:
                    print(f"Giveaway {mid} expiré, terminaison immédiate...")

                    # Créer une vue temporaire pour la terminaison
                    class DummyCtx:
                        def __init__(self, channel, author_id):
                            self.channel = channel
                            self.guild = channel.guild
                            self.author = channel.guild.get_member(author_id) if author_id else None

                    dummy_ctx = DummyCtx(channel, info.get("author_id"))
                    temp_view = GiveawayButton(ctx=dummy_ctx, message=msg, end_time=end_time, bot=self.bot)
                    temp_view.participants = set(info["participants"])

                    # Terminer le giveaway
                    await self.end_giveaway(temp_view)
                    continue

                # Classe temporaire pour le contexte
                class DummyCtx:
                    def __init__(self, channel, author_id):
                        self.channel = channel
                        self.guild = channel.guild
                        self.author = channel.guild.get_member(author_id) if author_id else None
                        self.cog = None

                dummy_ctx = DummyCtx(channel, info.get("author_id"))

                # Convertir l'heure de fin en heure de Paris pour l'affichage
                end_time_paris = end_time.astimezone(PARIS_TZ)

                embed = discord.Embed(
                    title="🎁 Giveaway !",
                    description=info.get("description", ""),
                    color=discord.Color.gold()
                )
                embed.set_footer(text=f"Se termine le {end_time_paris.strftime('%d/%m/%Y à %H:%M')}")

                view = GiveawayButton(ctx=dummy_ctx, message=msg, end_time=end_time, bot=self.bot)
                view.participants = set(info["participants"])

                await msg.edit(embed=embed, view=view)
                self.active_giveaways[message_id] = view
                print(f"Giveaway {mid} restauré avec succès")

            except Exception as e:
                print(f"[Giveaway] Erreur lors de la restauration du giveaway {mid} : {e}")

        self.save_giveaways()

    @commands.command()
    async def giveaway(self, ctx, *, args: str):
        """Créer un giveaway. Format: !giveaway JJ/MM/AAAA HH:MM <lot>"""
        if not self.is_staff(ctx.author):
            return await ctx.send("❌ Vous n'avez pas la permission d'utiliser cette commande.")

        print(f"Commande giveaway reçue de {ctx.author}: {args}")

        split_args = args.split()
        if len(split_args) < 3:
            return await ctx.send("❌ Format invalide. Utilise : `!giveaway JJ/MM/AAAA HH:MM <lot>`\nExemple : `!giveaway 25/07/2025 21:00 Nitro`")

        try:
            date_str = f"{split_args[0]} {split_args[1]}"
            end_time = datetime.strptime(date_str, "%d/%m/%Y %H:%M")
            end_time = PARIS_TZ.localize(end_time).astimezone(timezone.utc)

            if end_time <= datetime.now(timezone.utc):
                return await ctx.send("⏱️ La date de fin doit être dans le futur.")
        except ValueError:
            return await ctx.send("❌ Format invalide. Utilise : `JJ/MM/AAAA HH:MM` (ex: `25/07/2025 21:00`)")

        description = " ".join(split_args[2:])

        # Convertir l'heure de fin en heure de Paris pour l'affichage
        end_time_paris = end_time.astimezone(PARIS_TZ)

        embed = discord.Embed(
            title="🎁 Giveaway !",
            description=description,
            color=discord.Color.gold()
        )
        embed.set_footer(text=f"Se termine le {end_time_paris.strftime('%d/%m/%Y à %H:%M')}")

        message = await ctx.send(embed=embed)

        view = GiveawayButton(ctx, message, end_time, self.bot)
        self.active_giveaways[message.id] = view
        await message.edit(view=view)
        self.save_giveaways()

        print(f"Giveaway créé avec l'ID {message.id}")

    @commands.command()
    async def cancelgiveaway(self, ctx, message_id: int):
        """Annuler un giveaway actif"""
        if not self.is_staff(ctx.author):
            return await ctx.send("❌ Vous n'avez pas la permission d'utiliser cette commande.")

        view = self.active_giveaways.get(message_id)
        if not view:
            return await ctx.send("⚠️ Aucun giveaway actif avec cet ID.")

        # Récupérer les informations du giveaway avant suppression
        giveaway_description = view.message.embeds[0].description if view.message.embeds else "Lot non spécifié"
        participant_count = len(view.participants)

        view.cancelled = True

        # Supprimer le message du giveaway
        try:
            await view.message.delete()
        except discord.NotFound:
            pass
        except Exception as e:
            print(f"Erreur lors de la suppression du message: {e}")

        # Supprimer de la liste active
        del self.active_giveaways[message_id]
        self.save_giveaways()

        # Message d'annulation stylé
        embed = discord.Embed(
            title="❌ Giveaway Annulé",
            description=f"**{ctx.author.mention}** a annulé le giveaway",
            color=discord.Color.red()
        )
        embed.add_field(name="🎁 Lot", value=giveaway_description, inline=False)
        embed.add_field(name="📊 Participants", value=f"{participant_count} personnes", inline=True)
        embed.add_field(name="🆔 ID", value=f"`{message_id}`", inline=True)
        embed.timestamp = datetime.now(timezone.utc)

        await ctx.send(embed=embed)

    @commands.command(name="pg")
    async def participants_giveaway(self, ctx, message_id: int):
        """Voir les participants d'un giveaway"""
        if not self.is_staff(ctx.author):
            return await ctx.send("❌ Vous n'avez pas la permission d'utiliser cette commande.")

        view = self.active_giveaways.get(message_id)
        if not view:
            return await ctx.send("⚠️ Aucun giveaway actif avec cet ID.")

        if not view.participants:
            embed = discord.Embed(
                title="❌ Aucun Participant",
                description=f"**Lot :** {view.message.embeds[0].description}\n\nAucune personne n'a encore rejoint ce giveaway.",
                color=discord.Color.orange()
            )
            return await ctx.send(embed=embed)

        participants = list(view.participants)
        giveaway_description = view.message.embeds[0].description if view.message.embeds else "Lot non spécifié"

        paginator = ParticipantsView(ctx, participants, message_id, giveaway_description)

        # Initialiser l'état des boutons
        paginator.left_button.disabled = True
        if paginator.total_pages <= 1:
            paginator.right_button.disabled = True

        message = await ctx.send(embed=paginator.format_page(), view=paginator)
        paginator.message = message

    @commands.command()
    async def editgiveaway(self, ctx, message_id: int, *args):
        """Modifier un giveaway actif"""
        if not self.is_staff(ctx.author):
            return await ctx.send("❌ Vous n'avez pas la permission d'utiliser cette commande.")

        # Vérifier d'abord dans les giveaways actifs (priorité)
        view = self.active_giveaways.get(message_id)
        if not view:
            return await ctx.send("❌ Giveaway introuvable ou déjà terminé.")

        if not args:
            return await ctx.send("❌ Utilise : `!editgiveaway <id> <nouvelle_date> <nouveau_lot>` ou `!editgiveaway <id> <nouvelle_date>` ou `!editgiveaway <id> <nouveau_lot>`")

        new_end_time = None
        new_description = None

        # Pattern pour détecter une date au format JJ/MM/AAAA HH:MM
        date_regex = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})\s+(\d{1,2}):(\d{1,2})$")

        # Vérifier si les 2 premiers arguments forment une date valide
        if len(args) >= 2:
            potential_date = f"{args[0]} {args[1]}"
            match = date_regex.match(potential_date)

            if match:
                try:
                    day, month, year, hour, minute = map(int, match.groups())

                    # Validation des valeurs
                    if not (1 <= day <= 31 and 1 <= month <= 12 and 0 <= hour <= 23 and 0 <= minute <= 59):
                        raise ValueError("Valeurs de date/heure invalides")

                    # Créer la datetime
                    dt = datetime(year, month, day, hour, minute)
                    dt_paris = PARIS_TZ.localize(dt)

                    # Vérifier que c'est dans le futur
                    if dt_paris <= datetime.now(PARIS_TZ):
                        return await ctx.send("❌ La date donnée est déjà passée.")

                    new_end_time = dt_paris.astimezone(timezone.utc)

                    # Récupérer le reste comme description (s'il y en a)
                    if len(args) > 2:
                        new_description = " ".join(args[2:]).strip()

                except (ValueError, TypeError):
                    # Si la conversion échoue, traiter tout comme description
                    new_description = " ".join(args).strip()
            else:
                # Pas de date détectée, tout est traité comme description
                new_description = " ".join(args).strip()
        else:
            # Un seul argument, c'est forcément une description
            new_description = " ".join(args).strip()

        # Vérifier qu'au moins une modification est demandée
        if not new_end_time and not new_description:
            return await ctx.send("❌ Aucune modification détectée. Utilise une date au format `JJ/MM/AAAA HH:MM` ou une description.")

        # Mettre à jour l'objet view
        if new_end_time:
            view.end_time = new_end_time

        # Mise à jour visuelle du message
        try:
            embed = view.message.embeds[0]
            if new_description:
                embed.description = new_description

            # Afficher la nouvelle date de fin
            end_time_paris = view.end_time.astimezone(PARIS_TZ)
            embed.set_footer(text=f"Se termine le {end_time_paris.strftime('%d/%m/%Y à %H:%M')}")
            await view.message.edit(embed=embed)
        except Exception as e:
            print(f"Erreur mise à jour message giveaway: {e}")
            return await ctx.send("❌ Erreur lors de la mise à jour du message du giveaway.")

        # Sauvegarder les modifications
        self.save_giveaways()

        # Message de confirmation détaillé
        changes = []
        if new_end_time:
            paris_time = new_end_time.astimezone(PARIS_TZ)
            changes.append(f"🕐 **Nouvelle fin :** {paris_time.strftime('%d/%m/%Y à %H:%M')}")
        if new_description:
            changes.append(f"🎁 **Nouveau lot :** {new_description}")

        embed = discord.Embed(
            title="✅ Giveaway Modifié avec Succès",
            description="\n".join(changes),
            color=discord.Color.green()
        )

        # Ajouter des informations supplémentaires
        current_participants = len(view.participants)
        embed.add_field(
            name="📊 Informations",
            value=f"**Participants actuels :** {current_participants}\n**ID du giveaway :** `{message_id}`",
            inline=False
        )

        embed.timestamp = datetime.now(timezone.utc)

        await ctx.send(embed=embed)

    @commands.command()
    async def reroll(self, ctx, message_id: int):
        """Retirer un nouveau gagnant (max 3 jours après fin)"""
        if not self.is_staff(ctx.author):
            return await ctx.send("❌ Vous n'avez pas la permission d'utiliser cette commande.")

        message_id_str = str(message_id)
        finished_giveaway = self._finished_giveaways.get(message_id_str)

        if not finished_giveaway:
            return await ctx.send("❌ Aucun giveaway terminé trouvé avec cet ID.")

        # Vérifier si moins de 3 jours se sont écoulés
        finished_at = datetime.fromisoformat(finished_giveaway["finished_at"])
        if datetime.now(timezone.utc) - finished_at > timedelta(days=3):
            return await ctx.send("❌ Le reroll n'est possible que dans les 3 jours suivant la fin du giveaway.")

        participants = finished_giveaway["participants"]
        if not participants:
            return await ctx.send("❌ Aucun participant dans ce giveaway terminé.")

        new_winner_id = random.choice(participants)
        winner = ctx.guild.get_member(new_winner_id)

        # Mettre à jour le gagnant
        finished_giveaway["winner_id"] = new_winner_id
        self.save_finished_giveaways()

        embed = discord.Embed(
            title="🎲 Nouveau Gagnant !",
            description=f"Nouveau gagnant du giveaway **{finished_giveaway['description']}** :",
            color=discord.Color.purple()
        )

        if winner:
            embed.add_field(name="🏆 Gagnant", value=winner.mention, inline=False)
        else:
            embed.add_field(name="🏆 Gagnant", value=f"Utilisateur quitté (ID: {new_winner_id})", inline=False)

        await ctx.send(embed=embed)

    @commands.command()
    async def giveawaylist(self, ctx):
       """Liste les giveaways actifs"""
       # Vérifier si l'utilisateur est dans le staff
       if not self.bot.get_cog("StaffManager").is_staff(ctx.author):
           return await ctx.send("❌ Vous n'avez pas les permissions nécessaires pour utiliser cette commande.")

       self.load_giveaways()  # recharger pour s'assurer d'avoir les données à jour
       if not self._loaded_data:
           return await ctx.send("📭 Aucun giveaway actif actuellement.")

       # Compter les giveaways actifs avant de créer l'embed
       now_utc = datetime.now(timezone.utc)
       active_count = 0
       for mid, data in self._loaded_data.items():
           end_time = datetime.fromisoformat(data["end_time"]).replace(tzinfo=timezone.utc)
           if end_time >= now_utc:
               active_count += 1

       embed = discord.Embed(
           title=f"📋 Liste des Giveaways Actifs ({active_count})",
           color=discord.Color.blue()
       )

       count = 0
       for mid, data in self._loaded_data.items():
           end_time = datetime.fromisoformat(data["end_time"]).replace(tzinfo=timezone.utc)
           if end_time < now_utc:
               continue  # skip expired
           end_paris = end_time.astimezone(PARIS_TZ)
           description = data.get("description", "Lot non spécifié")
           participant_count = len(data.get("participants", []))
           embed.add_field(
               name=f"🎁 ID : {mid}",
               value=(
                   f"**Lot :** {description}\n"
                   f"**Participants :** {participant_count}\n"
                   f"**Se termine :** {end_paris.strftime('%d/%m/%Y à %H:%M')}"
               ),
               inline=False
           )
           count += 1

       if count == 0:
           return await ctx.send("📭 Aucun giveaway actif actuellement.")

       # Footer sans le total
       embed.set_footer(
           text=ctx.guild.name,
           icon_url=ctx.guild.icon.url if ctx.guild.icon else None
       )
       await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Giveaway(bot))
