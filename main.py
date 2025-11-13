import discord
from discord.ext import commands
import asyncio
import os
from config import TOKEN
import logging

# Configurazione logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="/", intents=intents)

@bot.event
async def on_ready():
    """Evento che si attiva quando il bot è pronto"""
    logger.info(f'{bot.user} è online!')
    print(f"Bot loggato come {bot.user}")
    
    try:
        synced = await bot.tree.sync()
        logger.info(f"Sincronizzati {len(synced)} comandi")
    except Exception as e:
        logger.error(f"Errore nella sincronizzazione: {e}")

async def load_cogs():
    """Carica tutti i cogs dalla cartella cogs"""
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py'):
            try:
                await bot.load_extension(f'cogs.{filename[:-3]}')
                logger.info(f'Caricato cog: {filename}')
            except Exception as e:
                logger.error(f'Errore nel caricamento di {filename}: {e}')

@bot.event
async def on_command_error(ctx, error):
    """Gestisce gli errori dei comandi"""
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Argomento mancante: {error.param}")
    elif isinstance(error, commands.BadArgument):
        await ctx.send(f"❌ Argomento non valido: {error}")
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Non hai i permessi per usare questo comando!")
    elif isinstance(error, commands.CommandNotFound):
        await ctx.send("❌ Comando non trovato!")
    else:
        logger.error(f"Errore: {error}")
        await ctx.send(f"❌ Si è verificato un errore: {error}")

async def main():
    """Funzione principale"""
    async with bot:
        await load_cogs()
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
