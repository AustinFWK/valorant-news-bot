import discord
from discord.ext import commands
from config import DISCORD_TOKEN, COMMAND_PREFIX
from valorant.scraper import get_latest_patch_notes
from valorant.formatter import smart_chunk
from storage import set_channel, get_channel


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
@commands.has_permissions(administrator=True)
async def setchannel(ctx, game: str):
    """Set the current channel to receive updates for a specific game."""
    valid_games = ['valorant']  # Extendable for future games

    game = game.lower()
    if game not in valid_games:
        await ctx.send(f"Invalid game. Valid options are: {', '.join(valid_games)}")
        return
    
    set_channel(ctx.guild.id, game, ctx.channel.id)
    await ctx.send(f"Channel set for {game} updates.")

@client.command()
async def getchannel(ctx, game: str):
    """Get the channel set for a specific game's updates"""
    game = game.lower()
    channel_id = get_channel(ctx.guild.id, game)

    if channel_id:
        await ctx.send(f"The channel for {game} updates is <#{channel_id}>")
    else:
        await ctx.send(f"No channel set for {game} updates. Use !setchannel to set one.")

@setchannel.error
async def setchannel_error(ctx, error):
    """Error handler for setchannel command."""
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("You do not have permission to use this command.")


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
