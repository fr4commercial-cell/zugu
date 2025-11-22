import discord
from discord import app_commands
from discord.ext import commands
import json
import os
from typing import Dict, Any, Optional

from .console_logger import logger
from .coralmc import CoralMCClient, PlayerStats

LINKS_FILE = os.path.join(os.path.dirname(__file__), 'mc_links.json')

def _load_links() -> Dict[str, Any]:
    if not os.path.exists(LINKS_FILE):
        return {}
    try:
        with open(LINKS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

def _save_links(data: Dict[str, Any]):
    try:
        with open(LINKS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f'Errore salvataggio mc_links.json: {e}')

class LoginCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.client = CoralMCClient()
        self.links: Dict[str, Any] = _load_links()

    async def _fetch_level(self, username: str) -> Optional[int]:
        stats = await self.client.get_player_stats(username)
        if not stats:
            return None
        try:
            return int(stats.bedwars.get('level', 0))
        except Exception:
            return None

    async def _apply_nick(self, member: discord.Member, level: int):
        prefix = f'✪{level}'
        # Limite 32 caratteri
        base = member.display_name
        new_nick = f'{prefix} {base}'
        if len(new_nick) > 32:
            # taglia il base
            overflow = len(new_nick) - 32
            base_short = base[:-overflow] if overflow < len(base) else base[:10]
            new_nick = f'{prefix} {base_short}'
        try:
            await member.edit(nick=new_nick, reason='Collegamento CoralMC /login')
            return new_nick
        except discord.Forbidden:
            return None
        except discord.HTTPException:
            return None

    @app_commands.command(name='login', description='Collega il tuo username Minecraft e mostra le stelle BedWars nel nickname')
    @app_commands.describe(username='Il tuo username Minecraft')
    async def login_cmd(self, interaction: discord.Interaction, username: str):
        await interaction.response.defer(ephemeral=True, thinking=True)
        member = interaction.user
        if not self.client.is_username_valid(username):
            await interaction.followup.send('❌ Username non valido.', ephemeral=True)
            return
        level = await self._fetch_level(username)
        if level is None:
            await interaction.followup.send('❌ Impossibile recuperare le tue statistiche BedWars (utente non trovato o API).', ephemeral=True)
            return
        # Salva original nick (una sola volta)
        uid = str(member.id)
        original = member.nick or member.name
        entry = self.links.get(uid)
        if entry and 'original_nick' in entry:
            original = entry['original_nick']
        self.links[uid] = {
            'minecraft': username,
            'original_nick': original,
            'last_level': level
        }
        _save_links(self.links)
        new_nick = await self._apply_nick(member, level)
        if not new_nick:
            await interaction.followup.send('⚠️ Non posso modificare il tuo nickname (permessi o gerarchia). Collegamento salvato comunque.', ephemeral=True)
        else:
            await interaction.followup.send(f'✅ Collegato `{username}`. Livello BedWars: `{level}`. Nick aggiornato: **{new_nick}**', ephemeral=True)

    @app_commands.command(name='login_update', description='Aggiorna il tuo nickname con il nuovo livello BedWars')
    async def login_update_cmd(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        uid = str(interaction.user.id)
        data = self.links.get(uid)
        if not data:
            await interaction.followup.send('❌ Non hai ancora usato /login.', ephemeral=True)
            return
        username = data['minecraft']
        level = await self._fetch_level(username)
        if level is None:
            await interaction.followup.send('❌ Impossibile recuperare statistiche dal tuo username salvato.', ephemeral=True)
            return
        data['last_level'] = level
        _save_links(self.links)
        new_nick = await self._apply_nick(interaction.user, level)
        if not new_nick:
            await interaction.followup.send('⚠️ Collegamento aggiornato ma impossibile cambiare nickname (permessi).', ephemeral=True)
        else:
            await interaction.followup.send(f'✅ Nick aggiornato con livello `{level}`.', ephemeral=True)

    @app_commands.command(name='login_unlink', description='Rimuove il collegamento Minecraft e ripristina il nickname')
    async def login_unlink_cmd(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        uid = str(interaction.user.id)
        data = self.links.pop(uid, None)
        if not data:
            await interaction.followup.send('ℹ️ Nessun collegamento da rimuovere.', ephemeral=True)
            return
        _save_links(self.links)
        original = data.get('original_nick')
        if original:
            try:
                await interaction.user.edit(nick=original, reason='Rimozione collegamento /login')
            except Exception:
                pass
        await interaction.followup.send('✅ Collegamento rimosso.', ephemeral=True)

async def setup(bot: commands.Bot):
    # Evita doppia registrazione su reload
    existing = bot.tree.get_command('login')
    if existing:
        bot.tree.remove_command('login')
    existing = bot.tree.get_command('login_update')
    if existing:
        bot.tree.remove_command('login_update')
    existing = bot.tree.get_command('login_unlink')
    if existing:
        bot.tree.remove_command('login_unlink')
    await bot.add_cog(LoginCog(bot))