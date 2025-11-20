import discord
from discord import app_commands
from discord.ext import commands

# Use explicit relative import to avoid path issues.
from .console_logger import logger

categories = {
    'moderation': {
        'emoji': '🛡️',
        'name': 'Moderazione',
        'commands': [
            '\\- `/ban` <utente> [reason] - Banna un membro',
            '\\- `/kick` <utente> - Kicka un membro',
            '\\- `/mute` <utente> - Muta un membro',
            '\\- `/unmute` <utente> - Smuta un membro',
            '\\- `/warn` <utente> - Aggiungi un warn',
            '\\- `/warn add` <utente> - Rimuovi un warn',
            '\\- `/warn list` <utente> - Mostra i warn di un utente',
            '\\- `/warn clear` <utente> - Rimuovi tutti i warn',
            '\\- `/listban` - Mostra i ban',
            '\\- `/checkban` <id utente> - Controlla se un utente è bannato',
            '\\- `/checkmute` <utente> - Controlla se un utente è mutato',
            '\\- `/nick` <nick> <utente> - Imposta nickname a un utente'
        ]
    },
    'ticket': {
        'emoji': '🎫',
        'name': 'Ticket',
        'commands': [
            '\\- `/ticketpanel` - Crea pannello ticket',
            '\\- `/close` - Chiudi ticket',
            '\\- `/transcript` <id ticket> - Visualizza transcript di un ticket',
            '\\- `/add` <utente> - Aggiungi utente al ticket',
            '\\- `/remove` <utente> - Rimuovi utente dal ticket',
            '\\- `/rename` <nome> - Rinomina ticket',
            '\\- `/blacklist` <utente> - Blacklist utente',
            '\\- `/sendtranscript` <id ticket> <utente> - Manda transcript di un ticket in DM'
        ]
    },
    'utility': {
        'emoji': '🔧',
        'name': 'Utilità',
        'commands': [
            '\\- `/ping` - Mostra latenza bot',
            '\\- `/uptime` - Mostra uptime bot',
            '\\- `/purge` <messaggi> - Elimina messaggi',
            '\\- `/delete` - Elimina canale',
            '\\- `/rename_channel` <nome> [canale] - Rinomina canale',
            '\\- `/embed` - Crea embed personalizzato',
            '\\- `/regole` - Manda le regole del server',
            '\\- `/verify panel` - Manda messaggio verifica',
			'\\- `/verify forceverify` <membro> - Verifica forzata per un membro'
        ]
    },
    'autorole': {
        'emoji': '🎭',
        'name': 'AutoRole',
        'commands': [
            '\\- `/createreact` <id messaggio> <emoji> <ruolo> - Crea messaggio reazione ruoli'
        ]
    },
    'fun': {
        'emoji': '🎲',
        'name': 'Fun',
        'commands': [
            '\\- `/coinflip` - Lancia una moneta',
            '\\- `/roll` - Tira un dado',
            '\\- `/avatar` [utente] - Mostra l\'avatar di un utente',
            '\\- `/userinfo` [utente] - Mostra informazioni su un utente',
            '\\- `/serverinfo` - Mostra informazioni sul server',
            '\\- `/marry` <utente> - Sposa un utente',
            '\\- `/divorce` <utente> - Divorzia da un utente',
            '\\- `/relationship` [utente] - Mostra relazioni'
        ]
    },
    'tts': {
        'emoji': '📝',
        'name': 'TTS',
        'commands': [
            '\\- `/tts say` <messaggio> - Usa TTS',
            '\\- `/tts voice` <voce> - Imposta voce',
            '\\- `/tts volume` <volume> - Cambia volume',
            '\\- `/tts stop` - Ferma TTS'
        ]
    },
    'cw': {
        'emoji': '📆',
        'name': 'Clan Wars',
        'commands': [
            '\\- `/cwend` - Termina partita CW',
            '\\- `/ruleset` - Mostra ruleset',
            '\\- `/setruleset` - Imposta ruleset',
            '\\- `/cw` <numero> <data> <ora> <rossi> <verdi> <mappa> <recap> <vincitore> - Invia punteggio CW',
        ]
    },
    'giveaway': {
        'emoji': '🎉',
        'name': 'Giveaway',
        'commands': [
            '\\- `/giveaway create` <premio> <durata> [numero vincitori]- Crea giveaway',
            '\\- `/giveaway remove` <id giveaway> <utente> - Rimuovi forzatamente un membro dal giveaway (solo owner o admin)',
            '\\- `/giveaway reroll` <id giveaway> - Estrai nuovi vincitori aggiuntivi (non sostituisce i precedenti)',
            '\\- `/giveaway end` <id giveaway> - Termina un giveaway immediatamente (solo owner o admin)',
            '\\- `/giveaway blacklist add` <utente> - Impedisci ad utenti di entrare nei giveaway',
            '\\- `/giveaway blacklist remove` <utente> - Permetti ad un utente blacklistato di entrare nei giveaway',
            '\\- `/giveaway blacklist list` - Mostra la blacklist'
        ]
    },
    'bday': {
        'emoji': '🎁',
        'name': 'Birthday',
        'commands': [
            '\\- `/birthday set` <data> - Imposta compleanno',
            '\\- `/birthday remove` - Rimuovi compleanno',
            '\\- `/birthday when` [utente] - Mostra compleanno di un utente',
            '\\- `/birthday next` - Mostra i prossimi compleanni',
        ]
    },
    'rep': {
        'emoji': '✅',
        'name': 'Reputation',
        'commands': [
            '\\- `/rep add` (`+rep`) <utente> [motivo] - Aggiungi reputation',
            '\\- `/rep remove` (`-rep`) <utente> [motivo] - Rimuovi reputation',
            '\\- `/rep show` [utente] - Mostra reputation di un utente',
        ]
    },
    'reminder': {
        'emoji': '🔔',
        'name': 'Reminders',
        'commands': [
            '\\- `/remind add` <quando> <messaggio> [manda in dm] - Crea promemoria',
            '\\- `/remind delete` <id> - Rimuovi promemoria',
            '\\- `/remind list` - Mostra promemoria',
        ]
    },
    'counters': {
        'emoji': '🔢',
        'name': 'Counters',
        'commands': [
            '\\- `/counter start` [tipi] - Crea e avvia i counter (es. total_members,role_members,bots)',
            '\\- `/counter stop` - Ferma ed elimina i counter',
            '\\- `/counter enable` <tipo> [canale] - Abilita un counter su un canale',
            '\\- `/counter disable` <tipo> - Disabilita un counter',
            '\\- `/counter setname` <tipo> <template> - Imposta il nome (usa {count})',
            '\\- `/counter setrole` <ruolo> - Imposta il ruolo per `role_members`',
            '\\- `/counter list` - Elenca i counter attivi',
            '\\- `/counter migrate` - Migra i counter creati con il vecchio sistema (se trovati)'
        ]
    },
    'levels': {
        'emoji': '📈',
        'name': 'Livelli',
        'commands': [
            '`Coming Soon...` 👀',
        ]
    },
    'coralmc': {
        'emoji': '<:VL_CoralMC:1434320425592033391>',
        'name': 'CoralMC',
        'commands': [
            '`Coming Soon...` 👀',
        ]
    },
    'stats': {
        'emoji': '📜',
        'name': 'Stats',
        'commands': [
            '`Coming Soon...` 👀',
        ]
    },
    'logs': {
        'emoji': '⚙️',
        'name': 'Logs',
        'commands': [
            '\\- `/logs` - Visualizza file di log',
            '\\- `/dellogs` - Elimina file di log',
            '\\- `/setlogchannel` [tipo di log] <id canale> - Imposta canali di log'
        ]
    },
    'reload': {
        'emoji': '🔄',
        'name': 'Reload',
        'commands': [
            '\\- `/reloadlog` - Ricarica config di log',
            '\\- `/reloadticket` - Ricarica config di ticket',
            '\\- `/reloadmod` - Ricarica config di moderazione',
            '\\- `/reloadcw` - Ricarica config di CW',
            '\\- `/reloadautorole` - Ricarica config di AutoRole',
            '\\- `/reloadregole` - Ricarica config di regole',
            '\\- `/reloadconfig` - Ricarica config generale',
            '\\- `/reloadall` - Ricarica tutte le configurazioni'
        ]
    }
}

class HelpSelectView(discord.ui.View):
    def __init__(self, author_id, bot):
        super().__init__(timeout=300)
        self.author_id = author_id
        self.bot = bot

        options = [discord.SelectOption(label='Tutti', value='all', emoji='📋')]
        for key, cat in categories.items():
            emoji_value = cat.get('emoji')
            try:
                # Support for custom emojis like <:Name:123> or <a:Name:123>
                if isinstance(emoji_value, str) and emoji_value.startswith('<') and emoji_value.endswith('>'):
                    opt_emoji = discord.PartialEmoji.from_str(emoji_value)
                else:
                    opt_emoji = emoji_value
            except Exception:
                opt_emoji = emoji_value
            options.append(discord.SelectOption(label=cat['name'], value=key, emoji=opt_emoji))

        self.select = discord.ui.Select(placeholder='Seleziona una categoria...', options=options)
        self.select.callback = self.select_callback
        self.add_item(self.select)

    async def select_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message('❌ Solo chi ha eseguito il comando può usare questo menu!', ephemeral=True)
            return

        selected = self.select.values[0]

        embed = discord.Embed(
            title='📋 Comandi Disponibili',
            color=0x00ff00
        )

        if selected == 'all':
            embed.description = 'Ecco una lista di tutti i comandi slash disponibili su questo bot:'
            for key, cat in categories.items():
                embed.add_field(
                    name=f"{cat['emoji']} {cat['name']}",
                    value='\n'.join(cat['commands']),
                    inline=False
                )
        else:
            cat = categories[selected]
            embed.title = f"{cat['emoji']} {cat['name']}"
            embed.description = f"Comandi disponibili nella categoria **{cat['name']}**:"
            embed.add_field(
                name='Comandi',
                value='\n'.join(cat['commands']),
                inline=False
            )

        embed.set_footer(text='Valiance Bot | "<campo>" indica un campo obbligatorio; "[campo]" indica un campo opzionale.')

        await interaction.response.edit_message(embed=embed, view=self)

class HelpCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name='help', description='Mostra una lista di tutti i comandi slash disponibili')
    async def slash_help(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title='📋 Comandi Disponibili',
            description='**Help** | **Valiance**\n\nBenvenuto nel pannello comandi di **Valiance**.\nQuesto bot è stato progettato per offrire strumenti intuitivi, affidabili e sempre aggiornati per la tua community Discord.\n\nUtilizza il menu sottostante per navigare tra le varie categorie e scoprire tutti i comandi disponibili.\nOgni sezione contiene descrizioni dettagliate e parametri d’uso per aiutarti a sfruttare al meglio ogni funzione.\n\n⚙️ | Developer: `indifferenzah`\n<:VL_Discord:1437134976217911407> | Discord: https://discord.gg/GVMGZuGZ8F\n🔗 | Sito: https://valiancev2.vercel.app/\n-# 💡 | Per suggerimenti o supporto apri un ticket.',
            color=0x00ff00
        )

        embed.set_footer(text='Valiance Bot | "<campo>" indica un campo obbligatorio; "[campo]" indica un campo opzionale.')

        view = HelpSelectView(interaction.user.id, self.bot)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        logger.info(f'Comando /help usato da {interaction.user.name}#{interaction.user.discriminator} ({interaction.user.id}) in {interaction.guild.name}')

async def setup(bot):
    await bot.add_cog(HelpCog(bot))
