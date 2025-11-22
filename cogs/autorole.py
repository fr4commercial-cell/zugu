import discord
from discord.ext import commands
from discord import app_commands
import json
import os

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.json')

def _read_config():
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

def _write_config(data: dict):
    try:
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass

class Autorole(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._load_local()

    def _load_local(self):
        cfg = _read_config()
        self.enabled: bool = cfg.get('autorole_enabled', True)
        self.role_ids: list[int] = cfg.get('autorole_role_ids', [])
        self.default_name: str = cfg.get('autorole_default_name', 'Member')

    def _persist(self):
        cfg = _read_config()
        cfg['autorole_enabled'] = self.enabled
        cfg['autorole_role_ids'] = self.role_ids
        cfg['autorole_default_name'] = self.default_name
        _write_config(cfg)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if not self.enabled:
            return
        # Assign configured roles
        assigned_any = False
        for rid in self.role_ids:
            role = member.guild.get_role(rid)
            if role:
                try:
                    await member.add_roles(role, reason='Autorole')
                    assigned_any = True
                except Exception:
                    pass
        # Fallback: create/find default role if none assigned
        if not assigned_any and self.default_name:
            role = discord.utils.get(member.guild.roles, name=self.default_name)
            if not role:
                try:
                    role = await member.guild.create_role(name=self.default_name, reason='Create default autorole')
                except Exception:
                    role = None
            if role:
                try:
                    await member.add_roles(role, reason='Autorole default')
                except Exception:
                    pass

    autorole_group = app_commands.Group(name='autorole', description='Gestione autorole')

    @autorole_group.command(name='addrole', description='Aggiunge un ruolo alla lista autorole')
    @app_commands.describe(role='Ruolo da assegnare ai nuovi membri')
    async def addrole_cmd(self, interaction: discord.Interaction, role: discord.Role):
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message('❌ Permessi insufficienti.', ephemeral=True)
            return
        if role.id in self.role_ids:
            await interaction.response.send_message('⚠️ Ruolo già presente.', ephemeral=True)
            return
        self.role_ids.append(role.id)
        self._persist()
        await interaction.response.send_message(f'✅ Ruolo aggiunto: {role.name}', ephemeral=True)

    @autorole_group.command(name='removerole', description='Rimuove un ruolo dalla lista autorole')
    @app_commands.describe(role='Ruolo da rimuovere')
    async def removerole_cmd(self, interaction: discord.Interaction, role: discord.Role):
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message('❌ Permessi insufficienti.', ephemeral=True)
            return
        if role.id not in self.role_ids:
            await interaction.response.send_message('⚠️ Ruolo non presente.', ephemeral=True)
            return
        self.role_ids = [r for r in self.role_ids if r != role.id]
        self._persist()
        await interaction.response.send_message(f'✅ Ruolo rimosso: {role.name}', ephemeral=True)

    @autorole_group.command(name='list', description='Mostra configurazione autorole')
    async def list_cmd(self, interaction: discord.Interaction):
        roles_fmt = []
        guild = interaction.guild
        for rid in self.role_ids:
            role = guild.get_role(rid)
            roles_fmt.append(role.name if role else f'ID:{rid} (missing)')
        roles_str = ', '.join(roles_fmt) if roles_fmt else 'Nessun ruolo configurato'
        status = 'Attivo' if self.enabled else 'Disattivato'
        await interaction.response.send_message(f'Autorole: {status}\nRuoli: {roles_str}\nDefault fallback: {self.default_name or "(none)"}', ephemeral=True)

    @autorole_group.command(name='enable', description='Attiva autorole')
    async def enable_cmd(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message('❌ Permessi insufficienti.', ephemeral=True)
            return
        self.enabled = True
        self._persist()
        await interaction.response.send_message('✅ Autorole attivato.', ephemeral=True)

    @autorole_group.command(name='disable', description='Disattiva autorole')
    async def disable_cmd(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message('❌ Permessi insufficienti.', ephemeral=True)
            return
        self.enabled = False
        self._persist()
        await interaction.response.send_message('✅ Autorole disattivato.', ephemeral=True)

    @autorole_group.command(name='setdefault', description='Imposta nome ruolo fallback se lista vuota')
    @app_commands.describe(name='Nome ruolo da creare/usare se nessun ruolo configurato')
    async def setdefault_cmd(self, interaction: discord.Interaction, name: str):
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message('❌ Permessi insufficienti.', ephemeral=True)
            return
        if len(name) > 50:
            await interaction.response.send_message('❌ Nome troppo lungo (max 50).', ephemeral=True)
            return
        self.default_name = name
        self._persist()
        await interaction.response.send_message(f'✅ Default fallback impostato a: {name}', ephemeral=True)

async def setup(bot: commands.Bot):
    cog = Autorole(bot)
    await bot.add_cog(cog)
    try:
        if bot.tree.get_command('autorole') is None:
            bot.tree.add_command(cog.autorole_group)
    except Exception as e:
        print(f'Errore registrando gruppo autorole: {e}')
