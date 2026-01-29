import os
import certifi
from dotenv import load_dotenv

load_dotenv()

# SSL certificate for secure requests
os.environ["SSL_CERT_FILE"] = certifi.where()

# Bot configuration
DISCORD_TOKEN = os.environ.get('DISCORD_TOKEN')
COMMAND_PREFIX = '!'

# Valorant news URLs
VALORANT_NEWS_URL = 'https://playvalorant.com/en-us/news/game-updates/'

# Selectors (update these if the website changes)
ARTICLE_LINK_SELECTOR = '.sc-b988531e-0.bvEIZU.sc-d043b2-0.bZMlAb.sc-8e176a18-5.hpxXxJ.action'
ARTICLE_CONTENT_SELECTOR = '[data-testid="rich-text"]'

# Discord limits
MAX_MESSAGE_LENGTH = 1900
