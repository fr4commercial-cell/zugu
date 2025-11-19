import discord
from discord.ext import commands

class Boost(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        if before.premium_since is None and after.premium_since is not None:
            channel = discord.utils.get(after.guild.text_channels, name='boost')
            if channel:
                await channel.send(f'Grazie {after.mention} per aver boostato il server!')

async def setup(bot):
    await bot.add_cog(Boost(bot))
