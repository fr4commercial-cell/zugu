import discord
from discord.ext import commands
from discord import ui

class VerifyView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label='Verificati', style=discord.ButtonStyle.success, custom_id='verify_button')
    async def verify_button(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.bot:
            await interaction.response.send_message('I bot non possono essere verificati.', ephemeral=True)
            return
        role = discord.utils.get(interaction.guild.roles, name='Verified')
        if not role:
            role = await interaction.guild.create_role(name='Verified')
        await interaction.user.add_roles(role)
        await interaction.response.send_message('Verifica completata! Ora hai accesso al server.', ephemeral=True)

class Verify(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        for guild in self.bot.guilds:
            channel = discord.utils.get(guild.text_channels, name='verifica')
            if channel:
                await channel.purge(limit=10)
                await channel.send('Clicca il bottone per verificarti!', view=VerifyView())

async def setup(bot):
    await bot.add_cog(Verify(bot))
