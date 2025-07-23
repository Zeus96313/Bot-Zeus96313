import discord
from discord.ext import commands
import os
import json
import asyncio

# === Préfixe dynamique depuis config.json ===
def get_prefix(bot, message):
    try:
        with open("config.json", "r") as f:
            config = json.load(f)
        return config.get("prefix", "!")
    except FileNotFoundError:
        return "!"

# === Intents ===
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.voice_states = True
intents.reactions = True

# === Initialisation du bot ===
bot = commands.Bot(command_prefix=get_prefix, intents=intents, help_command=None)

# === Liste des Cogs à charger ===
COGS = ["general", "moderation", "ticket", "vocal", "levels", "giveaway", "staff_manager"]

# === Chargement des Cogs ===
async def load_cogs():
    for cog in COGS:
        try:
            await bot.load_extension(f"cogs.{cog}")
            print(f"✅ Cog chargé : {cog}")
        except Exception as e:
            print(f"❌ Erreur en chargeant {cog} : {e}")

# === Événement prêt ===
@bot.event
async def on_ready():
    print(f"✅ Connecté en tant que {bot.user} (ID: {bot.user.id})")
    print("🚀 Le bot est prêt.")

# === Commande pour recharger un cog dynamiquement ===
@bot.command()
@commands.has_permissions(administrator=True)
async def reload(ctx, cog: str):
    """Recharge un cog (admin uniquement)"""
    try:
        await bot.unload_extension(f"cogs.{cog}")
        await bot.load_extension(f"cogs.{cog}")
        await ctx.send(f"♻️ Cog `{cog}` rechargé avec succès.")
    except Exception as e:
        await ctx.send(f"❌ Erreur lors du rechargement : `{e}`")

# === Lancement du bot ===
async def main():
    async with bot:
        await load_cogs()
        token = os.getenv("Tocken_Bot")  # ← Ton token doit être défini dans ton environnement (secrets ou .env)
        if not token:
            print("❌ Erreur : le token n'est pas défini dans les secrets.")
            return
        await bot.start(token)

asyncio.run(main())
