import discord
from discord.ext import commands
import certifi
import os
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium import webdriver

load_dotenv()

os.environ["SSL_CERT_FILE"] = certifi.where()

intents = discord.Intents.all()

client = commands.Bot(command_prefix = '!', intents=intents) 

@client.command()
async def scrape_patch_notes(ctx):
    # Initialize Chrome WebDriver
    driver = webdriver.Chrome()

    # Navigate to the Valorant news page
    driver.get('https://playvalorant.com/en-us/news/game-updates/')

    # Wait for dynamic content to load
    driver.implicitly_wait(5)

    # Get the HTML content after the page is fully loaded
    html_content = driver.page_source

    # Parse the HTML content with BeautifulSoup
    soup = BeautifulSoup(html_content, 'html.parser')

    #this finds the <a> tag with this class and gets the first href
    specific_div = driver.find_element(By.CSS_SELECTOR, '.sc-b988531e-0.bvEIZU.sc-d043b2-0.bZMlAb.sc-8e176a18-5.hpxXxJ.action')

    # Get the href of the most recent news article
    recent_href = specific_div.get_attribute('href')

    # Navigate to the most recent news article
    driver.get(recent_href)

    # Wait for the new page to load
    driver.implicitly_wait(10)

    # Retrieve all text content from the div containing the article text
    content_div = driver.find_element(By.CSS_SELECTOR, '[data-testid="rich-text"]')                                       
    text_content = content_div.text



    # Close the WebDriver
    driver.quit()

    # Format and smart chunk the content
    chunks = smart_chunk(text_content)

    # Send each chunk as a separate message to the Discord channel
    for chunk in chunks:
        await ctx.send(chunk)


def smart_chunk(text, max_length=1900):
    """Split text at natural break points while staying under Discord's limit."""

    # Apply markdown formatting line by line, preserving order
    lines = text.split('\n')
    formatted_lines = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            formatted_lines.append('')
        # Main headers (ALL CAPS like "BUG FIXES", "AGENTS")
        elif stripped.isupper() and len(stripped) < 50:
            formatted_lines.append(f'\n__**{stripped}**__')
        # Sub-headers (short title-case lines like "Harbor", "Fade", "General")
        elif len(stripped) < 30 and stripped.istitle() and not stripped.startswith('Fixed'):
            formatted_lines.append(f'\n**{stripped}**')
        # Bug fix lines - format as bullet points
        elif stripped.startswith('Fixed'):
            formatted_lines.append(f'• {stripped}')
        # Other bullet-point style lines
        elif stripped.startswith(('-', '•', '*')):
            formatted_lines.append(f'• {stripped[1:].strip()}')
        else:
            formatted_lines.append(stripped)

    formatted_text = '\n'.join(formatted_lines)

    # Smart chunking - split at section breaks (double newlines or before headers)
    chunks = []
    current_chunk = ''

    for line in formatted_text.split('\n'):
        # Check if adding this line exceeds the limit
        if len(current_chunk) + len(line) + 1 > max_length:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = line
        else:
            # Start new chunk before major headers to keep sections together
            if line.startswith('__**') and len(current_chunk) > 500:
                chunks.append(current_chunk.strip())
                current_chunk = line
            else:
                current_chunk += '\n' + line if current_chunk else line

    # Don't forget the last chunk
    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks
    



@client.event
async def on_ready():
    print("The bot is ready for use")
    print("------------------------")


@client.command()
async def hello(ctx):
    await ctx.send("hello user")

@client.command()
async def patchnotes(ctx):
     await scrape_patch_notes(ctx.channel)
 

client.run(os.environ.get('DISCORD_TOKEN'))   