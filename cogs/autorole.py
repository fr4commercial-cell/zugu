import discord
from discord.ext import commands

class Autorole(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member):
        role = discord.utils.get(member.guild.roles, name='Member')
        if not role:
            role = await member.guild.create_role(name='Member')
        await member.add_roles(role)

async def setup(bot):
    await bot.add_cog(Autorole(bot))
