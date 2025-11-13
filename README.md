# Zugu - Bot Discord con Sistema di Tickets

Un bot Discord in Python con un sistema completo di tickets per il supporto.

## ⚙️ Setup

### 1. Installa le dipendenze
```bash
pip install -r requirements.txt
```

### 2. Configura il token
1. Vai su [Discord Developer Portal](https://discord.com/developers/applications)
2. Crea una nuova applicazione
3. Vai su "Bot" e clicca "Add Bot"
4. Copia il token del bot
5. Apri `.env` e sostituisci `YOUR_BOT_TOKEN_HERE` con il tuo token

### 3. Dai i permessi necessari al bot
Il bot ha bisogno di questi permessi:
- Gestire canali
- Creare canali
- Leggere messaggi
- Inviare messaggi
- Gestire ruoli/permessi

### 4. Avvia il bot
```bash
python main.py
```

## 📋 Comandi

### Tickets
- `!ticket` - Mostra la guida ai comandi
- `!ticket create <argomento>` - Crea un nuovo ticket
- `!ticket close` - Chiude il ticket (solo nel canale ticket)
- `!ticket add <@utente>` - Aggiungi un utente al ticket
- `!ticket remove <@utente>` - Rimuovi un utente dal ticket
- `!ticket list` - Mostra i tuoi ticket aperti

## 🎯 Caratteristiche

✅ Creazione automatica di canali per ticket
✅ Gestione permessi per canale
✅ Aggiunta/rimozione utenti da ticket
✅ Persistenza dei dati (salvataggio su file JSON)
✅ Embed colorati e informativi
✅ Sistema di logging
✅ Gestione errori

## 📁 Struttura del Progetto

```
zugu/
├── main.py              # File principale del bot
├── config.py            # Configurazione
├── requirements.txt     # Dipendenze
├── .env                 # Variabili di ambiente
├── tickets.json         # Database dei tickets
└── cogs/
    └── tickets.py       # Cog per la gestione tickets
```

## ⚡ Note

- I ticket sono salvati in `tickets.json`
- Quando un ticket viene chiuso, il canale viene eliminato automaticamente
- Solo l'autore del ticket e gli admin possono chiudere/gestire il ticket
- I ticket vengono creati in una categoria "Tickets" automaticamente

## 🔧 Problemi Comuni

**Il bot non risponde:**
- Verifica che il token sia corretto in `.env`
- Assicurati che il bot abbia i permessi nel server
- Controlla che stia ascoltando i messaggi (intents abilitati)

**Errore con le dipendenze:**
- Aggiorna pip: `python -m pip install --upgrade pip`
- Reinstalla le dipendenze: `pip install -r requirements.txt`

## 📝 Customizzazione

Puoi modificare i colori degli embed in `config.py`:
```python
COLOR_OPEN = 0x2ECC71   # Verde
COLOR_CLOSED = 0xE74C3C # Rosso
COLOR_INFO = 0x3498DB   # Blu
```

Buon uso! 🚀
