# tickets_cog.py
import discord
from discord.ext import commands
from discord import app_commands, ui
import json
import os
from datetime import datetime
from typing import Optional

BASE_DIR = os.path.dirname(__file__)
TICKETS_FILE = os.path.join(BASE_DIR, '..', 'tickets.json')
CONFIG_FILE = os.path.join(BASE_DIR, '..', 'config.json')

def load_json(path, default):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default

def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


class TicketFormModal(ui.Modal):
    def __init__(self, panel, cog):
        super().__init__(title=panel.get('name', 'Modulo Ticket'))
        self.panel = panel
        self.cog = cog
        # Create up to 5 fields from panel config
        for field in panel.get('fields', [])[:5]:
            style = discord.TextStyle.paragraph if len(field.get('name', '')) > 20 else discord.TextStyle.short
            self.add_item(ui.TextInput(
                label=field.get('name', 'Campo'),
                placeholder=field.get('placeholder', ''),
                required=field.get('required', True),
                style=style
            ))

    async def on_submit(self, interaction: discord.Interaction):
        # Send a summary embed in the ticket channel (the modal is triggered from a channel)
        embed = discord.Embed(
            title=f"📋 Informazioni Ticket - {self.panel.get('name')}",
            color=self.panel.get('color', 0x2ECC71),
            timestamp=datetime.utcnow()
        )
        for i, child in enumerate(self.children):
            fname = self.panel.get('fields', [])[i].get('name', f'Campo {i+1}') if i < len(self.panel.get('fields', [])) else f'Campo {i+1}'
            embed.add_field(name=fname, value=child.value or "—", inline=False)

        if self.panel.get('image'):
            embed.set_image(url=self.panel['image'])

        await interaction.response.send_message("✅ Informazioni registrate!", ephemeral=True)
        # If invoked from a channel, also post the embed there
        try:
            await interaction.channel.send(embed=embed)
        except Exception:
            pass


class TicketFormView(ui.View):
    def __init__(self, modal: TicketFormModal):
        super().__init__(timeout=None)
        self.modal = modal
        # Button that opens modal (server-side handling uses custom_id; we'll handle via callback)
        self.add_item(ui.Button(label="Compila Informazioni", style=discord.ButtonStyle.success, custom_id="open_modal_button"))

    @ui.button(label="Compila Informazioni", style=discord.ButtonStyle.success, custom_id="open_modal_button")
    async def open_modal(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(self.modal)


class TicketPanelButton(ui.Button):
    def __init__(self, panel, cog):
        super().__init__(
            label=panel.get('name', 'Ticket'),
            emoji=panel.get('emoji', None),
            style=discord.ButtonStyle.primary,
            custom_id=f"ticket_panel_{panel.get('name', 'panel').lower().replace(' ', '_')}"
        )
        self.panel = panel
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        # Create category if not exists and create ticket channel with appropriate overwrites
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        if guild is None:
            await interaction.followup.send("Errore: comando non eseguibile qui.", ephemeral=True)
            return

        category = discord.utils.get(guild.categories, name="Tickets")
        if category is None:
            try:
                category = await guild.create_category("Tickets")
            except Exception as e:
                await interaction.followup.send(f"❌ Errore nella creazione della categoria: {e}", ephemeral=True)
                return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        staff_role_id = self.cog.config.get("staff_role_id")
        if staff_role_id:
            staff_role = guild.get_role(staff_role_id)
            if staff_role:
                overwrites[staff_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        channel_name = f"ticket-{interaction.user.name.lower()}-{len(self.cog.tickets) + 1}"
        try:
            ticket_channel = await category.create_text_channel(channel_name, overwrites=overwrites)
        except Exception as e:
            await interaction.followup.send(f"❌ Errore nella creazione del canale ticket: {e}", ephemeral=True)
            return

        ticket_id = str(ticket_channel.id)
        self.cog.tickets[ticket_id] = {
            'author': interaction.user.id,
            'panel': self.panel.get('name'),
            'created_at': datetime.utcnow().isoformat(),
            'members': [interaction.user.id],
            'status': 'open'
        }
        self.cog.save_tickets()

        embed = discord.Embed(
            title=f"🎟️ Ticket: {self.panel.get('name')}",
            description=self.panel.get('description', ''),
            color=self.panel.get('color', 0x2ECC71)
        )
        embed.add_field(name="ID Ticket", value=ticket_id, inline=False)
        embed.add_field(name="Richiedente", value=interaction.user.mention, inline=False)
        embed.set_footer(text="Usa /ticket close per chiudere il ticket")

        if self.panel.get('image'):
            embed.set_image(url=self.panel['image'])

        try:
            await ticket_channel.send(embed=embed)
            # Send a modal-open button in the channel for the user to fill info (if panel has fields)
            if self.panel.get('fields'):
                modal = TicketFormModal(self.panel, self.cog)
                view = TicketFormView(modal)
                await ticket_channel.send("Premi il pulsante per compilare le informazioni del ticket:", view=view)
        except Exception:
            pass

        await interaction.followup.send(f"✅ Ticket creato: {ticket_channel.mention}", ephemeral=True)


class TicketPanelsView(ui.View):
    def __init__(self, panels, cog):
        super().__init__(timeout=None)
        for panel in panels:
            self.add_item(TicketPanelButton(panel, cog))


class Tickets(commands.Cog):
    """Cog che gestisce il sistema tickets (slash + comandi classici)"""
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.tickets = load_json(TICKETS_FILE, {})
        self.config = load_json(CONFIG_FILE, {})

        # Create an app_commands.Group and register commands that point to methods below.
        self.ticket_group = app_commands.Group(name="ticket", description="Gestione tickets")

        # Bind group commands to methods
        # Note: methods are already defined, we decorate them programmatically here.
        self.ticket_group.command(name="panel", description="Mostra il pannello per creare ticket")(self.ticket_panel)
        self.ticket_group.command(name="create", description="Crea un nuovo ticket")(self.create_ticket)
        self.ticket_group.command(name="close", description="Chiude il ticket nel canale attuale")(self.close_ticket)
        self.ticket_group.command(name="reopen", description="Riapri un ticket chiuso (solo staff)")(self.reopen_ticket)
        self.ticket_group.command(name="delete", description="Elimina definitivamente il ticket (solo staff)")(self.delete_ticket)
        # Register the group to the bot tree
        try:
            self.bot.tree.add_command(self.ticket_group)
        except Exception:
            # in some contexts the group may already be present; ignore
            pass

    # ---------- Helpers ----------
    def save_tickets(self):
        save_json(TICKETS_FILE, self.tickets)

    def save_config(self):
        save_json(CONFIG_FILE, self.config)

    # ---------- Slash commands (app commands) ----------
    async def ticket_panel(self, interaction: discord.Interaction):
        """/ticket panel"""
        await interaction.response.defer(ephemeral=True)
        panels = self.config.get("panels", [])
        if not panels:
            await interaction.followup.send("❌ Nessun pannello configurato.", ephemeral=True)
            return

        embed = discord.Embed(
            title="🎟️ Pannelli Ticket",
            description="Clicca su un pulsante per aprire un ticket:",
            color=0x3498DB
        )
        for panel in panels:
            emoji = panel.get("emoji", "📝")
            embed.add_field(name=f"{emoji} {panel.get('name')}", value=panel.get('description', 'Nessuna descrizione'), inline=False)

        view = TicketPanelsView(panels, self)
        try:
            # send in the current channel
            await interaction.followup.send(embed=embed, view=view)
        except Exception:
            try:
                await interaction.channel.send(embed=embed, view=view)
            except Exception:
                await interaction.followup.send("❌ Impossibile inviare il pannello.", ephemeral=True)

    async def create_ticket(self, interaction: discord.Interaction, topic: str):
        """/ticket create <topic>"""
        await interaction.response.defer()
        guild = interaction.guild
        if guild is None:
            await interaction.followup.send("Errore: comando non eseguibile qui.", ephemeral=True)
            return

        category = discord.utils.get(guild.categories, name="Tickets")
        if category is None:
            try:
                category = await guild.create_category("Tickets")
            except Exception as e:
                await interaction.followup.send(f"❌ Errore nella creazione della categoria: {e}", ephemeral=True)
                return

        channel_name = f"ticket-{interaction.user.name.lower()}-{len(self.tickets) + 1}"
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        staff_role_id = self.config.get("staff_role_id")
        if staff_role_id:
            staff_role = guild.get_role(staff_role_id)
            if staff_role:
                overwrites[staff_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        try:
            ticket_channel = await category.create_text_channel(channel_name, overwrites=overwrites)
        except Exception as e:
            await interaction.followup.send(f"❌ Errore nella creazione del canale ticket: {e}", ephemeral=True)
            return

        ticket_id = str(ticket_channel.id)
        self.tickets[ticket_id] = {
            'author': interaction.user.id,
            'topic': topic,
            'created_at': datetime.utcnow().isoformat(),
            'members': [interaction.user.id],
            'status': 'open'
        }
        self.save_tickets()

        embed = discord.Embed(
            title=f"🎟️ Ticket: {topic}",
            description=f"Ticket creato da {interaction.user.mention}",
            color=0x2ECC71
        )
        embed.add_field(name="ID Ticket", value=ticket_id, inline=False)
        embed.add_field(name="Data Creazione", value=datetime.utcnow().strftime("%d/%m/%Y %H:%M:%S"), inline=False)
        embed.set_footer(text="Usa /ticket close per chiudere il ticket")

        await ticket_channel.send(embed=embed)
        await interaction.followup.send(f"✅ Ticket creato: {ticket_channel.mention}", ephemeral=True)

    async def close_ticket(self, interaction: discord.Interaction):
        """/ticket close"""
        try:
            await interaction.response.defer()
        except Exception:
            pass

        channel_id = str(interaction.channel.id)
        if channel_id not in self.tickets:
            await interaction.followup.send("❌ Questo non è un canale ticket!", ephemeral=True)
            return

        ticket = self.tickets[channel_id]
        # permission checks
        staff_role_id = self.config.get("staff_role_id")
        is_staff = False
        if staff_role_id:
            staff_role = interaction.guild.get_role(staff_role_id)
            is_staff = staff_role in interaction.user.roles if staff_role else False

        if interaction.user.id != ticket['author'] and not is_staff and not interaction.user.guild_permissions.administrator:
            await interaction.followup.send("❌ Solo l'autore, lo staff o un admin può chiudere questo ticket!", ephemeral=True)
            return

        ticket['status'] = 'closed'
        self.save_tickets()

        author_member = interaction.guild.get_member(ticket['author'])
        if author_member:
            try:
                await interaction.channel.set_permissions(author_member, read_messages=True, send_messages=False)
            except Exception:
                pass

        embed = discord.Embed(
            title="🔒 Ticket Chiuso",
            description=f"Il ticket è stato chiuso da {interaction.user.mention}\nIl canale rimane visibile ma non puoi scrivere nuovi messaggi.",
            color=0xE74C3C
        )

        try:
            await interaction.followup.send("✅ Ticket chiuso.", ephemeral=True)
        except Exception:
            try:
                await interaction.channel.send("✅ Ticket chiuso.")
            except Exception:
                pass

        try:
            await interaction.channel.send(embed=embed)
        except Exception:
            pass

    async def reopen_ticket(self, interaction: discord.Interaction):
        """/ticket reopen"""
        await interaction.response.defer()
        channel_id = str(interaction.channel.id)
        if channel_id not in self.tickets:
            await interaction.followup.send("❌ Questo non è un canale ticket!", ephemeral=True)
            return

        ticket = self.tickets[channel_id]
        staff_role_id = self.config.get("staff_role_id")
        is_staff = False
        if staff_role_id:
            staff_role = interaction.guild.get_role(staff_role_id)
            is_staff = staff_role in interaction.user.roles if staff_role else False

        if not is_staff and not interaction.user.guild_permissions.administrator:
            await interaction.followup.send("❌ Solo lo staff o un admin può riaprire i ticket!", ephemeral=True)
            return

        if ticket.get('status') != 'closed':
            await interaction.followup.send("❌ Questo ticket non è chiuso!", ephemeral=True)
            return

        ticket['status'] = 'open'
        self.save_tickets()

        author = interaction.guild.get_member(ticket['author'])
        if author:
            try:
                await interaction.channel.set_permissions(author, read_messages=True, send_messages=True)
            except Exception:
                pass

        embed = discord.Embed(
            title="🔓 Ticket Riaperto",
            description=f"Il ticket è stato riaperto da {interaction.user.mention}\nPuoi scrivere nuovi messaggi.",
            color=0x2ECC71
        )
        try:
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception:
            try:
                await interaction.channel.send("✅ Ticket riaperto.")
            except Exception:
                pass

        try:
            await interaction.channel.send(embed=embed)
        except Exception:
            pass

    async def delete_ticket(self, interaction: discord.Interaction):
        """/ticket delete"""
        try:
            await interaction.response.defer(ephemeral=True)
        except Exception:
            pass

        channel_id = str(interaction.channel.id)
        if channel_id not in self.tickets:
            await interaction.followup.send("❌ Questo non è un canale ticket!", ephemeral=True)
            return

        ticket = self.tickets[channel_id]
        staff_role_id = self.config.get("staff_role_id")
        is_staff = False
        if staff_role_id:
            staff_role = interaction.guild.get_role(staff_role_id)
            is_staff = staff_role in interaction.user.roles if staff_role else False

        if not is_staff and not interaction.user.guild_permissions.administrator:
            await interaction.followup.send("❌ Solo lo staff o un admin può eliminare i ticket!", ephemeral=True)
            return

        try:
            del self.tickets[channel_id]
            self.save_tickets()
            await interaction.channel.delete(reason=f"Ticket eliminato da {interaction.user}")
        except Exception as e:
            try:
                await interaction.followup.send(f"❌ Errore nell'eliminazione del canale: {e}", ephemeral=True)
            except Exception:
                pass

    # ---------- Classic (text) commands for ticket management ----------
    @commands.command(name="add_member")
    @commands.has_permissions(manage_channels=True)
    async def add_member(self, ctx: commands.Context, member: discord.Member):
        """Aggiunge un utente al ticket (comando testuale)"""
        channel_id = str(ctx.channel.id)
        if channel_id not in self.tickets:
            await ctx.send("❌ Questo non è un canale ticket!")
            return

        ticket = self.tickets[channel_id]
        if ctx.author.id != ticket['author'] and not ctx.author.guild_permissions.administrator:
            await ctx.send("❌ Solo l'autore del ticket o un admin può aggiungere utenti!")
            return

        if member.id in ticket.get('members', []):
            await ctx.send("❌ Questo utente è già nel ticket!")
            return

        ticket.setdefault('members', []).append(member.id)
        self.save_tickets()
        await ctx.channel.set_permissions(member, read_messages=True, send_messages=True)
        await ctx.send(f"✅ {member.mention} è stato aggiunto al ticket.")

    @commands.command(name="remove_member")
    @commands.has_permissions(manage_channels=True)
    async def remove_member(self, ctx: commands.Context, member: discord.Member):
        """Rimuove un utente dal ticket (comando testuale)"""
        channel_id = str(ctx.channel.id)
        if channel_id not in self.tickets:
            await ctx.send("❌ Questo non è un canale ticket!")
            return

        ticket = self.tickets[channel_id]
        if ctx.author.id != ticket['author'] and not ctx.author.guild_permissions.administrator:
            await ctx.send("❌ Solo l'autore del ticket o un admin può rimuovere utenti!")
            return

        if member.id not in ticket.get('members', []):
            await ctx.send("❌ Questo utente non è nel ticket!")
            return

        ticket['members'].remove(member.id)
        self.save_tickets()
        await ctx.channel.set_permissions(member, overwrite=None)
        await ctx.send(f"✅ {member.mention} è stato rimosso dal ticket.")

    @commands.command(name="list_tickets")
    async def list_tickets(self, ctx: commands.Context):
        """Mostra tutti i tuoi ticket aperti (comando testuale)"""
        user_tickets = [(tid, t) for tid, t in self.tickets.items() if t.get('author') == ctx.author.id and t.get('status') == 'open']
        if not user_tickets:
            await ctx.send("❌ Non hai ticket aperti!")
            return

        embed = discord.Embed(title="I Tuoi Ticket Aperti", description=f"Totale: {len(user_tickets)}", color=0x3498DB)
        for ticket_id, ticket in user_tickets:
            channel = ctx.guild.get_channel(int(ticket_id))
            created_date = datetime.fromisoformat(ticket.get('created_at')).strftime("%d/%m/%Y %H:%M")
            embed.add_field(name=f"{ticket.get('topic', 'Ticket')}", value=f"ID: {ticket_id}\nCreato: {created_date}\nCanale: {channel.mention if channel else 'Non trovato'}", inline=False)
        await ctx.send(embed=embed)

    @commands.command(name="ticket_help")
    async def ticket_help(self, ctx: commands.Context):
        """Mostra la guida ai comandi (testuale)"""
        embed = discord.Embed(title="Sistema Tickets", description="Usa i comandi seguenti:", color=0x3498DB)
        embed.add_field(name="/ticket create <argomento>", value="Crea un nuovo ticket", inline=False)
        embed.add_field(name="/ticket close", value="Chiude il ticket nel canale attuale", inline=False)
        embed.add_field(name="/ticket add_member <utente>", value="Aggiungi un utente al ticket (testuale)", inline=False)
        embed.add_field(name="/ticket remove_member <utente>", value="Rimuovi un utente dal ticket (testuale)", inline=False)
        embed.add_field(name="/ticket list", value="Mostra tutti i tuoi ticket aperti", inline=False)
        embed.add_field(name="/ticket panel", value="Mostra il pannello per creare ticket", inline=False)
        embed.add_field(name="/ticket reopen", value="Riapri un ticket chiuso (solo staff)", inline=False)
        await ctx.send(embed=embed)

    # Optional helper to add staff role to the channel (text command)
    @commands.command(name="add_staff_role")
    @commands.has_permissions(administrator=True)
    async def add_staff_role(self, ctx: commands.Context):
        """Aggiunge il ruolo staff al ticket attuale (testuale)"""
        channel_id = str(ctx.channel.id)
        if channel_id not in self.tickets:
            await ctx.send("❌ Questo non è un canale ticket!")
            return

        staff_role_id = self.config.get("staff_role_id")
        if not staff_role_id:
            await ctx.send("❌ Ruolo staff non configurato in config.json!")
            return

        staff_role = ctx.guild.get_role(staff_role_id)
        if not staff_role:
            await ctx.send("❌ Ruolo staff non trovato nel server!")
            return

        await ctx.channel.set_permissions(staff_role, read_messages=True, send_messages=True)
        await ctx.send(f"✅ {staff_role.mention} può ora visualizzare e scrivere in questo ticket")

# Setup function for extension
async def setup(bot: commands.Bot):
    await bot.add_cog(Tickets(bot))
