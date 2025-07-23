import discord
from discord.ext import commands
import json
import os


STAFF_FILE = "staff_roles.json"

class StaffManager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.staff_roles = self.load_staff_roles()

    def load_staff_roles(self):
        if os.path.exists(STAFF_FILE):
            with open(STAFF_FILE, "r") as f:
                return json.load(f)
        return {}

    def save_staff_roles(self):
        with open(STAFF_FILE, "w") as f:
            json.dump(self.staff_roles, f, indent=4)

    def is_staff(self, member: discord.Member):
        guild_id = str(member.guild.id)
        if guild_id not in self.staff_roles:
            return False
        return any(role.id in self.staff_roles[guild_id] for role in member.roles)

    def is_guild_owner():
        async def predicate(ctx):
            return ctx.author == ctx.guild.owner
        return commands.check(predicate)

    @commands.command(name="addstaff")
    @is_guild_owner()
    async def add_staff(self, ctx, *roles: discord.Role):
        guild_id = str(ctx.guild.id)
        if guild_id not in self.staff_roles:
            self.staff_roles[guild_id] = []

        added = 0
        for role in roles:
            if role.id not in self.staff_roles[guild_id]:
                self.staff_roles[guild_id].append(role.id)
                added += 1

        self.save_staff_roles()
        await ctx.send(f"✅ {added} rôle(s) ajouté(s) à la liste des rôles staff.")

    @commands.command(name="removestaff")
    @is_guild_owner()
    async def remove_staff(self, ctx, *roles: discord.Role):
        guild_id = str(ctx.guild.id)
        if guild_id not in self.staff_roles:
            return await ctx.send("❌ Aucun rôle staff configuré.")

        removed = 0
        for role in roles:
            if role.id in self.staff_roles[guild_id]:
                self.staff_roles[guild_id].remove(role.id)
                removed += 1

        self.save_staff_roles()
        await ctx.send(f"🗑️ {removed} rôle(s) retiré(s) de la liste staff.")

    @commands.command(name="resetstaff")
    @is_guild_owner()
    async def reset_staff(self, ctx):
        guild_id = str(ctx.guild.id)
        if guild_id in self.staff_roles:
            self.staff_roles[guild_id] = []
            self.save_staff_roles()
            await ctx.send("♻️ La liste des rôles staff a été réinitialisée.")
        else:
            await ctx.send("❌ Aucun rôle staff n’est défini pour ce serveur.")

    @commands.command(name="stafflist")
    @is_guild_owner()
    async def stafflist(self, ctx):
        guild_id = str(ctx.guild.id)
        if guild_id not in self.staff_roles or not self.staff_roles[guild_id]:
            return await ctx.send("🚫 Aucun rôle staff n’a été défini.")

        role_mentions = []
        for role_id in self.staff_roles[guild_id]:
            role = ctx.guild.get_role(role_id)
            if role:
                role_mentions.append(role.mention)

        if not role_mentions:
            return await ctx.send("⚠️ Aucun des rôles staff enregistrés n’a été trouvé sur le serveur.")

        embed = discord.Embed(
            title="👮‍♂️ Rôles du Staff",
            description="\n".join(role_mentions),
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)

# ✅ Décorateur à utiliser dans d'autres fichiers (import depuis ce module)
def is_admin_or_staff():
    async def predicate(ctx):
        if ctx.author.guild_permissions.administrator:
            return True
        staff_cog = ctx.bot.get_cog("StaffManager")
        if not staff_cog:
            return False
        return staff_cog.is_staff(ctx.author)
    return commands.check(predicate)

# Fonction setup pour charger le cog
async def setup(bot):
    await bot.add_cog(StaffManager(bot))
