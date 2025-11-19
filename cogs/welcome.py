import discord
from discord.ext import commands

class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member):
        channel = discord.utils.get(member.guild.text_channels, name='benvenuto')
        if channel:
            await channel.send(f'Benvenuto {member.mention} nel server!')

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        channel = discord.utils.get(member.guild.text_channels, name='addio')
        if channel:
            await channel.send(f'{member.mention} ha lasciato il server.')

async def setup(bot):
    await bot.add_cog(Welcome(bot))
