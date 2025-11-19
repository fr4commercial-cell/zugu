
import os
from discord.ext import commands
from discord import Intents
from dotenv import load_dotenv

load_dotenv()

intents = Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="/", intents=intents)

async def load_cogs():
    await bot.load_extension("cogs.tickets")
    await bot.load_extension("cogs.verify")
    await bot.load_extension("cogs.counting")

@bot.event
async def on_ready():
    print(f"Bot online come {bot.user}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(load_cogs())
    bot.run(os.getenv("DISCORD_TOKEN"))
