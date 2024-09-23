import discord
from discord.ext import commands
import certifi
import os
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium import webdriver



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
    specific_div = driver.find_element(By.CLASS_NAME, 'ContentListingCard-module--contentListingCard--JqMck')

    # Get the href of the most recent news article
    recent_href = specific_div.get_attribute('href')

    # Navigate to the most recent news article
    driver.get(recent_href)

    # Wait for the new page to load
    driver.implicitly_wait(10)

    # Get the HTML content of the new page
    new_page_content = driver.page_source

    # Parse the new page HTML with BeautifulSoup
    new_page_soup = BeautifulSoup(new_page_content, 'html.parser')

    # Retrieve all text content from the div containing the article text
    div_in_href = new_page_soup.find('div', {'class': 'sectionWrapper NewsArticleContent-module--articleSectionWrapper--a5tPH'})
    text_content = div_in_href.get_text()


    # Close the WebDriver
    driver.quit()

    chunks = [text_content[i:i + 2000] for i in range(0, len(text_content), 2000)]

    # Send each chunk as a separate message to the Discord channel
    for chunk in chunks:
        await ctx.send(chunk)
    



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
 



client.run('insert API key') 
