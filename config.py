import os
from dotenv import load_dotenv

load_dotenv()

# Bot Configuration
TOKEN = os.getenv('DISCORD_TOKEN')

# Tickets Configuration
TICKETS_CATEGORY_NAME = 'Tickets'
TICKET_LOG_CHANNEL_NAME = 'ticket-logs'

# Embed Colors
COLOR_OPEN = 0x2ECC71  # Green
COLOR_CLOSED = 0xE74C3C  # Red
COLOR_INFO = 0x3498DB  # Blue
