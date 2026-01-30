import discord
from discord.ext import commands
from config import DISCORD_TOKEN, COMMAND_PREFIX
from valorant.scraper import get_latest_patch_notes
from valorant.formatter import smart_chunk


# Bot setup
intents = discord.Intents.all()
client = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)


# --- Events ---

@client.event
async def on_ready():
    print("The bot is ready for use")
    print("------------------------")


# --- Commands ---

@client.command()
async def hello(ctx):
    """Simple test command."""
    await ctx.send("hello user")


@client.command()
async def patchnotes(ctx):
    """Fetch and display the latest Valorant patch notes."""

    try:
        text_content, article_url, content_type = get_latest_patch_notes()

        if content_type == 'video':
            await ctx.send(f"🔗 Latest video: {article_url}")
            return

        chunks = smart_chunk(text_content)

        for chunk in chunks:
            await ctx.send(chunk)

        await ctx.send(f"\n\n🔗 Full article: {article_url}")

    except Exception as e:
        await ctx.send(f"Error fetching patch notes: {str(e)}")


# --- Run ---

if __name__ == '__main__':
    client.run(DISCORD_TOKEN)
