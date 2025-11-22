import discord
from discord.ext import commands
from discord import ui, app_commands
import json
import os
import datetime
from bot_utils import owner_or_has_permissions
try:
    from .console_logger import logger
except Exception:
    import logging
    logger = logging.getLogger("verify")

# Path config (root)
BASE_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, '..'))
CONFIG_PATH = os.path.join(PROJECT_ROOT, 'config.json')

def load_config():
    if not os.path.exists(CONFIG_PATH):
        return {}
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_config(cfg: dict):
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

class VerifyView(ui.View):
    def __init__(self, role_id: int | None, *, button_label: str = 'Verificati', button_style: int = discord.ButtonStyle.success):
        super().__init__(timeout=None)
        self.role_id = role_id
        self.button_label = button_label[:80] or 'Verificati'
        self.button_style = button_style if button_style in (discord.ButtonStyle.primary, discord.ButtonStyle.secondary, discord.ButtonStyle.success, discord.ButtonStyle.danger) else discord.ButtonStyle.success
        # Dynamically create a button so we can customize label/style.
        self.verify_btn = ui.Button(label=self.button_label, style=self.button_style, custom_id='verify_button')
        self.verify_btn.callback = self._on_click
        self.add_item(self.verify_btn)

    async def _on_click(self, interaction: discord.Interaction):
        # Cooldown per utente (10s)
        cfg_root = load_config()
        ver_cfg = cfg_root.get('verification', {})
        cd_map = ver_cfg.setdefault('_cooldowns', {})
        now = int(datetime.datetime.utcnow().timestamp())
        last = cd_map.get(str(interaction.user.id), 0)
        if now - last < 10:
            remaining = 10 - (now - last)
            await interaction.response.send_message(f'⏳ Attendi {remaining}s prima di riprovare.', ephemeral=True)
            return
        cd_map[str(interaction.user.id)] = now
        cfg_root['verification'] = ver_cfg
        save_config(cfg_root)
        if interaction.user.bot:
            await interaction.response.send_message('I bot non possono essere verificati.', ephemeral=True)
            return
        cfg = load_config().get('verification', {})
        role = None
        if self.role_id:
            role = interaction.guild.get_role(self.role_id)
        if role is None:
            name = cfg.get('role_name', 'Verified')
            role = discord.utils.get(interaction.guild.roles, name=name)
        if role is None:
            name = cfg.get('role_name', 'Verified')
            role = await interaction.guild.create_role(name=name)
        try:
            await interaction.user.add_roles(role, reason='User verified')
        except Exception as e:
            logger.error(f"Errore assegnando ruolo verifica: {e}")
            await interaction.response.send_message('❌ Errore nel dare il ruolo di verifica.', ephemeral=True)
            return
        logger.info(f"Utente verificato: {interaction.user} ({interaction.user.id})")
        await interaction.response.send_message('✅ Verifica completata! Ora hai accesso al server.', ephemeral=True)
        # Log su canale dedicato se configurato
        try:
            parent_cog = interaction.client.get_cog('Verify')
            if parent_cog:
                await parent_cog._log_verification(interaction.guild, 'button', interaction.user, staffer=None)
        except Exception:
            pass

class Verify(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = load_config()
        if 'verification' not in self.config:
            self.config['verification'] = {}
            save_config(self.config)

    def _get_verification_cfg(self):
        self.config = load_config()
        return self.config.setdefault('verification', {})

    def _save_verification_cfg(self, data: dict):
        self.config = load_config()
        self.config['verification'] = data
        save_config(self.config)

    async def _log_verification(self, guild: discord.Guild, action: str, member: discord.Member, staffer: str | None):
        ver_cfg = self._get_verification_cfg()
        channel_id = ver_cfg.get('log_channel_id')
        if not channel_id:
            return
        channel = guild.get_channel(int(channel_id))
        if not isinstance(channel, discord.TextChannel):
            return
        try:
            embed = discord.Embed(title='Log Verifica', description=f'Azione: **{action}**', color=0x2ECC71)
            embed.add_field(name='Utente', value=f'{member.mention}\n`{member.id}`', inline=True)
            if staffer:
                embed.add_field(name='Staff', value=staffer, inline=True)
            embed.timestamp = datetime.datetime.utcnow()
            await channel.send(embed=embed)
        except Exception as e:
            logger.error(f'Errore invio log verifica: {e}')

    def _build_view(self):
        ver_cfg = self._get_verification_cfg()
        role_id = ver_cfg.get('role_id')
        label = ver_cfg.get('button_label', 'Verificati')
        style_name = ver_cfg.get('button_style', 'success').lower()
        style_map = {
            'primary': discord.ButtonStyle.primary,
            'secondary': discord.ButtonStyle.secondary,
            'success': discord.ButtonStyle.success,
            'danger': discord.ButtonStyle.danger
        }
        style = style_map.get(style_name, discord.ButtonStyle.success)
        return VerifyView(role_id, button_label=label, button_style=style)

    def _build_embed(self):
        ver_cfg = self._get_verification_cfg()
        if not ver_cfg.get('embed_enabled'):
            return None
        title = ver_cfg.get('embed_title', 'Verifica')
        desc = ver_cfg.get('embed_description', 'Clicca il bottone per verificarti!')
        color_val = ver_cfg.get('embed_color', 0x2ECC71)
        try:
            color = int(str(color_val), 16) if isinstance(color_val, str) else int(color_val)
        except Exception:
            color = 0x2ECC71
        embed = discord.Embed(title=title, description=desc, color=color)
        if ver_cfg.get('embed_thumbnail'):
            embed.set_thumbnail(url=ver_cfg['embed_thumbnail'])
        if ver_cfg.get('embed_footer'):
            embed.set_footer(text=ver_cfg['embed_footer'])
        return embed

    async def _send_panel(self, channel: discord.TextChannel, *, replace: bool = False):
        ver_cfg = self._get_verification_cfg()
        view = self._build_view()
        # Clean previous message if replace
        if replace:
            try:
                old_id = ver_cfg.get('message_id')
                if old_id:
                    msg = await channel.fetch_message(int(old_id))
                    await msg.delete()
            except Exception:
                pass
        embed = self._build_embed()
        if embed:
            msg = await channel.send(embed=embed, view=view)
        else:
            content = ver_cfg.get('panel_text', 'Clicca il bottone per verificarti!')
            msg = await channel.send(content, view=view)
        ver_cfg['message_id'] = msg.id
        self._save_verification_cfg(ver_cfg)

    @commands.Cog.listener()
    async def on_ready(self):
        # Optionally resend panel if configured with auto_resend
        ver_cfg = self._get_verification_cfg()
        channel_id = ver_cfg.get('channel_id')
        auto = ver_cfg.get('auto_resend', False)
        if channel_id and auto:
            channel = self.bot.get_channel(int(channel_id))
            if isinstance(channel, discord.TextChannel):
                try:
                    await self._send_panel(channel, replace=False)
                except Exception:
                    pass

    verify_group = app_commands.Group(name='verify', description='Gestione verifica utenti')

    @verify_group.command(name='setchannel', description='Imposta il canale di verifica')
    @owner_or_has_permissions(administrator=True)
    @app_commands.describe(channel='Canale da usare per la verifica')
    async def set_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        ver_cfg = self._get_verification_cfg()
        ver_cfg['channel_id'] = channel.id
        self._save_verification_cfg(ver_cfg)
        await interaction.response.send_message(f'✅ Canale di verifica impostato a {channel.mention}.', ephemeral=True)

    @verify_group.command(name='setrole', description='Imposta il ruolo assegnato alla verifica')
    @owner_or_has_permissions(manage_roles=True)
    @app_commands.describe(role='Ruolo da assegnare ai verificati', name='Nuovo nome ruolo (facoltativo)')
    async def set_role(self, interaction: discord.Interaction, role: discord.Role, name: str | None = None):
        ver_cfg = self._get_verification_cfg()
        if name:
            try:
                await role.edit(name=name, reason='Rename verify role')
            except Exception:
                pass
            ver_cfg['role_name'] = name
        ver_cfg['role_id'] = role.id
        self._save_verification_cfg(ver_cfg)
        await interaction.response.send_message(f'✅ Ruolo di verifica impostato: {role.mention}.', ephemeral=True)

    @verify_group.command(name='panel', description='Invia o sostituisce il pannello di verifica nel canale configurato')
    @owner_or_has_permissions(administrator=True)
    @app_commands.describe(replace='Se vero, sostituisce il pannello precedente', text='Testo sopra il bottone')
    async def send_panel(self, interaction: discord.Interaction, replace: bool = False, text: str | None = None):
        ver_cfg = self._get_verification_cfg()
        channel_id = ver_cfg.get('channel_id')
        if not channel_id:
            await interaction.response.send_message('❌ Nessun canale configurato. Usa /verify setchannel.', ephemeral=True)
            return
        channel = interaction.guild.get_channel(int(channel_id))
        if channel is None:
            await interaction.response.send_message('❌ Il canale configurato non esiste più.', ephemeral=True)
            return
        if text:
            ver_cfg['panel_text'] = text
            self._save_verification_cfg(ver_cfg)
        await self._send_panel(channel, replace=replace)
        await interaction.response.send_message('✅ Pannello inviato.', ephemeral=True)
        logger.info(f"Pannello verifica inviato in {channel.id} (replace={replace})")

    @verify_group.command(name='editpanel', description='Modifica il pannello di verifica esistente (testo / bottone)')
    @owner_or_has_permissions(administrator=True)
    @app_commands.describe(text='Nuovo testo (facoltativo)', button_label='Nuova label del bottone', button_style='Stile bottone: primary/secondary/success/danger')
    async def edit_panel(self, interaction: discord.Interaction, text: str | None = None, button_label: str | None = None, button_style: str | None = None):
        ver_cfg = self._get_verification_cfg()
        channel_id = ver_cfg.get('channel_id')
        message_id = ver_cfg.get('message_id')
        if not channel_id or not message_id:
            await interaction.response.send_message('❌ Nessun pannello da modificare. Usa /verify panel prima.', ephemeral=True)
            return
        channel = interaction.guild.get_channel(int(channel_id))
        if channel is None:
            await interaction.response.send_message('❌ Il canale configurato non esiste più.', ephemeral=True)
            return
        try:
            msg = await channel.fetch_message(int(message_id))
        except Exception:
            await interaction.response.send_message('❌ Messaggio pannello non trovato. Reinvia con /verify panel.', ephemeral=True)
            return
        changed = []
        if text:
            ver_cfg['panel_text'] = text
            changed.append('testo')
        if button_label:
            ver_cfg['button_label'] = button_label[:80]
            changed.append('label bottone')
        if button_style and button_style.lower() in ('primary','secondary','success','danger'):
            ver_cfg['button_style'] = button_style.lower()
            changed.append('stile bottone')
        self._save_verification_cfg(ver_cfg)
        # rebuild view + embed
        view = self._build_view()
        embed = self._build_embed()
        try:
            if embed:
                await msg.edit(embed=embed, view=view)
            else:
                await msg.edit(content=ver_cfg.get('panel_text', msg.content), view=view)
        except Exception as e:
            await interaction.response.send_message(f'❌ Errore modifica: {e}', ephemeral=True)
            return
        if not changed:
            await interaction.response.send_message('ℹ️ Nessuna modifica fornita.', ephemeral=True)
        else:
            await interaction.response.send_message('✅ Modifica pannello riuscita: ' + ', '.join(changed), ephemeral=True)
        logger.info(f"Pannello verifica modificato: {', '.join(changed) if changed else 'nessuna modifica'}")

    @verify_group.command(name='forceverify', description='Verifica forzatamente un utente assegnando il ruolo')
    @owner_or_has_permissions(manage_roles=True)
    @app_commands.describe(member='Utente da verificare')
    async def force_verify(self, interaction: discord.Interaction, member: discord.Member):
        ver_cfg = self._get_verification_cfg()
        role_id = ver_cfg.get('role_id')
        role = None
        if role_id:
            role = interaction.guild.get_role(int(role_id))
        if role is None:
            # fallback name search
            role = discord.utils.get(interaction.guild.roles, name=ver_cfg.get('role_name', 'Verified'))
        if role is None:
            role = await interaction.guild.create_role(name=ver_cfg.get('role_name', 'Verified'), reason='Create verify role')
            ver_cfg['role_id'] = role.id
            self._save_verification_cfg(ver_cfg)
        try:
            await member.add_roles(role, reason='Force verify')
            await interaction.response.send_message(f'✅ {member.mention} verificato.', ephemeral=True)
            logger.info(f"Force verify: {member} ({member.id})")
            await self._log_verification(interaction.guild, 'forceverify', member, staffer=str(interaction.user))
        except Exception as e:
            logger.error(f"Force verify error: {e}")
            await interaction.response.send_message(f'❌ Errore: {e}', ephemeral=True)

    @verify_group.command(name='remove', description='Rimuove il ruolo di verifica da un utente')
    @owner_or_has_permissions(manage_roles=True)
    @app_commands.describe(member='Utente da rimuovere dalla verifica')
    async def remove_verify(self, interaction: discord.Interaction, member: discord.Member):
        ver_cfg = self._get_verification_cfg()
        role_id = ver_cfg.get('role_id')        
        role = None
        if role_id:
            role = interaction.guild.get_role(int(role_id))
        if role is None:
            role = discord.utils.get(interaction.guild.roles, name=ver_cfg.get('role_name', 'Verified'))
        if role is None:
            await interaction.response.send_message('❌ Ruolo di verifica non trovato.', ephemeral=True)
            return
        try:
            await member.remove_roles(role, reason='Remove verify')
            await interaction.response.send_message(f'✅ Rimosso ruolo verifica da {member.mention}.', ephemeral=True)
            logger.info(f"Verifica rimossa da {member} ({member.id})")
            await self._log_verification(interaction.guild, 'remove', member, staffer=str(interaction.user))
        except Exception as e:
            logger.error(f"Errore rimozione verifica: {e}")
            await interaction.response.send_message(f'❌ Errore: {e}', ephemeral=True)

    @verify_group.command(name='config', description='Mostra la configurazione verifica corrente')
    async def show_config(self, interaction: discord.Interaction):
        ver_cfg = self._get_verification_cfg()
        channel_id = ver_cfg.get('channel_id')
        role_id = ver_cfg.get('role_id')
        message_id = ver_cfg.get('message_id')
        auto = ver_cfg.get('auto_resend', False)
        panel_text = ver_cfg.get('panel_text', 'Clicca il bottone per verificarti!')
        lines = [
            f'Canale: {f"<#{channel_id}>" if channel_id else "Non impostato"}',
            f'Ruolo: {f"<@&{role_id}>" if role_id else "Non impostato"}',
            f'Messaggio pannello ID: {message_id or "N/D"}',
            f'Auto resend: {"Attivo" if auto else "Disattivo"}',
            f'Testo pannello: {panel_text[:80] + ("..." if len(panel_text) > 80 else "")}'
        ]
        await interaction.response.send_message('\n'.join(lines), ephemeral=True)

    @verify_group.command(name='autoresend', description='Attiva/Disattiva la reinvio automatico del pannello a restart')
    @owner_or_has_permissions(administrator=True)
    @app_commands.describe(enabled='True/False')
    async def autoresend(self, interaction: discord.Interaction, enabled: bool):
        ver_cfg = self._get_verification_cfg()
        ver_cfg['auto_resend'] = enabled
        self._save_verification_cfg(ver_cfg)
        await interaction.response.send_message(f'✅ Auto resend impostato a {enabled}.', ephemeral=True)
        logger.info(f"Auto resend verifica impostato a {enabled}")
        await self._log_verification(interaction.guild, 'autoresend_toggle', interaction.user, staffer=str(interaction.user))

    @verify_group.command(name='setlogchannel', description='Imposta il canale log per le verifiche')
    @owner_or_has_permissions(administrator=True)
    async def set_log_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        ver_cfg = self._get_verification_cfg()
        ver_cfg['log_channel_id'] = channel.id
        self._save_verification_cfg(ver_cfg)
        await interaction.response.send_message(f'✅ Canale log verifica impostato a {channel.mention}.', ephemeral=True)

    # ---------------- EMBED CONFIG COMMANDS -----------------
    embed_group = app_commands.Group(name='verifyembed', description='Config embed verifica')

    @embed_group.command(name='toggle', description='Abilita/Disabilita embed nel pannello verifica')
    @owner_or_has_permissions(administrator=True)
    async def embed_toggle(self, interaction: discord.Interaction, enabled: bool):
        ver_cfg = self._get_verification_cfg()
        ver_cfg['embed_enabled'] = enabled
        self._save_verification_cfg(ver_cfg)
        await interaction.response.send_message(f'✅ Embed verifica {"abilitato" if enabled else "disabilitato"}.', ephemeral=True)
        logger.info(f"Embed verifica toggle: {enabled}")

    @embed_group.command(name='configure', description='Configura campi embed (titolo, descrizione, colore, footer, thumbnail)')
    @owner_or_has_permissions(administrator=True)
    @app_commands.describe(title='Titolo', description='Descrizione', color='Colore HEX (#RRGGBB) o int', footer='Footer', thumbnail='URL thumbnail')
    async def embed_configure(self, interaction: discord.Interaction, title: str | None = None, description: str | None = None, color: str | None = None, footer: str | None = None, thumbnail: str | None = None):
        ver_cfg = self._get_verification_cfg()
        changed = []
        if title:
            ver_cfg['embed_title'] = title[:256]
            changed.append('titolo')
        if description:
            ver_cfg['embed_description'] = description[:2000]
            changed.append('descrizione')
        if color:
            c = color.strip()
            try:
                if c.startswith('#'):
                    c = c[1:]
                ver_cfg['embed_color'] = int(c, 16)
                changed.append('colore')
            except Exception:
                await interaction.response.send_message('❌ Colore non valido. Usa formato #RRGGBB.', ephemeral=True)
                return
        if footer:
            ver_cfg['embed_footer'] = footer[:256]
            changed.append('footer')
        if thumbnail:
            ver_cfg['embed_thumbnail'] = thumbnail
            changed.append('thumbnail')
        self._save_verification_cfg(ver_cfg)
        await interaction.response.send_message('✅ Campi embed aggiornati: ' + (', '.join(changed) if changed else 'nessuna modifica'), ephemeral=True)
        logger.info(f"Embed verifica configurato: {', '.join(changed) if changed else 'no changes'}")

async def setup(bot):
    cog = Verify(bot)
    await bot.add_cog(cog)
    # Registra gruppi slash se non già presenti
    try:
        if bot.tree.get_command('verify') is None:
            bot.tree.add_command(cog.verify_group)
        if bot.tree.get_command('verifyembed') is None:
            bot.tree.add_command(cog.embed_group)
    except Exception as e:
        logger.error(f'Errore registrando gruppi verify: {e}')
