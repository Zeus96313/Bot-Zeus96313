import discord
from discord.ext import commands
import json
import os
import asyncio
import re

WARN_FILE = "warns.json"
MUTE_FILE = "mutes.json"
STAFF_FILE = "staff_roles.json"

def is_staff(member):
    if not os.path.exists(STAFF_FILE):
        return False
    with open(STAFF_FILE, "r") as f:
        data = json.load(f)
    role_ids = data.get(str(member.guild.id), [])
    return any(role.id in role_ids for role in member.roles)

def is_admin_or_staff():
    async def predicate(ctx):
        return ctx.author.guild_permissions.administrator or is_staff(ctx.author)
    return commands.check(predicate)

def load_json(path, default={}):
    if not os.path.exists(path):
        with open(path, "w") as f:
            json.dump(default, f)
    with open(path, "r") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=4)

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.warns = load_json(WARN_FILE)
        self.mutes = load_json(MUTE_FILE)
        self.anti_invite_enabled = {}
        self.bot.loop.create_task(self.check_mutes())

    def parse_duration(self, duration_str):
        match = re.match(r"(\d+)([smhd])", duration_str)
        if not match:
            return None
        num, unit = match.groups()
        return int(num) * {"s": 1, "m": 60, "h": 3600, "d": 86400}.get(unit, 0)

    async def get_or_create_mute_role(self, guild):
        mute_role = discord.utils.get(guild.roles, name="Muted")
        if not mute_role:
            mute_role = await guild.create_role(name="Muted", reason="Rôle mute automatique")
        for channel in guild.channels:
            overwrite = channel.overwrites_for(mute_role)
            overwrite.send_messages = False
            overwrite.speak = False
            try:
                await channel.set_permissions(mute_role, overwrite=overwrite)
            except discord.Forbidden:
                pass
        return mute_role

    async def create_log_channel_if_needed(self, guild):
        existing = discord.utils.get(guild.text_channels, name="🔫｜mod-logs")
        if not existing:
            try:
                await guild.create_text_channel("🔫｜mod-logs", reason="Salon de logs auto-créé")
            except discord.Forbidden:
                print(f"[WARN] Impossible de créer mod-logs sur {guild.name} (permissions manquantes)")

    async def log_action(self, ctx, action, user=None, reason=None):
        await self.create_log_channel_if_needed(ctx.guild)
        log_channel = discord.utils.get(ctx.guild.text_channels, name="🔫｜mod-logs")
        if log_channel:
            embed = discord.Embed(title=f"🔧 {action}", color=0xe67e22)
            embed.add_field(name="Modérateur", value=ctx.author.mention, inline=True)
            if user:
                embed.add_field(name="Cible", value=user.mention, inline=True)
            if reason:
                embed.add_field(name="Raison", value=reason, inline=False)
            await log_channel.send(embed=embed)

    async def unmute_member(self, guild, member):
        mute_role = await self.get_or_create_mute_role(guild)
        await member.remove_roles(mute_role)
        self.mutes.pop(str(member.id), None)
        save_json(MUTE_FILE, self.mutes)

    async def check_mutes(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            now = asyncio.get_event_loop().time()
            to_unmute = []
            for uid, data in list(self.mutes.items()):
                if now >= data["end_time"]:
                    guild = self.bot.get_guild(data["guild"])
                    if guild:
                        member = guild.get_member(int(uid))
                        if member:
                            await self.unmute_member(guild, member)
            await asyncio.sleep(10)

    # ------------------ COMMANDES ------------------

    @commands.command()
    @is_admin_or_staff()
    async def clear(self, ctx, amount: int):
           await ctx.channel.purge(limit=amount + 1)
           await ctx.send(f"🧹 {amount} messages supprimés.", delete_after=3)


    @commands.command()
    @is_admin_or_staff()  # ou @commands.has_permissions(manage_messages=True)
    async def purge(self, ctx, member: discord.Member):
        def is_user(m): return m.author == member
        deleted = await ctx.channel.purge(limit=100, check=is_user)
        await ctx.send(f"🧹 {len(deleted)} messages de {member.display_name} supprimés.", delete_after=3)

    @commands.command()
    @is_admin_or_staff()  # ou @commands.has_permissions(manage_messages=True)
    async def warn(self, ctx, member: discord.Member, *, reason: str = "Aucune raison"):
        uid = str(member.id)
        self.warns.setdefault(uid, []).append(reason)
        save_json(WARN_FILE, self.warns)
        await ctx.send(f"⚠️ {member.mention} a été averti : {reason}")
        await self.log_action(ctx, "Warn", user=member, reason=reason)

    @commands.command()
    @is_admin_or_staff()  # facultatif
    async def infractions(self, ctx, member: discord.Member):
        uid = str(member.id)
        reasons = self.warns.get(uid, [])
        if not reasons:
            return await ctx.send("✅ Aucun avertissement.")
        embed = discord.Embed(title=f"📄 Avertissements de {member.display_name}", color=discord.Color.orange())
        for i, r in enumerate(reasons, 1):
            embed.add_field(name=f"Infraction {i}", value=r, inline=False)
        await ctx.send(embed=embed)

    @commands.command()
    @is_admin_or_staff()  # ou @commands.has_permissions(manage_messages=True)
    async def clearwarns(self, ctx, member: discord.Member):
        uid = str(member.id)
        self.warns.pop(uid, None)
        save_json(WARN_FILE, self.warns)
        await ctx.send(f"🗑️ Tous les avertissements de {member.display_name} ont été supprimés.")
        await self.log_action(ctx, "Clear Warns", user=member)

    @commands.command()
    @is_admin_or_staff()  # ou @commands.has_permissions(manage_roles=True)
    async def tempmute(self, ctx, member: discord.Member, duration: str, *, reason="Aucune raison"):
        seconds = self.parse_duration(duration)
        if not seconds:
            return await ctx.send("⏱️ Format invalide. Utilise par ex : `10s`, `5m`, `2h`, `1d`.")

        mute_role = await self.get_or_create_mute_role(ctx.guild)
        await member.add_roles(mute_role, reason=reason)
        end_time = asyncio.get_event_loop().time() + seconds

        self.mutes[str(member.id)] = {
            "guild": ctx.guild.id,
            "end_time": end_time
        }
        save_json(MUTE_FILE, self.mutes)

        await ctx.send(f"🔇 {member.mention} a été mute pour `{duration}`.")
        await self.log_action(ctx, "Temp Mute", user=member, reason=reason)

    @commands.command()
    @is_admin_or_staff()  # ou @commands.has_permissions(manage_roles=True)
    async def unmute(self, ctx, member: discord.Member):
        await self.unmute_member(ctx.guild, member)
        await ctx.send(f"🔈 {member.mention} a été unmute.")
        await self.log_action(ctx, "Unmute", user=member)

    @commands.command()
    @is_admin_or_staff()  # ou @commands.has_permissions(manage_roles=True)
    async def mutelist(self, ctx):
        if not self.mutes:
            return await ctx.send("✅ Aucun membre n'est actuellement mute.")

        now = asyncio.get_event_loop().time()
        embed = discord.Embed(title="🔇 Membres Mutés", color=discord.Color.red())

        for uid, data in self.mutes.items():
            member = ctx.guild.get_member(int(uid))
            if member:
                remaining = int(data["end_time"] - now)
                if remaining <= 0:
                    continue
                minutes, seconds = divmod(remaining, 60)
                hours, minutes = divmod(minutes, 60)
                days, hours = divmod(hours, 24)

                time_parts = []
                if days: time_parts.append(f"{days}j")
                if hours: time_parts.append(f"{hours}h")
                if minutes: time_parts.append(f"{minutes}m")
                if seconds: time_parts.append(f"{seconds}s")
                time_str = ' '.join(time_parts)

                embed.add_field(name=member.display_name, value=f"Temps restant : `{time_str}`", inline=False)

        await ctx.send(embed=embed)


    @commands.command()
    @is_admin_or_staff()  # Ou @commands.has_permissions(ban_members=True)
    async def ban(self, ctx, member: discord.Member, *, reason="Aucune raison"):
        try:
            await member.ban(reason=reason)
            await ctx.send(f"⛔ {member.display_name} a été banni.")
            await self.log_action(ctx, "Ban", user=member, reason=reason)
        except discord.Forbidden:
            await ctx.send("❌ Je n'ai pas la permission de bannir ce membre.")

    @commands.command()
    @is_admin_or_staff()  # Ou @commands.has_permissions(kick_members=True)
    async def kick(self, ctx, member: discord.Member, *, reason="Aucune raison"):
        try:
            await member.kick(reason=reason)
            await ctx.send(f"👢 {member.display_name} a été kick.")
            await self.log_action(ctx, "Kick", user=member, reason=reason)
        except discord.Forbidden:
            await ctx.send("❌ Je n'ai pas la permission d'expulser ce membre.")

    @commands.command()
    @is_admin_or_staff()  # Ou @commands.has_permissions(administrator=True)
    async def nuke(self, ctx):
        try:
            new_channel = await ctx.channel.clone()
            await ctx.channel.delete()
            await new_channel.send("💥 Ce salon a été nuked !")
        except discord.Forbidden:
            await ctx.send("❌ Je ne peux pas cloner ou supprimer ce salon.")

    @commands.command()
    @is_admin_or_staff()  # Ou @commands.has_permissions(administrator=True)
    async def antiinvite(self, ctx, mode: str):
        mode = mode.lower()
        if mode == "on":
            self.anti_invite_enabled[ctx.guild.id] = True
            await ctx.send("🚫 Anti-invite activé.")
        elif mode == "off":
            self.anti_invite_enabled[ctx.guild.id] = False
            await ctx.send("✅ Anti-invite désactivé.")
        else:
            await ctx.send("❌ Utilise : `!antiinvite on` ou `!antiinvite off`")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        if self.anti_invite_enabled.get(message.guild.id, False):
            if "discord.gg/" in message.content or "discord.com/invite/" in message.content:
                try:
                    await message.delete()
                    await message.channel.send(
                        f"⚠️ {message.author.mention}, les liens d’invitation ne sont pas autorisés.",
                        delete_after=5
                    )
                except discord.Forbidden:
                    pass


# Setup function for the bot to load the cog
async def setup(bot):
    await bot.add_cog(Moderation(bot))
