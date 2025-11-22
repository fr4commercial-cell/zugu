import discord
from discord import app_commands
from discord.ext import commands, tasks
import json
import os
import re
import asyncio
from typing import Dict, Any, Optional
import time

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
        # Struttura: { user_id: { minecraft, last_level, last_check_ts } }
        # Aggiunge sezione impostazioni globale: __settings__ -> { suffix }
        if '__settings__' not in self.links or not isinstance(self.links['__settings__'], dict):
            self.links['__settings__'] = {'suffix': '✪'}
        for uid, data in self.links.items():
            if 'last_check_ts' not in data:
                data['last_check_ts'] = 0
        self.auto_update_levels.start()

    def _get_suffix(self) -> str:
        settings = self.links.get('__settings__', {})
        suf = settings.get('suffix', '✪')
        # Limita lunghezza per Discord nickname (evita abusi)
        return str(suf)[:4]

    def _set_suffix(self, new_suffix: str):
        self.links.setdefault('__settings__', {})['suffix'] = new_suffix[:4]
        _save_links(self.links)

    async def _fetch_level(self, username: str) -> Optional[int]:
        stats = await self.client.get_player_stats(username)
        if not stats:
            return None
        try:
            return int(stats.bedwars.get('level', 0))
        except Exception:
            return None

    async def _apply_nick(self, member: discord.Member, level: int):
        base_suffix_symbol = self._get_suffix()
        suffix = f'{base_suffix_symbol}{level}'
        base = member.display_name
        # Rimuove eventuale suffisso precedente formato SYMBOL + digits
        sanitized = re.sub(r'\s*[^\s\d]\d+$', '', base).strip()
        candidate = f'{sanitized} {suffix}'
        if len(candidate) > 32:
            # Taglia la parte base mantenendo suffisso
            max_base_len = 32 - (len(suffix) + 1)
            sanitized = sanitized[:max_base_len].rstrip()
            candidate = f'{sanitized} {suffix}'
        try:
            await member.edit(nick=candidate, reason='Collegamento CoralMC /login append')
            return candidate
        except (discord.Forbidden, discord.HTTPException):
            return None

    @tasks.loop(hours=6)
    async def auto_update_levels(self):
        await self.bot.wait_until_ready()
        # Aggiorna il livello e suffisso per ogni utente collegato
        for uid, data in list(self.links.items()):
            username = data.get('minecraft')
            if not username:
                continue
            level = await self._fetch_level(username)
            if level is None:
                continue
            if level != data.get('last_level'):
                data['last_level'] = level
                member_id = int(uid)
                for guild in self.bot.guilds:
                    member = guild.get_member(member_id)
                    if member:
                        await self._apply_nick(member, level)
                _save_links(self.links)
            # Piccola pausa per non saturare l'API
            await asyncio.sleep(0.5)

    def cog_unload(self):
        try:
            self.auto_update_levels.cancel()
        except Exception:
            pass

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
        self.links[uid] = {
            'minecraft': username,
            'last_level': level,
            'last_check_ts': time.time()
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
        data['last_check_ts'] = time.time()
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
        # Rimuove suffisso (simbolo configurabile + cifra/e)
        current = interaction.user.display_name
        new_nick = re.sub(r'\s*[^\s\d]\d+$', '', current).strip()
        if new_nick and new_nick != current:
            try:
                await interaction.user.edit(nick=new_nick, reason='Rimozione suffisso /login')
            except Exception:
                pass
        await interaction.followup.send('✅ Collegamento rimosso (suffisso eliminato).', ephemeral=True)

    @app_commands.command(name='login_suffix', description='Mostra o imposta il suffisso prima del livello BedWars')
    @app_commands.describe(nuovo='Nuovo simbolo (max 4 caratteri). Lascia vuoto per visualizzare quello attuale.')
    async def login_suffix_cmd(self, interaction: discord.Interaction, nuovo: Optional[str] = None):
        await interaction.response.defer(ephemeral=True, thinking=True)
        if nuovo is None:
            await interaction.followup.send(f'Suffisso corrente: `{self._get_suffix()}`', ephemeral=True)
            return
        # Permessi: richiede manage_guild
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.followup.send('❌ Permessi insufficienti (serve Gestire Server).', ephemeral=True)
            return
        nuovo = nuovo.strip()
        if not nuovo:
            await interaction.followup.send('❌ Il suffisso non può essere vuoto.', ephemeral=True)
            return
        # Evita caratteri di controllo
        if any(ord(c) < 32 for c in nuovo):
            await interaction.followup.send('❌ Il suffisso contiene caratteri non validi.', ephemeral=True)
            return
        self._set_suffix(nuovo)
        await interaction.followup.send(f'✅ Suffisso aggiornato a `{self._get_suffix()}`. I prossimi aggiornamenti del nickname useranno questo simbolo.', ephemeral=True)

    @app_commands.command(name='login_list', description='Elenco degli utenti collegati /login')
    @app_commands.describe(page='Pagina (default 1)')
    async def login_list_cmd(self, interaction: discord.Interaction, page: int = 1):
        await interaction.response.defer(ephemeral=True, thinking=True)
        if page < 1:
            page = 1
        entries = []
        for uid, data in self.links.items():
            if uid == '__settings__':
                continue
            if not isinstance(data, dict):
                continue
            mc = data.get('minecraft')
            lvl = data.get('last_level')
            if not mc:
                continue
            entries.append((int(uid), mc, lvl))
        if not entries:
            await interaction.followup.send('Nessun utente collegato.', ephemeral=True)
            return
        # Ordina per livello desc, poi username
        entries.sort(key=lambda x: (-int(x[2]) if isinstance(x[2], int) else 0, x[1].lower()))
        per_page = 20
        total_pages = (len(entries) + per_page - 1) // per_page
        if page > total_pages:
            page = total_pages
        start = (page - 1) * per_page
        chunk = entries[start:start+per_page]
        lines = []
        for user_id, mc, lvl in chunk:
            mention = f'<@{user_id}>'
            lvl_str = str(lvl) if lvl is not None else '?'
            lines.append(f'{mention} • `{mc}` • ⭐ {lvl_str}')
        desc = '\n'.join(lines)
        embed = discord.Embed(title='Utenti collegati Minecraft', description=desc, color=discord.Color.gold())
        embed.set_footer(text=f'Pagina {page}/{total_pages} • Totale {len(entries)} utenti')
        await interaction.followup.send(embed=embed, ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        uid = str(message.author.id)
        data = self.links.get(uid)
        if not data:
            return
        now = time.time()
        # Controlla almeno ogni 5 minuti per evitare spam API
        if now - data.get('last_check_ts', 0) < 300:
            return
        username = data.get('minecraft')
        if not username:
            return
        level = await self._fetch_level(username)
        data['last_check_ts'] = now
        if level is None:
            return
        if level != data.get('last_level'):
            data['last_level'] = level
            # Aggiorna nickname se il membro è nel server
            member = message.guild.get_member(message.author.id) if message.guild else None
            if member:
                await self._apply_nick(member, level)
            _save_links(self.links)

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
    existing = bot.tree.get_command('login_suffix')
    if existing:
        bot.tree.remove_command('login_suffix')
    existing = bot.tree.get_command('login_list')
    if existing:
        bot.tree.remove_command('login_list')
    await bot.add_cog(LoginCog(bot))
