# FULL INTEGRATED COUNTING SCRIPT WITH CUSTOM EMOJI SUPPORT (CLEANED)
# ==============================================================
# Removed all hardmode references and mode= parameters.

import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import asyncio
from datetime import timedelta
from typing import Optional, Dict, Any

BASE_DIR = os.path.dirname(__file__)
COUNTING_FILE = os.path.join(BASE_DIR, "..", "counting.json")
LEADERBOARD_FILE = os.path.join(BASE_DIR, "..", "counting_leaderboard.json")
CONFIG_FILE = os.path.join(BASE_DIR, "..", "counting_config.json")

# Load/save helpers

def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[Counting] Error saving {path}: {e}")

DEFAULT_CONFIG = {
    "milestones": [100, 500, 1000, 5000, 10000],
    "log_channel_id": None,
    "timeout_minutes": 1,
    "success_emoji": "<a:Corretto:1441169877552599253>",
    "error_emoji": "<a:Sbagliato:1441165123568930896>",
    "milestone_emoji": "<a:Fuoco:1381953999829336206>",
    "special_numbers": {
        "67": "<a:67:1441169460345176197>",
        "100": "<a:100:1441169427533009118>",
        "500": "<:500:1441169389792526428>",
        "666": "<:666:1441169193792700510>",
        "999": "<:999:1441169161526050866>",
        "1000": "<:1000:1441169358507217006>",
        "10000": "<:10000:1441169310012801035>"
    }
}

class Counting(commands.Cog):
    counting_group = app_commands.Group(name="counting", description="Funzioni del counting")

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.data: Dict[str, Any] = load_json(COUNTING_FILE, {})
        self.leaderboard = load_json(LEADERBOARD_FILE, {})
        self.config = load_json(CONFIG_FILE, DEFAULT_CONFIG.copy())

    def _ensure_guild(self, guild_id: str):
        if guild_id not in self.data:
            self.data[guild_id] = {"channels": {}}
        if guild_id not in self.leaderboard:
            self.leaderboard[guild_id] = {}
        save_json(COUNTING_FILE, self.data)
        save_json(LEADERBOARD_FILE, self.leaderboard)

    def get_channel_conf(self, guild_id: str, channel_id: str):
        return self.data.get(guild_id, {}).get("channels", {}).get(channel_id)

    def set_channel_conf(self, guild_id: str, channel_id: str, conf: dict):
        self._ensure_guild(guild_id)
        self.data[guild_id]["channels"][channel_id] = conf
        save_json(COUNTING_FILE, self.data)

    def inc_leaderboard(self, guild_id: str, user_id: str, amount: int = 1):
        self._ensure_guild(guild_id)
        self.leaderboard[guild_id][user_id] = self.leaderboard[guild_id].get(user_id, 0) + amount
        save_json(LEADERBOARD_FILE, self.leaderboard)

    # --- CONFIG EMOJI COMMAND ---
    @counting_group.command(name="emoji")
    @app_commands.describe(type="success/error/milestone o numero", emoji="Emoji personalizzata del server")
    async def counting_emoji(self, interaction, type: str, emoji: str):
        if not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message("❌ Permessi insufficienti.", ephemeral=True)

        type = type.lower()
        if (type not in ["success", "error", "milestone"] and not type.isdigit()):
            return await interaction.response.send_message("Usa: success, error, milestone, oppure un numero.", ephemeral=True)

        if not emoji.startswith("<"):
            return await interaction.response.send_message("Devi usare un'emoji personalizzata.", ephemeral=True)

        try:
            emoji_id = int(emoji.split(":")[2].replace('>', ''))
        except:
            return await interaction.response.send_message("Emoji non valida.", ephemeral=True)

        if type.isdigit():
            self.config["special_numbers"][type] = emoji_id
            save_json(CONFIG_FILE, self.config)
            return await interaction.response.send_message(f"Emoji per il numero {type} impostata!")

        key = f"{type}_emoji"
        self.config[key] = emoji_id
        save_json(CONFIG_FILE, self.config)
        await interaction.response.send_message(f"Emoji {type} impostata!")

    # --- MAIN SET COMMAND ---
    @counting_group.command(name="set")
    @app_commands.describe(channel="Canale", start="Valore iniziale", allow_recovery="Recovery mode")
    async def counting_set(self, interaction, channel: discord.TextChannel, start: int = 0, allow_recovery: bool = True):
        if not (interaction.user.guild_permissions.administrator or interaction.user.guild_permissions.manage_guild):
            return await interaction.response.send_message("❌ Permessi insufficienti.", ephemeral=True)

        guild_id = str(interaction.guild.id)
        chan_id = str(channel.id)

        conf = {
            "last": start,
            "last_user": None,
            "recovery": allow_recovery,
            "milestones": self.config.get("milestones", DEFAULT_CONFIG["milestones"])
        }

        self.set_channel_conf(guild_id, chan_id, conf)
        await interaction.response.send_message(f"Counting attivato in {channel.mention}", ephemeral=True)
        try:
            await channel.send(start + 1)
        except:
            pass

    # INFO COMMAND
    @counting_group.command(name="info")
    async def counting_info(self, interaction, channel: Optional[discord.TextChannel] = None):
        if channel is None:
            channel = interaction.channel
        guild_id = str(interaction.guild.id)
        conf = self.get_channel_conf(guild_id, str(channel.id))

        if not conf:
            return await interaction.response.send_message("Nessun counting qui.")

        e = discord.Embed(title="📊 Counting Info")
        e.add_field(name="Ultimo", value=conf["last"])
        e.add_field(name="Recovery", value=conf["recovery"])
        await interaction.response.send_message(embed=e)

    # MAIN COUNTING HANDLER
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.guild is None:
            return

        guild_id = str(message.guild.id)
        confs = self.data.get(guild_id, {}).get("channels", {})
        if not confs:
            return

        chan_conf = confs.get(str(message.channel.id))
        if not chan_conf:
            return

        raw = message.content.strip()

        try:
            num = int(raw)
        except:
            try:
                num = int(eval(raw, {"__builtins__": None}, {}))
            except:
                await self._delete_and_error(message, chan_conf, guild_id, "invalid")
                return

        expected = chan_conf["last"] + 1

        if message.author.id == chan_conf.get("last_user"):
            await self._delete_and_error(message, chan_conf, guild_id, "same_user")
            return

        if num != expected:
            await self._delete_and_error(message, chan_conf, guild_id, "wrong_number")
            return

        chan_conf["last"] = num
        chan_conf["last_user"] = message.author.id
        self.set_channel_conf(guild_id, str(message.channel.id), chan_conf)
        self.inc_leaderboard(guild_id, str(message.author.id))

        emoji = self._get_emoji(message.guild, "success_emoji") or "✅"
        try:
            await message.add_reaction(emoji)
        except:
            pass

        if num in chan_conf.get("milestones", []):
            m_emoji = self._get_emoji(message.guild, "milestone_emoji") or "🎉"
            try:
                await message.channel.send(f"{m_emoji} Milestone **{num}** raggiunta da {message.author.mention}!")
            except:
                pass

        special = self.config.get("special_numbers", {})
        if str(num) in special and special[str(num)]:
            sp = message.guild.get_emoji(special[str(num)])
            if sp:
                try:
                    await message.channel.send(f"{sp} Numero speciale **{num}** raggiunto da {message.author.mention}!")
                except:
                    pass

    async def _delete_and_error(self, message, chan_conf, guild_id, reason):
        try:
            await message.delete()
        except:
            pass

        chan_conf["last"] = 0
        chan_conf["last_user"] = None
        self.set


# --- REQUIRED SETUP FUNCTION ---
def setup(bot: commands.Bot):
    bot.add_cog(Counting(bot))

# Added async setup function
async def setup(bot):
    await bot.add_cog(Counting(bot))
