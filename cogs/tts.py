import asyncio
import io
import os
import json
import random
import logging
from collections import deque
from typing import List

import requests
import discord
from discord.ext import commands, tasks
from discord import app_commands, ui
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tts")

load_dotenv()
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

BASE_DIR = os.path.dirname(__file__)
TTS_JSON = os.path.join(BASE_DIR, "tts.json")

# -------------------------------------------------------------------
#  VOICE MANAGER
# -------------------------------------------------------------------
class VoiceManager:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.voice_cache = []
        self.session = requests.Session()

    def fetch_voices(self):
        url = "https://api.elevenlabs.io/v1/voices"
        headers = {"xi-api-key": self.api_key}
        response = self.session.get(url, headers=headers)
        response.raise_for_status()
        self.voice_cache = response.json().get("voices", [])

    def find_voice_by_name(self, name: str):
        return next((v for v in self.voice_cache if v["name"].lower() == name.lower()), None)

    def fetch_audio_stream(self, text: str, voice_id: str):
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"
        payload = {
            "model_id": "eleven_multilingual_v2",
            "text": text,
            "voice_settings": {
                "stability": 1,
                "similarity_boost": 0.8,
                "style": 0.5,
                "use_speaker_boost": True
            }
        }
        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json"
        }

        try:
            r = self.session.post(url, json=payload, headers=headers, stream=True)
            r.raise_for_status()
            return io.BytesIO(r.content)
        except requests.RequestException as e:
            logger.error(f"Audio stream error: {e}")
            return None


# -------------------------------------------------------------------
#  UI SELECT MENU PER /tts myvoice
# -------------------------------------------------------------------
class VoiceSelect(ui.Select):
    def __init__(self, voices: List[str]):
        options = [discord.SelectOption(label=v) for v in voices[:25]]
        super().__init__(placeholder="Scegli la tua voce...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        cog: "TTSCog" = interaction.client.get_cog("TTSCog")
        user_id = str(interaction.user.id)

        cog.tts_config["user_voices"][user_id] = self.values[0]
        cog.save_config()

        await interaction.response.send_message(f"✅ Voce personale impostata su **{self.values[0]}**", ephemeral=True)


class VoiceSelectView(ui.View):
    def __init__(self, voices: List[str]):
        super().__init__(timeout=60)
        self.add_item(VoiceSelect(voices))


# -------------------------------------------------------------------
#  MAIN COG
# -------------------------------------------------------------------
class TTSCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.voice_manager = VoiceManager(ELEVENLABS_API_KEY)
        self.audio_queue = deque()
        self.load_config()

        try:
            self.voice_manager.fetch_voices()
        except:
            pass

        self.update_voice_cache.start()

    # ------------------------------
    # Config
    # ------------------------------
    def load_config(self):
        if not os.path.exists(TTS_JSON):
            default_cfg = {
                "preset": "maschio",
                "presets": {
                    "maschio": "Luca",
                    "femmina": "Sofia"
                },
                "user_voices": {},
                "profiles": {
                    "narratore": {"stability": 0.7, "similarity_boost": 0.9},
                    "robotico": {"stability": 1.0, "similarity_boost": 0.2},
                    "profondo": {"stability": 0.9, "similarity_boost": 0.7},
                    "giovane": {"stability": 0.8, "similarity_boost": 0.95}
                }
            }
            with open(TTS_JSON, "w", encoding="utf-8") as f:
                json.dump(default_cfg, f, indent=2, ensure_ascii=False)

        with open(TTS_JSON, "r", encoding="utf-8") as f:
            self.tts_config = json.load(f)

    def save_config(self):
        with open(TTS_JSON, "w", encoding="utf-8") as f:
            json.dump(self.tts_config, f, indent=2, ensure_ascii=False)

    @tasks.loop(minutes=2)
    async def update_voice_cache(self):
        try:
            self.voice_manager.fetch_voices()
        except:
            pass

    # ------------------------------
    # AUDIO PLAYBACK
    # ------------------------------
    def play_next_audio(self, interaction: discord.Interaction, error=None):
        if error:
            logger.error(error)

        if self.audio_queue:
            stream = self.audio_queue.popleft()
            stream.seek(0)
            source = discord.FFmpegPCMAudio(stream, pipe=True)
            interaction.guild.voice_client.play(
                source,
                after=lambda e: self.play_next_audio(interaction, e)
            )
        else:
            try:
                asyncio.create_task(interaction.guild.voice_client.disconnect())
            except:
                pass

    async def ensure_voice(self, interaction: discord.Interaction):
        if not interaction.user.voice:
            await interaction.response.send_message("❌ Devi essere in un canale vocale.", ephemeral=True)
            raise commands.CommandError("No VC")
        vc = interaction.guild.voice_client
        channel = interaction.user.voice.channel
        if not vc:
            await channel.connect()
        elif vc.channel != channel:
            await vc.move_to(channel)

    # -------------------------------------------------------------------
    #   COMMAND GROUP
    # -------------------------------------------------------------------
    tts = app_commands.Group(name="tts", description="Sistema di TTS")

    # -------------------------------------------------------------------
    # /tts say
    # -------------------------------------------------------------------
    @tts.command(name="say", description="Fai parlare il bot.")
    async def say(self, interaction: discord.Interaction, text: str):
        await self.ensure_voice(interaction)

        user_id = str(interaction.user.id)

        # Priorità voce:
        # 1. voce personale
        if user_id in self.tts_config["user_voices"]:
            voice_name = self.tts_config["user_voices"][user_id]

        # 2. preset globale
        else:
            preset = self.tts_config.get("preset", "maschio")
            voice_name = self.tts_config["presets"].get(preset, "Luca")

        # Cerca voce
        selected = self.voice_manager.find_voice_by_name(voice_name)

        if not selected:
            selected = random.choice(self.voice_manager.voice_cache)

        voice_id = selected["voice_id"]

        stream = self.voice_manager.fetch_audio_stream(text, voice_id)

        if not stream:
            await interaction.response.send_message("❌ Errore nella generazione audio.", ephemeral=True)
            return

        await interaction.response.send_message("🔊 Sto parlando...", ephemeral=True)

        self.audio_queue.append(stream)
        if not interaction.guild.voice_client.is_playing():
            self.play_next_audio(interaction)

    # -------------------------------------------------------------------
    # PRESET COMMAND
    # -------------------------------------------------------------------
    @tts.command(name="preset", description="Imposta il preset globale (maschio o femmina).")
    @app_commands.describe(mode="maschio o femmina")
    async def preset(self, interaction: discord.Interaction, mode: str):
        mode = mode.lower()
        if mode not in ["maschio", "femmina"]:
            await interaction.response.send_message("❌ Opzioni valide: maschio / femmina", ephemeral=True)
            return

        self.tts_config["preset"] = mode
        self.save_config()

        await interaction.response.send_message(f"✅ Preset impostato su **{mode}**", ephemeral=True)

    # -------------------------------------------------------------------
    # /tts voice
    # -------------------------------------------------------------------
    @tts.command(name="voice", description="Imposta la tua voce personalizzata")
    async def voice(self, interaction: discord.Interaction, voice: str):
        user_id = str(interaction.user.id)
        self.tts_config["user_voices"][user_id] = voice
        self.save_config()

        await interaction.response.send_message(f"✅ Voce impostata su **{voice}**", ephemeral=True)

    # Autocomplete
    @voice.autocomplete("voice")
    async def voice_autocomplete(self, interaction: discord.Interaction, current: str):
        names = [v["name"] for v in self.voice_manager.voice_cache]
        filtered = [n for n in names if current.lower() in n.lower()]
        return [app_commands.Choice(name=n, value=n) for n in filtered[:25]]

    # -------------------------------------------------------------------
    # SELECT MENU /tts myvoice
    # -------------------------------------------------------------------
    @tts.command(name="myvoice", description="Scegli la tua voce da una lista.")
    async def myvoice(self, interaction: discord.Interaction):
        names = [v["name"] for v in self.voice_manager.voice_cache]
        view = VoiceSelectView(names)
        await interaction.response.send_message("🎤 Scegli la tua voce:", view=view, ephemeral=True)

    # -------------------------------------------------------------------
    # /tts list
    # -------------------------------------------------------------------
    @tts.command(name="list", description="Lista delle voci disponibili.")
    async def list(self, interaction: discord.Interaction):
        names = [v["name"] for v in self.voice_manager.voice_cache]
        text = "\n".join(f"• {n}" for n in names)
        await interaction.response.send_message(f"🎙️ **Voci disponibili:**\n{text}", ephemeral=True)

    # -------------------------------------------------------------------
    # /tts resetvoice
    # -------------------------------------------------------------------
    @tts.command(name="resetvoice", description="Rimuove la tua voce personale.")
    async def resetvoice(self, interaction: discord.Interaction):
        user = str(interaction.user.id)

        if user not in self.tts_config["user_voices"]:
            await interaction.response.send_message("ℹ️ Non hai una voce personalizzata.", ephemeral=True)
            return

        del self.tts_config["user_voices"][user]
        self.save_config()

        await interaction.response.send_message("🔄 Voce personale rimossa.", ephemeral=True)

    # -------------------------------------------------------------------
    # /tts stop
    # -------------------------------------------------------------------
    @tts.command(name="stop", description="Ferma il TTS.")
    async def stop(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        self.audio_queue.clear()

        if vc and vc.is_playing():
            vc.stop()

        await interaction.response.send_message("⏹️ TTS fermato.", ephemeral=True)


async def setup(bot):
    cog = TTSCog(bot)
    await bot.add_cog(cog)
    try:
        if bot.tree.get_command('tts') is None:
            bot.tree.add_command(cog.tts)
    except Exception as e:
        logger.error(f'Errore registrando gruppo tts: {e}')
