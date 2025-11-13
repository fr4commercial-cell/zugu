import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import json
import os
import asyncio

from bot_utils import owner_or_has_permissions, is_owner

class TicketCategoryView(discord.ui.View):
    def __init__(self, categories, cog):
        super().__init__(timeout=None)
        self.categories = categories
        self.cog = cog
        
        for category in categories:
            self.add_item(TicketCategoryButton(category, cog))

class TicketCategoryButton(discord.ui.Button):
    def __init__(self, category, cog):
        super().__init__(
            label=category["name"],
            emoji=category["emoji"],
            style=discord.ButtonStyle.primary,
            custom_id=f"ticket_create_{category['name'].lower().replace(' ', '_')}"
        )
        self.category = category
        self.cog = cog
    
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        # Verifica se esiste la categoria Tickets
        category_obj = discord.utils.get(interaction.guild.categories, name="Tickets")
        if not category_obj:
            try:
                category_obj = await interaction.guild.create_category("Tickets")
            except Exception as e:
                await interaction.followup.send(f"❌ Errore nella creazione della categoria: {e}", ephemeral=True)
                return
        
        # Crea il canale del ticket
        channel_name = f"ticket-{interaction.user.name.lower()}-{len(self.cog.tickets) + 1}"
        try:
            overwrites = {
                interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }
            
            # Aggiungi il ruolo staff se configurato
            staff_role_id = self.cog.config.get("staff_role_id")
            if staff_role_id:
                staff_role = interaction.guild.get_role(staff_role_id)
                if staff_role:
                    overwrites[staff_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
            
            ticket_channel = await category_obj.create_text_channel(
                channel_name,
                overwrites=overwrites
            )
            
            # Salva le informazioni del ticket
            ticket_id = str(ticket_channel.id)
            self.cog.tickets[ticket_id] = {
                'author': interaction.user.id,
                'topic': self.category['name'],
                'category': self.category['name'],
                'created_at': datetime.now().isoformat(),
                'members': [interaction.user.id],
                'status': 'open'
            }
            self.cog.save_tickets()
            
            # Invia il messaggio di benvenuto nel ticket
            embed = discord.Embed(
                title=f"Ticket: {self.category['name']}",
                description=self.category['description'],
                color=self.category['color']
            )
            embed.add_field(name="ID Ticket", value=ticket_id, inline=False)
            embed.add_field(name="Data Creazione", value=datetime.now().strftime("%d/%m/%Y %H:%M:%S"), inline=False)
            embed.set_footer(text="Usa /ticket close per chiudere il ticket")
            
            await ticket_channel.send(embed=embed)
            await interaction.followup.send(f"✅ Ticket creato: {ticket_channel.mention}", ephemeral=True)
        
        except Exception as e:
            await interaction.followup.send(f"❌ Errore nella creazione del ticket: {e}", ephemeral=True)

class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.tickets_file = 'tickets.json'
        self.load_tickets()
        self.load_config()

    def load_tickets(self):
        """Carica i tickets salvati da file"""
        if os.path.exists(self.tickets_file):
            with open(self.tickets_file, 'r', encoding='utf-8') as f:
                self.tickets = json.load(f)
        else:
            self.tickets = {}

    def load_config(self):
        """Carica la configurazione dei ticket"""
        try:
            with open('config.json', 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        except FileNotFoundError:
            self.config = {"categories": []}

    def save_tickets(self):
        """Salva i tickets su file"""
        with open(self.tickets_file, 'w', encoding='utf-8') as f:
            json.dump(self.tickets, f, indent=4, ensure_ascii=False)

    def save_config(self):
        """Salva la configurazione"""
        with open('config.json', 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)

    @commands.Cog.listener()
    async def on_ready(self):
        """Evento che si attiva quando il bot è pronto"""
        # Ricaricare il pannello salvato
        panel_msg_id = self.config.get("panel_message_id")
        panel_ch_id = self.config.get("panel_channel_id")
        
        if panel_msg_id and panel_ch_id:
            try:
                channel = self.bot.get_channel(panel_ch_id)
                if channel:
                    # Crea la view con i pulsanti
                    view = TicketCategoryView(self.config.get("categories", []), self)
                    self.bot.add_view(view)
            except Exception as e:
                print(f"Errore nel caricamento del pannello: {e}")

    ticket_group = app_commands.Group(name="ticket", description="Gestisci i tuoi tickets")

    @ticket_group.command(name="create", description="Crea un nuovo ticket")
    async def create_ticket(self, interaction: discord.Interaction, topic: str):
        """Crea un nuovo ticket"""
        await interaction.response.defer()

        # Verifica se esiste la categoria Tickets
        category = discord.utils.get(interaction.guild.categories, name="Tickets")
        if not category:
            try:
                category = await interaction.guild.create_category("Tickets")
            except Exception as e:
                await interaction.followup.send(f"❌ Errore nella creazione della categoria: {e}")
                return

        # Crea il canale del ticket
        channel_name = f"ticket-{interaction.user.name.lower()}-{len(self.tickets) + 1}"
        try:
            overwrites = {
                interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }
            
            # Aggiungi il ruolo staff se configurato
            staff_role_id = self.config.get("staff_role_id")
            if staff_role_id:
                staff_role = interaction.guild.get_role(staff_role_id)
                if staff_role:
                    overwrites[staff_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
                else:
                    print(f"⚠️ Ruolo staff con ID {staff_role_id} non trovato nel server")
            else:
                print("⚠️ staff_role_id non configurato in config.json")
            
            ticket_channel = await category.create_text_channel(
                channel_name,
                overwrites=overwrites
            )

            # Salva le informazioni del ticket
            ticket_id = str(ticket_channel.id)
            self.tickets[ticket_id] = {
                'author': interaction.user.id,
                'topic': topic,
                'created_at': datetime.now().isoformat(),
                'members': [interaction.user.id],
                'status': 'open'
            }
            self.save_tickets()

            # Invia il messaggio di benvenuto nel ticket
            embed = discord.Embed(
                title=f"Ticket: {topic}",
                description=f"Ticket creato da {interaction.user.mention}",
                color=0x2ECC71
            )
            embed.add_field(name="ID Ticket", value=ticket_id, inline=False)
            embed.add_field(name="Data Creazione", value=datetime.now().strftime("%d/%m/%Y %H:%M:%S"), inline=False)
            embed.set_footer(text="Usa /ticket close per chiudere il ticket")

            await ticket_channel.send(embed=embed)
            await interaction.followup.send(f"✅ Ticket creato: {ticket_channel.mention}")

        except Exception as e:
            await interaction.followup.send(f"❌ Errore nella creazione del ticket: {e}")

    @ticket_group.command(name="close", description="Chiude il ticket nel canale attuale")
    async def close_ticket(self, interaction: discord.Interaction):
        """Chiude il ticket nel canale attuale"""
        await interaction.response.defer()
        channel_id = str(interaction.channel.id)
        
        if channel_id not in self.tickets:
            await interaction.followup.send("❌ Questo non è un canale ticket!")
            return

        ticket = self.tickets[channel_id]
        
        # Verifica che sia l'autore o un admin
        if interaction.user.id != ticket['author'] and not interaction.user.guild_permissions.administrator:
            await interaction.followup.send("❌ Solo l'autore del ticket o un admin può chiuderlo!")
            return

        # Chiudi il ticket
        ticket['status'] = 'closed'
        self.save_tickets()

        embed = discord.Embed(
            title="Ticket Chiuso",
            description=f"Il ticket è stato chiuso da {interaction.user.mention}",
            color=0xE74C3C
        )
        await interaction.followup.send(embed=embed)

        # Attendi un po' e poi elimina il canale
        await interaction.channel.send("⏳ Eliminazione in corso tra 10 secondi...")
        await asyncio.sleep(10)
        
        try:
            del self.tickets[channel_id]
            self.save_tickets()
            await interaction.channel.delete(reason=f"Ticket chiuso da {interaction.user}")
        except Exception as e:
            await interaction.channel.send(f"❌ Errore nell'eliminazione del canale: {e}")

    @ticket_group.command(name="add", description="Aggiungi un utente al ticket")
    async def add_member(self, interaction: discord.Interaction, member: discord.Member):
        """Aggiungi un utente al ticket"""
        await interaction.response.defer()
        channel_id = str(interaction.channel.id)
        
        if channel_id not in self.tickets:
            await interaction.followup.send("❌ Questo non è un canale ticket!")
            return

        ticket = self.tickets[channel_id]
        
        # Verifica i permessi
        if interaction.user.id != ticket['author'] and not interaction.user.guild_permissions.administrator:
            await interaction.followup.send("❌ Solo l'autore del ticket o un admin può aggiungere utenti!")
            return

        if member.id in ticket['members']:
            await interaction.followup.send("❌ Questo utente è già nel ticket!")
            return

        # Aggiungi l'utente
        ticket['members'].append(member.id)
        self.save_tickets()

        # Aggiorna i permessi del canale
        await interaction.channel.set_permissions(member, read_messages=True, send_messages=True)

        embed = discord.Embed(
            title="Utente Aggiunto",
            description=f"{member.mention} è stato aggiunto al ticket",
            color=0x2ECC71
        )
        await interaction.followup.send(embed=embed)

    @ticket_group.command(name="remove", description="Rimuovi un utente dal ticket")
    async def remove_member(self, interaction: discord.Interaction, member: discord.Member):
        """Rimuovi un utente dal ticket"""
        await interaction.response.defer()
        channel_id = str(interaction.channel.id)
        
        if channel_id not in self.tickets:
            await interaction.followup.send("❌ Questo non è un canale ticket!")
            return

        ticket = self.tickets[channel_id]
        
        # Verifica i permessi
        if interaction.user.id != ticket['author'] and not interaction.user.guild_permissions.administrator:
            await interaction.followup.send("❌ Solo l'autore del ticket o un admin può rimuovere utenti!")
            return

        if member.id not in ticket['members']:
            await interaction.followup.send("❌ Questo utente non è nel ticket!")
            return

        # Rimuovi l'utente
        ticket['members'].remove(member.id)
        self.save_tickets()

        # Rimuovi i permessi del canale
        await interaction.channel.set_permissions(member, overwrite=None)

        embed = discord.Embed(
            title="Utente Rimosso",
            description=f"{member.mention} è stato rimosso dal ticket",
            color=0xE74C3C
        )
        await interaction.followup.send(embed=embed)

    @ticket_group.command(name="addstaff", description="Aggiungi il ruolo staff al ticket")
    @owner_or_has_permissions(administrator=True)
    async def add_staff_role(self, interaction: discord.Interaction):
        """Aggiungi il ruolo staff al ticket attuale"""
        await interaction.response.defer()
        channel_id = str(interaction.channel.id)
        
        if channel_id not in self.tickets:
            await interaction.followup.send("❌ Questo non è un canale ticket!")
            return

        staff_role_id = self.config.get("staff_role_id")
        if not staff_role_id:
            await interaction.followup.send("❌ Ruolo staff non configurato in config.json!")
            return

        staff_role = interaction.guild.get_role(staff_role_id)
        if not staff_role:
            await interaction.followup.send("❌ Ruolo staff non trovato nel server!")
            return

        # Aggiungi i permessi al ruolo
        await interaction.channel.set_permissions(staff_role, read_messages=True, send_messages=True)

        embed = discord.Embed(
            title="Ruolo Staff Aggiunto",
            description=f"{staff_role.mention} può ora visualizzare e scrivere in questo ticket",
            color=0x2ECC71
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @ticket_group.command(name="list", description="Mostra tutti i tuoi ticket aperti")
    @owner_or_has_permissions(administrator=True)
    async def list_tickets(self, interaction: discord.Interaction):
        """Mostra tutti i tuoi ticket aperti"""
        await interaction.response.defer()
        user_tickets = [
            (tid, t) for tid, t in self.tickets.items() 
            if t['author'] == interaction.user.id and t['status'] == 'open'
        ]

        if not user_tickets:
            await interaction.followup.send("❌ Non hai ticket aperti!")
            return

        embed = discord.Embed(
            title="I Tuoi Ticket Aperti",
            description=f"Totale: {len(user_tickets)}",
            color=0x3498DB
        )

        for ticket_id, ticket in user_tickets:
            channel = interaction.guild.get_channel(int(ticket_id))
            if channel:
                created_date = datetime.fromisoformat(ticket['created_at']).strftime("%d/%m/%Y %H:%M")
                embed.add_field(
                    name=f"{ticket['topic']}",
                    value=f"ID: {ticket_id}\nCreato: {created_date}\nCanale: {channel.mention}",
                    inline=False
                )

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="ticket_help", description="Mostra la guida ai comandi ticket")
    async def ticket_help(self, interaction: discord.Interaction):
        """Mostra la guida ai comandi"""
        embed = discord.Embed(
            title="Sistema Tickets",
            description="Usa i comandi seguenti:",
            color=0x3498DB
        )
        embed.add_field(name="/ticket create <argomento>", value="Crea un nuovo ticket", inline=False)
        embed.add_field(name="/ticket close", value="Chiude il ticket nel canale attuale", inline=False)
        embed.add_field(name="/ticket add <utente>", value="Aggiungi un utente al ticket", inline=False)
        embed.add_field(name="/ticket remove <utente>", value="Rimuovi un utente dal ticket", inline=False)
        embed.add_field(name="/ticket list", value="Mostra tutti i tuoi ticket aperti", inline=False)
        embed.add_field(name="/ticket panel", value="Mostra il pannello per creare ticket", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @ticket_group.command(name="panel", description="Mostra il pannello per creare ticket")
    @app_commands.checks.has_permissions(administrator=True)
    async def ticket_panel(self, interaction: discord.Interaction):
        """Mostra il pannello interattivo per creare ticket"""
        await interaction.response.defer()
        
        if not self.config.get("categories"):
            await interaction.followup.send("❌ Nessuna categoria di ticket configurata in config.json!")
            return
        
        # Crea l'embed del pannello
        embed = discord.Embed(
            title="📋 Pannello Ticket",
            description="Clicca su uno dei pulsanti sottostanti per creare un ticket:",
            color=0x3498DB
        )
        
        for category in self.config["categories"]:
            emoji = category.get("emoji", "📝")
            embed.add_field(
                name=f"{emoji} {category['name']}",
                value=category.get('description', 'Nessuna descrizione'),
                inline=False
            )
        
        # Crea la view con i pulsanti delle categorie
        view = TicketCategoryView(self.config["categories"], self)
        
        # Invia il messaggio
        message = await interaction.followup.send(embed=embed, view=view)
        
        # Salva l'ID del messaggio e del canale in config
        self.config["panel_message_id"] = message.id
        self.config["panel_channel_id"] = interaction.channel.id
        self.save_config()
        
        await interaction.followup.send("✅ Pannello salvato! Rimarrà attivo anche dopo i riavvii del bot.", ephemeral=True)

    def get_ticket_group(self):
        return self.ticket_group

async def setup(bot):
    await bot.add_cog(Tickets(bot))
