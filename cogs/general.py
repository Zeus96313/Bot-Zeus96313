import discord
import time
import random
from discord.ext import commands
from discord.ui import View, button, Button
from discord import Embed, ButtonStyle, Interaction

class HelpView(View):
    def __init__(self):
        super().__init__(timeout=120)
        self.embed = self.build_main_embed()

    def build_main_embed(self):
        embed = Embed(
            title="📘 Aide - Catégories de commandes",
            description="Clique sur un emoji ci-dessous pour afficher les commandes de cette catégorie.",
            color=0x3498db
        )
        embed.add_field(name="🎮 Commandes générales", value="Afficher ➡️", inline=False)
        embed.add_field(name="🎫 Commandes de tickets", value="Afficher ➡️", inline=False)
        embed.add_field(name="🧹 Commandes de modération", value="Afficher ➡️", inline=False)
        embed.add_field(name="🎙️ Commandes vocales", value="Afficher ➡️", inline=False)
        embed.add_field(name="📈 Niveaux & XP", value="Afficher ➡️", inline=False)
        embed.add_field(name="🎁 Giveaways", value="Afficher ➡️", inline=False)
        embed.add_field(name="🛠️ Commandes ADMIN", value="Afficher ➡️", inline=False)
        embed.set_footer(text="Tu as 2 minutes pour interagir avec les boutons.")
        return embed

    def get_category_embed(self, name):
        embed = Embed(title=f"{name}", color=0x3498db)
        if name == "🎮 Commandes générales":
            embed.description = (
                "!ping - Test de latence\n"
                "!pileouface - Lance une pièce\n"
                "!quoi - Répond avec humour\n"
                "!userinfo - Infos d'un utilisateur\n"
                "!avatar [@membre] - Affiche l'avatar\n"
                "!serveurinfo - Infos sur le serveur\n"
                "!say <x> <message> - Répète un message x fois (max 10)\n"
            )
        elif name == "🎫 Commandes de tickets":
            embed.description = (
                "!ticket - Crée un ticket\n"
                "!close - Ferme un ticket\n"
                "!addticket <@membre> - Ajoute un membre au ticket\n"
                "!removeticket <@membre> - Retire un membre du ticket\n"
                "!renameticket <nom> - Renomme le ticket"
            )
        elif name == "🧹 Commandes de modération":
            embed.description = (
                "!clear <nombre> - Supprime des messages\n"
                "!purge <@membre> - Supprime ses messages\n"
                "!warn <@membre> <raison> - Avertir un membre\n"
                "!infractions <@membre> - Voir les avertissements\n"
                "!clearwarns <@membre> - Supprimer ses avertissements\n"
                "!tempmute <@membre> <durée> - Mute temporairement\n"
                "!unmute <@membre> - Retirer manuellement le mute\n"
                "!mutelist - Liste des membres mutés\n"
                "!ban <@membre> - Bannir un membre\n"
                "!kick <@membre> - Expulser un membre\n"
                "!nuke - Réinitialiser un salon\n"
                "!antiinvite on/off - Anti-lien"
            )
        elif name == "🎙️ Commandes vocales":
            embed.description = (
                "!time <ID_du_salon_vocal> - Temps des utilisateur dans un salon vocal\n"
                "!voctime - Ton temps cumulé ce mois\n"
                "!voclist - Classement vocal du mois\n"
                "!setupvocal <id catégorie> - Créer système vocal\n"
                "!removevocal - Supprimer système vocal\n"
                "!renamevocal - Renommer ton salon vocal"
            )
        elif name == "📈 Niveaux & XP":
            embed.description = (
                "!rank - Voir ton niveau, XP et rank\n"
                "!topxp - Classement général XP\n"
                "!addxp @membre <xp> - ➕ Ajouter de l'XP\n"
                "!removexp @membre <xp> - ➖ Retirer de l'XP\n"
                "!resetxp @membre - 🔄 Réinitialiser l'XP"
            )
        elif name == "🎁 Giveaways":
            embed.description = (
            "!giveaway <JJ/MM/AAAA HH:MM> <lot> - Lance un giveaway\n"
            "!cancelgiveaway <id_message> - Annule un giveaway actif\n"
            "!editgiveaway <id_message> <nouvelle_durée> <nouveau_lot> - Modifier un giveaway\n"
            "!pg <id_message> - Voir les participants à un giveaway\n"
            "!reroll <id_message> - Retirer un nouveau gagnant (max 3 jours après fin)\n"
            "!giveawaylist - Liste les giveaways actifs"
        )
        elif name == "🛠️ Commandes ADMIN":
            embed.description = (
                    "**!addstaff @role1 @role2...** - Ajouter des rôles au staff\n"
                    "**!removestaff @role1 @role2...** - Supprimer des rôles du staff\n"
                    "**!resetstaff** - Réinitialiser tous les rôles staff\n"
                    "**!stafflist** - Voir les rôles ayant accès aux commandes staff\n"
                    "**!setprefix <préfixe>** - Modifier le préfixe du bot"
                )

        return embed

    @button(label="🎮", style=ButtonStyle.blurple)
    async def general_button(self, interaction: Interaction, button: Button):
        await interaction.response.edit_message(embed=self.get_category_embed("🎮 Commandes générales"), view=self)

    @button(label="🎫", style=ButtonStyle.blurple)
    async def ticket_button(self, interaction: Interaction, button: Button):
        await interaction.response.edit_message(embed=self.get_category_embed("🎫 Commandes de tickets"), view=self)

    @button(label="🧹", style=ButtonStyle.blurple)
    async def mod_button(self, interaction: Interaction, button: Button):
        await interaction.response.edit_message(embed=self.get_category_embed("🧹 Commandes de modération"), view=self)

    @button(label="🎙️", style=ButtonStyle.blurple)
    async def vocal_button(self, interaction: Interaction, button: Button):
        await interaction.response.edit_message(embed=self.get_category_embed("🎙️ Commandes vocales"), view=self)

    @button(label="📈", style=ButtonStyle.blurple)
    async def xp_button(self, interaction: Interaction, button: Button):
        await interaction.response.edit_message(embed=self.get_category_embed("📈 Niveaux & XP"), view=self)

    @button(label="🎁", style=ButtonStyle.blurple)
    async def giveaway_button(self, interaction: Interaction, button: Button):
        await interaction.response.edit_message(embed=self.get_category_embed("🎁 Giveaways"), view=self)

    @button(label="🛠️", style=ButtonStyle.red)
    async def admin_button(self, interaction: Interaction, button: Button):
        await interaction.response.edit_message(embed=self.get_category_embed("🛠️ Commandes ADMIN"), view=self)

    @button(label="🏠 Accueil", style=ButtonStyle.gray)
    async def home_button(self, interaction: Interaction, button: Button):
        await interaction.response.edit_message(embed=self.embed, view=self)

class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.user_last_use = {}

    @commands.command(name="ping")
    async def ping(self, ctx):
        latency = round(self.bot.latency * 1000)
        await ctx.send(f"Pong ! 🏓 {latency}ms")

    @commands.command()
    async def pileouface(self, ctx):
        result = random.choice(["🪙 Pile", "🪙 Face"])
        await ctx.send(f"{ctx.author.mention} a lancé la pièce... Résultat : **{result}**")

    @commands.command(name="quoi")
    async def quoi(self, ctx):
        await ctx.send("Feur 😏")

    @commands.command(name="userinfo")
    async def userinfo(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        embed = discord.Embed(title=f"Infos de {member}", color=discord.Color.blue())
        embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
        embed.add_field(name="ID", value=member.id)
        embed.add_field(name="Rejoint le", value=member.joined_at.strftime("%d/%m/%Y"))
        embed.add_field(name="Créé le", value=member.created_at.strftime("%d/%m/%Y"))
        roles = [role for role in member.roles if role != ctx.guild.default_role]
        roles = sorted(roles, key=lambda r: r.position, reverse=True)
        embed.add_field(
            name=f"Rôles ({len(roles)})",
            value=", ".join(role.mention for role in roles) or "Aucun",
            inline=False
        )
        await ctx.send(embed=embed)

    @commands.command(name="avatar")
    async def avatar(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        embed = discord.Embed(
            description=f"**Avatar de {member.mention}**",
            color=discord.Color.blurple()
        )
        embed.set_image(url=member.avatar.url if member.avatar else member.default_avatar.url)
        embed.set_footer(text=f"Requête par {ctx.author}", icon_url=ctx.author.avatar.url)
        await ctx.send(embed=embed)

    @commands.command(name="serveurinfo")
    async def serveurinfo(self, ctx):
        guild = ctx.guild
        embed = discord.Embed(title="📊 Informations du serveur", color=discord.Color.green())
        embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
        embed.add_field(name="Nom", value=guild.name, inline=True)
        embed.add_field(name="ID", value=guild.id, inline=True)
        embed.add_field(name="Membres", value=guild.member_count, inline=True)
        embed.add_field(name="Créé le", value=guild.created_at.strftime("%d/%m/%Y"), inline=True)
        embed.add_field(name="Propriétaire", value=guild.owner.mention, inline=True)
        await ctx.send(embed=embed)

    @commands.command(name="say")
    async def say(self, ctx, repetitions: int, *, message: str):
        if repetitions < 1 or repetitions > 10:
            return await ctx.send("❌ Tu dois répéter entre 1 et 10 fois.")

        if "say" in message.lower():
            return await ctx.send("❌ Tu ne peux pas utiliser `say` dans le message.")

        user_id = ctx.author.id
        now = time.time()
        last_use = self.user_last_use.get(user_id, 0)

        if now - last_use < 5:
            return await ctx.send("🕐 Tu dois attendre 5 secondes entre deux `!say`.")

        self.user_last_use[user_id] = now

        try:
            await ctx.message.delete()
        except:
            pass

        for _ in range(repetitions):
            await ctx.send(message)

    @commands.command(name="aide")
    async def aide(self, ctx):
        """Affiche la liste des commandes disponibles avec catégories interactives"""
        # Supprimer le message de commande
        try:
            await ctx.message.delete()
        except:
            pass

        view = HelpView()
        await ctx.send(embed=view.embed, view=view)

# Fonction setup obligatoire pour le chargement du cog
async def setup(bot):
    await bot.add_cog(General(bot))
