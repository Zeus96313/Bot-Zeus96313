import discord
from discord.ext import commands, tasks
from discord.utils import get
from datetime import datetime
import json
import os

VOCAL_STATS_FILE = "vocstats.json"
VOCAL_CONFIG_FILE = "vocal_config.json"

MONTHS_FR = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre"
]

def is_staff_check():
    async def predicate(ctx):
        staff_cog = ctx.bot.get_cog("StaffManager")
        if not staff_cog:
            await ctx.send("⚠️ Le module StaffManager n'est pas chargé.")
            return False
        return staff_cog.is_staff(ctx.author)
    return commands.check(predicate)

def load_json(file):
    if not os.path.exists(file):
        with open(file, "w") as f:
            json.dump({}, f)
    with open(file, "r") as f:
        return json.load(f)

def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=4)

def format_duration(seconds):
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    sec = seconds % 60
    return f"{hours}h {minutes}m {sec}s"

class Vocal(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.voice_data = load_json(VOCAL_STATS_FILE)
        self.config = load_json(VOCAL_CONFIG_FILE)
        self.user_channels = {}  # utilisateur_id: salon
        self.check_month_reset.start()

    def format_duration(seconds):
        minutes, seconds = divmod(int(seconds), 60)
        hours, minutes = divmod(minutes, 60)
        return f"{hours}h {minutes}m {seconds}s"

    def cog_unload(self):
        self.check_month_reset.cancel()

    def update_user(self, member_id, duration):
        uid = str(member_id)
        if uid not in self.voice_data:
            self.voice_data[uid] = {"total": 0, "start": 0, "monthly": 0}
        self.voice_data[uid]["total"] += duration
        self.voice_data[uid]["monthly"] += duration
        self.voice_data[uid]["start"] = 0
        save_json(VOCAL_STATS_FILE, self.voice_data)

    def start_session(self, member_id):
        uid = str(member_id)
        if uid not in self.voice_data:
            self.voice_data[uid] = {"total": 0, "start": 0, "monthly": 0}
        self.voice_data[uid]["start"] = datetime.utcnow().timestamp()
        save_json(VOCAL_STATS_FILE, self.voice_data)

    def stop_session(self, member_id):
        uid = str(member_id)
        now = datetime.utcnow().timestamp()
        start = self.voice_data.get(uid, {}).get("start", 0)
        if start:
            duration = now - start
            self.update_user(member_id, duration)

    @tasks.loop(hours=1)
    async def check_month_reset(self):
        now = datetime.utcnow()
        if now.day == 1 and now.hour == 0:
            for uid in self.voice_data:
                self.voice_data[uid]['monthly'] = 0
            save_json(VOCAL_STATS_FILE, self.voice_data)

    @commands.command()
    async def voctime(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        uid = str(member.id)
        seconds = self.voice_data.get(uid, {}).get("monthly", 0)
        embed = discord.Embed(
            title="🕒 Temps vocal",
            description=f"{member.mention} a passé {format_duration(seconds)} en vocal ce mois-ci.",
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)

    @commands.command()
    async def voclist(self, ctx):
        sorted_users = sorted(self.voice_data.items(), key=lambda x: x[1].get("monthly", 0), reverse=True)
        desc = ""
        for i, (uid, data) in enumerate(sorted_users[:10], 1):
            user = ctx.guild.get_member(int(uid))
            if user:
                desc += f"**{i}.** {user.mention} - {format_duration(data['monthly'])}\n"

        mois = MONTHS_FR[datetime.utcnow().month - 1].capitalize()
        embed = discord.Embed(
            title=f"📊 Classement vocal - {mois}",
            description=desc or "Aucune donnée disponible.",
            color=discord.Color.gold()
        )
        await ctx.send(embed=embed)

    @commands.command()
    @is_staff_check()
    async def time(self, ctx, channel_id: int):
        channel = ctx.guild.get_channel(channel_id)
        if not channel or not isinstance(channel, discord.VoiceChannel):
            return await ctx.send("❌ Salon vocal invalide. Vérifie l'ID.")
        members = channel.members
        if not members:
            return await ctx.send("👥 Personne n'est actuellement dans ce salon.")
        embed = discord.Embed(title=f"⏱️ Temps en vocal - {channel.name}", color=discord.Color.blue())
        now = datetime.utcnow().timestamp()
        for member in members:
            uid = str(member.id)
            start = self.voice_data.get(uid, {}).get("start", 0)
            if start:
                duration = now - start
                embed.add_field(name=member.display_name, value=format_duration(duration), inline=False)
            else:
                embed.add_field(name=member.display_name, value="⏳ Aucune donnée disponible", inline=False)
        await ctx.send(embed=embed)

    @commands.command()
    @is_staff_check()
    async def setupvocal(self, ctx, *, category: discord.CategoryChannel = None):
        if category is None:
            await ctx.send("❌ Veuillez mentionner une **catégorie existante**.")
            return
        overwrites = {
            ctx.guild.default_role: discord.PermissionOverwrite(connect=True),
        }
        channel = await ctx.guild.create_voice_channel("➕ Créer un salon vocal", overwrites=overwrites, category=category)
        self.config[str(ctx.guild.id)] = {"parent_id": category.id, "channel_id": channel.id}
        save_json(VOCAL_CONFIG_FILE, self.config)
        await ctx.send(f"✅ Salon vocal créateur créé dans {category.name} : {channel.mention}")

    @commands.command()
    @is_staff_check()
    async def removevocal(self, ctx):
        guild_id = str(ctx.guild.id)
        if guild_id in self.config:
            channel_id = self.config[guild_id]["channel_id"]
            channel = ctx.guild.get_channel(channel_id)
            if channel:
                await channel.delete()
            del self.config[guild_id]
            save_json(VOCAL_CONFIG_FILE, self.config)
            await ctx.send("❌ Salon vocal supprimé.")
        else:
            await ctx.send("Aucun système vocal actif.")

    @commands.command()
    async def renamevocal(self, ctx, *, name: str):
        channel = ctx.author.voice.channel if ctx.author.voice else None
        if channel and self.user_channels.get(ctx.author.id) == channel.id:
            await channel.edit(name=name)
            await ctx.send(f"✅ Salon renommé en : `{name}`")
        else:
            await ctx.send("❌ Tu ne peux pas renommer ce salon.")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot:
            return

        uid = str(member.id)
        self.stop_session(uid) if before.channel and not after.channel else None
        self.start_session(uid) if not before.channel and after.channel else None

        guild_id = str(member.guild.id)
        if guild_id not in self.config:
            return

        config = self.config[guild_id]
        vocal_trigger_id = config.get("channel_id")
        parent_id = config.get("parent_id")

        if after.channel and after.channel.id == vocal_trigger_id:
            new_channel = await member.guild.create_voice_channel(
                name=f"Salon de {member.display_name}",
                category=member.guild.get_channel(parent_id),
                overwrites={
                    member: discord.PermissionOverwrite(manage_channels=True, mute_members=True, deafen_members=True, move_members=True, connect=True, speak=True),
                    member.guild.default_role: discord.PermissionOverwrite(connect=True)
                }
            )
            self.user_channels[member.id] = new_channel.id
            await member.move_to(new_channel)

        for user_id, chan_id in list(self.user_channels.items()):
            channel = member.guild.get_channel(chan_id)
            if channel and len(channel.members) == 0:
                await channel.delete()
                del self.user_channels[user_id]

async def setup(bot):
    await bot.add_cog(Vocal(bot))
