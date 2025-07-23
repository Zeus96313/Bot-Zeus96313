import discord
from discord.ext import commands
import asyncio
from datetime import datetime
import pytz
import os

class Ticket(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ticket_category_name = "🎟️｜Tickets"

    def is_staff(self, member: discord.Member):
        staff_cog = self.bot.get_cog("StaffManager")
        if staff_cog:
            return staff_cog.is_staff(member)
        return False

    async def get_or_create_category(self, guild):
        category = discord.utils.get(guild.categories, name=self.ticket_category_name)
        if not category:
            category = await guild.create_category(self.ticket_category_name)
        return category

    @commands.command()
    async def ticket(self, ctx):
        existing = discord.utils.get(ctx.guild.text_channels, name=f"ticket-{ctx.author.name.lower()}")
        if existing:
            return await ctx.send("❗ Tu as déjà un ticket ouvert.")

        category = await self.get_or_create_category(ctx.guild)

        overwrites = {
            ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            ctx.author: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }

        for role in ctx.guild.roles:
            if self.is_staff(role):
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        channel = await ctx.guild.create_text_channel(f"ticket-{ctx.author.name}", category=category, overwrites=overwrites)
        await ctx.send(f"✅ Ton ticket a été créé : {channel.mention}")
        await channel.send(f"🎫 Bienvenue {ctx.author.mention}, explique ton problème !")

    @commands.command()
    async def addticket(self, ctx, target: discord.Role | discord.Member):
        if not self.is_staff(ctx.author):
            return await ctx.send("❌ Tu n'as pas la permission d'utiliser cette commande.")
        if not ctx.channel.name.startswith("ticket-"):
            return await ctx.send("❗ Commande à utiliser dans un ticket.")
        await ctx.channel.set_permissions(target, read_messages=True, send_messages=True)
        await ctx.send(f"✅ {target.mention} a été ajouté au ticket.")

    @commands.command()
    async def removeticket(self, ctx, target: discord.Role | discord.Member):
        if not self.is_staff(ctx.author):
            return await ctx.send("❌ Tu n'as pas la permission d'utiliser cette commande.")
        if not ctx.channel.name.startswith("ticket-"):
            return await ctx.send("❗ Commande à utiliser dans un ticket.")
        await ctx.channel.set_permissions(target, overwrite=None)
        await ctx.send(f"🚫 {target.mention} a été retiré du ticket.")

    @commands.command()
    async def renameticket(self, ctx, *, new_name: str):
        if not self.is_staff(ctx.author):
            return await ctx.send("❌ Tu n'as pas la permission d'utiliser cette commande.")
        if not ctx.channel.name.startswith("ticket-"):
            return await ctx.send("❗ Commande à utiliser dans un ticket.")
        await ctx.channel.edit(name=f"ticket-{new_name}")
        await ctx.send(f"🛠️ Le ticket a été renommé en `ticket-{new_name}`.")

    @commands.command()
    async def close(self, ctx):
        if not ctx.channel.name.startswith("ticket-"):
            return await ctx.send("❗ Cette commande ne peut être utilisée que dans un ticket.")
        await ctx.send("⏳ Fermeture du ticket dans 5 secondes...")

        # Salon de logs
        log_channel = discord.utils.get(ctx.guild.text_channels, name="📨-logs-tickets")
        if not log_channel:
            log_channel = await ctx.guild.create_text_channel("📨-logs-tickets")

        # Horodatage Paris
        tz = pytz.timezone("Europe/Paris")
        now_paris = datetime.now(tz)
        timestamp = now_paris.strftime("%d/%m/%Y %H:%M")

        # Transcription des messages
        messages = [
            f"[{msg.created_at.astimezone(tz).strftime('%d/%m/%Y %H:%M:%S')}] {msg.author} : {msg.content}"
            async for msg in ctx.channel.history(oldest_first=True, limit=1000)
        ]
        transcript = "\n".join(messages) or "Aucun message."

        file_name = f"{ctx.channel.name}_transcript.txt"
        with open(file_name, "w", encoding="utf-8") as f:
            f.write(transcript)

        await log_channel.send(
            content=f"📁 Transcript du salon **{ctx.channel.name}** fermé à **{timestamp}** par {ctx.author.mention} :",
            file=discord.File(file_name)
        )

        await asyncio.sleep(5)
        await ctx.channel.delete()
        os.remove(file_name)

async def setup(bot):
    await bot.add_cog(Ticket(bot))
