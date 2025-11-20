import discord
import json
from discord.ext import commands
from discord import app_commands

def load_config():
    try:
        with open("config.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except UnicodeDecodeError:
        # Fallback: try reading as UTF-8 with errors replaced to avoid import crash
        try:
            with open("config.json", "r", encoding="utf-8", errors="replace") as f:
                return json.load(f)
        except Exception:
            return {}

def save_config(data):
    with open("config.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

class Boost(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = load_config()

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        if before.premium_since is None and after.premium_since is not None:
            guild_id = str(after.guild.id)

            if guild_id not in self.config or "boost_channel" not in self.config[guild_id]:
                return

            channel_id = self.config[guild_id]["boost_channel"]
            channel = after.guild.get_channel(channel_id)
            if not channel:
                return

            # Embed personalizzato
            data = self.config[guild_id].get("boost_embed", {})

            title = data.get("title", "🎉 Nuovo Boost!")
            description = data.get("description", "{user} ha boostato il server!")
            color = data.get("color", 0xFF73FA)
            image = data.get("image", None)
            thumbnail = data.get("thumbnail", None)

            # Variabili dinamiche
            description = (
                description.replace("{user}", after.mention)
                           .replace("{username}", after.name)
                           .replace("{server}", after.guild.name)
            )

            embed = discord.Embed(
                title=title,
                description=description,
                color=color
            )

            if image:
                embed.set_image(url=image)

            if thumbnail:
                embed.set_thumbnail(url=thumbnail)

            await channel.send(embed=embed)

    # ---------- SLASH COMMAND: SET BOOST CHANNEL ----------
    @app_commands.command(
        name="setboostchannel",
        description="Imposta il canale dove inviare i messaggi di boost."
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def set_boost_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        guild_id = str(interaction.guild.id)

        if guild_id not in self.config:
            self.config[guild_id] = {}

        self.config[guild_id]["boost_channel"] = channel.id
        save_config(self.config)

        await interaction.response.send_message(
            f"📌 Canale dei boost impostato su {channel.mention}!"
        )

    # ---------- SLASH COMMAND: SET BOOST EMBED ----------
    @app_commands.command(
        name="setboostembed",
        description="Configura l'embed inviato quando qualcuno boosta il server."
    )
    @app_commands.describe(
        title="Titolo dell'embed",
        description="Descrizione, usa {user} {username} {server}",
        color="Colore HEX (es: FF00FF)",
        image="URL immagine",
        thumbnail="URL thumbnail"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def set_boost_embed(
        self,
        interaction: discord.Interaction,
        title: str = None,
        description: str = None,
        color: str = None,
        image: str = None,
        thumbnail: str = None
    ):
        guild_id = str(interaction.guild.id)

        if guild_id not in self.config:
            self.config[guild_id] = {}

        if "boost_embed" not in self.config[guild_id]:
            self.config[guild_id]["boost_embed"] = {}

        # Aggiorna solo i parametri forniti
        if title:
            self.config[guild_id]["boost_embed"]["title"] = title

        if description:
            self.config[guild_id]["boost_embed"]["description"] = description

        if color:
            try:
                self.config[guild_id]["boost_embed"]["color"] = int(color, 16)
            except:
                return await interaction.response.send_message("❌ Colore non valido. Usa formato HEX senza #.", ephemeral=True)

        if image:
            self.config[guild_id]["boost_embed"]["image"] = image

        if thumbnail:
            self.config[guild_id]["boost_embed"]["thumbnail"] = thumbnail

        save_config(self.config)

        await interaction.response.send_message("✨ Embed aggiornato correttamente!")

    # ---------- SLASH COMMAND: BOOST COUNT ----------
    @app_commands.command(
        name="boostcount",
        description="Mostra quanti boost ha il server."
    )
    async def boost_count(self, interaction: discord.Interaction):
        boosts = interaction.guild.premium_subscription_count
        level = interaction.guild.premium_tier

        await interaction.response.send_message(
            f"⚡ Il server ha attualmente **{boosts} boost** (Livello **{level}**)."
        )

async def setup(bot):
    await bot.add_cog(Boost(bot))
