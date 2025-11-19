counting_group = app_commands.Group(name="counting", description="Counting commands")

# Setup function for extension
async def setup(bot: commands.Bot):
    await bot.add_cog(Counting(bot))
import json
import os
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands



class Counting(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.file = "counting.json"
        self.data = {}
        self._load()

    def _load(self):
        if os.path.exists(self.file):
            try:
                with open(self.file, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
            except Exception:
                self.data = {}
        else:
            self.data = {}

    def _save(self):
        with open(self.file, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    @counting_group.command(name="set", description="Setta il canale di counting e il valore iniziale")
    @app_commands.describe(channel="Canale di testo dove abilitare il counting", start="Valore di partenza (default 0)")
    async def set_count_channel(self, interaction: discord.Interaction, channel: discord.TextChannel, start: int = 0):
        if not (interaction.user.guild_permissions.administrator or interaction.user.guild_permissions.manage_guild):
            await interaction.response.send_message("❌ Devi essere un amministratore o avere Manage Guild.", ephemeral=True)
            return
        guild_id = str(interaction.guild.id)
        next_num = start + 1
        self.data[guild_id] = {
            "channel_id": str(channel.id),
            "last": int(next_num)
        }
        self._save()
        await interaction.response.send_message(f"✅ Counting impostato su {channel.mention}. Messaggio iniziale: `{next_num}`", ephemeral=True)
        try:
            await channel.send(str(next_num))
        except Exception as e:
            await interaction.followup.send(f"Errore nell'inviare il messaggio nel canale: {e}", ephemeral=True)
