import discord
from discord.ext import commands
import json
import os
import asyncio
import math
from datetime import datetime
from discord.ui import View, Button
from PIL import Image, ImageDraw, ImageFont
import io
import aiohttp

XP_FILE = "levels.json"

def is_staff_check():
    async def predicate(ctx):
        staff_cog = ctx.bot.get_cog("StaffManager")
        if not staff_cog:
            await ctx.send("⚠️ Le module StaffManager n'est pas chargé.")
            return False
        return staff_cog.is_staff(ctx.author)
    return commands.check(predicate)

LEVEL_ROLES = {
    10: "🔰 Novice",
    20: "💪 Actif",
    30: "⏰ Assidu",
    40: "⭐ Confirmé",
    50: "🪖 Amateur",
    60: "💂 Pillier",
    70: "⚔️ Vétéran",
    80: "🛡️ Pro",
    100: "🎖️ Légende"
}

def load_xp():
    if not os.path.isfile(XP_FILE):
        return {}
    with open(XP_FILE, "r") as f:
        return json.load(f)

def save_xp(data):
    with open(XP_FILE, "w") as f:
        json.dump(data, f, indent=4)

def calculate_level(xp):
    return int((xp / 100) ** 0.7)

def xp_needed(level):
    return int((level + 1) ** (1 / 0.7) * 100)

class Levels(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.xp_data = load_xp()
        self.last_message_time = {}

    def ensure_user(self, user_id):
        if str(user_id) not in self.xp_data:
            self.xp_data[str(user_id)] = {"xp": 0, "last_xp": 0}

    async def download_avatar(self, member):
        """Télécharge l'avatar du membre"""
        try:
            async with aiohttp.ClientSession() as session:
                avatar_url = member.avatar.url if member.avatar else member.default_avatar.url
                async with session.get(str(avatar_url)) as resp:
                    if resp.status == 200:
                        return await resp.read()
        except:
            pass
        return None

    async def create_rank_image(self, member, level, xp, rank, level_xp, xp_needed_for_next, progress_percent):
        """Crée une image personnalisée pour le rang avec une écriture très nette et grande"""
        # Dimensions encore plus grandes pour une meilleure netteté sur Discord
        width, height = 1200, 400

        # Créer l'image avec fond noir en haute résolution
        img = Image.new('RGB', (width, height), color='#1a1a1a')
        draw = ImageDraw.Draw(img)

        # Couleurs améliorées
        primary_color = '#FFFFFF'  # Blanc pur
        secondary_color = '#ffd700'  # Or pour les accents
        accent_color = '#00ff88'  # Vert plus vif
        bar_bg_color = '#2a2a2a'  # Gris foncé pour la barre

        try:
            # Polices BEAUCOUP plus grandes pour une excellente lisibilité sur Discord
            try:
                # Polices très grandes pour être parfaitement lisibles
                title_font = ImageFont.truetype("arial.ttf", 56)   # Énorme pour le titre
                text_font = ImageFont.truetype("arial.ttf", 38)    # Très grand pour le texte principal
                small_font = ImageFont.truetype("arial.ttf", 32)   # Grand pour les détails
                tiny_font = ImageFont.truetype("arial.ttf", 26)    # Moyen pour les petits détails
            except:
                # Fallback avec des tailles par défaut plus grandes
                title_font = ImageFont.load_default().font_variant(size=56)
                text_font = ImageFont.load_default().font_variant(size=38)
                small_font = ImageFont.load_default().font_variant(size=32)
                tiny_font = ImageFont.load_default().font_variant(size=26)

            # Avatar plus grand et mieux positionné
            avatar_size = 160
            if avatar_data := await self.download_avatar(member):
                avatar_img = Image.open(io.BytesIO(avatar_data))
                # Utiliser LANCZOS pour un redimensionnement de meilleure qualité
                avatar_img = avatar_img.resize((avatar_size, avatar_size), Image.Resampling.LANCZOS)

                # Créer un masque circulaire pour l'avatar
                mask = Image.new('L', (avatar_size, avatar_size), 0)
                mask_draw = ImageDraw.Draw(mask)
                mask_draw.ellipse((0, 0, avatar_size, avatar_size), fill=255)

                # Appliquer le masque
                avatar_img.putalpha(mask)
                img.paste(avatar_img, (60, 120), avatar_img)

                # Bordure dorée plus épaisse autour de l'avatar
                draw.ellipse(
                    [(55, 115), (55 + avatar_size + 10, 115 + avatar_size + 10)], 
                    outline=secondary_color, 
                    width=4
                )

            # Nom du membre (titre principal) - TRÈS GRAND et net
            member_name = member.display_name
            if len(member_name) > 15:
                member_name = member_name[:12] + "..."

            # Position du texte à droite de l'avatar avec plus d'espace
            text_x = 280

            # Titre avec le nom du membre - ÉNORME et avec ombre pour la netteté
            shadow_offset = 2
            # Ombre noire pour faire ressortir le texte
            draw.text((text_x + shadow_offset, 50 + shadow_offset), f"🏅 {member_name}", fill='#000000', font=title_font)
            draw.text((text_x, 50), f"🏅 {member_name}", fill=primary_color, font=title_font)

            # Niveau et rang sur la même ligne mais TRÈS GRANDS
            # Niveau avec ombre
            draw.text((text_x + shadow_offset, 120 + shadow_offset), f"Niveau {level}", fill='#000000', font=text_font)
            draw.text((text_x, 120), f"Niveau {level}", fill=accent_color, font=text_font)

            # Rang avec ombre
            rank_text = f"Rang #{rank}"
            draw.text((text_x + 320 + shadow_offset, 120 + shadow_offset), rank_text, fill='#000000', font=text_font)
            draw.text((text_x + 320, 120), rank_text, fill=secondary_color, font=text_font)

            # XP actuel TRÈS VISIBLE
            xp_text = f"XP Total: {xp:,}"
            draw.text((text_x + shadow_offset, 170 + shadow_offset), xp_text, fill='#000000', font=small_font)
            draw.text((text_x, 170), xp_text, fill=primary_color, font=small_font)

            # Barre de progression ENCORE plus grande et plus nette
            bar_x = text_x
            bar_y = 220
            bar_width = 600  # Plus large
            bar_height = 45  # Plus haute

            # Fond de la barre avec bordure plus nette
            draw.rounded_rectangle(
                [(bar_x, bar_y), (bar_x + bar_width, bar_y + bar_height)],
                radius=20,
                fill=bar_bg_color,
                outline='#404040',
                width=2
            )

            # Barre de progression remplie avec dégradé amélioré
            fill_width = int((progress_percent / 100) * (bar_width - 8))
            if fill_width > 0:
                # Gradient plus smooth avec plus d'étapes
                gradient_steps = min(fill_width // 5, 50)
                for i in range(gradient_steps):
                    # Dégradé du vert foncé au vert clair
                    green_value = int(100 + (155 * i / gradient_steps))
                    step_width = max(1, fill_width // gradient_steps)
                    step_x = bar_x + 4 + (i * step_width)

                    draw.rounded_rectangle(
                        [(step_x, bar_y + 4), (step_x + step_width + 1, bar_y + bar_height - 4)],
                        radius=15,
                        fill=f"#{green_value:02x}ff{green_value:02x}"
                    )

            # Texte de progression sur la barre - BEAUCOUP plus grand
            progress_text = f"{level_xp:,} / {xp_needed_for_next:,} XP"

            # Calculer la position centrale du texte
            bbox = draw.textbbox((0, 0), progress_text, font=small_font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            text_pos_x = bar_x + (bar_width - text_width) // 2
            text_pos_y = bar_y + (bar_height - text_height) // 2

            # Ombre plus prononcée pour le texte sur la barre
            draw.text((text_pos_x + 2, text_pos_y + 2), progress_text, fill='#000000', font=small_font)
            draw.text((text_pos_x, text_pos_y), progress_text, fill=primary_color, font=small_font)

            # Pourcentage de progression TRÈS VISIBLE
            percent_text = f"{progress_percent:.1f}%"
            draw.text((text_x + shadow_offset, bar_y + 55 + shadow_offset), percent_text, fill='#000000', font=small_font)
            draw.text((text_x, bar_y + 55), percent_text, fill=accent_color, font=small_font)

            # Rôle de niveau (si applicable) GRAND
            role_level = max((lvl for lvl in LEVEL_ROLES if level >= lvl), default=None)
            if role_level:
                role_text = f"Rôle: {LEVEL_ROLES[role_level]}"
                draw.text((text_x + 300 + shadow_offset, bar_y + 55 + shadow_offset), role_text, fill='#000000', font=small_font)
                draw.text((text_x + 300, bar_y + 55), role_text, fill=secondary_color, font=small_font)

            # Statistiques supplémentaires GRANDES et bien espacées
            stats_y = 320
            next_level_text = f"🎯 Prochain niveau: {level + 1}"
            draw.text((text_x + shadow_offset, stats_y + shadow_offset), next_level_text, fill='#000000', font=tiny_font)
            draw.text((text_x, stats_y), next_level_text, fill=primary_color, font=tiny_font)

            xp_to_next = xp_needed_for_next - level_xp
            remaining_text = f"📈 XP restant: {xp_to_next:,}"
            draw.text((text_x + 350 + shadow_offset, stats_y + shadow_offset), remaining_text, fill='#000000', font=tiny_font)
            draw.text((text_x + 350, stats_y), remaining_text, fill=accent_color, font=tiny_font)

            # Ligne décorative en bas plus épaisse
            draw.rectangle([(60, height - 25), (width - 60, height - 15)], fill=secondary_color)

            # Sauvegarder l'image en bytes avec la MEILLEURE qualité possible
            img_bytes = io.BytesIO()
            # Sauvegarder sans compression pour une netteté maximale
            img.save(img_bytes, format='PNG', optimize=False, compress_level=0)
            img_bytes.seek(0)

            return img_bytes

        except Exception as e:
            print(f"Erreur lors de la création de l'image: {e}")
            return None

    async def update_roles(self, member, old_level, new_level):
        guild_roles = {role.name: role for role in member.guild.roles}

        # Trouver le meilleur rôle (le plus haut niveau atteint)
        best_level = max((lvl for lvl in LEVEL_ROLES if new_level >= lvl), default=None)
        target_role = guild_roles.get(LEVEL_ROLES.get(best_level)) if best_level else None

        # Supprimer tous les rôles de niveau
        for lvl, role_name in LEVEL_ROLES.items():
            role = guild_roles.get(role_name)
            if role and role in member.roles:
                await member.remove_roles(role, reason="Mise à jour des rôles de niveau")

        # Ajouter le seul rôle que le membre mérite
        if target_role and target_role not in member.roles:
            await member.add_roles(target_role, reason="Rôle de niveau attribué")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        user_id = str(message.author.id)
        now = datetime.utcnow().timestamp()
        self.ensure_user(user_id)

        # Limite : 1 XP par minute
        if now - self.xp_data[user_id].get("last_xp", 0) < 60:
            return

        self.xp_data[user_id]["last_xp"] = now
        old_xp = self.xp_data[user_id]["xp"]
        old_level = calculate_level(old_xp)

        self.xp_data[user_id]["xp"] += 15
        new_level = calculate_level(self.xp_data[user_id]["xp"])

        if new_level > old_level:
            await message.channel.send(f"🎉 {message.author.mention} est monté au niveau **{new_level}** !")

        await self.update_roles(message.author, old_level, new_level)
        save_xp(self.xp_data)

    @commands.command()
    async def rank(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        user_id = str(member.id)
        self.ensure_user(user_id)

        # Récupération XP + niveau
        xp = self.xp_data[user_id]["xp"]
        level = calculate_level(xp)

        # XP pour le niveau courant
        level_start_xp = int((level ** (1 / 0.7)) * 100)
        next_level_xp = xp_needed(level)
        level_xp = xp - level_start_xp  # XP gagné dans ce niveau
        xp_needed_for_next = next_level_xp - level_start_xp  # XP requis pour ce niveau

        # Pourcentage de progression
        progress_percent = (level_xp / xp_needed_for_next) * 100 if xp_needed_for_next > 0 else 100

        # Classement
        leaderboard = sorted(self.xp_data.items(), key=lambda x: x[1]["xp"], reverse=True)
        rank = next((i for i, (uid, _) in enumerate(leaderboard, start=1) if uid == user_id), None)

        # Créer l'image personnalisée
        rank_image = await self.create_rank_image(
            member, level, xp, rank, level_xp, xp_needed_for_next, progress_percent
        )

        if rank_image:
            # Envoyer l'image
            file = discord.File(rank_image, filename=f"rank_{member.id}.png")
            await ctx.send(file=file)
        else:
            # Fallback vers l'embed classique si l'image ne peut pas être créée
            embed = discord.Embed(
                title=f"🏅 Statistiques de {member.display_name}",
                color=discord.Color.blue()
            )
            embed.add_field(name="Niveau", value=f"**{level}**\n`{level_xp} / {xp_needed_for_next}`", inline=True)
            embed.add_field(name="Rang", value=f"**#{rank}**\n`{xp} XP`", inline=True)

            # Barre de progression textuelle
            progress = int((level_xp / xp_needed_for_next) * 20)
            bar = "🟦" * progress + "⬛" * (20 - progress)
            embed.add_field(name="Progression", value=f"{bar}", inline=False)

            await ctx.send(embed=embed)

    @commands.command()
    async def topxp(self, ctx):
        leaderboard = sorted(self.xp_data.items(), key=lambda x: x[1]["xp"], reverse=True)
        pages = []

        for i in range(0, len(leaderboard), 10):
            embed = discord.Embed(title="🏆 Classement XP", color=discord.Color.gold())
            for index, (user_id, data) in enumerate(leaderboard[i:i+10], start=i+1):
                try:
                    user = await self.bot.fetch_user(int(user_id))
                    embed.add_field(name=f"{index}. {user.name}", value=f"XP: {data['xp']}", inline=False)
                except:
                    embed.add_field(name=f"{index}. Utilisateur inconnu", value=f"XP: {data['xp']}", inline=False)
            pages.append(embed)

        class Paginator(View):
            def __init__(self):
                super().__init__(timeout=60)
                self.current = 0
                self.message = None

            async def update(self, interaction):
                await interaction.response.edit_message(embed=pages[self.current], view=self)

            @discord.ui.button(label="◀ Précédent", style=discord.ButtonStyle.secondary)
            async def previous(self, interaction: discord.Interaction, button: Button):
                if interaction.user != ctx.author:
                    return await interaction.response.send_message("Tu ne peux pas utiliser ces boutons.", ephemeral=True)
                if self.current > 0:
                    self.current -= 1
                    await self.update(interaction)

            @discord.ui.button(label="Suivant ▶", style=discord.ButtonStyle.secondary)
            async def next(self, interaction: discord.Interaction, button: Button):
                if interaction.user != ctx.author:
                    return await interaction.response.send_message("Tu ne peux pas utiliser ces boutons.", ephemeral=True)
                if self.current < len(pages) - 1:
                    self.current += 1
                    await self.update(interaction)

        view = Paginator()
        view.message = await ctx.send(embed=pages[0], view=view)

    @commands.command()
    @is_staff_check()
    async def addxp(self, ctx, member: discord.Member, amount: int):
        user_id = str(member.id)
        self.ensure_user(user_id)

        old_level = calculate_level(self.xp_data[user_id]["xp"])
        self.xp_data[user_id]["xp"] += amount
        new_level = calculate_level(self.xp_data[user_id]["xp"])

        await self.update_roles(member, old_level, new_level)
        save_xp(self.xp_data)
        await ctx.send(f"✅ {amount} XP ajoutés à {member.display_name}.")

    @commands.command()
    @is_staff_check()
    async def removexp(self, ctx, member: discord.Member, amount: int):
        user_id = str(member.id)
        self.ensure_user(user_id)

        old_level = calculate_level(self.xp_data[user_id]["xp"])
        self.xp_data[user_id]["xp"] = max(0, self.xp_data[user_id]["xp"] - amount)
        new_level = calculate_level(self.xp_data[user_id]["xp"])

        await self.update_roles(member, old_level, new_level)
        save_xp(self.xp_data)
        await ctx.send(f"✅ {amount} XP retirés à {member.display_name}.")

    @commands.command()
    @is_staff_check()
    async def resetxp(self, ctx, member: discord.Member):
        user_id = str(member.id)
        self.ensure_user(user_id)

        old_level = calculate_level(self.xp_data[user_id]["xp"])
        self.xp_data[user_id]["xp"] = 0
        new_level = 0

        await self.update_roles(member, old_level, new_level)
        save_xp(self.xp_data)
        await ctx.send(f"🔄 XP de {member.display_name} réinitialisé.")

async def setup(bot):
    await bot.add_cog(Levels(bot))
