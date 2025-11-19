import discord
from discord.ext import commands
from discord import app_commands
import json


import json
import os
import discord
from discord.ext import commands
from discord import app_commands

CONFIG_FILE = os.path.join(os.path.dirname(__file__), '..', 'config.json')

def load_json(path, default):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default

class Verify(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = load_json(CONFIG_FILE, {})

    @app_commands.command(name="verify", description="Verificati e ottieni il ruolo membro")
    async def verify(self, interaction: discord.Interaction):
        role_id = self.config.get("verify_role_id")
        if not role_id:
            await interaction.response.send_message("❌ Ruolo di verifica non configurato.", ephemeral=True)
            return
        role = interaction.guild.get_role(role_id)
        if not role:
            await interaction.response.send_message("❌ Ruolo non trovato nel server.", ephemeral=True)
            return
        try:
            await interaction.user.add_roles(role, reason="Verifica completata")
            await interaction.response.send_message(f"✅ Verifica completata! Ruolo {role.mention} assegnato.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Errore nell'assegnazione del ruolo: {e}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Verify(bot))
