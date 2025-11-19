import discord
from discord.ext import commands
import os
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.default()
intents.members = True
intents.guilds = True
intents.message_content = True
intents.messages = True
intents.guild_reactions = True
intents.guild_scheduled_events = True
intents.presences = True

class MyBot(commands.Bot):
    async def setup_hook(self):
        # Carica tutte le estensioni (COGS)
        initial_extensions = [
            'cogs.verify',
            'cogs.welcome',
            'cogs.boost',
            'cogs.tickets',
            'cogs.counting',
            'cogs.autorole'
        ]

        for ext in initial_extensions:
            try:
                await self.load_extension(ext)
                print(f"✅ Estensione caricata: {ext}")
            except Exception as e:
                print(f"❌ Errore nel caricare {ext}: {e}")

        # SYNC GLOBALE DEI COMANDI
        try:
            synced = await self.tree.sync()
            print(f"🌍 Comandi globali sincronizzati: {len(synced)}")
        except Exception as e:
            print(f"❌ Errore nella sincronizzazione globale: {e}")

    async def on_ready(self):
        print(f"🤖 Logged in as {self.user} ({self.user.id})")
        print("Bot pronto!")


bot = MyBot(command_prefix='!', intents=intents)


if __name__ == '__main__':
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        print("❌ ERRORE: DISCORD_TOKEN non presente nel file .env")
    else:
        bot.run(token)
    