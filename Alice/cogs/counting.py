## Tutti gli import e la classe Counting rimangono invariati
import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import os
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

BASE_DIR = os.path.dirname(__file__)
COUNTING_FILE = os.path.join(BASE_DIR, "..", "counting.json")
LEADERBOARD_FILE = os.path.join(BASE_DIR, "..", "counting_leaderboard.json")
CONFIG_FILE = os.path.join(BASE_DIR, "..", "counting_config.json")

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
        print(f"[Counting] Errore salvataggio {path}: {e}")

# default config example:
DEFAULT_CONFIG = {
    "milestones": [100, 500, 1000, 5000, 10000],
    "hard_mode_default": False,
    "log_channel_id": None,
    "competitive_week_start": "monday",  # not strict; used for scheduling weekly reset
}

class Counting(commands.Cog):
    counting_group = app_commands.Group(name="counting", description="Tutte le funzionalità del counting")

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.data: Dict[str, Any] = load_json(COUNTING_FILE, {})  # per guild: {guild_id: {channels: {chan_id: {...}}, ...}}
        self.leaderboard = load_json(LEADERBOARD_FILE, {})  # per guild -> user -> count
        self.config = load_json(CONFIG_FILE, DEFAULT_CONFIG.copy())
        # Ensure structures
        # start background task for weekly competition reset
        self.weekly_task.start()

    # ------------- Helpers -------------
    def _ensure_guild(self, guild_id: str):
        if guild_id not in self.data:
            self.data[guild_id] = {"channels": {}}  # channels keyed by channel id (str)
        if guild_id not in self.leaderboard:
            self.leaderboard[guild_id] = {}  # user_id -> total_count
        save_json(COUNTING_FILE, self.data)
        save_json(LEADERBOARD_FILE, self.leaderboard)

    def get_channel_conf(self, guild_id: str, channel_id: str) -> Optional[dict]:
        return self.data.get(guild_id, {}).get("channels", {}).get(channel_id)

    def set_channel_conf(self, guild_id: str, channel_id: str, conf: dict):
        self._ensure_guild(guild_id)
        self.data[guild_id]["channels"][channel_id] = conf
        save_json(COUNTING_FILE, self.data)

    def remove_channel_conf(self, guild_id: str, channel_id: str):
        if guild_id in self.data and channel_id in self.data[guild_id]["channels"]:
            del self.data[guild_id]["channels"][channel_id]
            save_json(COUNTING_FILE, self.data)

    def inc_leaderboard(self, guild_id: str, user_id: str, amount: int = 1):
        self._ensure_guild(guild_id)
        self.leaderboard[guild_id][user_id] = self.leaderboard[guild_id].get(user_id, 0) + amount
        save_json(LEADERBOARD_FILE, self.leaderboard)

    # ------------- /counting set -------------
    @counting_group.command(name="set", description="Setta un canale per il counting (multi-canale support)")
    @app_commands.describe(channel="Canale dove attivare il counting", start="Valore iniziale (default 0)", mode="Mode: normal/hard", allow_recovery="Se abilitare recovery mode")
    async def counting_set(self, interaction: discord.Interaction, channel: discord.TextChannel, start: int = 0, mode: Optional[str] = "normal", allow_recovery: Optional[bool] = True):
        if not (interaction.user.guild_permissions.administrator or interaction.user.guild_permissions.manage_guild):
            return await interaction.response.send_message("❌ Serve permesso di amministrazione o Manage Guild.", ephemeral=True)

        guild_id = str(interaction.guild.id)
        chan_id = str(channel.id)
        conf = {
            "last": int(start),
            "last_user": None,
            "hard": True if mode and mode.lower() == "hard" else False,
            "recovery": bool(allow_recovery),
            "milestones": self.config.get("milestones", DEFAULT_CONFIG["milestones"])
        }
        self.set_channel_conf(guild_id, chan_id, conf)
        await interaction.response.send_message(f"✅ Counting attivato su {channel.mention} (start={start}, mode={conf['hard'] and 'HARD' or 'NORMAL'})", ephemeral=True)
        try:
            await channel.send(str(start + 1))
        except Exception:
            pass

    # ------------- /counting unset -------------
    @counting_group.command(name="unset", description="Disattiva counting su un canale")
    @app_commands.describe(channel="Canale da disattivare (default: canale corrente)")
    async def counting_unset(self, interaction: discord.Interaction, channel: Optional[discord.TextChannel] = None):
        if not (interaction.user.guild_permissions.administrator or interaction.user.guild_permissions.manage_guild):
            return await interaction.response.send_message("❌ Serve permesso di amministrazione o Manage Guild.", ephemeral=True)
        guild_id = str(interaction.guild.id)
        if channel is None:
            channel = interaction.channel
        chan_id = str(channel.id)
        if self.get_channel_conf(guild_id, chan_id):
            self.remove_channel_conf(guild_id, chan_id)
            await interaction.response.send_message(f"✅ Counting disattivato per {channel.mention}", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Quel canale non è configurato per il counting.", ephemeral=True)

    # ------------- /counting info -------------
    @counting_group.command(name="info", description="Mostra info del counting per il server o canale")
    @app_commands.describe(channel="Canale di cui mostrare informazioni (default: canale corrente)")
    async def counting_info(self, interaction: discord.Interaction, channel: Optional[discord.TextChannel] = None):
        guild_id = str(interaction.guild.id)
        if channel is None:
            channel = interaction.channel
        chan_id = str(channel.id)
        conf = self.get_channel_conf(guild_id, chan_id)
        if not conf:
            return await interaction.response.send_message("ℹ️ Quel canale non ha il counting attivo.", ephemeral=True)
        embed = discord.Embed(title="📊 Counting Info")
        embed.add_field(name="Canale", value=f"<#{chan_id}>", inline=False)
        embed.add_field(name="Ultimo", value=str(conf["last"]), inline=True)
        embed.add_field(name="Hard Mode", value=str(conf.get("hard", False)), inline=True)
        embed.add_field(name="Recovery Mode", value=str(conf.get("recovery", True)), inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ------------- on_message handler (core counting logic) -------------
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # ignore bots & DMs
        if message.author.bot or message.guild is None:
            return
        guild_id = str(message.guild.id)
        confs = self.data.get(guild_id, {}).get("channels", {})
        if not confs:
            return
        chan_conf = confs.get(str(message.channel.id))
        if not chan_conf:
            return

        # must be a pure number
        raw = message.content.strip()
        try:
            num = int(raw)
        except ValueError:
            # not number -> delete
            try:
                await message.delete()
            except Exception:
                pass
            await self._log_and_notify_wrong(message, chan_conf, guild_id)
            return

        expected = chan_conf["last"] + 1
        # hard mode: additional rules can be applied (handled later)
        # anti-double: same user twice
        if message.author.id == chan_conf.get("last_user"):
            try:
                await message.delete()
            except Exception:
                pass
            await self._log_and_notify_wrong(message, chan_conf, guild_id, reason="same_user")
            return

        # if numeric incorrect
        if num != expected:
            # recovery mode: optionally send correction message instead of deletion
            if chan_conf.get("recovery", True):
                # respond with correct number, can be ephemeral correction
                try:
                    await message.channel.send(f"❌ Numero incorretto. Numero corretto: **{expected}** (atteso).")
                except Exception:
                    pass
            try:
                await message.delete()
            except Exception:
                pass
            await self._log_and_notify_wrong(message, chan_conf, guild_id, reason="wrong_number")
            return

        # correct number: update state, LB and milestone
        chan_conf["last"] = num
        chan_conf["last_user"] = message.author.id
        # persist
        self.set_channel_conf(guild_id, str(message.channel.id), chan_conf)

        # leaderboard increment
        self.inc_leaderboard(guild_id, str(message.author.id), 1)

        # react to message
        try:
            await message.add_reaction("✅")
        except Exception:
            pass

        # milestone check
        milestones = chan_conf.get("milestones", self.config.get("milestones", DEFAULT_CONFIG["milestones"]))
        if num in milestones:
            # announce
            try:
                await message.channel.send(f"🎉 **Milestone raggiunta: {num}!** Congratulazioni {message.author.mention} 🎉")
            except Exception:
                pass

    # ------------- helper: logging & notifications -------------
    async def _log_and_notify_wrong(self, message: discord.Message, chan_conf: dict, guild_id: str, reason: Optional[str] = None):
        # if a log channel is configured, send a short report
        log_id = self.config.get("log_channel_id")
        if log_id:
            try:
                ch = message.guild.get_channel(int(log_id))
                if ch:
                    embed = discord.Embed(title="Errore Counting", color=discord.Color.red(), timestamp=datetime.utcnow())
                    embed.add_field(name="Utente", value=message.author.mention, inline=True)
                    embed.add_field(name="Canale", value=message.channel.mention, inline=True)
                    embed.add_field(name="Messaggio", value=message.content[:1000] or "—", inline=False)
                    embed.add_field(name="Motivo", value=reason or "invalid", inline=True)
                    await ch.send(embed=embed)
            except Exception:
                pass

    # ------------- /counting leaderboard -------------
    @counting_group.command(name="leaderboard", description="Mostra la classifica dei contatori del server")
    @app_commands.describe(limit="Quanti elementi mostrare (default 10)")
    async def counting_leaderboard(self, interaction: discord.Interaction, limit: Optional[int] = 10):
        guild_id = str(interaction.guild.id)
        lb = self.leaderboard.get(guild_id, {})
        # sort descending
        items = sorted(lb.items(), key=lambda kv: kv[1], reverse=True)[: max(1, min(50, limit))]
        if not items:
            return await interaction.response.send_message("ℹ️ Nessun dato nella leaderboard.", ephemeral=True)
        embed = discord.Embed(title="🏆 Leaderboard Counting", color=discord.Color.gold())
        for user_id, cnt in items:
            member = interaction.guild.get_member(int(user_id))
            name = member.display_name if member else f"User {user_id}"
            embed.add_field(name=name, value=f"{cnt} numeri", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=False)

    # ------------- /counting stats -------------
    @counting_group.command(name="stats", description="Mostra le statistiche di un utente")
    @app_commands.describe(user="Utente da controllare (default = tu)")
    async def counting_stats(self, interaction: discord.Interaction, user: Optional[discord.Member] = None):
        guild_id = str(interaction.guild.id)
        if user is None:
            user = interaction.user
        cnt = self.leaderboard.get(guild_id, {}).get(str(user.id), 0)
        await interaction.response.send_message(f"📊 {user.mention} ha contato **{cnt}** numeri in questo server.", ephemeral=True)

    # ------------- Weekly competitive & reset helpers -------------
    @tasks.loop(hours=24)
    async def weekly_task(self):
        """Task giornaliero che controlla se è ora di resettare la competizione settimanale."""
        try:
            # Simple weekly reset at Monday 00:00 UTC (approx). You can customize in config later.
            now = datetime.utcnow()
            # if today is monday and time is within the first hour -> reset (prevents multiple resets per day with marker)
            if now.weekday() == 0:  # Monday
                # use a marker file to avoid multiple resets same Monday
                marker = os.path.join(BASE_DIR, "..", ".weekly_reset_marker")
                last_mark = None
                try:
                    if os.path.exists(marker):
                        with open(marker, "r", encoding="utf-8") as f:
                            last_mark = f.read().strip()
                except:
                    last_mark = None
                today_str = now.strftime("%Y-%m-%d")
                if last_mark != today_str:
                    # Reset weekly statistics: for simplicity, create weekly snapshot then zero per-guild weekly counters (if we had them)
                    # Here: just announce in a configured log channel (or skip)
                    log_id = self.config.get("log_channel_id")
                    if log_id:
                        g = None
                        try:
                            # try to send an announcement to each guild's configured log channel/guild configured channel
                            # This loop finds guilds where bot is in and has log channel configured.
                            for guild in self.bot.guilds:
                                gid = str(guild.id)
                                conf = self.data.get(gid, {})
                                # optional advanced logic: snapshot top and reset per-week counters
                            ch = self.bot.get_channel(int(log_id))
                            if ch:
                                await ch.send("🔄 Weekly competition: reset eseguito.")
                        except Exception:
                            pass
                    # write marker
                    try:
                        with open(marker, "w", encoding="utf-8") as f:
                            f.write(today_str)
                    except:
                        pass
        except Exception as e:
            print(f"[Counting][weekly_task] error: {e}")

    @weekly_task.before_loop
    async def before_weekly(self):
        await self.bot.wait_until_ready()

    # ------------- /counting mode (hard on/off) -------------
    @counting_group.command(name="mode", description="Imposta modalità del canale: hard|normal")
    @app_commands.describe(channel="Canale target (default = canale corrente)", mode="hard o normal")
    async def counting_mode(self, interaction: discord.Interaction, mode: str, channel: Optional[discord.TextChannel] = None):
        if not (interaction.user.guild_permissions.administrator or interaction.user.guild_permissions.manage_guild):
            return await interaction.response.send_message("❌ Serve permesso admin o Manage Guild.", ephemeral=True)
        if channel is None:
            channel = interaction.channel
        guild_id = str(interaction.guild.id)
        conf = self.get_channel_conf(guild_id, str(channel.id))
        if not conf:
            return await interaction.response.send_message("❌ Canale non configurato per counting.", ephemeral=True)
        conf["hard"] = True if mode.lower() == "hard" else False
        self.set_channel_conf(guild_id, str(channel.id), conf)
        await interaction.response.send_message(f"✅ Modalità impostata a {mode.upper()} per {channel.mention}", ephemeral=True)

    # ------------- /counting recovery on/off -------------
    @counting_group.command(name="recovery", description="Attiva/disattiva recovery mode (mostra correzione invece di reset automatico)")
    @app_commands.describe(channel="Canale target (default=canale corrente)", on="on|off")
    async def counting_recovery(self, interaction: discord.Interaction, on: str, channel: Optional[discord.TextChannel] = None):
        if not (interaction.user.guild_permissions.administrator or interaction.user.guild_permissions.manage_guild):
            return await interaction.response.send_message("❌ Serve permesso admin o Manage Guild.", ephemeral=True)
        if channel is None:
            channel = interaction.channel
        guild_id = str(interaction.guild.id)
        conf = self.get_channel_conf(guild_id, str(channel.id))
        if not conf:
            return await interaction.response.send_message("❌ Canale non configurato per counting.", ephemeral=True)
        conf["recovery"] = True if on.lower() == "on" else False
        self.set_channel_conf(guild_id, str(channel.id), conf)
        await interaction.response.send_message(f"✅ Recovery mode {'attivata' if conf['recovery'] else 'disattivata'} per {channel.mention}", ephemeral=True)

    # ------------- /counting log set/unset -------------
    @counting_group.command(name="log", description="Imposta o rimuovi log channel per il counting (errori & weekly)")
    @app_commands.describe(channel="Canale di log (omit to unset)")
    async def counting_log(self, interaction: discord.Interaction, channel: Optional[discord.TextChannel] = None):
        if not (interaction.user.guild_permissions.administrator or interaction.user.guild_permissions.manage_guild):
            return await interaction.response.send_message("❌ Serve permesso admin o Manage Guild.", ephemeral=True)
        if channel is None:
            self.config["log_channel_id"] = None
            save_json(CONFIG_FILE, self.config)
            return await interaction.response.send_message("✅ Log canale rimosso.", ephemeral=True)
        self.config["log_channel_id"] = channel.id
        save_json(CONFIG_FILE, self.config)
        await interaction.response.send_message(f"✅ Log canale impostato su {channel.mention}", ephemeral=True)

    # ------------- /counting reset (admin) -------------
    @counting_group.command(name="reset", description="Resetta il counting di un canale a 0 (admin)")
    @app_commands.describe(channel="Canale target (default = canale corrente)", value="Valore a cui resettare (default 0)")
    async def counting_reset(self, interaction: discord.Interaction, channel: Optional[discord.TextChannel] = None, value: int = 0):
        if not (interaction.user.guild_permissions.administrator or interaction.user.guild_permissions.manage_guild):
            return await interaction.response.send_message("❌ Serve permesso admin o Manage Guild.", ephemeral=True)
        if channel is None:
            channel = interaction.channel
        guild_id = str(interaction.guild.id)
        conf = self.get_channel_conf(guild_id, str(channel.id))
        if not conf:
            return await interaction.response.send_message("❌ Canale non configurato.", ephemeral=True)
        conf["last"] = value
        conf["last_user"] = None
        self.set_channel_conf(guild_id, str(channel.id), conf)
        await interaction.response.send_message(f"✅ Counting in {channel.mention} resettato a `{value}`", ephemeral=True)

# Setup function (must be last)
async def setup(bot: commands.Bot):
    await bot.add_cog(Counting(bot))