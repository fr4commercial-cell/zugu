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
        # Carica dinamicamente solo i cogs che hanno una funzione setup
        initial_extensions = []
        try:
            cogs_dir = os.path.join(os.path.dirname(__file__), 'cogs')
            for fname in os.listdir(cogs_dir):
                if not fname.endswith('.py'):
                    continue
                if fname.startswith('_'):
                    continue
                name = fname[:-3]
                # escludi moduli helper non-cog
                if name in { 'console_logger', '__init__' }:
                    continue
                fpath = os.path.join(cogs_dir, fname)
                try:
                    with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                        src = f.read()
                    if 'async def setup' in src or 'def setup(' in src:
                        initial_extensions.append(f'cogs.{name}')
                except Exception:
                    continue
        except Exception as e:
            print(f"⚠️ Scansione cogs fallita: {e}")

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
        # Fast guild sync to make slash commands appear immediately in joined guilds
        try:
            for g in self.guilds:
                try:
                    self.tree.copy_global_to(guild=g)
                    await self.tree.sync(guild=g)
                    print(f"⚡ Comandi sincronizzati velocemente per la guild: {g.name} ({g.id})")
                except Exception as e:
                    print(f"⚠️ Guild sync fallita per {g.id}: {e}")
        except Exception as e:
            print(f"⚠️ Fast guild sync errore: {e}")


bot = MyBot(command_prefix='!', intents=intents)


if __name__ == '__main__':
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        print("❌ ERRORE: DISCORD_TOKEN non presente nel file .env")
    else:
        bot.run(token)
    
